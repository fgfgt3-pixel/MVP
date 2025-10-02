#!/usr/bin/env python3
"""
Gate+Score 시스템 Recall 계산
"""

import pandas as pd
import json
import numpy as np
from pathlib import Path

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent

# 라벨 로드
labels_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
with open(labels_path, encoding='utf-8') as f:
    labels = json.load(f)

print("="*80)
print(f"Gate+Score Recall 계산 ({len(labels)}개 급등)")
print("="*80)

detection_results = []

for label in labels:
    file = label['file']
    stock_code = label['stock_code']
    date = label['date']
    surge_name = label['surge_name']
    strength = label['strength']

    start_ts = label['start_ts']
    end_ts = label['end_ts']

    # 이벤트 파일 로드
    event_file = f"gate_score_{stock_code}_{date}.jsonl"
    event_path = project_root / "onset_detection/data/events/gate_score" / event_file

    if not event_path.exists():
        print(f"[WARNING] 이벤트 파일 없음: {event_path.name}")
        detection_results.append({
            **label,
            "detected": False,
            "detection_ts": None,
            "latency_s": None,
            "num_alerts": 0,
            "score": None
        })
        continue

    # 이벤트 로드
    events = []
    with open(event_path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    # 급등 구간 내 탐지 여부 (±30초 허용)
    window_start = start_ts - 30000
    window_end = end_ts + 30000

    detected_events = [
        e for e in events
        if window_start <= e['ts'] <= window_end
    ]

    if detected_events:
        # 가장 빠른 탐지
        first_detection = min(detected_events, key=lambda x: x['ts'])
        detection_ts = first_detection['ts']
        latency_s = (detection_ts - start_ts) / 1000.0
        score = first_detection.get('score', 0)

        detection_results.append({
            **label,
            "detected": True,
            "detection_ts": detection_ts,
            "latency_s": latency_s,
            "num_alerts": len(detected_events),
            "score": score
        })

        print(f"[OK] {file} {surge_name} ({strength}): {latency_s:+.1f}s, {len(detected_events)} alerts, score={score:.1f}")
    else:
        detection_results.append({
            **label,
            "detected": False,
            "detection_ts": None,
            "latency_s": None,
            "num_alerts": 0,
            "score": None
        })

        print(f"[MISS] {file} {surge_name} ({strength}): 미탐지")

# 통계
print("\n" + "="*80)
print("Recall 통계")
print("="*80)

detected = [r for r in detection_results if r['detected']]
total_recall = len(detected) / len(detection_results) if detection_results else 0

print(f"\n전체 Recall: {total_recall*100:.1f}% ({len(detected)}/{len(detection_results)})")

# 강도별
recall_by_strength = {}
for strength in ["강한", "중간", "약한"]:
    strength_total = [r for r in detection_results if r['strength'] == strength]
    strength_detected = [r for r in detected if r['strength'] == strength]

    if strength_total:
        strength_recall = len(strength_detected) / len(strength_total)
        recall_by_strength[strength] = strength_recall
        print(f"{strength}: {strength_recall*100:.1f}% ({len(strength_detected)}/{len(strength_total)})")
    else:
        recall_by_strength[strength] = 0.0

# Latency 분석
latencies = [r['latency_s'] for r in detected]
if latencies:
    print(f"\nLatency 통계:")
    print(f"  Mean: {np.mean(latencies):.1f}s")
    print(f"  Median: {np.median(latencies):.1f}s")
    print(f"  Min: {np.min(latencies):.1f}s")
    print(f"  Max: {np.max(latencies):.1f}s")
    print(f"  Std: {np.std(latencies):.1f}s")

# Score 분석
scores = [r['score'] for r in detected if r['score']]
if scores:
    print(f"\nScore 분포 (탐지된 급등):")
    print(f"  Mean: {np.mean(scores):.1f}")
    print(f"  Median: {np.median(scores):.1f}")
    print(f"  Min: {np.min(scores):.1f}")
    print(f"  Max: {np.max(scores):.1f}")
    print(f"  P25: {np.percentile(scores, 25):.1f}")
    print(f"  P75: {np.percentile(scores, 75):.1f}")

# 목표 달성 여부
print("\n" + "="*80)
print("목표 달성 평가")
print("="*80)

if total_recall >= 0.60:
    print(f"[OK] Recall 목표 달성! (Recall {total_recall*100:.1f}% >= 60%)")
else:
    gap = 0.60 - total_recall
    needed = int(np.ceil(gap * len(detection_results)))
    print(f"[MISS] Recall 목표 미달 (Recall {total_recall*100:.1f}% < 60%)")
    print(f"       {needed}개 더 탐지 필요")

# FP/h 정보
summary_path = project_root / "onset_detection/reports/gate_score_summary.json"
if summary_path.exists():
    with open(summary_path, encoding='utf-8') as f:
        summary = json.load(f)
    fp_per_hour = summary['summary']['avg_fp_per_hour']
    print(f"\n평균 FP/h: {fp_per_hour:.1f}")
    if fp_per_hour > 40:
        print(f"[WARNING] FP/h 목표 초과 ({fp_per_hour:.1f} > 40)")
        print(f"          Score threshold 상향 필요 (현재 70)")

# 저장
output_path = project_root / "onset_detection/reports/gate_score_recall_results.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding='utf-8') as f:
    json.dump({
        "detection_results": detection_results,
        "summary": {
            "total_surges": len(detection_results),
            "detected_surges": len(detected),
            "total_recall": total_recall,
            "recall_by_strength": recall_by_strength,
            "latency_stats": {
                "mean": float(np.mean(latencies)) if latencies else None,
                "median": float(np.median(latencies)) if latencies else None,
                "min": float(np.min(latencies)) if latencies else None,
                "max": float(np.max(latencies)) if latencies else None,
                "std": float(np.std(latencies)) if latencies else None
            },
            "score_stats": {
                "mean": float(np.mean(scores)) if scores else None,
                "median": float(np.median(scores)) if scores else None,
                "min": float(np.min(scores)) if scores else None,
                "max": float(np.max(scores)) if scores else None
            }
        }
    }, f, indent=2, ensure_ascii=False)

print(f"\n결과 저장: {output_path.relative_to(project_root)}")
