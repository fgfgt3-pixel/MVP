"""Confirm detector for onset confirmation using Delta-based relative improvement."""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from ..config_loader import Config, load_config
from ..event_store import EventStore, create_event


class ConfirmDetector:
    """
    Confirm onset candidates based on relative improvement (Delta) analysis.

    Uses Pre vs Now window comparison to validate candidate events
    by checking if relative improvements persist in subsequent data.
    Price axis satisfaction is mandatory.
    """

    def __init__(self, config: Optional[Config] = None, event_store: Optional[EventStore] = None):
        """
        Initialize confirm detector with Delta-based parameters.

        Args:
            config: Configuration object. If None, loads default config.
            event_store: EventStore instance. If None, creates default one.
        """
        self.config = config or load_config()
        self.event_store = event_store or EventStore()

        # Extract confirmation parameters
        self.window_s = self.config.confirm.window_s
        self.min_axes = self.config.confirm.min_axes
        self.persistent_n = getattr(self.config.confirm, 'persistent_n', 2)
        self.exclude_cand_point = getattr(self.config.confirm, 'exclude_cand_point', True)

        # Delta-based parameters
        self.require_price_axis = getattr(self.config.confirm, 'require_price_axis', True)
        self.pre_window_s = getattr(self.config.confirm, 'pre_window_s', 5)

        # Delta thresholds
        delta_config = getattr(self.config.confirm, 'delta', {})
        if hasattr(delta_config, 'ret_min'):
            # Pydantic model
            self.delta_ret_min = delta_config.ret_min
            self.delta_zvol_min = delta_config.zvol_min
            self.delta_spread_drop = delta_config.spread_drop
        else:
            # Dict
            self.delta_ret_min = delta_config.get('ret_min', 0.0005)
            self.delta_zvol_min = delta_config.get('zvol_min', 0.5)
            self.delta_spread_drop = delta_config.get('spread_drop', 0.0005)

    def confirm_candidates(
        self,
        features_df: pd.DataFrame,
        candidate_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Confirm onset candidates using Delta-based relative improvement analysis.

        Args:
            features_df: DataFrame with calculated features from core_indicators.
            candidate_events: List of candidate events from candidate_detector.

        Returns:
            List[Dict]: List of confirmed onset events.
        """
        if features_df.empty or not candidate_events:
            return []

        confirmed_events = []

        # Required columns check
        required_cols = ['ts', 'stock_code', 'ret_1s', 'z_vol_1s', 'spread', 'microprice_slope']
        missing_cols = set(required_cols) - set(features_df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns for confirmation: {missing_cols}")

        # Sort features by timestamp for efficient lookup
        features_df = features_df.sort_values('ts')

        for candidate in candidate_events:
            candidate_ts = candidate['ts']
            stock_code = candidate['stock_code']

            # Convert candidate timestamp to datetime for comparison
            if isinstance(candidate_ts, (int, float)):
                # Check if timestamp is in seconds or milliseconds
                if candidate_ts < 1e10:  # Likely seconds
                    candidate_dt = pd.to_datetime(candidate_ts, unit='s', utc=True).tz_convert('Asia/Seoul')
                else:  # Likely milliseconds
                    candidate_dt = pd.to_datetime(candidate_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')
            else:
                candidate_dt = pd.to_datetime(candidate_ts)

            # Extract pre-window (before candidate)
            pre_window_start = candidate_dt - pd.Timedelta(seconds=self.pre_window_s)
            pre_window_end = candidate_dt - pd.Timedelta(milliseconds=1)

            pre_window_features = features_df[
                (features_df['ts'] > pre_window_start) &
                (features_df['ts'] <= pre_window_end) &
                (features_df['stock_code'].astype(str) == str(stock_code))
            ]

            # Extract confirmation window (after candidate)
            if self.exclude_cand_point:
                window_start = candidate_dt + pd.Timedelta(milliseconds=1)
            else:
                window_start = candidate_dt
            window_end = candidate_dt + pd.Timedelta(seconds=self.window_s)

            window_features = features_df[
                (features_df['ts'] > window_start) &
                (features_df['ts'] <= window_end) &
                (features_df['stock_code'].astype(str) == str(stock_code))
            ]

            if window_features.empty or pre_window_features.empty:
                continue

            # Check Delta-based confirmation conditions
            confirmation_result = self._check_delta_confirmation(
                pre_window_features,
                window_features
            )

            if confirmation_result['confirmed'] and confirmation_result['confirm_ts'] is not None:
                # Create confirmed event
                confirm_ts = confirmation_result['confirm_ts']
                if hasattr(confirm_ts, 'timestamp'):
                    confirm_ts = confirm_ts.timestamp()
                else:
                    confirm_ts = float(confirm_ts)

                confirmed_event = create_event(
                    timestamp=confirm_ts,
                    event_type="onset_confirmed",
                    stock_code=str(stock_code),
                    confirmed_from=float(candidate_ts),
                    evidence={
                        "axes": confirmation_result["satisfied_axes"],
                        "onset_strength": confirmation_result["onset_strength"],
                        "ret_1s": confirmation_result["evidence"]["ret_1s"],
                        "z_vol_1s": confirmation_result["evidence"]["z_vol_1s"],
                        "spread": confirmation_result["evidence"]["spread"],
                        "microprice_slope": confirmation_result["evidence"]["microprice_slope"],
                        "delta_ret": confirmation_result["evidence"]["delta_ret"],
                        "delta_zvol": confirmation_result["evidence"]["delta_zvol"],
                        "delta_spread": confirmation_result["evidence"]["delta_spread"]
                    }
                )

                confirmed_events.append(confirmed_event)

        return confirmed_events

    def _check_delta_confirmation(
        self,
        pre_window_df: pd.DataFrame,
        window_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Check if Delta-based confirmation conditions are satisfied.

        Args:
            pre_window_df: Features DataFrame for pre-window (before candidate).
            window_df: Features DataFrame for confirmation window (after candidate).

        Returns:
            Dict: Confirmation result with details.
        """
        if window_df.empty or pre_window_df.empty:
            return {
                "confirmed": False,
                "satisfied_axes": [],
                "onset_strength": 0.0,
                "evidence": {},
                "confirm_ts": None,
                "window_size": 0
            }

        # Calculate pre-window baselines (median for stability)
        pre_ret = pre_window_df['ret_1s'].median()
        pre_zvol = pre_window_df['z_vol_1s'].median()
        pre_spread = pre_window_df['spread'].median()
        pre_microprice = pre_window_df['microprice_slope'].median()

        # Create boolean arrays for each axis condition (Delta-based)
        # Price axis: MANDATORY - must show improvement in return OR microprice
        price_axis = (
            ((window_df['ret_1s'] - pre_ret) >= self.delta_ret_min) |
            ((window_df['microprice_slope'] - pre_microprice) >= self.delta_ret_min)
        ).astype(int)

        # Volume axis: relative z-score increase
        volume_axis = ((window_df['z_vol_1s'] - pre_zvol) >= self.delta_zvol_min).astype(int)

        # Friction axis: spread reduction (negative delta means improvement)
        friction_axis = ((pre_spread - window_df['spread']) >= self.delta_spread_drop).astype(int)

        # Calculate total satisfied axes per row
        # Price axis is mandatory, so check it separately
        price_satisfied = price_axis.astype(bool)
        other_axes_count = volume_axis + friction_axis

        # Condition: Price MUST be satisfied + at least 1 other axis
        if self.require_price_axis:
            axis_ok = price_satisfied & (other_axes_count >= (self.min_axes - 1))
        else:
            # Fallback to original logic if price not mandatory
            axis_ok = (price_axis + volume_axis + friction_axis) >= self.min_axes

        # Check for persistent confirmation
        if len(axis_ok) < self.persistent_n:
            return {
                "confirmed": False,
                "satisfied_axes": [],
                "onset_strength": 0.0,
                "evidence": {},
                "confirm_ts": None,
                "window_size": len(window_df)
            }

        # Rolling window to check for persistent satisfaction
        persistent_ok = axis_ok.rolling(window=self.persistent_n, min_periods=self.persistent_n).sum() == self.persistent_n

        if not persistent_ok.any():
            return {
                "confirmed": False,
                "satisfied_axes": [],
                "onset_strength": 0.0,
                "evidence": {},
                "confirm_ts": None,
                "window_size": len(window_df)
            }

        # Find EARLIEST occurrence of persistent confirmation (earliest-hit)
        first_hit_idx = persistent_ok.idxmax()
        confirm_ts = window_df.loc[first_hit_idx, 'ts']

        # Convert timestamp to float
        if hasattr(confirm_ts, 'timestamp'):
            confirm_ts_float = confirm_ts.timestamp()
        else:
            confirm_ts_float = float(confirm_ts)

        # Determine which axes were satisfied at confirmation time
        satisfied_axes = []
        confirm_row = window_df.loc[first_hit_idx]

        if price_axis.loc[first_hit_idx]:
            satisfied_axes.append("price")
        if volume_axis.loc[first_hit_idx]:
            satisfied_axes.append("volume")
        if friction_axis.loc[first_hit_idx]:
            satisfied_axes.append("friction")

        # Calculate onset strength (ratio of satisfied axes)
        onset_strength = len(satisfied_axes) / 3.0

        # Evidence from the confirmation row with Delta values
        evidence = {
            "ret_1s": float(confirm_row['ret_1s']),
            "z_vol_1s": float(confirm_row['z_vol_1s']),
            "spread": float(confirm_row['spread']),
            "microprice_slope": float(confirm_row['microprice_slope']),
            "delta_ret": float(confirm_row['ret_1s'] - pre_ret),
            "delta_zvol": float(confirm_row['z_vol_1s'] - pre_zvol),
            "delta_spread": float(pre_spread - confirm_row['spread'])
        }

        return {
            "confirmed": True,
            "satisfied_axes": satisfied_axes,
            "onset_strength": onset_strength,
            "evidence": evidence,
            "confirm_ts": confirm_ts_float,
            "window_size": len(window_df)
        }

    def save_confirmations(self, confirmed_events: List[Dict[str, Any]], filename: Optional[str] = None) -> bool:
        """
        Save confirmed events to EventStore.

        Args:
            confirmed_events: List of confirmed events.
            filename: Optional filename for saving events.

        Returns:
            bool: True if all events saved successfully.
        """
        if not confirmed_events:
            return True

        success_count = 0
        for event in confirmed_events:
            if self.event_store.save_event(event, filename=filename):
                success_count += 1

        return success_count == len(confirmed_events)

    def confirm_and_save(
        self,
        features_df: pd.DataFrame,
        candidate_events: List[Dict[str, Any]],
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Confirm candidates and save them in one operation.

        Args:
            features_df: DataFrame with calculated features.
            candidate_events: List of candidate events.
            filename: Optional filename for saving events.

        Returns:
            Dict: Summary with confirmation count and save status.
        """
        confirmed_events = self.confirm_candidates(features_df, candidate_events)

        if confirmed_events:
            save_success = self.save_confirmations(confirmed_events, filename)
        else:
            save_success = True

        # Calculate confirmation rate and time-to-alert
        confirmation_rate = len(confirmed_events) / len(candidate_events) if candidate_events else 0.0

        # Calculate TTA (Time-to-Alert) statistics
        tta_values = []
        for confirmed in confirmed_events:
            if 'confirmed_from' in confirmed:
                tta_ms = confirmed['ts'] - confirmed['confirmed_from']
                tta_seconds = tta_ms / 1000.0
                tta_values.append(tta_seconds)

        tta_stats = {}
        if tta_values:
            tta_stats = {
                "mean": float(np.mean(tta_values)),
                "median": float(np.median(tta_values)),
                "min": float(np.min(tta_values)),
                "max": float(np.max(tta_values)),
                "p95": float(np.percentile(tta_values, 95)) if len(tta_values) > 1 else float(tta_values[0])
            }

        # Calculate axes distribution
        axes_distribution = {"price": 0, "volume": 0, "friction": 0}
        for event in confirmed_events:
            for axis in event.get('evidence', {}).get('axes', []):
                if axis in axes_distribution:
                    axes_distribution[axis] += 1

        # Normalize to percentages
        if confirmed_events:
            for axis in axes_distribution:
                axes_distribution[axis] = axes_distribution[axis] / len(confirmed_events)

        # Guardrail warnings for unrealistic results
        warnings = []

        # Warning 1: Confirmation rate too high (>95%)
        if confirmation_rate > 0.95:
            warnings.append(f"WARNING: Very high confirmation rate ({confirmation_rate:.1%}). Check Delta thresholds.")

        # Warning 2: Confirmation rate too low (<5%)
        if candidate_events and confirmation_rate < 0.05:
            warnings.append(f"WARNING: Very low confirmation rate ({confirmation_rate:.1%}). Consider relaxing Delta thresholds.")

        # Warning 3: TTA too low (p95 < 0.2s)
        if tta_stats and tta_stats.get('p95', 1.0) < 0.2:
            warnings.append(f"WARNING: TTA p95 too low ({tta_stats['p95']:.2f}s). Check exclude_cand_point setting.")

        # Warning 4: Price axis not always satisfied (should be 100% if mandatory)
        if self.require_price_axis and confirmed_events and axes_distribution['price'] < 1.0:
            warnings.append(f"WARNING: Price axis not satisfied in all confirmations ({axes_distribution['price']:.1%}). Logic error.")

        # Log warnings
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for warning in warnings:
                logger.warning(warning)

        return {
            "candidates_processed": len(candidate_events),
            "confirmations_created": len(confirmed_events),
            "confirmation_rate": confirmation_rate,
            "save_success": save_success,
            "tta_stats": tta_stats,
            "axes_distribution": axes_distribution,
            "events": confirmed_events,
            "warnings": warnings
        }

    def get_confirmation_stats(
        self,
        features_df: pd.DataFrame,
        candidate_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get confirmation statistics without saving events.

        Args:
            features_df: DataFrame with calculated features.
            candidate_events: List of candidate events.

        Returns:
            Dict: Confirmation statistics.
        """
        if not candidate_events:
            return {
                "candidates_processed": 0,
                "confirmations_possible": 0,
                "confirmation_rate": 0.0,
                "axes_stats": {},
                "axes_distribution": {},
                "window_stats": {},
                "delta_stats": {}
            }

        confirmed_events = self.confirm_candidates(features_df, candidate_events)

        # Analyze all candidates for statistics
        axes_satisfied_counts = {"price": 0, "volume": 0, "friction": 0}
        window_sizes = []
        delta_improvements = {"ret": [], "zvol": [], "spread": []}

        for candidate in candidate_events:
            candidate_ts = candidate['ts']
            stock_code = candidate['stock_code']

            # Convert candidate timestamp to datetime
            if isinstance(candidate_ts, (int, float)):
                # Check if timestamp is in seconds or milliseconds
                if candidate_ts < 1e10:  # Likely seconds
                    candidate_dt = pd.to_datetime(candidate_ts, unit='s', utc=True).tz_convert('Asia/Seoul')
                else:  # Likely milliseconds
                    candidate_dt = pd.to_datetime(candidate_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')
            else:
                candidate_dt = pd.to_datetime(candidate_ts)

            # Extract windows
            pre_window_start = candidate_dt - pd.Timedelta(seconds=self.pre_window_s)
            pre_window_end = candidate_dt - pd.Timedelta(milliseconds=1)

            if self.exclude_cand_point:
                window_start = candidate_dt + pd.Timedelta(milliseconds=1)
            else:
                window_start = candidate_dt
            window_end = candidate_dt + pd.Timedelta(seconds=self.window_s)

            pre_window_features = features_df[
                (features_df['ts'] > pre_window_start) &
                (features_df['ts'] <= pre_window_end) &
                (features_df['stock_code'].astype(str) == str(stock_code))
            ]

            window_features = features_df[
                (features_df['ts'] > window_start) &
                (features_df['ts'] <= window_end) &
                (features_df['stock_code'].astype(str) == str(stock_code))
            ]

            if not window_features.empty and not pre_window_features.empty:
                window_sizes.append(len(window_features))
                result = self._check_delta_confirmation(pre_window_features, window_features)

                for axis in result["satisfied_axes"]:
                    if axis in axes_satisfied_counts:
                        axes_satisfied_counts[axis] += 1

                # Collect delta improvements
                if result["evidence"]:
                    delta_improvements["ret"].append(result["evidence"].get("delta_ret", 0))
                    delta_improvements["zvol"].append(result["evidence"].get("delta_zvol", 0))
                    delta_improvements["spread"].append(result["evidence"].get("delta_spread", 0))

        confirmation_rate = len(confirmed_events) / len(candidate_events) if candidate_events else 0.0

        # Calculate axes distribution
        axes_distribution = {"price": 0, "volume": 0, "friction": 0}
        for event in confirmed_events:
            for axis in event.get('evidence', {}).get('axes', []):
                if axis in axes_distribution:
                    axes_distribution[axis] += 1

        if confirmed_events:
            for axis in axes_distribution:
                axes_distribution[axis] = axes_distribution[axis] / len(confirmed_events)

        window_stats = {}
        if window_sizes:
            window_stats = {
                "mean_size": float(np.mean(window_sizes)),
                "min_size": int(np.min(window_sizes)),
                "max_size": int(np.max(window_sizes))
            }

        delta_stats = {}
        for key, values in delta_improvements.items():
            if values:
                delta_stats[key] = {
                    "mean": float(np.mean(values)),
                    "median": float(np.median(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values))
                }

        return {
            "candidates_processed": len(candidate_events),
            "confirmations_possible": len(confirmed_events),
            "confirmation_rate": confirmation_rate,
            "axes_stats": axes_satisfied_counts,
            "axes_distribution": axes_distribution,
            "window_stats": window_stats,
            "delta_stats": delta_stats,
            "config": {
                "window_s": self.window_s,
                "pre_window_s": self.pre_window_s,
                "min_axes": self.min_axes,
                "require_price_axis": self.require_price_axis,
                "delta": {
                    "ret_min": self.delta_ret_min,
                    "zvol_min": self.delta_zvol_min,
                    "spread_drop": self.delta_spread_drop
                }
            }
        }


def confirm_candidates(
    features_df: pd.DataFrame,
    candidate_events: List[Dict[str, Any]],
    config: Optional[Config] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to confirm onset candidates with Delta-based logic.

    Args:
        features_df: DataFrame with calculated features.
        candidate_events: List of candidate events.
        config: Optional configuration object.

    Returns:
        List[Dict]: List of confirmed onset events.
    """
    detector = ConfirmDetector(config)
    return detector.confirm_candidates(features_df, candidate_events)


if __name__ == "__main__":
    # Demo/test the Delta-based confirm detector
    from .candidate_detector import CandidateDetector
    from ..features import calculate_core_indicators
    import time

    print("Delta-based Confirm Detector Demo")
    print("=" * 40)

    # Create sample data with strong signals
    sample_data = {
        'ts': [1704067200000 + i * 1000 for i in range(40)],
        'stock_code': ['005930'] * 40,
        'price': [74000 + i * 100 for i in range(40)],  # Strong upward trend
        'volume': [1000 + i * 200 + np.random.randint(-50, 101) for i in range(40)],
        'bid1': [73950 + i * 100 for i in range(40)],
        'ask1': [74050 + i * 100 for i in range(40)],
        'bid_qty1': [500] * 40,
        'ask_qty1': [300] * 40,
    }

    df = pd.DataFrame(sample_data)
    print(f"Sample data shape: {df.shape}")

    # Calculate features
    features_df = calculate_core_indicators(df)
    print(f"Features DataFrame shape: {features_df.shape}")

    # Detect candidates first
    candidate_detector = CandidateDetector()
    # Lower thresholds for demo
    candidate_detector.score_threshold = 1.0
    candidate_detector.vol_z_min = 1.0
    candidate_detector.ticks_min = 1

    candidates = candidate_detector.detect_candidates(features_df)
    print(f"Candidates detected: {len(candidates)}")

    if candidates:
        # Confirm candidates with Delta-based logic
        confirm_detector = ConfirmDetector()
        confirmed_events = confirm_detector.confirm_candidates(features_df, candidates)

        print(f"Confirmations created: {len(confirmed_events)}")
        print(f"Confirmation rate: {len(confirmed_events) / len(candidates) * 100:.1f}%")

        # Show sample confirmed events
        for i, event in enumerate(confirmed_events[:3]):
            print(f"  {i+1}. Confirmed at: {event['ts']}, From: {event['confirmed_from']}")
            print(f"     Axes: {event['evidence']['axes']}")
            print(f"     Onset Strength: {event['evidence']['onset_strength']:.2f}")
            print(f"     TTA: {(event['ts'] - event['confirmed_from']) / 1000:.1f}s")
            print(f"     Delta values: ret={event['evidence']['delta_ret']:.4f}, "
                  f"zvol={event['evidence']['delta_zvol']:.2f}, "
                  f"spread={event['evidence']['delta_spread']:.4f}")

        # Get confirmation stats
        stats = confirm_detector.get_confirmation_stats(features_df, candidates)
        print(f"\nConfirmation Statistics:")
        print(f"  Confirmation rate: {stats['confirmation_rate']:.2%}")
        print(f"  Axes satisfaction: {stats['axes_stats']}")
        print(f"  Axes distribution: {stats['axes_distribution']}")
        print(f"  Window stats: {stats['window_stats']}")
        print(f"  Delta stats: {stats['delta_stats']}")
    else:
        print("No candidates to confirm")