#!/usr/bin/env python3
"""
20개 급등 구간의 실제 피처값 추출 및 분석
목적: 탐지 실패 원인 규명
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import sys

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.features.core_indicators import calculate_core_indicators

# 라벨 로드
labels_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
with open(labels_path, encoding='utf-8') as f:
    labels = json.load(f)

# 검증 결과 로드
recall_path = project_root / "onset_detection/reports/batch_recall_results.json"
with open(recall_path, encoding='utf-8') as f:
    recall_results = json.load(f)

print("="*80)
print("급등 구간 피처 분석")
print("="*80)

analysis_results = []
data_dir = project_root / "onset_detection/data/raw"

for label in labels:
    file = label['file']
    stock_code = label['stock_code']
    surge_name = label['surge_name']
    strength = label['strength']
    start_ts = label['start_ts']
    end_ts = label['end_ts']

    # 탐지 여부 확인
    recall_info = next((r for r in recall_results['detection_results']
                       if r['file'] == file and r['surge_name'] == surge_name), None)
    detected = recall_info['detected'] if recall_info else False

    print(f"\n{'='*80}")
    print(f"파일: {file}")
    print(f"급등: {surge_name} ({strength}) - {'[OK] 탐지' if detected else '[MISS] 미탐지'}")
    print(f"{'='*80}")

    # 데이터 로드
    filepath = data_dir / file
    if not filepath.exists():
        print(f"[WARNING] 파일 없음: {filepath}")
        continue

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

    # 급등 구간 데이터 추출 (±30초 포함)
    window_start = start_ts - 30000
    window_end = end_ts + 30000

    surge_window = features_df[
        (features_df['ts'] >= window_start) &
        (features_df['ts'] <= window_end)
    ].copy()

    if surge_window.empty:
        print("[WARNING] 급등 구간 데이터 없음")
        continue

    # 핵심 지표 통계
    stats = {
        'ret_1s': {
            'mean': float(surge_window['ret_1s'].mean()),
            'median': float(surge_window['ret_1s'].median()),
            'max': float(surge_window['ret_1s'].max()),
            'p90': float(surge_window['ret_1s'].quantile(0.9)),
            'p95': float(surge_window['ret_1s'].quantile(0.95))
        },
        'z_vol_1s': {
            'mean': float(surge_window['z_vol_1s'].mean()),
            'median': float(surge_window['z_vol_1s'].median()),
            'max': float(surge_window['z_vol_1s'].max()),
            'p90': float(surge_window['z_vol_1s'].quantile(0.9))
        },
        'ticks_per_sec': {
            'mean': float(surge_window['ticks_per_sec'].mean()),
            'median': float(surge_window['ticks_per_sec'].median()),
            'max': float(surge_window['ticks_per_sec'].max())
        },
        'spread': {
            'mean': float(surge_window['spread'].mean()),
            'median': float(surge_window['spread'].median()),
            'min': float(surge_window['spread'].min())
        },
        'microprice_slope': {
            'mean': float(surge_window['microprice_slope'].mean()),
            'median': float(surge_window['microprice_slope'].median()),
            'max': float(surge_window['microprice_slope'].max())
        }
    }

    # 현재 임계값 기준 3축 충족률 계산
    ret_1s_pass = (surge_window['ret_1s'] > 0.002).sum()
    z_vol_pass = (surge_window['z_vol_1s'] > 2.5).sum()

    # Spread narrowing: 단순화 (spread < baseline * 0.6)
    baseline_spread = surge_window['spread'].mean()
    spread_pass = (surge_window['spread'] < baseline_spread * 0.6).sum()

    total_ticks = len(surge_window)

    axes_pass_rate = {
        'speed': float(ret_1s_pass / total_ticks if total_ticks > 0 else 0),
        'participation': float(z_vol_pass / total_ticks if total_ticks > 0 else 0),
        'friction': float(spread_pass / total_ticks if total_ticks > 0 else 0)
    }

    # 3축 동시 충족 (min_axes=3)
    both_pass = surge_window[
        (surge_window['ret_1s'] > 0.002) &
        (surge_window['z_vol_1s'] > 2.5) &
        (surge_window['spread'] < baseline_spread * 0.6)
    ]
    three_axes_rate = float(len(both_pass) / total_ticks if total_ticks > 0 else 0)

    # 2축 이상 충족 (min_axes=2)
    two_plus_axes = surge_window[
        ((surge_window['ret_1s'] > 0.002) & (surge_window['z_vol_1s'] > 2.5)) |
        ((surge_window['ret_1s'] > 0.002) & (surge_window['spread'] < baseline_spread * 0.6)) |
        ((surge_window['z_vol_1s'] > 2.5) & (surge_window['spread'] < baseline_spread * 0.6))
    ]
    two_axes_rate = float(len(two_plus_axes) / total_ticks if total_ticks > 0 else 0)

    print(f"\n[피처 통계]")
    print(f"  ret_1s: mean={stats['ret_1s']['mean']:.4f}, p90={stats['ret_1s']['p90']:.4f}, max={stats['ret_1s']['max']:.4f}")
    print(f"  z_vol_1s: mean={stats['z_vol_1s']['mean']:.2f}, p90={stats['z_vol_1s']['p90']:.2f}, max={stats['z_vol_1s']['max']:.2f}")
    print(f"  ticks_per_sec: mean={stats['ticks_per_sec']['mean']:.1f}, max={stats['ticks_per_sec']['max']:.0f}")
    print(f"  spread: mean={stats['spread']['mean']:.5f}, min={stats['spread']['min']:.5f}")

    print(f"\n[축별 충족률] (현재 임계값)")
    print(f"  Speed (ret_1s > 0.002): {axes_pass_rate['speed']*100:.1f}%")
    print(f"  Participation (z_vol > 2.5): {axes_pass_rate['participation']*100:.1f}%")
    print(f"  Friction (spread narrowing): {axes_pass_rate['friction']*100:.1f}%")

    print(f"\n[복합 충족률]")
    print(f"  3축 모두 (min_axes=3): {three_axes_rate*100:.1f}%")
    print(f"  2축 이상 (min_axes=2): {two_axes_rate*100:.1f}%")

    # 결과 저장
    analysis_results.append({
        'file': file,
        'surge_name': surge_name,
        'strength': strength,
        'detected': detected,
        'total_ticks': total_ticks,
        'stats': stats,
        'axes_pass_rate': axes_pass_rate,
        'three_axes_rate': three_axes_rate,
        'two_axes_rate': two_axes_rate
    })

# 전체 요약
print("\n" + "="*80)
print("전체 요약")
print("="*80)

# 탐지 vs 미탐지 비교
detected_surges = [r for r in analysis_results if r['detected']]
missed_surges = [r for r in analysis_results if not r['detected']]

print(f"\n탐지된 급등 ({len(detected_surges)}개):")
if detected_surges:
    print(f"  평균 ret_1s p90: {np.mean([r['stats']['ret_1s']['p90'] for r in detected_surges]):.4f}")
    print(f"  평균 z_vol p90: {np.mean([r['stats']['z_vol_1s']['p90'] for r in detected_surges]):.2f}")
    print(f"  평균 3축 충족률: {np.mean([r['three_axes_rate'] for r in detected_surges])*100:.1f}%")

print(f"\n미탐지 급등 ({len(missed_surges)}개):")
if missed_surges:
    print(f"  평균 ret_1s p90: {np.mean([r['stats']['ret_1s']['p90'] for r in missed_surges]):.4f}")
    print(f"  평균 z_vol p90: {np.mean([r['stats']['z_vol_1s']['p90'] for r in missed_surges]):.2f}")
    print(f"  평균 3축 충족률: {np.mean([r['three_axes_rate'] for r in missed_surges])*100:.1f}%")

# 강도별 분석
print(f"\n강도별 분석:")
for strength in ['강한', '중간', '약한']:
    strength_results = [r for r in analysis_results if r['strength'] == strength]
    if strength_results:
        avg_3axes = np.mean([r['three_axes_rate'] for r in strength_results])
        avg_2axes = np.mean([r['two_axes_rate'] for r in strength_results])
        print(f"  {strength}: 3축={avg_3axes*100:.1f}%, 2축+={avg_2axes*100:.1f}%")

# 저장
output_path = project_root / "onset_detection/reports/surge_window_analysis.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(analysis_results, f, indent=2, ensure_ascii=False)

print(f"\n저장: {output_path.relative_to(project_root)}")
