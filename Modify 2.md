동의합니다. 수치 조정보다 **데이터 기반 분석**이 우선입니다.

---

## 📊 Phase 1.5 데이터 분석 작업 지시서

### 🎯 분석 목적
현재 놓친 11개 급등(55%)의 **실제 특성**을 파악하여:
1. **왜 놓쳤는지** 근본 원인 규명
2. **어떤 축이 부족했는지** 정량 분석
3. **Threshold를 어떻게 조정해야 하는지** 데이터 기반 결정

---

## 📋 작업 지시: Claude Code 실행

### Step 1: 급등 구간 피처 추출 스크립트

```python
# 파일: scripts/analyze_surge_windows.py

"""
21개 급등 구간의 실제 피처값 추출 및 분석
목적: 탐지 실패 원인 규명
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from onset_detection.src.features.core_indicators import calculate_core_indicators

# 라벨 로드
with open("data/labels/all_surge_labels.json") as f:
    labels = json.load(f)

# 검증 결과 로드
with open("reports/batch_recall_results.json") as f:
    recall_results = json.load(f)

print("="*80)
print("급등 구간 피처 분석")
print("="*80)

analysis_results = []

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
    print(f"급등: {surge_name} ({strength}) - {'✅ 탐지' if detected else '❌ 미탐지'}")
    print(f"{'='*80}")
    
    # 데이터 로드
    filepath = Path("data/raw") / file
    if not filepath.exists():
        print(f"⚠️ 파일 없음: {filepath}")
        continue
    
    df = pd.read_csv(filepath)
    features_df = calculate_core_indicators(df)
    
    # 급등 구간 데이터 추출 (±30초 포함)
    window_start = start_ts - 30000
    window_end = end_ts + 30000
    
    surge_window = features_df[
        (features_df['ts'] >= window_start) & 
        (features_df['ts'] <= window_end)
    ].copy()
    
    if surge_window.empty:
        print("⚠️ 급등 구간 데이터 없음")
        continue
    
    # 핵심 지표 통계
    stats = {
        'ret_1s': {
            'mean': surge_window['ret_1s'].mean(),
            'median': surge_window['ret_1s'].median(),
            'max': surge_window['ret_1s'].max(),
            'p90': surge_window['ret_1s'].quantile(0.9),
            'p95': surge_window['ret_1s'].quantile(0.95)
        },
        'z_vol_1s': {
            'mean': surge_window['z_vol_1s'].mean(),
            'median': surge_window['z_vol_1s'].median(),
            'max': surge_window['z_vol_1s'].max(),
            'p90': surge_window['z_vol_1s'].quantile(0.9)
        },
        'ticks_per_sec': {
            'mean': surge_window['ticks_per_sec'].mean(),
            'median': surge_window['ticks_per_sec'].median(),
            'max': surge_window['ticks_per_sec'].max()
        },
        'spread': {
            'mean': surge_window['spread'].mean(),
            'median': surge_window['spread'].median(),
            'min': surge_window['spread'].min()
        },
        'microprice_slope': {
            'mean': surge_window['microprice_slope'].mean(),
            'median': surge_window['microprice_slope'].median(),
            'max': surge_window['microprice_slope'].max()
        }
    }
    
    # 현재 임계값 기준 3축 충족률 계산
    ret_1s_pass = (surge_window['ret_1s'] > 0.002).sum()
    z_vol_pass = (surge_window['z_vol_1s'] > 2.5).sum()
    
    # Spread narrowing: 단순화 (spread < baseline * 0.6)
    # baseline = mean spread
    baseline_spread = surge_window['spread'].mean()
    spread_pass = (surge_window['spread'] < baseline_spread * 0.6).sum()
    
    total_ticks = len(surge_window)
    
    axes_pass_rate = {
        'speed': ret_1s_pass / total_ticks if total_ticks > 0 else 0,
        'participation': z_vol_pass / total_ticks if total_ticks > 0 else 0,
        'friction': spread_pass / total_ticks if total_ticks > 0 else 0
    }
    
    # 3축 동시 충족 (min_axes=3)
    both_pass = surge_window[
        (surge_window['ret_1s'] > 0.002) &
        (surge_window['z_vol_1s'] > 2.5) &
        (surge_window['spread'] < baseline_spread * 0.6)
    ]
    three_axes_rate = len(both_pass) / total_ticks if total_ticks > 0 else 0
    
    # 2축 이상 충족 (min_axes=2)
    two_plus_axes = surge_window[
        ((surge_window['ret_1s'] > 0.002) & (surge_window['z_vol_1s'] > 2.5)) |
        ((surge_window['ret_1s'] > 0.002) & (surge_window['spread'] < baseline_spread * 0.6)) |
        ((surge_window['z_vol_1s'] > 2.5) & (surge_window['spread'] < baseline_spread * 0.6))
    ]
    two_axes_rate = len(two_plus_axes) / total_ticks if total_ticks > 0 else 0
    
    print(f"\n📊 피처 통계:")
    print(f"  ret_1s: mean={stats['ret_1s']['mean']:.4f}, p90={stats['ret_1s']['p90']:.4f}, max={stats['ret_1s']['max']:.4f}")
    print(f"  z_vol_1s: mean={stats['z_vol_1s']['mean']:.2f}, p90={stats['z_vol_1s']['p90']:.2f}, max={stats['z_vol_1s']['max']:.2f}")
    print(f"  ticks_per_sec: mean={stats['ticks_per_sec']['mean']:.1f}, max={stats['ticks_per_sec']['max']:.0f}")
    print(f"  spread: mean={stats['spread']['mean']:.5f}, min={stats['spread']['min']:.5f}")
    
    print(f"\n🎯 축별 충족률 (현재 임계값):")
    print(f"  Speed (ret_1s > 0.002): {axes_pass_rate['speed']*100:.1f}%")
    print(f"  Participation (z_vol > 2.5): {axes_pass_rate['participation']*100:.1f}%")
    print(f"  Friction (spread narrowing): {axes_pass_rate['friction']*100:.1f}%")
    
    print(f"\n⚡ 복합 충족률:")
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
output_path = Path("reports/surge_window_analysis.json")
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(analysis_results, f, indent=2, ensure_ascii=False)

print(f"\n💾 저장: {output_path}")
```

---

### Step 2: 임계값 최적화 권장

```python
# 파일: scripts/recommend_thresholds.py

"""
분석 결과 기반 임계값 최적화 권장
"""

import json
import numpy as np
from pathlib import Path

# 분석 결과 로드
with open("reports/surge_window_analysis.json") as f:
    analysis = json.load(f)

print("="*80)
print("데이터 기반 임계값 최적화 권장")
print("="*80)

# 미탐지 급등의 실제 피처값 분석
missed = [r for r in analysis if not r['detected']]

print(f"\n미탐지 급등 ({len(missed)}개) 피처 분포:")

# ret_1s 분포
ret_1s_p90_values = [r['stats']['ret_1s']['p90'] for r in missed]
print(f"\nret_1s P90:")
print(f"  Min: {min(ret_1s_p90_values):.4f}")
print(f"  Median: {np.median(ret_1s_p90_values):.4f}")
print(f"  Max: {max(ret_1s_p90_values):.4f}")
print(f"  현재 임계값: 0.002")
print(f"  → 권장: {np.median(ret_1s_p90_values) * 0.8:.4f} (median의 80%)")

# z_vol 분포
z_vol_p90_values = [r['stats']['z_vol_1s']['p90'] for r in missed]
print(f"\nz_vol P90:")
print(f"  Min: {min(z_vol_p90_values):.2f}")
print(f"  Median: {np.median(z_vol_p90_values):.2f}")
print(f"  Max: {max(z_vol_p90_values):.2f}")
print(f"  현재 임계값: 2.5")
print(f"  → 권장: {np.median(z_vol_p90_values) * 0.8:.2f} (median의 80%)")

# 축 충족률 분석
print(f"\n축별 충족률 (미탐지 급등):")
for axis in ['speed', 'participation', 'friction']:
    rates = [r['axes_pass_rate'][axis] for r in missed]
    print(f"  {axis}: {np.mean(rates)*100:.1f}% (평균)")

# 가장 큰 문제 축 식별
avg_rates = {
    'speed': np.mean([r['axes_pass_rate']['speed'] for r in missed]),
    'participation': np.mean([r['axes_pass_rate']['participation'] for r in missed]),
    'friction': np.mean([r['axes_pass_rate']['friction'] for r in missed])
}

bottleneck = min(avg_rates, key=avg_rates.get)
print(f"\n🔴 병목 축: {bottleneck} ({avg_rates[bottleneck]*100:.1f}%)")

# 최종 권장사항
print("\n" + "="*80)
print("최종 권장사항")
print("="*80)

recommended_ret = np.median(ret_1s_p90_values) * 0.8
recommended_zvol = np.median(z_vol_p90_values) * 0.8

print(f"""
옵션 1: 보수적 완화 (Recall +10-15% 예상)
```yaml
onset:
  speed:
    ret_1s_threshold: {recommended_ret:.4f}  # 현재 0.002
  participation:
    z_vol_threshold: {recommended_zvol:.2f}  # 현재 2.5

confirm:
  onset_strength_min: 0.50  # 현재 0.67
```

옵션 2: 적극적 완화 (Recall +20-25% 예상)
```yaml
onset:
  speed:
    ret_1s_threshold: {recommended_ret * 0.9:.4f}
  participation:
    z_vol_threshold: {recommended_zvol * 0.85:.2f}

detection:
  min_axes_required: 2  # 현재 2 (유지)

confirm:
  onset_strength_min: 0.33  # 1/3 축만 충족
  persistent_n: 18  # 현재 22 (완화)
```
""")

# 예상 영향 추정
current_detected = len([r for r in analysis if r['detected']])
total = len(analysis)

if recommended_ret < 0.002 or recommended_zvol < 2.5:
    additional = len([
        r for r in missed 
        if (r['stats']['ret_1s']['p90'] >= recommended_ret or
            r['stats']['z_vol_1s']['p90'] >= recommended_zvol)
    ])
    
    new_recall = (current_detected + additional) / total
    print(f"\n예상 효과 (옵션 1):")
    print(f"  현재 Recall: {current_detected/total*100:.1f}%")
    print(f"  예상 Recall: {new_recall*100:.1f}%")
    print(f"  추가 탐지: +{additional}개")
```

---

## 🎯 실행 순서

```bash
# Step 1: 급등 구간 피처 분석
python scripts/analyze_surge_windows.py

# Step 2: 최적화 권장사항 생성
python scripts/recommend_thresholds.py
```

---

## 📊 기대 산출물

1. **`reports/surge_window_analysis.json`**
   - 21개 급등의 실제 피처값
   - 축별 충족률
   - 탐지 vs 미탐지 비교

2. **콘솔 출력**
   - 데이터 기반 임계값 권장
   - 병목 축 식별
   - 예상 Recall 개선 효과

---

이 분석 결과를 바탕으로 **다음 실행 내용을 제안**하겠습니다.