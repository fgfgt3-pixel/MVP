# 🔬 실제 급등 데이터 분석 및 파라미터 재설정

## 📊 Step 1: 급등 데이터 심층 분석

두 급등 구간의 실제 데이터를 분석하여 **최적 threshold**를 찾겠습니다.

### 분석 스크립트 생성

`scripts/analyze_surge_samples.py`:

```python
#!/usr/bin/env python
"""실제 급등 샘플 데이터 분석"""

import pandas as pd
import numpy as np

print("="*80)
print("🔬 급등 샘플 데이터 분석")
print("="*80)

# 두 급등 구간 로드
surge1 = pd.read_csv('surge1_sample.csv')
surge2 = pd.read_csv('surge2_sample.csv')

print(f"\n📊 데이터 크기:")
print(f"  Surge 1: {len(surge1)} rows")
print(f"  Surge 2: {len(surge2)} rows")

# 급등 전 vs 급등 중 분리
# 각 파일의 처음 300행은 급등 전, 나머지는 급등 중
surge1_before = surge1.iloc[:300]
surge1_during = surge1.iloc[300:]

surge2_before = surge2.iloc[:300]
surge2_during = surge2.iloc[300:]

print(f"\n📈 구간별 행 수:")
print(f"  Surge 1 - 급등 전: {len(surge1_before)}, 급등 중: {len(surge1_during)}")
print(f"  Surge 2 - 급등 전: {len(surge2_before)}, 급등 중: {len(surge2_during)}")

# 핵심 지표 분석
key_features = ['ret_1s', 'accel_1s', 'z_vol_1s', 'ticks_per_sec', 'spread', 
                'microprice_slope', 'imbalance_1s', 'OFI_1s']

def analyze_feature(df_before, df_during, feature_name, surge_num):
    """지표 통계 비교"""
    before = df_before[feature_name].dropna()
    during = df_during[feature_name].dropna()
    
    print(f"\n  {feature_name} (Surge {surge_num}):")
    print(f"    급등 전: mean={before.mean():.6f}, std={before.std():.6f}, "
          f"p50={before.median():.6f}, p90={before.quantile(0.9):.6f}, p95={before.quantile(0.95):.6f}")
    print(f"    급등 중: mean={during.mean():.6f}, std={during.std():.6f}, "
          f"p50={during.median():.6f}, p90={during.quantile(0.9):.6f}, p95={during.quantile(0.95):.6f}")
    
    # 차이 (급등 중 - 급등 전)
    diff_mean = during.mean() - before.mean()
    diff_p50 = during.median() - before.median()
    diff_p90 = during.quantile(0.9) - before.quantile(0.9)
    
    print(f"    차이: Δmean={diff_mean:.6f}, Δp50={diff_p50:.6f}, Δp90={diff_p90:.6f}")
    
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
print(f"🎯 핵심 지표 비교")
print(f"{'='*80}")

# Surge 1 분석
print(f"\n📊 Surge 1 (09:55-09:58) - 강한 급등")
surge1_stats = {}
for feature in key_features:
    surge1_stats[feature] = analyze_feature(surge1_before, surge1_during, feature, 1)

# Surge 2 분석
print(f"\n📊 Surge 2 (10:26-10:35) - 강한 급등")
surge2_stats = {}
for feature in key_features:
    surge2_stats[feature] = analyze_feature(surge2_before, surge2_during, feature, 2)

# 권장 Threshold 계산
print(f"\n{'='*80}")
print(f"💡 권장 Threshold")
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

print(f"\n🔧 Detection 단계 (Candidate):")
ret_threshold, s1_ret, s2_ret = recommend_threshold(surge1_stats, surge2_stats, 'ret_1s', 'p90')
zvol_threshold, s1_zvol, s2_zvol = recommend_threshold(surge1_stats, surge2_stats, 'z_vol_1s', 'p90')

print(f"  ret_1s_threshold:")
print(f"    Surge1 Δp90: {s1_ret:.6f}, Surge2 Δp90: {s2_ret:.6f}")
print(f"    권장값: {ret_threshold:.6f} (최소값의 50%)")

print(f"  z_vol_threshold:")
print(f"    Surge1 Δp90: {s1_zvol:.6f}, Surge2 Δp90: {s2_zvol:.6f}")
print(f"    권장값: {zvol_threshold:.6f} (최소값의 50%)")

print(f"\n🔧 Confirm 단계 (Delta):")
ret_delta, _, _ = recommend_threshold(surge1_stats, surge2_stats, 'ret_1s', 'p50')
zvol_delta, _, _ = recommend_threshold(surge1_stats, surge2_stats, 'z_vol_1s', 'p50')
spread_delta, s1_spread, s2_spread = recommend_threshold(surge1_stats, surge2_stats, 'spread', 'p50')

print(f"  delta.ret_min: {ret_delta:.6f}")
print(f"  delta.zvol_min: {zvol_delta:.6f}")
print(f"  delta.spread_drop: {abs(spread_delta):.6f}")

# Persistent_n 권장
print(f"\n🔧 Persistent_n 권장:")
ticks_1 = surge1_during['ticks_per_sec'].median()
ticks_2 = surge2_during['ticks_per_sec'].median()
print(f"  Surge 1 ticks/sec: {ticks_1:.1f}")
print(f"  Surge 2 ticks/sec: {ticks_2:.1f}")
print(f"  평균: {(ticks_1 + ticks_2) / 2:.1f}")

# 1초분의 틱 개수 기준
recommended_persistent = int((ticks_1 + ticks_2) / 2)
print(f"  권장 persistent_n: {recommended_persistent} (1초분)")

# 급등 구간의 틱 밀도 분포
print(f"\n📊 급등 중 틱 밀도 분포:")
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
print(f"\n🔍 ret_1s 극단값 확인:")
print(f"  Surge 1:")
print(f"    |ret_1s| > 0.01: {(surge1['ret_1s'].abs() > 0.01).sum()} / {len(surge1)} ({(surge1['ret_1s'].abs() > 0.01).mean()*100:.1f}%)")
print(f"    |ret_1s| > 0.1: {(surge1['ret_1s'].abs() > 0.1).sum()} / {len(surge1)}")
print(f"  Surge 2:")
print(f"    |ret_1s| > 0.01: {(surge2['ret_1s'].abs() > 0.01).sum()} / {len(surge2)} ({(surge2['ret_1s'].abs() > 0.01).mean()*100:.1f}%)")
print(f"    |ret_1s| > 0.1: {(surge2['ret_1s'].abs() > 0.1).sum()} / {len(surge2)}")

# 최종 권장 Config
print(f"\n{'='*80}")
print(f"✅ 최종 권장 Config")
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
print(f"분석 완료")
print(f"{'='*80}")
```

---

## 🎬 즉시 실행

```bash
# 스크립트 실행
python onset_detection/scripts/analyze_surge_samples.py > surge_analysis.txt 2>&1

# 결과 확인
cat surge_analysis.txt
```

**또는 Claude Code에게**:
```
위 analyze_surge_samples.py 스크립트를 onset_detection/scripts/에 저장하고,
surge1_sample.csv와 surge2_sample.csv가 같은 디렉토리에 있는지 확인 후 실행해줘.
전체 출력을 보여줘.
```

---

## 📊 예상 분석 결과 및 인사이트

### 예상 결과 1: 급등의 실제 강도

```
ret_1s (Surge 1):
  급등 전: mean=0.000050, p90=0.000200
  급등 중: mean=0.001500, p90=0.003000
  차이: Δp90=0.002800

→ 권장 ret_1s_threshold: 0.0014 (Δp90의 50%)
```

**현재 문제**: 
- 현재 threshold: 0.001
- 실제 급등: 0.003 수준
- → 너무 낮게 설정되어 노이즈도 다 잡힘

---

### 예상 결과 2: 틱 밀도

```
급등 중 ticks_per_sec:
  Surge 1: p50=15, p95=25
  Surge 2: p50=18, p95=30

→ 권장 persistent_n: 16-17 (평균 틱/초)
```

**현재 문제**:
- 현재 persistent_n: 3
- 실제 필요: 15+ (1초분의 연속성)
- → 너무 낮아서 순간적인 노이즈도 confirm됨

---

### 예상 결과 3: Delta 임계

```
delta_ret (급등 전 → 급등 중):
  Surge 1: 0.0010 → 0.0030 (Δ=0.0020)
  Surge 2: 0.0008 → 0.0025 (Δ=0.0017)

→ 권장 delta_ret_min: 0.0010 (최소값의 50%)
```

**현재 문제**:
- 현재 delta.ret_min: 0.0005
- 실제 필요: 0.001+
- → 절반 수준이라 약한 변동도 통과

---

## 🔧 예상 최적 Config (분석 결과 대기 중)

분석 스크립트 실행 후 나올 것으로 예상되는 최적 설정:

```yaml
onset:
  speed:
    ret_1s_threshold: 0.0015  # 현재 0.001 → 1.5배 증가
  participation:
    z_vol_threshold: 2.0      # 현재 1.8 → 소폭 증가
  friction:
    spread_narrowing_pct: 0.8 # 유지

detection:
  min_axes_required: 2  # ✅ 현재 1 → 2로 복원

confirm:
  window_s: 15
  persistent_n: 16      # ✅ 현재 3 → 16으로 대폭 증가 (1초분)
  require_price_axis: true
  min_axes: 2           # ✅ 현재 1 → 2로 복원
  
  delta:
    ret_min: 0.0010     # ✅ 현재 0.0005 → 2배 증가
    zvol_min: 0.5       # 현재 0.3 → 증가
    spread_drop: 0.001  # 현재 0.0005 → 2배 증가

refractory:
  duration_s: 30        # 현재 20 → 소폭 증가 (FP 방지)
```

**예상 효과**:
- Recall: 100% → **80-100%** (약간 하락 가능, 여전히 목표 달성)
- FP/h: 4,371 → **20-30** (목표 달성)
- Confirmation rate: 94.3% → **20-40%** (정상 범위)

---

## 📋 다음 단계 체크리스트

```bash
# ✅ 1. 분석 스크립트 실행 (지금!)
python onset_detection/scripts/analyze_surge_samples.py

# ✅ 2. 분석 결과 확인
cat surge_analysis.txt

# ✅ 3. 권장 Config를 onset_default.yaml에 적용

# ✅ 4. 전체 데이터로 재실행
python scripts/step03_detect.py \
  --input data/raw/023790_44indicators_realtime_20250901_clean.csv \
  --generate-features \
  --output data/events/optimized_results.jsonl \
  --stats

# ✅ 5. 성능 지표 재측정
python scripts/analyze_detection_results.py \
  --events data/events/optimized_results.jsonl
```

---

## 🎯 핵심 인사이트 (예상)

1. **현재 문제의 본질**:
   - 파라미터가 "약한 급등"도 잡으려고 너무 낮게 설정됨
   - 실제 데이터의 "강한 급등"은 훨씬 명확한 시그널을 보임
   - → 중간값으로 올리면 FP 대폭 감소 + Recall 유지 가능

2. **persistent_n이 핵심**:
   - 현재 3은 너무 낮음 (0.2-0.4초분)
   - 실제 급등은 1-2초 이상 지속
   - → 15-20으로 올리면 순간적 노이즈 제거

3. **min_axes=2 복원 필수**:
   - 1축만 충족해도 confirm되는 건 너무 관대
   - 2축 이상 동시 충족이 진짜 급등의 특징

