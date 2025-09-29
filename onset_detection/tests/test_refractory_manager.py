"""Tests for refractory period management functionality."""

import tempfile
from pathlib import Path
import pytest
import json

from src.detection import RefractoryManager, process_refractory_events
from src.config_loader import Config
from src.event_store import EventStore


class TestRefractoryManager:
    """Test refractory period management functionality."""
    
    def create_sample_events(self, base_ts: int = 1704067200000, stock_code: str = '005930') -> list:
        """Create sample events for testing."""
        return [
            # First candidate and confirmation
            {
                'ts': base_ts,
                'event_type': 'onset_candidate',
                'stock_code': stock_code,
                'score': 2.5,
                'evidence': {
                    'ret_1s': 0.005,
                    'z_vol_1s': 2.8,
                    'ticks_per_sec': 3
                }
            },
            {
                'ts': base_ts + 5000,  # 5 seconds later
                'event_type': 'onset_confirmed',
                'stock_code': stock_code,
                'confirmed_from': base_ts,
                'evidence': {
                    'axes': ['price', 'volume'],
                    'ret_1s': 0.006,
                    'z_vol_1s': 3.0
                }
            },
            # Second candidate during refractory period (should be blocked)
            {
                'ts': base_ts + 30000,  # 30 seconds after confirmation (within 120s refractory)
                'event_type': 'onset_candidate',
                'stock_code': stock_code,
                'score': 2.8,
                'evidence': {
                    'ret_1s': 0.004,
                    'z_vol_1s': 2.6,
                    'ticks_per_sec': 2
                }
            },
            # Third candidate after refractory period (should be allowed)
            {
                'ts': base_ts + 130000,  # 130 seconds after confirmation (past 120s refractory)
                'event_type': 'onset_candidate',
                'stock_code': stock_code,
                'score': 3.0,
                'evidence': {
                    'ret_1s': 0.007,
                    'z_vol_1s': 3.2,
                    'ticks_per_sec': 4
                }
            }
        ]
    
    def test_refractory_manager_initialization(self):
        """Test RefractoryManager initialization."""
        manager = RefractoryManager()
        
        assert manager.config is not None
        assert manager.event_store is not None
        assert manager.duration_s > 0
        assert isinstance(manager.extend_on_confirm, bool)
        assert isinstance(manager.last_confirm_ts, dict)
        assert len(manager.last_confirm_ts) == 0
    
    def test_refractory_manager_with_custom_config(self):
        """Test RefractoryManager initialization with custom config."""
        config = Config()
        config.refractory.duration_s = 60
        config.refractory.extend_on_confirm = False
        
        manager = RefractoryManager(config)
        
        assert manager.duration_s == 60
        assert manager.extend_on_confirm == False
    
    def test_allow_candidate_no_previous_confirm(self):
        """Test allowing candidate when no previous confirmation exists."""
        manager = RefractoryManager()
        
        # No previous confirmation for this stock
        assert manager.allow_candidate(1704067200000, '005930') == True
        assert manager.allow_candidate(1704067250000, '000010') == True
    
    def test_allow_candidate_after_refractory_period(self):
        """Test allowing candidate after refractory period has passed."""
        manager = RefractoryManager()
        base_ts = 1704067200000
        
        # Set up previous confirmation
        manager.update_confirm(base_ts, '005930')
        
        # Should be blocked during refractory period
        assert manager.allow_candidate(base_ts + 60000, '005930') == False  # 60s later
        
        # Should be allowed after refractory period
        assert manager.allow_candidate(base_ts + 130000, '005930') == True  # 130s later
    
    def test_allow_candidate_within_refractory_period(self):
        """Test blocking candidate within refractory period."""
        manager = RefractoryManager()
        base_ts = 1704067200000
        
        # Set up previous confirmation
        manager.update_confirm(base_ts, '005930')
        
        # Should be blocked within refractory period
        assert manager.allow_candidate(base_ts + 30000, '005930') == False   # 30s later
        assert manager.allow_candidate(base_ts + 90000, '005930') == False   # 90s later
        assert manager.allow_candidate(base_ts + 119000, '005930') == False  # 119s later
        
        # Should be allowed exactly at refractory end
        assert manager.allow_candidate(base_ts + 120000, '005930') == True   # 120s later
    
    def test_update_confirm_basic(self):
        """Test basic confirmation timestamp update."""
        manager = RefractoryManager()
        base_ts = 1704067200000
        
        # Update confirmation timestamp
        manager.update_confirm(base_ts, '005930')
        
        assert '005930' in manager.last_confirm_ts
        assert manager.last_confirm_ts['005930'] == base_ts
    
    def test_update_confirm_extend_on_confirm_true(self):
        """Test confirmation update with extend_on_confirm=True."""
        config = Config()
        config.refractory.extend_on_confirm = True
        manager = RefractoryManager(config)
        
        base_ts = 1704067200000
        
        # First confirmation
        manager.update_confirm(base_ts, '005930')
        assert manager.last_confirm_ts['005930'] == base_ts
        
        # Second confirmation should update timestamp
        new_ts = base_ts + 50000
        manager.update_confirm(new_ts, '005930')
        assert manager.last_confirm_ts['005930'] == new_ts
    
    def test_update_confirm_extend_on_confirm_false(self):
        """Test confirmation update with extend_on_confirm=False."""
        config = Config()
        config.refractory.extend_on_confirm = False
        manager = RefractoryManager(config)
        
        base_ts = 1704067200000
        
        # First confirmation
        manager.update_confirm(base_ts, '005930')
        assert manager.last_confirm_ts['005930'] == base_ts
        
        # Second confirmation should NOT update timestamp
        new_ts = base_ts + 50000
        manager.update_confirm(new_ts, '005930')
        assert manager.last_confirm_ts['005930'] == base_ts  # Still original timestamp
    
    def test_get_refractory_status_no_previous_confirm(self):
        """Test refractory status when no previous confirmation exists."""
        manager = RefractoryManager()
        
        status = manager.get_refractory_status('005930')
        
        assert status['is_refractory'] == False
        assert status['last_confirm_ts'] is None
        assert status['refractory_end_ts'] is None
        assert status['remaining_seconds'] == 0
    
    def test_get_refractory_status_within_refractory(self):
        """Test refractory status within refractory period."""
        manager = RefractoryManager()
        base_ts = 1704067200000
        
        # Set up confirmation
        manager.update_confirm(base_ts, '005930')
        
        # Check status 60 seconds later
        current_ts = base_ts + 60000
        status = manager.get_refractory_status('005930', current_ts)
        
        assert status['is_refractory'] == True
        assert status['last_confirm_ts'] == base_ts
        assert status['refractory_end_ts'] == base_ts + 120000
        assert status['remaining_seconds'] == 60.0
    
    def test_get_refractory_status_past_refractory(self):
        """Test refractory status past refractory period."""
        manager = RefractoryManager()
        base_ts = 1704067200000
        
        # Set up confirmation
        manager.update_confirm(base_ts, '005930')
        
        # Check status 130 seconds later
        current_ts = base_ts + 130000
        status = manager.get_refractory_status('005930', current_ts)
        
        assert status['is_refractory'] == False
        assert status['last_confirm_ts'] == base_ts
        assert status['refractory_end_ts'] == base_ts + 120000
        assert status['remaining_seconds'] == 0
    
    def test_process_events_basic(self):
        """Test basic event processing with refractory logic."""
        manager = RefractoryManager()
        events = self.create_sample_events()
        
        processed_events = manager.process_events(events)
        
        # Should have 4 events: candidate, confirmed, rejected_refractory, candidate
        assert len(processed_events) == 4
        
        # Check event types
        event_types = [e['event_type'] for e in processed_events]
        assert 'onset_candidate' in event_types
        assert 'onset_confirmed' in event_types
        assert 'onset_rejected_refractory' in event_types
        
        # Check that second candidate was rejected
        rejected_events = [e for e in processed_events if e['event_type'] == 'onset_rejected_refractory']
        assert len(rejected_events) == 1
        
        # Check that third candidate was allowed
        allowed_candidates = [e for e in processed_events if e['event_type'] == 'onset_candidate']
        assert len(allowed_candidates) == 2  # First and third
    
    def test_process_events_multiple_stocks(self):
        """Test event processing with multiple stocks."""
        manager = RefractoryManager()
        
        # Create events for two different stocks
        events_stock1 = self.create_sample_events(stock_code='005930')
        events_stock2 = self.create_sample_events(base_ts=1704067300000, stock_code='000660')
        
        all_events = events_stock1 + events_stock2
        processed_events = manager.process_events(all_events)
        
        # Each stock should have independent refractory periods
        stock1_rejected = [e for e in processed_events if e['stock_code'] == '005930' and e['event_type'] == 'onset_rejected_refractory']
        stock2_rejected = [e for e in processed_events if e['stock_code'] == '000660' and e['event_type'] == 'onset_rejected_refractory']
        
        assert len(stock1_rejected) == 1
        assert len(stock2_rejected) == 1
    
    def test_process_events_empty_list(self):
        """Test processing empty event list."""
        manager = RefractoryManager()
        
        processed_events = manager.process_events([])
        
        assert len(processed_events) == 0
    
    def test_process_events_only_candidates(self):
        """Test processing events with only candidates (no confirmations)."""
        manager = RefractoryManager()
        
        events = [
            {
                'ts': 1704067200000,
                'event_type': 'onset_candidate',
                'stock_code': '005930',
                'score': 2.5
            },
            {
                'ts': 1704067230000,
                'event_type': 'onset_candidate',
                'stock_code': '005930',
                'score': 2.8
            }
        ]
        
        processed_events = manager.process_events(events)
        
        # Both candidates should be allowed (no confirmations to trigger refractory)
        assert len(processed_events) == 2
        assert all(e['event_type'] == 'onset_candidate' for e in processed_events)
    
    def test_save_processed_events_success(self):
        """Test successful saving of processed events."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create temporary event store
            temp_events_path = Path(tmp_dir) / "events"
            temp_events_path.mkdir()
            event_store = EventStore(path=str(temp_events_path))
            
            manager = RefractoryManager(event_store=event_store)
            events = self.create_sample_events()
            processed_events = manager.process_events(events)
            
            success = manager.save_processed_events(processed_events, filename="test_refractory.jsonl")
            
            assert success == True
            
            # Verify file was created
            output_file = temp_events_path / "test_refractory.jsonl"
            assert output_file.exists()
    
    def test_process_and_save_complete(self):
        """Test complete process and save operation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_events_path = Path(tmp_dir) / "events"
            temp_events_path.mkdir()
            event_store = EventStore(path=str(temp_events_path))
            
            manager = RefractoryManager(event_store=event_store)
            events = self.create_sample_events()
            
            result = manager.process_and_save(events, filename="test_complete.jsonl")
            
            assert result['events_processed'] == 4
            assert result['events_output'] == 4
            assert result['original_candidates'] == 3
            assert result['original_confirmations'] == 1
            assert result['allowed_candidates'] == 2
            assert result['rejected_candidates'] == 1
            assert result['final_confirmations'] == 1
            assert result['rejection_rate'] > 0  # Should be 1/3 ≈ 0.33
            assert result['save_success'] == True
    
    def test_get_refractory_stats(self):
        """Test refractory statistics calculation."""
        manager = RefractoryManager()
        events = self.create_sample_events()
        
        stats = manager.get_refractory_stats(events)
        
        assert stats['total_events'] == 4
        assert stats['candidates_processed'] == 3
        assert stats['candidates_allowed'] == 2
        assert stats['candidates_rejected'] == 1
        assert stats['rejection_rate'] == pytest.approx(1/3, rel=1e-2)  # 1 rejected out of 3 candidates
        assert stats['stocks_tracked'] == 1  # One stock with confirmation
        assert stats['config']['duration_s'] == 120
        assert stats['config']['extend_on_confirm'] == True
    
    def test_reset_refractory_state(self):
        """Test resetting refractory state."""
        manager = RefractoryManager()
        
        # Add some confirmation timestamps
        manager.update_confirm(1704067200000, '005930')
        manager.update_confirm(1704067250000, '000660')
        
        assert len(manager.last_confirm_ts) == 2
        
        # Reset state
        manager.reset_refractory_state()
        
        assert len(manager.last_confirm_ts) == 0
    
    def test_process_refractory_events_function(self):
        """Test the convenience function."""
        events = self.create_sample_events()
        
        processed_events = process_refractory_events(events)
        
        assert len(processed_events) == 4
        
        # Should contain rejected events
        rejected_events = [e for e in processed_events if e['event_type'] == 'onset_rejected_refractory']
        assert len(rejected_events) == 1
    
    def test_rejected_event_structure(self):
        """Test structure of rejected refractory events."""
        manager = RefractoryManager()
        events = self.create_sample_events()
        
        processed_events = manager.process_events(events)
        
        rejected_events = [e for e in processed_events if e['event_type'] == 'onset_rejected_refractory']
        assert len(rejected_events) == 1
        
        rejected = rejected_events[0]
        
        # Check required fields
        assert 'ts' in rejected
        assert 'event_type' in rejected
        assert 'stock_code' in rejected
        assert 'rejected_at' in rejected
        assert 'original_score' in rejected
        assert 'refractory_info' in rejected
        assert 'original_evidence' in rejected
        
        # Check refractory info structure
        refractory_info = rejected['refractory_info']
        assert 'is_refractory' in refractory_info
        assert 'last_confirm_ts' in refractory_info
        assert 'refractory_end_ts' in refractory_info
        assert 'remaining_seconds' in refractory_info
        
        assert refractory_info['is_refractory'] == True
        assert refractory_info['remaining_seconds'] > 0