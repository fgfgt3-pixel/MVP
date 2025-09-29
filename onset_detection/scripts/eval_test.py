#!/usr/bin/env python3
"""CLI script for testing metrics evaluation functionality."""

import argparse
import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.event_store import EventStore
from src.metrics import MetricsCalculator
from src.logger import setup_logging, get_logger


def main():
    """Main evaluation test function."""
    parser = argparse.ArgumentParser(description="Evaluate onset detection performance")
    
    # Input options
    parser.add_argument("--events", type=str, help="Path to events JSONL file")
    parser.add_argument("--labels", type=str, help="Path to labels CSV file")
    parser.add_argument("--trading-hours", type=float, default=6.5, 
                       help="Trading hours for FP rate calculation (default: 6.5)")
    
    # Output options
    parser.add_argument("--output", type=str, help="Output JSON file path (default: reports/eval_summary.json)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger_system = setup_logging()
    logger = get_logger("eval_test")
    
    try:
        print("Onset Detection Evaluation Test")
        print("=" * 50)
        
        logger.info("Starting evaluation test")
        
        # Initialize components
        event_store = EventStore()
        calculator = MetricsCalculator()
        
        # Load events
        if args.events:
            print(f"Loading events from: {args.events}")
            logger.info(f"Loading events from: {args.events}")
            
            # Determine filename
            events_filename = Path(args.events).name if '/' in args.events or '\\' in args.events else args.events
            events = event_store.load_events(filename=events_filename)
        else:
            print("Loading events from default store...")
            logger.info("Loading events from default store")
            events = event_store.load_events()
        
        print(f"Loaded {len(events)} events")
        
        if args.verbose:
            event_types = {}
            for event in events:
                event_type = event.get('event_type', 'unknown')
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
            print("Event breakdown:")
            for event_type, count in event_types.items():
                print(f"  {event_type}: {count}")
        
        # Load labels
        if args.labels:
            labels_path = args.labels
        else:
            labels_path = "sample.csv"  # Default sample
        
        print(f"Loading labels from: {labels_path}")
        logger.info(f"Loading labels from: {labels_path}")
        
        labels_df = calculator.load_labels(labels_path)
        print(f"Loaded {len(labels_df)} label intervals")
        
        if args.verbose:
            print("Label intervals:")
            for idx, label in labels_df.iterrows():
                print(f"  {label['stock_code']}: {label['timestamp_start']} - {label['timestamp_end']} ({label['label_type']})")
        
        # Compute metrics
        print(f"\nComputing metrics (trading hours: {args.trading_hours})...")
        logger.info(f"Computing metrics with trading hours: {args.trading_hours}")
        
        metrics = calculator.compute_all_metrics(events, labels_df, args.trading_hours)
        
        # Display results
        print("\n" + "="*50)
        print("EVALUATION RESULTS")
        print("="*50)
        
        print(f"Overall Performance:")
        print(f"  Recall (In-window detection):  {metrics['recall']:.3f} ({metrics['n_detected']}/{metrics['n_labels']})")
        print(f"  False Positives per hour:      {metrics['fp_per_hour']:.3f} ({metrics['n_fp']} FP)")
        print(f"  Time-to-Alert p95:            {metrics['tta_p95']:.3f} seconds")
        print(f"  Time-to-Alert p50:            {metrics['tta_p50']:.3f} seconds")
        print(f"  Time-to-Alert mean:           {metrics['tta_mean']:.3f} seconds")
        
        print(f"\nEvent Statistics:")
        print(f"  Total events:                  {metrics['n_events']}")
        print(f"  Confirmed events:              {metrics['n_confirmed']}")
        print(f"  True positives:                {metrics['n_confirmed'] - metrics['n_fp']}")
        print(f"  False positives:               {metrics['n_fp']}")
        print(f"  Labels detected:               {metrics['n_detected']}")
        print(f"  TTA samples:                   {metrics['n_tta_samples']}")
        
        if args.verbose and metrics['event_counts']:
            print(f"\nEvent Type Breakdown:")
            for event_type, count in metrics['event_counts'].items():
                print(f"  {event_type}: {count}")
        
        # Save results
        output_path = args.output
        if output_path:
            output_path = Path(output_path)
        else:
            output_path = None
        
        report_path = calculator.save_metrics_report(metrics, output_path)
        print(f"\nResults saved to: {report_path}")
        logger.info(f"Evaluation report saved to: {report_path}")
        
        # Show JSON preview
        print(f"\nJSON Preview:")
        print("-" * 30)
        preview_metrics = {
            "recall": metrics["recall"],
            "fp_per_hour": metrics["fp_per_hour"], 
            "tta_p95": metrics["tta_p95"],
            "n_events": metrics["n_events"],
            "n_labels": metrics["n_labels"],
            "n_detected": metrics["n_detected"]
        }
        print(json.dumps(preview_metrics, indent=2))
        
        # Performance assessment
        print(f"\n" + "="*50)
        print("PERFORMANCE ASSESSMENT")
        print("="*50)
        
        # Simple performance thresholds (can be made configurable)
        recall_threshold = 0.8
        fp_threshold = 2.0
        tta_threshold = 5.0
        
        assessments = []
        
        if metrics["recall"] >= recall_threshold:
            assessments.append(f"✓ Good recall ({metrics['recall']:.3f} >= {recall_threshold})")
        else:
            assessments.append(f"✗ Low recall ({metrics['recall']:.3f} < {recall_threshold})")
        
        if metrics["fp_per_hour"] <= fp_threshold:
            assessments.append(f"✓ Acceptable FP rate ({metrics['fp_per_hour']:.3f} <= {fp_threshold}/h)")
        else:
            assessments.append(f"✗ High FP rate ({metrics['fp_per_hour']:.3f} > {fp_threshold}/h)")
        
        if metrics["tta_p95"] <= tta_threshold:
            assessments.append(f"✓ Fast detection ({metrics['tta_p95']:.3f}s <= {tta_threshold}s)")
        else:
            assessments.append(f"✗ Slow detection ({metrics['tta_p95']:.3f}s > {tta_threshold}s)")
        
        for assessment in assessments:
            # Remove unicode characters for Windows compatibility
            assessment = assessment.replace('✓', '[PASS]').replace('✗', '[FAIL]')
            print(f"  {assessment}")
        
        logger.info("Evaluation test completed successfully")
        print(f"\n[SUCCESS] Evaluation completed!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Evaluation test failed: {e}")
        print(f"\n[ERROR] Evaluation failed: {e}")
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())