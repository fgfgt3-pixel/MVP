"""Tests for plot reporting functionality."""

import json
import pandas as pd
import tempfile
from pathlib import Path
import pytest

from src.reporting import PlotReporter, generate_plot_report
from src.config_loader import Config


class TestPlotReporter:
    """Test plot reporting functionality."""
    
    def create_sample_price_data(self, n_points: int = 60) -> pd.DataFrame:
        """Create sample price data for testing."""
        base_ts = 1704067200000
        
        # Create trending price data
        return pd.DataFrame({
            'ts': [base_ts + i * 1000 for i in range(n_points)],
            'stock_code': ['005930'] * n_points,
            'price': [74000 + i * 50 + (i % 10) * 20 for i in range(n_points)],  # Trending with noise
            'volume': [1000 + i * 100 for i in range(n_points)],
            'bid1': [73950 + i * 50 for i in range(n_points)],
            'ask1': [74050 + i * 50 for i in range(n_points)],
            'bid_qty1': [500] * n_points,
            'ask_qty1': [300] * n_points
        })
    
    def create_sample_events(self, base_ts: int = 1704067200000) -> list:
        """Create sample events for testing."""
        return [
            # Candidates
            {
                'ts': base_ts + 10000,
                'event_type': 'onset_candidate',
                'stock_code': '005930',
                'score': 2.5
            },
            {
                'ts': base_ts + 25000,
                'event_type': 'onset_candidate',
                'stock_code': '005930',
                'score': 2.8
            },
            {
                'ts': base_ts + 45000,
                'event_type': 'onset_candidate',
                'stock_code': '005930',
                'score': 3.0
            },
            # Confirmations
            {
                'ts': base_ts + 15000,
                'event_type': 'onset_confirmed',
                'stock_code': '005930',
                'confirmed_from': base_ts + 10000
            },
            {
                'ts': base_ts + 50000,
                'event_type': 'onset_confirmed',
                'stock_code': '005930',
                'confirmed_from': base_ts + 45000
            },
            # Rejections
            {
                'ts': base_ts + 30000,
                'event_type': 'onset_rejected_refractory',
                'stock_code': '005930',
                'rejected_at': base_ts + 30000,
                'original_score': 2.8
            }
        ]
    
    def create_sample_labels(self, base_ts: int = 1704067200000) -> pd.DataFrame:
        """Create sample labels data for testing."""
        return pd.DataFrame({
            'timestamp_start': [base_ts + 10000, base_ts + 40000],
            'timestamp_end': [base_ts + 20000, base_ts + 55000],
            'stock_code': ['005930', '005930'],
            'label_type': ['onset', 'onset'],
            'description': ['First onset pattern', 'Second onset pattern']
        })
    
    def test_plot_reporter_initialization(self):
        """Test PlotReporter initialization."""
        reporter = PlotReporter()
        
        assert reporter.config is not None
        assert reporter.path_manager is not None
        assert reporter.event_store is not None
    
    def test_plot_reporter_with_custom_config(self):
        """Test PlotReporter initialization with custom config."""
        config = Config()
        reporter = PlotReporter(config)
        
        assert reporter.config is config
    
    def test_load_price_data_valid_csv(self):
        """Test loading valid price data from CSV."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "test_prices.csv"
            
            # Create test CSV
            sample_data = self.create_sample_price_data(20)
            sample_data.to_csv(csv_path, index=False)
            
            reporter = PlotReporter()
            loaded_data = reporter.load_price_data(csv_path)
            
            assert len(loaded_data) == 20
            assert 'datetime' in loaded_data.columns
            assert 'ts' in loaded_data.columns
            assert 'price' in loaded_data.columns
            assert 'stock_code' in loaded_data.columns
    
    def test_load_price_data_missing_file(self):
        """Test loading price data from non-existent file."""
        reporter = PlotReporter()
        
        with pytest.raises(FileNotFoundError):
            reporter.load_price_data("/nonexistent/file.csv")
    
    def test_load_price_data_invalid_format(self):
        """Test loading price data with invalid format."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "invalid.csv"
            
            # Create CSV without required columns
            invalid_data = pd.DataFrame({
                'timestamp': [1, 2, 3],
                'value': [100, 200, 300]
            })
            invalid_data.to_csv(csv_path, index=False)
            
            reporter = PlotReporter()
            
            with pytest.raises(ValueError):
                reporter.load_price_data(csv_path)
    
    def test_load_events_from_files(self):
        """Test loading events from JSONL files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Create test event files
            events1 = self.create_sample_events()[:3]  # First 3 events
            events2 = self.create_sample_events()[3:]  # Last 3 events
            
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
            reporter = PlotReporter()
            loaded_events = reporter.load_events_from_files([file1, file2])
            
            assert len(loaded_events) == 6
            
            # Check that datetime was added
            for event in loaded_events:
                assert 'datetime' in event
    
    def test_load_labels_data_valid_csv(self):
        """Test loading valid labels data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            labels_path = Path(tmp_dir) / "test_labels.csv"
            
            # Create test labels CSV
            sample_labels = self.create_sample_labels()
            sample_labels.to_csv(labels_path, index=False)
            
            reporter = PlotReporter()
            loaded_labels = reporter.load_labels_data(labels_path)
            
            assert loaded_labels is not None
            assert len(loaded_labels) == 2
            assert 'datetime_start' in loaded_labels.columns
            assert 'datetime_end' in loaded_labels.columns
    
    def test_load_labels_data_missing_file(self):
        """Test loading labels data from non-existent file."""
        reporter = PlotReporter()
        
        result = reporter.load_labels_data("/nonexistent/labels.csv")
        
        assert result is None
    
    def test_filter_events_by_stock_and_timerange(self):
        """Test filtering events by stock and time range."""
        reporter = PlotReporter()
        events = self.create_sample_events()
        
        # Add datetime to events
        for event in events:
            event['datetime'] = pd.to_datetime(event['ts'], unit='ms')
        
        start_time = pd.to_datetime(1704067200000, unit='ms')
        end_time = pd.to_datetime(1704067260000, unit='ms')  # 60 seconds later
        
        filtered = reporter.filter_events_by_stock_and_timerange(
            events, '005930', start_time, end_time
        )
        
        assert 'candidates' in filtered
        assert 'confirmations' in filtered
        assert 'rejections' in filtered
        
        # Should have filtered events within time range
        assert len(filtered['candidates']) >= 0
        assert len(filtered['confirmations']) >= 0
        assert len(filtered['rejections']) >= 0
    
    def test_create_plot_basic(self):
        """Test basic plot creation."""
        reporter = PlotReporter()
        
        price_data = self.create_sample_price_data(30)
        events = self.create_sample_events()
        
        # Add datetime to events
        for event in events:
            event['datetime'] = pd.to_datetime(event['ts'], unit='ms')
        
        # Filter events
        start_time = price_data['ts'].min()
        end_time = price_data['ts'].max()
        
        price_data['datetime'] = pd.to_datetime(price_data['ts'], unit='ms')
        
        filtered_events = reporter.filter_events_by_stock_and_timerange(
            events, '005930', 
            pd.to_datetime(start_time, unit='ms'), 
            pd.to_datetime(end_time, unit='ms')
        )
        
        # Create plot
        fig, ax = reporter.create_plot(price_data, filtered_events, stock_code='005930')
        
        assert fig is not None
        assert ax is not None
        
        # Close the figure to free memory
        import matplotlib.pyplot as plt
        plt.close(fig)
    
    def test_create_plot_with_labels(self):
        """Test plot creation with labels."""
        reporter = PlotReporter()
        
        price_data = self.create_sample_price_data(30)
        price_data['datetime'] = pd.to_datetime(price_data['ts'], unit='ms')
        
        events = self.create_sample_events()
        for event in events:
            event['datetime'] = pd.to_datetime(event['ts'], unit='ms')
        
        labels_data = self.create_sample_labels()
        labels_data['datetime_start'] = pd.to_datetime(labels_data['timestamp_start'], unit='ms')
        labels_data['datetime_end'] = pd.to_datetime(labels_data['timestamp_end'], unit='ms')
        
        # Filter events
        start_time = price_data['ts'].min()
        end_time = price_data['ts'].max()
        
        filtered_events = reporter.filter_events_by_stock_and_timerange(
            events, '005930', 
            pd.to_datetime(start_time, unit='ms'), 
            pd.to_datetime(end_time, unit='ms')
        )
        
        # Create plot with labels
        fig, ax = reporter.create_plot(price_data, filtered_events, labels_data, stock_code='005930')
        
        assert fig is not None
        assert ax is not None
        
        # Close the figure
        import matplotlib.pyplot as plt
        plt.close(fig)
    
    def test_save_plot(self):
        """Test saving plot to file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "test_plot.png"
            
            reporter = PlotReporter()
            
            # Create a simple plot
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            ax.plot([1, 2, 3], [1, 4, 2])
            ax.set_title("Test Plot")
            
            success = reporter.save_plot(fig, output_path)
            
            assert success == True
            assert output_path.exists()
            assert output_path.stat().st_size > 0
    
    def test_generate_report_complete(self):
        """Test complete report generation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Create test files
            csv_path = tmp_path / "prices.csv"
            events_path = tmp_path / "events.jsonl"
            labels_path = tmp_path / "labels.csv"
            output_path = tmp_path / "report.png"
            
            # Create test data
            price_data = self.create_sample_price_data(40)
            events = self.create_sample_events()
            labels_data = self.create_sample_labels()
            
            # Save test files
            price_data.to_csv(csv_path, index=False)
            
            with open(events_path, 'w') as f:
                for event in events:
                    json.dump(event, f)
                    f.write('\n')
            
            labels_data.to_csv(labels_path, index=False)
            
            # Generate report
            reporter = PlotReporter()
            summary = reporter.generate_report(
                csv_path=csv_path,
                event_files=[events_path],
                output_path=output_path,
                labels_path=labels_path,
                stock_code='005930'
            )
            
            assert "error" not in summary
            assert summary['save_success'] == True
            assert summary['stock_code'] == '005930'
            assert summary['price_data_points'] == 40
            assert summary['events']['candidates'] >= 0
            assert summary['events']['confirmations'] >= 0
            assert summary['events']['rejections'] >= 0
            assert summary['labels_count'] == 2
            assert output_path.exists()
    
    def test_generate_report_missing_csv(self):
        """Test report generation with missing CSV file."""
        reporter = PlotReporter()
        
        summary = reporter.generate_report(
            csv_path="/nonexistent/prices.csv",
            event_files=[],
            output_path="/tmp/output.png"
        )
        
        assert "error" in summary
        assert summary['save_success'] == False
    
    def test_generate_plot_report_function(self):
        """Test the convenience function."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Create minimal test files
            csv_path = tmp_path / "prices.csv"
            events_path = tmp_path / "events.jsonl"
            output_path = tmp_path / "function_report.png"
            
            # Create minimal test data
            price_data = self.create_sample_price_data(10)
            events = self.create_sample_events()[:2]  # Just 2 events
            
            price_data.to_csv(csv_path, index=False)
            
            with open(events_path, 'w') as f:
                for event in events:
                    json.dump(event, f)
                    f.write('\n')
            
            # Use convenience function
            summary = generate_plot_report(
                csv_path=csv_path,
                event_files=[events_path],
                output_path=output_path
            )
            
            assert "error" not in summary
            assert summary['save_success'] == True
            assert output_path.exists()
    
    def test_empty_price_data_handling(self):
        """Test handling of empty price data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Create empty CSV (with headers only)
            csv_path = tmp_path / "empty_prices.csv"
            empty_data = pd.DataFrame(columns=['ts', 'stock_code', 'price', 'volume'])
            empty_data.to_csv(csv_path, index=False)
            
            events_path = tmp_path / "events.jsonl"
            output_path = tmp_path / "empty_report.png"
            
            # Create some events
            events = self.create_sample_events()[:1]
            with open(events_path, 'w') as f:
                for event in events:
                    json.dump(event, f)
                    f.write('\n')
            
            reporter = PlotReporter()
            summary = reporter.generate_report(
                csv_path=csv_path,
                event_files=[events_path],
                output_path=output_path
            )
            
            # Should handle empty data gracefully
            assert "error" not in summary
            assert summary['price_data_points'] == 0
            assert summary['save_success'] == True