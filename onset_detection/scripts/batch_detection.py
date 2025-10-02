#!/usr/bin/env python3
"""
12개 파일 배치 Detection
목적: 현재 설정으로 전체 파일 검증
"""

import pandas as pd
import json
from pathlib import Path
import sys

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.detection.onset_pipeline import OnsetPipelineDF
from onset_detection.src.features.core_indicators import calculate_core_indicators
from onset_detection.src.config_loader import load_config

# 라벨 로드
labels_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
with open(labels_path, encoding='utf-8') as f:
    labels = json.load(f)

# 파일 목록 추출 (중복 제거)
files = sorted(list(set([label['file'] for label in labels])))

print("="*60)
print(f"배치 Detection 실행 ({len(files)}개 파일)")
print("="*60)

config = load_config(project_root / "onset_detection/config/onset_default.yaml")
results_summary = []

for i, filename in enumerate(files, 1):
    print(f"\n[{i}/{len(files)}] {filename}")

    filepath = project_root / "onset_detection/data/raw" / filename
    if not filepath.exists():
        print(f"  [WARNING] 파일 없음, 건너뜀")
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
    if df.columns.tolist() == df.iloc[0].tolist():  # Header duplication check
        df = df[1:].reset_index(drop=True)
    if rename_map:
        df = df.rename(columns=rename_map)

    # Ensure ts is int64
    df['ts'] = df['ts'].astype('int64')

    # Features 이미 있는지 확인
    if 'ret_1s' in df.columns and 'z_vol_1s' in df.columns:
        print(f"  Features already present, using existing")
        features_df = df
    else:
        print(f"  Calculating features...")
        features_df = calculate_core_indicators(df)

    # Detection 실행
    pipeline = OnsetPipelineDF(config=config)
    result = pipeline.run_batch(features_df)

    # alerts 리스트 추출
    confirmed = result.get('alerts', [])

    # 결과 저장
    stock_code = filename.split('_')[0]
    date = filename.split('_')[-2]  # 20250901 형식
    output_file = f"strategy_c_plus_{stock_code}_{date}.jsonl"
    output_path = project_root / "onset_detection/data/events/batch" / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for event in confirmed:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')

    # 통계
    duration_ms = df['ts'].max() - df['ts'].min()
    duration_hours = duration_ms / (1000 * 3600)
    fp_per_hour = len(confirmed) / duration_hours if duration_hours > 0 else 0

    print(f"  Candidates: {result.get('candidates_count', 0)}")
    print(f"  Confirmed: {len(confirmed)}개")
    print(f"  Duration: {duration_hours:.2f}h")
    print(f"  FP/h: {fp_per_hour:.1f}")

    results_summary.append({
        "file": filename,
        "confirmed": len(confirmed),
        "fp_per_hour": fp_per_hour,
        "duration_hours": duration_hours
    })

# 전체 요약
print("\n" + "="*60)
print("배치 실행 완료")
print("="*60)

total_confirmed = sum([r['confirmed'] for r in results_summary])
total_hours = sum([r['duration_hours'] for r in results_summary])
avg_fp_per_hour = total_confirmed / total_hours if total_hours > 0 else 0

print(f"\n총 파일: {len(results_summary)}개")
print(f"총 Confirmed: {total_confirmed}개")
print(f"총 시간: {total_hours:.1f}시간")
print(f"평균 FP/h: {avg_fp_per_hour:.1f}")

# 저장
summary_path = project_root / "onset_detection/reports/batch_detection_summary.json"
summary_path.parent.mkdir(parents=True, exist_ok=True)

with open(summary_path, "w", encoding='utf-8') as f:
    json.dump({
        "files": results_summary,
        "summary": {
            "total_files": len(results_summary),
            "total_confirmed": total_confirmed,
            "total_hours": total_hours,
            "avg_fp_per_hour": avg_fp_per_hour
        }
    }, f, indent=2, ensure_ascii=False)

print(f"\n결과 저장: {summary_path.relative_to(project_root)}")
