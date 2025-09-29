"""Tests for replay engine and data loader modules."""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from datetime import datetime, timezone

from src.data_loader import DataLoader, load_sample_data
from src.replay_engine import ReplaySource, ReplayEngine, create_simple_replay
from src.config_loader import Config


class TestDataLoader:
    """Test data loading functionality."""
    
    def test_sample_data_loading(self):
        """Test loading sample data."""
        df = load_sample_data()
        
        assert not df.empty
        assert 'ts' in df.columns
        assert 'stock_code' in df.columns
        assert 'price' in df.columns
        assert 'volume' in df.columns
        
        # Check timestamp parsing
        assert pd.api.types.is_datetime64_any_dtype(df['ts'])
        
        # Check derived columns
        assert 'spread' in df.columns
        assert 'mid_price' in df.columns
        assert 'bid_ask_imbalance' in df.columns
    
    def test_data_loader_initialization(self):
        """Test DataLoader initialization."""
        loader = DataLoader()
        assert loader.config is not None
        assert loader.path_manager is not None
    
    def test_csv_validation(self):
        """Test CSV schema validation."""
        loader = DataLoader()
        
        # Test valid CSV
        valid_data = {
            'ts': [1704067200000, 1704067201000],
            'stock_code': ['005930', '005930'],
            'price': [74000, 74100],
            'volume': [1000, 800],
            'bid1': [73900, 74000],
            'ask1': [74000, 74100],
            'bid_qty1': [500, 400],
            'ask_qty1': [300, 350]
        }
        valid_df = pd.DataFrame(valid_data)
        processed_df = loader._preprocess_data(valid_df)
        
        assert not processed_df.empty
        assert 'spread' in processed_df.columns
        
        # Test invalid CSV (missing required columns)
        invalid_data = {
            'ts': [1704067200000],
            'price': [74000]
            # Missing required columns
        }
        invalid_df = pd.DataFrame(invalid_data)
        
        with pytest.raises(ValueError, match="Missing required columns"):
            loader._validate_schema(invalid_df)
    
    def test_timestamp_parsing(self):
        """Test timestamp parsing functionality."""
        loader = DataLoader()
        
        # Test epoch milliseconds
        epoch_series = pd.Series([1704067200000, 1704067201000])
        parsed = loader._parse_timestamp(epoch_series)
        assert pd.api.types.is_datetime64_any_dtype(parsed)
        assert parsed.dt.tz is not None  # Should have timezone
        
        # Test datetime strings
        datetime_series = pd.Series(['2024-01-01 09:00:00', '2024-01-01 09:00:01'])
        parsed = loader._parse_timestamp(datetime_series)
        assert pd.api.types.is_datetime64_any_dtype(parsed)
    
    def test_data_info(self):
        """Test data info generation."""
        df = load_sample_data()
        loader = DataLoader()
        
        info = loader.get_data_info(df)
        
        assert 'shape' in info
        assert 'date_range' in info
        assert 'stocks' in info
        assert 'price_stats' in info
        assert 'volume_stats' in info
        
        assert info['shape'] == df.shape
        assert len(info['stocks']) > 0
        assert info['price_stats']['min'] is not None


class TestReplaySource:
    """Test ReplaySource functionality."""
    
    def create_test_dataframe(self) -> pd.DataFrame:
        """Create test DataFrame."""
        data = {
            'ts': pd.to_datetime(['2024-01-01 09:00:00', '2024-01-01 09:00:01', 
                                 '2024-01-01 09:00:02'], utc=True),
            'stock_code': ['005930', '005930', '005930'],
            'price': [74000, 74100, 74050],
            'volume': [1000, 800, 1200],
            'bid1': [73900, 74000, 73950],
            'ask1': [74000, 74100, 74050],
            'bid_qty1': [500, 400, 600],
            'ask_qty1': [300, 350, 200]
        }
        return pd.DataFrame(data)
    
    def test_replay_source_initialization(self):
        """Test ReplaySource initialization."""
        df = self.create_test_dataframe()
        
        # Valid initialization
        source = ReplaySource(df, speed=2.0, sleep=False)
        assert source.speed == 2.0
        assert source.sleep == False
        assert len(source.df) == 3
        
        # Test with empty DataFrame
        with pytest.raises(ValueError, match="DataFrame cannot be empty"):
            ReplaySource(pd.DataFrame())
        
        # Test without timestamp column
        df_no_ts = df.drop('ts', axis=1)
        with pytest.raises(ValueError, match="must have 'ts'"):
            ReplaySource(df_no_ts)
    
    def test_replay_iteration(self):
        """Test replay iteration functionality."""
        df = self.create_test_dataframe()
        source = ReplaySource(df, speed=1.0, sleep=False)
        
        ticks = list(source)
        
        assert len(ticks) == 3
        
        # Check first tick
        first_tick = ticks[0]
        assert first_tick['stock_code'] == '005930'
        assert first_tick['price'] == 74000
        assert '_metadata' in first_tick
        assert first_tick['_metadata']['index'] == 0
        assert first_tick['_metadata']['total_rows'] == 3
        
        # Check metadata progression
        assert ticks[0]['_metadata']['progress_pct'] == pytest.approx(33.33, abs=0.1)
        assert ticks[1]['_metadata']['progress_pct'] == pytest.approx(66.67, abs=0.1)
        assert ticks[2]['_metadata']['progress_pct'] == pytest.approx(100.0, abs=0.1)
    
    def test_replay_with_callbacks(self):
        """Test replay with callback functions."""
        df = self.create_test_dataframe()
        source = ReplaySource(df, speed=1.0, sleep=False)
        
        callback_results = []
        
        def test_callback(tick_data):
            callback_results.append(tick_data['price'])
        
        source.add_callback(test_callback)
        
        # Consume the iterator
        ticks = list(source)
        
        assert len(callback_results) == 3
        assert callback_results == [74000, 74100, 74050]
        
        # Test callback removal
        source.remove_callback(test_callback)
        callback_results.clear()
        
        # Iterate again
        ticks = list(source)
        assert len(callback_results) == 0  # Callback was removed
    
    def test_replay_speed_control(self):
        """Test speed control (without actual timing)."""
        df = self.create_test_dataframe()
        
        # Test different speeds
        for speed in [0.5, 1.0, 2.0, 10.0]:
            source = ReplaySource(df, speed=speed, sleep=False)
            assert source.speed == speed
            
            ticks = list(source)
            assert len(ticks) == 3
    
    def test_replay_reset(self):
        """Test replay reset functionality."""
        df = self.create_test_dataframe()
        source = ReplaySource(df, speed=1.0, sleep=False)
        
        # Iterate partially
        iterator = iter(source)
        next(iterator)  # Get first tick
        assert source.current_index == 1
        
        # Reset
        source.reset()
        assert source.current_index == 0
        assert source.start_time is None
    
    def test_skip_to(self):
        """Test skip to functionality."""
        df = self.create_test_dataframe()
        source = ReplaySource(df, speed=1.0, sleep=False)
        
        # Skip to index 2
        source.skip_to(2)
        assert source.current_index == 2
        
        # Test invalid index
        with pytest.raises(ValueError, match="Index .* out of bounds"):
            source.skip_to(10)
        
        with pytest.raises(ValueError, match="Index .* out of bounds"):
            source.skip_to(-1)
    
    def test_progress_info(self):
        """Test progress information."""
        df = self.create_test_dataframe()
        source = ReplaySource(df, speed=1.0, sleep=False)
        
        # Initial progress
        progress = source.get_progress()
        assert progress['progress_pct'] == 0
        assert progress['current_index'] == 0
        assert progress['total_rows'] == 3
        
        # Skip and check progress
        source.skip_to(1)
        progress = source.get_progress()
        assert progress['progress_pct'] == pytest.approx(33.33, abs=0.1)
        assert progress['remaining_rows'] == 2


class TestReplayEngine:
    """Test ReplayEngine functionality."""
    
    def create_test_dataframe(self) -> pd.DataFrame:
        """Create test DataFrame."""
        data = {
            'ts': pd.to_datetime(['2024-01-01 09:00:00', '2024-01-01 09:00:01'], utc=True),
            'stock_code': ['005930', '005930'],
            'price': [74000, 74100],
            'volume': [1000, 800],
            'bid1': [73900, 74000],
            'ask1': [74000, 74100],
            'bid_qty1': [500, 400],
            'ask_qty1': [300, 350]
        }
        return pd.DataFrame(data)
    
    def test_engine_initialization(self):
        """Test ReplayEngine initialization."""
        engine = ReplayEngine()
        assert engine.config is not None
        assert len(engine._sources) == 0
    
    def test_source_management(self):
        """Test source add/get/remove functionality."""
        engine = ReplayEngine()
        df = self.create_test_dataframe()
        
        # Add source
        source = engine.add_source("test", df, speed=2.0)
        assert isinstance(source, ReplaySource)
        assert source.speed == 2.0
        
        # Get source
        retrieved = engine.get_source("test")
        assert retrieved is source
        
        # Get non-existent source
        assert engine.get_source("nonexistent") is None
        
        # Remove source
        assert engine.remove_source("test") == True
        assert engine.remove_source("nonexistent") == False
        assert engine.get_source("test") is None
    
    def test_source_replay(self):
        """Test replaying specific sources."""
        engine = ReplayEngine()
        df = self.create_test_dataframe()
        
        engine.add_source("test", df)
        
        ticks = list(engine.replay_source("test", limit=1))
        assert len(ticks) == 1
        assert ticks[0]['stock_code'] == '005930'
        
        # Test non-existent source
        with pytest.raises(KeyError, match="Source 'nonexistent' not found"):
            list(engine.replay_source("nonexistent"))
    
    def test_global_callbacks(self):
        """Test global callback functionality."""
        engine = ReplayEngine()
        df = self.create_test_dataframe()
        
        callback_results = []
        
        def global_callback(source_name, tick_data):
            callback_results.append((source_name, tick_data['price']))
        
        engine.add_global_callback(global_callback)
        engine.add_source("test", df)
        
        ticks = list(engine.replay_source("test", limit=1))
        
        assert len(callback_results) == 1
        assert callback_results[0] == ("test", 74000)
    
    def test_sources_info(self):
        """Test sources information."""
        engine = ReplayEngine()
        df = self.create_test_dataframe()
        
        engine.add_source("test1", df, speed=1.0)
        engine.add_source("test2", df, speed=2.0, sleep=True)
        
        info = engine.get_sources_info()
        
        assert len(info) == 2
        assert "test1" in info
        assert "test2" in info
        
        assert info["test1"]["speed"] == 1.0
        assert info["test1"]["sleep_enabled"] == False
        assert info["test2"]["speed"] == 2.0
        assert info["test2"]["sleep_enabled"] == True


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_create_simple_replay(self):
        """Test create_simple_replay function."""
        data = {
            'ts': pd.to_datetime(['2024-01-01 09:00:00'], utc=True),
            'stock_code': ['005930'],
            'price': [74000],
            'volume': [1000],
            'bid1': [73900],
            'ask1': [74000],
            'bid_qty1': [500],
            'ask_qty1': [300]
        }
        df = pd.DataFrame(data)
        
        ticks = list(create_simple_replay(df, speed=2.0))
        
        assert len(ticks) == 1
        assert ticks[0]['stock_code'] == '005930'
        assert ticks[0]['_metadata']['speed'] == 2.0


class TestIntegration:
    """Integration tests."""
    
    def test_end_to_end_replay(self):
        """Test complete end-to-end replay functionality."""
        # Load sample data
        df = load_sample_data()
        
        # Create replay engine
        engine = ReplayEngine()
        engine.add_source("sample", df, speed=1.0, sleep=False)
        
        # Track results
        results = []
        
        def callback(source_name, tick_data):
            results.append({
                'source': source_name,
                'price': tick_data['price'],
                'volume': tick_data['volume'],
                'progress': tick_data['_metadata']['progress_pct']
            })
        
        engine.add_global_callback(callback)
        
        # Replay limited number of ticks
        ticks = list(engine.replay_source("sample", limit=5))
        
        # Verify results
        assert len(ticks) == 5
        assert len(results) == 5
        
        # Check monotonic progress
        progresses = [r['progress'] for r in results]
        assert all(progresses[i] <= progresses[i+1] for i in range(len(progresses)-1))
    
    def test_data_loader_replay_integration(self):
        """Test integration between data loader and replay engine."""
        loader = DataLoader()
        df = loader.load_csv("sample.csv")
        
        # Verify loaded data has required structure for replay
        assert 'ts' in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df['ts'])
        
        # Create replay from loaded data
        source = ReplaySource(df, speed=1.0, sleep=False)
        ticks = list(source)
        
        assert len(ticks) == len(df)
        assert all('_metadata' in tick for tick in ticks)