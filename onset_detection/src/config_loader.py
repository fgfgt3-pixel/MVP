"""Configuration loader for onset detection system."""

import argparse
import os
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class PathsConfig(BaseModel):
    """Path configuration model."""
    data_raw: str = Field(default="data/raw")
    data_clean: str = Field(default="data/clean")
    data_features: str = Field(default="data/features")
    data_events: str = Field(default="data/events")
    data_labels: str = Field(default="data/labels")
    reports: str = Field(default="reports")
    plots: str = Field(default="reports/plots")
    logs: str = Field(default="logs")


class WeightsConfig(BaseModel):
    """Onset detection weights configuration."""
    speed: float = Field(default=0.4)
    participation: float = Field(default=0.4)
    friction: float = Field(default=0.2)


class ThresholdsConfig(BaseModel):
    """Onset detection thresholds configuration."""
    percentile: float = Field(default=95.0)
    min_volume_z: float = Field(default=1.5)
    min_return_pct: float = Field(default=0.005)


class TimeConfig(BaseModel):
    """Time configuration model."""
    epoch_unit: str = Field(default="ms")
    timezone: str = Field(default="Asia/Seoul")


class VolumeConfig(BaseModel):
    """Volume configuration model."""
    is_cumulative: bool = Field(default=True)
    roll_window_s: int = Field(default=300)


class OnsetConfig(BaseModel):
    """Onset detection configuration model."""
    refractory_s: int = Field(default=120)
    confirm_window_s: int = Field(default=20)
    score_threshold: float = Field(default=2.0)
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)


class FeaturesConfig(BaseModel):
    """Features computation configuration."""
    short_window: int = Field(default=60)
    long_window: int = Field(default=1800)
    rolling: Dict[str, int] = Field(default_factory=lambda: {
        "vol_window": 300,
        "price_window": 600
    })


class SessionConfig(BaseModel):
    """Session configuration."""
    timezone: str = Field(default="Asia/Seoul")
    market_open: str = Field(default="09:00")
    market_close: str = Field(default="15:30")
    lunch_start: str = Field(default="12:00")
    lunch_end: str = Field(default="13:00")


class VisualConfig(BaseModel):
    """Visualization configuration."""
    mode: str = Field(default="point")
    show_stages: bool = Field(default=True)
    debug_labels: bool = Field(default=False)
    timeline_panel: bool = Field(default=True)


class SegmenterConfig(BaseModel):
    """Segmenter configuration."""
    dd_stop_pct: float = Field(default=0.012)
    vol_norm_z: float = Field(default=1.0)
    max_hold_s: int = Field(default=180)


class DetectionConfig(BaseModel):
    """Detection configuration."""
    score_threshold: float = Field(default=2.0)
    vol_z_min: float = Field(default=2.0)
    ticks_min: int = Field(default=2)
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "ret": 1.0,
        "accel": 1.0,
        "z_vol": 1.0,
        "ticks": 0.5
    })


class ConfirmConfig(BaseModel):
    """Confirmation configuration."""
    window_s: int = Field(default=18)
    min_axes: int = Field(default=1)
    vol_z_min: float = Field(default=1.0)
    spread_max: float = Field(default=0.03)
    persistent_n: int = Field(default=2)
    exclude_cand_point: bool = Field(default=True)


class RefractoryConfig(BaseModel):
    """Refractory configuration."""
    duration_s: int = Field(default=120)
    extend_on_confirm: bool = Field(default=True)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_rotation: bool = Field(default=True)


class Config(BaseModel):
    """Main configuration model."""
    paths: PathsConfig = Field(default_factory=PathsConfig)
    onset: OnsetConfig = Field(default_factory=OnsetConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    time: TimeConfig = Field(default_factory=TimeConfig)
    volume: VolumeConfig = Field(default_factory=VolumeConfig)
    visual: VisualConfig = Field(default_factory=VisualConfig)
    segmenter: SegmenterConfig = Field(default_factory=SegmenterConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    confirm: ConfirmConfig = Field(default_factory=ConfirmConfig)
    refractory: RefractoryConfig = Field(default_factory=RefractoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(
    config_path: Optional[str] = None,
    load_env: bool = True,
    project_root: Optional[str] = None
) -> Config:
    """
    Load configuration from YAML file and merge with environment variables.
    
    Args:
        config_path: Path to YAML config file. If None, uses default.
        load_env: Whether to load .env file and merge environment variables.
        project_root: Project root directory. If None, auto-detected.
    
    Returns:
        Config: Parsed and validated configuration object.
    """
    # Determine project root
    if project_root is None:
        current_file = Path(__file__)
        project_root = current_file.parent.parent  # Go up from src/ to project root
    else:
        project_root = Path(project_root)
    
    # Load environment variables if requested
    if load_env:
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    
    # Determine config path
    if config_path is None:
        config_path = project_root / "config" / "onset_default.yaml"
    else:
        config_path = Path(config_path)
        if not config_path.is_absolute():
            config_path = project_root / config_path
    
    # Load YAML config
    config_data = {}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
    
    # Merge with environment variables
    if load_env:
        env_overrides = _get_env_overrides()
        config_data = _deep_merge(config_data, env_overrides)
    
    # Create and validate config
    return Config(**config_data)


def _get_env_overrides() -> Dict[str, Any]:
    """Extract configuration overrides from environment variables."""
    overrides = {}
    
    # Path overrides
    if os.getenv("DATA_RAW_PATH"):
        overrides.setdefault("paths", {})["data_raw"] = os.getenv("DATA_RAW_PATH")
    if os.getenv("DATA_CLEAN_PATH"):
        overrides.setdefault("paths", {})["data_clean"] = os.getenv("DATA_CLEAN_PATH")
    if os.getenv("REPORTS_PATH"):
        overrides.setdefault("paths", {})["reports"] = os.getenv("REPORTS_PATH")
    if os.getenv("PLOTS_PATH"):
        overrides.setdefault("paths", {})["plots"] = os.getenv("PLOTS_PATH")
    if os.getenv("LOG_PATH"):
        overrides.setdefault("paths", {})["logs"] = os.getenv("LOG_PATH")
    
    # Logging overrides
    if os.getenv("LOG_LEVEL"):
        overrides.setdefault("logging", {})["level"] = os.getenv("LOG_LEVEL")
    
    # Session overrides
    if os.getenv("TIMEZONE"):
        overrides.setdefault("session", {})["timezone"] = os.getenv("TIMEZONE")
    
    return overrides


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def main():
    """CLI entry point for config loader."""
    parser = argparse.ArgumentParser(description="Onset detection configuration loader")
    parser.add_argument("--print", action="store_true", help="Print current configuration")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--no-env", action="store_true", help="Don't load .env file")
    
    args = parser.parse_args()
    
    try:
        config = load_config(
            config_path=args.config,
            load_env=not args.no_env
        )
        
        if args.print:
            print("Current configuration:")
            print("=" * 50)
            print(config.model_dump_json(indent=2))
        else:
            print("Configuration loaded successfully!")
            print(f"Paths: {config.paths}")
            print(f"Onset settings: refractory={config.onset.refractory_s}s, "
                  f"confirm_window={config.onset.confirm_window_s}s")
    
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())