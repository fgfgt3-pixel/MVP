#!/usr/bin/env python
"""
타이밍 불일치 원인 조사
목적: 왜 413630은 느린지, 023790과 무엇이 다른지 파악
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def analyze_surge_characteristics(df, surge_start, surge_end, surge_name):
    """급등 구간의 특성 분석"""

    # 급등 구간 데이터
    surge_df = df[(df['ts'] >= surge_start) & (df['ts'] <= surge_end)].copy()

    if surge_df.empty:
        return None

    # 급등 전 30초 (베이스라인)
    baseline_df = df[(df['ts'] >= surge_start - 30000) & (df['ts'] < surge_start)].copy()

    print(f"\n{'='*70}")
    print(f"{surge_name} Characteristics")
    print(f"{'='*70}")

    # 기본 통계
    print(f"\n### Basic Statistics")
    duration_s = (surge_end - surge_start) / 1000
    price_change_pct = (surge_df['price'].iloc[-1] / surge_df['price'].iloc[0] - 1) * 100

    print(f"Duration: {duration_s:.1f}s")
    print(f"Total ticks: {len(surge_df)}")
    print(f"Price change: {price_change_pct:+.2f}%")

    # 초당 틱 수
    surge_df['second'] = (surge_df['ts'] // 1000)
    ticks_per_sec = surge_df.groupby('second').size()

    print(f"\n### Ticks per Second")
    print(f"Mean: {ticks_per_sec.mean():.1f}")
    print(f"Median: {ticks_per_sec.median():.1f}")
    print(f"Min: {ticks_per_sec.min()}")
    print(f"Max: {ticks_per_sec.max()}")

    # ret_1s 분석
    print(f"\n### ret_1s (Return)")
    print(f"Mean: {surge_df['ret_1s'].mean():.6f}")
    print(f"Median: {surge_df['ret_1s'].median():.6f}")
    print(f"P90: {surge_df['ret_1s'].quantile(0.9):.6f}")
    print(f"Max: {surge_df['ret_1s'].max():.6f}")

    # z_vol_1s 분석
    if 'z_vol_1s' in surge_df.columns:
        print(f"\n### z_vol_1s (Volume Z-score)")
        print(f"Mean: {surge_df['z_vol_1s'].mean():.2f}")
        print(f"Median: {surge_df['z_vol_1s'].median():.2f}")
        print(f"P90: {surge_df['z_vol_1s'].quantile(0.9):.2f}")
        print(f"Max: {surge_df['z_vol_1s'].max():.2f}")

    # Candidate 조건 충족률 (초기 30초)
    early_surge = surge_df[surge_df['ts'] <= surge_start + 30000]

    all_3_ok = 0
    if not early_surge.empty:
        print(f"\n### Early 30s Candidate Condition Satisfaction")

        # Speed axis
        speed_ok = (early_surge['ret_1s'] > 0.002).sum()
        print(f"Speed (ret_1s > 0.002): {speed_ok}/{len(early_surge)} ({speed_ok/len(early_surge)*100:.1f}%)")

        # Participation axis
        if 'z_vol_1s' in early_surge.columns:
            participation_ok = (early_surge['z_vol_1s'] > 2.5).sum()
            print(f"Participation (z_vol > 2.5): {participation_ok}/{len(early_surge)} ({participation_ok/len(early_surge)*100:.1f}%)")

        # 2축 동시 충족 (min_axes=2)
        if 'z_vol_1s' in early_surge.columns:
            two_axes_ok = ((early_surge['ret_1s'] > 0.002) |
                          (early_surge['z_vol_1s'] > 2.5)).sum()
            print(f"2-axis OR: {two_axes_ok}/{len(early_surge)} ({two_axes_ok/len(early_surge)*100:.1f}%)")

            # 2축 동시 AND
            all_2_ok = ((early_surge['ret_1s'] > 0.002) &
                       (early_surge['z_vol_1s'] > 2.5)).sum()
            print(f"2-axis AND: {all_2_ok}/{len(early_surge)} ({all_2_ok/len(early_surge)*100:.1f}%)")
            all_3_ok = all_2_ok  # Use as proxy for trigger rate

    # Baseline 대비 변화
    if not baseline_df.empty:
        print(f"\n### Change from Baseline")

        baseline_tps = baseline_df.groupby(baseline_df['ts'] // 1000).size().mean()
        surge_tps = ticks_per_sec.mean()
        print(f"Ticks/sec: {baseline_tps:.1f} -> {surge_tps:.1f} ({(surge_tps/baseline_tps-1)*100:+.1f}%)")

        if 'z_vol_1s' in baseline_df.columns and 'z_vol_1s' in surge_df.columns:
            baseline_zvol = baseline_df['z_vol_1s'].median()
            surge_zvol = surge_df['z_vol_1s'].median()
            print(f"z_vol: {baseline_zvol:.2f} -> {surge_zvol:.2f} ({surge_zvol - baseline_zvol:+.2f})")

    return {
        "duration_s": duration_s,
        "total_ticks": len(surge_df),
        "price_change_pct": price_change_pct,
        "ticks_per_sec_mean": float(ticks_per_sec.mean()),
        "ret_1s_mean": float(surge_df['ret_1s'].mean()),
        "ret_1s_p90": float(surge_df['ret_1s'].quantile(0.9)),
        "z_vol_mean": float(surge_df['z_vol_1s'].mean()) if 'z_vol_1s' in surge_df.columns else None,
        "early_2axes_rate": float(all_3_ok / len(early_surge)) if not early_surge.empty else 0
    }

# 023790 분석
print("\n" + "="*70)
print("023790 Surge Analysis")
print("="*70)

df_023790 = pd.read_csv(project_root / "onset_detection/data/raw/023790_44indicators_realtime_20250901_clean.csv")

# Column normalization
rename_map = {}
if 'time' in df_023790.columns:
    rename_map['time'] = 'ts'
if 'current_price' in df_023790.columns:
    rename_map['current_price'] = 'price'
if 'ret_accel' in df_023790.columns:
    rename_map['ret_accel'] = 'accel_1s'

if rename_map:
    df_023790 = df_023790.rename(columns=rename_map)

# File already has features calculated, no need to call calculate_core_indicators

surges_023790 = [
    {"name": "Surge1", "start": 1756688123304, "end": 1756688123304 + 180000},
    {"name": "Surge2", "start": 1756689969627, "end": 1756689969627 + 180000}
]

results_023790 = []
for surge in surges_023790:
    result = analyze_surge_characteristics(
        df_023790,
        surge['start'],
        surge['end'],
        surge['name']
    )
    if result:
        results_023790.append(result)

# 413630 분석
print("\n" + "="*70)
print("413630 Surge Analysis")
print("="*70)

df_413630 = pd.read_csv(project_root / "onset_detection/data/raw/413630_44indicators_realtime_20250911_clean.csv")

# Column normalization
rename_map = {}
if 'time' in df_413630.columns:
    rename_map['time'] = 'ts'
if 'current_price' in df_413630.columns:
    rename_map['current_price'] = 'price'
if 'ret_accel' in df_413630.columns:
    rename_map['ret_accel'] = 'accel_1s'

if rename_map:
    df_413630 = df_413630.rename(columns=rename_map)

# File already has features calculated, no need to call calculate_core_indicators

# 시작 시점 계산
first_ts = df_413630['ts'].min()
first_dt = pd.to_datetime(first_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')

surge_times = [
    ("09:09", 360000, "Surge1"),  # 6분
    ("10:01", 780000, "Surge2"),  # 13분
    ("11:46", 240000, "Surge3"),  # 4분
    ("13:29", 480000, "Surge4"),  # 8분
    ("14:09", 180000, "Surge5")   # 3분
]

surges_413630 = []
for time_str, duration_ms, name in surge_times:
    hour, minute = map(int, time_str.split(':'))
    surge_dt = first_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    surge_start = int(surge_dt.timestamp() * 1000)
    surge_end = surge_start + duration_ms
    surges_413630.append({"name": name, "start": surge_start, "end": surge_end})

results_413630 = []
for surge in surges_413630:
    result = analyze_surge_characteristics(
        df_413630,
        surge['start'],
        surge['end'],
        surge['name']
    )
    if result:
        results_413630.append(result)

# 비교 분석
print("\n" + "="*70)
print("023790 vs 413630 Comparison")
print("="*70)

print(f"\n### Average Characteristics")

avg_023790 = {
    "ticks_per_sec": np.mean([r['ticks_per_sec_mean'] for r in results_023790]),
    "ret_1s_p90": np.mean([r['ret_1s_p90'] for r in results_023790]),
    "z_vol_mean": np.mean([r['z_vol_mean'] for r in results_023790 if r['z_vol_mean']]),
    "early_2axes_rate": np.mean([r['early_2axes_rate'] for r in results_023790])
}

avg_413630 = {
    "ticks_per_sec": np.mean([r['ticks_per_sec_mean'] for r in results_413630]),
    "ret_1s_p90": np.mean([r['ret_1s_p90'] for r in results_413630]),
    "z_vol_mean": np.mean([r['z_vol_mean'] for r in results_413630 if r['z_vol_mean']]),
    "early_2axes_rate": np.mean([r['early_2axes_rate'] for r in results_413630])
}

print(f"\n023790 Average:")
print(f"  Ticks/sec: {avg_023790['ticks_per_sec']:.1f}")
print(f"  ret_1s P90: {avg_023790['ret_1s_p90']:.6f}")
print(f"  z_vol: {avg_023790['z_vol_mean']:.2f}")
print(f"  Early 2-axis AND rate: {avg_023790['early_2axes_rate']*100:.1f}%")

print(f"\n413630 Average:")
print(f"  Ticks/sec: {avg_413630['ticks_per_sec']:.1f}")
print(f"  ret_1s P90: {avg_413630['ret_1s_p90']:.6f}")
print(f"  z_vol: {avg_413630['z_vol_mean']:.2f}")
print(f"  Early 2-axis AND rate: {avg_413630['early_2axes_rate']*100:.1f}%")

# 핵심 발견
print("\n" + "="*70)
print("Key Findings")
print("="*70)

if avg_023790['early_2axes_rate'] > avg_413630['early_2axes_rate'] * 2:
    print(f"\nWARNING: 413630 early 30s 2-axis satisfaction is very low: {avg_413630['early_2axes_rate']*100:.1f}%")
    print(f"         (023790: {avg_023790['early_2axes_rate']*100:.1f}%)")
    print(f"         -> Gradual surge characteristics, hard to detect early")

if avg_413630['ticks_per_sec'] < avg_023790['ticks_per_sec'] * 0.7:
    print(f"\nWARNING: 413630 has lower tick density ({avg_413630['ticks_per_sec']:.1f} vs {avg_023790['ticks_per_sec']:.1f})")
    print(f"         -> Hard to satisfy Participation axis")

if avg_413630['ret_1s_p90'] < 0.002:
    print(f"\nWARNING: 413630 ret_1s P90 below threshold (0.002): {avg_413630['ret_1s_p90']:.6f}")
    print(f"         -> Hard to satisfy Speed axis")

# 결과 저장
summary = {
    "023790": {
        "avg_characteristics": avg_023790,
        "individual_surges": results_023790
    },
    "413630": {
        "avg_characteristics": avg_413630,
        "individual_surges": results_413630
    },
    "comparison": {
        "ticks_ratio": avg_413630['ticks_per_sec'] / avg_023790['ticks_per_sec'],
        "ret_ratio": avg_413630['ret_1s_p90'] / avg_023790['ret_1s_p90'],
        "zvol_ratio": avg_413630['z_vol_mean'] / avg_023790['z_vol_mean'],
        "early_detection_ratio": avg_413630['early_2axes_rate'] / avg_023790['early_2axes_rate'] if avg_023790['early_2axes_rate'] > 0 else 0
    }
}

reports_dir = project_root / "onset_detection/reports"
reports_dir.mkdir(exist_ok=True)
with open(reports_dir / "timing_discrepancy_analysis.json", "w", encoding='utf-8') as f:
    json.dump(summary, f, indent=2)

print(f"\nResults saved: reports/timing_discrepancy_analysis.json")
