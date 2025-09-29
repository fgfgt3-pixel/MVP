"""Tests for core indicators calculation functionality."""

import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
import pytest

from src.features import CoreIndicators, calculate_core_indicators
from src.config_loader import Config


class TestCoreIndicators:
    """Test core indicators calculation functionality."""
    
    def create_sample_data(self, n_rows: int = 10) -> pd.DataFrame:
        """Create sample tick data for testing."""
        return pd.DataFrame({
            'ts': [1704067200000 + i * 1000 for i in range(n_rows)],
            'stock_code': ['005930'] * n_rows,
            'price': [74000 + i * 50 + np.random.randint(-10, 11) for i in range(n_rows)],
            'volume': [1000 + i * 100 + np.random.randint(-50, 51) for i in range(n_rows)],
            'bid1': [73950 + i * 50 + np.random.randint(-5, 6) for i in range(n_rows)],
            'ask1': [74000 + i * 50 + np.random.randint(-5, 6) for i in range(n_rows)],
            'bid_qty1': [500 + i * 10 + np.random.randint(-10, 11) for i in range(n_rows)],
            'ask_qty1': [300 + i * 20 + np.random.randint(-10, 11) for i in range(n_rows)],
        })
    
    def test_core_indicators_initialization(self):
        """Test CoreIndicators initialization."""
        calculator = CoreIndicators()
        assert calculator.config is not None
        assert calculator.vol_window > 0
    
    def test_core_indicators_with_config(self):
        """Test CoreIndicators initialization with custom config."""
        config = Config()
        config.features.rolling["vol_window"] = 100
        
        calculator = CoreIndicators(config)
        assert calculator.vol_window == 100
    
    def test_add_indicators_basic(self):
        """Test basic indicator calculation."""
        df = self.create_sample_data(20)
        calculator = CoreIndicators()
        
        result_df = calculator.add_indicators(df)
        
        # Check that all expected columns are added
        expected_indicators = [
            'ret_1s', 'accel_1s', 'ticks_per_sec', 'vol_1s', 'z_vol_1s',
            'spread', 'microprice', 'microprice_slope'
        ]
        
        for indicator in expected_indicators:
            assert indicator in result_df.columns, f"Missing indicator: {indicator}"
        
        # Check that original columns are preserved
        for col in df.columns:
            assert col in result_df.columns, f"Original column missing: {col}"
        
        # Check that we have the right number of rows
        assert len(result_df) == len(df)
    
    def test_add_indicators_empty_dataframe(self):
        """Test indicator calculation with empty DataFrame."""
        empty_df = pd.DataFrame()
        calculator = CoreIndicators()
        
        result_df = calculator.add_indicators(empty_df)
        assert result_df.empty
    
    def test_price_indicators_calculation(self):
        """Test price indicators calculation accuracy."""
        # Create simple test data
        df = pd.DataFrame({
            'ts': [1704067200000, 1704067201000, 1704067202000],
            'stock_code': ['005930'] * 3,
            'price': [100, 110, 105],
            'volume': [1000, 1100, 1050],
            'bid1': [99, 109, 104],
            'ask1': [101, 111, 106],
            'bid_qty1': [500, 550, 525],
            'ask_qty1': [300, 330, 315],
        })
        
        calculator = CoreIndicators()
        result_df = calculator.add_indicators(df)
        
        # Test ret_1s calculation
        expected_ret_1 = np.log(110 / 100)  # Second row
        expected_ret_2 = np.log(105 / 110)  # Third row
        
        assert np.isclose(result_df.loc[1, 'ret_1s'], expected_ret_1, atol=1e-6)
        assert np.isclose(result_df.loc[2, 'ret_1s'], expected_ret_2, atol=1e-6)
        
        # Test accel_1s (should be diff of ret_1s)
        expected_accel_2 = expected_ret_2 - expected_ret_1
        assert np.isclose(result_df.loc[2, 'accel_1s'], expected_accel_2, atol=1e-6)
    
    def test_spread_calculation(self):
        """Test spread calculation accuracy."""
        df = pd.DataFrame({
            'ts': [1704067200000, 1704067201000],
            'stock_code': ['005930'] * 2,
            'price': [100, 110],
            'volume': [1000, 1100],
            'bid1': [99, 109],
            'ask1': [101, 111],
            'bid_qty1': [500, 550],
            'ask_qty1': [300, 330],
        })
        
        calculator = CoreIndicators()
        result_df = calculator.add_indicators(df)
        
        # Test spread calculation
        # spread = (ask1 - bid1) / ((ask1 + bid1) / 2)
        expected_spread_0 = (101 - 99) / ((101 + 99) / 2)  # 2 / 100 = 0.02
        expected_spread_1 = (111 - 109) / ((111 + 109) / 2)  # 2 / 110 ≈ 0.0182
        
        assert np.isclose(result_df.loc[0, 'spread'], expected_spread_0, atol=1e-6)
        assert np.isclose(result_df.loc[1, 'spread'], expected_spread_1, atol=1e-6)
    
    def test_microprice_calculation(self):
        """Test microprice calculation accuracy."""
        df = pd.DataFrame({
            'ts': [1704067200000],
            'stock_code': ['005930'],
            'price': [100],
            'volume': [1000],
            'bid1': [99],
            'ask1': [101],
            'bid_qty1': [400],  # bid quantity
            'ask_qty1': [600],  # ask quantity
        })
        
        calculator = CoreIndicators()
        result_df = calculator.add_indicators(df)
        
        # microprice = (bid1*ask_qty1 + ask1*bid_qty1) / (ask_qty1 + bid_qty1)
        # = (99*600 + 101*400) / (600 + 400) = (59400 + 40400) / 1000 = 99800 / 1000 = 99.8
        expected_microprice = (99 * 600 + 101 * 400) / (600 + 400)
        
        assert np.isclose(result_df.loc[0, 'microprice'], expected_microprice, atol=1e-6)
    
    def test_volume_indicators(self):
        """Test volume indicators calculation."""
        # Create data with multiple ticks per second
        df = pd.DataFrame({
            'ts': [1704067200000, 1704067200500, 1704067201000, 1704067201500],  # 2 ticks per second
            'stock_code': ['005930'] * 4,
            'price': [100, 101, 102, 103],
            'volume': [1000, 500, 800, 600],
            'bid1': [99, 100, 101, 102],
            'ask1': [101, 102, 103, 104],
            'bid_qty1': [500] * 4,
            'ask_qty1': [300] * 4,
        })
        
        calculator = CoreIndicators()
        result_df = calculator.add_indicators(df)
        
        # Check that ticks_per_sec is calculated
        assert 'ticks_per_sec' in result_df.columns
        assert 'vol_1s' in result_df.columns
        
        # For the data above, we should have 2 ticks per second
        # (timestamps 1704067200000, 1704067200500 -> same second)
        # (timestamps 1704067201000, 1704067201500 -> same second)
        assert result_df.loc[0, 'ticks_per_sec'] == 2
        assert result_df.loc[1, 'ticks_per_sec'] == 2
        assert result_df.loc[2, 'ticks_per_sec'] == 2
        assert result_df.loc[3, 'ticks_per_sec'] == 2
    
    def test_nan_handling(self):
        """Test NaN value handling."""
        df = self.create_sample_data(5)
        calculator = CoreIndicators()
        
        result_df = calculator.add_indicators(df)
        
        # Check that critical indicators don't have NaN values
        indicator_columns = [
            'ret_1s', 'accel_1s', 'ticks_per_sec', 'vol_1s', 'z_vol_1s',
            'spread', 'microprice', 'microprice_slope'
        ]
        
        for col in indicator_columns:
            if col in result_df.columns:
                nan_count = result_df[col].isna().sum()
                assert nan_count == 0, f"Column {col} has {nan_count} NaN values"
    
    def test_z_vol_calculation(self):
        """Test z-score volume calculation."""
        # Create data with varying volumes
        np.random.seed(42)  # For reproducible results
        n_rows = 100
        df = pd.DataFrame({
            'ts': [1704067200000 + i * 1000 for i in range(n_rows)],
            'stock_code': ['005930'] * n_rows,
            'price': [74000 + i for i in range(n_rows)],
            'volume': np.random.normal(1000, 200, n_rows),  # Normal distribution
            'bid1': [73999 + i for i in range(n_rows)],
            'ask1': [74001 + i for i in range(n_rows)],
            'bid_qty1': [500] * n_rows,
            'ask_qty1': [300] * n_rows,
        })
        
        config = Config()
        config.features.rolling["vol_window"] = 50  # Use smaller window for test
        calculator = CoreIndicators(config)
        
        result_df = calculator.add_indicators(df)
        
        # z_vol_1s should be calculated
        assert 'z_vol_1s' in result_df.columns
        
        # Check that z-scores are reasonable (should be mostly between -3 and 3)
        z_vol_values = result_df['z_vol_1s'].dropna()
        assert len(z_vol_values) > 0
        
        # Most values should be within reasonable z-score range
        reasonable_range = np.abs(z_vol_values) < 5
        assert reasonable_range.sum() / len(z_vol_values) > 0.8
    
    def test_convenience_function(self):
        """Test the convenience function calculate_core_indicators."""
        df = self.create_sample_data(10)
        
        result_df = calculate_core_indicators(df)
        
        # Should have all expected indicators
        expected_indicators = [
            'ret_1s', 'accel_1s', 'ticks_per_sec', 'vol_1s', 'z_vol_1s',
            'spread', 'microprice', 'microprice_slope'
        ]
        
        for indicator in expected_indicators:
            assert indicator in result_df.columns


class TestCoreIndicatorsIntegration:
    """Test integration with other components."""
    
    def test_with_real_csv_structure(self):
        """Test with realistic CSV data structure."""
        # Create data similar to actual CSV format
        df = pd.DataFrame({
            'ts': [1704067200000, 1704067201000, 1704067202000, 1704067203000, 1704067204000],
            'stock_code': ['005930'] * 5,
            'price': [74000, 74100, 74050, 74200, 74150],
            'volume': [1000, 800, 1200, 2000, 900],
            'bid1': [73900, 74000, 73950, 74100, 74050],
            'ask1': [74000, 74100, 74050, 74200, 74150],
            'bid_qty1': [500, 400, 600, 800, 450],
            'ask_qty1': [300, 350, 200, 400, 320],
        })
        
        result_df = calculate_core_indicators(df)
        
        # Should have original data plus indicators
        assert len(result_df) == len(df)
        assert len(result_df.columns) > len(df.columns)
        
        # Check some basic properties
        assert result_df['ret_1s'].iloc[0] == 0  # First row should be 0 due to NaN handling
        assert result_df['ticks_per_sec'].min() >= 1  # Should have at least 1 tick per second
        assert result_df['spread'].min() >= 0  # Spread should be non-negative
    
    def test_file_save_load_cycle(self):
        """Test saving and loading features to/from CSV."""
        with tempfile.TemporaryDirectory() as temp_dir:
            df = pd.DataFrame({
                'ts': [1704067200000, 1704067201000, 1704067202000],
                'stock_code': ['005930'] * 3,
                'price': [74000, 74100, 74050],
                'volume': [1000, 800, 1200],
                'bid1': [73900, 74000, 73950],
                'ask1': [74000, 74100, 74050],
                'bid_qty1': [500, 400, 600],
                'ask_qty1': [300, 350, 200],
            })
            
            # Calculate indicators
            result_df = calculate_core_indicators(df)
            
            # Save to CSV
            csv_path = Path(temp_dir) / "test_features.csv"
            result_df.to_csv(csv_path, index=False)
            
            # Load back
            loaded_df = pd.read_csv(csv_path)
            
            # Should have same shape and columns
            assert loaded_df.shape == result_df.shape
            assert list(loaded_df.columns) == list(result_df.columns)
            
            # Check that indicator values are preserved
            indicator_cols = ['ret_1s', 'spread', 'microprice']
            for col in indicator_cols:
                if col in result_df.columns:
                    assert np.allclose(loaded_df[col], result_df[col], equal_nan=True)