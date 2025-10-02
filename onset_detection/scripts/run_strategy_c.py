#!/usr/bin/env python
"""
전략 C Detection 실행 스크립트
목적: 수정된 파라미터로 전체 파이프라인 실행
"""

import sys
from pathlib import Path
import pandas as pd
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.detection.onset_pipeline import OnsetPipelineDF
from onset_detection.src.config_loader import load_config

print("=" * 70)
print("전략 C Detection Pipeline 실행")
print("=" * 70)

# 1. 데이터 로드
data_path = project_root / "onset_detection/data/raw/023790_44indicators_realtime_20250901_clean.csv"
print(f"\n데이터 로드: {data_path.name}")
df = pd.read_csv(data_path)

# Rename columns to match expected names
rename_map = {}
if 'time' in df.columns and 'ts' not in df.columns:
    rename_map['time'] = 'ts'
if 'ret_accel' in df.columns and 'accel_1s' not in df.columns:
    rename_map['ret_accel'] = 'accel_1s'
if 'current_price' in df.columns and 'price' not in df.columns:
    rename_map['current_price'] = 'price'

if rename_map:
    df = df.rename(columns=rename_map)
    print(f"  Renamed columns: {rename_map}")

print(f"  Total rows: {len(df):,}")
print(f"  Columns: {len(df.columns)}")

# Features는 이미 계산되어 있음
features_df = df

# 2. Config 로드
print("\nConfig 로드...")
config = load_config()
print(f"  Candidate threshold:")
print(f"    ret_1s: {config.onset.speed.ret_1s_threshold}")
print(f"    z_vol: {config.onset.participation.z_vol_threshold}")
print(f"    spread_narrowing: {config.onset.friction.spread_narrowing_pct}")
print(f"  Confirmation:")
print(f"    persistent_n: {config.confirm.persistent_n}")
print(f"    min_axes: {config.confirm.min_axes}")
print(f"    require_price_axis: {config.confirm.require_price_axis}")
print(f"  Refractory: {config.refractory.duration_s}s")

# 3. Pipeline 실행
print("\n" + "=" * 70)
print("Pipeline 실행 중...")
print("=" * 70)

pipeline = OnsetPipelineDF(config=config)
result = pipeline.run_batch(features_df)

# 4. 결과 출력
alerts = result.get('alerts', [])
print(f"\n결과:")
print(f"  Candidates: {result.get('candidates_count', 0)}개")
print(f"  Confirmed: {result.get('confirmed_count', 0)}개")
print(f"  Rejected (refractory): {result.get('rejected_count', 0)}개")
print(f"  Final alerts: {len(alerts)}개")

# 5. 이벤트 저장
output_path = project_root / "onset_detection/data/events/strategy_c_results.jsonl"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w') as f:
    for event in alerts:
        f.write(json.dumps(event) + '\n')

print(f"\n이벤트 저장: {output_path}")

# 6. 간단한 통계
if alerts:
    print(f"\n상위 5개 alerts:")
    for i, event in enumerate(alerts[:5], 1):
        print(f"  {i}. ts={event.get('ts')}, stock={event.get('stock_code')}")

print("\n" + "=" * 70)
print("완료!")
print("=" * 70)
