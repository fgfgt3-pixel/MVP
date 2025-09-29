"""Tests for confirmation detection functionality."""

import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
import pytest
import json

from src.detection import ConfirmDetector, confirm_candidates
from src.config_loader import Config
from src.event_store import EventStore
from src.features import calculate_core_indicators


class TestConfirmDetector:
    """Test confirmation detection functionality."""
    
    def create_sample_features_data(self, n_rows: int = 50, trend_strength: float = 1.0) -> pd.DataFrame:
        """Create sample features data for testing."""
        # Create data with controllable trend strength
        base_ts = 1704067200000
        
        return pd.DataFrame({
            'ts': [base_ts + i * 1000 for i in range(n_rows)],
            'stock_code': ['005930'] * n_rows,
            'price': [74000 + i * 50 * trend_strength for i in range(n_rows)],
            'volume': [1000 + i * 100 for i in range(n_rows)],
            'bid1': [73950 + i * 50 * trend_strength for i in range(n_rows)],
            'ask1': [74050 + i * 50 * trend_strength for i in range(n_rows)],
            'bid_qty1': [500] * n_rows,
            'ask_qty1': [300] * n_rows,
            # Features (simulated as if calculated by core_indicators)
            'ts_sec': [1704067200 + i for i in range(n_rows)],
            'ret_1s': [0.001 * trend_strength + np.random.normal(0, 0.0005) for _ in range(n_rows)],
            'accel_1s': [0.0005 + np.random.normal(0, 0.0002) for _ in range(n_rows)],
            'vol_1s': [1000 + i * 100 for i in range(n_rows)],
            'ticks_per_sec': [1] * n_rows,
            'z_vol_1s': [2.5 + np.random.normal(0, 0.3) for _ in range(n_rows)],
            'spread': [0.015 + np.random.normal(0, 0.002) for _ in range(n_rows)],
            'microprice': [74000 + i * 50 * trend_strength for i in range(n_rows)],
            'microprice_slope': [0.5 * trend_strength + np.random.normal(0, 0.1) for _ in range(n_rows)],
        })
    
    def create_sample_candidate_events(self, features_df: pd.DataFrame, n_candidates: int = 3) -> list:
        """Create sample candidate events based on features."""
        candidates = []
        
        # Select evenly spaced timestamps for candidates
        for i in range(n_candidates):
            idx = i * (len(features_df) // (n_candidates + 1))
            if idx < len(features_df):
                row = features_df.iloc[idx]
                
                candidate = {
                    'ts': row['ts'],
                    'event_type': 'onset_candidate',
                    'stock_code': row['stock_code'],
                    'score': 2.5 + i * 0.2,
                    'evidence': {
                        'ret_1s': row['ret_1s'],
                        'accel_1s': row['accel_1s'],
                        'z_vol_1s': row['z_vol_1s'],
                        'ticks_per_sec': row['ticks_per_sec']
                    }
                }
                candidates.append(candidate)
        
        return candidates
    
    def test_confirm_detector_initialization(self):
        """Test ConfirmDetector initialization."""
        detector = ConfirmDetector()
        
        assert detector.config is not None
        assert detector.event_store is not None
        assert detector.window_s > 0
        assert detector.min_axes > 0
        assert detector.vol_z_min > 0
        assert detector.spread_max > 0
    
    def test_confirm_detector_with_custom_config(self):
        """Test ConfirmDetector initialization with custom config."""
        config = Config()
        config.confirm.window_s = 30
        config.confirm.min_axes = 2
        config.confirm.vol_z_min = 1.5
        config.confirm.spread_max = 0.03
        
        detector = ConfirmDetector(config)
        
        assert detector.window_s == 30
        assert detector.min_axes == 2
        assert detector.vol_z_min == 1.5
        assert detector.spread_max == 0.03
    
    def test_confirm_candidates_basic(self):
        """Test basic candidate confirmation."""
        features_df = self.create_sample_features_data(trend_strength=1.5)  # Strong trend
        candidate_events = self.create_sample_candidate_events(features_df)
        
        detector = ConfirmDetector()
        confirmed_events = detector.confirm_candidates(features_df, candidate_events)
        
        # Should create at least some confirmations with strong trend
        assert len(confirmed_events) > 0
        
        # Check confirmation structure
        for confirmation in confirmed_events:
            assert 'ts' in confirmation
            assert 'stock_code' in confirmation
            assert 'event_type' in confirmation
            assert 'confirmed_from' in confirmation
            assert 'evidence' in confirmation
            
            assert confirmation['event_type'] == 'onset_confirmed'
            
            # Check evidence structure
            evidence = confirmation['evidence']
            assert 'axes' in evidence
            assert 'ret_1s' in evidence
            assert 'z_vol_1s' in evidence
            assert 'spread' in evidence
            assert 'microprice_slope' in evidence
            
            # Axes should be a list
            assert isinstance(evidence['axes'], list)
            assert len(evidence['axes']) > 0
    
    def test_confirm_candidates_weak_signal(self):
        """Test candidate confirmation with weak signal."""
        features_df = self.create_sample_features_data(trend_strength=0.1)  # Weak trend
        candidate_events = self.create_sample_candidate_events(features_df)
        
        detector = ConfirmDetector()
        confirmed_events = detector.confirm_candidates(features_df, candidate_events)
        
        # Should create fewer confirmations with weak signal
        assert len(confirmed_events) <= len(candidate_events)
    
    def test_confirm_candidates_empty_inputs(self):
        """Test confirmation with empty inputs."""
        detector = ConfirmDetector()
        
        # Empty features
        empty_df = pd.DataFrame()
        candidates = self.create_sample_candidate_events(self.create_sample_features_data())
        confirmed = detector.confirm_candidates(empty_df, candidates)
        assert len(confirmed) == 0
        
        # Empty candidates
        features = self.create_sample_features_data()
        empty_candidates = []
        confirmed = detector.confirm_candidates(features, empty_candidates)
        assert len(confirmed) == 0
    
    def test_confirm_candidates_missing_columns(self):
        """Test confirmation with missing required columns."""
        # Features missing required columns
        incomplete_df = pd.DataFrame({
            'ts': [1704067200000],
            'stock_code': ['005930'],
            'price': [74000],
            # Missing ret_1s, z_vol_1s, spread, microprice_slope
        })
        
        candidates = [{
            'ts': 1704067200000,
            'stock_code': '005930',
            'event_type': 'onset_candidate'
        }]
        
        detector = ConfirmDetector()
        
        with pytest.raises(ValueError, match="Missing required columns"):
            detector.confirm_candidates(incomplete_df, candidates)
    
    def test_confirmation_window(self):
        """Test that confirmation window is properly applied."""
        features_df = self.create_sample_features_data(n_rows=50)
        
        # Create candidate at the beginning
        candidate = {
            'ts': features_df.iloc[5]['ts'],  # 5th row
            'stock_code': '005930',
            'event_type': 'onset_candidate'
        }
        
        config = Config()
        config.confirm.window_s = 10  # 10 second window
        detector = ConfirmDetector(config)
        
        confirmed_events = detector.confirm_candidates(features_df, [candidate])
        
        # Confirmation should use only data within the window
        if confirmed_events:
            confirmation = confirmed_events[0]
            # Confirmation timestamp should be within window
            assert confirmation['ts'] >= candidate['ts']
            assert confirmation['ts'] <= candidate['ts'] + (10 * 1000)  # 10 seconds in ms
            assert confirmation['confirmed_from'] == candidate['ts']
    
    def test_axes_requirements(self):
        """Test minimum axes requirement."""
        features_df = self.create_sample_features_data()
        candidate_events = self.create_sample_candidate_events(features_df)
        
        # Test with min_axes = 1 (should be easier to satisfy)
        config_easy = Config()
        config_easy.confirm.min_axes = 1
        detector_easy = ConfirmDetector(config_easy)
        confirmed_easy = detector_easy.confirm_candidates(features_df, candidate_events)
        
        # Test with min_axes = 3 (should be harder to satisfy)
        config_hard = Config()
        config_hard.confirm.min_axes = 3
        detector_hard = ConfirmDetector(config_hard)
        confirmed_hard = detector_hard.confirm_candidates(features_df, candidate_events)
        
        # Easier requirement should result in more or equal confirmations
        assert len(confirmed_easy) >= len(confirmed_hard)
    
    def test_save_confirmations(self):
        """Test saving confirmations to EventStore."""
        with tempfile.TemporaryDirectory() as temp_dir:
            event_store = EventStore(path=temp_dir)
            detector = ConfirmDetector(event_store=event_store)
            
            # Create sample confirmations
            confirmations = [
                {
                    'ts': 1704067210000,
                    'event_type': 'onset_confirmed',
                    'stock_code': '005930',
                    'confirmed_from': 1704067200000,
                    'evidence': {
                        'axes': ['price', 'volume'],
                        'ret_1s': 0.01,
                        'z_vol_1s': 2.5,
                        'spread': 0.015,
                        'microprice_slope': 0.5
                    }
                }
            ]
            
            # Save confirmations
            success = detector.save_confirmations(confirmations)
            assert success == True
            
            # Verify saved events
            saved_events = event_store.load_events()
            assert len(saved_events) == 1
            
            event = saved_events[0]
            assert event['event_type'] == 'onset_confirmed'
            assert event['confirmed_from'] == 1704067200000
            assert 'axes' in event['evidence']
    
    def test_confirm_and_save(self):
        """Test confirm_and_save method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            event_store = EventStore(path=temp_dir)
            detector = ConfirmDetector(event_store=event_store)
            
            features_df = self.create_sample_features_data(trend_strength=1.5)
            candidate_events = self.create_sample_candidate_events(features_df)
            
            result = detector.confirm_and_save(features_df, candidate_events, filename="test_confirms.jsonl")
            
            assert 'candidates_processed' in result
            assert 'confirmations_created' in result
            assert 'confirmation_rate' in result
            assert 'save_success' in result
            assert 'tta_stats' in result
            assert 'events' in result
            
            assert result['candidates_processed'] == len(candidate_events)
            assert result['save_success'] == True
            assert 0 <= result['confirmation_rate'] <= 1.0
            assert len(result['events']) == result['confirmations_created']
            
            # Verify file was created
            test_file = Path(temp_dir) / "test_confirms.jsonl"
            if result['confirmations_created'] > 0:
                assert test_file.exists()
    
    def test_get_confirmation_stats(self):
        """Test confirmation statistics calculation."""
        features_df = self.create_sample_features_data()
        candidate_events = self.create_sample_candidate_events(features_df)
        
        detector = ConfirmDetector()
        stats = detector.get_confirmation_stats(features_df, candidate_events)
        
        # Check stats structure
        required_keys = [
            'candidates_processed', 'confirmations_possible', 'confirmation_rate',
            'axes_stats', 'window_stats', 'config'
        ]
        
        for key in required_keys:
            assert key in stats
        
        # Check reasonable values
        assert stats['candidates_processed'] == len(candidate_events)
        assert stats['confirmations_possible'] <= stats['candidates_processed']
        assert 0 <= stats['confirmation_rate'] <= 1.0
        
        # Check axes stats
        assert 'price' in stats['axes_stats']
        assert 'volume' in stats['axes_stats']
        assert 'friction' in stats['axes_stats']
        
        # Check config
        assert 'window_s' in stats['config']
        assert 'min_axes' in stats['config']
    
    def test_time_to_alert_calculation(self):
        """Test TTA (Time-to-Alert) calculation."""
        features_df = self.create_sample_features_data(trend_strength=1.5)
        
        # Create candidate with known timestamp
        candidate_ts = features_df.iloc[10]['ts']
        candidate = {
            'ts': candidate_ts,
            'stock_code': '005930',
            'event_type': 'onset_candidate'
        }
        
        detector = ConfirmDetector()
        result = detector.confirm_and_save(features_df, [candidate])
        
        if result['confirmations_created'] > 0:
            tta_stats = result['tta_stats']
            assert 'mean' in tta_stats
            assert 'median' in tta_stats
            assert 'min' in tta_stats
            assert 'max' in tta_stats
            
            # TTA should be positive (confirmation comes after candidate)
            assert tta_stats['mean'] >= 0
            assert tta_stats['min'] >= 0
            
            # Check that confirmed event has correct TTA
            confirmed_event = result['events'][0]
            expected_tta = (confirmed_event['ts'] - confirmed_event['confirmed_from']) / 1000.0
            assert abs(tta_stats['mean'] - expected_tta) < 0.01  # Within 10ms tolerance
    
    def test_convenience_function(self):
        """Test the convenience function confirm_candidates."""
        features_df = self.create_sample_features_data(trend_strength=1.5)
        candidate_events = self.create_sample_candidate_events(features_df)
        
        confirmed_events = confirm_candidates(features_df, candidate_events)
        
        assert isinstance(confirmed_events, list)
        
        # Check structure if confirmations exist
        for confirmation in confirmed_events:
            assert confirmation['event_type'] == 'onset_confirmed'
            assert 'confirmed_from' in confirmation
            assert 'evidence' in confirmation


class TestConfirmDetectorIntegration:
    """Test integration with other components."""
    
    def test_with_real_features_data(self):
        """Test with features calculated from core_indicators."""
        # Create raw data with strong trend
        raw_data = pd.DataFrame({
            'ts': [1704067200000 + i * 1000 for i in range(40)],
            'stock_code': ['005930'] * 40,
            'price': [74000 + i * 150 + np.random.randint(-25, 26) for i in range(40)],  # Strong trend
            'volume': [1000 + i * 300 + np.random.randint(-100, 101) for i in range(40)], # Increasing volume
            'bid1': [74000 + i * 150 + np.random.randint(-30, -20) for i in range(40)],
            'ask1': [74000 + i * 150 + np.random.randint(20, 30) for i in range(40)],
            'bid_qty1': [500 + np.random.randint(-50, 51) for _ in range(40)],
            'ask_qty1': [300 + np.random.randint(-50, 51) for _ in range(40)],
        })
        
        # Calculate features
        features_df = calculate_core_indicators(raw_data)
        
        # Create sample candidates
        candidates = [
            {
                'ts': features_df.iloc[5]['ts'],
                'stock_code': '005930',
                'event_type': 'onset_candidate'
            },
            {
                'ts': features_df.iloc[15]['ts'],
                'stock_code': '005930', 
                'event_type': 'onset_candidate'
            }
        ]
        
        # Confirm candidates
        detector = ConfirmDetector()
        confirmed_events = detector.confirm_candidates(features_df, candidates)
        
        # Should work without errors
        assert isinstance(confirmed_events, list)
        
        # If confirmations exist, check their structure
        for confirmation in confirmed_events:
            assert confirmation['event_type'] == 'onset_confirmed'
            assert isinstance(confirmation['confirmed_from'], (int, float))
            assert isinstance(confirmation['evidence'], dict)
            assert 'axes' in confirmation['evidence']
    
    def test_full_pipeline_integration(self):
        """Test complete pipeline: features -> candidates -> confirmations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            from src.detection import CandidateDetector
            
            # Create features data
            raw_data = pd.DataFrame({
                'ts': [1704067200000 + i * 1000 for i in range(30)],
                'stock_code': ['005930'] * 30,
                'price': [74000 + i * 100 for i in range(30)],  # Linear increase
                'volume': [1000 + i * 200 for i in range(30)],
                'bid1': [73950 + i * 100 for i in range(30)],
                'ask1': [74050 + i * 100 for i in range(30)],
                'bid_qty1': [500] * 30,
                'ask_qty1': [300] * 30,
            })
            
            # Calculate features
            features_df = calculate_core_indicators(raw_data)
            
            # Detect candidates (lower thresholds for testing)
            config = Config()
            config.detection.score_threshold = 1.0
            config.detection.vol_z_min = 1.0
            config.detection.ticks_min = 1
            
            candidate_detector = CandidateDetector(config)
            candidates = candidate_detector.detect_candidates(features_df)
            
            if candidates:
                # Confirm candidates
                confirm_detector = ConfirmDetector(config)
                confirmed_events = confirm_detector.confirm_candidates(features_df, candidates)
                
                # Pipeline should work end-to-end
                assert isinstance(confirmed_events, list)
                
                # Check confirmed events structure
                for confirmation in confirmed_events:
                    assert confirmation['event_type'] == 'onset_confirmed'
                    assert 'confirmed_from' in confirmation
                    
                    # confirmed_from should match a candidate timestamp
                    candidate_timestamps = [c['ts'] for c in candidates]
                    assert confirmation['confirmed_from'] in candidate_timestamps