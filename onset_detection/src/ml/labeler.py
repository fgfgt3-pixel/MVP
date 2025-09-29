"""Labeling utilities for converting onset events to ML training labels."""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import yaml
import logging

logger = logging.getLogger(__name__)


def load_ml_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load ML configuration from YAML file.

    Args:
        config_path: Path to ML config YAML. If None, uses default.

    Returns:
        Dict: ML configuration.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / 'config' / 'ml.yaml'

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"ML config not found: {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    return config.get('ml', {})


def load_events_from_jsonl(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Load events from JSONL file.

    Args:
        file_path: Path to JSONL file with events.

    Returns:
        List[Dict]: List of event dictionaries.
    """
    events = []
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Events file not found: {file_path}")

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON line: {line[:50]}... Error: {e}")

    logger.info(f"Loaded {len(events)} events from {file_path}")
    return events


def convert_timestamps_to_datetime(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert event timestamps to pandas datetime objects.

    Args:
        events: List of events with 'ts' field.

    Returns:
        List[Dict]: Events with datetime 'ts' field.
    """
    converted_events = []

    for event in events:
        event_copy = event.copy()
        ts = event.get('ts')

        if ts is not None:
            if isinstance(ts, (int, float)):
                # Check if timestamp is in seconds or milliseconds
                if ts < 1e10:  # Likely seconds
                    dt = pd.to_datetime(ts, unit='s', utc=True).tz_convert('Asia/Seoul')
                else:  # Likely milliseconds
                    dt = pd.to_datetime(ts, unit='ms', utc=True).tz_convert('Asia/Seoul')
            else:
                dt = pd.to_datetime(ts)

            event_copy['ts'] = dt

        converted_events.append(event_copy)

    return converted_events


def create_labels(
    features_df: pd.DataFrame,
    events: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Create training labels from onset events.

    Args:
        features_df: Features DataFrame with 'ts' column.
        events: List of onset events (candidates/confirmations).
        config: ML configuration dict. If None, loads from default config.

    Returns:
        DataFrame: Features with added label columns (y_span, y_forecast).
    """
    if config is None:
        config = load_ml_config()

    # Get labeling parameters
    label_config = config.get('label', {})
    span_s = label_config.get('span_s', 60)
    max_span_s = label_config.get('max_span_s', 90)
    forecast_s = label_config.get('forecast_s', 10)
    pre_buffer_s = label_config.get('pre_buffer_s', 30)

    logger.info(f"Creating labels with span_s={span_s}, forecast_s={forecast_s}")

    # Ensure features DataFrame has datetime index
    if 'ts' not in features_df.columns:
        raise ValueError("Features DataFrame must have 'ts' column")

    # Sort by timestamp
    features_df = features_df.sort_values('ts').copy()

    # Convert event timestamps to datetime
    events = convert_timestamps_to_datetime(events)

    # Filter to relevant event types (candidates and confirmations)
    onset_events = [
        e for e in events
        if e.get('event_type') in ['onset_candidate', 'onset_confirmed']
    ]

    logger.info(f"Using {len(onset_events)} onset events for labeling")

    # Initialize label columns
    features_df['y_span'] = 0
    features_df['y_forecast'] = 0

    # Process each onset event
    for event in onset_events:
        event_ts = event.get('ts')
        if event_ts is None:
            continue

        stock_code = event.get('stock_code')

        # Filter features for this stock
        if stock_code:
            stock_features = features_df[
                features_df['stock_code'].astype(str) == str(stock_code)
            ]
        else:
            stock_features = features_df

        if stock_features.empty:
            continue

        # Create span labels (onset_ts ~ onset_ts + span_s)
        span_start = event_ts
        span_end = event_ts + pd.Timedelta(seconds=min(span_s, max_span_s))

        span_mask = (
            (stock_features['ts'] >= span_start) &
            (stock_features['ts'] <= span_end)
        )

        # Apply span labels
        if stock_code:
            features_df.loc[
                (features_df['stock_code'].astype(str) == str(stock_code)) & span_mask,
                'y_span'
            ] = 1
        else:
            features_df.loc[span_mask, 'y_span'] = 1

        # Create forecast labels (pre_buffer before onset)
        forecast_start = event_ts - pd.Timedelta(seconds=pre_buffer_s)
        forecast_end = event_ts

        forecast_mask = (
            (stock_features['ts'] >= forecast_start) &
            (stock_features['ts'] < forecast_end)
        )

        # Check if there's an onset within forecast_s seconds
        future_onset_end = event_ts + pd.Timedelta(seconds=forecast_s)

        # Apply forecast labels (anticipating onset within forecast_s)
        if stock_code:
            features_df.loc[
                (features_df['stock_code'].astype(str) == str(stock_code)) & forecast_mask,
                'y_forecast'
            ] = 1
        else:
            features_df.loc[forecast_mask, 'y_forecast'] = 1

    # Log class distribution
    span_dist = features_df['y_span'].value_counts()
    forecast_dist = features_df['y_forecast'].value_counts()

    logger.info(f"Span label distribution: {dict(span_dist)}")
    logger.info(f"Forecast label distribution: {dict(forecast_dist)}")

    span_pos_rate = span_dist.get(1, 0) / len(features_df)
    forecast_pos_rate = forecast_dist.get(1, 0) / len(features_df)

    logger.info(f"Span positive rate: {span_pos_rate:.4f}")
    logger.info(f"Forecast positive rate: {forecast_pos_rate:.4f}")

    return features_df


def prepare_training_data(
    features_df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    target_column: str = 'y_span'
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Prepare features and target for training.

    Args:
        features_df: DataFrame with features and labels.
        config: ML configuration dict.
        target_column: Name of target column ('y_span' or 'y_forecast').

    Returns:
        Tuple: (X features DataFrame, y target Series).
    """
    if config is None:
        config = load_ml_config()

    # Get columns to drop
    features_config = config.get('features', {})
    drop_columns = features_config.get('drop_columns', [])

    # Ensure target column exists
    if target_column not in features_df.columns:
        raise ValueError(f"Target column '{target_column}' not found in DataFrame")

    # Separate features and target
    y = features_df[target_column].copy()

    # Drop specified columns and target columns
    all_drop_columns = drop_columns + ['y_span', 'y_forecast']
    available_drop_columns = [col for col in all_drop_columns if col in features_df.columns]

    X = features_df.drop(columns=available_drop_columns)

    logger.info(f"Training data shape: X={X.shape}, y={y.shape}")
    logger.info(f"Dropped columns: {available_drop_columns}")
    logger.info(f"Target distribution: {dict(y.value_counts())}")

    return X, y


def create_training_dataset(
    features_file: Union[str, Path],
    events_file: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Create complete training dataset from features CSV and events JSONL.

    Args:
        features_file: Path to features CSV file.
        events_file: Path to events JSONL file.
        output_file: Optional path to save labeled dataset.
        config: ML configuration dict.

    Returns:
        DataFrame: Complete dataset with features and labels.
    """
    if config is None:
        config = load_ml_config()

    logger.info("Creating training dataset")
    logger.info(f"Features file: {features_file}")
    logger.info(f"Events file: {events_file}")

    # Load features
    features_df = pd.read_csv(features_file)
    logger.info(f"Loaded features: shape={features_df.shape}")

    # Parse timestamp column
    if 'ts' in features_df.columns:
        features_df['ts'] = pd.to_datetime(features_df['ts'], format='mixed')

    # Load events
    events = load_events_from_jsonl(events_file)

    # Create labels
    labeled_df = create_labels(features_df, events, config)

    # Save if output path specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        labeled_df.to_csv(output_path, index=False)
        logger.info(f"Saved labeled dataset to: {output_path}")

    return labeled_df


if __name__ == "__main__":
    # Demo/test the labeling functionality
    import argparse

    parser = argparse.ArgumentParser(description="Create training labels from onset events")
    parser.add_argument("--features", type=str, required=True, help="Features CSV file")
    parser.add_argument("--events", type=str, required=True, help="Events JSONL file")
    parser.add_argument("--output", type=str, help="Output labeled CSV file")
    parser.add_argument("--config", type=str, help="ML config YAML file")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Load config if specified
    config = None
    if args.config:
        config = load_ml_config(args.config)

    # Create training dataset
    try:
        labeled_df = create_training_dataset(
            features_file=args.features,
            events_file=args.events,
            output_file=args.output,
            config=config
        )

        print("\nLabeling Summary:")
        print(f"Total samples: {len(labeled_df)}")
        print(f"Features: {len(labeled_df.columns) - 2}")  # Subtract y_span, y_forecast
        print(f"Span labels: {dict(labeled_df['y_span'].value_counts())}")
        print(f"Forecast labels: {dict(labeled_df['y_forecast'].value_counts())}")

    except Exception as e:
        logger.error(f"Labeling failed: {e}")
        raise