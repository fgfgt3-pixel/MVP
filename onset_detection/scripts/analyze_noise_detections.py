#!/usr/bin/env python3
"""
라벨링 구간 외부의 Noise 탐지 분석
목적: 실제 급등이 아닌 곳에서 얼마나 오탐지되었는지 확인
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent

# 라벨 로드
labels_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
with open(labels_path, encoding='utf-8') as f:
    labels = json.load(f)

# 파일별로 라벨 그룹화
labels_by_file = defaultdict(list)
for label in labels:
    labels_by_file[label['file']].append(label)

print("="*80)
print("Noise 탐지 분석 (라벨 구간 외부)")
print("="*80)

total_detections = 0
noise_detections = 0
true_detections = 0

file_analysis = []

for filename, file_labels in sorted(labels_by_file.items()):
    stock_code = filename.split('_')[0]
    date = filename.split('_')[-2]

    # Gate+Score 이벤트 로드
    event_file = f"gate_score_{stock_code}_{date}.jsonl"
    event_path = project_root / "onset_detection/data/events/gate_score" / event_file

    if not event_path.exists():
        continue

    events = []
    with open(event_path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    total_events = len(events)

    # 각 이벤트가 라벨 구간 내부인지 확인
    true_positive = 0
    false_positive = 0

    for event in events:
        event_ts = event['ts']
        is_in_label = False

        # ±30초 여유를 둔 라벨 구간 내부인지 확인
        for label in file_labels:
            window_start = label['start_ts'] - 30000
            window_end = label['end_ts'] + 30000

            if window_start <= event_ts <= window_end:
                is_in_label = True
                break

        if is_in_label:
            true_positive += 1
        else:
            false_positive += 1

    noise_rate = (false_positive / total_events * 100) if total_events > 0 else 0

    print(f"\n{filename}")
    print(f"  총 탐지: {total_events}개")
    print(f"  라벨 내부 (True Positive): {true_positive}개 ({true_positive/total_events*100:.1f}%)")
    print(f"  라벨 외부 (Noise/FP): {false_positive}개 ({noise_rate:.1f}%)")
    print(f"  급등 라벨 수: {len(file_labels)}개")

    total_detections += total_events
    true_detections += true_positive
    noise_detections += false_positive

    file_analysis.append({
        'file': filename,
        'total_events': total_events,
        'true_positive': true_positive,
        'false_positive': false_positive,
        'noise_rate': noise_rate,
        'num_labels': len(file_labels)
    })

# 전체 요약
print("\n" + "="*80)
print("전체 Noise 분석")
print("="*80)

overall_noise_rate = (noise_detections / total_detections * 100) if total_detections > 0 else 0

print(f"\n총 탐지: {total_detections}개")
print(f"  라벨 내부 (실제 급등): {true_detections}개 ({true_detections/total_detections*100:.1f}%)")
print(f"  라벨 외부 (Noise): {noise_detections}개 ({overall_noise_rate:.1f}%)")

print(f"\nNoise 비율: {overall_noise_rate:.1f}%")

# Noise가 많은 파일 Top 5
print(f"\n[Noise 많은 파일 Top 5]")
sorted_by_fp = sorted(file_analysis, key=lambda x: x['false_positive'], reverse=True)
for i, item in enumerate(sorted_by_fp[:5], 1):
    print(f"{i}. {item['file']}: {item['false_positive']}개 Noise ({item['noise_rate']:.1f}%)")

# Noise 비율 높은 파일 Top 5
print(f"\n[Noise 비율 높은 파일 Top 5]")
sorted_by_rate = sorted(file_analysis, key=lambda x: x['noise_rate'], reverse=True)
for i, item in enumerate(sorted_by_rate[:5], 1):
    print(f"{i}. {item['file']}: {item['noise_rate']:.1f}% ({item['false_positive']}/{item['total_events']})")

# 평가
print("\n" + "="*80)
print("평가 및 권장사항")
print("="*80)

if overall_noise_rate > 90:
    print(f"""
[심각] Noise 비율 {overall_noise_rate:.1f}% - 대부분이 오탐지
→ Score threshold를 대폭 상향해야 함
→ 권장: threshold 70 → 90-100
""")
elif overall_noise_rate > 70:
    print(f"""
[경고] Noise 비율 {overall_noise_rate:.1f}% - 오탐지 많음
→ Score threshold 상향 필요
→ 권장: threshold 70 → 85-90
""")
elif overall_noise_rate > 50:
    print(f"""
[주의] Noise 비율 {overall_noise_rate:.1f}% - 오탐지 적지 않음
→ Score threshold 조정 고려
→ 권장: threshold 70 → 80-85
""")
else:
    print(f"""
[양호] Noise 비율 {overall_noise_rate:.1f}% - 대부분 실제 급등
→ 현재 threshold 70 적절
→ 추가 조정 불필요할 수 있음
""")

# Noise 상세 분석 (시간대별)
print("\n" + "="*80)
print("Noise 분포 추가 정보")
print("="*80)

# 파일당 평균 Noise
avg_noise_per_file = noise_detections / len(file_analysis) if file_analysis else 0
avg_tp_per_file = true_detections / len(file_analysis) if file_analysis else 0

print(f"\n파일당 평균:")
print(f"  실제 급등 탐지: {avg_tp_per_file:.1f}개")
print(f"  Noise 탐지: {avg_noise_per_file:.1f}개")

# 급등당 평균 탐지 수
total_labels = sum([len(labels_by_file[f]) for f in labels_by_file])
avg_detections_per_surge = true_detections / total_labels if total_labels > 0 else 0

print(f"\n급등당 평균 탐지:")
print(f"  {avg_detections_per_surge:.1f}개 (중복 포함)")

if avg_detections_per_surge > 200:
    print(f"  → 급등당 탐지가 너무 많음 (과도한 중복)")
    print(f"  → Refractory 또는 threshold 조정 필요")

# 저장
output_path = project_root / "onset_detection/reports/noise_analysis.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding='utf-8') as f:
    json.dump({
        "summary": {
            "total_detections": total_detections,
            "true_positive": true_detections,
            "false_positive": noise_detections,
            "noise_rate": overall_noise_rate
        },
        "by_file": file_analysis,
        "recommendations": {
            "current_threshold": 70,
            "recommended_threshold": 85 if overall_noise_rate > 70 else 80,
            "noise_severity": "high" if overall_noise_rate > 70 else "medium" if overall_noise_rate > 50 else "low"
        }
    }, f, indent=2, ensure_ascii=False)

print(f"\n저장: {output_path.relative_to(project_root)}")
