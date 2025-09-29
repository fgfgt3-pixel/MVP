#!/usr/bin/env python3
"""CLI script for generating onset detection quality reports."""

import argparse
import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.reporting import QualityReporter
from src.logger import setup_logging, get_logger


def main():
    """Main quality report generation function."""
    parser = argparse.ArgumentParser(description="Generate onset detection quality report")
    
    # Input options
    parser.add_argument("--events", type=str, action='append', help="Path to events JSONL file(s). Can be used multiple times.")
    parser.add_argument("--candidates", type=str, help="Path to candidates JSONL file")
    parser.add_argument("--confirms", type=str, help="Path to confirmations JSONL file")
    parser.add_argument("--refractory", type=str, help="Path to refractory events JSONL file")
    parser.add_argument("--out", type=str, required=True, help="Output JSON report file path")
    
    # Report options
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--summary", action="store_true", help="Print summary to console")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger_system = setup_logging()
    logger = get_logger("quality_test")
    
    try:
        print("Onset Detection Quality Report Generator")
        print("=" * 50)
        
        logger.info("Starting quality report generation")
        
        # Collect event files
        event_files = []
        
        # Add files specified with --events
        if args.events:
            event_files.extend(args.events)
        
        # Add individual file types
        if args.candidates:
            event_files.append(args.candidates)
        if args.confirms:
            event_files.append(args.confirms)
        if args.refractory:
            event_files.append(args.refractory)
        
        if not event_files:
            print("No event files specified. Using default EventStore files.")
            logger.info("No event files specified, using default files")
            event_files = None
        else:
            print(f"Event files to process: {len(event_files)}")
            if args.verbose:
                for i, file_path in enumerate(event_files):
                    file_path = Path(file_path)
                    exists_status = "[EXISTS]" if file_path.exists() else "[MISSING]"
                    print(f"  {i+1}. {file_path} {exists_status}")
            
            # Verify at least one file exists
            existing_files = [f for f in event_files if Path(f).exists()]
            if not existing_files:
                raise FileNotFoundError("None of the specified event files exist")
            
            print(f"Valid event files found: {len(existing_files)}")
        
        # Initialize quality reporter
        print(f"\nInitializing quality reporter...")
        logger.info("Initializing quality reporter")
        
        from src.config_loader import load_config
        config = None
        if args.config:
            config = load_config(args.config)
            print(f"Using custom config: {args.config}")
        else:
            config = load_config()
            print(f"Using default configuration")
        
        reporter = QualityReporter(config)
        
        # Load and analyze events
        print(f"\nLoading and analyzing events...")
        logger.info("Loading and analyzing events")
        
        if event_files:
            # Load from specified files
            events = reporter.load_events_from_files(event_files)
            print(f"Loaded {len(events)} events from {len([f for f in event_files if Path(f).exists()])} files")
            
            if args.verbose and events:
                print("Sample events (first 5):")
                for i, event in enumerate(events[:5]):
                    event_type = event.get('event_type', 'unknown')
                    timestamp = event.get('ts', 0)
                    stock_code = event.get('stock_code', 'N/A')
                    print(f"  {i+1}. {event_type} at {timestamp}, Stock: {stock_code}")
            
            report = reporter.analyze_events(events)
        else:
            # Use default EventStore files
            report = reporter.generate_report()
            print(f"Analyzed {report['total_events']} events from default EventStore")
        
        # Save report
        output_path = Path(args.out)
        print(f"\nGenerating quality report...")
        logger.info(f"Saving quality report to: {output_path}")
        
        save_success = reporter.save_report(report, output_path)
        
        print(f"\n" + "="*50)
        print("QUALITY REPORT GENERATION RESULTS")
        print("="*50)
        
        print(f"Events analyzed: {report['total_events']}")
        print(f"Stocks analyzed: {report['stocks_analyzed']}")
        print(f"Save successful: {save_success}")
        print(f"Output file: {output_path.absolute()}")
        
        # Print key metrics
        print(f"\nKey Metrics:")
        print(f"  Candidates: {report['n_candidates']}")
        print(f"  Confirmations: {report['n_confirms']}")
        print(f"  Rejections: {report['n_rejected']}")
        print(f"  Confirmation rate: {report['confirm_rate']:.2%}")
        print(f"  Rejection rate: {report['rejection_rate']:.2%}")
        
        if report['n_confirms'] > 0:
            print(f"  TTA Average: {report['tta_avg']:.2f}s")
            print(f"  TTA P95: {report['tta_p95']:.2f}s")
        else:
            print(f"  TTA: N/A (no confirmations)")
        
        # Print full summary if requested
        if args.summary:
            reporter.print_summary(report)
        
        # Verify output file
        if output_path.exists():
            print(f"\nOutput file verification:")
            print(f"  File exists: [OK]")
            print(f"  File size: {output_path.stat().st_size} bytes")
            
            # Try to load and verify JSON structure
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    loaded_report = json.load(f)
                required_fields = ['n_candidates', 'n_confirms', 'n_rejected', 'confirm_rate', 'tta_p95']
                missing_fields = [field for field in required_fields if field not in loaded_report]
                if missing_fields:
                    print(f"  [WARNING] Missing required fields: {missing_fields}")
                else:
                    print(f"  JSON structure: [OK]")
                print(f"  Fields in report: {len(loaded_report)}")
            except Exception as e:
                print(f"  [ERROR] Could not verify JSON structure: {e}")
        else:
            print(f"\n[WARNING] Output file was not created")
        
        # Performance assessment
        print(f"\n" + "="*50)
        print("PERFORMANCE ASSESSMENT")
        print("="*50)
        
        confirm_rate = report['confirm_rate']
        rejection_rate = report['rejection_rate']
        
        if report['total_events'] == 0:
            print("  [INFO] No events analyzed. Check input files.")
        elif report['n_candidates'] == 0:
            print("  [INFO] No candidate events found. Check event types in input files.")
        else:
            if confirm_rate == 0:
                print("  [INFO] No confirmations found. This could indicate:")
                print("    - Confirmation thresholds too strict")
                print("    - No follow-through in feature data")
                print("    - Missing confirmation events in input")
            elif confirm_rate < 0.1:
                print(f"  [INFO] Low confirmation rate ({confirm_rate:.1%}). Consider:")
                print("    - Reviewing confirmation thresholds")
                print("    - Checking feature data quality")
            elif confirm_rate > 0.8:
                print(f"  [WARNING] Very high confirmation rate ({confirm_rate:.1%}). Consider:")
                print("    - Increasing confirmation requirements")
                print("    - Reviewing detection sensitivity")
            else:
                print(f"  [SUCCESS] Reasonable confirmation rate ({confirm_rate:.1%})")
            
            if rejection_rate > 0.5:
                print(f"  [INFO] High rejection rate ({rejection_rate:.1%}). Consider:")
                print("    - Shortening refractory duration")
                print("    - Reviewing candidate detection sensitivity")
            elif rejection_rate > 0:
                print(f"  [SUCCESS] Reasonable rejection rate ({rejection_rate:.1%})")
            
            if report['n_confirms'] > 0 and report['tta_p95'] > 10:
                print(f"  [INFO] High TTA P95 ({report['tta_p95']:.1f}s). Consider:")
                print("    - Shortening confirmation window")
                print("    - Reviewing confirmation criteria")
            elif report['n_confirms'] > 0:
                print(f"  [SUCCESS] Reasonable TTA P95 ({report['tta_p95']:.1f}s)")
        
        logger.info("Quality report generation completed successfully")
        print(f"\n[SUCCESS] Quality report completed!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Quality report generation failed: {e}")
        print(f"\n[ERROR] Quality report generation failed: {e}")
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())