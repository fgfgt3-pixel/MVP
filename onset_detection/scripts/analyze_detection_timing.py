#!/usr/bin/env python
"""
급등 탐지 타이밍 분석
목적: 각 급등의 시작/피크 대비 언제 탐지했는지 확인
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 급등 정의 (시작, 피크, 종료)
surges_023790 = [
    {"name": "Surge1", "start": 1756688123304, "peak_offset": 180000, "strength": "중간"},  # 3분
    {"name": "Surge2", "start": 1756689969627, "peak_offset": 180000, "strength": "중간"}   # 3분
]

surges_413630 = [
    {"name": "Surge1", "time": "09:09-09:15", "peak_offset": 360000, "strength": "중간"},  # 6분
    {"name": "Surge2", "time": "10:01-10:14", "peak_offset": 780000, "strength": "강한"},  # 13분
    {"name": "Surge3", "time": "11:46-11:50", "peak_offset": 240000, "strength": "약한"},  # 4분
    {"name": "Surge4", "time": "13:29-13:37", "peak_offset": 480000, "strength": "중간"},  # 8분
    {"name": "Surge5", "time": "14:09-14:12", "peak_offset": 180000, "strength": "약한"}   # 3분
]

def load_events(file_path):
    """이벤트 로드"""
    events = []
    with open(file_path, 'r') as f:
        for line in f:
            events.append(json.loads(line))
    return events

def ms_to_kst(ms):
    """밀리초를 KST datetime으로 변환"""
    return pd.to_datetime(ms, unit='ms', utc=True).tz_convert('Asia/Seoul')

def analyze_file_timing(events, surges, data_path, file_name):
    """파일별 타이밍 분석"""
    df = pd.read_csv(data_path)

    # Column name normalization
    if 'time' in df.columns and 'ts' not in df.columns:
        df = df.rename(columns={'time': 'ts'})

    print(f"\n{'='*70}")
    print(f"{file_name} Timing Analysis")
    print(f"{'='*70}")

    results = []

    for surge in surges:
        surge_name = surge['name']
        surge_strength = surge['strength']

        # 급등 시작 시점
        if 'start' in surge:
            surge_start = surge['start']
        else:
            # 413630의 경우 데이터에서 시작 시점 추출
            time_str = surge['time'].split('-')[0]  # "09:09"
            hour, minute = map(int, time_str.split(':'))

            # 데이터의 첫 timestamp 가져오기
            first_ts = df['ts'].min()
            first_dt = ms_to_kst(first_ts)

            # 해당 시각으로 설정
            surge_dt = first_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            surge_start = int(surge_dt.timestamp() * 1000)

        surge_peak = surge_start + surge.get('peak_offset', 180000)

        # 해당 구간 탐지 이벤트 찾기
        detected_events = [
            e for e in events
            if surge_start - 30000 <= e['ts'] <= surge_peak + 30000
        ]

        if not detected_events:
            print(f"\nMISSED {surge_name} ({surge_strength})")
            results.append({
                "surge": surge_name,
                "strength": surge_strength,
                "detected": False,
                "detection_time_kst": None,
                "latency_from_start": None,
                "latency_to_peak": None
            })
            continue

        # 가장 빠른 탐지 시점
        first_detection = min(detected_events, key=lambda x: x['ts'])
        detection_ts = first_detection['ts']

        # 타이밍 계산
        latency_from_start = (detection_ts - surge_start) / 1000.0  # 초
        latency_to_peak = (surge_peak - detection_ts) / 1000.0

        # 백분율 계산 (시작→피크 구간 중 몇 %에서 탐지)
        surge_duration = (surge_peak - surge_start) / 1000.0
        detection_position_pct = (latency_from_start / surge_duration) * 100 if surge_duration > 0 else 0

        detection_dt = ms_to_kst(detection_ts)

        print(f"\nDETECTED {surge_name} ({surge_strength}):")
        print(f"   Detection time: {detection_dt.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"   From start: {latency_from_start:+.1f}s")
        print(f"   To peak: {latency_to_peak:.1f}s")
        print(f"   Position: {detection_position_pct:.1f}% of start-to-peak")
        print(f"   Alert count: {len(detected_events)}")

        # 평가
        if latency_from_start < 5:
            quality = "Excellent (<5s)"
        elif latency_from_start < 15:
            quality = "Good (5-15s)"
        elif latency_from_start < 30:
            quality = "Fair (15-30s)"
        else:
            quality = "Slow (>30s)"

        print(f"   Quality: {quality}")

        results.append({
            "surge": surge_name,
            "strength": surge_strength,
            "detected": True,
            "detection_time_kst": detection_dt.strftime('%H:%M:%S.%f')[:-3],
            "latency_from_start": latency_from_start,
            "latency_to_peak": latency_to_peak,
            "detection_position_pct": detection_position_pct,
            "quality": quality,
            "alert_count": len(detected_events)
        })

    return results

# 023790 분석
events_023790 = load_events(project_root / "onset_detection/data/events/strategy_c_plus_023790.jsonl")
results_023790 = analyze_file_timing(
    events_023790,
    surges_023790,
    project_root / "onset_detection/data/raw/023790_44indicators_realtime_20250901_clean.csv",
    "023790"
)

# 413630 분석
events_413630 = load_events(project_root / "onset_detection/data/events/strategy_c_plus_413630.jsonl")
results_413630 = analyze_file_timing(
    events_413630,
    surges_413630,
    project_root / "onset_detection/data/raw/413630_44indicators_realtime_20250911_clean.csv",
    "413630"
)

# 종합 통계
print(f"\n{'='*70}")
print("Overall Timing Statistics")
print(f"{'='*70}")

all_results = results_023790 + results_413630
detected_results = [r for r in all_results if r['detected']]

if detected_results:
    latencies = [r['latency_from_start'] for r in detected_results]
    positions = [r['detection_position_pct'] for r in detected_results]

    print(f"\nDetected surges: {len(detected_results)}/{len(all_results)}")
    print(f"Avg latency from start: {np.mean(latencies):.1f}s")
    print(f"Median latency from start: {np.median(latencies):.1f}s")
    print(f"Avg detection position: {np.mean(positions):.1f}% of start-to-peak")

# 강도별 분석
print(f"\n{'='*70}")
print("Timing by Surge Strength")
print(f"{'='*70}")

strengths = ["강한", "중간", "약한"]
for strength in strengths:
    strength_detected = [r for r in detected_results if r['strength'] == strength]
    strength_total = [r for r in all_results if r['strength'] == strength]

    if strength_total:
        recall = len(strength_detected) / len(strength_total)
        print(f"\n{strength} ({len(strength_detected)}/{len(strength_total)}, Recall {recall*100:.0f}%):")

        if strength_detected:
            avg_latency = np.mean([r['latency_from_start'] for r in strength_detected])
            avg_position = np.mean([r['detection_position_pct'] for r in strength_detected])
            print(f"  Avg latency: {avg_latency:.1f}s from start")
            print(f"  Avg position: {avg_position:.1f}% of start-to-peak")

# 결과 저장
summary = {
    "023790": results_023790,
    "413630": results_413630,
    "summary": {
        "total_surges": len(all_results),
        "detected_surges": len(detected_results),
        "avg_latency_from_start": float(np.mean(latencies)) if latencies else None,
        "median_latency_from_start": float(np.median(latencies)) if latencies else None,
        "avg_detection_position_pct": float(np.mean(positions)) if positions else None
    }
}

reports_dir = project_root / "onset_detection/reports"
reports_dir.mkdir(exist_ok=True)
with open(reports_dir / "detection_timing_analysis.json", "w", encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"\nResults saved: reports/detection_timing_analysis.json")
