"""Sliding window feature generation for pattern detection."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


def load_window_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load window features configuration.

    Args:
        config_path: Path to window features config YAML. If None, uses default.

    Returns:
        Dict: Window features configuration.
    """
    if config_path is None:
        # Default path relative to this module
        config_path = Path(__file__).parent.parent.parent / 'config' / 'window_features.yaml'

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Window features config not found: {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    return config.get('window_features', {})


def calculate_slope(series: pd.Series) -> float:
    """
    Calculate linear regression slope for a series.

    Args:
        series: Pandas Series of values.

    Returns:
        float: Slope of the linear regression line.
    """
    if len(series) < 2:
        return 0.0

    try:
        # Remove NaN values
        clean_series = series.dropna()
        if len(clean_series) < 2:
            return 0.0

        # Create x values (0, 1, 2, ...)
        x = np.arange(len(clean_series))
        y = clean_series.values

        # Calculate slope using polyfit (degree 1)
        coeffs = np.polyfit(x, y, 1)
        return float(coeffs[0])  # Slope is the first coefficient
    except:
        return 0.0


def calculate_uptick_ratio(series: pd.Series) -> float:
    """
    Calculate the ratio of upticks (positive changes) in a series.

    Args:
        series: Pandas Series of values.

    Returns:
        float: Ratio of upticks to total changes.
    """
    if len(series) < 2:
        return 0.5  # Default to neutral

    try:
        changes = series.diff()
        upticks = (changes > 0).sum()
        total_changes = len(changes) - 1  # Exclude first NaN

        if total_changes <= 0:
            return 0.5

        return float(upticks / total_changes)
    except:
        return 0.5


def calculate_last_first(series: pd.Series) -> float:
    """
    Calculate the difference between last and first values.

    Args:
        series: Pandas Series of values.

    Returns:
        float: Last value - First value.
    """
    if len(series) == 0:
        return 0.0

    try:
        # Get first and last non-NaN values
        clean_series = series.dropna()
        if len(clean_series) == 0:
            return 0.0

        return float(clean_series.iloc[-1] - clean_series.iloc[0])
    except:
        return 0.0


def generate_window_features(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    config_path: Optional[Union[str, Path]] = None
) -> pd.DataFrame:
    """
    Generate sliding window aggregate features for pattern detection.

    Args:
        df: DataFrame with features (must have 'ts' column and be sorted).
        config: Window features configuration dict. If None, loads from config_path.
        config_path: Path to window features config YAML.

    Returns:
        DataFrame: Original dataframe with additional window feature columns.
    """
    # Load configuration
    if config is None:
        config = load_window_config(config_path)

    if not config.get('enabled', True):
        logger.info("Window features generation is disabled")
        return df

    # Validate input
    if 'ts' not in df.columns:
        raise ValueError("DataFrame must have 'ts' column")

    # Ensure DataFrame is sorted by timestamp
    df = df.sort_values('ts').copy()

    # Set timestamp as index for rolling operations
    df_indexed = df.set_index('ts')

    # Get configuration parameters
    time_windows = config.get('time_windows', [0.5, 1, 2, 5, 10])
    tick_windows = config.get('tick_windows', [10, 20, 50])
    agg_funcs = config.get('agg_funcs', ['mean', 'std', 'min', 'max'])
    target_features = config.get('target_features', ['price', 'ret_1s', 'z_vol_1s'])
    fillna_method = config.get('fillna_method', 'forward')
    min_periods = config.get('min_periods', 3)

    # Filter target features to only those that exist in dataframe
    target_features = [f for f in target_features if f in df.columns]

    if not target_features:
        logger.warning("No target features found in dataframe")
        return df

    logger.info(f"Generating window features for {len(target_features)} features")

    # Generate time-based window features
    for window_s in time_windows:
        window_str = f"{window_s}s"

        for feature in target_features:
            if feature not in df_indexed.columns:
                continue

            # Create rolling window
            rolling = df_indexed[feature].rolling(
                window=pd.Timedelta(seconds=window_s),
                min_periods=min_periods
            )

            # Apply aggregation functions
            for func_name in agg_funcs:
                col_name = f"{feature}_{func_name}_{window_s}s"

                if func_name == 'mean':
                    df[col_name] = rolling.mean().values
                elif func_name == 'std':
                    df[col_name] = rolling.std().values
                elif func_name == 'min':
                    df[col_name] = rolling.min().values
                elif func_name == 'max':
                    df[col_name] = rolling.max().values
                elif func_name == 'slope':
                    df[col_name] = rolling.apply(calculate_slope, raw=False).values
                elif func_name == 'last_first':
                    df[col_name] = rolling.apply(calculate_last_first, raw=False).values
                elif func_name == 'uptick_ratio':
                    df[col_name] = rolling.apply(calculate_uptick_ratio, raw=False).values

    # Generate tick-based window features
    for window_ticks in tick_windows:
        for feature in target_features:
            if feature not in df.columns:
                continue

            # Create rolling window (tick-based)
            rolling = df[feature].rolling(
                window=window_ticks,
                min_periods=min(min_periods, window_ticks)
            )

            # Apply aggregation functions
            for func_name in agg_funcs:
                col_name = f"{feature}_{func_name}_{window_ticks}t"

                if func_name == 'mean':
                    df[col_name] = rolling.mean()
                elif func_name == 'std':
                    df[col_name] = rolling.std()
                elif func_name == 'min':
                    df[col_name] = rolling.min()
                elif func_name == 'max':
                    df[col_name] = rolling.max()
                elif func_name == 'slope':
                    df[col_name] = rolling.apply(calculate_slope, raw=False)
                elif func_name == 'last_first':
                    df[col_name] = rolling.apply(calculate_last_first, raw=False)
                elif func_name == 'uptick_ratio':
                    df[col_name] = rolling.apply(calculate_uptick_ratio, raw=False)

    # Generate Pre vs Now Delta features if enabled
    if config.get('pre_vs_now', True):
        pre_window_s = config.get('pre_window_s', 5)

        for feature in target_features:
            if feature not in df_indexed.columns:
                continue

            # Calculate pre-window mean (shifted back by pre_window_s)
            pre_mean = df_indexed[feature].rolling(
                window=pd.Timedelta(seconds=pre_window_s),
                min_periods=min_periods
            ).mean()

            # Calculate current mean (various windows)
            for window_s in [1, 2, 5]:
                current_mean = df_indexed[feature].rolling(
                    window=pd.Timedelta(seconds=window_s),
                    min_periods=min_periods
                ).mean()

                # Delta (absolute difference)
                delta_col = f"{feature}_delta_{window_s}s"
                df[delta_col] = (current_mean - pre_mean).values

                # Ratio (relative change)
                ratio_col = f"{feature}_ratio_{window_s}s"
                # Avoid division by zero
                with np.errstate(divide='ignore', invalid='ignore'):
                    ratio = current_mean / pre_mean
                    ratio = ratio.replace([np.inf, -np.inf], np.nan)
                    df[ratio_col] = ratio.values

    # Handle NaN values
    if fillna_method == 'forward':
        df = df.fillna(method='ffill')
    elif fillna_method == 'backward':
        df = df.fillna(method='bfill')
    elif fillna_method == 'zero':
        df = df.fillna(0)

    # Fill any remaining NaN with 0
    df = df.fillna(0)

    logger.info(f"Generated {len(df.columns) - len(target_features) - 1} new window features")

    return df


def get_window_feature_names(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Get list of window feature column names that will be generated.

    Args:
        config: Window features configuration dict.

    Returns:
        List[str]: List of window feature column names.
    """
    if config is None:
        config = load_window_config()

    if not config.get('enabled', True):
        return []

    feature_names = []

    time_windows = config.get('time_windows', [0.5, 1, 2, 5, 10])
    tick_windows = config.get('tick_windows', [10, 20, 50])
    agg_funcs = config.get('agg_funcs', ['mean', 'std', 'min', 'max'])
    target_features = config.get('target_features', ['price', 'ret_1s', 'z_vol_1s'])

    # Time-based features
    for window_s in time_windows:
        for feature in target_features:
            for func_name in agg_funcs:
                feature_names.append(f"{feature}_{func_name}_{window_s}s")

    # Tick-based features
    for window_ticks in tick_windows:
        for feature in target_features:
            for func_name in agg_funcs:
                feature_names.append(f"{feature}_{func_name}_{window_ticks}t")

    # Delta features
    if config.get('pre_vs_now', True):
        for feature in target_features:
            for window_s in [1, 2, 5]:
                feature_names.append(f"{feature}_delta_{window_s}s")
                feature_names.append(f"{feature}_ratio_{window_s}s")

    return feature_names


if __name__ == "__main__":
    # Demo/test the window features generation
    print("Window Features Generation Demo")
    print("=" * 50)

    # Create sample data
    sample_data = {
        'ts': pd.date_range('2025-01-01 09:00:00', periods=100, freq='100ms', tz='Asia/Seoul'),
        'stock_code': ['005930'] * 100,
        'price': 74000 + np.cumsum(np.random.randn(100) * 10),
        'ret_1s': np.random.randn(100) * 0.001,
        'z_vol_1s': np.random.randn(100),
        'spread': np.random.uniform(0.001, 0.01, 100),
        'microprice_slope': np.random.randn(100) * 0.0001,
        'ticks_per_sec': np.random.randint(1, 20, 100)
    }

    df = pd.DataFrame(sample_data)
    print(f"Original DataFrame shape: {df.shape}")
    print(f"Original columns: {list(df.columns)}")

    # Generate window features
    df_with_windows = generate_window_features(df)

    print(f"\nDataFrame with windows shape: {df_with_windows.shape}")
    print(f"New features added: {df_with_windows.shape[1] - df.shape[1]}")

    # Show sample of new columns
    new_cols = [col for col in df_with_windows.columns if col not in df.columns]
    print(f"\nSample new columns (first 10):")
    for col in new_cols[:10]:
        print(f"  - {col}")

    # Check for NaN values
    nan_counts = df_with_windows[new_cols].isna().sum()
    print(f"\nNaN counts in new features:")
    print(f"  Total NaN: {nan_counts.sum()}")
    print(f"  Features with NaN: {(nan_counts > 0).sum()}")