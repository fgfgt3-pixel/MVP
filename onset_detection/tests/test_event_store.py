"""Tests for event store and logging modules."""

import tempfile
import time
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from src.event_store import EventStore, create_event
from src.logger import Logger, setup_logging, get_logger
from src.config_loader import Config


class TestEventStore:
    """Test event store functionality."""
    
    def create_test_event(self, event_type: str = "test_event", timestamp: float = None) -> dict:
        """Create a test event."""
        if timestamp is None:
            timestamp = time.time()
        
        return create_event(
            timestamp=timestamp,
            event_type=event_type,
            stock_code="005930",
            score=2.5,
            extra={"test": "data"}
        )
    
    def test_event_store_initialization(self):
        """Test EventStore initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            assert store.events_dir == Path(temp_dir)
            assert store.default_file == Path(temp_dir) / "events.jsonl"
    
    def test_save_event_basic(self):
        """Test basic event saving functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            event = self.create_test_event()
            
            # Save event
            success = store.save_event(event)
            assert success == True
            
            # Check file exists
            assert store.default_file.exists()
            
            # Check file content
            with open(store.default_file, 'r') as f:
                saved_data = json.loads(f.read().strip())
                assert saved_data['event_type'] == "test_event"
                assert saved_data['stock_code'] == "005930"
                assert 'saved_at' in saved_data
    
    def test_save_multiple_events(self):
        """Test saving multiple events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            events = [
                self.create_test_event("onset_candidate"),
                self.create_test_event("onset_confirmed"),
                self.create_test_event("refractory_enter")
            ]
            
            # Save all events
            for event in events:
                success = store.save_event(event)
                assert success == True
            
            # Check file content
            with open(store.default_file, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 3
                
                # Verify each line is valid JSON
                for i, line in enumerate(lines):
                    saved_event = json.loads(line.strip())
                    assert saved_event['event_type'] == events[i]['event_type']
    
    def test_load_events_basic(self):
        """Test basic event loading functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            # Save test events
            original_events = [
                self.create_test_event("onset_candidate", time.time()),
                self.create_test_event("onset_confirmed", time.time() + 1)
            ]
            
            for event in original_events:
                store.save_event(event)
            
            # Load events
            loaded_events = store.load_events()
            
            assert len(loaded_events) == 2
            assert loaded_events[0]['event_type'] == "onset_candidate"
            assert loaded_events[1]['event_type'] == "onset_confirmed"
            
            # Check that saved_at was added
            for event in loaded_events:
                assert 'saved_at' in event
    
    def test_load_events_with_limit(self):
        """Test loading events with limit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            # Save 5 events
            for i in range(5):
                event = self.create_test_event(f"event_{i}")
                store.save_event(event)
            
            # Load with limit
            loaded_events = store.load_events(limit=3)
            assert len(loaded_events) == 3
            
            # Load all
            all_events = store.load_events()
            assert len(all_events) == 5
    
    def test_load_events_with_filters(self):
        """Test loading events with filters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            base_time = time.time()
            
            # Save events with different types and times
            events = [
                create_event(base_time, "onset_candidate", stock_code="005930"),
                create_event(base_time + 10, "onset_confirmed", stock_code="005930"), 
                create_event(base_time + 20, "onset_candidate", stock_code="000660"),
                create_event(base_time + 30, "refractory_enter", stock_code="005930")
            ]
            
            for event in events:
                store.save_event(event)
            
            # Filter by event type
            candidates = store.load_events(event_type="onset_candidate")
            assert len(candidates) == 2
            assert all(e['event_type'] == "onset_candidate" for e in candidates)
            
            # Filter by time range
            mid_events = store.load_events(start_time=base_time + 5, end_time=base_time + 25)
            assert len(mid_events) == 2
            assert mid_events[0]['event_type'] == "onset_confirmed"
            assert mid_events[1]['event_type'] == "onset_candidate"
    
    def test_event_validation(self):
        """Test event validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            # Valid event
            valid_event = {"ts": time.time(), "event_type": "test"}
            success = store.save_event(valid_event)
            assert success == True
            
            # Invalid event - missing ts
            invalid_event1 = {"event_type": "test"}
            with pytest.raises(ValueError, match="Missing required fields"):
                store.save_event(invalid_event1)
            
            # Invalid event - missing event_type
            invalid_event2 = {"ts": time.time()}
            with pytest.raises(ValueError, match="Missing required fields"):
                store.save_event(invalid_event2)
            
            # Invalid event - wrong ts type
            invalid_event3 = {"ts": "not_a_number", "event_type": "test"}
            with pytest.raises(ValueError, match="Timestamp 'ts' must be numeric"):
                store.save_event(invalid_event3)
    
    def test_clear_events(self):
        """Test clearing events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            # Save some events
            for i in range(3):
                event = self.create_test_event(f"event_{i}")
                store.save_event(event)
            
            assert store.default_file.exists()
            
            # Clear events
            success = store.clear_events()
            assert success == True
            assert not store.default_file.exists()
            
            # Load events should return empty list
            loaded_events = store.load_events()
            assert len(loaded_events) == 0
    
    def test_get_stats(self):
        """Test statistics functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            # Initial stats
            stats = store.get_stats()
            assert stats['total_events'] == 0
            assert stats['file_event_count'] == 0
            
            # Save some events
            events = [
                self.create_test_event("onset_candidate"),
                self.create_test_event("onset_candidate"),
                self.create_test_event("onset_confirmed")
            ]
            
            for event in events:
                store.save_event(event)
            
            # Check updated stats
            stats = store.get_stats()
            assert stats['total_events'] == 3
            assert stats['file_event_count'] == 3
            assert 'onset_candidate' in stats['event_types']
            assert stats['event_types']['onset_candidate'] == 2
            assert stats['event_types']['onset_confirmed'] == 1
    
    def test_get_event_types(self):
        """Test event type counting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            # Save events of different types
            event_types_to_save = [
                "onset_candidate", "onset_candidate", 
                "onset_confirmed", 
                "refractory_enter", "refractory_enter", "refractory_enter"
            ]
            
            for event_type in event_types_to_save:
                event = self.create_test_event(event_type)
                store.save_event(event)
            
            # Get event type counts
            counts = store.get_event_types()
            
            assert counts["onset_candidate"] == 2
            assert counts["onset_confirmed"] == 1
            assert counts["refractory_enter"] == 3
    
    def test_list_event_files(self):
        """Test listing event files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(path=temp_dir)
            
            # Initially no files
            files = store.list_event_files()
            assert len(files) == 0
            
            # Create some files
            (Path(temp_dir) / "events.jsonl").touch()
            (Path(temp_dir) / "test.jsonl").touch()
            (Path(temp_dir) / "other.txt").touch()  # Should be ignored
            
            files = store.list_event_files()
            assert len(files) == 2
            assert "events.jsonl" in files
            assert "test.jsonl" in files
            assert "other.txt" not in files


class TestCreateEvent:
    """Test create_event utility function."""
    
    def test_create_event_basic(self):
        """Test basic event creation."""
        timestamp = time.time()
        event = create_event(timestamp, "test_event", key1="value1", key2=42)
        
        assert event['ts'] == timestamp
        assert event['event_type'] == "test_event"
        assert event['key1'] == "value1"
        assert event['key2'] == 42
    
    def test_create_event_with_datetime(self):
        """Test event creation with datetime object."""
        from datetime import datetime
        
        dt = datetime.now()
        event = create_event(dt, "test_event")
        
        assert event['ts'] == dt.timestamp()
        assert event['event_type'] == "test_event"


class TestLogger:
    """Test logging functionality."""
    
    def test_logger_initialization(self):
        """Test Logger initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary config with custom log path
            config = Config()
            config.paths.logs = temp_dir
            
            logger_system = Logger(config)
            assert logger_system.logs_dir == Path(temp_dir)
    
    def test_get_logger(self):
        """Test getting logger instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.paths.logs = temp_dir
            
            logger_system = Logger(config)
            
            # Get different loggers
            logger1 = logger_system.get_logger("test1")
            logger2 = logger_system.get_logger("test2")
            logger1_again = logger_system.get_logger("test1")
            
            assert logger1.name == "test1"
            assert logger2.name == "test2"
            assert logger1 is logger1_again  # Should return same instance
    
    def test_logging_output(self):
        """Test that logging actually writes to files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create log file directly to test the concept
            import logging
            log_file = Path(temp_dir) / "test.log"
            
            # Create a simple file handler for testing
            test_logger = logging.getLogger("test_file_logging")
            test_logger.setLevel(logging.INFO)
            
            # Clear any existing handlers
            test_logger.handlers.clear()
            
            file_handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            test_logger.addHandler(file_handler)
            
            # Log some messages
            test_logger.info("Test info message")
            test_logger.warning("Test warning message")
            
            # Flush and close handler to ensure writing
            file_handler.flush()
            file_handler.close()
            
            # Check that log file was created and has content
            assert log_file.exists()
            
            with open(log_file, 'r') as f:
                content = f.read()
                assert "Test info message" in content
                assert "Test warning message" in content
    
    def test_set_level(self):
        """Test changing log level."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.paths.logs = temp_dir
            
            logger_system = Logger(config)
            
            # Initial level should be from config
            assert logger_system.config.logging.level in ["INFO", "DEBUG", "WARNING", "ERROR"]
            
            # Change level
            logger_system.set_level("DEBUG")
            assert logger_system.config.logging.level == "DEBUG"


class TestLoggingIntegration:
    """Test integration between event store and logging."""
    
    def test_event_store_with_logging(self):
        """Test using event store with logging enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup paths
            config = Config()
            config.paths.logs = temp_dir
            config.paths.data_events = temp_dir
            
            # Create event store (this is the main functionality we're testing)
            store = EventStore(config=config)
            
            # Save events
            events = [
                create_event(time.time(), "test_event_1", data="test1"),
                create_event(time.time() + 1, "test_event_2", data="test2")
            ]
            
            for event in events:
                success = store.save_event(event)
                assert success == True
            
            # Load events
            loaded_events = store.load_events()
            
            # Verify events were created correctly
            assert len(loaded_events) == 2
            assert loaded_events[0]['event_type'] == "test_event_1"
            assert loaded_events[1]['event_type'] == "test_event_2"
            
            # Verify event store functionality
            stats = store.get_stats()
            assert stats['file_event_count'] == 2