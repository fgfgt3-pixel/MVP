"""Tests for candidate detection functionality."""

import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
import pytest
import json

from src.detection import CandidateDetector, detect_candidates
from src.config_loader import Config
from src.event_store import EventStore
from src.features import calculate_core_indicators


class TestCandidateDetector:
    """Test candidate detection functionality."""
    
    def create_sample_features_data(self, n_rows: int = 20, high_signal: bool = True) -> pd.DataFrame:
        """Create sample features data for testing."""
        if high_signal:
            # Create data that should trigger detections
            base_ret = 0.01  # High returns
            base_vol_z = 3.0  # High volume z-scores
            ticks = 3        # High tick count
        else:
            # Create data that should NOT trigger detections
            base_ret = 0.001  # Low returns
            base_vol_z = 0.5  # Low volume z-scores  
            ticks = 1         # Low tick count
        
        return pd.DataFrame({
            'ts': [1704067200000 + i * 1000 for i in range(n_rows)],
            'stock_code': ['005930'] * n_rows,
            'price': [74000 + i * 50 for i in range(n_rows)],
            'volume': [1000 + i * 100 for i in range(n_rows)],
            'bid1': [73950 + i * 50 for i in range(n_rows)],
            'ask1': [74050 + i * 50 for i in range(n_rows)],
            'bid_qty1': [500] * n_rows,
            'ask_qty1': [300] * n_rows,
            # Features (simulated as if calculated by core_indicators)
            'ts_sec': [1704067200 + i for i in range(n_rows)],
            'ret_1s': [base_ret + np.random.normal(0, 0.001) for _ in range(n_rows)],
            'accel_1s': [0.001 + np.random.normal(0, 0.0005) for _ in range(n_rows)],
            'vol_1s': [1000 + i * 100 for i in range(n_rows)],
            'ticks_per_sec': [ticks] * n_rows,
            'z_vol_1s': [base_vol_z + np.random.normal(0, 0.2) for _ in range(n_rows)],
            'spread': [0.001] * n_rows,
            'microprice': [74000 + i * 50 for i in range(n_rows)],
            'microprice_slope': [0.5] * n_rows,
        })
    
    def test_candidate_detector_initialization(self):
        """Test CandidateDetector initialization."""
        detector = CandidateDetector()
        
        assert detector.config is not None
        assert detector.event_store is not None
        assert detector.score_threshold > 0
        assert detector.vol_z_min > 0
        assert detector.ticks_min > 0
        assert len(detector.weights) == 4
    
    def test_candidate_detector_with_custom_config(self):
        """Test CandidateDetector initialization with custom config."""
        config = Config()
        config.detection.score_threshold = 1.5
        config.detection.vol_z_min = 1.5
        config.detection.ticks_min = 3
        config.detection.weights["ret"] = 2.0
        
        detector = CandidateDetector(config)
        
        assert detector.score_threshold == 1.5
        assert detector.vol_z_min == 1.5
        assert detector.ticks_min == 3
        assert detector.weights["ret"] == 2.0
    
    def test_detect_candidates_basic(self):
        """Test basic candidate detection."""
        features_df = self.create_sample_features_data(high_signal=True)
        detector = CandidateDetector()
        
        candidates = detector.detect_candidates(features_df)
        
        # Should detect at least some candidates with high signal data
        assert len(candidates) > 0
        
        # Check candidate structure
        for candidate in candidates:
            assert 'ts' in candidate
            assert 'stock_code' in candidate
            assert 'event_type' in candidate
            assert 'score' in candidate
            assert 'evidence' in candidate
            
            assert candidate['event_type'] == 'onset_candidate'
            
            # Check evidence structure
            evidence = candidate['evidence']
            assert 'ret_1s' in evidence
            assert 'accel_1s' in evidence
            assert 'z_vol_1s' in evidence
            assert 'ticks_per_sec' in evidence
    
    def test_detect_candidates_low_signal(self):
        """Test candidate detection with low signal data."""
        features_df = self.create_sample_features_data(high_signal=False)
        detector = CandidateDetector()
        
        candidates = detector.detect_candidates(features_df)
        
        # Should detect fewer or no candidates with low signal data
        assert len(candidates) == 0
    
    def test_detect_candidates_empty_dataframe(self):
        """Test candidate detection with empty DataFrame."""
        empty_df = pd.DataFrame()
        detector = CandidateDetector()
        
        candidates = detector.detect_candidates(empty_df)
        assert len(candidates) == 0
    
    def test_detect_candidates_missing_columns(self):
        """Test candidate detection with missing required columns."""
        # DataFrame missing required columns
        incomplete_df = pd.DataFrame({
            'ts': [1704067200000],
            'stock_code': ['005930'],
            'price': [74000],
            # Missing ret_1s, accel_1s, z_vol_1s, ticks_per_sec
        })
        
        detector = CandidateDetector()
        
        with pytest.raises(ValueError, match="Missing required columns"):
            detector.detect_candidates(incomplete_df)
    
    def test_score_calculation(self):
        """Test score calculation accuracy."""
        # Create controlled test data
        features_df = pd.DataFrame({
            'ts': [1704067200000],
            'stock_code': ['005930'],
            'ret_1s': [0.01],
            'accel_1s': [0.005],
            'z_vol_1s': [2.5],
            'ticks_per_sec': [4]
        })
        
        detector = CandidateDetector()
        candidates = detector.detect_candidates(features_df)
        
        # Should have 1 candidate due to high values
        assert len(candidates) == 1
        
        # Calculate expected score manually
        expected_score = (
            detector.weights["ret"] * 0.01 +
            detector.weights["accel"] * 0.005 +
            detector.weights["z_vol"] * 2.5 +
            detector.weights["ticks"] * 4
        )
        
        actual_score = candidates[0]['score']
        assert abs(actual_score - expected_score) < 1e-6
    
    def test_threshold_adjustment(self):
        """Test that threshold adjustment affects candidate count."""
        features_df = self.create_sample_features_data(high_signal=True)
        
        # Low threshold should detect more candidates
        config_low = Config()
        config_low.detection.score_threshold = 0.5
        detector_low = CandidateDetector(config_low)
        candidates_low = detector_low.detect_candidates(features_df)
        
        # High threshold should detect fewer candidates
        config_high = Config()
        config_high.detection.score_threshold = 10.0
        detector_high = CandidateDetector(config_high)
        candidates_high = detector_high.detect_candidates(features_df)
        
        # Low threshold should detect more or equal candidates
        assert len(candidates_low) >= len(candidates_high)
    
    def test_save_candidates(self):
        """Test saving candidates to EventStore."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create custom event store with temp directory
            event_store = EventStore(path=temp_dir)
            detector = CandidateDetector(event_store=event_store)
            
            # Create sample candidates
            candidates = [
                {
                    'ts': 1704067200000,
                    'event_type': 'onset_candidate',
                    'stock_code': '005930',
                    'score': 2.5,
                    'evidence': {'ret_1s': 0.01, 'accel_1s': 0.005, 'z_vol_1s': 2.0, 'ticks_per_sec': 3}
                },
                {
                    'ts': 1704067201000,
                    'event_type': 'onset_candidate',
                    'stock_code': '005930',
                    'score': 3.0,
                    'evidence': {'ret_1s': 0.012, 'accel_1s': 0.006, 'z_vol_1s': 2.2, 'ticks_per_sec': 3}
                }
            ]
            
            # Save candidates
            success = detector.save_candidates(candidates)
            assert success == True
            
            # Verify saved events
            saved_events = event_store.load_events()
            assert len(saved_events) == 2
            
            for event in saved_events:
                assert event['event_type'] == 'onset_candidate'
                assert 'score' in event
                assert 'evidence' in event
    
    def test_detect_and_save(self):
        """Test detect_and_save method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            event_store = EventStore(path=temp_dir)
            detector = CandidateDetector(event_store=event_store)
            
            features_df = self.create_sample_features_data(high_signal=True)
            
            result = detector.detect_and_save(features_df, filename="test_candidates.jsonl")
            
            assert 'candidates_detected' in result
            assert 'save_success' in result
            assert 'events' in result
            
            assert result['candidates_detected'] > 0
            assert result['save_success'] == True
            assert len(result['events']) == result['candidates_detected']
            
            # Verify file was created
            test_file = Path(temp_dir) / "test_candidates.jsonl"
            assert test_file.exists()
    
    def test_get_detection_stats(self):
        """Test detection statistics calculation."""
        features_df = self.create_sample_features_data(high_signal=True)
        detector = CandidateDetector()
        
        stats = detector.get_detection_stats(features_df)
        
        # Check stats structure
        required_keys = [
            'total_rows', 'valid_rows', 'candidates_detected', 'detection_rate',
            'score_stats', 'condition_stats'
        ]
        
        for key in required_keys:
            assert key in stats
        
        # Check reasonable values
        assert stats['total_rows'] == len(features_df)
        assert stats['valid_rows'] <= stats['total_rows']
        assert 0 <= stats['detection_rate'] <= 1.0
        
        # Check score stats
        if stats['score_stats']:
            assert 'mean' in stats['score_stats']
            assert 'std' in stats['score_stats']
            assert 'min' in stats['score_stats']
            assert 'max' in stats['score_stats']
    
    def test_convenience_function(self):
        """Test the convenience function detect_candidates."""
        features_df = self.create_sample_features_data(high_signal=True)
        
        candidates = detect_candidates(features_df)
        
        assert isinstance(candidates, list)
        assert len(candidates) > 0
        
        # Check structure of first candidate
        if candidates:
            candidate = candidates[0]
            assert candidate['event_type'] == 'onset_candidate'
            assert 'score' in candidate
            assert 'evidence' in candidate


class TestCandidateDetectorIntegration:
    """Test integration with other components."""
    
    def test_with_real_features_data(self):
        """Test with features calculated from core_indicators."""
        # Create raw data
        raw_data = pd.DataFrame({
            'ts': [1704067200000 + i * 1000 for i in range(30)],
            'stock_code': ['005930'] * 30,
            'price': [74000 + i * 100 + np.random.randint(-50, 51) for i in range(30)],  # Strong trend
            'volume': [1000 + i * 200 + np.random.randint(-100, 101) for i in range(30)], # Increasing volume
            'bid1': [74000 + i * 100 + np.random.randint(-55, -45) for i in range(30)],
            'ask1': [74000 + i * 100 + np.random.randint(45, 55) for i in range(30)],
            'bid_qty1': [500 + np.random.randint(-50, 51) for _ in range(30)],
            'ask_qty1': [300 + np.random.randint(-50, 51) for _ in range(30)],
        })
        
        # Calculate features
        features_df = calculate_core_indicators(raw_data)
        
        # Detect candidates
        detector = CandidateDetector()
        candidates = detector.detect_candidates(features_df)
        
        # Should work without errors
        assert isinstance(candidates, list)
        
        # If candidates exist, check their structure
        for candidate in candidates:
            assert candidate['event_type'] == 'onset_candidate'
            assert isinstance(candidate['score'], (int, float))
            assert isinstance(candidate['evidence'], dict)
    
    def test_file_round_trip(self):
        """Test complete file round trip: features -> detection -> save -> load."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create features data
            features_df = pd.DataFrame({
                'ts': [1704067200000, 1704067201000],
                'stock_code': ['005930', '005930'],
                'ret_1s': [0.015, 0.012],  # High returns
                'accel_1s': [0.002, 0.003],
                'z_vol_1s': [3.0, 2.5],    # High volume z-scores
                'ticks_per_sec': [4, 3],   # High tick counts
            })
            
            # Save features to CSV
            features_path = Path(temp_dir) / "test_features.csv"
            features_df.to_csv(features_path, index=False)
            
            # Load features and detect candidates
            loaded_features = pd.read_csv(features_path)
            
            event_store = EventStore(path=temp_dir)
            detector = CandidateDetector(event_store=event_store)
            
            result = detector.detect_and_save(loaded_features, filename="candidates.jsonl")
            
            # Should detect candidates and save them
            assert result['candidates_detected'] > 0
            assert result['save_success'] == True
            
            # Load and verify saved events
            saved_events = event_store.load_events(filename="candidates.jsonl")
            assert len(saved_events) == result['candidates_detected']
            
            for event in saved_events:
                assert event['event_type'] == 'onset_candidate'