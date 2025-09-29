"""Hybrid confirm detector combining rule-based and ML approaches."""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..config_loader import Config, load_config
from ..event_store import EventStore, create_event
from .confirm_detector import ConfirmDetector
from ..online.score_onset import OnsetScorer

import logging

logger = logging.getLogger(__name__)


class HybridConfirmDetector(ConfirmDetector):
    """
    Hybrid confirm detector that combines rule-based validation with ML onset strength.

    Inherits from ConfirmDetector and adds ML-based filtering on top of rule-based logic.
    """

    def __init__(self, config: Optional[Config] = None, event_store: Optional[EventStore] = None):
        """
        Initialize hybrid confirm detector.

        Args:
            config: Configuration object. If None, loads default config.
            event_store: EventStore instance. If None, creates default one.
        """
        super().__init__(config, event_store)

        # Check if hybrid mode is enabled
        ml_config = getattr(self.config, 'ml', None)
        if ml_config is None:
            logger.warning("No ML configuration found. Falling back to rule-based only.")
            self.use_hybrid = False
            self.ml_threshold = 0.6
        else:
            self.use_hybrid = getattr(ml_config, 'use_hybrid_confirm', True)
            self.ml_threshold = getattr(ml_config, 'threshold', 0.6)

        # Initialize onset scorer
        if self.use_hybrid:
            try:
                self.onset_scorer = OnsetScorer(config)
                logger.info(f"Hybrid mode enabled with ML threshold: {self.ml_threshold}")
            except Exception as e:
                logger.error(f"Failed to initialize onset scorer: {e}")
                self.use_hybrid = False
                logger.warning("Falling back to rule-based confirmation only")
        else:
            logger.info("Hybrid mode disabled, using rule-based confirmation only")

    def confirm_candidates(
        self,
        features_df: pd.DataFrame,
        candidate_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Confirm onset candidates using hybrid rule-based + ML approach.

        Args:
            features_df: DataFrame with calculated features from core_indicators.
            candidate_events: List of candidate events from candidate_detector.

        Returns:
            List[Dict]: List of confirmed onset events.
        """
        if features_df.empty or not candidate_events:
            return []

        # Add onset strength if using hybrid mode
        if self.use_hybrid:
            try:
                logger.info("Adding ML onset strength scores to features")
                features_with_strength = self.onset_scorer.add_onset_strength(features_df)
            except Exception as e:
                logger.error(f"Failed to add onset strength: {e}")
                logger.warning("Falling back to rule-based confirmation")
                features_with_strength = features_df.copy()
                self.use_hybrid = False
        else:
            features_with_strength = features_df.copy()

        confirmed_events = []

        # Required columns check
        required_cols = ['ts', 'stock_code', 'ret_1s', 'z_vol_1s', 'spread', 'microprice_slope']
        missing_cols = set(required_cols) - set(features_with_strength.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns for confirmation: {missing_cols}")

        # Sort features by timestamp for efficient lookup
        features_with_strength = features_with_strength.sort_values('ts')

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

            pre_window_features = features_with_strength[
                (features_with_strength['ts'] > pre_window_start) &
                (features_with_strength['ts'] <= pre_window_end) &
                (features_with_strength['stock_code'].astype(str) == str(stock_code))
            ]

            # Extract confirmation window (after candidate)
            if self.exclude_cand_point:
                window_start = candidate_dt + pd.Timedelta(milliseconds=1)
            else:
                window_start = candidate_dt
            window_end = candidate_dt + pd.Timedelta(seconds=self.window_s)

            window_features = features_with_strength[
                (features_with_strength['ts'] > window_start) &
                (features_with_strength['ts'] <= window_end) &
                (features_with_strength['stock_code'].astype(str) == str(stock_code))
            ]

            if window_features.empty or pre_window_features.empty:
                continue

            # Check Delta-based confirmation conditions (from parent class)
            confirmation_result = self._check_hybrid_confirmation(
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
                        "onset_strength": confirmation_result.get("onset_strength", 0.5),
                        "hybrid_used": self.use_hybrid,
                        "ml_threshold": self.ml_threshold,
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

    def _check_hybrid_confirmation(
        self,
        pre_window_df: pd.DataFrame,
        window_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Check hybrid confirmation conditions (rule-based + ML).

        Args:
            pre_window_df: Features DataFrame for pre-window (before candidate).
            window_df: Features DataFrame for confirmation window (after candidate).

        Returns:
            Dict: Confirmation result with details.
        """
        # Start with the parent class Delta-based confirmation
        rule_result = self._check_delta_confirmation(pre_window_df, window_df)

        # If rule-based confirmation failed, return early
        if not rule_result['confirmed']:
            return rule_result

        # If hybrid mode is disabled, return rule-based result
        if not self.use_hybrid:
            return rule_result

        # Apply ML-based filtering
        if 'onset_strength' not in window_df.columns:
            logger.warning("onset_strength column not found, using rule-based result only")
            return rule_result

        # Find the confirmation row identified by rule-based logic
        confirm_ts = rule_result['confirm_ts']
        if hasattr(confirm_ts, 'timestamp'):
            confirm_ts_float = confirm_ts
        else:
            confirm_ts_float = pd.to_datetime(confirm_ts, unit='s' if confirm_ts < 1e10 else 'ms', utc=True).tz_convert('Asia/Seoul')

        # Find the row closest to confirmation timestamp
        closest_idx = (window_df['ts'] - confirm_ts_float).abs().idxmin()
        confirm_row = window_df.loc[closest_idx]

        # Check ML threshold
        onset_strength = confirm_row['onset_strength']
        ml_passed = onset_strength >= self.ml_threshold

        if not ml_passed:
            logger.debug(f"ML threshold not met: {onset_strength:.3f} < {self.ml_threshold}")
            return {
                "confirmed": False,
                "satisfied_axes": [],
                "onset_strength": onset_strength,
                "evidence": {},
                "confirm_ts": None,
                "window_size": len(window_df),
                "ml_failed": True
            }

        # Both rule-based and ML conditions passed
        rule_result['onset_strength'] = onset_strength
        logger.debug(f"Hybrid confirmation passed: rules + ML({onset_strength:.3f} >= {self.ml_threshold})")

        return rule_result

    def get_confirmation_stats(
        self,
        features_df: pd.DataFrame,
        candidate_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get hybrid confirmation statistics.

        Args:
            features_df: DataFrame with calculated features.
            candidate_events: List of candidate events.

        Returns:
            Dict: Confirmation statistics including ML metrics.
        """
        if not candidate_events:
            return {
                "candidates_processed": 0,
                "confirmations_possible": 0,
                "confirmation_rate": 0.0,
                "axes_stats": {},
                "axes_distribution": {},
                "window_stats": {},
                "delta_stats": {},
                "ml_stats": {}
            }

        # Get base stats from parent class
        base_stats = super().get_confirmation_stats(features_df, candidate_events)

        # Add ML-specific statistics if hybrid mode is enabled
        if self.use_hybrid:
            try:
                # Add onset strength to features
                features_with_strength = self.onset_scorer.add_onset_strength(features_df)

                # Calculate ML statistics
                if 'onset_strength' in features_with_strength.columns:
                    strength_scores = features_with_strength['onset_strength']
                    ml_stats = {
                        "mean_strength": float(strength_scores.mean()),
                        "max_strength": float(strength_scores.max()),
                        "min_strength": float(strength_scores.min()),
                        "above_threshold": int((strength_scores >= self.ml_threshold).sum()),
                        "threshold_rate": float((strength_scores >= self.ml_threshold).mean()),
                        "threshold_used": self.ml_threshold,
                        "hybrid_enabled": True
                    }
                else:
                    ml_stats = {"hybrid_enabled": False, "error": "onset_strength not found"}

                base_stats['ml_stats'] = ml_stats

            except Exception as e:
                base_stats['ml_stats'] = {"hybrid_enabled": False, "error": str(e)}
        else:
            base_stats['ml_stats'] = {"hybrid_enabled": False}

        return base_stats


def confirm_candidates(
    features_df: pd.DataFrame,
    candidate_events: List[Dict[str, Any]],
    config: Optional[Config] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to confirm onset candidates with hybrid approach.

    Args:
        features_df: DataFrame with calculated features.
        candidate_events: List of candidate events.
        config: Optional configuration object.

    Returns:
        List[Dict]: List of confirmed onset events.
    """
    detector = HybridConfirmDetector(config)
    return detector.confirm_candidates(features_df, candidate_events)


if __name__ == "__main__":
    # Demo/test the hybrid confirm detector
    from ..features import calculate_core_indicators
    from .candidate_detector import CandidateDetector
    import time

    print("Hybrid Confirm Detector Demo")
    print("=" * 50)

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
        # Confirm candidates with hybrid approach
        hybrid_detector = HybridConfirmDetector()
        confirmed_events = hybrid_detector.confirm_candidates(features_df, candidates)

        print(f"Confirmations created: {len(confirmed_events)}")
        print(f"Confirmation rate: {len(confirmed_events) / len(candidates) * 100:.1f}%")
        print(f"Hybrid mode enabled: {hybrid_detector.use_hybrid}")

        # Show sample confirmed events
        for i, event in enumerate(confirmed_events[:3]):
            print(f"  {i+1}. Confirmed at: {event['ts']}, From: {event['confirmed_from']}")
            print(f"     Axes: {event['evidence']['axes']}")
            print(f"     Onset Strength: {event['evidence'].get('onset_strength', 'N/A')}")
            print(f"     Hybrid Used: {event['evidence'].get('hybrid_used', False)}")
            print(f"     TTA: {(event['ts'] - event['confirmed_from']) / 1000:.1f}s")

        # Get confirmation stats
        stats = hybrid_detector.get_confirmation_stats(features_df, candidates)
        print(f"\nHybrid Confirmation Statistics:")
        print(f"  Confirmation rate: {stats['confirmation_rate']:.2%}")
        print(f"  ML stats: {stats.get('ml_stats', {})}")

    else:
        print("No candidates to confirm")