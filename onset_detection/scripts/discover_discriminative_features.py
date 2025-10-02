#!/usr/bin/env python3
"""
목적: 탐지 vs 미탐지 급등 간 지표 차이 정량 분석
출력: 각 지표의 변별력 점수
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from scipy import stats

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent.parent

# 분석 결과 로드
analysis_path = project_root / "onset_detection/reports/surge_window_analysis.json"
with open(analysis_path, encoding='utf-8') as f:
    analysis = json.load(f)

detected = [r for r in analysis if r['detected']]
missed = [r for r in analysis if not r['detected']]

print("="*80)
print("지표별 변별력 분석")
print("="*80)

indicators = [
    'ret_1s',
    'z_vol_1s',
    'ticks_per_sec',
    'microprice_slope',
    'spread'
]

discriminative_scores = {}

for indicator in indicators:
    # 통계값 추출 (p90 우선, 없으면 mean 사용)
    detected_values = []
    for r in detected:
        stat = r['stats'][indicator]
        if 'p90' in stat:
            detected_values.append(stat['p90'])
        elif 'mean' in stat:
            detected_values.append(stat['mean'])
        else:
            detected_values.append(0)

    missed_values = []
    for r in missed:
        stat = r['stats'][indicator]
        if 'p90' in stat:
            missed_values.append(stat['p90'])
        elif 'mean' in stat:
            missed_values.append(stat['mean'])
        else:
            missed_values.append(0)

    # 통계 검정
    t_stat, p_value = stats.ttest_ind(detected_values, missed_values)

    # Effect Size (Cohen's d)
    mean_detected = np.mean(detected_values)
    mean_missed = np.mean(missed_values)
    std_pooled = np.sqrt(
        (np.var(detected_values) + np.var(missed_values)) / 2
    )
    cohens_d = abs(mean_detected - mean_missed) / std_pooled if std_pooled > 0 else 0

    # 변별력 점수 (0-100)
    # Effect size 기반: d >= 0.8 (large) = 100점
    discriminative_score = min(100, cohens_d * 125)

    discriminative_scores[indicator] = {
        'mean_detected': float(mean_detected),
        'mean_missed': float(mean_missed),
        'difference': float(mean_detected - mean_missed),
        'cohens_d': float(cohens_d),
        'p_value': float(p_value),
        'discriminative_score': float(discriminative_score)
    }

    print(f"\n{indicator}:")
    print(f"  탐지됨: {mean_detected:.4f}")
    print(f"  미탐지: {mean_missed:.4f}")
    print(f"  차이: {mean_detected - mean_missed:+.4f}")
    print(f"  Effect Size (d): {cohens_d:.3f}")
    print(f"  p-value: {p_value:.4f}")
    print(f"  변별력 점수: {discriminative_score:.1f}/100")

# 정렬
sorted_indicators = sorted(
    discriminative_scores.items(),
    key=lambda x: x[1]['discriminative_score'],
    reverse=True
)

print("\n" + "="*80)
print("변별력 순위")
print("="*80)

for i, (indicator, score) in enumerate(sorted_indicators, 1):
    print(f"{i}. {indicator}: {score['discriminative_score']:.1f}점 (d={score['cohens_d']:.3f})")

# 권장 가중치 계산
print("\n" + "="*80)
print("권장 가중치")
print("="*80)

# 정규화 (합=100)
total_score = sum([s[1]['discriminative_score'] for s in sorted_indicators if s[1]['discriminative_score'] > 0])

print("\n1단계: 데이터 기반 가중치")
for indicator, score in sorted_indicators:
    if total_score > 0:
        weight = (score['discriminative_score'] / total_score) * 100
        print(f"  {indicator}: {weight:.1f}%")
    else:
        print(f"  {indicator}: 0.0%")

# 실용적 조정
print("\n2단계: 실용적 조정 (Primary/Secondary 구분)")

# Top 2 지표 식별
if len(sorted_indicators) >= 2:
    top1 = sorted_indicators[0][0]
    top2 = sorted_indicators[1][0]
    top3 = sorted_indicators[2][0] if len(sorted_indicators) >= 3 else None
    top4 = sorted_indicators[3][0] if len(sorted_indicators) >= 4 else None

    print(f"""
Gate (필수):
  ret_1s > 0.0005  # 최소 상승

Primary (고배점):
  - {top1}: 50점
  - {top2}: 40점

Secondary (중배점):
  - {top3}: 20점
  - {top4}: 15점

Tertiary (저배점):
  - 기타: 10점

Threshold:
  - 70점 이상: Candidate
""")

# 저장
output_path = project_root / "onset_detection/reports/discriminative_analysis.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding='utf-8') as f:
    json.dump({
        'indicators': discriminative_scores,
        'ranking': [
            {'indicator': ind, 'score': score['discriminative_score']}
            for ind, score in sorted_indicators
        ],
        'recommended_weights': {
            sorted_indicators[i][0]: [50, 40, 20, 15, 10][i] if i < 5 else 5
            for i in range(min(5, len(sorted_indicators)))
        }
    }, f, indent=2, ensure_ascii=False)

print(f"\n저장: {output_path.relative_to(project_root)}")

# 핵심 발견사항
print("\n" + "="*80)
print("핵심 발견사항")
print("="*80)

print(f"""
1. 가장 변별력 있는 지표: {sorted_indicators[0][0]}
   - Effect Size: {sorted_indicators[0][1]['cohens_d']:.3f}
   - 탐지됨 vs 미탐지: {sorted_indicators[0][1]['mean_detected']:.4f} vs {sorted_indicators[0][1]['mean_missed']:.4f}

2. 변별력 순위:
""")

for i, (ind, score) in enumerate(sorted_indicators[:5], 1):
    print(f"   {i}. {ind}: {score['discriminative_score']:.1f}점")

if sorted_indicators[0][1]['discriminative_score'] < 20:
    print("""
[경고] 모든 지표의 변별력이 낮습니다 (Cohen's d < 0.2)
→ 탐지된 급등과 미탐지 급등의 특성이 매우 유사함
→ Threshold 조정이 아닌 다른 접근 필요 (예: 시간 윈도우, 패턴 인식)
""")
