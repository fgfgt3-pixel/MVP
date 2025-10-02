#!/usr/bin/env python
"""
2개 파일 병행 검증 스크립트
목적: 023790과 413630 파일로 전략 C 성능 비교
"""

import sys
from pathlib import Path
import pandas as pd
import json
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.detection.onset_pipeline import OnsetPipelineDF
from onset_detection.src.config_loader import load_config

# 파일 정보
FILES = {
    "023790": {
        "path": "onset_detection/data/raw/023790_44indicators_realtime_20250901_clean.csv",
        "surges": [
            {"name": "Surge 1", "start": 1756688123304, "duration": 180000},
            {"name": "Surge 2", "start": 1756689969627, "duration": 180000}
        ]
    },
    "413630": {
        "path": "onset_detection/data/raw/413630_44indicators_realtime_20250911_clean.csv",
        "surges": [
            # TODO: 급등 구간 정보 입력 필요
            # {"name": "Surge 1", "start": ?, "duration": 180000},
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
    data_path = project_root / file_info["path"]
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

    recall = sum(1 for s in detected_surges if s["detected"]) / len(surges) if surges else 0

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
    print(f"  Recall: {recall*100:.0f}% ({sum(1 for s in detected_surges if s['detected'])}/{len(surges)})")

    for surge in detected_surges:
        status = "DETECTED" if surge["detected"] else "MISSED"
        print(f"    {surge['name']}: {status} ({surge['count']} alerts)")

    return metrics, alerts

def main():
    print("="*70)
    print("2-File Validation: Strategy C")
    print("="*70)

    # Load config
    config = load_config()
    print(f"\nConfig:")
    print(f"  Candidate: ret_1s={config.onset.speed.ret_1s_threshold}, "
          f"z_vol={config.onset.participation.z_vol_threshold}")
    print(f"  Confirm: persistent_n={config.confirm.persistent_n}, "
          f"min_axes={config.confirm.min_axes}")
    print(f"  Refractory: {config.refractory.duration_s}s")

    # Run both files
    all_metrics = {}
    all_alerts = {}

    for file_key, file_info in FILES.items():
        try:
            metrics, alerts = run_detection(file_key, file_info, config)
            all_metrics[file_key] = metrics
            all_alerts[file_key] = alerts
        except Exception as e:
            print(f"\nError processing {file_key}: {e}")
            continue

    # Comparison summary
    print(f"\n{'='*70}")
    print("Comparison Summary")
    print(f"{'='*70}")

    print(f"\n{'Metric':<20} {'023790':<15} {'413630':<15} {'Status'}")
    print("-"*70)

    for metric in ["rows", "fp_per_hour", "recall"]:
        val1 = all_metrics.get("023790", {}).get(metric, 0)
        val2 = all_metrics.get("413630", {}).get(metric, 0)

        if metric == "rows":
            print(f"{metric:<20} {val1:<15,} {val2:<15,}")
        elif metric == "recall":
            status = "PASS" if val1 >= 0.65 and val2 >= 0.65 else "CHECK"
            print(f"{metric:<20} {val1*100:<15.0f}% {val2*100:<15.0f}% {status}")
        else:
            avg = (val1 + val2) / 2
            status = "PASS" if avg <= 30 else "HIGH"
            print(f"{metric:<20} {val1:<15.1f} {val2:<15.1f} {status}")

    # Save results
    output_path = project_root / "onset_detection/reports/dual_validation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(all_metrics, f, indent=2)

    print(f"\nResults saved: {output_path}")

    print(f"\n{'='*70}")
    print("Validation Complete")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
