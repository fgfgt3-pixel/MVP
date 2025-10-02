#!/usr/bin/env python
"""
413630 파일 Recall 검증
급등 구간 타임스탬프 변환 및 탐지 확인
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import pytz
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 파일 로드
csv_path = project_root / "onset_detection/data/raw/413630_44indicators_realtime_20250911_clean.csv"
events_path = project_root / "onset_detection/data/events/strategy_c_plus_413630.jsonl"

df = pd.read_csv(csv_path)
print(f"CSV loaded: {len(df):,} rows")

# 타임스탬프 범위 확인
df['datetime'] = pd.to_datetime(df['time'], unit='ms', utc=True).dt.tz_convert('Asia/Seoul')
print(f"Time range: {df['datetime'].min()} ~ {df['datetime'].max()}")

# 급등 구간 정의 (사용자 제공 정보 기반)
# 날짜: 2025-09-11 (파일명 기준)
kst = pytz.timezone('Asia/Seoul')
date = datetime(2025, 9, 11, tzinfo=kst)

surges = [
    {
        "name": "Surge 1",
        "start_time": "09:09",
        "end_time": "09:15",
        "strength": "중간",
        "note": "마지막 4분 하락"
    },
    {
        "name": "Surge 2",
        "start_time": "10:01",
        "end_time": "10:14",
        "strength": "강한",
        "note": "마지막 4분 하락"
    },
    {
        "name": "Surge 3",
        "start_time": "11:46",
        "end_time": "11:50",
        "strength": "약한",
        "note": "마지막 3분 하락"
    },
    {
        "name": "Surge 4",
        "start_time": "13:29",
        "end_time": "13:37",
        "strength": "중간",
        "note": "마지막 4분 하락"
    },
    {
        "name": "Surge 5",
        "start_time": "14:09",
        "end_time": "14:12",
        "strength": "약한",
        "note": "마지막 2분 하락"
    }
]

# 타임스탬프 변환 (ms epoch)
for surge in surges:
    start_h, start_m = map(int, surge["start_time"].split(":"))
    end_h, end_m = map(int, surge["end_time"].split(":"))

    start_dt = kst.localize(datetime(2025, 9, 11, start_h, start_m, 0))
    end_dt = kst.localize(datetime(2025, 9, 11, end_h, end_m, 0))

    surge["start_ts"] = int(start_dt.timestamp() * 1000)
    surge["end_ts"] = int(end_dt.timestamp() * 1000)
    surge["window_start"] = surge["start_ts"] - 30000  # -30s
    surge["window_end"] = surge["end_ts"]  # end at surge end (no extension)

print("\n" + "="*70)
print("Surge Definitions (413630)")
print("="*70)

for i, surge in enumerate(surges, 1):
    print(f"\n{surge['name']} ({surge['strength']} 급등):")
    print(f"  Time: {surge['start_time']} ~ {surge['end_time']} ({surge['note']})")
    print(f"  Start TS: {surge['start_ts']}")
    print(f"  End TS: {surge['end_ts']}")
    print(f"  Detection Window: {surge['window_start']} ~ {surge['window_end']}")

    # CSV에서 해당 구간 확인
    surge_df = df[(df['time'] >= surge['start_ts']) & (df['time'] <= surge['end_ts'])]
    print(f"  CSV rows in surge: {len(surge_df)}")

# 이벤트 로드
events = []
with open(events_path, 'r') as f:
    for line in f:
        events.append(json.loads(line))

print(f"\n\nTotal events detected: {len(events)}")

# 각 급등별 탐지 확인
print("\n" + "="*70)
print("Detection Results")
print("="*70)

detected_count = 0
detection_details = []

for surge in surges:
    # Detection window 내 이벤트 찾기
    detected_events = [
        e for e in events
        if surge['window_start'] <= e['ts'] <= surge['window_end']
    ]

    is_detected = len(detected_events) > 0
    if is_detected:
        detected_count += 1

    status = "DETECTED" if is_detected else "MISSED"

    print(f"\n{surge['name']} ({surge['strength']}): {status}")
    print(f"  Window: {surge['start_time']} ~ {surge['end_time']}")
    print(f"  Alerts: {len(detected_events)}")

    if detected_events:
        for i, evt in enumerate(detected_events[:3], 1):  # 처음 3개만 표시
            evt_dt = pd.to_datetime(evt['ts'], unit='ms', utc=True).tz_convert('Asia/Seoul')
            print(f"    Alert {i}: {evt_dt.strftime('%H:%M:%S')}")
            if i == 3 and len(detected_events) > 3:
                print(f"    ... ({len(detected_events)-3} more)")

    detection_details.append({
        "surge": surge["name"],
        "strength": surge["strength"],
        "detected": is_detected,
        "alert_count": len(detected_events),
        "window": f"{surge['start_time']} ~ {surge['end_time']}"
    })

# 성능 요약
recall = detected_count / len(surges)
duration_hours = (df['time'].max() - df['time'].min()) / (1000 * 3600)
fp_per_hour = len(events) / duration_hours

print("\n" + "="*70)
print("Performance Summary (413630)")
print("="*70)
print(f"\nRecall: {recall*100:.0f}% ({detected_count}/{len(surges)} surges)")
print(f"FP/h: {fp_per_hour:.1f}")
print(f"Total alerts: {len(events)}")
print(f"Duration: {duration_hours:.2f}h")

# 급등별 강도 분석
print("\n### Detection by Surge Strength:")
strong = [d for d in detection_details if d['strength'] == '강한']
medium = [d for d in detection_details if d['strength'] == '중간']
weak = [d for d in detection_details if d['strength'] == '약한']

print(f"강한 급등: {sum(d['detected'] for d in strong)}/{len(strong)} detected")
print(f"중간 급등: {sum(d['detected'] for d in medium)}/{len(medium)} detected")
print(f"약한 급등: {sum(d['detected'] for d in weak)}/{len(weak)} detected")

# 결과 저장
result = {
    "file": "413630",
    "total_surges": len(surges),
    "detected_surges": detected_count,
    "recall": recall,
    "fp_per_hour": fp_per_hour,
    "total_alerts": len(events),
    "duration_hours": duration_hours,
    "surges": surges,
    "detection_details": detection_details,
    "by_strength": {
        "강한": {"total": len(strong), "detected": sum(d['detected'] for d in strong)},
        "중간": {"total": len(medium), "detected": sum(d['detected'] for d in medium)},
        "약한": {"total": len(weak), "detected": sum(d['detected'] for d in weak)}
    }
}

output_path = project_root / "onset_detection/reports/recall_413630_validation.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"\n\nResults saved: {output_path}")

# 목표 달성 여부
print("\n" + "="*70)
print("Goal Achievement (413630)")
print("="*70)

goals = {
    "Recall ≥ 65%": recall >= 0.65,
    "FP/h ≤ 30": fp_per_hour <= 30
}

for goal, met in goals.items():
    status = "OK" if met else "FAIL"
    print(f"{goal}: {status}")

if all(goals.values()):
    print("\nPhase 1 Goal Achieved (413630 Validation Complete)")
else:
    print("\nSome goals not met")
