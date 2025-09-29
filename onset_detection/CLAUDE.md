# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Development Setup
```bash
pip install -r requirements.txt
# Or for development with linting/testing tools:
pip install -e ".[dev]"
```

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_candidate_detector.py

# Run specific test
pytest tests/test_candidate_detector.py::TestCandidateDetector::test_detect_candidates
```

### Code Quality
```bash
# Format code
black src/ tests/ scripts/

# Lint code
flake8 src/ tests/ scripts/

# Type checking
mypy src/
```

### Data Processing Pipeline
```bash
# Convert raw CSV to clean format
python scripts/raw_to_clean_converter.py --input "filename.csv"

# Generate features from clean CSV
python scripts/generate_features.py --input "filename_clean.csv"

# Generate visual reports
python scripts/plot_report_test.py --csv data/clean/sample.csv --events data/events/sample_candidates.jsonl
```

### Testing Individual Components
```bash
# Test candidate detection
python scripts/candidate_test.py

# Test confirmation logic
python scripts/confirm_test.py

# Test refractory management
python scripts/refractory_test.py

# Test feature generation
python scripts/features_test.py

# Test event storage
python scripts/event_test.py
```

## Architecture Overview

### Core Data Pipeline
The system processes Korean stock tick data through a multi-stage pipeline:

1. **Raw → Clean**: `data_loader.py` handles CSV loading with proper timestamp parsing (ms epochs → Asia/Seoul timezone) and data type enforcement
2. **Clean → Features**: `core_indicators.py` calculates 7+ core indicators including price returns, volume z-scores, and friction metrics
3. **Features → Events**: Detection modules process features to identify onset candidates

### Detection Engine (3-Stage Process)
The onset detection follows a candidate → confirm → refractory workflow:

- **CandidateDetector**: Rule-based detection using Speed + Participation + Friction scoring
- **ConfirmDetector**: Validates candidates within a confirmation window (default 20s)
- **RefractoryManager**: Enforces cooldown periods (default 120s) to prevent duplicate signals

### Configuration System
Uses Pydantic models with YAML configuration files:
- Main config: `config/onset_default.yaml`
- Key sections: `time` (epoch handling), `volume` (cumulative processing), `onset` (thresholds), `detection` (weights)
- Config loader supports safe attribute access and type validation

### Event Storage
JSONL-based event storage system (`event_store.py`):
- One JSON object per line for efficient append operations
- Supports filtering by event type, time ranges
- Used for storing candidates, confirmations, and refractory states

### Critical Data Processing Notes
- **Timestamp Handling**: Raw data contains ms epochs that must be parsed as int64 to prevent precision loss
- **Volume Processing**: CSV volume data is cumulative and requires `.diff().clip(0)` conversion to per-tick volumes
- **Feature Aggregation**: Time-based features (ticks_per_sec, vol_1s, z_vol_1s) are aggregated by second-level timestamps

### Directory Structure Context
- `src/`: Main modules organized by function (detection, features, reporting, utils)
- `scripts/`: CLI tools for testing individual components and data processing
- `data/`: Segregated by processing stage (raw → clean → features → events)
- `tests/`: Unit tests mirroring src/ structure
- `config/`: YAML configuration files with validation schemas

### Important Implementation Details
- The system expects input files with specific column mappings: `time` → `ts`, `current_price` → `price`, etc.
- Core indicators require these minimum columns: ts, stock_code, price, volume, bid1, ask1, bid_qty1, ask_qty1
- Feature generation produces 23 columns including derived metrics like spread, microprice, and time-bucketed aggregations
- All timestamp operations preserve timezone information (Asia/Seoul)

### Testing Strategy
Each major component has dedicated test scripts for isolated testing plus comprehensive unit tests. The system supports both individual module testing and full pipeline validation with sample data.