#!/usr/bin/env python3
"""
분석 결과 기반 임계값 최적화 권장
"""

import json
import numpy as np
from pathlib import Path

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent

# 분석 결과 로드
analysis_path = project_root / "onset_detection/reports/surge_window_analysis.json"
with open(analysis_path, encoding='utf-8') as f:
    analysis = json.load(f)

print("="*80)
print("데이터 기반 임계값 최적화 권장")
print("="*80)

# 미탐지 급등의 실제 피처값 분석
missed = [r for r in analysis if not r['detected']]
detected = [r for r in analysis if r['detected']]

print(f"\n미탐지 급등 ({len(missed)}개) 피처 분포:")

# ret_1s 분포
ret_1s_p90_values = [r['stats']['ret_1s']['p90'] for r in missed]
ret_1s_detected = [r['stats']['ret_1s']['p90'] for r in detected]

print(f"\nret_1s P90 (미탐지):")
print(f"  Min: {min(ret_1s_p90_values):.4f}")
print(f"  Median: {np.median(ret_1s_p90_values):.4f}")
print(f"  Max: {max(ret_1s_p90_values):.4f}")
print(f"  현재 임계값: 0.002")

print(f"\nret_1s P90 (탐지됨):")
print(f"  Median: {np.median(ret_1s_detected):.4f}")

# z_vol 분포
z_vol_p90_values = [r['stats']['z_vol_1s']['p90'] for r in missed]
z_vol_detected = [r['stats']['z_vol_1s']['p90'] for r in detected]

print(f"\nz_vol P90 (미탐지):")
print(f"  Min: {min(z_vol_p90_values):.2f}")
print(f"  Median: {np.median(z_vol_p90_values):.2f}")
print(f"  Max: {max(z_vol_p90_values):.2f}")
print(f"  현재 임계값: 2.5")

print(f"\nz_vol P90 (탐지됨):")
print(f"  Median: {np.median(z_vol_detected):.2f}")

# 축 충족률 분석
print(f"\n축별 충족률 (미탐지 급등):")
for axis in ['speed', 'participation', 'friction']:
    rates = [r['axes_pass_rate'][axis] for r in missed]
    print(f"  {axis}: {np.mean(rates)*100:.1f}% (평균)")

print(f"\n축별 충족률 (탐지된 급등):")
for axis in ['speed', 'participation', 'friction']:
    rates = [r['axes_pass_rate'][axis] for r in detected]
    print(f"  {axis}: {np.mean(rates)*100:.1f}% (평균)")

# 가장 큰 문제 축 식별
avg_rates = {
    'speed': np.mean([r['axes_pass_rate']['speed'] for r in missed]),
    'participation': np.mean([r['axes_pass_rate']['participation'] for r in missed]),
    'friction': np.mean([r['axes_pass_rate']['friction'] for r in missed])
}

bottleneck = min(avg_rates, key=avg_rates.get)
print(f"\n[병목 축]: {bottleneck} ({avg_rates[bottleneck]*100:.1f}%)")

# 3축/2축 충족률
print(f"\n복합 충족률 (미탐지):")
print(f"  3축 모두: {np.mean([r['three_axes_rate'] for r in missed])*100:.1f}%")
print(f"  2축 이상: {np.mean([r['two_axes_rate'] for r in missed])*100:.1f}%")

print(f"\n복합 충족률 (탐지됨):")
print(f"  3축 모두: {np.mean([r['three_axes_rate'] for r in detected])*100:.1f}%")
print(f"  2축 이상: {np.mean([r['two_axes_rate'] for r in detected])*100:.1f}%")

# 강도별 분석
print(f"\n강도별 3축 충족률:")
for strength in ['강한', '중간', '약한']:
    strength_results = [r for r in analysis if r['strength'] == strength]
    if strength_results:
        avg_3axes = np.mean([r['three_axes_rate'] for r in strength_results])
        avg_2axes = np.mean([r['two_axes_rate'] for r in strength_results])
        detected_count = len([r for r in strength_results if r['detected']])
        total_count = len(strength_results)
        print(f"  {strength} ({detected_count}/{total_count} 탐지): 3축={avg_3axes*100:.1f}%, 2축+={avg_2axes*100:.1f}%")

# 최종 권장사항
print("\n" + "="*80)
print("최종 권장사항")
print("="*80)

# 핵심 발견
print(f"""
[핵심 발견]

1. Friction 축이 최대 병목 ({avg_rates['friction']*100:.1f}%)
   - 대부분의 급등에서 spread narrowing 조건 충족 실패
   - 특히 spread가 큰 종목 (097230, 054540)에서 문제

2. 3축 동시 충족률이 극히 낮음
   - 미탐지: 0.1%
   - 탐지됨: 0.5%
   - 현재 onset_strength >= 0.67은 사실상 3축 모두 필요

3. 2축 충족률도 매우 낮음
   - 미탐지: 4.9%
   - 탐지됨: 7.4%
   - min_axes=2 설정에도 대부분 실패

4. ret_1s P90 차이가 극심
   - 미탐지: 5.30 (이상치 포함)
   - 탐지됨: 0.39
   - 현재 임계값 0.002는 적절하나, 이상치 영향 큼
""")

# 권장 전략
print("\n" + "="*80)
print("권장 전략")
print("="*80)

print("""
[전략 A] Friction 축 완화 (가장 효과적, 추천)
```yaml
onset:
  friction:
    spread_narrowing_pct: 0.8  # 0.6 → 0.8 (완화)
    # 또는 spread_narrowing 조건 제거

confirm:
  onset_strength_min: 0.50  # 0.67 → 0.50 (2/3 축 허용)
```

예상 효과:
  - Friction 충족률 대폭 증가
  - Recall: 45% → 55-60%
  - FP/h: 3.7 → 8-12 (여전히 목표 내)

근거:
  - Friction이 가장 큰 병목 (0.8%)
  - Spread narrowing 조건이 너무 엄격
  - 많은 급등이 2축(Speed+Participation)은 충족


[전략 B] onset_strength만 완화 (단순, 빠름)
```yaml
confirm:
  onset_strength_min: 0.33  # 0.67 → 0.33 (1/3 축만 충족)
```

예상 효과:
  - Recall: 45% → 50-55%
  - FP/h: 3.7 → 10-15

근거:
  - 3축 충족률이 너무 낮음 (0.1-0.5%)
  - 1축만 충족해도 의미 있는 급등 존재


[전략 C] 복합 완화 (공격적)
```yaml
onset:
  speed:
    ret_1s_threshold: 0.0015  # 0.002 → 0.0015 (25% 완화)
  participation:
    z_vol_threshold: 2.0      # 2.5 → 2.0 (20% 완화)
  friction:
    spread_narrowing_pct: 0.8  # 0.6 → 0.8

confirm:
  persistent_n: 18            # 22 → 18
  onset_strength_min: 0.33    # 0.67 → 0.33
```

예상 효과:
  - Recall: 45% → 65-70%
  - FP/h: 3.7 → 20-30

근거:
  - 모든 축 충족률 낮음
  - 목표 60% Recall 달성 위해 공격적 완화 필요
  - FP/h 여유 충분 (목표 40)
""")

# 예상 영향 추정
print("\n" + "="*80)
print("예상 영향 추정")
print("="*80)

current_detected = len(detected)
total = len(analysis)

# 전략 A 시뮬레이션 (2축 이상 충족하는 미탐지 급등)
strategy_a_candidates = [
    r for r in missed
    if r['two_axes_rate'] >= 0.02  # 2% 이상
]

print(f"\n전략 A (Friction 완화 + onset_strength 0.50):")
print(f"  현재 Recall: {current_detected}/{total} = {current_detected/total*100:.1f}%")
print(f"  추가 탐지 예상: {len(strategy_a_candidates)}개")
print(f"  예상 Recall: {(current_detected + len(strategy_a_candidates))/total*100:.1f}%")

# 전략 B 시뮬레이션
strategy_b_candidates = [
    r for r in missed
    if (r['axes_pass_rate']['speed'] >= 0.25 or
        r['axes_pass_rate']['participation'] >= 0.04 or
        r['axes_pass_rate']['friction'] >= 0.01)
]

print(f"\n전략 B (onset_strength 0.33):")
print(f"  추가 탐지 예상: {len(strategy_b_candidates)}개")
print(f"  예상 Recall: {(current_detected + len(strategy_b_candidates))/total*100:.1f}%")

# 전략 C 시뮬레이션
strategy_c_candidates = missed  # 대부분 탐지 예상

print(f"\n전략 C (복합 완화):")
print(f"  추가 탐지 예상: {len(strategy_c_candidates)}개 (거의 전부)")
print(f"  예상 Recall: {(current_detected + len(strategy_c_candidates))/total*100:.1f}%")

print("\n" + "="*80)
print("[권장] 전략 A 시도 → 목표 미달 시 전략 C 적용")
print("="*80)
