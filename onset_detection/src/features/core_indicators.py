"""Core indicators calculation for onset detection."""

import pandas as pd
import numpy as np
from typing import Optional
from pathlib import Path

from ..config_loader import Config, load_config


class CoreIndicators:
    """
    Calculate core indicators for onset detection.
    
    Computes price, volume, and friction indicators from tick data
    to identify potential onset patterns.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize core indicators calculator.

        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()
        self.vol_window = self.config.features.rolling.get("vol_window", 300)

        # Volume configuration
        self.is_cumulative_volume = getattr(self.config.volume, 'is_cumulative', True)
        self.vol_roll_window_s = getattr(self.config.volume, 'roll_window_s', 300)
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add core indicators to the DataFrame.
        
        Args:
            df: Input DataFrame with columns [ts, stock_code, price, volume, 
                bid1, ask1, bid_qty1, ask_qty1]
        
        Returns:
            pd.DataFrame: DataFrame with added indicator columns.
        """
        if df.empty:
            return df
        
        # Create a copy to avoid modifying original
        result_df = df.copy()
        
        # Add timestamp processing
        result_df = self._add_timestamp_features(result_df)
        
        # Add price indicators
        result_df = self._add_price_indicators(result_df)
        
        # Add volume/trading indicators
        result_df = self._add_volume_indicators(result_df)
        
        # Add friction indicators
        result_df = self._add_friction_indicators(result_df)
        
        # Handle NaN values
        result_df = self._handle_nan_values(result_df)
        
        return result_df
    
    def _add_timestamp_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add timestamp-based features."""
        # Handle both datetime and numeric timestamps
        if pd.api.types.is_datetime64_any_dtype(df['ts']):
            # For datetime, floor to seconds (preserving timezone)
            df['ts_sec'] = df['ts'].dt.floor('S')
            # Also create integer epoch seconds for grouping if needed
            df['epoch_sec'] = (df['ts'].view('int64') // 1_000_000_000)
        else:
            # For numeric millisecond timestamps, convert to seconds
            df['ts_sec'] = df['ts'] // 1000
            df['epoch_sec'] = df['ts_sec']
        return df
    
    def _add_price_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price-based indicators."""
        # Calculate log returns (1s interval approximation using sequential returns)
        df['ret_1s'] = np.log(df['price'] / df['price'].shift(1))
        
        # Calculate acceleration (change in returns)
        df['accel_1s'] = df['ret_1s'].diff(1)
        
        return df
    
    def _add_volume_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume and trading indicators."""
        # Handle cumulative volume properly
        if self.is_cumulative_volume:
            # Convert cumulative volume to per-tick volume
            df['vol_tick'] = df['volume'].diff().clip(lower=0).fillna(0)
        else:
            # Volume is already per-tick
            df['vol_tick'] = df['volume'].fillna(0)

        # Group by second to calculate per-second aggregates
        g = df.groupby('ts_sec', sort=True, as_index=False)
        sec_stats = g.agg({
            'price': 'last',              # price_last
            'vol_tick': 'sum',            # vol_1s (sum of tick volumes per second)
            'ts': 'count',                # ticks_per_sec
            'bid1': 'last',               # bid1_last
            'ask1': 'last',               # ask1_last
            'bid_qty1': 'last',           # bid_qty1_last
            'ask_qty1': 'last'            # ask_qty1_last
        }).rename(columns={
            'price': 'price_last',
            'vol_tick': 'vol_1s',
            'ts': 'ticks_per_sec',
            'bid1': 'bid1_last',
            'ask1': 'ask1_last',
            'bid_qty1': 'bid_qty1_last',
            'ask_qty1': 'ask_qty1_last'
        })

        # Calculate z-score for volume using rolling window
        win = self.vol_roll_window_s
        sec_stats['vol_1s_mean'] = sec_stats['vol_1s'].rolling(window=win, min_periods=10).mean()
        sec_stats['vol_1s_std'] = sec_stats['vol_1s'].rolling(window=win, min_periods=10).std()

        # Avoid division by zero
        sec_stats['vol_1s_std'] = sec_stats['vol_1s_std'].fillna(1.0)
        sec_stats['vol_1s_std'] = sec_stats['vol_1s_std'].replace(0, 1.0)

        sec_stats['z_vol_1s'] = (
            (sec_stats['vol_1s'] - sec_stats['vol_1s_mean']) / sec_stats['vol_1s_std']
        ).fillna(0)

        # Merge back to original DataFrame (propagate second-based indicators to tick level)
        merge_columns = ['ts_sec', 'vol_1s', 'ticks_per_sec', 'z_vol_1s']
        df = df.merge(
            sec_stats[merge_columns],
            on='ts_sec',
            how='left'
        ).fillna({'vol_1s': 0, 'ticks_per_sec': 0, 'z_vol_1s': 0})

        return df
    
    def _add_friction_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market friction indicators."""
        # Calculate mid price
        mid_price = (df['ask1'] + df['bid1']) / 2
        
        # Calculate spread as percentage of mid price
        df['spread'] = (df['ask1'] - df['bid1']) / mid_price
        
        # Calculate microprice (volume-weighted mid)
        total_qty = df['ask_qty1'] + df['bid_qty1']
        # Avoid division by zero
        total_qty = total_qty.replace(0, 1)
        
        df['microprice'] = (df['bid1'] * df['ask_qty1'] + df['ask1'] * df['bid_qty1']) / total_qty
        
        # Calculate microprice slope (change in microprice)
        df['microprice_slope'] = df['microprice'].diff(1)
        
        return df
    
    def _handle_nan_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle NaN values in calculated indicators."""
        # List of indicator columns to process
        indicator_columns = [
            'ret_1s', 'accel_1s', 'ticks_per_sec', 'vol_1s', 'z_vol_1s',
            'spread', 'microprice', 'microprice_slope'
        ]
        
        for col in indicator_columns:
            if col in df.columns:
                # Fill initial NaNs with 0
                df[col] = df[col].fillna(0)
        
        return df


def calculate_core_indicators(df: pd.DataFrame, config: Optional[Config] = None) -> pd.DataFrame:
    """
    Convenience function to calculate core indicators.
    
    Args:
        df: Input DataFrame with tick data.
        config: Optional configuration object.
    
    Returns:
        pd.DataFrame: DataFrame with added indicator columns.
    """
    calculator = CoreIndicators(config)
    return calculator.add_indicators(df)


if __name__ == "__main__":
    # Demo/test the core indicators
    from ..data_loader import DataLoader
    import time
    
    print("Core Indicators Demo")
    print("=" * 40)
    
    # Create sample data
    sample_data = {
        'ts': [1704067200000 + i * 1000 for i in range(10)],
        'stock_code': ['005930'] * 10,
        'price': [74000 + i * 50 for i in range(10)],
        'volume': [1000 + i * 100 for i in range(10)],
        'bid1': [73950 + i * 50 for i in range(10)],
        'ask1': [74000 + i * 50 for i in range(10)],
        'bid_qty1': [500 + i * 10 for i in range(10)],
        'ask_qty1': [300 + i * 20 for i in range(10)],
    }
    
    df = pd.DataFrame(sample_data)
    print(f"Original DataFrame shape: {df.shape}")
    print(f"Original columns: {list(df.columns)}")
    
    # Calculate indicators
    result_df = calculate_core_indicators(df)
    
    print(f"\nResult DataFrame shape: {result_df.shape}")
    print(f"Result columns: {list(result_df.columns)}")
    
    # Show some indicators
    indicator_cols = ['ret_1s', 'accel_1s', 'ticks_per_sec', 'vol_1s', 'z_vol_1s', 
                     'spread', 'microprice', 'microprice_slope']
    
    available_indicators = [col for col in indicator_cols if col in result_df.columns]
    print(f"\nCalculated indicators ({len(available_indicators)}): {available_indicators}")
    
    # Show first few rows of indicators
    if available_indicators:
        print(f"\nSample values:")
        print(result_df[available_indicators].head())
        
        # Check for NaN values
        nan_counts = result_df[available_indicators].isna().sum()
        if nan_counts.sum() > 0:
            print(f"\nNaN counts: {nan_counts[nan_counts > 0].to_dict()}")
        else:
            print("\nNo NaN values found in indicators.")