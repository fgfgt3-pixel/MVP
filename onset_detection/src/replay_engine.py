"""Replay engine for simulating real-time tick data processing."""

import time
from typing import Iterator, Dict, Any, Optional, Callable, Union
import pandas as pd
from datetime import datetime, timedelta

from .config_loader import Config, load_config


class ReplaySource:
    """
    Replay source that yields DataFrame rows as tick events.
    
    Simulates real-time data streaming from historical CSV data,
    supporting speed control and optional time delays.
    """
    
    def __init__(
        self, 
        df: pd.DataFrame, 
        speed: float = 1.0, 
        sleep: bool = False,
        config: Optional[Config] = None
    ):
        """
        Initialize replay source.
        
        Args:
            df: DataFrame with tick data (must have 'ts' column).
            speed: Playback speed multiplier (1.0 = real-time, >1.0 = faster, <1.0 = slower).
            sleep: Whether to add real-time delays between ticks.
            config: Configuration object.
            
        Raises:
            ValueError: If DataFrame is empty or missing required columns.
        """
        if df.empty:
            raise ValueError("DataFrame cannot be empty")
        
        if 'ts' not in df.columns:
            raise ValueError("DataFrame must have 'ts' (timestamp) column")
        
        self.df = df.copy().sort_values('ts').reset_index(drop=True)
        self.speed = max(0.01, speed)  # Minimum speed to prevent division by zero
        self.sleep = sleep
        self.config = config or load_config()
        
        # State tracking
        self.current_index = 0
        self.start_time = None
        self.first_tick_time = None
        
        # Event callbacks
        self._callbacks = []
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Add callback function to be called for each tick.
        
        Args:
            callback: Function that takes a tick dictionary as input.
        """
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove callback function."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """
        Iterate through DataFrame rows as tick events.
        
        Yields:
            Dict[str, Any]: Row data as dictionary with metadata.
        """
        self.reset()
        
        for index, row in self.df.iterrows():
            # Handle timing if sleep is enabled
            if self.sleep:
                self._handle_timing(row)
            
            # Convert row to dictionary
            tick_data = self._row_to_tick(row, index)
            
            # Call registered callbacks
            for callback in self._callbacks:
                try:
                    callback(tick_data)
                except Exception as e:
                    print(f"Warning: Callback error: {e}")
            
            self.current_index = index + 1
            yield tick_data
    
    def _handle_timing(self, row: pd.Series) -> None:
        """Handle real-time delays based on timestamp differences."""
        current_time = time.time()
        
        if self.start_time is None:
            self.start_time = current_time
            self.first_tick_time = row['ts']
            return
        
        # Calculate elapsed time in simulation vs real world
        sim_elapsed = (row['ts'] - self.first_tick_time).total_seconds()
        real_elapsed = current_time - self.start_time
        
        # Adjust for speed
        target_elapsed = sim_elapsed / self.speed
        
        # Sleep if we're ahead of schedule
        if target_elapsed > real_elapsed:
            sleep_time = target_elapsed - real_elapsed
            time.sleep(sleep_time)
    
    def _row_to_tick(self, row: pd.Series, index: int) -> Dict[str, Any]:
        """
        Convert DataFrame row to tick dictionary.
        
        Args:
            row: DataFrame row.
            index: Row index.
            
        Returns:
            Dict[str, Any]: Tick data with metadata.
        """
        tick_data = row.to_dict()
        
        # Add metadata
        tick_data['_metadata'] = {
            'index': index,
            'total_rows': len(self.df),
            'progress_pct': (index + 1) / len(self.df) * 100,
            'replay_time': datetime.now().isoformat(),
            'speed': self.speed,
            'sleep_enabled': self.sleep
        }
        
        return tick_data
    
    def reset(self) -> None:
        """Reset replay state to beginning."""
        self.current_index = 0
        self.start_time = None
        self.first_tick_time = None
    
    def skip_to(self, index: int) -> None:
        """
        Skip to specific row index.
        
        Args:
            index: Target row index.
            
        Raises:
            ValueError: If index is out of bounds.
        """
        if not 0 <= index < len(self.df):
            raise ValueError(f"Index {index} out of bounds (0-{len(self.df)-1})")
        
        self.current_index = index
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current replay progress information.
        
        Returns:
            Dict[str, Any]: Progress information.
        """
        if len(self.df) == 0:
            return {"progress_pct": 0, "current_index": 0, "total_rows": 0}
        
        return {
            "progress_pct": self.current_index / len(self.df) * 100,
            "current_index": self.current_index,
            "total_rows": len(self.df),
            "remaining_rows": len(self.df) - self.current_index,
            "current_timestamp": self.df.iloc[self.current_index]['ts'].isoformat() if self.current_index < len(self.df) else None
        }


class ReplayEngine:
    """
    High-level replay engine that manages multiple replay sources and provides
    event processing capabilities.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize replay engine.
        
        Args:
            config: Configuration object.
        """
        self.config = config or load_config()
        self._sources = {}
        self._global_callbacks = []
    
    def add_source(self, name: str, df: pd.DataFrame, **kwargs) -> ReplaySource:
        """
        Add a replay source.
        
        Args:
            name: Source identifier.
            df: DataFrame with tick data.
            **kwargs: Additional arguments for ReplaySource.
            
        Returns:
            ReplaySource: Created replay source.
        """
        source = ReplaySource(df, config=self.config, **kwargs)
        self._sources[name] = source
        return source
    
    def get_source(self, name: str) -> Optional[ReplaySource]:
        """Get replay source by name."""
        return self._sources.get(name)
    
    def remove_source(self, name: str) -> bool:
        """
        Remove replay source.
        
        Args:
            name: Source identifier.
            
        Returns:
            bool: True if removed, False if not found.
        """
        if name in self._sources:
            del self._sources[name]
            return True
        return False
    
    def add_global_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Add global callback that receives ticks from all sources.
        
        Args:
            callback: Function that takes (source_name, tick_data) as arguments.
        """
        self._global_callbacks.append(callback)
    
    def replay_source(
        self, 
        name: str, 
        limit: Optional[int] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Replay a specific source.
        
        Args:
            name: Source name.
            limit: Maximum number of ticks to replay.
            callback: Optional callback for each tick.
            
        Yields:
            Dict[str, Any]: Tick data.
            
        Raises:
            KeyError: If source not found.
        """
        if name not in self._sources:
            raise KeyError(f"Source '{name}' not found")
        
        source = self._sources[name]
        
        for i, tick_data in enumerate(source):
            # Apply limit
            if limit is not None and i >= limit:
                break
            
            # Call specific callback
            if callback:
                try:
                    callback(tick_data)
                except Exception as e:
                    print(f"Warning: Callback error: {e}")
            
            # Call global callbacks
            for global_callback in self._global_callbacks:
                try:
                    global_callback(name, tick_data)
                except Exception as e:
                    print(f"Warning: Global callback error: {e}")
            
            yield tick_data
    
    def get_sources_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all sources.
        
        Returns:
            Dict[str, Dict[str, Any]]: Source information.
        """
        info = {}
        for name, source in self._sources.items():
            info[name] = {
                "total_rows": len(source.df),
                "current_index": source.current_index,
                "speed": source.speed,
                "sleep_enabled": source.sleep,
                "date_range": {
                    "start": source.df['ts'].min().isoformat(),
                    "end": source.df['ts'].max().isoformat()
                } if not source.df.empty else None
            }
        return info


def create_simple_replay(df: pd.DataFrame, **kwargs) -> Iterator[Dict[str, Any]]:
    """
    Create a simple replay iterator from DataFrame.
    
    Args:
        df: DataFrame with tick data.
        **kwargs: Arguments for ReplaySource.
        
    Yields:
        Dict[str, Any]: Tick data.
    """
    source = ReplaySource(df, **kwargs)
    yield from source


if __name__ == "__main__":
    # Demo/test the replay engine
    from .data_loader import load_sample_data
    
    print("Replay Engine Demo")
    print("=" * 40)
    
    try:
        # Load sample data
        df = load_sample_data()
        print(f"Loaded {len(df)} ticks")
        
        # Create simple replay
        print("\nSimple Replay (first 5 ticks):")
        print("-" * 30)
        
        for i, tick in enumerate(create_simple_replay(df, speed=1.0)):
            if i >= 5:
                break
            
            print(f"Tick {i+1}: {tick['stock_code']} @ {tick['price']} "
                  f"(volume: {tick['volume']}, progress: {tick['_metadata']['progress_pct']:.1f}%)")
        
        # Test replay engine
        print("\nReplay Engine Test:")
        print("-" * 30)
        
        engine = ReplayEngine()
        engine.add_source("sample", df, speed=2.0, sleep=False)
        
        def tick_handler(tick_data):
            print(f"  Handler: {tick_data['stock_code']} @ {tick_data['price']}")
        
        count = 0
        for tick in engine.replay_source("sample", limit=3, callback=tick_handler):
            count += 1
        
        print(f"Processed {count} ticks")
        
    except Exception as e:
        print(f"Error in demo: {e}")