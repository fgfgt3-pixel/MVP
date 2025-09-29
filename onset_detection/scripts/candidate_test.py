#!/usr/bin/env python3
"""CLI script for testing candidate detection functionality."""

import argparse
import sys
import pandas as pd
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.detection import CandidateDetector
from src.logger import setup_logging, get_logger


def main():
    """Main candidate detection test function."""
    parser = argparse.ArgumentParser(description="Detect onset candidates from features")
    
    # Input options
    parser.add_argument("--features", type=str, required=True, help="Path to features CSV file")
    parser.add_argument("--out", type=str, required=True, help="Output candidates JSONL file path")
    
    # Detection options
    parser.add_argument("--threshold", type=float, help="Override score threshold")
    parser.add_argument("--vol-z-min", type=float, help="Override volume z-score minimum")
    parser.add_argument("--ticks-min", type=int, help="Override minimum ticks per second")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger_system = setup_logging()
    logger = get_logger("candidate_test")
    
    try:
        print("Onset Candidate Detection Test")
        print("=" * 50)
        
        logger.info("Starting candidate detection test")
        
        # Load features CSV
        print(f"Loading features from: {args.features}")
        logger.info(f"Loading features from: {args.features}")
        
        # Check if file exists
        features_path = Path(args.features)
        if not features_path.exists():
            raise FileNotFoundError(f"Features file not found: {args.features}")
        
        # Load features DataFrame
        features_df = pd.read_csv(features_path)
        # Parse timestamp column properly
        if 'ts' in features_df.columns:
            features_df['ts'] = pd.to_datetime(features_df['ts'], format='mixed')
        print(f"Loaded {len(features_df)} feature rows, {len(features_df.columns)} columns")
        
        if args.verbose:
            print(f"Features columns: {list(features_df.columns)}")
            print(f"Sample features data:")
            indicator_cols = ['ret_1s', 'accel_1s', 'z_vol_1s', 'ticks_per_sec']
            available_cols = [col for col in indicator_cols if col in features_df.columns]
            if available_cols:
                print(features_df[available_cols].head())
        
        # Initialize candidate detector
        print(f"\\nInitializing candidate detector...")
        logger.info("Initializing candidate detector")
        
        detector = CandidateDetector()
        
        # Override detection parameters if provided
        if args.threshold is not None:
            detector.score_threshold = args.threshold
            print(f"Overriding score threshold to: {args.threshold}")
        
        if args.vol_z_min is not None:
            detector.vol_z_min = args.vol_z_min
            print(f"Overriding volume z-score minimum to: {args.vol_z_min}")
        
        if args.ticks_min is not None:
            detector.ticks_min = args.ticks_min
            print(f"Overriding minimum ticks per second to: {args.ticks_min}")
        
        print(f"Detection parameters:")
        print(f"  Score threshold: {detector.score_threshold}")
        print(f"  Volume z-score min: {detector.vol_z_min}")
        print(f"  Ticks per second min: {detector.ticks_min}")
        print(f"  Weights: {detector.weights}")
        
        # Get detection statistics first
        print(f"\\nAnalyzing detection potential...")
        logger.info("Getting detection statistics")
        
        stats = detector.get_detection_stats(features_df)
        
        print(f"Detection Analysis:")
        print(f"  Total rows: {stats['total_rows']}")
        print(f"  Valid rows: {stats['valid_rows']}")
        print(f"  Candidates detected: {stats['candidates_detected']}")
        print(f"  Detection rate: {stats['detection_rate']:.2%}")
        
        if stats['score_stats']:
            print(f"  Score statistics:")
            print(f"    Mean: {stats['score_stats']['mean']:.3f}")
            print(f"    Std: {stats['score_stats']['std']:.3f}")
            print(f"    Min: {stats['score_stats']['min']:.3f}")
            print(f"    Max: {stats['score_stats']['max']:.3f}")
            print(f"    P95: {stats['score_stats']['p95']:.3f}")
        
        print(f"  Condition satisfaction:")
        print(f"    Volume z >= {stats['condition_stats']['vol_z_min']}: {stats['condition_stats']['vol_z_satisfied']}")
        print(f"    Ticks >= {stats['condition_stats']['ticks_min']}: {stats['condition_stats']['ticks_satisfied']}")
        
        # Detect and save candidates
        print(f"\\nDetecting candidates...")
        logger.info("Detecting and saving candidates")
        
        # Extract filename for EventStore
        output_path = Path(args.out)
        output_filename = output_path.name
        
        result = detector.detect_and_save(features_df, filename=output_filename)
        
        candidates_count = result["candidates_detected"]
        save_success = result["save_success"]
        candidates = result["events"]
        
        print(f"\\n" + "="*50)
        print("DETECTION RESULTS")
        print("="*50)
        
        print(f"Candidates detected: {candidates_count}")
        print(f"Save successful: {save_success}")
        print(f"Output file: {output_path.absolute()}")
        
        # Show sample candidates
        if candidates and args.verbose:
            print(f"\\nSample candidates (first 5):")
            for i, candidate in enumerate(candidates[:5]):
                print(f"  {i+1}. Timestamp: {candidate['ts']}")
                print(f"     Stock: {candidate['stock_code']}")
                print(f"     Score: {candidate['score']:.3f}")
                print(f"     Evidence:")
                evidence = candidate['evidence']
                print(f"       ret_1s: {evidence['ret_1s']:.4f}")
                print(f"       accel_1s: {evidence['accel_1s']:.4f}")
                print(f"       z_vol_1s: {evidence['z_vol_1s']:.2f}")
                print(f"       ticks_per_sec: {evidence['ticks_per_sec']}")
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
        
        if candidates_count == 0:
            print("  [INFO] No candidates detected. Consider:")
            print("    - Lowering score_threshold")
            print("    - Lowering vol_z_min")
            print("    - Lowering ticks_min") 
            print("    - Check if features data has sufficient variation")
        elif candidates_count > len(features_df) * 0.1:
            print(f"  [WARNING] High detection rate ({stats['detection_rate']:.1%}). Consider:")
            print("    - Increasing score_threshold")
            print("    - Increasing vol_z_min or ticks_min")
        else:
            print(f"  [SUCCESS] Reasonable detection rate ({stats['detection_rate']:.1%})")
        
        logger.info("Candidate detection completed successfully")
        print(f"\\n[SUCCESS] Candidate detection completed!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Candidate detection failed: {e}")
        print(f"\\n[ERROR] Candidate detection failed: {e}")
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())