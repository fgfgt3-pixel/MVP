"""Onset detection pipeline - DataFrame batch processing wrapper.

This module provides a unified pipeline that orchestrates:
1. Candidate detection (CandidateDetector)
2. Confirmation with Delta-based validation (ConfirmDetector)
3. Refractory period management (RefractoryManager)

Architecture:
- Works with DataFrame batch processing (not tick-by-tick streaming)
- Integrates existing detectors without modifying their interfaces
- Provides simplified run_batch() API for Detection Only pipeline
- Supports streaming mode via run_tick() with internal buffering
"""

from typing import List, Dict, Any, Optional
from collections import deque
import pandas as pd
import logging

from .candidate_detector import CandidateDetector
from .confirm_detector import ConfirmDetector
from .refractory_manager import RefractoryManager
from ..config_loader import Config, load_config
from ..event_store import EventStore


logger = logging.getLogger(__name__)


class OnsetPipelineDF:
    """
    DataFrame-based onset detection pipeline.

    Orchestrates the full detection flow:
    features_df -> candidates -> refractory filter -> confirmations -> alerts
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        event_store: Optional[EventStore] = None,
        candidate_detector: Optional[CandidateDetector] = None,
        confirm_detector: Optional[ConfirmDetector] = None,
        refractory_manager: Optional[RefractoryManager] = None
    ):
        """
        Initialize onset detection pipeline.

        Args:
            config: Configuration object. If None, loads default.
            event_store: EventStore instance. If None, creates default.
            candidate_detector: Custom CandidateDetector. If None, creates default.
            confirm_detector: Custom ConfirmDetector. If None, creates default.
            refractory_manager: Custom RefractoryManager. If None, creates default.
        """
        self.config = config or load_config()
        self.event_store = event_store or EventStore()

        # Initialize detectors (allow injection for testing)
        self.candidate_detector = candidate_detector or CandidateDetector(
            config=self.config,
            event_store=self.event_store
        )
        self.confirm_detector = confirm_detector or ConfirmDetector(
            config=self.config,
            event_store=self.event_store
        )
        self.refractory_manager = refractory_manager or RefractoryManager(
            config=self.config,
            event_store=self.event_store
        )

        # Extract config parameters
        self.min_axes_required = self.config.detection.get("min_axes_required", 2) if hasattr(
            self.config.detection, "get"
        ) else 2

        # Streaming mode: tick buffer
        self.tick_buffer = deque(maxlen=1000)  # Keep last 1000 ticks for feature calculation
        self.buffer_window_s = 60  # Process last 60 seconds of data

    def run_batch(
        self,
        features_df: pd.DataFrame,
        return_intermediates: bool = False
    ) -> Dict[str, Any]:
        """
        Run full detection pipeline on a batch of features.

        Args:
            features_df: DataFrame with calculated features from core_indicators.
            return_intermediates: If True, include intermediate results (candidates, etc).

        Returns:
            Dict with:
                - alerts: List[Dict] - Final confirmed onset alerts
                - candidates_count: int - Number of initial candidates
                - confirmed_count: int - Number of confirmations
                - rejected_count: int - Number rejected by refractory
                - intermediates: Dict (optional) - Intermediate stage results
        """
        if features_df.empty:
            logger.warning("Empty features DataFrame provided to pipeline")
            return {
                "alerts": [],
                "candidates_count": 0,
                "confirmed_count": 0,
                "rejected_count": 0
            }

        logger.info(f"Running onset pipeline on {len(features_df)} feature rows")

        # Step 1: Detect candidates
        logger.debug("Step 1: Detecting candidates")
        candidates = self.candidate_detector.detect_candidates(features_df)
        logger.info(f"Detected {len(candidates)} candidates")

        if not candidates:
            return {
                "alerts": [],
                "candidates_count": 0,
                "confirmed_count": 0,
                "rejected_count": 0
            }

        # Step 2: Apply refractory filtering to candidates
        logger.debug("Step 2: Applying refractory filter to candidates")
        candidate_events_with_refractory = self.refractory_manager.process_events(candidates)

        # Separate allowed vs rejected candidates
        allowed_candidates = [
            e for e in candidate_events_with_refractory
            if e.get('event_type') == 'onset_candidate'
        ]
        rejected_candidates = [
            e for e in candidate_events_with_refractory
            if e.get('event_type') == 'onset_rejected_refractory'
        ]

        logger.info(f"After refractory filter: {len(allowed_candidates)} allowed, "
                   f"{len(rejected_candidates)} rejected")

        if not allowed_candidates:
            return {
                "alerts": [],
                "candidates_count": len(candidates),
                "confirmed_count": 0,
                "rejected_count": len(rejected_candidates)
            }

        # Step 3: Confirm allowed candidates
        logger.debug("Step 3: Confirming candidates")
        confirmed_events = self.confirm_detector.confirm_candidates(
            features_df,
            allowed_candidates
        )
        logger.info(f"Confirmed {len(confirmed_events)} onsets")

        # Step 4: Update refractory state with confirmations
        if confirmed_events:
            logger.debug("Step 4: Updating refractory state with confirmations")
            # Process confirmations to update refractory state
            _ = self.refractory_manager.process_events(confirmed_events)

        # Prepare result
        result = {
            "alerts": confirmed_events,
            "candidates_count": len(candidates),
            "confirmed_count": len(confirmed_events),
            "rejected_count": len(rejected_candidates)
        }

        # Include intermediates if requested
        if return_intermediates:
            result["intermediates"] = {
                "candidates": candidates,
                "allowed_candidates": allowed_candidates,
                "rejected_candidates": rejected_candidates,
                "confirmed_events": confirmed_events
            }

        return result

    def run_tick(self, raw_tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single tick in streaming mode.

        This method buffers ticks and triggers batch processing when enough data accumulates.
        It maintains a sliding window of recent ticks for feature calculation.

        Args:
            raw_tick: Dict with tick data (ts, code, price, volume, etc.)

        Returns:
            Dict with confirmed onset event, or None if no alert generated.
        """
        from ..features import calculate_core_indicators

        # Add tick to buffer
        self.tick_buffer.append(raw_tick)

        # Need minimum ticks for feature calculation
        if len(self.tick_buffer) < 30:
            return None

        # Convert buffer to DataFrame
        buffer_df = pd.DataFrame(list(self.tick_buffer))

        # Ensure proper timestamp format
        if 'ts' in buffer_df.columns:
            # Convert to datetime if not already
            if buffer_df['ts'].dtype in ['int64', 'float64']:
                buffer_df['ts'] = pd.to_datetime(buffer_df['ts'], unit='ms', utc=True).dt.tz_convert('Asia/Seoul')
            elif not isinstance(buffer_df['ts'].iloc[0], pd.Timestamp):
                buffer_df['ts'] = pd.to_datetime(buffer_df['ts'])

        # Calculate features
        try:
            features_df = calculate_core_indicators(buffer_df)
        except Exception as e:
            logger.warning(f"Feature calculation failed: {e}")
            return None

        if features_df.empty:
            return None

        # Run batch detection on recent window
        result = self.run_batch(features_df, return_intermediates=False)

        # Return most recent alert if any
        if result['alerts']:
            # Return the latest alert
            return result['alerts'][-1]

        return None

    def run_batch_and_save(
        self,
        features_df: pd.DataFrame,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run pipeline and save all events to EventStore.

        Args:
            features_df: DataFrame with calculated features.
            filename: Optional filename for saving events.

        Returns:
            Dict with pipeline results and save status.
        """
        result = self.run_batch(features_df, return_intermediates=True)

        # Save all event types
        all_events = []
        if "intermediates" in result:
            all_events.extend(result["intermediates"].get("candidates", []))
            all_events.extend(result["intermediates"].get("rejected_candidates", []))
            all_events.extend(result["intermediates"].get("confirmed_events", []))

        save_success = True
        if all_events:
            for event in all_events:
                if not self.event_store.save_event(event, filename=filename):
                    save_success = False

        result["save_success"] = save_success
        result["events_saved"] = len(all_events)

        return result

    def get_pipeline_stats(self, features_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get pipeline statistics without saving events.

        Args:
            features_df: DataFrame with calculated features.

        Returns:
            Dict with pipeline statistics.
        """
        result = self.run_batch(features_df, return_intermediates=False)

        candidates_count = result["candidates_count"]
        confirmed_count = result["confirmed_count"]
        rejected_count = result["rejected_count"]

        confirmation_rate = confirmed_count / candidates_count if candidates_count > 0 else 0.0
        rejection_rate = rejected_count / candidates_count if candidates_count > 0 else 0.0

        return {
            "total_features": len(features_df),
            "candidates_detected": candidates_count,
            "candidates_rejected_refractory": rejected_count,
            "onsets_confirmed": confirmed_count,
            "confirmation_rate": confirmation_rate,
            "rejection_rate": rejection_rate,
            "config": {
                "window_s": self.confirm_detector.window_s,
                "persistent_n": self.confirm_detector.persistent_n,
                "refractory_duration_s": self.refractory_manager.duration_s,
                "min_axes_required": self.min_axes_required
            }
        }


def run_onset_pipeline(
    features_df: pd.DataFrame,
    config: Optional[Config] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to run onset detection pipeline.

    Args:
        features_df: DataFrame with calculated features.
        config: Optional configuration object.

    Returns:
        List[Dict]: List of confirmed onset alert events.
    """
    pipeline = OnsetPipelineDF(config=config)
    result = pipeline.run_batch(features_df)
    return result["alerts"]


if __name__ == "__main__":
    # Demo/test the onset pipeline
    from ..features import calculate_core_indicators
    import numpy as np

    print("Onset Pipeline Demo")
    print("=" * 50)

    # Create sample data with onset pattern
    np.random.seed(42)
    n_rows = 100

    # Generate timestamps as pandas Timestamp objects (proper timezone-aware format)
    base_time = pd.Timestamp('2024-01-01 09:00:00', tz='Asia/Seoul')
    timestamps = [base_time + pd.Timedelta(seconds=i) for i in range(n_rows)]

    sample_data = {
        'ts': timestamps,
        'stock_code': ['005930'] * n_rows,
        'price': [74000 + i * 50 + np.random.randint(-20, 21) for i in range(n_rows)],
        'volume': [1000 + i * 100 + np.random.randint(-50, 51) for i in range(n_rows)],
        'bid1': [73950 + i * 50 for i in range(n_rows)],
        'ask1': [74050 + i * 50 for i in range(n_rows)],
        'bid_qty1': [500 + np.random.randint(-50, 51) for _ in range(n_rows)],
        'ask_qty1': [300 + np.random.randint(-30, 31) for _ in range(n_rows)],
    }

    df = pd.DataFrame(sample_data)
    print(f"Sample data shape: {df.shape}")

    # Calculate features
    features_df = calculate_core_indicators(df)
    print(f"Features DataFrame shape: {features_df.shape}")

    # Run pipeline
    pipeline = OnsetPipelineDF()
    result = pipeline.run_batch(features_df, return_intermediates=True)

    print(f"\nPipeline Results:")
    print(f"  Candidates detected: {result['candidates_count']}")
    print(f"  Rejected by refractory: {result['rejected_count']}")
    print(f"  Onsets confirmed: {result['confirmed_count']}")
    print(f"  Final alerts: {len(result['alerts'])}")

    if result['alerts']:
        print(f"\nSample alerts:")
        for i, alert in enumerate(result['alerts'][:3]):
            print(f"  {i+1}. Timestamp: {alert['ts']}")
            print(f"     Stock: {alert['stock_code']}")
            print(f"     Axes: {alert.get('evidence', {}).get('axes', [])}")
            print(f"     Onset Strength: {alert.get('evidence', {}).get('onset_strength', 0):.2f}")

    # Get pipeline stats
    stats = pipeline.get_pipeline_stats(features_df)
    print(f"\nPipeline Statistics:")
    print(f"  Total features processed: {stats['total_features']}")
    print(f"  Confirmation rate: {stats['confirmation_rate']:.2%}")
    print(f"  Rejection rate: {stats['rejection_rate']:.2%}")
    print(f"  Config: window_s={stats['config']['window_s']}, "
          f"persistent_n={stats['config']['persistent_n']}")
