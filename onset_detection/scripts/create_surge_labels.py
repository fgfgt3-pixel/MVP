#!/usr/bin/env python3
"""
12개 파일 23개 급등 라벨링 데이터 생성
"""

import pandas as pd
import json
from pathlib import Path

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent

# 급등 라벨 정의 (labeling.md 기준)
surge_labels = {
    "023790_20250901": [
        {"time": "09:55", "end_time": "09:58", "strength": "중간", "name": "Surge1"},
        {"time": "10:26", "end_time": "10:35", "strength": "중간", "name": "Surge2"}
    ],
    "023790_20250902": [
        {"time": "09:03", "end_time": "09:12", "strength": "강한", "name": "Surge1"}
    ],
    "054540_20250901": [
        {"time": "10:08", "end_time": "10:19", "strength": "강한", "name": "Surge1"}
    ],
    "054540_20250902": [
        {"time": "09:45", "end_time": "09:48", "strength": "약한", "name": "Surge1"},
        {"time": "09:51", "end_time": "10:03", "strength": "중간", "name": "Surge2"}
    ],
    "054540_20250903": [
        {"time": "09:20", "end_time": "09:25", "strength": "약한", "name": "Surge1"}
    ],
    "362320_20250901": [
        {"time": "13:00", "end_time": "13:04", "strength": "약한", "name": "Surge1"}
    ],
    "097230_20250902": [
        {"time": "09:13", "end_time": "09:28", "strength": "강한", "name": "Surge1"}
    ],
    "097230_20250903": [
        {"time": "09:13", "end_time": "09:17", "strength": "약한", "name": "Surge1"},
        {"time": "09:32", "end_time": "09:37", "strength": "약한", "name": "Surge2"}
    ],
    "355690_20250903": [
        {"time": "10:37", "end_time": "10:44", "strength": "약한", "name": "Surge1"},
        {"time": "10:49", "end_time": "10:57", "strength": "중간", "name": "Surge2"}
    ],
    "049470_20250903": [
        {"time": "14:04", "end_time": "14:15", "strength": "약한", "name": "Surge1"}
    ],
    "208640_20250903": [
        {"time": "09:42", "end_time": "09:44", "strength": "중간", "name": "Surge1"}
    ],
    "413630_20250911": [
        {"time": "09:09", "end_time": "09:15", "strength": "중간", "name": "Surge1"},
        {"time": "10:01", "end_time": "10:14", "strength": "강한", "name": "Surge2"},
        {"time": "11:46", "end_time": "11:50", "strength": "약한", "name": "Surge3"},
        {"time": "13:29", "end_time": "13:37", "strength": "중간", "name": "Surge4"},
        {"time": "14:09", "end_time": "14:12", "strength": "약한", "name": "Surge5"}
    ]
}

def calculate_surge_timestamps(file_key, surge_info, data_dir):
    """급등 시작/종료 timestamp 계산"""

    # 파일명 생성
    stock_code, date = file_key.split('_')
    filename = f"{stock_code}_44indicators_realtime_{date}_clean.csv"
    filepath = data_dir / filename

    if not filepath.exists():
        print(f"[WARNING] File not found: {filepath}")
        return None

    # CSV 로드 (첫 행만)
    df = pd.read_csv(filepath, nrows=1)

    # Column 이름 확인 및 매핑
    if 'time' in df.columns and 'ts' not in df.columns:
        ts_col = 'time'
    else:
        ts_col = 'ts'

    first_ts = df[ts_col].iloc[0]
    first_dt = pd.to_datetime(first_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')

    results = []
    for surge in surge_info:
        # 시작 시간
        start_hour, start_minute = map(int, surge['time'].split(':'))
        surge_start_dt = first_dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        surge_start_ts = int(surge_start_dt.timestamp() * 1000)

        # 종료 시간
        end_hour, end_minute = map(int, surge['end_time'].split(':'))
        surge_end_dt = first_dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        surge_end_ts = int(surge_end_dt.timestamp() * 1000)

        duration_min = (surge_end_ts - surge_start_ts) / (60 * 1000)

        results.append({
            "file": filename,
            "stock_code": stock_code,
            "date": date,
            "surge_name": surge['name'],
            "strength": surge['strength'],
            "start_time": surge['time'],
            "end_time": surge['end_time'],
            "start_ts": surge_start_ts,
            "end_ts": surge_end_ts,
            "duration_min": duration_min
        })

    return results

# 모든 급등 라벨 생성
print("="*60)
print("급등 라벨 데이터 생성")
print("="*60)

data_dir = project_root / "onset_detection/data/raw"
all_labels = []

for file_key, surges in surge_labels.items():
    results = calculate_surge_timestamps(file_key, surges, data_dir)
    if results:
        all_labels.extend(results)
        print(f"[OK] {file_key}: {len(results)}개 급등")

print(f"\n총 {len(all_labels)}개 급등 라벨 생성")

# 강도별 통계
strength_counts = {}
for label in all_labels:
    strength = label['strength']
    strength_counts[strength] = strength_counts.get(strength, 0) + 1

print(f"\n강도별 분포:")
for strength in ["강한", "중간", "약한"]:
    count = strength_counts.get(strength, 0)
    pct = count / len(all_labels) * 100 if all_labels else 0
    print(f"  {strength}: {count}개 ({pct:.1f}%)")

# 저장
output_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_labels, f, indent=2, ensure_ascii=False)

print(f"\n저장: {output_path.relative_to(project_root)}")
