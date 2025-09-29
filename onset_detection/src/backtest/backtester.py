"""Backtesting engine for onset detection evaluation."""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import logging

from ..config_loader import Config, load_config
from ..detection.confirm_detector import ConfirmDetector
from ..detection.confirm_hybrid import HybridConfirmDetector
from ..ml.labeler import load_events_from_jsonl, create_labels

logger = logging.getLogger(__name__)


class Backtester:
    """
    Backtest engine for evaluating onset detection performance.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize backtester.

        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()

        # Get backtest configuration
        backtest_config = getattr(self.config, 'backtest', None)
        if backtest_config is None:
            logger.warning("No backtest configuration found. Using defaults.")
            self.start_date = "2025-09-01"
            self.end_date = "2025-09-30"
            self.use_hybrid_confirm = True
            self.report_dir = "reports/"
        else:
            self.start_date = getattr(backtest_config, 'start_date', "2025-09-01")
            self.end_date = getattr(backtest_config, 'end_date', "2025-09-30")
            self.use_hybrid_confirm = getattr(backtest_config, 'use_hybrid_confirm', True)
            self.report_dir = getattr(backtest_config, 'report_dir', "reports/")

        # Parse dates
        self.start_dt = pd.to_datetime(self.start_date)
        self.end_dt = pd.to_datetime(self.end_date)

        logger.info(f"Backtester initialized: {self.start_date} to {self.end_date}")
        logger.info(f"Using hybrid confirm: {self.use_hybrid_confirm}")

    def filter_by_date_range(
        self,
        features_df: pd.DataFrame,
        events: List[Dict[str, Any]]
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Filter features and events by date range.

        Args:
            features_df: Features DataFrame with 'ts' column.
            events: List of events with 'ts' field.

        Returns:
            Tuple: (filtered_features_df, filtered_events).
        """
        # Filter features by date range
        if 'ts' in features_df.columns:
            features_df['ts'] = pd.to_datetime(features_df['ts'], format='mixed')
            filtered_features = features_df[
                (features_df['ts'] >= self.start_dt) &
                (features_df['ts'] <= self.end_dt)
            ].copy()
        else:
            filtered_features = features_df.copy()

        # Filter events by date range
        filtered_events = []
        for event in events:
            event_ts = event.get('ts')
            if event_ts is not None:
                # Convert timestamp to datetime
                if isinstance(event_ts, (int, float)):
                    if event_ts < 1e10:  # Likely seconds
                        event_dt = pd.to_datetime(event_ts, unit='s')
                    else:  # Likely milliseconds
                        event_dt = pd.to_datetime(event_ts, unit='ms')
                else:
                    event_dt = pd.to_datetime(event_ts)

                # Check if in date range
                if self.start_dt <= event_dt <= self.end_dt:
                    filtered_events.append(event)

        logger.info(f"Filtered features: {len(features_df)} → {len(filtered_features)} rows")
        logger.info(f"Filtered events: {len(events)} → {len(filtered_events)} events")

        return filtered_features, filtered_events

    def run_confirmation(
        self,
        features_df: pd.DataFrame,
        candidate_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Run confirmation detection on candidates.

        Args:
            features_df: Features DataFrame.
            candidate_events: List of candidate events.

        Returns:
            List[Dict]: List of confirmed events.
        """
        if self.use_hybrid_confirm:
            detector = HybridConfirmDetector(self.config)
            logger.info("Using hybrid confirmation detector")
        else:
            detector = ConfirmDetector(self.config)
            logger.info("Using rule-based confirmation detector")

        confirmed_events = detector.confirm_candidates(features_df, candidate_events)
        logger.info(f"Confirmation results: {len(candidate_events)} candidates → {len(confirmed_events)} confirmed")

        return confirmed_events

    def calculate_metrics(
        self,
        candidate_events: List[Dict[str, Any]],
        confirmed_events: List[Dict[str, Any]],
        features_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate backtest performance metrics.

        Args:
            candidate_events: List of candidate events.
            confirmed_events: List of confirmed events.
            features_df: Features DataFrame for additional calculations.

        Returns:
            Dict: Performance metrics.
        """
        n_candidates = len(candidate_events)
        n_confirmed = len(confirmed_events)

        # Basic rates
        confirm_rate = n_confirmed / n_candidates if n_candidates > 0 else 0.0

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
                "p50": float(np.percentile(tta_values, 50)),
                "p95": float(np.percentile(tta_values, 95)),
                "min": float(np.min(tta_values)),
                "max": float(np.max(tta_values))
            }

        # Calculate time span for FP/hour calculation
        if not features_df.empty and 'ts' in features_df.columns:
            time_span_hours = (features_df['ts'].max() - features_df['ts'].min()).total_seconds() / 3600
        else:
            time_span_hours = 24  # Default assumption

        fp_per_hour = n_confirmed / time_span_hours if time_span_hours > 0 else 0.0

        # Collect onset strength statistics if available
        onset_strength_stats = {}
        if confirmed_events:
            strength_values = []
            for event in confirmed_events:
                strength = event.get('evidence', {}).get('onset_strength')
                if strength is not None:
                    strength_values.append(strength)

            if strength_values:
                onset_strength_stats = {
                    "mean": float(np.mean(strength_values)),
                    "median": float(np.median(strength_values)),
                    "min": float(np.min(strength_values)),
                    "max": float(np.max(strength_values)),
                    "count": len(strength_values)
                }

        # Axes distribution
        axes_distribution = {"price": 0, "volume": 0, "friction": 0}
        axes_counts = {"price": 0, "volume": 0, "friction": 0}

        for event in confirmed_events:
            axes = event.get('evidence', {}).get('axes', [])
            for axis in axes:
                if axis in axes_counts:
                    axes_counts[axis] += 1

        if n_confirmed > 0:
            for axis in axes_distribution:
                axes_distribution[axis] = axes_counts[axis] / n_confirmed

        metrics = {
            "period": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "time_span_hours": float(time_span_hours)
            },
            "events": {
                "candidates": n_candidates,
                "confirmed": n_confirmed,
                "confirm_rate": confirm_rate
            },
            "timing": {
                "tta_stats": tta_stats,
                "fp_per_hour": fp_per_hour
            },
            "axes": {
                "distribution": axes_distribution,
                "counts": axes_counts
            },
            "ml": {
                "onset_strength_stats": onset_strength_stats,
                "hybrid_used": self.use_hybrid_confirm
            },
            "data": {
                "features_rows": len(features_df),
                "features_columns": len(features_df.columns) if not features_df.empty else 0
            }
        }

        return metrics

    def create_event_summary(
        self,
        candidate_events: List[Dict[str, Any]],
        confirmed_events: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Create detailed event-by-event summary.

        Args:
            candidate_events: List of candidate events.
            confirmed_events: List of confirmed events.

        Returns:
            DataFrame: Event summary with match status.
        """
        # Create confirmed events lookup
        confirmed_lookup = {}
        for confirmed in confirmed_events:
            confirmed_from = confirmed.get('confirmed_from')
            if confirmed_from:
                confirmed_lookup[confirmed_from] = confirmed

        # Build summary rows
        summary_rows = []
        for candidate in candidate_events:
            candidate_ts = candidate['ts']
            is_confirmed = candidate_ts in confirmed_lookup

            row = {
                "candidate_ts": candidate_ts,
                "stock_code": candidate.get('stock_code', ''),
                "candidate_score": candidate.get('score', 0.0),
                "is_confirmed": is_confirmed,
                "confirm_ts": confirmed_lookup[candidate_ts]['ts'] if is_confirmed else None,
                "tta_seconds": (confirmed_lookup[candidate_ts]['ts'] - candidate_ts) / 1000.0 if is_confirmed else None,
                "onset_strength": confirmed_lookup[candidate_ts].get('evidence', {}).get('onset_strength') if is_confirmed else None,
                "satisfied_axes": ','.join(confirmed_lookup[candidate_ts].get('evidence', {}).get('axes', [])) if is_confirmed else ''
            }
            summary_rows.append(row)

        return pd.DataFrame(summary_rows)

    def run_backtest(
        self,
        features_file: Union[str, Path],
        events_file: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        Run complete backtest pipeline.

        Args:
            features_file: Path to features CSV file.
            events_file: Path to events JSONL file.

        Returns:
            Dict: Complete backtest results.
        """
        logger.info("Starting backtest run")
        logger.info(f"Features file: {features_file}")
        logger.info(f"Events file: {events_file}")

        # Load data
        features_df = pd.read_csv(features_file)
        logger.info(f"Loaded features: shape={features_df.shape}")

        events = load_events_from_jsonl(events_file)
        logger.info(f"Loaded events: {len(events)}")

        # Filter by date range
        filtered_features, filtered_events = self.filter_by_date_range(features_df, events)

        # Get candidates only
        candidates = [e for e in filtered_events if e.get('event_type') == 'onset_candidate']
        logger.info(f"Found {len(candidates)} candidate events")

        if not candidates:
            logger.warning("No candidate events found for backtest period")
            return {
                "metrics": {"events": {"candidates": 0, "confirmed": 0, "confirm_rate": 0.0}},
                "event_summary": pd.DataFrame(),
                "config": {"use_hybrid": self.use_hybrid_confirm}
            }

        # Run confirmation
        confirmed_events = self.run_confirmation(filtered_features, candidates)

        # Calculate metrics
        metrics = self.calculate_metrics(candidates, confirmed_events, filtered_features)

        # Create event summary
        event_summary = self.create_event_summary(candidates, confirmed_events)

        return {
            "metrics": metrics,
            "event_summary": event_summary,
            "confirmed_events": confirmed_events,
            "config": {
                "use_hybrid": self.use_hybrid_confirm,
                "date_range": f"{self.start_date} to {self.end_date}"
            }
        }


def run_backtest(
    features_file: Union[str, Path],
    events_file: Union[str, Path],
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Convenience function to run backtest.

    Args:
        features_file: Path to features CSV file.
        events_file: Path to events JSONL file.
        config: Optional configuration object.

    Returns:
        Dict: Backtest results.
    """
    backtester = Backtester(config)
    return backtester.run_backtest(features_file, events_file)


if __name__ == "__main__":
    # Demo/test the backtester
    import sys
    from pathlib import Path

    # Add project root to Python path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    print("Backtester Demo")
    print("=" * 40)

    # Initialize backtester
    try:
        backtester = Backtester()
        print(f"Backtester initialized")
        print(f"Date range: {backtester.start_date} to {backtester.end_date}")
        print(f"Hybrid mode: {backtester.use_hybrid_confirm}")

        # Create dummy data for testing
        sample_features = pd.DataFrame({
            'ts': pd.date_range('2025-09-02', periods=100, freq='1s'),
            'stock_code': ['005930'] * 100,
            'price': 1000 + np.random.randn(100) * 10,
            'ret_1s': np.random.randn(100) * 0.001,
            'z_vol_1s': np.random.randn(100),
            'spread': np.random.uniform(0.001, 0.01, 100),
            'microprice_slope': np.random.randn(100) * 0.0001
        })

        sample_events = [
            {
                'ts': sample_features['ts'].iloc[10].timestamp(),
                'event_type': 'onset_candidate',
                'stock_code': '005930',
                'score': 2.5
            },
            {
                'ts': sample_features['ts'].iloc[50].timestamp(),
                'event_type': 'onset_candidate',
                'stock_code': '005930',
                'score': 3.2
            }
        ]

        print(f"Sample features shape: {sample_features.shape}")
        print(f"Sample events: {len(sample_events)}")

        # Filter data
        filtered_features, filtered_events = backtester.filter_by_date_range(
            sample_features, sample_events
        )

        print(f"Filtered features: {len(filtered_features)} rows")
        print(f"Filtered events: {len(filtered_events)} events")

        # Calculate metrics
        candidates = [e for e in filtered_events if e.get('event_type') == 'onset_candidate']
        metrics = backtester.calculate_metrics(candidates, [], filtered_features)

        print(f"Sample metrics:")
        print(f"  Candidates: {metrics['events']['candidates']}")
        print(f"  Confirm rate: {metrics['events']['confirm_rate']:.2%}")
        print(f"  Time span: {metrics['period']['time_span_hours']:.2f} hours")

    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()