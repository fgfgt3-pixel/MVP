"""Tests for config_loader module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest
import yaml

from src.config_loader import (
    Config, PathsConfig, OnsetConfig, load_config,
    _get_env_overrides, _deep_merge
)
from src.utils.paths import PathManager, get_path_manager, ensure_directory


class TestConfigModels:
    """Test Pydantic models."""
    
    def test_paths_config_defaults(self):
        """Test PathsConfig default values."""
        config = PathsConfig()
        assert config.data_raw == "data/raw"
        assert config.data_clean == "data/clean"
        assert config.reports == "reports"
        assert config.plots == "reports/plots"
    
    def test_onset_config_defaults(self):
        """Test OnsetConfig default values."""
        config = OnsetConfig()
        assert config.refractory_s == 120
        assert config.confirm_window_s == 20
        assert config.score_threshold == 2.0
        assert config.weights.speed == 0.4
        assert config.weights.participation == 0.4
        assert config.weights.friction == 0.2
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config_data = {
            "onset": {
                "refractory_s": 60,
                "confirm_window_s": 15,
                "score_threshold": 1.5
            }
        }
        config = Config(**config_data)
        assert config.onset.refractory_s == 60
        
        # Invalid config (negative values should still pass unless we add validation)
        config_data_invalid = {
            "onset": {
                "refractory_s": -10
            }
        }
        config = Config(**config_data_invalid)
        assert config.onset.refractory_s == -10  # No validation rules yet


class TestConfigLoader:
    """Test configuration loading functionality."""
    
    def test_load_config_with_defaults(self):
        """Test loading config with all default values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(project_root=temp_dir, load_env=False)
            assert isinstance(config, Config)
            assert config.onset.refractory_s == 120
            assert config.paths.data_raw == "data/raw"
    
    def test_load_config_from_yaml(self):
        """Test loading config from YAML file."""
        config_content = {
            "onset": {
                "refractory_s": 90,
                "confirm_window_s": 25,
                "score_threshold": 3.0
            },
            "paths": {
                "data_raw": "custom/raw",
                "reports": "custom/reports"
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config directory and file
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            config_file = config_dir / "onset_default.yaml"
            
            with open(config_file, 'w') as f:
                yaml.safe_dump(config_content, f)
            
            # Load config
            config = load_config(project_root=temp_dir, load_env=False)
            
            assert config.onset.refractory_s == 90
            assert config.onset.confirm_window_s == 25
            assert config.onset.score_threshold == 3.0
            assert config.paths.data_raw == "custom/raw"
            assert config.paths.reports == "custom/reports"
    
    def test_load_config_with_custom_path(self):
        """Test loading config from custom path."""
        config_content = {
            "onset": {"refractory_s": 150}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_config = Path(temp_dir) / "custom_config.yaml"
            with open(custom_config, 'w') as f:
                yaml.safe_dump(config_content, f)
            
            config = load_config(config_path=str(custom_config), load_env=False)
            assert config.onset.refractory_s == 150
    
    @patch.dict(os.environ, {
        'DATA_RAW_PATH': '/custom/raw',
        'LOG_LEVEL': 'DEBUG',
        'TIMEZONE': 'UTC'
    })
    def test_load_config_with_env_overrides(self):
        """Test config loading with environment variable overrides."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(project_root=temp_dir, load_env=True)
            
            assert config.paths.data_raw == '/custom/raw'
            assert config.logging.level == 'DEBUG'
            assert config.session.timezone == 'UTC'
    
    def test_env_overrides_extraction(self):
        """Test extraction of environment variable overrides."""
        with patch.dict(os.environ, {
            'DATA_RAW_PATH': '/env/raw',
            'REPORTS_PATH': '/env/reports',
            'LOG_LEVEL': 'WARNING'
        }):
            overrides = _get_env_overrides()
            
            expected = {
                'paths': {
                    'data_raw': '/env/raw',
                    'reports': '/env/reports'
                },
                'logging': {
                    'level': 'WARNING'
                }
            }
            assert overrides == expected
    
    def test_deep_merge(self):
        """Test deep dictionary merging."""
        base = {
            'a': 1,
            'b': {
                'c': 2,
                'd': 3
            }
        }
        
        override = {
            'a': 10,
            'b': {
                'd': 30,
                'e': 4
            },
            'f': 5
        }
        
        result = _deep_merge(base, override)
        
        expected = {
            'a': 10,
            'b': {
                'c': 2,
                'd': 30,
                'e': 4
            },
            'f': 5
        }
        
        assert result == expected


class TestPathManager:
    """Test path management utilities."""
    
    def test_path_manager_initialization(self):
        """Test PathManager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pm = PathManager(project_root=temp_dir)
            assert pm.project_root == Path(temp_dir)
    
    def test_path_manager_with_config(self):
        """Test PathManager with custom config."""
        config_data = {
            "paths": {
                "data_raw": "custom/raw",
                "reports": "custom/reports"
            }
        }
        config = Config(**config_data)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            pm = PathManager(config=config, project_root=temp_dir)
            
            raw_path = pm.get_data_raw_path()
            reports_path = pm.get_reports_path()
            
            assert raw_path == Path(temp_dir) / "custom/raw"
            assert reports_path == Path(temp_dir) / "custom/reports"
            assert raw_path.exists()  # Should be created
            assert reports_path.exists()  # Should be created
    
    def test_absolute_path_conversion(self):
        """Test absolute path conversion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pm = PathManager(project_root=temp_dir)
            
            # Test relative path
            rel_path = "data/test"
            abs_path = pm.get_absolute_path(rel_path)
            assert abs_path == Path(temp_dir) / "data/test"
            
            # Test already absolute path
            existing_abs = Path(temp_dir) / "absolute"
            result = pm.get_absolute_path(existing_abs)
            assert result == existing_abs
    
    def test_ensure_dir_exists(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pm = PathManager(project_root=temp_dir)
            
            test_dir = "test/nested/directory"
            result_path = pm.ensure_dir_exists(test_dir)
            
            expected_path = Path(temp_dir) / test_dir
            assert result_path == expected_path
            assert result_path.exists()
            assert result_path.is_dir()
    
    def test_get_file_path(self):
        """Test file path generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pm = PathManager(project_root=temp_dir)
            
            file_path = pm.get_file_path('raw', 'test.csv')
            expected_path = Path(temp_dir) / "data/raw/test.csv"
            
            assert file_path == expected_path
            assert file_path.parent.exists()  # Directory should be created
    
    def test_get_file_path_invalid_type(self):
        """Test file path generation with invalid directory type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pm = PathManager(project_root=temp_dir)
            
            with pytest.raises(ValueError, match="Unknown directory type"):
                pm.get_file_path('invalid_type', 'test.csv')
    
    def test_ensure_all_paths(self):
        """Test ensuring all configured paths exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pm = PathManager(project_root=temp_dir)
            
            paths = pm.ensure_all_paths()
            
            # Check that all expected paths are returned
            expected_keys = {
                'data_raw', 'data_clean', 'data_features', 'data_events',
                'reports', 'plots', 'logs'
            }
            assert set(paths.keys()) == expected_keys
            
            # Check that all paths exist
            for path in paths.values():
                assert path.exists()
                assert path.is_dir()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_get_path_manager(self):
        """Test get_path_manager function."""
        pm = get_path_manager()
        assert isinstance(pm, PathManager)
    
    def test_ensure_directory(self):
        """Test ensure_directory convenience function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "test_convenience"
            result = ensure_directory(test_dir)
            
            assert result == test_dir
            assert test_dir.exists()


# Integration test
def test_integration_config_and_paths():
    """Test integration between config loading and path management."""
    config_content = {
        "paths": {
            "data_raw": "integration/raw",
            "reports": "integration/reports"
        },
        "onset": {
            "refractory_s": 180
        }
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create config file
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir()
        config_file = config_dir / "onset_default.yaml"
        
        with open(config_file, 'w') as f:
            yaml.safe_dump(config_content, f)
        
        # Load config and create path manager
        config = load_config(project_root=temp_dir, load_env=False)
        pm = PathManager(config=config, project_root=temp_dir)
        
        # Test that paths work correctly
        raw_path = pm.get_data_raw_path()
        reports_path = pm.get_reports_path()
        
        assert raw_path == Path(temp_dir) / "integration/raw"
        assert reports_path == Path(temp_dir) / "integration/reports"
        assert raw_path.exists()
        assert reports_path.exists()
        
        # Test file path generation
        csv_path = pm.get_file_path('raw', 'data.csv')
        assert csv_path == Path(temp_dir) / "integration/raw/data.csv"