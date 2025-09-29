"""Tests for quality reporting functionality."""

import json
import tempfile
from pathlib import Path
import pytest

from src.reporting import QualityReporter, generate_quality_report
from src.config_loader import Config


class TestQualityReporter:
    """Test quality reporting functionality."""
    
    def create_sample_events(self, scenario: str = "basic") -> list:
        """Create sample events for testing."""
        base_ts = 1704067200000
        
        if scenario == "basic":
            return [
                # First candidate and confirmation
                {
                    'ts': base_ts,
                    'event_type': 'onset_candidate',
                    'stock_code': '005930',
                    'score': 2.5
                },
                {
                    'ts': base_ts + 5000,  # 5 seconds later
                    'event_type': 'onset_confirmed',
                    'stock_code': '005930',
                    'confirmed_from': base_ts
                },
                # Second candidate rejected
                {
                    'ts': base_ts + 30000,  # 30 seconds after confirmation
                    'event_type': 'onset_candidate',
                    'stock_code': '005930',
                    'score': 2.8
                },
                {
                    'ts': base_ts + 35000,
                    'event_type': 'onset_rejected_refractory',
                    'stock_code': '005930',
                    'rejected_at': base_ts + 35000,
                    'original_score': 2.8
                },
                # Third candidate and confirmation for different stock
                {
                    'ts': base_ts + 60000,
                    'event_type': 'onset_candidate',
                    'stock_code': '000660',
                    'score': 3.0
                },
                {
                    'ts': base_ts + 68000,  # 8 seconds later
                    'event_type': 'onset_confirmed',
                    'stock_code': '000660',
                    'confirmed_from': base_ts + 60000
                }
            ]
        
        elif scenario == "no_confirmations":
            return [
                {
                    'ts': base_ts,
                    'event_type': 'onset_candidate',
                    'stock_code': '005930',
                    'score': 2.5
                },
                {
                    'ts': base_ts + 10000,
                    'event_type': 'onset_candidate',
                    'stock_code': '000660',
                    'score': 2.8
                }
            ]
        
        elif scenario == "only_rejections":
            return [
                {
                    'ts': base_ts,
                    'event_type': 'onset_candidate',
                    'stock_code': '005930',
                    'score': 2.5
                },
                {
                    'ts': base_ts + 5000,
                    'event_type': 'onset_rejected_refractory',
                    'stock_code': '005930',
                    'rejected_at': base_ts + 5000,
                    'original_score': 2.5
                }
            ]
        
        elif scenario == "high_tta":
            return [
                {
                    'ts': base_ts,
                    'event_type': 'onset_candidate',
                    'stock_code': '005930',
                    'score': 2.5
                },
                {
                    'ts': base_ts + 15000,  # 15 seconds later (high TTA)
                    'event_type': 'onset_confirmed',
                    'stock_code': '005930',
                    'confirmed_from': base_ts
                }
            ]
        
        else:
            return []
    
    def test_quality_reporter_initialization(self):
        """Test QualityReporter initialization."""
        reporter = QualityReporter()
        
        assert reporter.config is not None
        assert reporter.path_manager is not None
        assert reporter.event_store is not None
    
    def test_quality_reporter_with_custom_config(self):
        """Test QualityReporter initialization with custom config."""
        config = Config()
        config.refractory.duration_s = 60
        config.confirm.window_s = 30
        config.detection.score_threshold = 3.0
        
        reporter = QualityReporter(config)
        
        assert reporter.config.refractory.duration_s == 60
        assert reporter.config.confirm.window_s == 30
        assert reporter.config.detection.score_threshold == 3.0
    
    def test_analyze_events_empty_list(self):
        """Test analyzing empty event list."""
        reporter = QualityReporter()
        
        report = reporter.analyze_events([])
        
        assert report['n_candidates'] == 0
        assert report['n_confirms'] == 0
        assert report['n_rejected'] == 0
        assert report['confirm_rate'] == 0.0
        assert report['rejection_rate'] == 0.0
        assert report['tta_avg'] == 0.0
        assert report['tta_p95'] == 0.0
        assert report['stocks_analyzed'] == 0
        assert report['total_events'] == 0
    
    def test_analyze_events_basic_scenario(self):
        """Test analyzing basic event scenario."""
        reporter = QualityReporter()
        events = self.create_sample_events("basic")
        
        report = reporter.analyze_events(events)
        
        assert report['n_candidates'] == 3
        assert report['n_confirms'] == 2
        assert report['n_rejected'] == 1
        assert report['total_events'] == 6
        assert report['stocks_analyzed'] == 2  # Two different stock codes
        
        # Calculate expected rates
        assert report['confirm_rate'] == pytest.approx(2/3, rel=1e-2)  # 2 confirms out of 3 candidates
        assert report['rejection_rate'] == pytest.approx(1/3, rel=1e-2)  # 1 rejection out of 3 candidates
        
        # TTA should be calculated (5s and 8s)
        assert report['tta_avg'] == pytest.approx(6.5, rel=1e-1)  # (5 + 8) / 2
        assert report['tta_median'] == pytest.approx(6.5, rel=1e-1)  # median of [5, 8]
        assert report['tta_p95'] > 0
        assert report['tta_min'] == 5.0
        assert report['tta_max'] == 8.0
        
        # Check event type breakdown
        assert 'onset_candidate' in report['event_types']
        assert 'onset_confirmed' in report['event_types']
        assert 'onset_rejected_refractory' in report['event_types']
        assert report['event_types']['onset_candidate'] == 3
        assert report['event_types']['onset_confirmed'] == 2
        assert report['event_types']['onset_rejected_refractory'] == 1
    
    def test_analyze_events_no_confirmations(self):
        """Test analyzing events with no confirmations."""
        reporter = QualityReporter()
        events = self.create_sample_events("no_confirmations")
        
        report = reporter.analyze_events(events)
        
        assert report['n_candidates'] == 2
        assert report['n_confirms'] == 0
        assert report['n_rejected'] == 0
        assert report['confirm_rate'] == 0.0
        assert report['rejection_rate'] == 0.0
        assert report['tta_avg'] == 0.0
        assert report['tta_p95'] == 0.0
        assert report['stocks_analyzed'] == 2
    
    def test_analyze_events_only_rejections(self):
        """Test analyzing events with only rejections."""
        reporter = QualityReporter()
        events = self.create_sample_events("only_rejections")
        
        report = reporter.analyze_events(events)
        
        assert report['n_candidates'] == 1
        assert report['n_confirms'] == 0
        assert report['n_rejected'] == 1
        assert report['confirm_rate'] == 0.0
        assert report['rejection_rate'] == 1.0
        assert report['tta_avg'] == 0.0  # No confirmations
    
    def test_analyze_events_high_tta(self):
        """Test analyzing events with high TTA."""
        reporter = QualityReporter()
        events = self.create_sample_events("high_tta")
        
        report = reporter.analyze_events(events)
        
        assert report['n_candidates'] == 1
        assert report['n_confirms'] == 1
        assert report['confirm_rate'] == 1.0
        assert report['tta_avg'] == 15.0  # 15 seconds TTA
        assert report['tta_median'] == 15.0
        assert report['tta_p95'] == 15.0
    
    def test_load_events_from_files(self):
        """Test loading events from JSONL files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Create test JSONL files
            events1 = self.create_sample_events("basic")[:3]  # First 3 events
            events2 = self.create_sample_events("basic")[3:]  # Last 3 events
            
            file1 = tmp_path / "events1.jsonl"
            file2 = tmp_path / "events2.jsonl"
            
            # Write events to files
            with open(file1, 'w') as f:
                for event in events1:
                    json.dump(event, f)
                    f.write('\n')
            
            with open(file2, 'w') as f:
                for event in events2:
                    json.dump(event, f)
                    f.write('\n')
            
            # Load events
            reporter = QualityReporter()
            loaded_events = reporter.load_events_from_files([file1, file2])
            
            assert len(loaded_events) == 6  # Should load all events
            
            # Events should be the same as original (may be in different order)
            original_events = self.create_sample_events("basic")
            loaded_timestamps = [e['ts'] for e in loaded_events]
            original_timestamps = [e['ts'] for e in original_events]
            assert sorted(loaded_timestamps) == sorted(original_timestamps)
    
    def test_load_events_from_nonexistent_files(self):
        """Test loading events from non-existent files."""
        reporter = QualityReporter()
        
        # Should return empty list for non-existent files
        events = reporter.load_events_from_files(["/nonexistent/file.jsonl"])
        
        assert len(events) == 0
    
    def test_save_report(self):
        """Test saving quality report to JSON file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "test_report.json"
            
            reporter = QualityReporter()
            events = self.create_sample_events("basic")
            report = reporter.analyze_events(events)
            
            success = reporter.save_report(report, output_path)
            
            assert success == True
            assert output_path.exists()
            
            # Verify file contents
            with open(output_path, 'r') as f:
                loaded_report = json.load(f)
            
            assert loaded_report['n_candidates'] == report['n_candidates']
            assert loaded_report['n_confirms'] == report['n_confirms']
            assert loaded_report['confirm_rate'] == report['confirm_rate']
    
    def test_generate_report_with_events(self):
        """Test generating report directly from events."""
        reporter = QualityReporter()
        events = self.create_sample_events("basic")
        
        report = reporter.generate_report(events=events)
        
        assert report['n_candidates'] == 3
        assert report['n_confirms'] == 2
        assert report['total_events'] == 6
    
    def test_generate_and_save_report(self):
        """Test generating and saving report in one operation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "combined_report.json"
            
            reporter = QualityReporter()
            events = self.create_sample_events("basic")
            
            report = reporter.generate_and_save_report(output_path, events=events)
            
            assert '_metadata' in report
            assert report['_metadata']['save_success'] == True
            assert output_path.exists()
            
            # Check the main report data
            assert report['n_candidates'] == 3
            assert report['n_confirms'] == 2
    
    def test_print_summary(self, capsys):
        """Test printing summary of quality report."""
        reporter = QualityReporter()
        events = self.create_sample_events("basic")
        report = reporter.analyze_events(events)
        
        reporter.print_summary(report)
        
        captured = capsys.readouterr()
        output = captured.out
        
        assert "ONSET DETECTION QUALITY REPORT" in output
        assert "Total Events Analyzed: 6" in output
        assert "Candidates: 3" in output
        assert "Confirmations: 2" in output
        assert "Confirmation Rate:" in output
        assert "Time-to-Alert (TTA) Statistics:" in output
    
    def test_generate_quality_report_function(self):
        """Test the convenience function."""
        events = self.create_sample_events("basic")
        
        report = generate_quality_report(events=events)
        
        assert report['n_candidates'] == 3
        assert report['n_confirms'] == 2
        assert report['total_events'] == 6
    
    def test_generate_quality_report_function_with_save(self):
        """Test the convenience function with saving."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "function_report.json"
            events = self.create_sample_events("basic")
            
            report = generate_quality_report(events=events, output_path=output_path)
            
            assert '_metadata' in report
            assert report['_metadata']['save_success'] == True
            assert output_path.exists()
    
    def test_config_in_report(self):
        """Test that configuration is included in report."""
        config = Config()
        config.refractory.duration_s = 90
        config.confirm.window_s = 25
        config.detection.score_threshold = 2.5
        
        reporter = QualityReporter(config)
        events = self.create_sample_events("basic")
        report = reporter.analyze_events(events)
        
        assert 'config_used' in report
        config_used = report['config_used']
        assert config_used['refractory_duration_s'] == 90
        assert config_used['confirm_window_s'] == 25
        assert config_used['detection_threshold'] == 2.5
    
    def test_malformed_events_handling(self):
        """Test handling of malformed events."""
        # Create events with missing required fields
        malformed_events = [
            {'ts': 1704067200000},  # Missing event_type
            {'event_type': 'onset_candidate'},  # Missing ts
            {
                'ts': 1704067200000,
                'event_type': 'onset_candidate',
                'stock_code': '005930',
                'score': 2.5
            },  # Valid event
        ]
        
        reporter = QualityReporter()
        report = reporter.analyze_events(malformed_events)
        
        # Should process all events, counting by event_type regardless of missing fields
        assert report['total_events'] == 3
        assert report['n_candidates'] == 2  # Both events with event_type='onset_candidate'
        
        # Should count event types correctly
        assert 'onset_candidate' in report['event_types']
        assert 'unknown' in report['event_types']
        assert report['event_types']['onset_candidate'] == 2
        assert report['event_types']['unknown'] == 1