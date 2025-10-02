#!/usr/bin/env python3
"""State Machine 결과 검증"""

import json
from pathlib import Path
from collections import Counter
import pandas as pd

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent

# 결과 로드
results_path = project_root / "onset_detection/data/events/state_machine_confirmed.jsonl"
with open(results_path, encoding='utf-8') as f:
    events = [json.loads(line) for line in f]

# 라벨 로드
labels_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
with open(labels_path, encoding='utf-8') as f:
    labels = json.load(f)

print("="*80)
print("State Machine 기본 통계")
print("="*80)
print(f"총 탐지: {len(events)}개")
print(f"총 급등: {len(labels)}개")
print(f"급등당 평균: {len(events) / len(labels):.1f}개")

# 종목별 탐지 수
stock_counts = Counter([e['stock_code'] for e in events])

print("\n종목별 탐지 수:")
for stock, count in stock_counts.most_common():
    print(f"  {stock}: {count}개")

# Pathway별 통계
pathway_counts = Counter([e.get('pathway', 'unknown') for e in events])
print(f"\nPathway별 통계:")
for pathway, count in pathway_counts.items():
    print(f"  {pathway}: {count}개 ({count/len(events)*100:.1f}%)")

# Recall 계산
print(f"\n{'='*80}")
print("Recall 분석")
print(f"{'='*80}")

detected_surges = []
missed_surges = []

for label in labels:
    file = label['file']
    surge_name = label['surge_name']
    strength = label['strength']
    start_ts = label['start_ts']
    end_ts = label['end_ts']

    # 해당 파일 이벤트만 필터
    file_events = [e for e in events if e['file'] == file]

    # ±30초 윈도우
    window_start = start_ts - 30000
    window_end = end_ts + 30000

    detected_events = [
        e for e in file_events
        if window_start <= e['ts'] <= window_end
    ]

    detected = len(detected_events) > 0

    result = {
        'file': file,
        'surge_name': surge_name,
        'strength': strength,
        'detected': detected,
        'detection_count': len(detected_events)
    }

    if detected:
        detected_surges.append(result)
        status = "[OK]"
    else:
        missed_surges.append(result)
        status = "[MISS]"

    print(f"{status} {file} - {surge_name} ({strength}): {len(detected_events)}개")

# 전체 Recall
total_surges = len(labels)
detected_count = len(detected_surges)
recall = detected_count / total_surges if total_surges > 0 else 0

print(f"\n{'='*80}")
print(f"전체 Recall: {recall*100:.1f}% ({detected_count}/{total_surges})")

# 강도별 Recall
for strength in ['강한', '중간', '약한']:
    strength_total = len([l for l in labels if l['strength'] == strength])
    strength_detected = len([d for d in detected_surges if d['strength'] == strength])
    strength_recall = strength_detected / strength_total if strength_total > 0 else 0
    print(f"  {strength}: {strength_recall*100:.1f}% ({strength_detected}/{strength_total})")

# Noise 분석
print(f"\n{'='*80}")
print("Noise 분석")
print(f"{'='*80}")

true_positive = 0
false_positive = 0

for event in events:
    event_file = event['file']
    event_ts = event['ts']

    # 해당 파일의 라벨
    file_labels = [l for l in labels if l['file'] == event_file]

    # 라벨 내부인가?
    is_in_label = False
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

total_detections = len(events)
noise_ratio = false_positive / total_detections if total_detections > 0 else 0

print(f"총 탐지: {total_detections}개")
print(f"  True Positive (급등 내부): {true_positive}개")
print(f"  False Positive (Noise): {false_positive}개")
print(f"  Noise 비율: {noise_ratio*100:.1f}%")

# 파일별 FP/h
print(f"\n{'='*80}")
print("파일별 FP/h")
print(f"{'='*80}")

total_fp_per_hour = 0
file_count = 0

for label in labels:
    file = label['file']
    file_labels = [l for l in labels if l['file'] == file]

    # 중복 제거
    if any(l['file'] == file for l in labels[:labels.index(label)]):
        continue

    file_events = [e for e in events if e['file'] == file]

    # FP 계산
    file_fp = 0
    for event in file_events:
        event_ts = event['ts']
        is_in_label = False
        for lbl in file_labels:
            window_start = lbl['start_ts'] - 30000
            window_end = lbl['end_ts'] + 30000
            if window_start <= event_ts <= window_end:
                is_in_label = True
                break
        if not is_in_label:
            file_fp += 1

    # 시간 범위
    data_path = project_root / f"onset_detection/data/raw/{file}"
    if data_path.exists():
        df = pd.read_csv(data_path)
        if 'time' in df.columns and 'ts' not in df.columns:
            df = df.rename(columns={'time': 'ts'})

        duration_ms = df['ts'].max() - df['ts'].min()
        duration_hours = duration_ms / (1000 * 3600)

        fp_per_hour = file_fp / duration_hours if duration_hours > 0 else 0
        total_fp_per_hour += fp_per_hour
        file_count += 1

        print(f"{file}: {fp_per_hour:.1f} FP/h ({file_fp}개 FP, {duration_hours:.1f}h)")

avg_fp_per_hour = total_fp_per_hour / file_count if file_count > 0 else 0
print(f"\n평균 FP/h: {avg_fp_per_hour:.1f}")

# 결과 저장
output_path = project_root / "onset_detection/reports/state_machine_validation.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump({
        'total_detections': len(events),
        'total_surges': len(labels),
        'avg_per_surge': len(events) / len(labels),
        'recall': {
            'total': recall,
            'detected_count': detected_count,
            'total_surges': total_surges,
            'by_strength': {
                strength: {
                    'detected': len([d for d in detected_surges if d['strength'] == strength]),
                    'total': len([l for l in labels if l['strength'] == strength])
                }
                for strength in ['강한', '중간', '약한']
            }
        },
        'noise': {
            'total_detections': total_detections,
            'true_positive': true_positive,
            'false_positive': false_positive,
            'noise_ratio': noise_ratio
        },
        'fp_per_hour': {
            'average': avg_fp_per_hour
        }
    }, f, indent=2, ensure_ascii=False)

print(f"\n저장: {output_path.relative_to(project_root)}")
