#!/usr/bin/env python3
"""Generate features from clean CSV using core_indicators."""

import argparse
import sys
from pathlib import Path
import pandas as pd

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.features.core_indicators import CoreIndicators, calculate_core_indicators
from src.data_loader import DataLoader
from src.config_loader import load_config
from src.utils.paths import PathManager
from src.ml.window_features import generate_window_features


def main():
    """Generate features from clean CSV data."""
    parser = argparse.ArgumentParser(description='Generate features from clean CSV')
    parser.add_argument('--input', '-i', type=str, required=True,
                       help='Input clean CSV filename (in data/clean/)')
    parser.add_argument('--output', '-o', type=str,
                       help='Output features CSV filename (in data/features/)')

    args = parser.parse_args()

    print("Features Generation Tool")
    print("=" * 40)

    try:
        # Load configuration
        config = load_config()
        path_manager = PathManager(config)

        # Load clean CSV
        clean_path = path_manager.get_data_clean_path() / args.input
        print(f"Loading clean CSV: {clean_path}")

        if not clean_path.exists():
            raise FileNotFoundError(f"Clean CSV not found: {clean_path}")

        # Load data using data_loader for proper parsing
        loader = DataLoader(config)
        df = pd.read_csv(clean_path)

        # Ensure timestamp is properly parsed
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'], format='mixed')

        print(f"Loaded clean data: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print(f"Date range: {df['ts'].min()} to {df['ts'].max()}")

        # Generate core indicators
        print("\nGenerating core indicators...")
        calculator = CoreIndicators(config)

        # Add indicators to DataFrame
        df_with_features = calculator.add_indicators(df)

        print(f"Core features generated: {df_with_features.shape}")

        # Add window features
        try:
            print("\nGenerating window features...")
            df_with_features = generate_window_features(df_with_features)
            print(f"Window features added. Final shape: {df_with_features.shape}")
        except Exception as e:
            print(f"Warning: Window features failed: {e}")

        print(f"Total columns: {len(df_with_features.columns)}")

        # Check for required indicators
        required_indicators = [
            'ret_1s', 'accel_1s', 'z_vol_1s', 'ticks_per_sec',
            'spread', 'microprice', 'microprice_slope'
        ]

        missing_indicators = [ind for ind in required_indicators if ind not in df_with_features.columns]
        if missing_indicators:
            print(f"Warning: Missing indicators: {missing_indicators}")
        else:
            print("All required indicators generated successfully!")

        # Display sample statistics
        print(f"\nIndicator Statistics:")
        for indicator in required_indicators:
            if indicator in df_with_features.columns:
                series = df_with_features[indicator]
                print(f"  {indicator}: mean={series.mean():.6f}, std={series.std():.6f}, "
                      f"min={series.min():.6f}, max={series.max():.6f}")

        # Determine output filename
        if args.output:
            output_filename = args.output
        else:
            # Generate output filename - keep original name structure
            input_stem = Path(args.input).stem
            if input_stem.endswith('_clean'):
                # Replace _clean with _features
                output_filename = input_stem.replace('_clean', '_features') + '.csv'
            else:
                # Add _features suffix
                output_filename = f"{input_stem}_features.csv"

        # Save to features directory
        features_path = path_manager.get_data_features_path()
        output_path = features_path / output_filename

        # Ensure features directory exists
        features_path.mkdir(parents=True, exist_ok=True)

        print(f"\nSaving features CSV: {output_path}")
        df_with_features.to_csv(output_path, index=False)

        print(f"\nFeatures generation completed!")
        print(f"Features file: {output_path}")
        print(f"Final shape: {df_with_features.shape}")

        # Verify file was saved
        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"File size: {file_size:,} bytes")
        else:
            print("Warning: Output file was not created")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())