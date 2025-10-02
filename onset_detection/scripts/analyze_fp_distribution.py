#!/usr/bin/env python
"""
FP(False Positive) 분포 분석
목적: FP가 발생하는 시간대/패턴/특성 파악
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 이벤트 로드
events_path = project_root / "onset_detection/data/events/strategy_c_results.jsonl"
events = []
with open(events_path, 'r') as f:
    for line in f:
        events.append(json.loads(line))

confirmed = [e for e in events if e['event_type'] == 'onset_confirmed']

# 데이터 기간
data_path = project_root / "onset_detection/data/raw/023790_44indicators_realtime_20250901_clean.csv"
df = pd.read_csv(data_path)

# 알려진 급등 구간 정의 (±30초)
surge1_start = 1756688123304
surge1_end = surge1_start + 180000  # +3분 (Modify 1 기준)
surge1_window_start = surge1_start - 30000
surge1_window_end = surge1_end + 30000

surge2_start = 1756689969627
surge2_end = surge2_start + 180000
surge2_window_start = surge2_start - 30000
surge2_window_end = surge2_end + 30000

# TP vs FP 분류
tp_events = []
fp_events = []

for e in confirmed:
    ts = e['ts']
    if (surge1_window_start <= ts <= surge1_window_end) or \
       (surge2_window_start <= ts <= surge2_window_end):
        tp_events.append(e)
    else:
        fp_events.append(e)

print("=" * 60)
print("FP Distribution Analysis")
print("=" * 60)
print(f"\nTotal Confirmed: {len(confirmed)}")
print(f"True Positives (TP): {len(tp_events)}")
print(f"False Positives (FP): {len(fp_events)}")
print(f"FP Rate: {len(fp_events)/len(confirmed)*100:.1f}%")

# FP 시간대 분석
fp_df = pd.DataFrame(fp_events)
morning = 0
afternoon = 0
hour_dist = {}

if not fp_df.empty:
    fp_df['datetime'] = pd.to_datetime(fp_df['ts'], unit='ms', utc=True).dt.tz_convert('Asia/Seoul')
    fp_df['hour'] = fp_df['datetime'].dt.hour
    fp_df['minute'] = fp_df['datetime'].dt.minute

    print("\n### FP Time Distribution (by hour)")
    hour_dist = fp_df['hour'].value_counts().sort_index()
    for hour, count in hour_dist.items():
        print(f"  {hour:02d}h: {count}")

    # 장 초반 vs 후반
    morning = len(fp_df[fp_df['hour'] < 12])
    afternoon = len(fp_df[fp_df['hour'] >= 12])
    print(f"\nMorning (09-12h): {morning} ({morning/len(fp_df)*100:.1f}%)")
    print(f"Afternoon (12-15h): {afternoon} ({afternoon/len(fp_df)*100:.1f}%)")

# FP 특성 분석 (evidence)
print("\n### FP Characteristics")

# Axes 분포
axes_counts = {'price': 0, 'volume': 0, 'friction': 0}
onset_strengths = []

for e in fp_events:
    evidence = e.get('evidence', {})
    axes = evidence.get('axes', [])
    for axis in axes:
        if axis in axes_counts:
            axes_counts[axis] += 1

    strength = evidence.get('onset_strength', 0)
    onset_strengths.append(strength)

print("Axes frequency:")
for axis, count in axes_counts.items():
    print(f"  {axis}: {count} ({count/len(fp_events)*100:.1f}%)")

print(f"\nOnset Strength statistics:")
print(f"  Mean: {np.mean(onset_strengths):.3f}")
print(f"  Median: {np.median(onset_strengths):.3f}")
print(f"  Min: {np.min(onset_strengths):.3f}")
print(f"  Max: {np.max(onset_strengths):.3f}")
print(f"  P25: {np.percentile(onset_strengths, 25):.3f}")

# FP 군집 분석 (연속 발생 여부)
print("\n### FP Cluster Analysis")
fp_timestamps = sorted([e['ts'] for e in fp_events])
clusters = []
current_cluster = [fp_timestamps[0]]

for i in range(1, len(fp_timestamps)):
    # 5분(300초) 이내면 같은 군집
    if (fp_timestamps[i] - current_cluster[-1]) <= 300000:
        current_cluster.append(fp_timestamps[i])
    else:
        clusters.append(current_cluster)
        current_cluster = [fp_timestamps[i]]
clusters.append(current_cluster)

print(f"Total clusters: {len(clusters)}")
print(f"Average cluster size: {np.mean([len(c) for c in clusters]):.1f}")
print(f"Max cluster size: {max([len(c) for c in clusters])}")

# 큰 군집 (5개 이상) 분석
large_clusters = [c for c in clusters if len(c) >= 5]
if large_clusters:
    print(f"\nLarge clusters (>=5): {len(large_clusters)}")
    for i, cluster in enumerate(large_clusters[:5], 1):
        start_dt = pd.to_datetime(cluster[0], unit='ms', utc=True).tz_convert('Asia/Seoul')
        print(f"  Cluster {i}: {len(cluster)}, start={start_dt.strftime('%H:%M:%S')}")

# 결과 저장
summary = {
    "total_confirmed": len(confirmed),
    "true_positives": len(tp_events),
    "false_positives": len(fp_events),
    "fp_rate": len(fp_events) / len(confirmed),
    "fp_by_hour": hour_dist.to_dict() if not fp_df.empty else {},
    "fp_morning": morning if not fp_df.empty else 0,
    "fp_afternoon": afternoon if not fp_df.empty else 0,
    "axes_distribution": axes_counts,
    "onset_strength_stats": {
        "mean": float(np.mean(onset_strengths)),
        "median": float(np.median(onset_strengths)),
        "p25": float(np.percentile(onset_strengths, 25))
    },
    "clusters": {
        "total": len(clusters),
        "avg_size": float(np.mean([len(c) for c in clusters])),
        "large_clusters": len(large_clusters)
    }
}

reports_dir = project_root / "onset_detection/reports"
reports_dir.mkdir(exist_ok=True)
with open(reports_dir / "fp_distribution_analysis.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"\nResults saved: reports/fp_distribution_analysis.json")

# 핵심 인사이트 제시
print("\n" + "=" * 60)
print("Key Insights")
print("=" * 60)

if len(large_clusters) > 0:
    print("WARNING: FPs occur in clusters -> Refractory extension effective")
    print(f"   Suggestion: Increase refractory_s to 45-60s")

if morning > afternoon * 1.5:
    print("WARNING: FPs concentrated in morning -> Strengthen early session thresholds")
    print(f"   Suggestion: Increase thresholds for 09-11h period")

if np.median(onset_strengths) < 0.7:
    print("WARNING: Many weak signals -> Add onset_strength threshold")
    print(f"   Suggestion: Add onset_strength >= 0.7 condition")

if axes_counts['friction'] < len(fp_events) * 0.3:
    print("WARNING: Low friction axis contribution -> Keep min_axes=2")
