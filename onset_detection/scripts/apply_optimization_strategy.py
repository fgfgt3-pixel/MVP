#!/usr/bin/env python
"""
최적화 전략 자동 적용 및 재실행
Dual-file validation: 023790 + 413630
"""

import json
import yaml
from pathlib import Path
import pandas as pd
import sys
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.detection.onset_pipeline import OnsetPipelineDF
from onset_detection.src.config_loader import load_config

# Step 1 결과 로드
with open(project_root / "onset_detection/reports/fp_distribution_analysis.json") as f:
    fp_analysis = json.load(f)

print("=" * 70)
print("Optimization Strategy Auto-Selection and Application")
print("=" * 70)

# 전략 선택 로직
large_clusters = fp_analysis['clusters']['large_clusters']
median_strength = fp_analysis['onset_strength_stats']['median']
fp_rate = fp_analysis['fp_rate']

print(f"\nFP Analysis Results:")
print(f"  FP Rate: {fp_rate*100:.1f}%")
print(f"  Large Clusters: {large_clusters}")
print(f"  Median Onset Strength: {median_strength:.3f}")

# 전략 결정 (복합 전략 선택)
if large_clusters >= 5:
    print("\nStrategy D selected: Composite Strategy (FP clusters + weak signals)")
    strategy_params = {
        "refractory_s": 45,
        "persistent_n": 22,
        "onset_strength_min": 0.70
    }
elif median_strength < 0.65:
    print("\nStrategy B selected: Onset Strength threshold (weak signals)")
    strategy_params = {
        "refractory_s": 30,
        "persistent_n": 20,
        "onset_strength_min": 0.7
    }
elif fp_rate > 0.9:
    print("\nStrategy C selected: Persistent_n increase (very high FP rate)")
    strategy_params = {
        "refractory_s": 30,
        "persistent_n": 30,
        "onset_strength_min": None
    }
else:
    print("\nStrategy D selected: Composite Strategy (balanced approach)")
    strategy_params = {
        "refractory_s": 45,
        "persistent_n": 22,
        "onset_strength_min": 0.67
    }

# Config 수정
config_path = project_root / "onset_detection/config/onset_default.yaml"
with open(config_path, 'r', encoding='utf-8') as f:
    config_data = yaml.safe_load(f)

config_data['refractory']['duration_s'] = strategy_params['refractory_s']
config_data['confirm']['persistent_n'] = strategy_params['persistent_n']

with open(config_path, 'w', encoding='utf-8') as f:
    yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

print(f"\nConfig modified:")
print(f"  refractory_s: {strategy_params['refractory_s']}")
print(f"  persistent_n: {strategy_params['persistent_n']}")
if strategy_params['onset_strength_min']:
    print(f"  onset_strength_min: {strategy_params['onset_strength_min']} (manual step required)")

# Onset Strength 필터링 적용 (필요 시)
if strategy_params['onset_strength_min']:
    print(f"\nWARNING: Manual modification required:")
    print(f"  Add 'onset_strength >= {strategy_params['onset_strength_min']}' condition")
    print(f"  in src/detection/confirm_detector.py -> _check_delta_confirmation()")
    print(f"  (Automatic modification skipped for safety)")

# 파일 정보 (Dual-file validation)
FILES = {
    "023790": {
        "path": project_root / "onset_detection/data/raw/023790_44indicators_realtime_20250901_clean.csv",
        "surges": [
            {"name": "Surge 1", "start": 1756688123304, "duration": 180000},
            {"name": "Surge 2", "start": 1756689969627, "duration": 180000}
        ]
    },
    "413630": {
        "path": project_root / "onset_detection/data/raw/413630_44indicators_realtime_20250911_clean.csv",
        "surges": [
            # TODO: 급등 구간 정보 입력 필요
        ]
    }
}

def prepare_dataframe(df):
    """DataFrame 전처리 (컬럼명 통일)"""
    rename_map = {}
    if 'time' in df.columns and 'ts' not in df.columns:
        rename_map['time'] = 'ts'
    if 'ret_accel' in df.columns and 'accel_1s' not in df.columns:
        rename_map['ret_accel'] = 'accel_1s'
    if 'current_price' in df.columns and 'price' not in df.columns:
        rename_map['current_price'] = 'price'

    if rename_map:
        df = df.rename(columns=rename_map)

    return df

def run_detection(file_key, file_info, config):
    """단일 파일 detection 실행"""
    print(f"\n{'='*70}")
    print(f"Processing: {file_key}")
    print(f"{'='*70}")

    # Load data
    data_path = file_info["path"]
    print(f"Loading: {data_path.name}")

    start_time = time.time()
    df = pd.read_csv(data_path)
    load_time = time.time() - start_time

    print(f"  Rows: {len(df):,}")
    print(f"  Load time: {load_time:.2f}s")

    # Prepare
    features_df = prepare_dataframe(df)

    # Run pipeline
    print(f"\nRunning pipeline...")
    pipeline_start = time.time()
    pipeline = OnsetPipelineDF(config=config)
    result = pipeline.run_batch(features_df)
    pipeline_time = time.time() - pipeline_start

    alerts = result.get('alerts', [])

    print(f"  Candidates: {result.get('candidates_count', 0):,}")
    print(f"  Confirmed: {result.get('confirmed_count', 0):,}")
    print(f"  Final alerts: {len(alerts)}")
    print(f"  Pipeline time: {pipeline_time:.2f}s")

    # Calculate metrics
    start_ts = features_df['ts'].min()
    end_ts = features_df['ts'].max()
    duration_hours = (end_ts - start_ts) / (1000 * 3600)
    fp_per_hour = len(alerts) / duration_hours

    # Recall calculation
    surges = file_info.get("surges", [])
    detected_surges = []

    for surge in surges:
        surge_start = surge["start"]
        surge_end = surge_start + surge["duration"]

        count = sum(1 for e in alerts
                   if surge_start - 30000 <= e['ts'] <= surge_end)
        detected = count > 0

        detected_surges.append({
            "name": surge["name"],
            "detected": detected,
            "count": count
        })

    recall = sum(1 for s in detected_surges if s["detected"]) / len(surges) if surges else None

    # Results
    metrics = {
        "file": file_key,
        "rows": len(df),
        "duration_hours": duration_hours,
        "load_time": load_time,
        "pipeline_time": pipeline_time,
        "candidates": result.get('candidates_count', 0),
        "confirmed": result.get('confirmed_count', 0),
        "alerts": len(alerts),
        "fp_per_hour": fp_per_hour,
        "recall": recall,
        "surges": detected_surges
    }

    # Print summary
    print(f"\nMetrics:")
    print(f"  Duration: {duration_hours:.2f}h")
    print(f"  FP/h: {fp_per_hour:.1f}")
    if recall is not None:
        print(f"  Recall: {recall*100:.0f}% ({sum(1 for s in detected_surges if s['detected'])}/{len(surges)})")

        for surge in detected_surges:
            status = "DETECTED" if surge["detected"] else "MISSED"
            print(f"    {surge['name']}: {status} ({surge['count']} alerts)")
    else:
        print(f"  Recall: N/A (no surge info)")

    return metrics, alerts

# Detection 재실행 (Dual files)
print(f"\n{'='*70}")
print("Detection Re-run (Strategy C+)")
print(f"{'='*70}")

config = load_config()
all_metrics = {}
all_alerts = {}

for file_key, file_info in FILES.items():
    try:
        metrics, alerts = run_detection(file_key, file_info, config)
        all_metrics[file_key] = metrics
        all_alerts[file_key] = alerts
    except Exception as e:
        print(f"\nError processing {file_key}: {e}")
        import traceback
        traceback.print_exc()
        continue

# 결과 저장
output_dir = project_root / "onset_detection/data/events"
output_dir.mkdir(parents=True, exist_ok=True)

for file_key, alerts in all_alerts.items():
    output_path = output_dir / f"strategy_c_plus_{file_key}.jsonl"
    with open(output_path, 'w') as f:
        for event in alerts:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(f"\nSaved {file_key} events: {output_path}")

# Summary 저장
summary = {
    "strategy": "D",
    "strategy_params": strategy_params,
    "files": all_metrics
}

reports_dir = project_root / "onset_detection/reports"
with open(reports_dir / "strategy_c_plus_dual_result.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n{'='*70}")
print("Dual-File Validation Complete")
print(f"{'='*70}")
print(f"\nResults saved: reports/strategy_c_plus_dual_result.json")
