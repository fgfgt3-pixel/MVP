#!/usr/bin/env python3
"""
Gate+Score 시스템 배치 테스트
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import sys

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.detection.gate_score_detector import GateScoreDetector
from onset_detection.src.features.core_indicators import calculate_core_indicators

# 라벨 로드
labels_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
with open(labels_path, encoding='utf-8') as f:
    labels = json.load(f)

files = sorted(list(set([label['file'] for label in labels])))

print("="*80)
print("Gate+Score 시스템 테스트")
print("="*80)

detector = GateScoreDetector()
results_summary = []
data_dir = project_root / "onset_detection/data/raw"

for i, filename in enumerate(files, 1):
    print(f"\n[{i}/{len(files)}] {filename}")

    filepath = data_dir / filename
    if not filepath.exists():
        print(f"  [WARNING] 파일 없음")
        continue

    # 데이터 로드
    df = pd.read_csv(filepath)

    # Column rename if needed
    rename_map = {}
    if 'time' in df.columns and 'ts' not in df.columns:
        rename_map['time'] = 'ts'
    if 'current_price' in df.columns and 'price' not in df.columns:
        rename_map['current_price'] = 'price'
    if 'ret_accel' in df.columns and 'accel_1s' not in df.columns:
        rename_map['ret_accel'] = 'accel_1s'
    if rename_map:
        df = df.rename(columns=rename_map)

    # Features 계산 (이미 있으면 skip)
    if 'ret_1s' in df.columns and 'z_vol_1s' in df.columns:
        features_df = df
    else:
        features_df = calculate_core_indicators(df)

    # Detection
    candidates = detector.detect_candidates(features_df)

    # 통계
    duration_ms = features_df['ts'].max() - features_df['ts'].min()
    duration_hours = duration_ms / (1000 * 3600)
    fp_per_hour = len(candidates) / duration_hours if duration_hours > 0 else 0

    print(f"  Candidates: {len(candidates)}개")
    print(f"  Duration: {duration_hours:.2f}h")
    print(f"  FP/h: {fp_per_hour:.1f}")

    # 이벤트 저장
    stock_code = filename.split('_')[0]
    date = filename.split('_')[-2]
    output_file = f"gate_score_{stock_code}_{date}.jsonl"
    output_path = project_root / "onset_detection/data/events/gate_score" / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for event in candidates:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')

    results_summary.append({
        "file": filename,
        "candidates": len(candidates),
        "fp_per_hour": fp_per_hour,
        "duration_hours": duration_hours
    })

# 전체 요약
print("\n" + "="*80)
print("전체 요약")
print("="*80)

total_candidates = sum([r['candidates'] for r in results_summary])
total_hours = sum([r['duration_hours'] for r in results_summary])
avg_fp = total_candidates / total_hours if total_hours > 0 else 0

print(f"\n총 파일: {len(results_summary)}개")
print(f"총 Candidates: {total_candidates}개")
print(f"총 시간: {total_hours:.1f}시간")
print(f"평균 FP/h: {avg_fp:.1f}")

# 저장
summary_path = project_root / "onset_detection/reports/gate_score_summary.json"
summary_path.parent.mkdir(parents=True, exist_ok=True)

with open(summary_path, "w", encoding='utf-8') as f:
    json.dump({
        "files": results_summary,
        "summary": {
            "total_files": len(results_summary),
            "total_candidates": total_candidates,
            "total_hours": total_hours,
            "avg_fp_per_hour": avg_fp
        }
    }, f, indent=2, ensure_ascii=False)

print(f"\n결과 저장: {summary_path.relative_to(project_root)}")
print("\n다음 단계: Recall 계산")
print("  python onset_detection/scripts/calculate_gate_score_recall.py")
