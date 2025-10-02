#!/usr/bin/env python
"""
Candidate threshold 상향 시뮬레이션 스크립트
목적: 3축 동시 충족 + 강화된 threshold 적용 시 몇 개의 candidate가 남는지 확인
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.features.core_indicators import calculate_core_indicators

# 데이터 로드
data_path = project_root / "onset_detection/data/raw/023790_44indicators_realtime_20250901_clean.csv"
print(f"Loading data: {data_path}")
df = pd.read_csv(data_path)

# Rename time -> ts if needed
if 'time' in df.columns and 'ts' not in df.columns:
    df = df.rename(columns={'time': 'ts'})

# Features는 이미 계산되어 있음 (CSV에 포함)
print("Features already calculated in CSV")
features_df = df

# 현재 threshold
current_thresholds = {
    "ret_1s": 0.001,
    "z_vol_1s": 1.8,
    "spread_narrowing": 0.8
}

# 제안된 강화 threshold
proposed_thresholds = {
    "ret_1s": 0.002,
    "z_vol_1s": 2.5,
    "spread_narrowing": 0.6
}

# 알려진 급등 구간
surge1_start = 1756688123304  # ms
surge2_start = 1756689969627  # ms

def count_candidates_with_thresholds(df, thresholds, min_axes=2):
    """주어진 threshold로 candidate 개수 계산"""
    # Speed axis
    speed_ok = df['ret_1s'] > thresholds['ret_1s']

    # Participation axis
    participation_ok = df['z_vol_1s'] > thresholds['z_vol_1s']

    # Friction axis (spread narrowing)
    # spread_baseline = 현재 spread * 1.5 (간단 추정)
    df_copy = df.copy()
    df_copy['spread_baseline'] = df_copy['spread'] * 1.5
    friction_ok = df_copy['spread'] < (df_copy['spread_baseline'] * thresholds['spread_narrowing'])

    # min_axes 충족 여부
    axes_count = speed_ok.astype(int) + participation_ok.astype(int) + friction_ok.astype(int)
    candidates = df_copy[axes_count >= min_axes].copy()

    return candidates, axes_count

# 현재 설정 분석
print("=" * 60)
print("현재 Threshold 분석 (min_axes=2)")
print("=" * 60)
current_cands, current_axes = count_candidates_with_thresholds(features_df, current_thresholds, min_axes=2)
print(f"Candidates: {len(current_cands):,}개")

# 급등 구간 포함 여부
surge1_in = len(current_cands[current_cands['ts'].between(surge1_start - 30000, surge1_start + 30000)]) > 0
surge2_in = len(current_cands[current_cands['ts'].between(surge2_start - 30000, surge2_start + 30000)]) > 0
print(f"Surge 1 포함: {surge1_in}")
print(f"Surge 2 포함: {surge2_in}")

# 제안 설정 분석 (min_axes=2)
print("\n" + "=" * 60)
print("제안 Threshold 분석 (min_axes=2)")
print("=" * 60)
proposed_cands_2axes, proposed_axes_2 = count_candidates_with_thresholds(features_df, proposed_thresholds, min_axes=2)
print(f"Candidates: {len(proposed_cands_2axes):,}개 (감소율: {(1 - len(proposed_cands_2axes)/len(current_cands))*100:.1f}%)")

surge1_in = len(proposed_cands_2axes[proposed_cands_2axes['ts'].between(surge1_start - 30000, surge1_start + 30000)]) > 0
surge2_in = len(proposed_cands_2axes[proposed_cands_2axes['ts'].between(surge2_start - 30000, surge2_start + 30000)]) > 0
print(f"Surge 1 포함: {surge1_in}")
print(f"Surge 2 포함: {surge2_in}")

# 제안 설정 분석 (min_axes=3) - 핵심
print("\n" + "=" * 60)
print("제안 Threshold 분석 (min_axes=3) <- 핵심 설정")
print("=" * 60)
proposed_cands_3axes, proposed_axes_3 = count_candidates_with_thresholds(features_df, proposed_thresholds, min_axes=3)
print(f"Candidates: {len(proposed_cands_3axes):,}개 (감소율: {(1 - len(proposed_cands_3axes)/len(current_cands))*100:.1f}%)")

surge1_in = len(proposed_cands_3axes[proposed_cands_3axes['ts'].between(surge1_start - 30000, surge1_start + 30000)]) > 0
surge2_in = len(proposed_cands_3axes[proposed_cands_3axes['ts'].between(surge2_start - 30000, surge2_start + 30000)]) > 0
print(f"Surge 1 포함: {surge1_in}")
print(f"Surge 2 포함: {surge2_in}")

# 위험 경고
if not (surge1_in and surge2_in):
    print("\n⚠️ 경고: 급등 구간이 포함되지 않음! Threshold 완화 필요")
else:
    print("\n✅ 두 급등 구간 모두 포함됨. 안전하게 적용 가능")

# 결과 저장
summary = {
    "current_candidates": int(len(current_cands)),
    "proposed_2axes_candidates": int(len(proposed_cands_2axes)),
    "proposed_3axes_candidates": int(len(proposed_cands_3axes)),
    "reduction_rate_2axes": float(1 - len(proposed_cands_2axes)/len(current_cands)),
    "reduction_rate_3axes": float(1 - len(proposed_cands_3axes)/len(current_cands)),
    "surge1_included_3axes": bool(surge1_in),
    "surge2_included_3axes": bool(surge2_in)
}

import json
output_path = project_root / "onset_detection/reports/candidate_threshold_analysis.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n결과 저장: {output_path}")
