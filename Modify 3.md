정확합니다. 두 가지만으로는 위험하고, 가격은 Pass/Fail 조건이어야 합니다.

---

## 🔍 재검토: 올바른 구조

### 문제점 인정

1. **가격은 가중치가 아닌 필수 조건**
   - 거래량↑ + 가격↓ = 급락 (급등 아님)
   - 거래량↑ + 가격→ = 보합 (급등 아님)
   - **가격 상승은 Gate 조건이어야 함**

2. **두 지표만으로는 불충분**
   - 노이즈 걸러내기 어려움
   - 다양한 급등 타입 구분 불가
   - 보조 지표 필요

3. **현재 데이터 분석의 한계**
   - "어떤 지표가 실제로 변별력 있는가?" 검증 부족
   - 탐지/미탐지 간 지표 차이 정량 분석 필요

---

## 💡 제안: Gate + Weighted Scoring 시스템

### 구조

```
Step 1: Gate Check (필수 조건)
  ├─ 가격 상승 확인 (ret_1s > threshold)
  └─ FAIL → 즉시 종료

Step 2: Signal Scoring (가중 점수)
  ├─ Primary (High Weight)
  │   ├─ z_vol_1s: 거래량 급증
  │   └─ ticks_per_sec: 체결 빈도
  │
  ├─ Secondary (Medium Weight)
  │   ├─ ret_1s 크기: 상승 강도
  │   ├─ microprice_slope: 방향성
  │   └─ accel_1s: 가속도
  │
  └─ Tertiary (Low Weight)
      ├─ imbalance: 호가 불균형
      └─ spread: 마찰 (참고용)

Step 3: Threshold Decision
  └─ Total Score >= Threshold → Candidate
```

---

## 📋 Claude Code 작업 지시서

### 작업 1: 변별력 분석 (Data-Driven Weight Discovery)

```python
# 파일: scripts/discover_discriminative_features.py

"""
목적: 탐지 vs 미탐지 급등 간 지표 차이 정량 분석
출력: 각 지표의 변별력 점수
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from scipy import stats

# 분석 결과 로드
with open("reports/surge_window_analysis.json") as f:
    analysis = json.load(f)

detected = [r for r in analysis if r['detected']]
missed = [r for r in analysis if not r['detected']]

print("="*80)
print("지표별 변별력 분석")
print("="*80)

indicators = [
    'ret_1s',
    'z_vol_1s', 
    'ticks_per_sec',
    'microprice_slope'
]

discriminative_scores = {}

for indicator in indicators:
    # P90 값 추출
    detected_values = [r['stats'][indicator]['p90'] for r in detected]
    missed_values = [r['stats'][indicator]['p90'] for r in missed]
    
    # 통계 검정
    t_stat, p_value = stats.ttest_ind(detected_values, missed_values)
    
    # Effect Size (Cohen's d)
    mean_detected = np.mean(detected_values)
    mean_missed = np.mean(missed_values)
    std_pooled = np.sqrt(
        (np.var(detected_values) + np.var(missed_values)) / 2
    )
    cohens_d = abs(mean_detected - mean_missed) / std_pooled if std_pooled > 0 else 0
    
    # 변별력 점수 (0-100)
    # Effect size 기반: d >= 0.8 (large) = 100점
    discriminative_score = min(100, cohens_d * 125)
    
    discriminative_scores[indicator] = {
        'mean_detected': mean_detected,
        'mean_missed': mean_missed,
        'difference': mean_detected - mean_missed,
        'cohens_d': cohens_d,
        'p_value': p_value,
        'discriminative_score': discriminative_score
    }
    
    print(f"\n{indicator}:")
    print(f"  탐지됨: {mean_detected:.4f}")
    print(f"  미탐지: {mean_missed:.4f}")
    print(f"  차이: {mean_detected - mean_missed:+.4f}")
    print(f"  Effect Size (d): {cohens_d:.3f}")
    print(f"  변별력 점수: {discriminative_score:.1f}/100")

# 정렬
sorted_indicators = sorted(
    discriminative_scores.items(),
    key=lambda x: x[1]['discriminative_score'],
    reverse=True
)

print("\n" + "="*80)
print("변별력 순위")
print("="*80)

for i, (indicator, score) in enumerate(sorted_indicators, 1):
    print(f"{i}. {indicator}: {score['discriminative_score']:.1f}점 (d={score['cohens_d']:.3f})")

# 권장 가중치 계산
print("\n" + "="*80)
print("권장 가중치")
print("="*80)

# 정규화 (합=100)
total_score = sum([s[1]['discriminative_score'] for s in sorted_indicators])

print("\n1단계: 데이터 기반 가중치")
for indicator, score in sorted_indicators:
    weight = (score['discriminative_score'] / total_score) * 100
    print(f"  {indicator}: {weight:.1f}%")

# 실용적 조정
print("\n2단계: 실용적 조정 (Primary/Secondary 구분)")
print("""
Gate (필수):
  ret_1s > 0.0005  # 최소 상승

Primary (고배점):
  - Top 1 지표: 50점
  - Top 2 지표: 40점

Secondary (중배점):
  - Top 3 지표: 20점
  - Top 4 지표: 15점

Threshold:
  - 70점 이상: Candidate
""")

# 저장
with open("reports/discriminative_analysis.json", "w") as f:
    json.dump({
        'indicators': discriminative_scores,
        'ranking': [
            {'indicator': ind, 'score': score['discriminative_score']}
            for ind, score in sorted_indicators
        ]
    }, f, indent=2)

print(f"\n저장: reports/discriminative_analysis.json")
```

---

### 작업 2: Gate + Scoring Detector 구현

```python
# 파일: onset_detection/src/detection/gate_score_detector.py

"""
Gate + Weighted Scoring 기반 후보 탐지
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from ..config_loader import Config, load_config
from ..event_store import create_event

class GateScoreDetector:
    """
    2단계 탐지:
    1. Gate: 필수 조건 (가격 상승)
    2. Scoring: 가중 점수 시스템
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or load_config()
        
        # Gate 조건
        self.gate_ret_min = 0.0005  # 최소 상승
        
        # Scoring 가중치 (데이터 분석 결과 반영)
        # 실행 후 discriminative_analysis.json 기반으로 조정
        self.weights = {
            # Primary (변별력 높음)
            'z_vol_1s': 50,
            'ticks_per_sec': 40,
            
            # Secondary (보조)
            'ret_1s_magnitude': 20,
            'microprice_slope': 15,
            
            # Tertiary (참고)
            'accel_1s': 10
        }
        
        # Threshold
        self.score_threshold = 70  # 조정 가능
    
    def detect_candidates(self, features_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """후보 탐지"""
        
        if features_df.empty:
            return []
        
        candidates = []
        
        for idx, row in features_df.iterrows():
            # Step 1: Gate Check
            ret_1s = row.get('ret_1s', 0)
            
            if ret_1s <= self.gate_ret_min:
                continue  # 가격 상승 없음 → 즉시 종료
            
            # Step 2: Scoring
            score = self._calculate_score(row)
            
            # Step 3: Threshold
            if score >= self.score_threshold:
                candidate = create_event(
                    timestamp=row['ts'],
                    event_type="onset_candidate",
                    stock_code=str(row['stock_code']),
                    score=float(score),
                    evidence={
                        "ret_1s": float(ret_1s),
                        "z_vol_1s": float(row.get('z_vol_1s', 0)),
                        "ticks_per_sec": int(row.get('ticks_per_sec', 0)),
                        "microprice_slope": float(row.get('microprice_slope', 0)),
                        "scoring_details": self._get_scoring_details(row)
                    }
                )
                candidates.append(candidate)
        
        return candidates
    
    def _calculate_score(self, row: pd.Series) -> float:
        """가중 점수 계산"""
        
        score = 0.0
        
        # z_vol_1s (Primary)
        z_vol = row.get('z_vol_1s', 0)
        if z_vol > 3.0:
            score += self.weights['z_vol_1s']
        elif z_vol > 2.5:
            score += self.weights['z_vol_1s'] * 0.8
        elif z_vol > 2.0:
            score += self.weights['z_vol_1s'] * 0.5
        
        # ticks_per_sec (Primary)
        ticks = row.get('ticks_per_sec', 0)
        if ticks > 70:
            score += self.weights['ticks_per_sec']
        elif ticks > 50:
            score += self.weights['ticks_per_sec'] * 0.8
        elif ticks > 30:
            score += self.weights['ticks_per_sec'] * 0.5
        
        # ret_1s magnitude (Secondary)
        ret_1s = row.get('ret_1s', 0)
        if ret_1s > 0.003:
            score += self.weights['ret_1s_magnitude']
        elif ret_1s > 0.002:
            score += self.weights['ret_1s_magnitude'] * 0.7
        elif ret_1s > 0.001:
            score += self.weights['ret_1s_magnitude'] * 0.4
        
        # microprice_slope (Secondary)
        slope = row.get('microprice_slope', 0)
        if slope > 0.001:
            score += self.weights['microprice_slope']
        elif slope > 0.0005:
            score += self.weights['microprice_slope'] * 0.6
        
        # accel_1s (Tertiary)
        accel = row.get('accel_1s', 0)
        if accel > 0.0005:
            score += self.weights['accel_1s']
        elif accel > 0.0002:
            score += self.weights['accel_1s'] * 0.5
        
        return score
    
    def _get_scoring_details(self, row: pd.Series) -> Dict[str, Any]:
        """점수 상세 (디버깅용)"""
        
        details = {}
        
        for indicator, weight in self.weights.items():
            if indicator == 'ret_1s_magnitude':
                value = row.get('ret_1s', 0)
            else:
                value = row.get(indicator, 0)
            
            details[indicator] = {
                'value': float(value),
                'max_weight': weight
            }
        
        return details
```

---

### 작업 3: 배치 테스트 (Gate+Score)

```python
# 파일: scripts/test_gate_score_system.py

"""
Gate+Score 시스템 배치 테스트
"""

import pandas as pd
import json
from pathlib import Path
from onset_detection.src.detection.gate_score_detector import GateScoreDetector
from onset_detection.src.features.core_indicators import calculate_core_indicators

# 라벨 로드
with open("data/labels/all_surge_labels.json") as f:
    labels = json.load(f)

files = list(set([label['file'] for label in labels]))

print("="*80)
print("Gate+Score 시스템 테스트")
print("="*80)

detector = GateScoreDetector()
results_summary = []

for i, filename in enumerate(files, 1):
    print(f"\n[{i}/{len(files)}] {filename}")
    
    filepath = Path("data/raw") / filename
    if not filepath.exists():
        continue
    
    # 데이터 로드
    df = pd.read_csv(filepath)
    features_df = calculate_core_indicators(df)
    
    # Detection
    candidates = detector.detect_candidates(features_df)
    
    # 통계
    duration_hours = (df['ts'].max() - df['ts'].min()) / (1000 * 3600)
    fp_per_hour = len(candidates) / duration_hours if duration_hours > 0 else 0
    
    print(f"  Candidates: {len(candidates)}개")
    print(f"  FP/h: {fp_per_hour:.1f}")
    
    results_summary.append({
        "file": filename,
        "candidates": len(candidates),
        "fp_per_hour": fp_per_hour
    })

# 전체 요약
total_candidates = sum([r['candidates'] for r in results_summary])
total_files = len(results_summary)
avg_fp = np.mean([r['fp_per_hour'] for r in results_summary])

print("\n" + "="*80)
print("전체 요약")
print("="*80)
print(f"총 Candidates: {total_candidates}개")
print(f"평균 FP/h: {avg_fp:.1f}")

# Recall 계산 필요 → calculate_batch_recall.py 재사용
```

---

## 🎯 실행 순서

```bash
# 1. 변별력 분석 (어떤 지표가 중요한가?)
python scripts/discover_discriminative_features.py

# 2. 결과 검토 후 gate_score_detector.py의 가중치 조정

# 3. 배치 테스트
python scripts/test_gate_score_system.py

# 4. Recall 측정
python scripts/calculate_batch_recall.py
```

---

## 📊 예상 결과

**변별력 분석** → `ticks_per_sec`와 `z_vol_1s` 중 어느 것이 더 변별력 있는지 데이터로 확인

**Gate+Score** → Friction 병목 제거 + 유연한 점수 시스템으로 Recall 60-75% 달성 예상