#!/usr/bin/env python3
"""CLI script for generating onset detection visual reports."""

import argparse
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.reporting import PlotReporter
from src.logger import setup_logging, get_logger


def main():
    """Main plot report generation function."""
    parser = argparse.ArgumentParser(description="Generate onset detection visual report")
    
    # Input options
    parser.add_argument("--csv", type=str, required=True, help="Path to price data CSV file")
    parser.add_argument("--events", type=str, action='append', help="Path to events JSONL file(s). Can be used multiple times.")
    parser.add_argument("--candidates", type=str, help="Path to candidates JSONL file")
    parser.add_argument("--confirms", type=str, help="Path to confirmations JSONL file")
    parser.add_argument("--refractory", type=str, help="Path to refractory events JSONL file")
    parser.add_argument("--labels", type=str, help="Path to labels CSV file (optional)")
    parser.add_argument("--out", type=str, required=True, help="Output PNG file path")
    
    # Plot options
    parser.add_argument("--stock", type=str, help="Stock code to filter (if not specified, uses first stock from data)")
    parser.add_argument("--title", type=str, help="Additional title suffix")
    parser.add_argument("--dpi", type=int, default=300, help="Plot resolution (DPI)")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger_system = setup_logging()
    logger = get_logger("plot_report_test")
    
    try:
        print("Onset Detection Visual Report Generator")
        print("=" * 50)
        
        logger.info("Starting plot report generation")
        
        # Validate input CSV
        csv_path = Path(args.csv)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {args.csv}")
        
        print(f"Price data CSV: {csv_path}")
        
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
            raise ValueError("No event files specified. Use --events, --candidates, --confirms, or --refractory")
        
        # Verify event files exist
        existing_files = []
        for file_path in event_files:
            file_path = Path(file_path)
            if file_path.exists():
                existing_files.append(file_path)
            elif args.verbose:
                print(f"  [WARNING] Event file not found: {file_path}")
        
        if not existing_files:
            raise FileNotFoundError("None of the specified event files exist")
        
        print(f"Event files: {len(existing_files)} files found")
        if args.verbose:
            for i, file_path in enumerate(existing_files):
                print(f"  {i+1}. {file_path}")
        
        # Handle labels file
        labels_path = None
        if args.labels:
            labels_path = Path(args.labels)
            if labels_path.exists():
                print(f"Labels file: {labels_path}")
            else:
                print(f"[WARNING] Labels file not found: {labels_path}")
                labels_path = None
        
        # Initialize plot reporter
        print(f"\nInitializing plot reporter...")
        logger.info("Initializing plot reporter")
        
        from src.config_loader import load_config
        config = None
        if args.config:
            config = load_config(args.config)
            print(f"Using custom config: {args.config}")
        else:
            config = load_config()
            print(f"Using default configuration")
        
        reporter = PlotReporter(config)
        
        # Set plot parameters
        stock_code = args.stock
        title_suffix = args.title or ""
        output_path = Path(args.out)
        
        print(f"\nGenerating visual report...")
        logger.info(f"Generating plot report for output: {output_path}")
        
        if stock_code:
            print(f"Stock filter: {stock_code}")
        if title_suffix:
            print(f"Title suffix: {title_suffix}")
        
        # Generate report
        summary = reporter.generate_report(
            csv_path=csv_path,
            event_files=existing_files,
            output_path=output_path,
            labels_path=labels_path,
            stock_code=stock_code,
            title_suffix=title_suffix
        )
        
        print(f"\n" + "="*50)
        print("PLOT REPORT GENERATION RESULTS")
        print("="*50)
        
        if "error" in summary:
            print(f"Error: {summary['error']}")
            raise Exception(summary['error'])
        
        # Display results
        print(f"Stock code: {summary['stock_code']}")
        print(f"Time range: {summary['time_range']['start']} to {summary['time_range']['end']}")
        print(f"Price data points: {summary['price_data_points']}")
        
        events = summary['events']
        print(f"Events plotted:")
        print(f"  Candidates: {events['candidates']}")
        print(f"  Confirmations: {events['confirmations']}")
        print(f"  Rejections: {events['rejections']}")
        
        total_events = events['candidates'] + events['confirmations'] + events['rejections']
        print(f"  Total events: {total_events}")
        
        print(f"Labels: {summary['labels_count']} label spans")
        print(f"Save successful: {summary['save_success']}")
        print(f"Output file: {summary['output_path']}")
        
        # Console output as specified in requirements
        print(f"\nEvent Summary:")
        print(f"cand={events['candidates']}, confirm={events['confirmations']}, rejected={events['rejections']}")
        
        # Verify output file
        if output_path.exists():
            print(f"\nOutput file verification:")
            print(f"  File exists: [OK]")
            print(f"  File size: {output_path.stat().st_size} bytes")
            
            # Check if it's a valid image by attempting to get file info
            try:
                import os
                file_size = os.path.getsize(output_path)
                if file_size > 0:
                    print(f"  Image file: [OK]")
                else:
                    print(f"  [WARNING] Image file is empty")
            except Exception as e:
                print(f"  [WARNING] Could not verify image file: {e}")
        else:
            print(f"\n[WARNING] Output file was not created")
        
        # Performance assessment
        print(f"\n" + "="*50)
        print("VISUALIZATION ASSESSMENT")
        print("="*50)
        
        if summary['price_data_points'] == 0:
            print("  [INFO] No price data found. Check CSV file format.")
        elif total_events == 0:
            print("  [INFO] No events found to plot. Check event files.")
        elif events['candidates'] == 0 and events['confirmations'] == 0:
            print("  [INFO] Only rejection events found. Consider:")
            print("    - Including candidate and confirmation files")
            print("    - Checking event file formats")
        else:
            print(f"  [SUCCESS] Plotted {total_events} events on {summary['price_data_points']} price points")
            
            if events['candidates'] > 0 and events['confirmations'] == 0:
                print("    - Only candidates found, no confirmations")
            elif events['confirmations'] > 0:
                confirmation_rate = events['confirmations'] / events['candidates'] if events['candidates'] > 0 else 0
                print(f"    - Confirmation rate: {confirmation_rate:.1%}")
            
            if summary['labels_count'] > 0:
                print(f"    - {summary['labels_count']} label spans overlaid")
        
        logger.info("Plot report generation completed successfully")
        print(f"\n[SUCCESS] Visual report completed!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Plot report generation failed: {e}")
        print(f"\n[ERROR] Plot report generation failed: {e}")
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())