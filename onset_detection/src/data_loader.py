"""Data loader for Korean stock tick data."""

import pandas as pd
from pathlib import Path
from typing import Union, Optional, List
import numpy as np
from datetime import datetime

from .config_loader import Config, load_config
from .utils.paths import PathManager


class DataLoader:
    """Load and preprocess Korean stock tick data from CSV files."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize data loader.
        
        Args:
            config: Configuration object. If None, loads default config.
        """
        if config is None:
            config = load_config()
        
        self.config = config
        self.path_manager = PathManager(config)
        
        # Expected column schema
        self.required_columns = ['ts', 'stock_code', 'price', 'volume', 'bid1', 'ask1', 'bid_qty1', 'ask_qty1']
    
    def load_csv(self, file_path: Union[str, Path], validate_schema: bool = True) -> pd.DataFrame:
        """
        Load CSV file and return DataFrame with proper preprocessing.
        
        Args:
            file_path: Path to CSV file (relative or absolute).
            validate_schema: Whether to validate required columns.
            
        Returns:
            pd.DataFrame: Loaded and preprocessed data.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If schema validation fails.
        """
        # Convert to absolute path if relative
        if not Path(file_path).is_absolute():
            file_path = self.path_manager.get_data_raw_path() / file_path
        else:
            file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        # Load CSV with proper dtypes to prevent precision loss
        # Force timestamp columns to int64 to prevent float conversion
        dtype_hints = {}

        # Try to detect timestamp column names
        with open(file_path, 'r') as f:
            header = f.readline().strip().lower()
            ts_columns = ['time', 'ts', 'timestamp']
            for col in ts_columns:
                if col in header:
                    dtype_hints[col] = 'int64'

        df = pd.read_csv(file_path, dtype=dtype_hints)
        
        # Validate schema
        if validate_schema:
            self._validate_schema(df)
        
        # Preprocess data
        df = self._preprocess_data(df)
        
        return df
    
    def _validate_schema(self, df: pd.DataFrame) -> None:
        """
        Validate that DataFrame has required columns.
        
        Args:
            df: DataFrame to validate.
            
        Raises:
            ValueError: If required columns are missing.
        """
        missing_columns = set(self.required_columns) - set(df.columns)
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
    
    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess loaded data.
        
        Args:
            df: Raw DataFrame.
            
        Returns:
            pd.DataFrame: Preprocessed DataFrame.
        """
        df = df.copy()
        
        # Parse timestamp column
        df['ts'] = self._parse_timestamp(df['ts'])
        
        # Ensure proper data types
        numeric_columns = ['price', 'volume', 'bid1', 'ask1', 'bid_qty1', 'ask_qty1']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Sort by timestamp
        df = df.sort_values('ts').reset_index(drop=True)
        
        # Add derived columns
        df = self._add_derived_columns(df)
        
        return df
    
    def to_datetime_utc(self, series: pd.Series, unit: str) -> pd.Series:
        """Convert timestamp series to UTC datetime."""
        # Ensure int64 to prevent precision loss
        int_series = series.astype('int64')
        return pd.to_datetime(int_series, unit=unit, origin='unix', utc=True)

    def infer_epoch_unit(self, series: pd.Series) -> str:
        """Infer epoch unit from timestamp values."""
        # Get max value and count digits
        max_val = series.astype('int64').abs().max()
        n_digits = int(np.log10(max_val)) + 1

        # Map digits to units: 10: s, 13: ms, 16: us, 19: ns
        unit_map = {10: "s", 13: "ms", 16: "us", 19: "ns"}
        return unit_map.get(n_digits, "ms")

    def _parse_timestamp(self, ts_series: pd.Series) -> pd.Series:
        """
        Parse timestamp column supporting both epoch ms and datetime strings.

        Args:
            ts_series: Timestamp series.

        Returns:
            pd.Series: Parsed datetime series with timezone info.
        """
        # Check if it's already datetime
        if pd.api.types.is_datetime64_any_dtype(ts_series):
            result = pd.to_datetime(ts_series)
        else:
            # Try to detect format
            sample_value = ts_series.iloc[0] if len(ts_series) > 0 else None

            if isinstance(sample_value, (int, float, np.integer, np.floating)):
                # Get epoch unit from config or infer
                if hasattr(self.config, 'time') and hasattr(self.config.time, 'epoch_unit'):
                    unit = self.config.time.epoch_unit
                else:
                    unit = self.infer_epoch_unit(ts_series)
                    print(f"Warning: No epoch_unit in config, inferred as '{unit}'")

                # Convert to UTC first, then to target timezone
                result = self.to_datetime_utc(ts_series, unit)
            else:
                # Assume string datetime
                result = pd.to_datetime(ts_series)

        # Get target timezone from config (safe access)
        target_tz = 'Asia/Seoul'  # default
        if hasattr(self.config, 'time') and hasattr(self.config.time, 'timezone'):
            target_tz = self.config.time.timezone
        elif hasattr(self.config, 'session') and hasattr(self.config.session, 'timezone'):
            target_tz = self.config.session.timezone

        # Ensure timezone awareness
        if result.dt.tz is None:
            result = result.dt.tz_localize('UTC')

        # Convert to target timezone
        result = result.dt.tz_convert(target_tz)

        return result
    
    def _add_derived_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add derived columns for analysis.
        
        Args:
            df: Input DataFrame.
            
        Returns:
            pd.DataFrame: DataFrame with additional columns.
        """
        df = df.copy()
        
        # Add spread
        if 'ask1' in df.columns and 'bid1' in df.columns:
            df['spread'] = df['ask1'] - df['bid1']
            df['mid_price'] = (df['ask1'] + df['bid1']) / 2
        
        # Add bid-ask imbalance
        if 'bid_qty1' in df.columns and 'ask_qty1' in df.columns:
            total_qty = df['bid_qty1'] + df['ask_qty1']
            df['bid_ask_imbalance'] = (df['bid_qty1'] - df['ask_qty1']) / (total_qty + 1e-8)
        
        # Add price returns (will be NaN for first row)
        df['price_return'] = df['price'].pct_change()
        
        # Add time delta (seconds since previous tick)
        df['time_delta'] = df['ts'].diff().dt.total_seconds()
        
        return df
    
    def load_multiple_files(self, file_pattern: str = "*.csv") -> pd.DataFrame:
        """
        Load multiple CSV files from raw data directory.
        
        Args:
            file_pattern: Glob pattern for file selection.
            
        Returns:
            pd.DataFrame: Combined DataFrame from all files.
        """
        raw_path = self.path_manager.get_data_raw_path()
        csv_files = list(raw_path.glob(file_pattern))
        
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found matching pattern: {file_pattern}")
        
        dfs = []
        for file_path in csv_files:
            try:
                df = self.load_csv(file_path)
                df['source_file'] = file_path.name
                dfs.append(df)
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")
        
        if not dfs:
            raise ValueError("No files could be loaded successfully")
        
        # Combine all DataFrames
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # Sort by timestamp across all files
        combined_df = combined_df.sort_values('ts').reset_index(drop=True)
        
        return combined_df
    
    def get_data_info(self, df: pd.DataFrame) -> dict:
        """
        Get summary information about the loaded data.
        
        Args:
            df: DataFrame to analyze.
            
        Returns:
            dict: Summary statistics and information.
        """
        if df.empty:
            return {"error": "DataFrame is empty"}
        
        info = {
            "shape": df.shape,
            "date_range": {
                "start": df['ts'].min().isoformat() if not df['ts'].empty else None,
                "end": df['ts'].max().isoformat() if not df['ts'].empty else None,
                "duration_hours": (df['ts'].max() - df['ts'].min()).total_seconds() / 3600 if len(df) > 1 else 0
            },
            "stocks": df['stock_code'].unique().tolist() if 'stock_code' in df.columns else [],
            "price_stats": {
                "min": float(df['price'].min()) if 'price' in df.columns else None,
                "max": float(df['price'].max()) if 'price' in df.columns else None,
                "mean": float(df['price'].mean()) if 'price' in df.columns else None
            },
            "volume_stats": {
                "total": int(df['volume'].sum()) if 'volume' in df.columns else None,
                "mean": float(df['volume'].mean()) if 'volume' in df.columns else None
            },
            "missing_data": df.isnull().sum().to_dict()
        }
        
        return info


def load_sample_data(config: Optional[Config] = None) -> pd.DataFrame:
    """
    Convenience function to load sample data.
    
    Args:
        config: Configuration object.
        
    Returns:
        pd.DataFrame: Sample data.
    """
    loader = DataLoader(config)
    return loader.load_csv("sample.csv")


if __name__ == "__main__":
    # Demo/test the data loader
    loader = DataLoader()
    
    try:
        df = load_sample_data()
        print("Data Loader Demo")
        print("=" * 40)
        print(f"Loaded {len(df)} rows")
        print("\nFirst 5 rows:")
        print(df.head())
        print("\nData Info:")
        info = loader.get_data_info(df)
        for key, value in info.items():
            print(f"{key}: {value}")
            
    except Exception as e:
        print(f"Error loading sample data: {e}")
        print("Make sure sample.csv exists in data/raw/ directory")