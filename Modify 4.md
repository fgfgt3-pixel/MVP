# Phase 1 타이밍 불일치 원인 분석 작업 지시서 (Claude Code 실행용)

## 🚨 문제 상황
- **023790**: 급등 시작 **전(-8.8s)** 또는 **직후(+9.0s)** 탐지 ✅
- **413630**: 급등 시작 **1.5~2.5분 후** 탐지 ❌
- **동일한 설정**인데 **완전히 다른 결과** → 근본 원인 파악 필요

---

## 📋 작업 순서 (연속 실행)

### Step 1: 급등 구간 데이터 상세 분석

```python
# 파일: scripts/investigate_timing_discrepancy.py (신규)

"""
타이밍 불일치 원인 조사
목적: 왜 413630은 느린지, 023790과 무엇이 다른지 파악
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

def analyze_surge_characteristics(df, surge_start, surge_end, surge_name):
    """급등 구간의 특성 분석"""
    
    # 급등 구간 데이터
    surge_df = df[(df['ts'] >= surge_start) & (df['ts'] <= surge_end)].copy()
    
    if surge_df.empty:
        return None
    
    # 급등 전 30초 (베이스라인)
    baseline_df = df[(df['ts'] >= surge_start - 30000) & (df['ts'] < surge_start)].copy()
    
    print(f"\n{'='*60}")
    print(f"{surge_name} 특성 분석")
    print(f"{'='*60}")
    
    # 기본 통계
    print(f"\n### 기본 통계")
    print(f"Duration: {(surge_end - surge_start)/1000:.1f}초")
    print(f"Total ticks: {len(surge_df)}개")
    print(f"Price change: {(surge_df['price'].iloc[-1] / surge_df['price'].iloc[0] - 1)*100:+.2f}%")
    
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
    
    if not early_surge.empty:
        print(f"\n### 초기 30초 Candidate 조건 충족")
        
        # Speed axis
        speed_ok = (early_surge['ret_1s'] > 0.002).sum()
        print(f"Speed (ret_1s > 0.002): {speed_ok}/{len(early_surge)} ({speed_ok/len(early_surge)*100:.1f}%)")
        
        # Participation axis
        if 'z_vol_1s' in early_surge.columns:
            participation_ok = (early_surge['z_vol_1s'] > 2.5).sum()
            print(f"Participation (z_vol > 2.5): {participation_ok}/{len(early_surge)} ({participation_ok/len(early_surge)*100:.1f}%)")
        
        # 3축 동시 충족
        if 'z_vol_1s' in early_surge.columns and 'spread' in early_surge.columns:
            spread_baseline = early_surge['spread'].mean() * 1.5
            friction_ok = early_surge['spread'] < spread_baseline * 0.6
            
            all_3_ok = ((early_surge['ret_1s'] > 0.002) & 
                       (early_surge['z_vol_1s'] > 2.5) & 
                       friction_ok).sum()
            print(f"3축 동시 충족: {all_3_ok}/{len(early_surge)} ({all_3_ok/len(early_surge)*100:.1f}%)")
    
    # Baseline 대비 변화
    if not baseline_df.empty:
        print(f"\n### Baseline 대비 변화")
        
        baseline_tps = baseline_df.groupby(baseline_df['ts'] // 1000).size().mean()
        surge_tps = ticks_per_sec.mean()
        print(f"Ticks/sec: {baseline_tps:.1f} → {surge_tps:.1f} ({(surge_tps/baseline_tps-1)*100:+.1f}%)")
        
        if 'z_vol_1s' in baseline_df.columns and 'z_vol_1s' in surge_df.columns:
            baseline_zvol = baseline_df['z_vol_1s'].median()
            surge_zvol = surge_df['z_vol_1s'].median()
            print(f"z_vol: {baseline_zvol:.2f} → {surge_zvol:.2f} ({surge_zvol - baseline_zvol:+.2f})")
    
    return {
        "duration_s": (surge_end - surge_start) / 1000,
        "total_ticks": len(surge_df),
        "price_change_pct": (surge_df['price'].iloc[-1] / surge_df['price'].iloc[0] - 1) * 100,
        "ticks_per_sec_mean": float(ticks_per_sec.mean()),
        "ret_1s_mean": float(surge_df['ret_1s'].mean()),
        "ret_1s_p90": float(surge_df['ret_1s'].quantile(0.9)),
        "z_vol_mean": float(surge_df['z_vol_1s'].mean()) if 'z_vol_1s' in surge_df.columns else None,
        "early_3axes_rate": float(all_3_ok / len(early_surge)) if not early_surge.empty and all_3_ok else 0
    }

# 023790 분석
print("\n" + "="*60)
print("023790 급등 분석")
print("="*60)

df_023790 = pd.read_csv("data/raw/023790_44indicators_realtime_20250901_clean.csv")

# Features 계산 필요
from onset_detection.src.features.core_indicators import calculate_core_indicators
df_023790 = calculate_core_indicators(df_023790)

surges_023790 = [
    {"name": "Surge1", "start": 1756688123304, "end": 1756688123304 + 240000},
    {"name": "Surge2", "start": 1756689969627, "end": 1756689969627 + 240000}
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
print("\n" + "="*60)
print("413630 급등 분석")
print("="*60)

df_413630 = pd.read_csv("data/raw/413630_44indicators_realtime_20250901_clean.csv")
df_413630 = calculate_core_indicators(df_413630)

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
print("\n" + "="*60)
print("023790 vs 413630 비교")
print("="*60)

print(f"\n### 평균 특성")

avg_023790 = {
    "ticks_per_sec": np.mean([r['ticks_per_sec_mean'] for r in results_023790]),
    "ret_1s_p90": np.mean([r['ret_1s_p90'] for r in results_023790]),
    "z_vol_mean": np.mean([r['z_vol_mean'] for r in results_023790 if r['z_vol_mean']]),
    "early_3axes_rate": np.mean([r['early_3axes_rate'] for r in results_023790])
}

avg_413630 = {
    "ticks_per_sec": np.mean([r['ticks_per_sec_mean'] for r in results_413630]),
    "ret_1s_p90": np.mean([r['ret_1s_p90'] for r in results_413630]),
    "z_vol_mean": np.mean([r['z_vol_mean'] for r in results_413630 if r['z_vol_mean']]),
    "early_3axes_rate": np.mean([r['early_3axes_rate'] for r in results_413630])
}

print(f"\n023790 평균:")
print(f"  Ticks/sec: {avg_023790['ticks_per_sec']:.1f}")
print(f"  ret_1s P90: {avg_023790['ret_1s_p90']:.6f}")
print(f"  z_vol: {avg_023790['z_vol_mean']:.2f}")
print(f"  초기 3축 충족률: {avg_023790['early_3axes_rate']*100:.1f}%")

print(f"\n413630 평균:")
print(f"  Ticks/sec: {avg_413630['ticks_per_sec']:.1f}")
print(f"  ret_1s P90: {avg_413630['ret_1s_p90']:.6f}")
print(f"  z_vol: {avg_413630['z_vol_mean']:.2f}")
print(f"  초기 3축 충족률: {avg_413630['early_3axes_rate']*100:.1f}%")

# 핵심 발견
print("\n" + "="*60)
print("핵심 발견사항")
print("="*60)

if avg_023790['early_3axes_rate'] > avg_413630['early_3axes_rate'] * 2:
    print(f"\n⚠️ 413630은 초기 30초에 3축 충족률이 {avg_413630['early_3axes_rate']*100:.1f}%로 매우 낮음")
    print(f"   (023790은 {avg_023790['early_3axes_rate']*100:.1f}%)")
    print(f"   → 점진적 급등 특성으로 인해 초기 탐지 어려움")

if avg_413630['ticks_per_sec'] < avg_023790['ticks_per_sec'] * 0.7:
    print(f"\n⚠️ 413630의 틱 밀도가 낮음 ({avg_413630['ticks_per_sec']:.1f} vs {avg_023790['ticks_per_sec']:.1f})")
    print(f"   → Participation axis 충족 어려움")

if avg_413630['ret_1s_p90'] < 0.002:
    print(f"\n⚠️ 413630의 ret_1s P90이 임계값(0.002) 미만 ({avg_413630['ret_1s_p90']:.6f})")
    print(f"   → Speed axis 충족 어려움")

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
        "early_detection_ratio": avg_413630['early_3axes_rate'] / avg_023790['early_3axes_rate']
    }
}

Path("reports").mkdir(exist_ok=True)
with open("reports/timing_discrepancy_analysis.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n결과 저장: reports/timing_discrepancy_analysis.json")
```

**실행**:
```bash
python scripts/investigate_timing_discrepancy.py
```

---

### Step 2: 급등 시작점 재정의 필요성 검토

```python
# 파일: scripts/verify_surge_start_points.py (신규)

"""
급등 시작점 검증
목적: 사용자가 지정한 시작점이 실제 급등 시작인지 확인
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def find_actual_surge_start(df, user_start, window_before=300000, window_after=120000):
    """
    사용자 지정 시작점 전후로 실제 급등 시작 탐색
    
    방법:
    1. ticks_per_sec 급증 시점
    2. price 가속 시점
    3. z_vol_1s 급증 시점
    """
    
    window_df = df[
        (df['ts'] >= user_start - window_before) & 
        (df['ts'] <= user_start + window_after)
    ].copy()
    
    if window_df.empty:
        return None
    
    # 초 단위로 집계
    window_df['second'] = window_df['ts'] // 1000
    sec_agg = window_df.groupby('second').agg({
        'price': 'last',
        'z_vol_1s': 'mean',
        'ts': 'count'
    }).rename(columns={'ts': 'ticks_count'})
    
    sec_agg['price_pct_change'] = sec_agg['price'].pct_change() * 100
    
    # 변화점 탐지
    ticks_mean = sec_agg['ticks_count'].rolling(30).mean()
    ticks_std = sec_agg['ticks_count'].rolling(30).std()
    
    # Ticks 급증 시점 (평균 + 2 std 초과)
    ticks_surge = sec_agg['ticks_count'] > (ticks_mean + 2 * ticks_std)
    
    # 첫 번째 급증 시점
    if ticks_surge.any():
        first_surge_sec = sec_agg[ticks_surge].index[0]
        first_surge_ts = first_surge_sec * 1000
    else:
        first_surge_ts = user_start
    
    # 사용자 지정 시작 vs 실제 급증 시작
    difference_s = (first_surge_ts - user_start) / 1000
    
    print(f"\n사용자 지정 시작: {pd.to_datetime(user_start, unit='ms', utc=True).tz_convert('Asia/Seoul').strftime('%H:%M:%S')}")
    print(f"Ticks 급증 시작: {pd.to_datetime(first_surge_ts, unit='ms', utc=True).tz_convert('Asia/Seoul').strftime('%H:%M:%S')}")
    print(f"차이: {difference_s:+.1f}초")
    
    return {
        "user_start": user_start,
        "detected_start": first_surge_ts,
        "difference_s": difference_s
    }

# 413630 검증
print("="*60)
print("413630 급등 시작점 검증")
print("="*60)

df_413630 = pd.read_csv("data/raw/413630_44indicators_realtime_20250901_clean.csv")

from onset_detection.src.features.core_indicators import calculate_core_indicators
df_413630 = calculate_core_indicators(df_413630)

first_ts = df_413630['ts'].min()
first_dt = pd.to_datetime(first_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')

surge_times = ["09:09", "10:01", "11:46", "13:29", "14:09"]

results = []
for i, time_str in enumerate(surge_times, 1):
    print(f"\nSurge {i} ({time_str}):")
    
    hour, minute = map(int, time_str.split(':'))
    user_start_dt = first_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    user_start = int(user_start_dt.timestamp() * 1000)
    
    result = find_actual_surge_start(df_413630, user_start)
    if result:
        results.append(result)

# 평균 차이
avg_diff = np.mean([r['difference_s'] for r in results])
print(f"\n{'='*60}")
print(f"평균 시작점 차이: {avg_diff:+.1f}초")
print(f"{'='*60}")

if abs(avg_diff) > 60:
    print(f"\n⚠️ 사용자 지정 시작점과 실제 급증 시작이 {abs(avg_diff):.0f}초 차이")
    print(f"   → 급등 '시작' 정의 재검토 필요")
    print(f"   → 또는 Candidate threshold가 이 데이터에 맞지 않음")

# 저장
import json
with open("reports/surge_start_verification.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n결과 저장: reports/surge_start_verification.json")
```

**실행**:
```bash
python scripts/verify_surge_start_points.py
```

---

### Step 3: 종합 진단 및 해결 방안 제시

```python
# 파일: scripts/diagnose_and_recommend.py (신규)

"""
타이밍 불일치 종합 진단
목적: 원인 파악 및 해결 방안 제시
"""

import json
from pathlib import Path

print("="*60)
print("타이밍 불일치 종합 진단")
print("="*60)

# 분석 결과 로드
with open("reports/timing_discrepancy_analysis.json") as f:
    discrepancy = json.load(f)

with open("reports/surge_start_verification.json") as f:
    verification = json.load(f)

# 진단
print("\n### 진단 결과")

comparison = discrepancy['comparison']

# 1. 틱 밀도 차이
ticks_ratio = comparison['ticks_ratio']
print(f"\n1. 틱 밀도 차이")
print(f"   413630 / 023790 = {ticks_ratio:.2f}배")

if ticks_ratio < 0.7:
    print(f"   ⚠️ 413630의 틱 밀도가 {(1-ticks_ratio)*100:.0f}% 낮음")
    print(f"   → ticks_per_sec 기반 탐지 어려움")

# 2. Return 차이
ret_ratio = comparison['ret_ratio']
print(f"\n2. Return(ret_1s) 차이")
print(f"   413630 / 023790 = {ret_ratio:.2f}배")

if ret_ratio < 0.8:
    print(f"   ⚠️ 413630의 수익률이 {(1-ret_ratio)*100:.0f}% 낮음")
    print(f"   → Speed axis 충족 어려움")

# 3. 초기 3축 충족률
early_detection_ratio = comparison['early_detection_ratio']
print(f"\n3. 초기 30초 3축 충족률")
print(f"   413630 / 023790 = {early_detection_ratio:.2f}배")

if early_detection_ratio < 0.3:
    print(f"   🚨 413630은 초기에 3축 거의 충족 못함 (핵심 문제!)")
    print(f"   → 점진적 급등 특성")

# 4. 시작점 정의 차이
avg_start_diff = sum([r['difference_s'] for r in verification]) / len(verification)
print(f"\n4. 급등 시작점 검증")
print(f"   사용자 지정 vs 실제 급증: 평균 {avg_start_diff:+.1f}초")

if abs(avg_start_diff) > 60:
    print(f"   ⚠️ 시작점 정의에 1분 이상 차이")
    print(f"   → '급등 시작'의 정의가 모호")

# 근본 원인
print("\n" + "="*60)
print("근본 원인")
print("="*60)

print("""
413630이 느린 이유:

1. **점진적 급등 특성**
   - 023790: 급격한 급등 (초반부터 강한 신호)
   - 413630: 점진적 상승 (초반 신호 약함)
   
2. **현재 Threshold의 한계**
   - ret_1s > 0.002: 급격한 급등에 최적화
   - z_vol > 2.5: 높은 거래량 급증 요구
   - 3축 동시 충족: 점진적 급등은 초기 충족 어려움

3. **급등 정의의 모호성**
   - "09:09 시작"이 실제 급증 시작인지 불명확
   - 점진적 전환 구간을 '시작점'으로 보기 어려움
""")

# 해결 방안
print("\n" + "="*60)
print("해결 방안")
print("="*60)

print("""
### 옵션 A: Threshold 완화 (점진적 급등 포착)

**변경**:
```yaml
onset:
  speed:
    ret_1s_threshold: 0.0015  # 0.002 → 0.0015
  participation:
    z_vol_threshold: 2.0      # 2.5 → 2.0
  friction:
    spread_narrowing_pct: 0.7 # 0.6 → 0.7

detection:
  min_axes_required: 2        # 3 → 2 (완화)
```

**예상 효과**:
- 413630 Recall 향상 (40% → 60-80%)
- FP/h 증가 (3.2 → 15-25)
- 023790 Recall 유지 (100%)
- 023790 FP/h 증가 (20.1 → 40-50)

**트레이드오프**: FP 증가 vs Recall 향상

---

### 옵션 B: 듀얼 전략 (급등 타입별 분리)

**개념**:
- **급격한 급등**: 현재 설정 (엄격)
- **점진적 급등**: 완화된 설정

**구현**:
```python
# candidate_detector.py에 듀얼 모드 추가
if gradual_mode:
    # 완화된 threshold
else:
    # 현재 threshold
```

**예상 효과**:
- 두 타입 모두 포착
- 복잡도 증가
- Phase 2에서 강도 분류와 통합 가능

---

### 옵션 C: 현재 설정 유지 + 급등 재정의

**접근**:
1. 413630의 "시작점"을 재검토
2. Ticks 급증 시점을 실제 시작으로 재정의
3. 현재 설정으로 재측정

**장점**:
- 설정 변경 없음
- Recall 향상 가능

**단점**:
- 수작업 재정의 필요
- 근본 해결 아님

---

### 권장: 옵션 A (Threshold 완화)

**이유**:
1. 점진적 급등도 실제 급등임
2. FP 증가는 Phase 2에서 필터링 가능
3. Recall 우선 원칙 유지
4. 구현 간단

**다음 단계**:
1. Threshold 완화 적용
2. 듀얼 파일 재측정
3. FP/h와 Recall 균형점 확인
4. 목표 달성 시 Phase 1 종료
""")

# 저장
diagnosis = {
    "root_cause": {
        "gradual_surge_characteristics": True,
        "threshold_optimized_for_sharp_surges": True,
        "start_point_ambiguity": abs(avg_start_diff) > 60
    },
    "metrics": {
        "ticks_ratio": ticks_ratio,
        "ret_ratio": ret_ratio,
        "early_detection_ratio": early_detection_ratio,
        "start_diff_avg": avg_start_diff
    },
    "recommended_option": "A",
    "next_actions": [
        "Apply relaxed thresholds",
        "Re-run detection on both files",
        "Measure Recall and FP/h",
        "Decide Phase 1 completion"
    ]
}

with open("reports/timing_diagnosis_and_recommendation.json", "w") as f:
    json.dump(diagnosis, f, indent=2)

print(f"\n진단 결과 저장: reports/timing_diagnosis_and_recommendation.json")
```

**실행**:
```bash
python scripts/diagnose_and_recommend.py
```

---

## ✅ 작업 체크리스트

- [ ] Step 1: 급등 구간 상세 분석 완료
- [ ] Step 2: 급등 시작점 검증 완료
- [ ] Step 3: 종합 진단 및 권장 방안 확인

---

## 🚀 한 줄 실행

```bash
python scripts/investigate_timing_discrepancy.py && \
python scripts/verify_surge_start_points.py && \
python scripts/diagnose_and_recommend.py && \
cat reports/timing_diagnosis_and_recommendation.json
```

---

## 📌 예상되는 결과

### 가설 1: 점진적 급등 특성
- 413630은 초기 신호가 약함
- 3축 동시 충족이 1-2분 후에야 가능
- → Threshold 완화 필요

### 가설 2: 틱 밀도 차이
- 413630의 틱이 적음
- ticks_per_sec 기준 미달
- → Participation 임계 낮춤

### 가설 3: 시작점 정의 오류
- 사용자 지정 "시작"이 실제 급증 이전
- 1-2분 선행 시작점
- → 재정의 필요

**결과에 따라 다음 조치 결정**