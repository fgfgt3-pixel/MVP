"""Path utilities for onset detection system."""

import os
from pathlib import Path
from typing import Union, Optional

from ..config_loader import Config, load_config


class PathManager:
    """Manages paths and ensures directories exist."""
    
    def __init__(self, config: Optional[Config] = None, project_root: Optional[str] = None):
        """
        Initialize path manager.
        
        Args:
            config: Configuration object. If None, loads default config.
            project_root: Project root directory. If None, auto-detected.
        """
        if config is None:
            config = load_config(project_root=project_root)
        
        self.config = config
        
        # Determine project root
        if project_root is None:
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent  # Go up to project root
        else:
            self.project_root = Path(project_root)
    
    def get_absolute_path(self, relative_path: Union[str, Path]) -> Path:
        """
        Convert relative path to absolute path based on project root.
        
        Args:
            relative_path: Relative path string or Path object.
            
        Returns:
            Path: Absolute path.
        """
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return self.project_root / path
    
    def ensure_dir_exists(self, path: Union[str, Path]) -> Path:
        """
        Ensure directory exists, creating it if necessary.
        
        Args:
            path: Directory path.
            
        Returns:
            Path: Absolute path to the directory.
        """
        abs_path = self.get_absolute_path(path)
        abs_path.mkdir(parents=True, exist_ok=True)
        return abs_path
    
    def get_data_raw_path(self) -> Path:
        """Get absolute path to raw data directory."""
        return self.ensure_dir_exists(self.config.paths.data_raw)
    
    def get_data_clean_path(self) -> Path:
        """Get absolute path to clean data directory."""
        return self.ensure_dir_exists(self.config.paths.data_clean)
    
    def get_data_features_path(self) -> Path:
        """Get absolute path to features data directory."""
        return self.ensure_dir_exists(self.config.paths.data_features)
    
    def get_data_events_path(self) -> Path:
        """Get absolute path to events data directory."""
        return self.ensure_dir_exists(self.config.paths.data_events)
    
    def get_data_labels_path(self) -> Path:
        """Get absolute path to labels data directory."""
        return self.ensure_dir_exists(self.config.paths.data_labels)
    
    def get_reports_path(self) -> Path:
        """Get absolute path to reports directory."""
        return self.ensure_dir_exists(self.config.paths.reports)
    
    def get_plots_path(self) -> Path:
        """Get absolute path to plots directory."""
        return self.ensure_dir_exists(self.config.paths.plots)
    
    def get_logs_path(self) -> Path:
        """Get absolute path to logs directory."""
        return self.ensure_dir_exists(self.config.paths.logs)
    
    def get_file_path(self, directory_type: str, filename: str) -> Path:
        """
        Get full file path for a given directory type and filename.
        
        Args:
            directory_type: Type of directory ('raw', 'clean', 'features', 'events', 
                          'labels', 'reports', 'plots', 'logs').
            filename: Name of the file.
            
        Returns:
            Path: Full path to the file.
            
        Raises:
            ValueError: If directory_type is not recognized.
        """
        directory_methods = {
            'raw': self.get_data_raw_path,
            'clean': self.get_data_clean_path,
            'features': self.get_data_features_path,
            'events': self.get_data_events_path,
            'labels': self.get_data_labels_path,
            'reports': self.get_reports_path,
            'plots': self.get_plots_path,
            'logs': self.get_logs_path,
        }
        
        if directory_type not in directory_methods:
            available_types = ', '.join(directory_methods.keys())
            raise ValueError(f"Unknown directory type '{directory_type}'. "
                           f"Available types: {available_types}")
        
        directory_path = directory_methods[directory_type]()
        return directory_path / filename
    
    def ensure_all_paths(self) -> dict:
        """
        Ensure all configured paths exist.
        
        Returns:
            dict: Dictionary mapping path names to their absolute paths.
        """
        paths = {
            'data_raw': self.get_data_raw_path(),
            'data_clean': self.get_data_clean_path(),
            'data_features': self.get_data_features_path(),
            'data_events': self.get_data_events_path(),
            'reports': self.get_reports_path(),
            'plots': self.get_plots_path(),
            'logs': self.get_logs_path(),
        }
        
        return paths


# Convenience functions for quick access
def get_path_manager(config: Optional[Config] = None) -> PathManager:
    """Get a PathManager instance."""
    return PathManager(config=config)


def ensure_directory(path: Union[str, Path], project_root: Optional[str] = None) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path (relative or absolute).
        project_root: Project root directory for relative paths.
        
    Returns:
        Path: Absolute path to the directory.
    """
    path_manager = PathManager(project_root=project_root)
    return path_manager.ensure_dir_exists(path)


def to_absolute_path(path: Union[str, Path], project_root: Optional[str] = None) -> Path:
    """
    Convert path to absolute path.
    
    Args:
        path: Path to convert.
        project_root: Project root directory for relative paths.
        
    Returns:
        Path: Absolute path.
    """
    path_manager = PathManager(project_root=project_root)
    return path_manager.get_absolute_path(path)


if __name__ == "__main__":
    # Demo/test the path utilities
    path_manager = get_path_manager()
    
    print("Path Manager Demo")
    print("=" * 40)
    
    # Ensure all paths exist
    paths = path_manager.ensure_all_paths()
    
    for name, path in paths.items():
        print(f"{name}: {path}")
    
    # Test file path generation
    print("\nFile Path Examples:")
    print("-" * 20)
    print(f"Raw data CSV: {path_manager.get_file_path('raw', 'sample.csv')}")
    print(f"Event log: {path_manager.get_file_path('events', 'onsets.parquet')}")
    print(f"Plot: {path_manager.get_file_path('plots', 'onset_chart.png')}")