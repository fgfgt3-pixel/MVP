# Phase 1.5: 대규모 검증 및 Threshold 최적화 작업 지시서

## 🎯 수정된 목표

### 기존 목표 (Phase 1)
- ~~모든 라벨링 급등 포착~~ ❌ 비현실적

### 새로운 목표 (Phase 1.5)
- **다수의 급등을 빠르게 포착** (Recall 50-70% 목표)
- **FP/h ≤ 30-40 유지**
- **다양한 형태/강도 급등에서 일관된 성능**

**핵심 인식**: 
- 모든 급등은 포착 불가능 (너무 다양함)
- 하지만 **상당수(50-70%)를 빠르게** 잡는 것이 목표
- 놓친 급등은 Phase 2에서 패턴 분석으로 보완

---

## 📊 데이터 규모

### 총 12개 파일, 21개 급등
- **강한 급등**: 4개 (19%)
- **중간 급등**: 9개 (43%)
- **약한 급등**: 8개 (38%)

### 기대치 설정
```
현재 설정 (Sharp 최적화):
- 강한: 80-100% 예상
- 중간: 50-70% 예상
- 약한: 20-40% 예상

→ 전체 Recall: 50-65% 예상
→ 목표: 60% 달성 (21개 중 13개)
```

---

## 📋 작업 순서

### Step 1: 대규모 급등 라벨 파일 생성

```python
# 파일: scripts/create_surge_labels.py (신규)

"""
12개 파일 21개 급등 라벨링 데이터 생성
"""

import pandas as pd
import json
from pathlib import Path

# 급등 라벨 정의
surge_labels = {
    "023790_20250901": [
        {"time": "09:55", "duration_min": 3, "strength": "중간", "name": "Surge1"},
        {"time": "10:26", "duration_min": 9, "strength": "중간", "name": "Surge2"}
    ],
    "023790_20250902": [
        {"time": "09:03", "duration_min": 9, "strength": "강한", "name": "Surge1"}
    ],
    "054540_20250901": [
        {"time": "10:08", "duration_min": 11, "strength": "강한", "name": "Surge1"}
    ],
    "054540_20250902": [
        {"time": "09:45", "duration_min": 3, "strength": "약한", "name": "Surge1"},
        {"time": "09:51", "duration_min": 12, "strength": "중간", "name": "Surge2"}
    ],
    "054540_20250903": [
        {"time": "09:20", "duration_min": 5, "strength": "약한", "name": "Surge1"}
    ],
    "362320_20250901": [
        {"time": "13:00", "duration_min": 4, "strength": "약한", "name": "Surge1"}
    ],
    "097230_20250902": [
        {"time": "09:13", "duration_min": 15, "strength": "강한", "name": "Surge1"}
    ],
    "097230_20250903": [
        {"time": "09:13", "duration_min": 4, "strength": "약한", "name": "Surge1"},
        {"time": "09:32", "duration_min": 5, "strength": "약한", "name": "Surge2"}
    ],
    "355690_20250903": [
        {"time": "10:37", "duration_min": 7, "strength": "약한", "name": "Surge1"},
        {"time": "10:49", "duration_min": 8, "strength": "중간", "name": "Surge2"}
    ],
    "049470_20250903": [
        {"time": "14:04", "duration_min": 11, "strength": "약한", "name": "Surge1"}
    ],
    "208640_20250903": [
        {"time": "09:42", "duration_min": 2, "strength": "중간", "name": "Surge1"}
    ],
    "413630_20250911": [
        {"time": "09:09", "duration_min": 6, "strength": "중간", "name": "Surge1"},
        {"time": "10:01", "duration_min": 13, "strength": "강한", "name": "Surge2"},
        {"time": "11:46", "duration_min": 4, "strength": "약한", "name": "Surge3"},
        {"time": "13:29", "duration_min": 8, "strength": "중간", "name": "Surge4"},
        {"time": "14:09", "duration_min": 3, "strength": "약한", "name": "Surge5"}
    ]
}

def calculate_surge_timestamps(file_key, surge_info, data_dir="data/raw"):
    """급등 시작/종료 timestamp 계산"""
    
    # 파일명 생성
    stock_code, date = file_key.split('_')
    filename = f"{stock_code}_44indicators_realtime_{date}_clean.csv"
    filepath = Path(data_dir) / filename
    
    if not filepath.exists():
        print(f"⚠️ File not found: {filepath}")
        return None
    
    # CSV 로드 (첫 행만)
    df = pd.read_csv(filepath, nrows=1)
    first_ts = df['ts'].iloc[0]
    first_dt = pd.to_datetime(first_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')
    
    results = []
    for surge in surge_info:
        hour, minute = map(int, surge['time'].split(':'))
        
        # 급등 시작 시점
        surge_start_dt = first_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        surge_start_ts = int(surge_start_dt.timestamp() * 1000)
        
        # 급등 종료 (duration 후)
        surge_end_ts = surge_start_ts + (surge['duration_min'] * 60 * 1000)
        
        results.append({
            "file": filename,
            "stock_code": stock_code,
            "surge_name": surge['name'],
            "strength": surge['strength'],
            "start_time": surge['time'],
            "start_ts": surge_start_ts,
            "end_ts": surge_end_ts,
            "duration_min": surge['duration_min']
        })
    
    return results

# 모든 급등 라벨 생성
print("="*60)
print("급등 라벨 데이터 생성")
print("="*60)

all_labels = []
for file_key, surges in surge_labels.items():
    results = calculate_surge_timestamps(file_key, surges)
    if results:
        all_labels.extend(results)

print(f"\n총 {len(all_labels)}개 급등 라벨 생성")

# 강도별 통계
strength_counts = {}
for label in all_labels:
    strength = label['strength']
    strength_counts[strength] = strength_counts.get(strength, 0) + 1

print(f"\n강도별 분포:")
for strength, count in sorted(strength_counts.items()):
    print(f"  {strength}: {count}개 ({count/len(all_labels)*100:.1f}%)")

# 저장
output_path = Path("data/labels/all_surge_labels.json")
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_labels, f, indent=2, ensure_ascii=False)

print(f"\n저장: {output_path}")
```

**실행**:
```bash
python scripts/create_surge_labels.py
```

---

### Step 2: 배치 Detection 실행

```python
# 파일: scripts/batch_detection.py (신규)

"""
12개 파일 배치 Detection
목적: 현재 설정으로 전체 파일 검증
"""

import pandas as pd
import json
from pathlib import Path
from onset_detection.src.detection.onset_pipeline import OnsetPipelineDF
from onset_detection.src.features.core_indicators import calculate_core_indicators
from onset_detection.src.config_loader import load_config

# 라벨 로드
with open("data/labels/all_surge_labels.json") as f:
    labels = json.load(f)

# 파일 목록 추출
files = list(set([label['file'] for label in labels]))

print("="*60)
print(f"배치 Detection 실행 ({len(files)}개 파일)")
print("="*60)

config = load_config()
results_summary = []

for i, filename in enumerate(files, 1):
    print(f"\n[{i}/{len(files)}] {filename}")
    
    filepath = Path("data/raw") / filename
    if not filepath.exists():
        print(f"  ⚠️ 파일 없음, 건너뜀")
        continue
    
    # 데이터 로드
    df = pd.read_csv(filepath)
    features_df = calculate_core_indicators(df)
    
    # Detection 실행
    pipeline = OnsetPipelineDF(config=config)
    confirmed = pipeline.run_batch(features_df)
    
    # 결과 저장
    stock_code = filename.split('_')[0]
    date = filename.split('_')[-2]
    output_file = f"strategy_c_plus_{stock_code}_{date}.jsonl"
    output_path = Path("data/events/batch") / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        for event in confirmed:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    # 통계
    duration_hours = (df['ts'].max() - df['ts'].min()) / (1000 * 3600)
    fp_per_hour = len(confirmed) / duration_hours
    
    print(f"  Confirmed: {len(confirmed)}개")
    print(f"  FP/h: {fp_per_hour:.1f}")
    print(f"  저장: {output_path}")
    
    results_summary.append({
        "file": filename,
        "confirmed": len(confirmed),
        "fp_per_hour": fp_per_hour,
        "duration_hours": duration_hours
    })

# 전체 요약
print("\n" + "="*60)
print("배치 실행 완료")
print("="*60)

total_confirmed = sum([r['confirmed'] for r in results_summary])
total_hours = sum([r['duration_hours'] for r in results_summary])
avg_fp_per_hour = total_confirmed / total_hours

print(f"\n총 파일: {len(results_summary)}개")
print(f"총 Confirmed: {total_confirmed}개")
print(f"총 시간: {total_hours:.1f}시간")
print(f"평균 FP/h: {avg_fp_per_hour:.1f}")

# 저장
with open("reports/batch_detection_summary.json", "w") as f:
    json.dump({
        "files": results_summary,
        "summary": {
            "total_files": len(results_summary),
            "total_confirmed": total_confirmed,
            "total_hours": total_hours,
            "avg_fp_per_hour": avg_fp_per_hour
        }
    }, f, indent=2)

print(f"\n결과 저장: reports/batch_detection_summary.json")
```

**실행**:
```bash
python scripts/batch_detection.py
```

---

### Step 3: Recall 계산 및 분석

```python
# 파일: scripts/calculate_batch_recall.py (신규)

"""
21개 급등에 대한 Recall 계산
"""

import pandas as pd
import json
from pathlib import Path

# 라벨 로드
with open("data/labels/all_surge_labels.json") as f:
    labels = json.load(f)

print("="*60)
print(f"Recall 계산 ({len(labels)}개 급등)")
print("="*60)

detection_results = []

for label in labels:
    file = label['file']
    stock_code = label['stock_code']
    date = file.split('_')[-2]
    surge_name = label['surge_name']
    strength = label['strength']
    
    start_ts = label['start_ts']
    end_ts = label['end_ts']
    
    # 이벤트 파일 로드
    event_file = f"strategy_c_plus_{stock_code}_{date}.jsonl"
    event_path = Path("data/events/batch") / event_file
    
    if not event_path.exists():
        print(f"⚠️ 이벤트 파일 없음: {event_path}")
        detection_results.append({
            **label,
            "detected": False,
            "detection_ts": None,
            "latency_s": None
        })
        continue
    
    # 이벤트 로드
    events = []
    with open(event_path) as f:
        for line in f:
            events.append(json.loads(line))
    
    # 급등 구간 내 탐지 여부 (±30초 허용)
    detected_events = [
        e for e in events
        if start_ts - 30000 <= e['ts'] <= end_ts + 30000
    ]
    
    if detected_events:
        # 가장 빠른 탐지
        first_detection = min(detected_events, key=lambda x: x['ts'])
        detection_ts = first_detection['ts']
        latency_s = (detection_ts - start_ts) / 1000.0
        
        detection_results.append({
            **label,
            "detected": True,
            "detection_ts": detection_ts,
            "latency_s": latency_s,
            "num_alerts": len(detected_events)
        })
        
        print(f"✅ {file} {surge_name} ({strength}): {latency_s:+.1f}s")
    else:
        detection_results.append({
            **label,
            "detected": False,
            "detection_ts": None,
            "latency_s": None
        })
        
        print(f"❌ {file} {surge_name} ({strength}): 미탐지")

# 통계
print("\n" + "="*60)
print("Recall 통계")
print("="*60)

detected = [r for r in detection_results if r['detected']]
total_recall = len(detected) / len(detection_results)

print(f"\n전체 Recall: {total_recall*100:.1f}% ({len(detected)}/{len(detection_results)})")

# 강도별
for strength in ["강한", "중간", "약한"]:
    strength_total = [r for r in detection_results if r['strength'] == strength]
    strength_detected = [r for r in detected if r['strength'] == strength]
    
    if strength_total:
        strength_recall = len(strength_detected) / len(strength_total)
        print(f"{strength}: {strength_recall*100:.1f}% ({len(strength_detected)}/{len(strength_total)})")

# Latency 분석
latencies = [r['latency_s'] for r in detected]
if latencies:
    import numpy as np
    print(f"\nLatency 통계:")
    print(f"  Mean: {np.mean(latencies):.1f}s")
    print(f"  Median: {np.median(latencies):.1f}s")
    print(f"  Min: {np.min(latencies):.1f}s")
    print(f"  Max: {np.max(latencies):.1f}s")

# 목표 달성 여부
print("\n" + "="*60)
if total_recall >= 0.60:
    print(f"✅ 목표 달성! (Recall {total_recall*100:.1f}% >= 60%)")
else:
    gap = 0.60 - total_recall
    needed = int(gap * len(detection_results))
    print(f"⚠️ 목표 미달 (Recall {total_recall*100:.1f}% < 60%)")
    print(f"   {needed}개 더 탐지 필요")

# 저장
with open("reports/batch_recall_results.json", "w", encoding='utf-8') as f:
    json.dump({
        "detection_results": detection_results,
        "summary": {
            "total_surges": len(detection_results),
            "detected_surges": len(detected),
            "total_recall": total_recall,
            "recall_by_strength": {
                "강한": len([r for r in detected if r['strength'] == '강한']) / len([r for r in detection_results if r['strength'] == '강한']),
                "중간": len([r for r in detected if r['strength'] == '중간']) / len([r for r in detection_results if r['strength'] == '중간']),
                "약한": len([r for r in detected if r['strength'] == '약한']) / len([r for r in detection_results if r['strength'] == '약한'])
            },
            "latency_stats": {
                "mean": float(np.mean(latencies)) if latencies else None,
                "median": float(np.median(latencies)) if latencies else None
            }
        }
    }, f, indent=2, ensure_ascii=False)

print(f"\n결과 저장: reports/batch_recall_results.json")
```

**실행**:
```bash
python scripts/calculate_batch_recall.py
```

---

### Step 4: Threshold 조정 (필요 시)

```python
# 파일: scripts/optimize_for_60_percent.py (신규)

"""
Recall 60% 달성을 위한 Threshold 최적화
"""

import json

# Step 3 결과 로드
with open("reports/batch_recall_results.json") as f:
    results = json.load(f)

current_recall = results['summary']['total_recall']

print("="*60)
print("Threshold 최적화 권장사항")
print("="*60)

print(f"\n현재 Recall: {current_recall*100:.1f}%")
print(f"목표 Recall: 60%")

if current_recall >= 0.60:
    print("\n✅ 이미 목표 달성! 추가 조정 불필요")
elif current_recall >= 0.50:
    print(f"\n⚠️ 목표에 근접 ({current_recall*100:.1f}%)")
    print("\n미세 조정 권장:")
    print("""
```yaml
onset:
  speed:
    ret_1s_threshold: 0.0018  # 0.002 → 0.0018 (10% 완화)
  participation:
    z_vol_threshold: 2.3      # 2.5 → 2.3 (약간 완화)
```

예상 효과: Recall +5-10%, FP/h +5-10
""")
else:
    print(f"\n🚨 큰 격차 ({current_recall*100:.1f}%)")
    print("\n대폭 완화 필요:")
    print("""
```yaml
onset:
  speed:
    ret_1s_threshold: 0.0015  # 0.002 → 0.0015 (25% 완화)
  participation:
    z_vol_threshold: 2.0      # 2.5 → 2.0 (대폭 완화)

detection:
  min_axes_required: 2        # 3 → 2
```

예상 효과: Recall +15-20%, FP/h +15-25
""")

# 놓친 급등 분석
missed = [r for r in results['detection_results'] if not r['detected']]

print(f"\n놓친 급등 분석 ({len(missed)}개):")
for m in missed[:5]:  # 처음 5개만
    print(f"  {m['file']} {m['surge_name']} ({m['strength']})")
```

**실행**:
```bash
python scripts/optimize_for_60_percent.py
```

---

## ✅ 작업 체크리스트

- [ ] Step 1: 급등 라벨 파일 생성
- [ ] Step 2: 12개 파일 배치 Detection
- [ ] Step 3: Recall 계산 (목표: 60%)
- [ ] Step 4: (필요 시) Threshold 조정 및 재실행

---

## 🚀 한 줄 실행

```bash
python scripts/create_surge_labels.py && \
python scripts/batch_detection.py && \
python scripts/calculate_batch_recall.py && \
python scripts/optimize_for_60_percent.py
```

---

## 📌 성공 기준 (수정됨)

### Phase 1.5 목표
- **Recall ≥ 60%** (21개 중 13개 이상)
- **평균 FP/h ≤ 40**
- **Latency Mean ≤ 30s**

**달성 시**: Phase 2로 이동
**미달 시**: Threshold 미세 조정 후 재실행