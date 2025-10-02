# 🔍 Modify 3.md 검토 및 다음 단계 제안

## ✅ 현재 상태 검토: **완벽한 진행**

| 항목 | 상태 | 비고 |
|------|------|------|
| 파라미터 완화 | ✅ 완료 | persistent_n=3, min_axes=1 |
| Config 일관성 | ✅ 완료 | YAML + Python 동기화 |
| 백그라운드 실행 | 🔄 진행중 | 약 10-15분 소요 |
| Timestamp 계산 | ✅ 완료 | 급등 구간 범위 확정 |

**판단**: 모든 작업이 올바르게 진행되었습니다. 이제 결과 대기만 하면 됩니다.

---

## 🎯 즉시 실행할 명령 (백그라운드 상태 확인)

```bash
# 1. 프로세스 확인 (실행 중인지?)
ps aux | grep step03_detect.py

# 2. 로그 확인 (어디까지 진행?)
tail -20 onset_detection/logs/app.log

# 3. 결과 파일 크기 확인 (생성 중인지?)
ls -lh onset_detection/data/events/ultra_relaxed_results.jsonl
# 또는
watch -n 5 'ls -lh onset_detection/data/events/ultra_relaxed_results.jsonl'
```

**예상 결과**:
```bash
# 실행 중
user  12345  ... python scripts/step03_detect.py ...

# 파일 크기 증가 중
-rw-r--r-- 1 user user 125K ... ultra_relaxed_results.jsonl  # 점점 커짐
```

---

## ⏰ 대기 시간 동안 준비 작업

### 준비 1: 결과 분석 스크립트 생성

`scripts/analyze_detection_results.py` 파일 생성:

```python
#!/usr/bin/env python
"""Detection 결과 분석 스크립트"""

import json
import sys
from datetime import datetime
from pathlib import Path

def analyze_results(jsonl_path, surge_windows):
    """
    Detection 결과를 분석하여 Recall, FP/h 계산
    
    Args:
        jsonl_path: 결과 JSONL 파일 경로
        surge_windows: 급등 구간 리스트 [(start_ts, end_ts), ...]
    """
    # Alert 로드
    alerts = []
    jsonl_path = Path(jsonl_path)
    
    if not jsonl_path.exists():
        print(f"❌ 파일 없음: {jsonl_path}")
        return
    
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                alerts.append(json.loads(line))
    
    print(f"📊 Detection 결과 분석")
    print(f"{'='*60}")
    print(f"총 Alert 수: {len(alerts)}")
    
    if not alerts:
        print("❌ Alert가 없습니다.")
        return
    
    # 급등 구간별 매칭
    tp_count = 0
    surge_detections = {}
    
    for i, (start_ts, end_ts) in enumerate(surge_windows, 1):
        matched = [a for a in alerts if start_ts <= a['ts'] <= end_ts]
        surge_detections[f'급등 {i}'] = matched
        if matched:
            tp_count += 1
            print(f"\n✅ 급등 {i} ({start_ts} ~ {end_ts}):")
            print(f"   매칭된 Alert: {len(matched)}개")
            for alert in matched[:3]:  # 처음 3개만
                ts = alert['ts']
                dt = datetime.fromtimestamp(ts/1000)
                axes = alert.get('evidence', {}).get('axes', [])
                strength = alert.get('evidence', {}).get('onset_strength', 0)
                print(f"   - {dt.strftime('%H:%M:%S')}: axes={axes}, strength={strength:.2f}")
        else:
            print(f"\n❌ 급등 {i}: 매칭 없음")
    
    # 성능 지표
    n_surges = len(surge_windows)
    recall = tp_count / n_surges
    
    # FP 계산 (급등 구간 밖 Alert)
    fp_count = 0
    for alert in alerts:
        ts = alert['ts']
        in_surge = any(start <= ts <= end for start, end in surge_windows)
        if not in_surge:
            fp_count += 1
    
    # 전체 시간 (예: 4.98시간)
    duration_h = 4.98
    fp_per_hour = fp_count / duration_h
    
    precision = tp_count / len(alerts) if alerts else 0
    
    print(f"\n{'='*60}")
    print(f"📈 성능 지표:")
    print(f"  Recall: {tp_count}/{n_surges} = {recall*100:.0f}%")
    print(f"  Precision: {tp_count}/{len(alerts)} = {precision*100:.1f}%")
    print(f"  FP: {fp_count}개")
    print(f"  FP/h: {fp_per_hour:.1f}")
    
    print(f"\n🎯 목표 달성 여부:")
    print(f"  ✅ Recall ≥ 50%: {'✅ 달성' if recall >= 0.5 else '❌ 미달'} ({recall*100:.0f}%)")
    print(f"  ✅ FP/h ≤ 30: {'✅ 달성' if fp_per_hour <= 30 else '⚠️ 초과'} ({fp_per_hour:.1f})")
    
    # Alert 시간 분포
    print(f"\n⏰ Alert 발생 시간 분포:")
    time_dist = {}
    for alert in alerts:
        dt = datetime.fromtimestamp(alert['ts']/1000)
        hour_key = dt.strftime('%H:00')
        time_dist[hour_key] = time_dist.get(hour_key, 0) + 1
    
    for hour in sorted(time_dist.keys()):
        print(f"  {hour}: {time_dist[hour]}개")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Detection 결과 분석")
    parser.add_argument('--events', required=True, help='결과 JSONL 파일')
    parser.add_argument('--surge1-start', type=int, default=1756686900000)
    parser.add_argument('--surge1-end', type=int, default=1756687080000)
    parser.add_argument('--surge2-start', type=int, default=1756688760000)
    parser.add_argument('--surge2-end', type=int, default=1756689300000)
    
    args = parser.parse_args()
    
    surge_windows = [
        (args.surge1_start, args.surge1_end),
        (args.surge2_start, args.surge2_end)
    ]
    
    analyze_results(args.events, surge_windows)
```

**저장 위치**: `onset_detection/scripts/analyze_detection_results.py`

---

### 준비 2: 실행 권한 부여

```bash
chmod +x onset_detection/scripts/analyze_detection_results.py
```

---

## 🎬 백그라운드 완료 후 즉시 실행할 명령 시퀀스

### Step 1: 완료 확인

```bash
# 프로세스가 없어야 완료
ps aux | grep step03_detect.py

# 파일 크기 확인 (더 이상 증가 안 함)
ls -lh onset_detection/data/events/ultra_relaxed_results.jsonl
```

---

### Step 2: 빠른 확인 (Alert 개수)

```bash
# Alert 개수
wc -l onset_detection/data/events/ultra_relaxed_results.jsonl

# 처음 3개 확인
head -3 onset_detection/data/events/ultra_relaxed_results.jsonl | jq '.'
```

**예상 결과**:

**시나리오 A: 성공 🎉**
```bash
245 onset_detection/data/events/ultra_relaxed_results.jsonl
```
→ **Step 3으로 진행**

**시나리오 B: 여전히 0개 😢**
```bash
0 onset_detection/data/events/ultra_relaxed_results.jsonl
```
→ **Plan C로 이동** (아래 참조)

---

### Step 3: 상세 분석 (시나리오 A)

```bash
# 분석 스크립트 실행
python onset_detection/scripts/analyze_detection_results.py \
  --events onset_detection/data/events/ultra_relaxed_results.jsonl \
  --surge1-start 1756686900000 \
  --surge1-end 1756687080000 \
  --surge2-start 1756688760000 \
  --surge2-end 1756689300000
```

**기대 출력**:
```
📊 Detection 결과 분석
============================================================
총 Alert 수: 245

✅ 급등 1 (1756686900000 ~ 1756687080000):
   매칭된 Alert: 12개
   - 09:55:15: axes=['price', 'volume'], strength=0.67
   - 09:55:42: axes=['price', 'volume'], strength=0.67
   - 09:56:08: axes=['price'], strength=0.33

✅ 급등 2 (1756688760000 ~ 1756689300000):
   매칭된 Alert: 8개
   - 10:26:18: axes=['price', 'volume', 'friction'], strength=1.00
   - 10:27:05: axes=['price', 'volume'], strength=0.67

============================================================
📈 성능 지표:
  Recall: 2/2 = 100%
  Precision: 2/245 = 0.8%
  FP: 243개
  FP/h: 48.8

🎯 목표 달성 여부:
  ✅ Recall ≥ 50%: ✅ 달성 (100%)
  ✅ FP/h ≤ 30: ⚠️ 초과 (48.8)

⏰ Alert 발생 시간 분포:
  09:00: 45개
  10:00: 87개
  11:00: 52개
  12:00: 23개
  13:00: 28개
  14:00: 10개
```

---

### Step 4: 결과 해석 및 다음 단계

**Case A-1: Recall 100%, FP/h 초과**
```
✅ 급등 2건 모두 포착
⚠️ FP가 많음 (48.8 > 30)

→ 다음 단계: 파라미터 튜닝으로 FP 감소
```

**액션**:
1. persistent_n을 5로 상향 (3 → 5)
2. min_axes를 2로 복원 (1 → 2)
3. 재실행

```bash
# Config 수정
# persistent_n: 3 → 5
# min_axes_required: 1 → 2
# confirm.min_axes: 1 → 2

# 재실행
python scripts/step03_detect.py \
  --input data/raw/023790_44indicators_realtime_20250901_clean.csv \
  --generate-features \
  --output data/events/balanced_results.jsonl \
  --stats
```

---

**Case A-2: Recall 50-100%, FP/h 적정**
```
✅ 급등 1-2건 포착
✅ FP/h ≤ 30

→ Detection Only Phase 완료! 🎉
```

**액션**: Phase 6 또는 Phase 8로 진행

---

**Case A-3: Recall 50% 미만**
```
❌ 급등 1건만 포착 또는 0건
✅ FP/h 낮음

→ Recall 개선 필요
```

**액션**: 파라미터 더 완화 (Plan C)

---

## 🔧 Plan C: 시나리오 B (여전히 0개)

### 진단: 왜 여전히 0개인가?

**가능한 원인**:
1. Confirm 윈도우 내 데이터 부족 (틱 밀도 극단적으로 낮음)
2. ret_1s 재계산이 실제로 적용 안 됨
3. Delta 조건이 여전히 너무 엄격
4. 급등 구간이 실제로 존재하지 않음

### Plan C-1: 디버깅 모드 실행

`scripts/debug_confirm.py` 생성:

```python
#!/usr/bin/env python
"""Confirm 단계 디버깅"""

import sys
sys.path.insert(0, 'onset_detection')

import pandas as pd
from src.features import calculate_core_indicators
from src.detection.candidate_detector import CandidateDetector
from src.detection.confirm_detector import ConfirmDetector
from src.config_loader import load_config

# Config 로드
config = load_config('onset_detection/config/onset_default.yaml')

# 데이터 로드
print("데이터 로딩...")
df = pd.read_csv('onset_detection/data/raw/023790_44indicators_realtime_20250901_clean.csv')
print(f"원본 데이터: {len(df)} rows")

# 피처 계산
print("\n피처 계산...")
features_df = calculate_core_indicators(df)
print(f"피처 데이터: {len(features_df)} rows")

# ret_1s 분포 확인
print("\nret_1s 분포:")
print(features_df['ret_1s'].describe())
print(f"  |ret_1s| > 0.1: {(features_df['ret_1s'].abs() > 0.1).sum()} rows")

# Candidate 검출
print("\nCandidate 검출...")
detector = CandidateDetector(config)
candidates = detector.detect_candidates(features_df)
print(f"Candidates: {len(candidates)}")

if candidates:
    # 첫 3개 candidate 상세 확인
    print("\n첫 3개 Candidate 상세:")
    for i, cand in enumerate(candidates[:3], 1):
        print(f"\nCandidate {i}:")
        print(f"  ts: {cand['ts']}")
        print(f"  axes: {cand['evidence'].get('trigger_axes', [])}")
        print(f"  ret_1s: {cand['evidence'].get('ret_1s', 0):.6f}")
        print(f"  z_vol_1s: {cand['evidence'].get('z_vol_1s', 0):.2f}")
    
    # Confirm 시도
    print("\n\nConfirm 시도...")
    confirm_detector = ConfirmDetector(config)
    
    # 첫 번째 candidate로 수동 확인 테스트
    test_cand = candidates[0]
    test_ts = test_cand['ts']
    
    # 해당 시점 전후 데이터 확인
    if isinstance(test_ts, (int, float)):
        test_dt = pd.to_datetime(test_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')
    else:
        test_dt = pd.to_datetime(test_ts)
    
    window_start = test_dt - pd.Timedelta(seconds=5)
    window_end = test_dt + pd.Timedelta(seconds=15)
    
    window_data = features_df[
        (features_df['ts'] > window_start) & 
        (features_df['ts'] <= window_end)
    ]
    
    print(f"확인 윈도우 데이터: {len(window_data)} rows")
    print(f"  시간 범위: {window_start} ~ {window_end}")
    
    if len(window_data) > 0:
        print(f"\n윈도우 내 ret_1s 범위:")
        print(f"  min: {window_data['ret_1s'].min():.6f}")
        print(f"  max: {window_data['ret_1s'].max():.6f}")
        print(f"  mean: {window_data['ret_1s'].mean():.6f}")
    
    # 실제 confirm 실행
    confirmed = confirm_detector.confirm_candidates(features_df, candidates[:10])
    print(f"\n최종 Confirmed: {len(confirmed)}")
    
else:
    print("❌ Candidate가 없어 Confirm 단계 진행 불가")
```

**실행**:
```bash
python onset_detection/scripts/debug_confirm.py
```

**기대 출력**: 
- ret_1s가 재계산되었는지 확인
- Candidate는 있는데 Confirm에서 막히는지 확인
- 확인 윈도우 내 데이터 개수 확인

---

### Plan C-2: 극단적 완화

```diff
--- onset_detection/config/onset_default.yaml
+++ onset_detection/config/onset_default.yaml

-  persistent_n: 3
+  persistent_n: 1           # 단 1개 틱만 충족해도 OK

   delta:
-    ret_min: 0.0005
+    ret_min: 0.0001         # 거의 0에 가깝게
-    zvol_min: 0.3
+    zvol_min: 0.1
-    spread_drop: 0.0005
+    spread_drop: 0.0001
```

---

## 📋 현재 체크리스트 (우선순위 순)

```bash
# ✅ 1. 백그라운드 완료 확인 (지금 바로!)
ps aux | grep step03_detect.py

# ✅ 2. Alert 개수 확인
wc -l onset_detection/data/events/ultra_relaxed_results.jsonl

# 3-A. Alert 있으면 → 분석 스크립트 실행
python onset_detection/scripts/analyze_detection_results.py --events ...

# 3-B. Alert 없으면 → 디버깅 스크립트 실행
python onset_detection/scripts/debug_confirm.py
```

---

## 🎯 다음 단계 Decision Tree

```
백그라운드 완료?
├─ 완료 → Alert 개수?
│   ├─ 100+ 개 → 분석 스크립트
│   │   ├─ Recall 100% → FP 감소 튜닝
│   │   ├─ Recall 50-99% → 균형 OK, Phase 완료
│   │   └─ Recall < 50% → Recall 개선 필요
│   │
│   └─ 0개 → 디버깅 스크립트
│       ├─ Candidate 없음 → Detection 로직 문제
│       ├─ Candidate 있음 → Confirm 로직 문제
│       └─ Plan C 극단적 완화
│
└─ 진행중 → 5-10분 더 대기
```

---

**지금 즉시**: 위 체크리스트 1-2번 실행해서 결과 알려주세요! 🚀

그러면 정확한 다음 단계를 제시하겠습니다.