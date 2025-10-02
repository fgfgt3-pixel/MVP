#!/usr/bin/env python3
"""
Noise의 Score 분포 분석
목적: 어느 threshold에서 Noise가 걸러지는가?
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
print("Noise Score 분포 분석")
print("="*80)

all_noise_scores = []
all_signal_scores = []
data_dir = project_root / "onset_detection/data/events/gate_score"

for label in labels:
    file = label['file']
    start_ts = label['start_ts']
    end_ts = label['end_ts']

    # 탐지 이벤트 로드
    stock_code = label['stock_code']
    date = label['date']
    event_file = f"gate_score_{stock_code}_{date}.jsonl"
    event_path = data_dir / event_file

    if not event_path.exists():
        continue

    with open(event_path, encoding='utf-8') as f:
        events = [json.loads(line) for line in f if line.strip()]

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
if all_signal_scores:
    print(f"  Mean: {np.mean(all_signal_scores):.1f}")
    print(f"  Median: {np.median(all_signal_scores):.1f}")
    print(f"  P25: {np.percentile(all_signal_scores, 25):.1f}")
    print(f"  Min: {np.min(all_signal_scores):.1f}")
    print(f"  Max: {np.max(all_signal_scores):.1f}")

print(f"\nNoise (급등 외부): {len(all_noise_scores)}개")
if all_noise_scores:
    print(f"  Mean: {np.mean(all_noise_scores):.1f}")
    print(f"  Median: {np.median(all_noise_scores):.1f}")
    print(f"  P75: {np.percentile(all_noise_scores, 75):.1f}")
    print(f"  P90: {np.percentile(all_noise_scores, 90):.1f}")
    print(f"  P95: {np.percentile(all_noise_scores, 95):.1f}")
    print(f"  Max: {np.max(all_noise_scores):.1f}")

# Threshold 시뮬레이션
print("\n" + "="*80)
print("Threshold별 효과 예측")
print("="*80)

for threshold in [75, 80, 85, 90, 95, 100]:
    signal_pass = sum(s >= threshold for s in all_signal_scores)
    noise_pass = sum(s >= threshold for s in all_noise_scores)

    signal_rate = signal_pass / len(all_signal_scores) * 100 if all_signal_scores else 0
    noise_rate = noise_pass / len(all_noise_scores) * 100 if all_noise_scores else 0

    total_pass = signal_pass + noise_pass
    noise_ratio = noise_pass / total_pass * 100 if total_pass > 0 else 0

    print(f"\nThreshold = {threshold}:")
    print(f"  Signal 통과: {signal_rate:.1f}% ({signal_pass}/{len(all_signal_scores)})")
    print(f"  Noise 통과: {noise_rate:.1f}% ({noise_pass}/{len(all_noise_scores)})")
    print(f"  총 탐지: {total_pass}개")
    print(f"  Noise 비율: {noise_ratio:.1f}%")

# 최적 threshold 추천
print("\n" + "="*80)
print("권장 Threshold (Noise < 40% 목표)")
print("="*80)

# 목표: Noise 비율 < 40%
best_threshold = None
for threshold in range(70, 121):
    signal_pass = sum(s >= threshold for s in all_signal_scores)
    noise_pass = sum(s >= threshold for s in all_noise_scores)
    total_pass = signal_pass + noise_pass

    if total_pass == 0:
        continue

    noise_ratio = noise_pass / total_pass
    signal_rate = signal_pass / len(all_signal_scores) if all_signal_scores else 0

    if noise_ratio < 0.4 and best_threshold is None:  # 40% 미만 최초
        best_threshold = threshold
        print(f"\n[최적] Threshold = {threshold}:")
        print(f"  Signal Recall: {signal_rate*100:.1f}% ({signal_pass}/{len(all_signal_scores)})")
        print(f"  Noise 비율: {noise_ratio*100:.1f}%")
        print(f"  총 탐지: {total_pass}개")
        print(f"  Noise 탐지: {noise_pass}개")

# 추가 옵션
print("\n[추가 옵션]")
for target_noise in [30, 20, 10]:
    for threshold in range(70, 121):
        signal_pass = sum(s >= threshold for s in all_signal_scores)
        noise_pass = sum(s >= threshold for s in all_noise_scores)
        total_pass = signal_pass + noise_pass

        if total_pass == 0:
            continue

        noise_ratio = noise_pass / total_pass
        signal_rate = signal_pass / len(all_signal_scores) if all_signal_scores else 0

        if noise_ratio < target_noise/100:
            print(f"\nNoise < {target_noise}%: Threshold = {threshold}")
            print(f"  Signal Recall: {signal_rate*100:.1f}%")
            print(f"  Noise 비율: {noise_ratio*100:.1f}%")
            print(f"  총 탐지: {total_pass}개")
            break

# 저장
output_path = project_root / "onset_detection/reports/noise_score_analysis.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

# Threshold별 상세 결과
threshold_results = []
for threshold in range(70, 121):
    signal_pass = sum(s >= threshold for s in all_signal_scores)
    noise_pass = sum(s >= threshold for s in all_noise_scores)
    total_pass = signal_pass + noise_pass

    if total_pass > 0:
        threshold_results.append({
            'threshold': threshold,
            'signal_pass': signal_pass,
            'noise_pass': noise_pass,
            'total_pass': total_pass,
            'signal_recall': signal_pass / len(all_signal_scores) if all_signal_scores else 0,
            'noise_ratio': noise_pass / total_pass
        })

with open(output_path, "w", encoding='utf-8') as f:
    json.dump({
        "signal_scores": {
            "count": len(all_signal_scores),
            "mean": float(np.mean(all_signal_scores)) if all_signal_scores else None,
            "median": float(np.median(all_signal_scores)) if all_signal_scores else None,
            "p25": float(np.percentile(all_signal_scores, 25)) if all_signal_scores else None
        },
        "noise_scores": {
            "count": len(all_noise_scores),
            "mean": float(np.mean(all_noise_scores)) if all_noise_scores else None,
            "median": float(np.median(all_noise_scores)) if all_noise_scores else None,
            "p75": float(np.percentile(all_noise_scores, 75)) if all_noise_scores else None,
            "p90": float(np.percentile(all_noise_scores, 90)) if all_noise_scores else None
        },
        "threshold_simulation": threshold_results,
        "recommendation": {
            "best_threshold": best_threshold,
            "target": "Noise < 40%"
        }
    }, f, indent=2, ensure_ascii=False)

print(f"\n저장: {output_path.relative_to(project_root)}")
