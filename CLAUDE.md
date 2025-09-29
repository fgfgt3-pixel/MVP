# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
# Install core dependencies
pip install -r requirements.txt

# Or install with development tools
pip install -e ".[dev]"
```

### Testing and Quality
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=onset_detection/src

# Format code
black onset_detection/src/ onset_detection/scripts/ tests/

# Lint code
flake8 onset_detection/src/ onset_detection/scripts/ tests/

# Type checking
mypy onset_detection/src/
```

### Data Processing Pipeline
```bash
# Convert raw CSV to clean format
python onset_detection/scripts/raw_to_clean_converter.py --input "filename.csv"

# Generate features from clean CSV
python onset_detection/scripts/generate_features.py --input "filename_clean.csv"

# Run backtest analysis
python scripts/backtest_run.py --features data/features/sample.csv --events data/events/sample.jsonl

# Run simulation
python scripts/run_simulation.py --config config/onset_default.yaml

# Run live system (stub)
python scripts/run_live.py --config config/onset_default.yaml
```

### Component Testing
```bash
# Test individual detection components
python onset_detection/scripts/candidate_test.py
python onset_detection/scripts/confirm_test.py
python onset_detection/scripts/refractory_test.py
python onset_detection/scripts/features_test.py
python onset_detection/scripts/event_test.py

# Generate visual reports
python onset_detection/scripts/plot_report_test.py --csv data/clean/sample.csv --events data/events/sample_candidates.jsonl
```

## Architecture Overview

### Project Purpose
This is an MVP system for detecting Korean stock market surge onsets (급등 시작점) from 1-tick data. The system processes real-time tick data to identify the beginning of price surges using a multi-stage detection pipeline optimized for speed and accuracy.

### High-Level Architecture
The system follows a **4-Phase development approach** with **CPD 3-Layer Structure**:

1. **Phase 0**: Baseline & Parity (CSV replay ≈ real-time streaming)
2. **Phase 1**: Onset Detection Engine v3 (CPD→Δ확인→불응, ML 필터)
3. **Phase 2**: Execution Readiness Guards (liquidity/slippage checks)
4. **Phase 3**: Ranking & Tuning (47 indicators/CPD parameters with parameter sweeps)

### Core Data Flow
```
Raw CSV (1-tick) → Clean → Features (47 indicators) → CPD Gate → Detection → Events → Reports
```

The system is designed to maintain **identical decision logic** between offline CSV replay and online real-time streaming to ensure production parity.

### Detection Engine (4-Stage State Machine with CPD Gate)
- **CPD Gate**: Change Point Detection using CUSUM (price axis) + Page-Hinkley (volume axis)
- **CandidateDetector**: Rule-based scoring using Speed + Participation + Friction metrics (only after CPD gate pass)
- **ConfirmDetector**: Delta-based validation within confirmation window (default 20s) with earliest-hit + persistent_n
- **RefractoryManager**: Cooldown periods (default 120s) to prevent duplicate alerts
- **ML Filter**: Optional ML-based final filtering with onset_strength threshold

### Key Modules

#### onset_detection/src/
- **config_loader.py**: YAML configuration with config hash injection for version tracking (includes CPD parameters)
- **data_loader.py**: Timestamp parsing (ms epochs → Asia/Seoul timezone) with data validation
- **features/core_indicators.py**: Core feature calculation (returns, volume z-scores, friction metrics)
- **cpd/**: CPD gate modules
  - **online_cusum.py**: OnlineCUSUM(k,h).update(x)->bool
  - **page_hinkley.py**: PageHinkley(delta,lambda).update(x)->bool
- **detection/**: 4-stage detection state machine (CPD/candidate/confirm/refractory)
  - **cpd_gate.py**: CPD gate integration (price=CUSUM, volume=Page-Hinkley)
- **event_store.py**: JSONL-based event storage for efficient append operations
- **backtest/**: Backtesting framework with performance metrics
- **ml/**: ML integration for hybrid rule-based + ML confirmation

#### Key Configuration Files
- **config/onset_default.yaml**: Main configuration with thresholds, weights, windows
- **config/ml.yaml**: ML model settings and hybrid confirmation parameters

### Critical Data Processing Notes

#### Timestamp Handling
- Raw CSV contains ms epoch timestamps that must be parsed as int64 to prevent precision loss
- All operations maintain Asia/Seoul timezone awareness
- System enforces chronological ordering and prevents future data leakage

#### Volume Processing
- CSV volume data is cumulative and requires `.diff().clip(0)` conversion to per-tick volumes
- Volume z-scores use rolling windows for session-adaptive normalization

#### Feature Engineering
- **Core set (6-8 indicators)**: `ret_1s`, `ret_accel`, `z_vol_1s`, `ticks_per_sec`, `spread`, `microprice_momentum`
- **Extended set (47 indicators)**: Includes additional friction, participation, and momentum metrics
  - **Recent additions**: `inter_trade_time`, `imbalance_1s`, `OFI_1s`
  - **Categories**: Basic data (4), Technical indicators (11), Returns (2), Order book (10+10), Advanced (10)
- Time-based aggregation uses second-level timestamps with proper sliding window calculations

#### Session Management
- Market sessions: Morning (09:00-12:00), Lunch (12:00-13:00), Afternoon (13:00-15:30)
- Thresholds adapt per session using percentile-based normalization
- Proper handling of session boundaries and gap periods

### Detection Logic Specifics

#### CPD Gate Parameters
- **CUSUM**: `k`=0.5~1.0×평시σ(MAD 기반), `h`=4~8×k for price axis (ret_50ms/microprice_slope)
- **Page-Hinkley**: `delta`≈0.05–0.1, `lambda`≈5–10 for volume axis (z_vol_1s)
- **Operational**: `min_pre_s` (early market protection), `cooldown_s` (re-trigger suppression)

#### Onset Scoring (Post-CPD Gate)
```
S_t = w_Speed × Speed_metrics + w_Participation × Volume_metrics + w_Friction × Spread_metrics
```

#### Confirmation Process (Delta-based)
- **Pre-window**: 5 seconds before candidate for baseline comparison
- **Confirmation window**: 20 seconds after candidate
- **Requirements**: Price axis mandatory + minimum 2 additional axes + persistent_n consecutive ticks
- **Delta thresholds**: Relative improvement over pre-window baseline

#### Event Types
- `cpd_trigger`: CPD gate passage event
- `onset_candidate`: Initial detection trigger (post-CPD gate)
- `onset_confirm`: Validated onset after confirmation window
- `refractory_enter`/`refractory_exit`: Cooldown state management

### File Structure Context

#### Data Pipeline Directories
- **data/raw/**: Original 1-tick CSV files
- **data/clean/**: Processed CSV with validated timestamps and column mappings
- **data/features/**: Generated 47-indicator feature sets
- **data/events/**: JSONL event logs (candidates, confirmations)
- **reports/**: Analysis outputs, performance metrics, plots

#### Expected Input Format
CSV files must contain columns mappable to: `ts`, `stock_code`, `price`, `volume`, `bid1`, `ask1`, `bid_qty1`, `ask_qty1`

### Testing Strategy
- **Unit tests**: Component-level testing with mock data
- **Integration tests**: Full pipeline validation
- **Leakage tests**: Verify no future data usage in streaming mode
- **Parity tests**: Ensure CSV replay ≡ real-time streaming decisions

### ML Integration
- Hybrid confirmation combining rule-based + ML strength scores
- Model storage and versioning through `ml/model_store.py`
- Feature window extraction for ML training via `ml/window_features.py`

### Performance Requirements
- **TTA (Time to Alert) p95**: ≤ 2 seconds from tick ingestion to onset confirmation
- **Detection Quality**: In-window detection rate maximization, FP/hour minimization
- **Execution Readiness**: ≥70% liquidity/spread threshold pass rate

### Important Implementation Details
- All feature calculations use streaming-compatible sliding windows
- No future data leakage: computation at time t uses only data up to time t
- Config-driven parameter tuning with hash-based version tracking
- Event storage optimized for real-time append with efficient time-range queries