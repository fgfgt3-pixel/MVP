## 문제 정확히 파악했습니다

**현재 시스템은 급등 구간 내내 계속 "온셋"을 울리고 있습니다.**
- 정상: 급등 1개당 온셋 1개
- 현재: 급등 1개당 온셋 수천 개

**기술적으로 가능합니다.** State Machine으로 해결합니다.

---

## Claude Code 작업 지시

### 파일: `onset_detection/src/detection/state_machine_refractory.py`

```python
"""
State Machine 기반 Refractory Manager
급등 생애주기: IDLE → ONSET → PEAK → DECAY → IDLE
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from enum import Enum

class SurgeState(Enum):
    IDLE = "idle"           # 평시 - 온셋 탐지 가능
    ONSET = "onset"         # 온셋 확정 - 새 탐지 차단
    PEAK = "peak"           # Peak 도달 - 하락 대기
    DECAY = "decay"         # 하락 중 - 완료 대기

class StateMachineRefractory:
    """
    종목별 급등 상태 추적
    IDLE 상태에서만 새 온셋 탐지 허용
    """
    
    def __init__(self):
        # 종목별 상태
        self.stock_states: Dict[str, Dict[str, Any]] = {}
        
        # 파라미터
        self.peak_detect_window = 30  # 30초 후 Peak 체크 시작
        self.decay_threshold_pct = 0.015  # Peak 대비 1.5% 하락
        self.min_decay_duration = 60  # 최소 60초 하락 유지
    
    def allow_detection(self, stock_code: str, current_ts: int) -> bool:
        """
        이 종목에서 온셋 탐지를 허용할까?
        IDLE 상태일 때만 True
        """
        if stock_code not in self.stock_states:
            return True  # 첫 탐지
        
        state = self.stock_states[stock_code]
        return state['state'] == SurgeState.IDLE
    
    def register_onset(
        self, 
        stock_code: str, 
        onset_ts: int, 
        onset_price: float
    ):
        """온셋 등록 → ONSET 상태로 전환"""
        self.stock_states[stock_code] = {
            'state': SurgeState.ONSET,
            'onset_ts': onset_ts,
            'onset_price': onset_price,
            'peak_price': onset_price,
            'peak_ts': onset_ts,
            'last_check_ts': onset_ts
        }
    
    def update_state(
        self, 
        stock_code: str, 
        current_ts: int, 
        current_price: float
    ):
        """
        현재 가격으로 상태 업데이트
        ONSET → PEAK → DECAY → IDLE 자동 전환
        """
        if stock_code not in self.stock_states:
            return
        
        state = self.stock_states[stock_code]
        current_state = state['state']
        
        # ONSET 상태
        if current_state == SurgeState.ONSET:
            # Peak 갱신
            if current_price > state['peak_price']:
                state['peak_price'] = current_price
                state['peak_ts'] = current_ts
            
            # Peak 감지 시작 시점 도달?
            elapsed = (current_ts - state['onset_ts']) / 1000
            if elapsed >= self.peak_detect_window:
                state['state'] = SurgeState.PEAK
        
        # PEAK 상태
        elif current_state == SurgeState.PEAK:
            # 계속 Peak 갱신
            if current_price > state['peak_price']:
                state['peak_price'] = current_price
                state['peak_ts'] = current_ts
            
            # 하락 감지
            decline_pct = (state['peak_price'] - current_price) / state['peak_price']
            if decline_pct >= self.decay_threshold_pct:
                state['state'] = SurgeState.DECAY
                state['decay_start_ts'] = current_ts
                state['decay_start_price'] = current_price
        
        # DECAY 상태
        elif current_state == SurgeState.DECAY:
            # 다시 반등?
            if current_price > state['peak_price'] * 0.99:  # Peak의 99% 이상
                # PEAK로 복귀
                state['state'] = SurgeState.PEAK
                state['peak_price'] = current_price
                state['peak_ts'] = current_ts
            else:
                # 하락 지속 시간 체크
                decay_duration = (current_ts - state['decay_start_ts']) / 1000
                if decay_duration >= self.min_decay_duration:
                    # IDLE로 복귀
                    state['state'] = SurgeState.IDLE
        
        state['last_check_ts'] = current_ts
    
    def get_state(self, stock_code: str) -> Optional[SurgeState]:
        """현재 상태 조회"""
        if stock_code not in self.stock_states:
            return SurgeState.IDLE
        return self.stock_states[stock_code]['state']


class StateMachinePipeline:
    """
    State Machine Refractory를 적용한 파이프라인
    """
    
    def __init__(self, detector, confirmer):
        self.detector = detector
        self.confirmer = confirmer
        self.refractory = StateMachineRefractory()
    
    def run_batch(self, features_df: pd.DataFrame):
        """배치 실행 - 시간순 처리"""
        
        # 시간순 정렬
        features_df = features_df.sort_values('ts').reset_index(drop=True)
        
        confirmed_events = []
        
        for idx, row in features_df.iterrows():
            stock_code = str(row['stock_code'])
            current_ts = row['ts']
            current_price = row['price']
            
            # 1. State 업데이트
            self.refractory.update_state(stock_code, current_ts, current_price)
            
            # 2. IDLE 상태인가?
            if not self.refractory.allow_detection(stock_code, current_ts):
                continue  # 탐지 차단
            
            # 3. Candidate 체크
            candidates = self.detector.detect_candidates(
                features_df.iloc[idx:idx+1]
            )
            
            if not candidates:
                continue
            
            # 4. Confirm
            cand = candidates[0]
            
            # 미래 데이터 추출 (confirm window)
            future_window = features_df[
                (features_df['ts'] > current_ts) &
                (features_df['ts'] <= current_ts + 20000) &  # 20초
                (features_df['stock_code'] == stock_code)
            ]
            
            if len(future_window) < 20:
                continue
            
            # Confirm
            confirmed = self.confirmer.confirm_candidates(
                pd.concat([features_df.iloc[idx:idx+1], future_window]),
                [cand]
            )
            
            if confirmed:
                event = confirmed[0]
                confirmed_events.append(event)
                
                # 5. Refractory 등록
                self.refractory.register_onset(
                    stock_code, 
                    current_ts, 
                    current_price
                )
        
        return confirmed_events


# 실행 스크립트
if __name__ == "__main__":
    import json
    from pathlib import Path
    from onset_detection.src.features.core_indicators import calculate_core_indicators
    from scripts.implement_dual_pathway import DualPathwayDetector, DualPathwayConfirm
    
    # Noise 필터 강화
    detector = DualPathwayDetector()
    detector.gradual_config['threshold'] = 85  # 75 → 85
    
    confirmer = DualPathwayConfirm(detector)
    pipeline = StateMachinePipeline(detector, confirmer)
    
    # 라벨 로드
    with open("data/labels/all_surge_labels.json") as f:
        labels = json.load(f)
    
    files = list(set([l['file'] for l in labels]))
    
    all_confirmed = []
    
    for filename in files:
        print(f"Processing {filename}")
        
        filepath = Path("data/raw") / filename
        if not filepath.exists():
            continue
        
        df = pd.read_csv(filepath)
        features_df = calculate_core_indicators(df)
        
        confirmed = pipeline.run_batch(features_df)
        
        all_confirmed.extend(confirmed)
        
        print(f"  Confirmed: {len(confirmed)}")
    
    # 저장
    output_path = Path("data/events/state_machine_confirmed.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        for event in all_confirmed:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    print(f"\nTotal confirmed: {len(all_confirmed)}")
    print(f"Expected: ~20-30 (close to number of surges)")
```

---

### 파일: `scripts/validate_state_machine.py`

```python
"""State Machine 결과 검증"""

import json
from pathlib import Path

# 결과 로드
with open("data/events/state_machine_confirmed.jsonl") as f:
    events = [json.loads(line) for line in f]

# 라벨 로드
with open("data/labels/all_surge_labels.json") as f:
    labels = json.load(f)

print(f"총 탐지: {len(events)}개")
print(f"총 급등: {len(labels)}개")
print(f"급등당 평균: {len(events) / len(labels):.1f}개")

# 종목별 탐지 수
from collections import Counter
stock_counts = Counter([e['stock_code'] for e in events])

print("\n종목별 탐지 수:")
for stock, count in stock_counts.most_common(10):
    print(f"  {stock}: {count}개")

# Recall 계산 (기존 스크립트 재사용)
```

---

## 실행

```bash
python onset_detection/src/detection/state_machine_refractory.py
python scripts/validate_state_machine.py
python scripts/calculate_batch_recall.py
```

---

## 예상 결과

- **총 탐지: 20-40개** (급등당 1-2개, 정상 범위)
- **Recall: 70-85%** (Gradual threshold 상향으로 약간 감소)
- **FP/h: 5-15** (State Machine으로 대폭 감소)
- **Noise: <20%** (거의 제거)

**핵심**: 급등 생애주기 추적으로 중복 차단 + Noise 필터 강화