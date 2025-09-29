#!/usr/bin/env python3
"""Convert raw CSV to clean format using existing data_loader."""

import argparse
import sys
from pathlib import Path
import pandas as pd

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data_loader import DataLoader
from src.config_loader import load_config
from src.utils.paths import PathManager


def preprocess_raw_csv(df_raw):
    """Preprocess raw CSV to match data_loader expectations."""
    import pandas as pd

    df = df_raw.copy()

    # Column mapping from raw to expected format
    column_map = {
        'time': 'ts',
        'current_price': 'price',
        'bid1_qty': 'bid_qty1',
        'ask1_qty': 'ask_qty1'
    }

    # Rename columns
    df = df.rename(columns=column_map)

    # Keep only required columns
    required_columns = ['ts', 'stock_code', 'price', 'volume', 'bid1', 'ask1', 'bid_qty1', 'ask_qty1']
    available_columns = [col for col in required_columns if col in df.columns]

    df = df[available_columns].copy()

    # Handle missing columns with defaults
    if 'bid1' not in df.columns and 'price' in df.columns:
        df['bid1'] = df['price']
    if 'ask1' not in df.columns and 'price' in df.columns:
        df['ask1'] = df['price']
    if 'bid_qty1' not in df.columns:
        df['bid_qty1'] = 0
    if 'ask_qty1' not in df.columns:
        df['ask_qty1'] = 0

    return df


def main():
    """Convert raw CSV to clean format."""
    parser = argparse.ArgumentParser(description='Convert raw CSV to clean format')
    parser.add_argument('--input', '-i', type=str, required=True,
                       help='Input raw CSV filename (in data/raw/)')
    parser.add_argument('--output', '-o', type=str,
                       help='Output clean CSV filename (in data/clean/)')

    args = parser.parse_args()

    print("Raw to Clean CSV Converter")
    print("=" * 40)

    try:
        # Load configuration
        config = load_config()
        path_manager = PathManager(config)

        # Load raw CSV first
        raw_path = path_manager.get_data_raw_path() / args.input
        print(f"Loading raw CSV: {raw_path}")

        if not raw_path.exists():
            raise FileNotFoundError(f"Raw CSV not found: {raw_path}")

        df_raw = pd.read_csv(raw_path)
        print(f"Raw data shape: {df_raw.shape}")
        print(f"Raw columns: {list(df_raw.columns)}")

        # Preprocess to match data_loader format
        print("Preprocessing raw data...")
        df_preprocessed = preprocess_raw_csv(df_raw)

        # Save preprocessed data temporarily
        temp_path = path_manager.get_data_raw_path() / "temp_preprocessed.csv"
        df_preprocessed.to_csv(temp_path, index=False)

        # Now use data_loader for final processing
        print("Using data_loader for final processing...")
        loader = DataLoader(config)
        df_final = loader.load_csv("temp_preprocessed.csv", validate_schema=True)

        # Clean up temp file
        temp_path.unlink()

        print(f"Final processed data shape: {df_final.shape}")
        print(f"Final columns: {list(df_final.columns)}")

        # Determine output filename
        if args.output:
            output_filename = args.output
        else:
            # Generate output filename
            input_stem = Path(args.input).stem
            output_filename = f"{input_stem}_clean.csv"

        # Save to clean directory
        clean_path = path_manager.get_data_clean_path()
        output_path = clean_path / output_filename

        # Ensure clean directory exists
        clean_path.mkdir(parents=True, exist_ok=True)

        print(f"Saving clean CSV: {output_path}")
        df_final.to_csv(output_path, index=False)

        print(f"\nConversion completed!")
        print(f"Clean file: {output_path}")
        print(f"Shape: {df_final.shape}")

        # Show data info
        info = loader.get_data_info(df_final)
        print(f"\nData Info:")
        for key, value in info.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())