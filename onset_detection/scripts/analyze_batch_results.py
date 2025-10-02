#!/usr/bin/env python3
"""
배치 결과 분석 및 Threshold 최적화 권장
"""

import json
import numpy as np
from pathlib import Path

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent

# 결과 로드
recall_path = project_root / "onset_detection/reports/batch_recall_results.json"
detection_path = project_root / "onset_detection/reports/batch_detection_summary.json"

with open(recall_path, encoding='utf-8') as f:
    recall_results = json.load(f)

with open(detection_path, encoding='utf-8') as f:
    detection_summary = json.load(f)

print("="*60)
print("Phase 1.5 대규모 검증 결과 분석")
print("="*60)

# 1. 전체 성능 요약
summary = recall_results['summary']
det_summary = detection_summary['summary']

print("\n[전체 성능]")
print(f"  총 급등: {summary['total_surges']}개")
print(f"  탐지 급등: {summary['detected_surges']}개")
print(f"  Recall: {summary['total_recall']*100:.1f}%")
print(f"  평균 FP/h: {det_summary['avg_fp_per_hour']:.1f}")
print(f"  평균 Latency: {summary['latency_stats']['mean']:.1f}s")

# 2. 강도별 분석
print("\n[강도별 Recall]")
for strength in ["강한", "중간", "약한"]:
    recall = summary['recall_by_strength'].get(strength, 0)
    print(f"  {strength}: {recall*100:.1f}%")

# 3. 목표 달성 여부
print("\n[목표 평가]")
target_recall = 0.60
target_fp = 40

if summary['total_recall'] >= target_recall:
    print(f"  Recall: [OK] {summary['total_recall']*100:.1f}% >= 60%")
else:
    gap = target_recall - summary['total_recall']
    needed = int(np.ceil(gap * summary['total_surges']))
    print(f"  Recall: [MISS] {summary['total_recall']*100:.1f}% < 60%")
    print(f"          {needed}개 더 필요 (현재 {summary['detected_surges']}/{summary['total_surges']})")

if det_summary['avg_fp_per_hour'] <= target_fp:
    print(f"  FP/h: [OK] {det_summary['avg_fp_per_hour']:.1f} <= 40")
else:
    print(f"  FP/h: [MISS] {det_summary['avg_fp_per_hour']:.1f} > 40")

# 4. 놓친 급등 분석
missed = [r for r in recall_results['detection_results'] if not r['detected']]
detected = [r for r in recall_results['detection_results'] if r['detected']]

print(f"\n[놓친 급등 분석] (총 {len(missed)}개)")

missed_by_strength = {}
for m in missed:
    strength = m['strength']
    if strength not in missed_by_strength:
        missed_by_strength[strength] = []
    missed_by_strength[strength].append(m)

for strength in ["강한", "중간", "약한"]:
    items = missed_by_strength.get(strength, [])
    if items:
        print(f"\n  {strength} ({len(items)}개):")
        for item in items[:5]:  # 최대 5개만
            print(f"    - {item['file']} {item['surge_name']}")

# 5. 파일별 성능 분포
print(f"\n[파일별 FP/h 분포]")
fp_rates = [f['fp_per_hour'] for f in detection_summary['files']]
print(f"  Min: {np.min(fp_rates):.1f}")
print(f"  Median: {np.median(fp_rates):.1f}")
print(f"  Mean: {np.mean(fp_rates):.1f}")
print(f"  Max: {np.max(fp_rates):.1f}")
print(f"  Std: {np.std(fp_rates):.1f}")

high_fp_files = [f for f in detection_summary['files'] if f['fp_per_hour'] > 10]
if high_fp_files:
    print(f"\n  FP/h > 10인 파일 ({len(high_fp_files)}개):")
    for f in sorted(high_fp_files, key=lambda x: x['fp_per_hour'], reverse=True):
        print(f"    - {f['file']}: {f['fp_per_hour']:.1f}")

# 6. 최적화 권장사항
print("\n" + "="*60)
print("최적화 권장사항")
print("="*60)

current_recall = summary['total_recall']
current_fp = det_summary['avg_fp_per_hour']

if current_recall >= 0.60:
    print("\n[OK] Recall 목표 달성! 추가 조정 불필요")
    print("\n현재 설정 유지:")
    print("""
  onset:
    speed:
      ret_1s_threshold: 0.002
    participation:
      z_vol_threshold: 2.5
    friction:
      spread_narrowing_pct: 0.6

  confirm:
    persistent_n: 22
    onset_strength_min: 0.67

  refractory:
    duration_s: 45
""")

elif current_recall >= 0.50:
    print(f"\n[WARNING] 목표에 근접 ({current_recall*100:.1f}%)")
    print("\n미세 조정 권장:")
    print("""
Option 1: onset_strength 완화 (추천)
  confirm:
    onset_strength_min: 0.50  # 0.67 → 0.50 (1/2 축 허용)

  예상 효과: Recall +10-15%, FP/h +3-5

Option 2: Candidate 임계 미세 완화
  onset:
    speed:
      ret_1s_threshold: 0.0018  # 0.002 → 0.0018 (10% 완화)
    participation:
      z_vol_threshold: 2.3      # 2.5 → 2.3 (약간 완화)

  예상 효과: Recall +5-10%, FP/h +5-10
""")

else:
    print(f"\n[ERROR] 큰 격차 ({current_recall*100:.1f}%)")
    print("\n대폭 완화 필요:")
    print("""
Option 1: onset_strength 제거 (가장 효과적)
  confirm:
    onset_strength_min: 0.33  # 0.67 → 0.33 (1/3 축만 충족)

  예상 효과: Recall +20-25%, FP/h +10-15

Option 2: Candidate + Confirm 동시 완화
  onset:
    speed:
      ret_1s_threshold: 0.0015  # 0.002 → 0.0015 (25% 완화)
    participation:
      z_vol_threshold: 2.0      # 2.5 → 2.0 (대폭 완화)

  confirm:
    persistent_n: 18            # 22 → 18
    onset_strength_min: 0.50    # 0.67 → 0.50

  예상 효과: Recall +25-30%, FP/h +15-25
""")

# 7. 핵심 발견사항
print("\n" + "="*60)
print("핵심 발견사항")
print("="*60)

print(f"""
1. 현재 설정 (Strategy C+)은 Sharp 급등에 최적화됨
   - 강한 급등: 75% Recall [OK]
   - 중간 급등: 57% Recall (목표 미달)
   - 약한 급등: 22% Recall (의도적 필터)

2. onset_strength >= 0.67 필터가 너무 강함
   - 약한/중간 급등의 상당수가 2/3 축만 충족
   - 0.67 → 0.50 완화로 중간 급등 Recall 대폭 향상 예상

3. Latency 분포가 매우 넓음 (7.6s ~ 245.6s)
   - Sharp 급등: 7-20s (빠름)
   - Gradual 급등: 90-250s (느림)
   - Phase 1.5에서는 단일 전략 한계 명확

4. FP/h는 목표 대비 매우 낮음 (3.7 vs 40 목표)
   - Threshold 완화 여지가 충분함
   - Recall 향상을 위해 적극 활용 가능

5. 파일별 편차가 큼
   - 023790_0901: FP/h 20.1 (Sharp, 높음)
   - 097230_0902/0903: FP/h 0.1-0.2 (Gradual, 낮음)
   - 종목/날짜별 특성 차이 존재
""")

# 8. 다음 단계 제안
print("\n" + "="*60)
print("다음 단계 제안")
print("="*60)

if current_recall >= 0.60:
    print("""
1. [OK] Phase 1.5 목표 달성
2. Phase 2로 진행:
   - Dual-Strategy 시스템 설계
   - Sharp/Gradual 분류기 개발
   - 적응형 Threshold 구현
""")
else:
    print(f"""
1. onset_strength 완화 테스트 (권장)
   - 0.67 → 0.50 또는 0.33
   - 예상 Recall: {current_recall*100:.1f}% → 55-60%

2. 완화 후 재검증
   - python scripts/batch_detection.py
   - python scripts/calculate_batch_recall.py

3. Recall 60% 달성 시 Phase 1.5 완료
   - 설정 백업
   - Phase 2 설계 착수
""")

print("\n" + "="*60)
print("분석 완료")
print("="*60)
