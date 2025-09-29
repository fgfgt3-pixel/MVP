"""Refractory manager for preventing duplicate onset detections."""

import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from ..config_loader import Config, load_config
from ..event_store import EventStore, create_event


class RefractoryManager:
    """
    Manage refractory periods to prevent duplicate onset detections.
    
    Implements a cooldown mechanism where new candidates are blocked
    for a specified duration after a confirmation occurs.
    """
    
    def __init__(self, config: Optional[Config] = None, event_store: Optional[EventStore] = None):
        """
        Initialize refractory manager.
        
        Args:
            config: Configuration object. If None, loads default config.
            event_store: EventStore instance. If None, creates default one.
        """
        self.config = config or load_config()
        self.event_store = event_store or EventStore()
        
        # Extract refractory parameters
        self.duration_s = self.config.refractory.duration_s
        self.extend_on_confirm = self.config.refractory.extend_on_confirm
        
        # Track last confirmation timestamp per stock
        self.last_confirm_ts: Dict[str, float] = {}
    
    def allow_candidate(self, event_ts: float, stock_code: str) -> bool:
        """
        Check if a candidate event should be allowed based on refractory period.
        
        Args:
            event_ts: Timestamp of the candidate event (milliseconds).
            stock_code: Stock code for the event.
        
        Returns:
            bool: True if candidate is allowed, False if in refractory period.
        """
        if stock_code not in self.last_confirm_ts:
            # No previous confirmation for this stock
            return True
        
        last_confirm = self.last_confirm_ts[stock_code]
        refractory_end = last_confirm + (self.duration_s * 1000)  # Convert to milliseconds
        
        # Allow if current time is past refractory period
        return event_ts >= refractory_end
    
    def update_confirm(self, event_ts: float, stock_code: str) -> None:
        """
        Update the last confirmation timestamp for a stock.
        
        Args:
            event_ts: Timestamp of the confirmation event (milliseconds).
            stock_code: Stock code for the event.
        """
        if self.extend_on_confirm or stock_code not in self.last_confirm_ts:
            # Update if extending on confirm OR if no previous record
            self.last_confirm_ts[stock_code] = event_ts
    
    def get_refractory_status(self, stock_code: str, current_ts: Optional[float] = None) -> Dict[str, Any]:
        """
        Get refractory status for a stock.
        
        Args:
            stock_code: Stock code to check.
            current_ts: Current timestamp. If None, uses latest known timestamp.
        
        Returns:
            Dict: Refractory status information.
        """
        if stock_code not in self.last_confirm_ts:
            return {
                "is_refractory": False,
                "last_confirm_ts": None,
                "refractory_end_ts": None,
                "remaining_seconds": 0
            }
        
        last_confirm = self.last_confirm_ts[stock_code]
        refractory_end = last_confirm + (self.duration_s * 1000)
        
        if current_ts is None:
            # Use the last confirmation timestamp as reference
            current_ts = last_confirm
        
        is_refractory = current_ts < refractory_end
        remaining_ms = max(0, refractory_end - current_ts)
        remaining_seconds = remaining_ms / 1000.0
        
        return {
            "is_refractory": is_refractory,
            "last_confirm_ts": last_confirm,
            "refractory_end_ts": refractory_end,
            "remaining_seconds": remaining_seconds
        }
    
    def process_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a list of events applying refractory logic.
        
        Args:
            events: List of events (candidates and confirmations) in chronological order.
        
        Returns:
            List[Dict]: Processed events with rejected candidates converted to refractory events.
        """
        processed_events = []
        
        # Sort events by timestamp to ensure proper chronological processing
        sorted_events = sorted(events, key=lambda x: x.get('ts', 0))
        
        for event in sorted_events:
            event_type = event.get('event_type', '')
            event_ts = event.get('ts', 0)
            stock_code = str(event.get('stock_code', ''))
            
            if event_type == 'onset_candidate':
                if self.allow_candidate(event_ts, stock_code):
                    # Candidate allowed - keep original event
                    processed_events.append(event)
                else:
                    # Candidate rejected - create refractory rejection event
                    refractory_event = create_event(
                        timestamp=event_ts,
                        event_type="onset_rejected_refractory",
                        stock_code=stock_code,
                        rejected_at=event_ts,
                        original_score=event.get('score', 0),
                        refractory_info=self.get_refractory_status(stock_code, event_ts),
                        original_evidence=event.get('evidence', {})
                    )
                    processed_events.append(refractory_event)
            
            elif event_type == 'onset_confirmed':
                # Process confirmation - update refractory state
                self.update_confirm(event_ts, stock_code)
                processed_events.append(event)
            
            else:
                # Other event types pass through unchanged
                processed_events.append(event)
        
        return processed_events
    
    def save_processed_events(
        self, 
        processed_events: List[Dict[str, Any]], 
        filename: Optional[str] = None
    ) -> bool:
        """
        Save processed events to EventStore.
        
        Args:
            processed_events: List of processed events.
            filename: Optional filename for saving events.
        
        Returns:
            bool: True if all events saved successfully.
        """
        if not processed_events:
            return True
        
        success_count = 0
        for event in processed_events:
            if self.event_store.save_event(event, filename=filename):
                success_count += 1
        
        return success_count == len(processed_events)
    
    def process_and_save(
        self, 
        events: List[Dict[str, Any]], 
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process events and save them in one operation.
        
        Args:
            events: List of events to process.
            filename: Optional filename for saving events.
        
        Returns:
            Dict: Summary with processing statistics.
        """
        processed_events = self.process_events(events)
        
        if processed_events:
            save_success = self.save_processed_events(processed_events, filename)
        else:
            save_success = True
        
        # Calculate statistics
        original_candidates = sum(1 for e in events if e.get('event_type') == 'onset_candidate')
        original_confirmations = sum(1 for e in events if e.get('event_type') == 'onset_confirmed')
        
        allowed_candidates = sum(1 for e in processed_events if e.get('event_type') == 'onset_candidate')
        rejected_candidates = sum(1 for e in processed_events if e.get('event_type') == 'onset_rejected_refractory')
        final_confirmations = sum(1 for e in processed_events if e.get('event_type') == 'onset_confirmed')
        
        rejection_rate = rejected_candidates / original_candidates if original_candidates > 0 else 0.0
        
        return {
            "events_processed": len(events),
            "events_output": len(processed_events),
            "original_candidates": original_candidates,
            "original_confirmations": original_confirmations,
            "allowed_candidates": allowed_candidates,
            "rejected_candidates": rejected_candidates,
            "final_confirmations": final_confirmations,
            "rejection_rate": rejection_rate,
            "save_success": save_success,
            "processed_events": processed_events
        }
    
    def get_refractory_stats(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get refractory statistics without saving events.
        
        Args:
            events: List of events to analyze.
        
        Returns:
            Dict: Refractory processing statistics.
        """
        if not events:
            return {
                "total_events": 0,
                "candidates_processed": 0,
                "candidates_allowed": 0,
                "candidates_rejected": 0,
                "rejection_rate": 0.0,
                "stocks_tracked": 0,
                "config": {
                    "duration_s": self.duration_s,
                    "extend_on_confirm": self.extend_on_confirm
                }
            }
        
        processed_events = self.process_events(events)
        
        candidates_processed = sum(1 for e in events if e.get('event_type') == 'onset_candidate')
        candidates_allowed = sum(1 for e in processed_events if e.get('event_type') == 'onset_candidate')
        candidates_rejected = sum(1 for e in processed_events if e.get('event_type') == 'onset_rejected_refractory')
        
        rejection_rate = candidates_rejected / candidates_processed if candidates_processed > 0 else 0.0
        
        return {
            "total_events": len(events),
            "candidates_processed": candidates_processed,
            "candidates_allowed": candidates_allowed,
            "candidates_rejected": candidates_rejected,
            "rejection_rate": rejection_rate,
            "stocks_tracked": len(self.last_confirm_ts),
            "config": {
                "duration_s": self.duration_s,
                "extend_on_confirm": self.extend_on_confirm
            }
        }
    
    def reset_refractory_state(self) -> None:
        """Reset all refractory state (for testing or new sessions)."""
        self.last_confirm_ts.clear()


def process_refractory_events(
    events: List[Dict[str, Any]], 
    config: Optional[Config] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to process events with refractory logic.
    
    Args:
        events: List of events to process.
        config: Optional configuration object.
    
    Returns:
        List[Dict]: Processed events with refractory logic applied.
    """
    manager = RefractoryManager(config)
    return manager.process_events(events)


if __name__ == "__main__":
    # Demo/test the refractory manager
    import time
    
    print("Refractory Manager Demo")
    print("=" * 40)
    
    # Create sample events with close timing
    base_time = 1704067200000
    sample_events = [
        # First candidate and confirmation
        {
            'ts': base_time,
            'event_type': 'onset_candidate',
            'stock_code': '005930',
            'score': 2.5
        },
        {
            'ts': base_time + 5000,  # 5 seconds later
            'event_type': 'onset_confirmed',
            'stock_code': '005930',
            'confirmed_from': base_time
        },
        # Second candidate during refractory period (should be blocked)
        {
            'ts': base_time + 30000,  # 30 seconds after confirmation (within 120s refractory)
            'event_type': 'onset_candidate',
            'stock_code': '005930',
            'score': 2.8
        },
        # Third candidate after refractory period (should be allowed)
        {
            'ts': base_time + 130000,  # 130 seconds after confirmation (past 120s refractory)
            'event_type': 'onset_candidate',
            'stock_code': '005930',
            'score': 3.0
        }
    ]
    
    print(f"Sample events: {len(sample_events)}")
    
    # Process events
    manager = RefractoryManager()
    processed_events = manager.process_events(sample_events)
    
    print(f"Processed events: {len(processed_events)}")
    
    # Show results
    for event in processed_events:
        event_type = event['event_type']
        timestamp = event['ts']
        print(f"  {event_type} at {timestamp}")
        
        if event_type == 'onset_rejected_refractory':
            remaining = event.get('refractory_info', {}).get('remaining_seconds', 0)
            print(f"    (rejected, {remaining:.1f}s remaining in refractory)")
    
    # Get statistics
    stats = manager.get_refractory_stats(sample_events)
    print(f"\nRefractory Statistics:")
    print(f"  Candidates processed: {stats['candidates_processed']}")
    print(f"  Candidates allowed: {stats['candidates_allowed']}")
    print(f"  Candidates rejected: {stats['candidates_rejected']}")
    print(f"  Rejection rate: {stats['rejection_rate']:.1%}")