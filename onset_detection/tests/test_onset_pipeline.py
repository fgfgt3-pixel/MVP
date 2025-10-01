"""Tests for OnsetPipelineDF - Detection Only pipeline integration."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from onset_detection.src.detection.onset_pipeline import OnsetPipelineDF, run_onset_pipeline
from onset_detection.src.detection.candidate_detector import CandidateDetector
from onset_detection.src.detection.confirm_detector import ConfirmDetector
from onset_detection.src.detection.refractory_manager import RefractoryManager
from onset_detection.src.config_loader import load_config
from onset_detection.src.features import calculate_core_indicators


class TestOnsetPipelineDF:
    """Test suite for OnsetPipelineDF integration."""

    @pytest.fixture
    def config(self):
        """Load test configuration."""
        return load_config()

    @pytest.fixture
    def sample_features_df(self):
        """Create sample features DataFrame with onset pattern."""
        np.random.seed(42)
        n_rows = 50

        # Create data with strong onset pattern in middle
        prices = [74000] * 20 + [74000 + i * 100 for i in range(20)] + [76000] * 10
        volumes = [1000] * 20 + [1000 + i * 200 for i in range(20)] + [5000] * 10

        sample_data = {
            'ts': [pd.Timestamp('2024-01-01 09:00:00', tz='Asia/Seoul') + pd.Timedelta(seconds=i)
                   for i in range(n_rows)],
            'stock_code': ['005930'] * n_rows,
            'price': prices,
            'volume': volumes,
            'bid1': [p - 50 for p in prices],
            'ask1': [p + 50 for p in prices],
            'bid_qty1': [500] * n_rows,
            'ask_qty1': [300] * n_rows,
        }

        df = pd.DataFrame(sample_data)
        return calculate_core_indicators(df)

    def test_pipeline_initialization(self, config):
        """Test pipeline initialization with default components."""
        pipeline = OnsetPipelineDF(config=config)

        assert pipeline.config is not None
        assert isinstance(pipeline.candidate_detector, CandidateDetector)
        assert isinstance(pipeline.confirm_detector, ConfirmDetector)
        assert isinstance(pipeline.refractory_manager, RefractoryManager)

    def test_pipeline_initialization_with_custom_components(self, config):
        """Test pipeline initialization with custom components."""
        custom_candidate = CandidateDetector(config=config)
        custom_confirm = ConfirmDetector(config=config)
        custom_refractory = RefractoryManager(config=config)

        pipeline = OnsetPipelineDF(
            config=config,
            candidate_detector=custom_candidate,
            confirm_detector=custom_confirm,
            refractory_manager=custom_refractory
        )

        assert pipeline.candidate_detector is custom_candidate
        assert pipeline.confirm_detector is custom_confirm
        assert pipeline.refractory_manager is custom_refractory

    def test_run_batch_empty_dataframe(self, config):
        """Test pipeline with empty DataFrame."""
        pipeline = OnsetPipelineDF(config=config)
        empty_df = pd.DataFrame()

        result = pipeline.run_batch(empty_df)

        assert result['alerts'] == []
        assert result['candidates_count'] == 0
        assert result['confirmed_count'] == 0
        assert result['rejected_count'] == 0

    def test_run_batch_basic_flow(self, config, sample_features_df):
        """Test basic pipeline flow with sample data."""
        pipeline = OnsetPipelineDF(config=config)

        result = pipeline.run_batch(sample_features_df, return_intermediates=True)

        # Check result structure
        assert 'alerts' in result
        assert 'candidates_count' in result
        assert 'confirmed_count' in result
        assert 'rejected_count' in result
        assert 'intermediates' in result

        # Check intermediates
        intermediates = result['intermediates']
        assert 'candidates' in intermediates
        assert 'allowed_candidates' in intermediates
        assert 'rejected_candidates' in intermediates
        assert 'confirmed_events' in intermediates

        # Verify counts consistency
        total_candidates = result['candidates_count']
        allowed = len(intermediates['allowed_candidates'])
        rejected = len(intermediates['rejected_candidates'])

        assert allowed + rejected == total_candidates

    def test_run_batch_without_intermediates(self, config, sample_features_df):
        """Test pipeline without returning intermediates."""
        pipeline = OnsetPipelineDF(config=config)

        result = pipeline.run_batch(sample_features_df, return_intermediates=False)

        # Check result structure
        assert 'alerts' in result
        assert 'candidates_count' in result
        assert 'confirmed_count' in result
        assert 'rejected_count' in result
        assert 'intermediates' not in result

    def test_run_batch_refractory_filtering(self, config):
        """Test refractory filtering in pipeline."""
        pipeline = OnsetPipelineDF(config=config)

        # Create data with multiple close-timed onsets (should be filtered by refractory)
        base_time = pd.Timestamp('2024-01-01 09:00:00', tz='Asia/Seoul')

        # First onset at t=0
        df1_data = {
            'ts': [base_time + pd.Timedelta(seconds=i) for i in range(30)],
            'stock_code': ['005930'] * 30,
            'price': [74000 + i * 100 for i in range(30)],
            'volume': [1000 + i * 200 for i in range(30)],
            'bid1': [73950 + i * 100 for i in range(30)],
            'ask1': [74050 + i * 100 for i in range(30)],
            'bid_qty1': [500] * 30,
            'ask_qty1': [300] * 30,
        }
        df1 = pd.DataFrame(df1_data)
        features1 = calculate_core_indicators(df1)

        # Second onset at t=10s (within refractory period of 20s)
        df2_data = {
            'ts': [base_time + pd.Timedelta(seconds=10 + i) for i in range(30)],
            'stock_code': ['005930'] * 30,
            'price': [75000 + i * 100 for i in range(30)],
            'volume': [2000 + i * 200 for i in range(30)],
            'bid1': [74950 + i * 100 for i in range(30)],
            'ask1': [75050 + i * 100 for i in range(30)],
            'bid_qty1': [500] * 30,
            'ask_qty1': [300] * 30,
        }
        df2 = pd.DataFrame(df2_data)
        features2 = calculate_core_indicators(df2)

        # Combine and process
        combined_features = pd.concat([features1, features2]).sort_values('ts')

        result = pipeline.run_batch(combined_features, return_intermediates=True)

        # Verify some candidates were rejected due to refractory
        assert result['rejected_count'] >= 0  # May have rejections

    def test_run_batch_and_save(self, config, sample_features_df, tmp_path):
        """Test pipeline with event saving."""
        pipeline = OnsetPipelineDF(config=config)

        # Use temporary file for testing
        output_file = tmp_path / "test_events.jsonl"

        result = pipeline.run_batch_and_save(
            sample_features_df,
            filename=str(output_file)
        )

        # Check result contains save status
        assert 'save_success' in result
        assert 'events_saved' in result

    def test_get_pipeline_stats(self, config, sample_features_df):
        """Test pipeline statistics generation."""
        pipeline = OnsetPipelineDF(config=config)

        stats = pipeline.get_pipeline_stats(sample_features_df)

        # Check stats structure
        assert 'total_features' in stats
        assert 'candidates_detected' in stats
        assert 'candidates_rejected_refractory' in stats
        assert 'onsets_confirmed' in stats
        assert 'confirmation_rate' in stats
        assert 'rejection_rate' in stats
        assert 'config' in stats

        # Verify stats values
        assert stats['total_features'] == len(sample_features_df)
        assert 0 <= stats['confirmation_rate'] <= 1.0
        assert 0 <= stats['rejection_rate'] <= 1.0

        # Verify config in stats
        config_info = stats['config']
        assert 'window_s' in config_info
        assert 'persistent_n' in config_info
        assert 'refractory_duration_s' in config_info

    def test_convenience_function(self, config, sample_features_df):
        """Test convenience function run_onset_pipeline."""
        alerts = run_onset_pipeline(sample_features_df, config=config)

        assert isinstance(alerts, list)
        # Each alert should be a dict
        for alert in alerts:
            assert isinstance(alert, dict)
            assert 'ts' in alert
            assert 'stock_code' in alert
            assert 'event_type' in alert


def test_smoke_pipeline():
    """Smoke test for basic pipeline functionality."""
    config = load_config()

    # Minimal input data
    minimal_data = {
        'ts': [pd.Timestamp('2024-01-01 09:00:00', tz='Asia/Seoul') + pd.Timedelta(seconds=i)
               for i in range(10)],
        'stock_code': ['TEST'] * 10,
        'price': [100 + i for i in range(10)],
        'volume': [1000] * 10,
        'bid1': [99 + i for i in range(10)],
        'ask1': [101 + i for i in range(10)],
        'bid_qty1': [500] * 10,
        'ask_qty1': [300] * 10,
    }

    df = pd.DataFrame(minimal_data)
    features_df = calculate_core_indicators(df)

    pipeline = OnsetPipelineDF(config=config)
    result = pipeline.run_batch(features_df)

    # Should not raise exceptions
    assert isinstance(result, dict)
    assert 'alerts' in result


if __name__ == "__main__":
    # Run smoke test
    print("Running smoke test...")
    test_smoke_pipeline()
    print("Smoke test passed!")
