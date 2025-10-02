#!/usr/bin/env python
"""실제 급등 샘플 데이터 분석"""

import pandas as pd
import numpy as np

print("="*80)
print("Surge Sample Data Analysis")
print("="*80)

# 두 급등 구간 로드
surge1 = pd.read_csv('onset_detection/data/features/surge1_sample.csv')
surge2 = pd.read_csv('onset_detection/data/features/surge2_sample.csv')

print(f"\n[Data Size]")
print(f"  Surge 1: {len(surge1)} rows")
print(f"  Surge 2: {len(surge2)} rows")

# 급등 전 vs 급등 중 분리 (실제 라벨링 기반)
# Surge 1: row 439 (ts=1756688123304) 부터 급등 시작
# Surge 2: row 358 (ts=1756689969627) 부터 급등 시작
surge1_before = surge1.iloc[:439]
surge1_during = surge1.iloc[439:]

surge2_before = surge2.iloc[:358]
surge2_during = surge2.iloc[358:]

print(f"\n[Row Counts]")
print(f"  Surge 1 - Before: {len(surge1_before)}, During: {len(surge1_during)}")
print(f"  Surge 2 - Before: {len(surge2_before)}, During: {len(surge2_during)}")

# 핵심 지표 분석
key_features = ['ret_1s', 'accel_1s', 'z_vol_1s', 'ticks_per_sec', 'spread',
                'microprice_slope', 'imbalance_1s', 'OFI_1s']

def analyze_feature(df_before, df_during, feature_name, surge_num):
    """지표 통계 비교"""
    before = df_before[feature_name].dropna()
    during = df_during[feature_name].dropna()

    print(f"\n  {feature_name} (Surge {surge_num}):")
    print(f"    Before: mean={before.mean():.6f}, std={before.std():.6f}, "
          f"p50={before.median():.6f}, p90={before.quantile(0.9):.6f}, p95={before.quantile(0.95):.6f}")
    print(f"    During: mean={during.mean():.6f}, std={during.std():.6f}, "
          f"p50={during.median():.6f}, p90={during.quantile(0.9):.6f}, p95={during.quantile(0.95):.6f}")

    # 차이 (급등 중 - 급등 전)
    diff_mean = during.mean() - before.mean()
    diff_p50 = during.median() - before.median()
    diff_p90 = during.quantile(0.9) - before.quantile(0.9)

    print(f"    Delta: mean={diff_mean:.6f}, p50={diff_p50:.6f}, p90={diff_p90:.6f}")

    return {
        'before_mean': before.mean(),
        'before_p50': before.median(),
        'before_p90': before.quantile(0.9),
        'during_mean': during.mean(),
        'during_p50': during.median(),
        'during_p90': during.quantile(0.9),
        'delta_mean': diff_mean,
        'delta_p50': diff_p50,
        'delta_p90': diff_p90
    }

print(f"\n{'='*80}")
print(f"[Key Feature Comparison]")
print(f"{'='*80}")

# Surge 1 분석
print(f"\n[Surge 1 Analysis] (09:55-09:58)")
surge1_stats = {}
for feature in key_features:
    surge1_stats[feature] = analyze_feature(surge1_before, surge1_during, feature, 1)

# Surge 2 분석
print(f"\n[Surge 2 Analysis] (10:26-10:35)")
surge2_stats = {}
for feature in key_features:
    surge2_stats[feature] = analyze_feature(surge2_before, surge2_during, feature, 2)

# 권장 Threshold 계산
print(f"\n{'='*80}")
print(f"[Recommended Thresholds]")
print(f"{'='*80}")

def recommend_threshold(surge1_stats, surge2_stats, feature, percentile='p90'):
    """두 급등의 delta를 기반으로 threshold 추천"""
    s1_delta = surge1_stats[feature][f'delta_{percentile}']
    s2_delta = surge2_stats[feature][f'delta_{percentile}']

    # 두 급등 중 작은 값의 50-70%를 threshold로 설정 (보수적)
    min_delta = min(s1_delta, s2_delta)

    # 음수일 경우 처리
    if min_delta <= 0:
        threshold = min_delta * 0.3  # 음수는 30%만
    else:
        threshold = min_delta * 0.5  # 양수는 50%

    return threshold, s1_delta, s2_delta

print(f"\n[Detection Stage - Candidate]")
ret_threshold, s1_ret, s2_ret = recommend_threshold(surge1_stats, surge2_stats, 'ret_1s', 'p90')
zvol_threshold, s1_zvol, s2_zvol = recommend_threshold(surge1_stats, surge2_stats, 'z_vol_1s', 'p90')

print(f"  ret_1s_threshold:")
print(f"    Surge1 Delta-p90: {s1_ret:.6f}, Surge2 Delta-p90: {s2_ret:.6f}")
print(f"    Recommended: {ret_threshold:.6f} (50% of min)")

print(f"  z_vol_threshold:")
print(f"    Surge1 Delta-p90: {s1_zvol:.6f}, Surge2 Delta-p90: {s2_zvol:.6f}")
print(f"    Recommended: {zvol_threshold:.6f} (50% of min)")

print(f"\n[Confirmation Stage - Delta]")
ret_delta, _, _ = recommend_threshold(surge1_stats, surge2_stats, 'ret_1s', 'p50')
zvol_delta, _, _ = recommend_threshold(surge1_stats, surge2_stats, 'z_vol_1s', 'p50')
spread_delta, s1_spread, s2_spread = recommend_threshold(surge1_stats, surge2_stats, 'spread', 'p50')

print(f"  delta.ret_min: {ret_delta:.6f}")
print(f"  delta.zvol_min: {zvol_delta:.6f}")
print(f"  delta.spread_drop: {abs(spread_delta):.6f}")

# Persistent_n 권장
print(f"\n[Persistent_n Recommendation]")
ticks_1 = surge1_during['ticks_per_sec'].median()
ticks_2 = surge2_during['ticks_per_sec'].median()
print(f"  Surge 1 ticks/sec: {ticks_1:.1f}")
print(f"  Surge 2 ticks/sec: {ticks_2:.1f}")
print(f"  Average: {(ticks_1 + ticks_2) / 2:.1f}")

# 1초분의 틱 개수 기준
recommended_persistent = int((ticks_1 + ticks_2) / 2)
print(f"  Recommended persistent_n: {recommended_persistent} (1 second worth)")

# 급등 구간의 틱 밀도 분포
print(f"\n[Tick Density Distribution During Surge]")
print(f"  Surge 1:")
print(f"    min: {surge1_during['ticks_per_sec'].min()}")
print(f"    p25: {surge1_during['ticks_per_sec'].quantile(0.25):.1f}")
print(f"    p50: {surge1_during['ticks_per_sec'].median():.1f}")
print(f"    p75: {surge1_during['ticks_per_sec'].quantile(0.75):.1f}")
print(f"    p95: {surge1_during['ticks_per_sec'].quantile(0.95):.1f}")
print(f"    max: {surge1_during['ticks_per_sec'].max()}")

print(f"  Surge 2:")
print(f"    min: {surge2_during['ticks_per_sec'].min()}")
print(f"    p25: {surge2_during['ticks_per_sec'].quantile(0.25):.1f}")
print(f"    p50: {surge2_during['ticks_per_sec'].median():.1f}")
print(f"    p75: {surge2_during['ticks_per_sec'].quantile(0.75):.1f}")
print(f"    p95: {surge2_during['ticks_per_sec'].quantile(0.95):.1f}")
print(f"    max: {surge2_during['ticks_per_sec'].max()}")

# ret_1s 극단값 확인
print(f"\n[ret_1s Extreme Value Check]")
print(f"  Surge 1:")
print(f"    |ret_1s| > 0.01: {(surge1['ret_1s'].abs() > 0.01).sum()} / {len(surge1)} ({(surge1['ret_1s'].abs() > 0.01).mean()*100:.1f}%)")
print(f"    |ret_1s| > 0.1: {(surge1['ret_1s'].abs() > 0.1).sum()} / {len(surge1)}")
print(f"  Surge 2:")
print(f"    |ret_1s| > 0.01: {(surge2['ret_1s'].abs() > 0.01).sum()} / {len(surge2)} ({(surge2['ret_1s'].abs() > 0.01).mean()*100:.1f}%)")
print(f"    |ret_1s| > 0.1: {(surge2['ret_1s'].abs() > 0.1).sum()} / {len(surge2)}")

# 최종 권장 Config
print(f"\n{'='*80}")
print(f"[Final Recommended Config]")
print(f"{'='*80}")

print(f"""
onset:
  speed:
    ret_1s_threshold: {max(0.0005, ret_threshold):.4f}  # 최소 0.0005
  participation:
    z_vol_threshold: {max(1.0, zvol_threshold):.2f}      # 최소 1.0
  friction:
    spread_narrowing_pct: 0.8                              # 유지

detection:
  min_axes_required: 2  # 2축 필수 (FP 감소)

confirm:
  window_s: 15
  persistent_n: {max(3, recommended_persistent)}         # 최소 3
  require_price_axis: true
  min_axes: 2           # 2축 필수 (FP 감소)

  delta:
    ret_min: {max(0.0005, ret_delta):.4f}      # 최소 0.0005
    zvol_min: {max(0.3, zvol_delta):.2f}       # 최소 0.3
    spread_drop: {max(0.0005, abs(spread_delta)):.4f}  # 최소 0.0005
""")

print(f"\n{'='*80}")
print(f"Analysis Complete")
print(f"{'='*80}")
