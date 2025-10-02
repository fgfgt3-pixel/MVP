## Noise 분석 검토

당신 판단이 맞습니다. **81.9% Noise는 심각한 문제**입니다.

### 현재 상황
- 급등 1개당 평균 **261개 중복 탐지**
- 실제로는 "조기 포착"이 아니라 **"급등 구간 내내 계속 울림"**
- 이건 실용성 0입니다

### 근본 원인
1. **Threshold 70이 너무 낮음** (쉽게 넘어감)
2. **Refractory 45초가 부족** (급등은 수분 지속)
3. **확인창이 약함** (persistent_n=15가 짧음)

---

## Claude Code 작업 지시

### 작업 1: Noise 특성 분석

```python
# 파일: scripts/analyze_noise_patterns.py

"""
Noise의 Score 분포 분석
목적: 어느 threshold에서 Noise가 걸러지는가?
"""

import pandas as pd
import json
import numpy as np
from pathlib import Path

# 라벨 로드
with open("data/labels/all_surge_labels.json") as f:
    labels = json.load(f)

print("="*80)
print("Noise Score 분포 분석")
print("="*80)

all_noise_scores = []
all_signal_scores = []

for label in labels:
    file = label['file']
    start_ts = label['start_ts']
    end_ts = label['end_ts']
    
    # 탐지 이벤트 로드
    stock_code = label['stock_code']
    date = file.split('_')[-2]
    event_file = f"gate_score_{stock_code}_{date}.jsonl"
    event_path = Path("data/events/gate_score") / event_file
    
    if not event_path.exists():
        continue
    
    with open(event_path) as f:
        events = [json.loads(line) for line in f]
    
    for event in events:
        score = event['score']
        ts = event['ts']
        
        # ±30초 허용
        if start_ts - 30000 <= ts <= end_ts + 30000:
            all_signal_scores.append(score)
        else:
            all_noise_scores.append(score)

# 분포 분석
print(f"\nSignal (급등 내부): {len(all_signal_scores)}개")
print(f"  Mean: {np.mean(all_signal_scores):.1f}")
print(f"  Median: {np.median(all_signal_scores):.1f}")
print(f"  P25: {np.percentile(all_signal_scores, 25):.1f}")

print(f"\nNoise (급등 외부): {len(all_noise_scores)}개")
print(f"  Mean: {np.mean(all_noise_scores):.1f}")
print(f"  Median: {np.median(all_noise_scores):.1f}")
print(f"  P75: {np.percentile(all_noise_scores, 75):.1f}")
print(f"  P90: {np.percentile(all_noise_scores, 90):.1f}")

# Threshold 시뮬레이션
print("\n" + "="*80)
print("Threshold별 효과 예측")
print("="*80)

for threshold in [75, 80, 85, 90, 95]:
    signal_pass = sum(s >= threshold for s in all_signal_scores)
    noise_pass = sum(s >= threshold for s in all_noise_scores)
    
    signal_rate = signal_pass / len(all_signal_scores) * 100
    noise_rate = noise_pass / len(all_noise_scores) * 100
    
    total_pass = signal_pass + noise_pass
    noise_ratio = noise_pass / total_pass * 100 if total_pass > 0 else 0
    
    print(f"\nThreshold = {threshold}:")
    print(f"  Signal 통과: {signal_rate:.1f}% ({signal_pass}/{len(all_signal_scores)})")
    print(f"  Noise 통과: {noise_rate:.1f}% ({noise_pass}/{len(all_noise_scores)})")
    print(f"  Noise 비율: {noise_ratio:.1f}%")

# 최적 threshold 추천
print("\n" + "="*80)
print("권장 Threshold")
print("="*80)

# 목표: Noise 비율 < 40%
for threshold in range(70, 101):
    signal_pass = sum(s >= threshold for s in all_signal_scores)
    noise_pass = sum(s >= threshold for s in all_noise_scores)
    total_pass = signal_pass + noise_pass
    
    if total_pass == 0:
        continue
    
    noise_ratio = noise_pass / total_pass
    
    if noise_ratio < 0.4:  # 40% 미만
        signal_rate = signal_pass / len(all_signal_scores)
        print(f"\nThreshold = {threshold}:")
        print(f"  Signal Recall: {signal_rate*100:.1f}%")
        print(f"  Noise 비율: {noise_ratio*100:.1f}%")
        print(f"  총 탐지: {total_pass}개")
        break
```

---

### 작업 2: 강화된 Confirm 로직

```python
# 파일: onset_detection/src/detection/strict_confirm_detector.py

"""
Noise 제거를 위한 강화된 확인 로직
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

class StrictConfirmDetector:
    """
    3단계 확인:
    1. Pre-window 대비 개선 확인
    2. Persistent 지속성 (더 길게)
    3. Peak 검증 (급등 진행 중인가?)
    """
    
    def __init__(self, config=None):
        # 강화된 파라미터
        self.pre_window_s = 10  # 5 → 10초
        self.confirm_window_s = 20  # 15 → 20초
        self.persistent_n = 30  # 15 → 30 (3초분)
        
        # Delta 강화
        self.delta_ret_min = 0.001  # 0.0005 → 0.001
        self.delta_zvol_min = 0.5   # 0.3 → 0.5
        
        # Peak 검증
        self.require_peak_progress = True
    
    def confirm_candidates(
        self, 
        features_df: pd.DataFrame,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """후보 확인"""
        
        confirmed = []
        
        for cand in candidates:
            cand_ts = cand['ts']
            stock_code = cand['stock_code']
            
            # Window 추출
            pre_start = cand_ts - self.pre_window_s * 1000
            pre_end = cand_ts
            
            conf_start = cand_ts
            conf_end = cand_ts + self.confirm_window_s * 1000
            
            pre_window = features_df[
                (features_df['ts'] >= pre_start) &
                (features_df['ts'] < pre_end) &
                (features_df['stock_code'] == stock_code)
            ]
            
            conf_window = features_df[
                (features_df['ts'] >= conf_start) &
                (features_df['ts'] <= conf_end) &
                (features_df['stock_code'] == stock_code)
            ]
            
            if pre_window.empty or conf_window.empty:
                continue
            
            # 1단계: Delta 확인
            if not self._check_delta(pre_window, conf_window):
                continue
            
            # 2단계: Persistent 확인
            persist_result = self._check_persistent(conf_window)
            if not persist_result['confirmed']:
                continue
            
            # 3단계: Peak 검증
            if self.require_peak_progress:
                if not self._check_peak_progress(conf_window):
                    continue
            
            # 확정
            confirmed.append({
                'ts': persist_result['confirm_ts'],
                'stock_code': stock_code,
                'event_type': 'onset_confirmed',
                'confirmed_from': cand_ts,
                'evidence': persist_result['evidence']
            })
        
        return confirmed
    
    def _check_delta(self, pre_df, conf_df):
        """Pre 대비 개선"""
        pre_ret = pre_df['ret_1s'].median()
        pre_zvol = pre_df['z_vol_1s'].median()
        
        conf_ret = conf_df['ret_1s'].median()
        conf_zvol = conf_df['z_vol_1s'].median()
        
        delta_ret = conf_ret - pre_ret
        delta_zvol = conf_zvol - pre_zvol
        
        return (delta_ret >= self.delta_ret_min and 
                delta_zvol >= self.delta_zvol_min)
    
    def _check_persistent(self, conf_df):
        """지속성 확인"""
        if len(conf_df) < self.persistent_n:
            return {'confirmed': False}
        
        # ret_1s > 0 (상승 중)
        positive_ret = (conf_df['ret_1s'] > 0).astype(int)
        
        # Rolling sum
        rolling_sum = positive_ret.rolling(
            window=self.persistent_n, 
            min_periods=self.persistent_n
        ).sum()
        
        # persistent_n 중 80% 이상 양수
        threshold = self.persistent_n * 0.8
        persistent_ok = rolling_sum >= threshold
        
        if not persistent_ok.any():
            return {'confirmed': False}
        
        # 최초 충족 시점
        first_idx = persistent_ok.idxmax()
        confirm_ts = conf_df.loc[first_idx, 'ts']
        
        return {
            'confirmed': True,
            'confirm_ts': confirm_ts,
            'evidence': {
                'persistent_rate': float(positive_ret.sum() / len(conf_df))
            }
        }
    
    def _check_peak_progress(self, conf_df):
        """Peak 진행 확인 (가격이 계속 오르는가?)"""
        prices = conf_df['price'].values
        
        # 최근 1/3 구간의 평균 > 초반 1/3 구간의 평균
        third = len(prices) // 3
        
        if third < 3:
            return True  # 너무 짧으면 통과
        
        early_mean = np.mean(prices[:third])
        late_mean = np.mean(prices[-third:])
        
        return late_mean > early_mean * 1.005  # 0.5% 이상 상승
```

---

### 작업 3: 재실행

```python
# 파일: scripts/run_strict_pipeline.py

"""
Strict Confirm + 높은 Threshold로 재실행
"""

from onset_detection.src.detection.gate_score_detector import GateScoreDetector
from onset_detection.src.detection.strict_confirm_detector import StrictConfirmDetector

# Threshold 상향
detector = GateScoreDetector()
detector.score_threshold = 90  # 70 → 90

confirmer = StrictConfirmDetector()

# 12개 파일 재실행
# (배치 코드 재사용)

# 예상 결과:
# - Recall: 70-80%
# - Noise 비율: 30-40%
# - 평균 FP/h: 30-60
```

---

## 실행 순서

```bash
# 1. Noise 분석 (최적 threshold 찾기)
python scripts/analyze_noise_patterns.py

# 2. 결과 확인 후 threshold 결정

# 3. Strict Confirm 적용 + 재실행
python scripts/run_strict_pipeline.py

# 4. Recall 측정
python scripts/calculate_batch_recall.py
```

---

## 목표

**Noise 비율 < 40%**
**Recall > 70%**
**약한 급등 일부 포기 허용**
But 급등만 최대한 많이 잡는게 최고 좋음