"""Event store for managing onset detection events."""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import numpy as np

from .config_loader import Config, load_config
from .utils.paths import PathManager


class EventStore:
    """
    Event storage system using JSONL (JSON Lines) format.
    
    Stores events as one JSON object per line for efficient append operations
    and streaming processing.
    """
    
    def __init__(self, path: Optional[Union[str, Path]] = None, config: Optional[Config] = None):
        """
        Initialize event store.
        
        Args:
            path: Path to events directory. If None, uses config default.
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()
        self.path_manager = PathManager(self.config)
        
        if path is None:
            self.events_dir = self.path_manager.get_data_events_path()
        else:
            self.events_dir = self.path_manager.ensure_dir_exists(path)
        
        # Default event file
        self.default_file = self.events_dir / "events.jsonl"
        
        # Statistics
        self._stats = {
            'total_events': 0,
            'last_event_time': None,
            'event_types': {}
        }
    
    def save_event(
        self, 
        event: Dict[str, Any], 
        filename: Optional[str] = None,
        validate: bool = True
    ) -> bool:
        """
        Save event to JSONL file.
        
        Args:
            event: Event dictionary to save.
            filename: Optional filename. If None, uses default.
            validate: Whether to validate event structure.
            
        Returns:
            bool: True if saved successfully.
            
        Raises:
            ValueError: If event validation fails.
        """
        if validate:
            self._validate_event(event)
        
        # Add metadata if not present
        if 'saved_at' not in event:
            event = event.copy()
            event['saved_at'] = time.time()
        
        # Determine file path
        if filename is None:
            file_path = self.default_file
        else:
            file_path = self.events_dir / filename
        
        try:
            # Append to JSONL file
            with open(file_path, 'a', encoding='utf-8') as f:
                json.dump(event, f, default=str, separators=(',', ':'))
                f.write('\n')
            
            # Update statistics
            self._update_stats(event)
            
            return True
            
        except Exception as e:
            print(f"Error saving event: {e}")
            return False
    
    def load_events(
        self, 
        filename: Optional[str] = None,
        limit: Optional[int] = None,
        event_type: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Load events from JSONL file.
        
        Args:
            filename: Optional filename. If None, uses default.
            limit: Maximum number of events to load.
            event_type: Filter by event type.
            start_time: Filter events after this timestamp.
            end_time: Filter events before this timestamp.
            
        Returns:
            List[Dict[str, Any]]: List of event dictionaries.
        """
        # Determine file path
        if filename is None:
            file_path = self.default_file
        else:
            file_path = self.events_dir / filename
        
        if not file_path.exists():
            return []
        
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        event = json.loads(line)
                        
                        # Apply filters
                        if not self._event_matches_filters(event, event_type, start_time, end_time):
                            continue
                        
                        events.append(event)
                        
                        # Apply limit
                        if limit is not None and len(events) >= limit:
                            break
                            
                    except json.JSONDecodeError as e:
                        print(f"Warning: Invalid JSON on line {line_num}: {e}")
                        continue
                        
        except Exception as e:
            print(f"Error loading events: {e}")
            return []
        
        return events
    
    def _validate_event(self, event: Dict[str, Any]) -> None:
        """
        Validate event structure.
        
        Args:
            event: Event to validate.
            
        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(event, dict):
            raise ValueError("Event must be a dictionary")
        
        # Required fields
        required_fields = ['ts', 'event_type']
        missing_fields = [field for field in required_fields if field not in event]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Validate timestamp
        if not isinstance(event['ts'], (int, float, np.integer, np.floating)):
            raise ValueError("Timestamp 'ts' must be numeric (Unix timestamp)")
        
        # Validate event type
        if not isinstance(event['event_type'], str):
            raise ValueError("Event type must be a string")
    
    def _event_matches_filters(
        self,
        event: Dict[str, Any],
        event_type: Optional[str],
        start_time: Optional[float],
        end_time: Optional[float]
    ) -> bool:
        """Check if event matches the given filters."""
        # Event type filter
        if event_type is not None and event.get('event_type') != event_type:
            return False
        
        # Time filters
        event_time = event.get('ts', 0)
        if start_time is not None and event_time < start_time:
            return False
        if end_time is not None and event_time > end_time:
            return False
        
        return True
    
    def _update_stats(self, event: Dict[str, Any]) -> None:
        """Update internal statistics."""
        self._stats['total_events'] += 1
        self._stats['last_event_time'] = time.time()
        
        event_type = event.get('event_type', 'unknown')
        if event_type in self._stats['event_types']:
            self._stats['event_types'][event_type] += 1
        else:
            self._stats['event_types'][event_type] = 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get event store statistics.
        
        Returns:
            Dict[str, Any]: Statistics dictionary.
        """
        # Count events in default file
        if self.default_file.exists():
            try:
                with open(self.default_file, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for line in f if line.strip())
                self._stats['file_event_count'] = line_count
            except Exception:
                self._stats['file_event_count'] = 0
        else:
            self._stats['file_event_count'] = 0
        
        return self._stats.copy()
    
    def clear_events(self, filename: Optional[str] = None) -> bool:
        """
        Clear all events from file.
        
        Args:
            filename: Optional filename. If None, uses default.
            
        Returns:
            bool: True if cleared successfully.
        """
        if filename is None:
            file_path = self.default_file
        else:
            file_path = self.events_dir / filename
        
        try:
            if file_path.exists():
                file_path.unlink()
            
            # Reset stats
            self._stats = {
                'total_events': 0,
                'last_event_time': None,
                'event_types': {}
            }
            
            return True
            
        except Exception as e:
            print(f"Error clearing events: {e}")
            return False
    
    def list_event_files(self) -> List[str]:
        """
        List all JSONL event files in the events directory.
        
        Returns:
            List[str]: List of filenames.
        """
        if not self.events_dir.exists():
            return []
        
        jsonl_files = []
        for file_path in self.events_dir.glob("*.jsonl"):
            jsonl_files.append(file_path.name)
        
        return sorted(jsonl_files)
    
    def get_event_types(self, filename: Optional[str] = None) -> Dict[str, int]:
        """
        Get count of each event type.
        
        Args:
            filename: Optional filename. If None, uses default.
            
        Returns:
            Dict[str, int]: Event type counts.
        """
        events = self.load_events(filename)
        event_type_counts = {}
        
        for event in events:
            event_type = event.get('event_type', 'unknown')
            if event_type in event_type_counts:
                event_type_counts[event_type] += 1
            else:
                event_type_counts[event_type] = 1
        
        return event_type_counts


def create_event(
    timestamp: Union[int, float, datetime],
    event_type: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Create an event dictionary with standard structure.
    
    Args:
        timestamp: Event timestamp (Unix timestamp or datetime).
        event_type: Type of event.
        **kwargs: Additional event fields.
        
    Returns:
        Dict[str, Any]: Event dictionary.
    """
    # Convert datetime to timestamp if needed
    if isinstance(timestamp, datetime):
        timestamp = timestamp.timestamp()
    elif hasattr(timestamp, 'timestamp'):  # pandas Timestamp
        timestamp = timestamp.timestamp()
    elif hasattr(timestamp, 'to_pydatetime'):  # pandas datetime64
        timestamp = timestamp.to_pydatetime().timestamp()

    # Convert to milliseconds for consistency
    if isinstance(timestamp, (int, float)):
        timestamp = int(timestamp * 1000)

    event = {
        'ts': timestamp,
        'event_type': event_type,
        **kwargs
    }
    
    return event


if __name__ == "__main__":
    # Demo/test the event store
    print("Event Store Demo")
    print("=" * 40)
    
    # Create event store
    store = EventStore()
    
    # Create and save sample events
    events_to_save = [
        create_event(time.time(), "onset_candidate", stock_code="005930", score=2.3, extra={"spread": 0.05}),
        create_event(time.time() + 1, "onset_confirmed", stock_code="005930", score=3.1, extra={"spread": 0.03}),
        create_event(time.time() + 2, "refractory_enter", stock_code="005930", duration=120)
    ]
    
    print(f"Saving {len(events_to_save)} sample events...")
    for event in events_to_save:
        success = store.save_event(event)
        print(f"  Saved event: {event['event_type']} -> {success}")
    
    # Load and display events
    print("\nLoading events from store:")
    loaded_events = store.load_events(limit=10)
    for i, event in enumerate(loaded_events, 1):
        print(f"  #{i}: {event['event_type']} at {event['ts']} ({event.get('stock_code', 'N/A')})")
    
    # Show statistics
    print("\nEvent Store Statistics:")
    stats = store.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print(f"\nEvent files: {store.list_event_files()}")
    print(f"Event types: {store.get_event_types()}")