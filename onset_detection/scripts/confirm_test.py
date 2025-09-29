#!/usr/bin/env python3
"""CLI script for testing confirmation detection functionality."""

import argparse
import sys
import pandas as pd
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.detection import ConfirmDetector
from src.logger import setup_logging, get_logger


def load_candidate_events(candidates_file: Path) -> list:
    """Load candidate events from JSONL file."""
    candidates = []
    
    if not candidates_file.exists():
        raise FileNotFoundError(f"Candidates file not found: {candidates_file}")
    
    with open(candidates_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    event = json.loads(line)
                    candidates.append(event)
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse line: {line[:50]}...")
                    continue
    
    return candidates


def main():
    """Main confirmation test function."""
    parser = argparse.ArgumentParser(description="Confirm onset candidates")
    
    # Input options
    parser.add_argument("--features", type=str, required=True, help="Path to features CSV file")
    parser.add_argument("--cands", type=str, required=True, help="Path to candidates JSONL file")
    parser.add_argument("--out", type=str, required=True, help="Output confirmations JSONL file path")
    
    # Confirmation options
    parser.add_argument("--window", type=int, help="Override confirmation window (seconds)")
    parser.add_argument("--min-axes", type=int, help="Override minimum axes requirement")
    parser.add_argument("--vol-z-min", type=float, help="Override volume z-score minimum")
    parser.add_argument("--spread-max", type=float, help="Override maximum spread")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger_system = setup_logging()
    logger = get_logger("confirm_test")
    
    try:
        print("Onset Confirmation Test")
        print("=" * 50)
        
        logger.info("Starting confirmation test")
        
        # Load features CSV
        print(f"Loading features from: {args.features}")
        logger.info(f"Loading features from: {args.features}")
        
        features_path = Path(args.features)
        if not features_path.exists():
            raise FileNotFoundError(f"Features file not found: {args.features}")
        
        features_df = pd.read_csv(features_path)
        # Parse timestamp column properly
        if 'ts' in features_df.columns:
            features_df['ts'] = pd.to_datetime(features_df['ts'], format='mixed')
        print(f"Loaded {len(features_df)} feature rows, {len(features_df.columns)} columns")
        
        # Load candidate events
        print(f"Loading candidates from: {args.cands}")
        logger.info(f"Loading candidates from: {args.cands}")
        
        candidates_path = Path(args.cands)
        candidate_events = load_candidate_events(candidates_path)
        print(f"Loaded {len(candidate_events)} candidate events")
        
        if args.verbose and candidate_events:
            print("Sample candidate events:")
            for i, cand in enumerate(candidate_events[:3]):
                print(f"  {i+1}. Timestamp: {cand['ts']}, Stock: {cand['stock_code']}, Score: {cand.get('score', 'N/A')}")
        
        # Initialize confirm detector
        print(f"\\nInitializing confirm detector...")
        logger.info("Initializing confirm detector")
        
        detector = ConfirmDetector()
        
        # Override confirmation parameters if provided
        if args.window is not None:
            detector.window_s = args.window
            print(f"Overriding confirmation window to: {args.window}s")

        if args.min_axes is not None:
            detector.min_axes = args.min_axes
            print(f"Overriding minimum axes requirement to: {args.min_axes}")

        # Note: vol_z_min and spread_max are deprecated in Delta-based logic
        # but kept for compatibility
        if args.vol_z_min is not None:
            print(f"Note: vol_z_min parameter is deprecated in Delta-based logic")

        if args.spread_max is not None:
            print(f"Note: spread_max parameter is deprecated in Delta-based logic")

        print(f"Confirmation parameters (Delta-based):")
        print(f"  Window length: {detector.window_s}s")
        print(f"  Pre-window length: {detector.pre_window_s}s")
        print(f"  Minimum axes: {detector.min_axes}")
        print(f"  Price axis required: {detector.require_price_axis}")
        print(f"  Delta thresholds:")
        print(f"    Return improvement: {detector.delta_ret_min:.4f}")
        print(f"    Volume z-score increase: {detector.delta_zvol_min:.2f}")
        print(f"    Spread reduction: {detector.delta_spread_drop:.4f}")
        
        # Get confirmation statistics first
        print(f"\\nAnalyzing confirmation potential...")
        logger.info("Getting confirmation statistics")
        
        stats = detector.get_confirmation_stats(features_df, candidate_events)
        
        print(f"Confirmation Analysis:")
        print(f"  Candidates processed: {stats['candidates_processed']}")
        print(f"  Confirmations possible: {stats['confirmations_possible']}")
        print(f"  Confirmation rate: {stats['confirmation_rate']:.2%}")
        
        if stats['axes_stats']:
            print(f"  Axes satisfaction:")
            for axis, count in stats['axes_stats'].items():
                percentage = count / stats['candidates_processed'] * 100 if stats['candidates_processed'] > 0 else 0
                print(f"    {axis}: {count}/{stats['candidates_processed']} ({percentage:.1f}%)")
        
        if stats['window_stats']:
            print(f"  Window statistics:")
            print(f"    Mean window size: {stats['window_stats']['mean_size']:.1f} rows")
            print(f"    Window size range: {stats['window_stats']['min_size']}-{stats['window_stats']['max_size']}")
        
        # Confirm candidates and save
        print(f"\\nConfirming candidates...")
        logger.info("Confirming and saving candidates")
        
        # Extract filename for EventStore
        output_path = Path(args.out)
        output_filename = output_path.name
        
        result = detector.confirm_and_save(features_df, candidate_events, filename=output_filename)
        
        confirmations_count = result["confirmations_created"]
        save_success = result["save_success"]
        confirmation_rate = result["confirmation_rate"]
        confirmed_events = result["events"]
        tta_stats = result["tta_stats"]
        
        print(f"\\n" + "="*50)
        print("CONFIRMATION RESULTS")
        print("="*50)
        
        print(f"Candidates processed: {result['candidates_processed']}")
        print(f"Confirmations created: {confirmations_count}")
        print(f"Confirmation rate: {confirmation_rate:.2%}")
        print(f"Save successful: {save_success}")
        print(f"Output file: {output_path.absolute()}")
        
        # Show TTA statistics
        if tta_stats:
            print(f"\\nTime-to-Alert (TTA) Statistics:")
            print(f"  Mean TTA: {tta_stats['mean']:.2f}s")
            print(f"  Median TTA: {tta_stats['median']:.2f}s")
            print(f"  TTA range: {tta_stats['min']:.2f}s - {tta_stats['max']:.2f}s")
        
        # Show sample confirmations
        if confirmed_events and args.verbose:
            print(f"\\nSample confirmations (first 5):")
            for i, confirmation in enumerate(confirmed_events[:5]):
                print(f"  {i+1}. Timestamp: {confirmation['ts']}")
                print(f"     Stock: {confirmation['stock_code']}")
                print(f"     Confirmed from: {confirmation['confirmed_from']}")
                print(f"     TTA: {(confirmation['ts'] - confirmation['confirmed_from']) / 1000:.2f}s")
                print(f"     Satisfied axes: {confirmation['evidence']['axes']}")
                evidence = confirmation['evidence']
                print(f"     Evidence:")
                print(f"       ret_1s: {evidence['ret_1s']:.4f}")
                print(f"       z_vol_1s: {evidence['z_vol_1s']:.2f}")
                print(f"       spread: {evidence['spread']:.4f}")
                print()
        
        # Verify output file
        if output_path.exists():
            print(f"\\nOutput file verification:")
            print(f"  File exists: [OK]")
            print(f"  File size: {output_path.stat().st_size} bytes")
            
            # Try to load and count lines
            try:
                with open(output_path, 'r') as f:
                    lines = f.readlines()
                print(f"  Events in file: {len(lines)}")
            except Exception as e:
                print(f"  Could not verify file contents: {e}")
        else:
            print(f"\\n[WARNING] Output file was not created")
        
        # Performance assessment
        print(f"\\n" + "="*50)
        print("PERFORMANCE ASSESSMENT")
        print("="*50)
        
        if confirmations_count == 0:
            print("  [INFO] No confirmations created. Consider:")
            print("    - Lowering min_axes requirement")
            print("    - Increasing window_s duration")
            print("    - Lowering vol_z_min threshold")
            print("    - Increasing spread_max threshold")
            print("    - Check if features data has sufficient follow-through")
        elif confirmation_rate < 0.1:
            print(f"  [INFO] Low confirmation rate ({confirmation_rate:.1%}). Consider:")
            print("    - Adjusting confirmation thresholds")
            print("    - Extending confirmation window")
        elif confirmation_rate > 0.8:
            print(f"  [WARNING] Very high confirmation rate ({confirmation_rate:.1%}). Consider:")
            print("    - Increasing min_axes requirement")
            print("    - Tightening vol_z_min or spread_max thresholds")
        else:
            print(f"  [SUCCESS] Reasonable confirmation rate ({confirmation_rate:.1%})")
        
        if tta_stats and 'mean' in tta_stats:
            if tta_stats['mean'] > 10:
                print(f"  [INFO] High mean TTA ({tta_stats['mean']:.1f}s). Consider shortening confirmation window")
            else:
                print(f"  [SUCCESS] Reasonable mean TTA ({tta_stats['mean']:.1f}s)")
        
        logger.info("Confirmation test completed successfully")
        print(f"\\n[SUCCESS] Confirmation completed!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Confirmation test failed: {e}")
        print(f"\\n[ERROR] Confirmation failed: {e}")
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())