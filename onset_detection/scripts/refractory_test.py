#!/usr/bin/env python3
"""CLI script for testing refractory period management functionality."""

import argparse
import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.detection import RefractoryManager
from src.logger import setup_logging, get_logger


def load_events_from_jsonl(jsonl_file: Path) -> list:
    """Load events from JSONL file."""
    events = []
    
    if not jsonl_file.exists():
        raise FileNotFoundError(f"Events file not found: {jsonl_file}")
    
    with open(jsonl_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse line: {line[:50]}...")
                    continue
    
    return events


def save_events_to_jsonl(events: list, output_file: Path) -> None:
    """Save events to JSONL file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        for event in events:
            json.dump(event, f, ensure_ascii=False)
            f.write('\n')


def main():
    """Main refractory test function."""
    parser = argparse.ArgumentParser(description="Apply refractory period logic to onset events")
    
    # Input options
    parser.add_argument("--cands", type=str, required=True, help="Path to candidates JSONL file")
    parser.add_argument("--confirms", type=str, required=True, help="Path to confirmations JSONL file")
    parser.add_argument("--out", type=str, required=True, help="Output processed events JSONL file path")
    
    # Refractory options
    parser.add_argument("--duration", type=int, help="Override refractory duration (seconds)")
    parser.add_argument("--extend-on-confirm", action="store_true", help="Extend refractory on new confirmation")
    parser.add_argument("--no-extend-on-confirm", action="store_true", help="Don't extend refractory on new confirmation")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger_system = setup_logging()
    logger = get_logger("refractory_test")
    
    try:
        print("Onset Refractory Period Test")
        print("=" * 50)
        
        logger.info("Starting refractory test")
        
        # Load candidate events
        print(f"Loading candidates from: {args.cands}")
        logger.info(f"Loading candidates from: {args.cands}")
        
        candidates_path = Path(args.cands)
        candidate_events = load_events_from_jsonl(candidates_path)
        print(f"Loaded {len(candidate_events)} candidate events")
        
        # Load confirmation events
        print(f"Loading confirmations from: {args.confirms}")
        logger.info(f"Loading confirmations from: {args.confirms}")
        
        confirms_path = Path(args.confirms)
        confirm_events = load_events_from_jsonl(confirms_path)
        print(f"Loaded {len(confirm_events)} confirmation events")
        
        # Combine and sort all events by timestamp
        all_events = candidate_events + confirm_events
        all_events = sorted(all_events, key=lambda x: x.get('ts', 0))
        
        print(f"Total events to process: {len(all_events)}")
        
        if args.verbose:
            print("Sample events (first 5):")
            for i, event in enumerate(all_events[:5]):
                event_type = event.get('event_type', 'unknown')
                timestamp = event.get('ts', 0)
                stock_code = event.get('stock_code', 'N/A')
                print(f"  {i+1}. {event_type} at {timestamp}, Stock: {stock_code}")
        
        # Initialize refractory manager
        print(f"\nInitializing refractory manager...")
        logger.info("Initializing refractory manager")
        
        manager = RefractoryManager()
        
        # Override refractory parameters if provided
        if args.duration is not None:
            manager.duration_s = args.duration
            print(f"Overriding refractory duration to: {args.duration}s")
        
        if args.extend_on_confirm:
            manager.extend_on_confirm = True
            print(f"Setting extend_on_confirm to: True")
        elif args.no_extend_on_confirm:
            manager.extend_on_confirm = False
            print(f"Setting extend_on_confirm to: False")
        
        print(f"Refractory parameters:")
        print(f"  Duration: {manager.duration_s}s")
        print(f"  Extend on confirm: {manager.extend_on_confirm}")
        
        # Get refractory statistics first
        print(f"\nAnalyzing refractory impact...")
        logger.info("Getting refractory statistics")
        
        stats = manager.get_refractory_stats(all_events)
        
        print(f"Refractory Analysis:")
        print(f"  Total events: {stats['total_events']}")
        print(f"  Candidates processed: {stats['candidates_processed']}")
        print(f"  Candidates allowed: {stats['candidates_allowed']}")
        print(f"  Candidates rejected: {stats['candidates_rejected']}")
        print(f"  Rejection rate: {stats['rejection_rate']:.2%}")
        print(f"  Stocks tracked: {stats['stocks_tracked']}")
        
        # Process and save events
        print(f"\nProcessing events with refractory logic...")
        logger.info("Processing and saving events")
        
        # Extract filename for EventStore
        output_path = Path(args.out)
        output_filename = output_path.name
        
        result = manager.process_and_save(all_events, filename=output_filename)
        
        processed_count = result["events_processed"]
        output_count = result["events_output"]
        save_success = result["save_success"]
        processed_events = result["processed_events"]
        
        print(f"\n" + "="*50)
        print("REFRACTORY PROCESSING RESULTS")
        print("="*50)
        
        print(f"Events processed: {processed_count}")
        print(f"Events output: {output_count}")
        print(f"Original candidates: {result['original_candidates']}")
        print(f"Original confirmations: {result['original_confirmations']}")
        print(f"Allowed candidates: {result['allowed_candidates']}")
        print(f"Rejected candidates: {result['rejected_candidates']}")
        print(f"Final confirmations: {result['final_confirmations']}")
        print(f"Rejection rate: {result['rejection_rate']:.2%}")
        print(f"Save successful: {save_success}")
        print(f"Output file: {output_path.absolute()}")
        
        # Show sample processed events
        if processed_events and args.verbose:
            print(f"\nSample processed events (first 10):")
            for i, event in enumerate(processed_events[:10]):
                event_type = event.get('event_type', 'unknown')
                timestamp = event.get('ts', 0)
                stock_code = event.get('stock_code', 'N/A')
                print(f"  {i+1}. {event_type} at {timestamp}, Stock: {stock_code}")
                
                if event_type == 'onset_rejected_refractory':
                    refractory_info = event.get('refractory_info', {})
                    remaining = refractory_info.get('remaining_seconds', 0)
                    print(f"       Rejected - {remaining:.1f}s remaining in refractory")
        
        # Save to separate JSONL file as well
        if processed_events:
            save_events_to_jsonl(processed_events, output_path)
            print(f"\nEvents also saved to: {output_path}")
        
        # Verify output file
        if output_path.exists():
            print(f"\nOutput file verification:")
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
            print(f"\n[WARNING] Output file was not created")
        
        # Performance assessment
        print(f"\n" + "="*50)
        print("PERFORMANCE ASSESSMENT")
        print("="*50)
        
        rejection_rate = result['rejection_rate']
        
        if rejection_rate == 0:
            print("  [INFO] No candidates rejected. This could mean:")
            print("    - No overlapping events within refractory periods")
            print("    - Refractory duration too short")
            print("    - Events are well-spaced naturally")
        elif rejection_rate < 0.1:
            print(f"  [SUCCESS] Low rejection rate ({rejection_rate:.1%}) - good event spacing")
        elif rejection_rate > 0.5:
            print(f"  [INFO] High rejection rate ({rejection_rate:.1%}). Consider:")
            print("    - Shortening refractory duration")
            print("    - Reviewing candidate detection sensitivity")
        else:
            print(f"  [SUCCESS] Reasonable rejection rate ({rejection_rate:.1%})")
        
        if result['rejected_candidates'] > 0:
            # Get stocks tracked from the manager
            stocks_tracked = len(manager.last_confirm_ts)
            if stocks_tracked > 0:
                avg_refractory_per_stock = result['rejected_candidates'] / stocks_tracked
                print(f"  Average rejections per stock: {avg_refractory_per_stock:.1f}")
        
        logger.info("Refractory test completed successfully")
        print(f"\n[SUCCESS] Refractory processing completed!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Refractory test failed: {e}")
        print(f"\n[ERROR] Refractory processing failed: {e}")
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())