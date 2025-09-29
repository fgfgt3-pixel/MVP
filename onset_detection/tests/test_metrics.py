"""Tests for metrics computation functionality."""

import tempfile
import time
import json
import pandas as pd
from pathlib import Path
import pytest

from src.metrics import MetricsCalculator, compute_in_window, compute_fp_rate, compute_tta
from src.event_store import EventStore, create_event
from src.config_loader import Config


class TestMetricsCalculator:
    """Test metrics calculation functionality."""
    
    def create_sample_events(self, base_time: float = None) -> list:
        """Create sample events for testing."""
        if base_time is None:
            base_time = time.time()
        
        return [
            create_event(base_time + 5, "onset_candidate", stock_code="005930"),
            create_event(base_time + 10, "onset_confirmed", stock_code="005930", score=2.5),
            create_event(base_time + 50, "onset_confirmed", stock_code="005930", score=1.8),  # FP
            create_event(base_time + 95, "onset_candidate", stock_code="000660"),
            create_event(base_time + 100, "onset_confirmed", stock_code="000660", score=3.2),
        ]
    
    def create_sample_labels(self, base_time: float = None) -> pd.DataFrame:
        """Create sample labels for testing."""
        if base_time is None:
            base_time = time.time()
        
        labels_data = {
            'timestamp_start': [base_time, base_time + 90],
            'timestamp_end': [base_time + 30, base_time + 120],
            'stock_code': ['005930', '000660'],
            'label_type': ['onset', 'onset']
        }
        return pd.DataFrame(labels_data)
    
    def test_metrics_calculator_initialization(self):
        """Test MetricsCalculator initialization."""
        calculator = MetricsCalculator()
        assert calculator.config is not None
        assert calculator.path_manager is not None
    
    def test_load_labels_basic(self):
        """Test basic label loading functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test labels file
            labels_data = {
                'timestamp_start': [1704067205000, 1704067300000],
                'timestamp_end': [1704067225000, 1704067320000],
                'stock_code': ['005930', '000660'],
                'label_type': ['onset', 'onset']
            }
            labels_df = pd.DataFrame(labels_data)
            
            # Save to CSV
            labels_path = Path(temp_dir) / "test_labels.csv"
            labels_df.to_csv(labels_path, index=False)
            
            # Test loading
            calculator = MetricsCalculator()
            loaded_labels = calculator.load_labels(str(labels_path))
            
            assert len(loaded_labels) == 2
            assert 'timestamp_start' in loaded_labels.columns
            assert 'timestamp_end' in loaded_labels.columns
            assert 'stock_code' in loaded_labels.columns
            assert 'label_type' in loaded_labels.columns
            
            # Check data types
            assert pd.api.types.is_numeric_dtype(loaded_labels['timestamp_start'])
            assert pd.api.types.is_numeric_dtype(loaded_labels['timestamp_end'])
    
    def test_load_labels_missing_file(self):
        """Test loading labels from non-existent file."""
        calculator = MetricsCalculator()
        
        with pytest.raises(FileNotFoundError):
            calculator.load_labels("non_existent_file.csv")
    
    def test_load_labels_missing_columns(self):
        """Test loading labels with missing required columns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create invalid labels file
            invalid_data = pd.DataFrame({'only_one_column': [1, 2, 3]})
            labels_path = Path(temp_dir) / "invalid_labels.csv"
            invalid_data.to_csv(labels_path, index=False)
            
            calculator = MetricsCalculator()
            
            with pytest.raises(ValueError, match="Missing required columns"):
                calculator.load_labels(str(labels_path))
    
    def test_compute_in_window_detection(self):
        """Test in-window detection rate computation."""
        base_time = time.time()
        events = self.create_sample_events(base_time)
        labels_df = self.create_sample_labels(base_time)
        
        calculator = MetricsCalculator()
        result = calculator.compute_in_window_detection(events, labels_df)
        
        # Should detect both labeled intervals (both have confirmed events within windows)
        assert result["n_labels"] == 2
        assert result["n_detected"] == 2
        assert result["recall"] == 1.0
        assert len(result["detected_label_indices"]) == 2
    
    def test_compute_in_window_detection_empty_labels(self):
        """Test in-window detection with empty labels."""
        events = self.create_sample_events()
        empty_labels = pd.DataFrame(columns=['timestamp_start', 'timestamp_end', 'stock_code', 'label_type'])
        
        calculator = MetricsCalculator()
        result = calculator.compute_in_window_detection(events, empty_labels)
        
        assert result["recall"] == 0.0
        assert result["n_labels"] == 0
        assert result["n_detected"] == 0
    
    def test_compute_false_positive_rate(self):
        """Test false positive rate computation."""
        base_time = time.time()
        events = self.create_sample_events(base_time)
        labels_df = self.create_sample_labels(base_time)
        
        calculator = MetricsCalculator()
        result = calculator.compute_false_positive_rate(events, labels_df, trading_hours=1.0)
        
        # Should have 1 FP (the event at base_time + 50 is outside label windows)
        assert result["n_confirmed"] == 3  # Total confirmed events
        assert result["n_fp"] == 1
        assert result["fp_per_hour"] == 1.0
        assert len(result["fp_events"]) == 1
    
    def test_compute_false_positive_rate_no_events(self):
        """Test FP rate with no confirmed events."""
        empty_events = []
        labels_df = self.create_sample_labels()
        
        calculator = MetricsCalculator()
        result = calculator.compute_false_positive_rate(empty_events, labels_df, trading_hours=6.5)
        
        assert result["fp_per_hour"] == 0.0
        assert result["n_fp"] == 0
        assert result["n_confirmed"] == 0
    
    def test_compute_time_to_alert(self):
        """Test time-to-alert computation."""
        base_time = time.time()
        events = self.create_sample_events(base_time)
        labels_df = self.create_sample_labels(base_time)
        
        calculator = MetricsCalculator()
        result = calculator.compute_time_to_alert(events, labels_df)
        
        # Should have 2 TTA samples (one for each label)
        assert result["n_tta_samples"] == 2
        assert result["tta_p50"] > 0
        assert result["tta_p95"] > 0
        assert result["tta_mean"] > 0
        assert len(result["tta_values"]) == 2
        
        # First TTA: base_time + 10 - base_time = 10 seconds
        # Second TTA: base_time + 100 - (base_time + 90) = 10 seconds
        assert 10.0 in result["tta_values"]
    
    def test_compute_time_to_alert_empty_labels(self):
        """Test TTA computation with empty labels."""
        events = self.create_sample_events()
        empty_labels = pd.DataFrame(columns=['timestamp_start', 'timestamp_end', 'stock_code', 'label_type'])
        
        calculator = MetricsCalculator()
        result = calculator.compute_time_to_alert(events, empty_labels)
        
        assert result["tta_p50"] == 0.0
        assert result["tta_p95"] == 0.0
        assert result["n_tta_samples"] == 0
    
    def test_compute_all_metrics(self):
        """Test computing all metrics at once."""
        base_time = time.time()
        events = self.create_sample_events(base_time)
        labels_df = self.create_sample_labels(base_time)
        
        calculator = MetricsCalculator()
        metrics = calculator.compute_all_metrics(events, labels_df, trading_hours=2.0)
        
        # Check all required metrics are present
        required_keys = [
            "recall", "fp_per_hour", "tta_p95", "tta_p50", "tta_mean",
            "n_events", "n_labels", "n_detected", "n_confirmed", "n_fp", 
            "n_tta_samples", "event_counts", "trading_hours"
        ]
        
        for key in required_keys:
            assert key in metrics
        
        # Verify some values
        assert metrics["recall"] == 1.0
        assert metrics["fp_per_hour"] == 0.5  # 1 FP / 2.0 hours
        assert metrics["n_events"] == 5
        assert metrics["n_labels"] == 2
        assert metrics["n_detected"] == 2
        assert metrics["trading_hours"] == 2.0
        
        # Check event counts
        assert "onset_candidate" in metrics["event_counts"]
        assert "onset_confirmed" in metrics["event_counts"]
        assert metrics["event_counts"]["onset_candidate"] == 2
        assert metrics["event_counts"]["onset_confirmed"] == 3
    
    def test_save_metrics_report(self):
        """Test saving metrics report to JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_time = time.time()
            events = self.create_sample_events(base_time)
            labels_df = self.create_sample_labels(base_time)
            
            calculator = MetricsCalculator()
            metrics = calculator.compute_all_metrics(events, labels_df)
            
            # Save to specific path
            output_path = Path(temp_dir) / "test_metrics.json"
            saved_path = calculator.save_metrics_report(metrics, output_path)
            
            assert saved_path == output_path
            assert output_path.exists()
            
            # Load and verify content
            with open(output_path, 'r') as f:
                saved_metrics = json.load(f)
            
            assert saved_metrics["recall"] == metrics["recall"]
            assert saved_metrics["fp_per_hour"] == metrics["fp_per_hour"]
            assert saved_metrics["n_events"] == metrics["n_events"]
    
    def test_save_metrics_report_default_path(self):
        """Test saving metrics report to default path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create custom config with temp directory
            config = Config()
            config.paths.reports = temp_dir
            
            base_time = time.time()
            events = self.create_sample_events(base_time)
            labels_df = self.create_sample_labels(base_time)
            
            calculator = MetricsCalculator(config)
            metrics = calculator.compute_all_metrics(events, labels_df)
            
            # Save to default path
            saved_path = calculator.save_metrics_report(metrics)
            
            expected_path = Path(temp_dir) / "eval_summary.json"
            assert saved_path == expected_path
            assert expected_path.exists()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_compute_in_window_function(self):
        """Test compute_in_window convenience function."""
        base_time = time.time()
        events = [
            create_event(base_time + 10, "onset_confirmed", stock_code="005930")
        ]
        labels_data = {
            'timestamp_start': [base_time],
            'timestamp_end': [base_time + 20],
            'stock_code': ['005930'],
            'label_type': ['onset']
        }
        labels_df = pd.DataFrame(labels_data)
        
        recall = compute_in_window(events, labels_df)
        assert recall == 1.0
    
    def test_compute_fp_rate_function(self):
        """Test compute_fp_rate convenience function."""
        base_time = time.time()
        events = [
            create_event(base_time + 10, "onset_confirmed", stock_code="005930"),  # FP
            create_event(base_time + 50, "onset_confirmed", stock_code="000660")   # TP
        ]
        labels_data = {
            'timestamp_start': [base_time + 40],
            'timestamp_end': [base_time + 60],
            'stock_code': ['000660'],
            'label_type': ['onset']
        }
        labels_df = pd.DataFrame(labels_data)
        
        fp_rate = compute_fp_rate(events, labels_df, trading_hours=2.0)
        assert fp_rate == 0.5  # 1 FP / 2.0 hours
    
    def test_compute_tta_function(self):
        """Test compute_tta convenience function."""
        base_time = time.time()
        events = [
            create_event(base_time + 10, "onset_confirmed", stock_code="005930")
        ]
        labels_data = {
            'timestamp_start': [base_time],
            'timestamp_end': [base_time + 20],
            'stock_code': ['005930'],
            'label_type': ['onset']
        }
        labels_df = pd.DataFrame(labels_data)
        
        tta_p95 = compute_tta(events, labels_df)
        assert tta_p95 == 10.0  # 10 second delay


class TestMetricsIntegration:
    """Test integration with other components."""
    
    def test_metrics_with_event_store(self):
        """Test metrics computation using EventStore."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create event store and save events
            store = EventStore(path=temp_dir)
            base_time = time.time()
            
            events_to_save = [
                create_event(base_time + 5, "onset_candidate", stock_code="005930"),
                create_event(base_time + 10, "onset_confirmed", stock_code="005930", score=2.5),
                create_event(base_time + 15, "onset_confirmed", stock_code="005930", score=1.8),
            ]
            
            for event in events_to_save:
                store.save_event(event)
            
            # Load events and create labels
            loaded_events = store.load_events()
            labels_data = {
                'timestamp_start': [base_time],
                'timestamp_end': [base_time + 20],
                'stock_code': ['005930'],
                'label_type': ['onset']
            }
            labels_df = pd.DataFrame(labels_data)
            
            # Compute metrics
            calculator = MetricsCalculator()
            metrics = calculator.compute_all_metrics(loaded_events, labels_df)
            
            assert metrics["n_events"] == 3
            assert metrics["n_confirmed"] == 2
            assert metrics["recall"] == 1.0  # Label interval contains confirmed events
    
    def test_metrics_edge_case_milliseconds(self):
        """Test TTA computation with millisecond timestamps."""
        base_time_ms = time.time() * 1000  # Convert to milliseconds
        
        events = [
            create_event(base_time_ms + 5000, "onset_confirmed", stock_code="005930")  # +5 seconds
        ]
        labels_data = {
            'timestamp_start': [base_time_ms],
            'timestamp_end': [base_time_ms + 10000],  # +10 seconds
            'stock_code': ['005930'],
            'label_type': ['onset']
        }
        labels_df = pd.DataFrame(labels_data)
        
        calculator = MetricsCalculator()
        result = calculator.compute_time_to_alert(events, labels_df)
        
        # Should convert from ms to seconds
        assert result["tta_values"][0] == 5.0
        assert result["tta_p95"] == 5.0