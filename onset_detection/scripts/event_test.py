#!/usr/bin/env python3
"""CLI script for testing event store and logging functionality."""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.event_store import EventStore, create_event
from src.logger import setup_logging, get_logger
from src.config_loader import load_config


def main():
    """Main test function for event store and logging."""
    print("Event Store & Logging Test")
    print("=" * 50)
    
    # Setup logging
    logger_system = setup_logging()
    logger = get_logger("event_test")
    
    logger.info("Starting event store test")
    
    try:
        # Create event store
        store = EventStore()
        logger.info("EventStore initialized")
        
        # Clear existing events for clean test
        store.clear_events()
        logger.info("Cleared existing events")
        
        # Create sample events
        current_time = time.time()
        events_to_save = [
            create_event(
                timestamp=current_time,
                event_type="onset_candidate",
                stock_code="005930",
                score=2.3,
                extra={"spread": 0.05, "volume": 1000}
            ),
            create_event(
                timestamp=current_time + 5,
                event_type="onset_confirmed",
                stock_code="005930",
                score=3.1,
                extra={"spread": 0.03, "volume": 2500}
            ),
            create_event(
                timestamp=current_time + 10,
                event_type="onset_confirmed",
                stock_code="000660",
                score=2.8,
                extra={"spread": 0.04, "volume": 1800}
            ),
            create_event(
                timestamp=current_time + 60,
                event_type="refractory_enter",
                stock_code="005930",
                duration=120,
                reason="confirmed_onset_completed"
            ),
            create_event(
                timestamp=current_time + 65,
                event_type="refractory_enter",
                stock_code="000660",
                duration=90,
                reason="confirmed_onset_completed"
            )
        ]
        
        print(f"\nSaving {len(events_to_save)} sample events...")
        logger.info(f"Saving {len(events_to_save)} sample events")
        
        # Save events
        for i, event in enumerate(events_to_save, 1):
            success = store.save_event(event)
            print(f"  #{i}: {event['event_type']} ({event.get('stock_code')}) -> {'OK' if success else 'FAIL'}")
            
            if success:
                logger.info(f"Saved event: {event['event_type']} for {event.get('stock_code')} "
                           f"with score {event.get('score', 'N/A')}")
            else:
                logger.error(f"Failed to save event: {event['event_type']}")
        
        # Load and display all events
        print("\n" + "="*50)
        print("Loading all events from store:")
        print("="*50)
        
        loaded_events = store.load_events()
        logger.info(f"Loaded {len(loaded_events)} events from store")
        
        for i, event in enumerate(loaded_events, 1):
            event_time = datetime.fromtimestamp(event['ts']).strftime('%H:%M:%S')
            stock = event.get('stock_code', 'N/A')
            score = event.get('score', 'N/A')
            
            print(f"  #{i}: [{event_time}] {event['event_type']} - {stock} (score: {score})")
            
            # Show extra details if available
            if 'extra' in event:
                extra_str = ", ".join([f"{k}: {v}" for k, v in event['extra'].items()])
                print(f"      Extra: {extra_str}")
        
        # Test filtering
        print("\n" + "="*50)
        print("Testing event filtering:")
        print("="*50)
        
        # Filter by event type
        confirmed_events = store.load_events(event_type="onset_confirmed")
        print(f"\nConfirmed onsets: {len(confirmed_events)}")
        for event in confirmed_events:
            print(f"  - {event.get('stock_code')}: score {event.get('score')}")
        
        # Filter by time range
        time_filtered = store.load_events(
            start_time=current_time + 5,
            end_time=current_time + 60
        )
        print(f"\nEvents in middle time range: {len(time_filtered)}")
        for event in time_filtered:
            print(f"  - {event['event_type']} ({event.get('stock_code')})")
        
        # Test limit
        limited_events = store.load_events(limit=2)
        print(f"\nLimited to 2 events: {len(limited_events)}")
        
        # Show statistics
        print("\n" + "="*50)
        print("Event Store Statistics:")
        print("="*50)
        
        stats = store.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Show event type counts
        event_types = store.get_event_types()
        print(f"\nEvent type distribution:")
        for event_type, count in event_types.items():
            print(f"  {event_type}: {count}")
        
        # Show log files
        print("\n" + "="*50)
        print("Log Files:")
        print("="*50)
        
        log_files = logger_system.get_log_files()
        for log_file in log_files:
            print(f"  {log_file}")
            
            # Show last few lines of log file
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print(f"    Last {min(3, len(lines))} lines:")
                    for line in lines[-3:]:
                        print(f"      {line.rstrip()}")
            except Exception as e:
                print(f"    Error reading log file: {e}")
        
        logger.info("Event store test completed successfully")
        print(f"\n[SUCCESS] Test completed successfully!")
        print(f"   - Events saved to: {store.default_file}")
        print(f"   - Logs saved to: {logger_system.logs_dir}/app.log")
        
        return 0
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())