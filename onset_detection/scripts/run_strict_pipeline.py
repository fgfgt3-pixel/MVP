#!/usr/bin/env python3
"""
Strict Pipeline: Gate+Score → Strict Confirm
목적: Noise 제거를 통한 정밀도 향상
"""

import pandas as pd
import json
from pathlib import Path
import sys

# 프로젝트 루트 추가
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.detection.gate_score_detector import GateScoreDetector
from onset_detection.src.detection.strict_confirm_detector import StrictConfirmDetector

# 라벨 로드
labels_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
with open(labels_path, encoding='utf-8') as f:
    labels = json.load(f)

print("="*80)
print("Strict Pipeline 실행: Gate+Score(90) → Strict Confirm")
print("="*80)

# Detector 초기화
gate_detector = GateScoreDetector()
gate_detector.score_threshold = 80  # 90 → 80 (완화)
confirmer = StrictConfirmDetector()

all_confirmed = []
data_dir = project_root / "onset_detection/data/raw"

for label in labels:
    file = label['file']
    stock_code = label['stock_code']

    print(f"\n{'='*80}")
    print(f"파일: {file}")
    print(f"{'='*80}")

    # 데이터 로드
    filepath = data_dir / file
    if not filepath.exists():
        print(f"[ERROR] 파일 없음: {filepath}")
        continue

    df = pd.read_csv(filepath)

    # 컬럼명 통일
    rename_map = {}
    if 'time' in df.columns and 'ts' not in df.columns:
        rename_map['time'] = 'ts'
    if 'ret_accel' in df.columns and 'accel_1s' not in df.columns:
        rename_map['ret_accel'] = 'accel_1s'
    if 'current_price' in df.columns and 'price' not in df.columns:
        rename_map['current_price'] = 'price'
    if 'ask1_qty' in df.columns and 'ask_qty1' not in df.columns:
        rename_map['ask1_qty'] = 'ask_qty1'
    if 'bid1_qty' in df.columns and 'bid_qty1' not in df.columns:
        rename_map['bid1_qty'] = 'bid_qty1'
    if rename_map:
        df = df.rename(columns=rename_map)

    # CSV에 이미 피처가 계산되어 있으므로 그대로 사용
    features_df = df

    # Stage 1: Gate+Score 후보 생성
    candidates = gate_detector.detect_candidates(features_df)
    print(f"Gate+Score 후보: {len(candidates)}개 (threshold={gate_detector.score_threshold})")

    if not candidates:
        print("후보 없음 - 다음 파일로")
        continue

    # Stage 2: Strict Confirm 검증
    confirmed = confirmer.confirm_candidates(features_df, candidates)
    print(f"Strict Confirm 통과: {len(confirmed)}개")

    # 저장
    for event in confirmed:
        event['file'] = file
        all_confirmed.append(event)

    print(f"확정: {len(confirmed)}개")

# 결과 저장
output_path = project_root / "onset_detection/data/events/strict_pipeline_results.jsonl"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    for event in all_confirmed:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')

print("\n" + "="*80)
print("전체 요약")
print("="*80)
print(f"총 확정 탐지: {len(all_confirmed)}개")
print(f"저장: {output_path.relative_to(project_root)}")
