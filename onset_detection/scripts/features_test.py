#!/usr/bin/env python3
"""CLI script for testing core indicators calculation functionality."""

import argparse
import sys
import pandas as pd
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data_loader import DataLoader
from src.features import calculate_core_indicators
from src.logger import setup_logging, get_logger


def main():
    """Main features test function."""
    parser = argparse.ArgumentParser(description="Calculate core indicators for onset detection")
    
    # Input options
    parser.add_argument("--csv", type=str, required=True, help="Path to clean CSV file")
    parser.add_argument("--out", type=str, required=True, help="Output features CSV file path")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger_system = setup_logging()
    logger = get_logger("features_test")
    
    try:
        print("Core Indicators Calculation Test")
        print("=" * 50)
        
        logger.info("Starting features calculation test")
        
        # Load CSV data
        print(f"Loading data from: {args.csv}")
        logger.info(f"Loading data from: {args.csv}")
        
        # Check if file exists
        csv_path = Path(args.csv)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {args.csv}")
        
        # Load data using pandas directly for clean data
        df = pd.read_csv(csv_path)
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
        
        if args.verbose:
            print(f"Input columns: {list(df.columns)}")
            print(f"Data shape: {df.shape}")
            print(f"Sample data:")
            print(df.head())
        
        # Validate required columns
        required_columns = ['ts', 'stock_code', 'price', 'volume', 'bid1', 'ask1', 'bid_qty1', 'ask_qty1']
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Calculate core indicators
        print(f"\\nCalculating core indicators...")
        logger.info("Calculating core indicators")
        
        result_df = calculate_core_indicators(df)
        
        print(f"Result shape: {result_df.shape}")
        
        # Check added columns
        original_cols = set(df.columns)
        result_cols = set(result_df.columns)
        new_cols = result_cols - original_cols
        
        print(f"\\nAdded {len(new_cols)} indicator columns:")
        for col in sorted(new_cols):
            print(f"  - {col}")
        
        if args.verbose:
            print(f"\\nSample indicator values:")
            indicator_cols = ['ret_1s', 'accel_1s', 'ticks_per_sec', 'vol_1s', 'z_vol_1s',
                             'spread', 'microprice', 'microprice_slope']
            available_indicators = [col for col in indicator_cols if col in result_df.columns]
            if available_indicators:
                print(result_df[available_indicators].head(10))
            
            # Check for NaN values
            nan_counts = result_df[available_indicators].isna().sum()
            if nan_counts.sum() > 0:
                print(f"\\nNaN counts: {nan_counts[nan_counts > 0].to_dict()}")
            else:
                print("\\nNo NaN values found in indicators.")
        
        # Save results
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"\\nSaving results to: {args.out}")
        logger.info(f"Saving results to: {args.out}")
        
        result_df.to_csv(output_path, index=False)
        
        # Verify saved file
        saved_df = pd.read_csv(output_path)
        print(f"Saved file verified: {len(saved_df)} rows, {len(saved_df.columns)} columns")
        
        # Summary statistics
        print(f"\\n" + "="*50)
        print("CALCULATION SUMMARY")
        print("="*50)
        
        summary_stats = {
            "Input rows": len(df),
            "Output rows": len(result_df),
            "Input columns": len(df.columns),
            "Output columns": len(result_df.columns),
            "Added indicators": len(new_cols),
            "File saved": str(output_path.absolute())
        }
        
        for key, value in summary_stats.items():
            print(f"  {key:<20}: {value}")
        
        # Quick validation of key indicators
        expected_indicators = ['ret_1s', 'accel_1s', 'ticks_per_sec', 'vol_1s', 'z_vol_1s',
                              'spread', 'microprice', 'microprice_slope']
        
        missing_indicators = [col for col in expected_indicators if col not in result_df.columns]
        if missing_indicators:
            print(f"\\n[WARNING] Missing expected indicators: {missing_indicators}")
        else:
            print(f"\\n[SUCCESS] All {len(expected_indicators)} expected indicators calculated!")
        
        logger.info("Features calculation completed successfully")
        print(f"\\n[SUCCESS] Features calculation completed!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Features calculation failed: {e}")
        print(f"\\n[ERROR] Features calculation failed: {e}")
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())