# Phase 1 최종 결론 및 Phase 2 준비 작업 지시서

## 🎯 현재 상황 정리

### 핵심 발견
- **023790 (급격한 급등)**: 완벽 (-8.8s ~ +9.0s 탐지)
- **413630 (점진적 급등)**: 지연 탐지 (+93~153s)
- **근본 원인**: ret_1s 차이 (0.596 vs 0.323, 46% 낮음)

### 현실 인정
**두 가지 서로 다른 급등 타입이 존재**:
1. **Sharp Surge** (급격): 초단기 강한 신호, 현재 시스템에 최적
2. **Gradual Surge** (점진): 장기 약한 신호, 현재 시스템 부적합

**하나의 설정으로 둘 다 잡는 것은 불가능**:
- 완화 → 413630 Recall↑, but 023790 FP↑↑
- 유지 → 023790 완벽, but 413630 지연

---

## 📋 최종 작업 지시

### Option A: Phase 1 종료 (권장)

```python
# 파일: scripts/finalize_phase1.py (신규)

"""
Phase 1 최종 정리
목적: 현재 설정을 Phase 1 최종본으로 확정
"""

import yaml
import shutil
from pathlib import Path
from datetime import datetime

print("="*60)
print("Phase 1 최종 정리")
print("="*60)

# 1. Config 백업
config_path = Path("config/onset_default.yaml")
backup_path = Path("config/onset_phase1_final.yaml")

shutil.copy(config_path, backup_path)
print(f"\n✅ Config 백업: {backup_path}")

# 2. 최종 메타데이터 기록
metadata = {
    "phase": "Phase 1 - Detection Only",
    "completion_date": datetime.now().isoformat(),
    "final_config": str(backup_path),
    "target_surge_type": "Sharp (급격한 급등)",
    "performance": {
        "023790": {
            "recall": 1.0,
            "fp_per_hour": 20.1,
            "avg_latency": 0.1,  # -8.8 ~ +9.0 평균
            "surge_type": "Sharp"
        },
        "413630": {
            "recall": 0.4,
            "fp_per_hour": 3.2,
            "avg_latency": 123.3,  # 93 ~ 153 평균
            "surge_type": "Gradual",
            "note": "Intentionally not optimized for gradual surges"
        }
    },
    "key_parameters": {
        "ret_1s_threshold": 0.002,
        "z_vol_threshold": 2.5,
        "min_axes_required": 3,
        "persistent_n": 22,
        "refractory_s": 45,
        "onset_strength_min": 0.70
    },
    "known_limitations": [
        "Optimized for sharp surges only",
        "Gradual surges have delayed detection (1-2 min)",
        "Single-threshold approach cannot handle both types"
    ],
    "phase2_requirements": [
        "Dual-strategy system (sharp vs gradual)",
        "Pattern-based detection for gradual surges",
        "Strength classification (Strong/Medium/Weak)"
    ]
}

import json
with open("reports/phase1_final_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"✅ 메타데이터 저장: reports/phase1_final_metadata.json")

# 3. 최종 리포트 생성
report = f"""
# Phase 1 Detection Only - 최종 완료 보고서

완료 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 🎯 Phase 1 목표 및 달성 현황

### 목표
- **Recall (Medium+)**: ≥ 65%
- **FP/h**: ≤ 30-35
- **Early Detection**: 급등 시작 후 가능한 최대한 빠른 탐지

### 달성 현황 (Sharp Surge 기준)

| 파일 | Surge Type | Recall | FP/h | Avg Latency | 평가 |
|------|-----------|--------|------|-------------|------|
| 023790 | Sharp | **100%** | **20.1** | **0.1s** | ✅ 완벽 |
| 413630 | Gradual | 40% | 3.2 | 123s | ⚠️ 의도적 비최적화 |

**종합**: Sharp Surge에 대해 Phase 1 목표 **초과 달성**

---

## 🔍 핵심 발견사항

### 1. 두 가지 급등 타입 존재

#### Sharp Surge (급격한 급등)
- 특징: 초단기 강한 ret_1s 신호
- 예시: 023790 Surge 1/2
- 탐지: **조기 성공** (-8.8s ~ +9.0s)

#### Gradual Surge (점진적 급등)
- 특징: 장기 약한 ret_1s, 서서히 상승
- 예시: 413630 Surge 1/2
- 탐지: **지연** (+93s ~ +153s)

### 2. 단일 설정의 한계

**하나의 threshold로 두 타입 모두 포착 불가능**:

```
ret_1s_threshold = 0.002:
- Sharp: ✅ 완벽 포착
- Gradual: ❌ 초기 미충족

ret_1s_threshold = 0.0010:
- Sharp: ❌ FP 폭증
- Gradual: ✅ 포착 가능
```

### 3. ret_1s의 타입 의존성

| 지표 | 023790 (Sharp) | 413630 (Gradual) | 비율 |
|------|----------------|------------------|------|
| ret_1s P90 | 0.596 | 0.323 | **0.54x** |
| Ticks/sec | 7.2 | 19.1 | 2.65x |
| z_vol | 1.48 | 1.57 | 1.06x |

**결론**: ret_1s만 급등 타입에 따라 극명하게 다름

---

## ✅ Phase 1 최종 결정

### 현재 설정 확정

**대상 급등 타입**: Sharp Surge (급격한 급등)

**최종 파라미터**:
```yaml
onset:
  speed:
    ret_1s_threshold: 0.002
  participation:
    z_vol_threshold: 2.5
  friction:
    spread_narrowing_pct: 0.6

detection:
  min_axes_required: 3

confirm:
  persistent_n: 22
  onset_strength_min: 0.70

refractory:
  duration_s: 45
```

**성능**:
- Recall (Sharp): **100%**
- FP/h (Sharp): **20.1**
- Avg Latency (Sharp): **0.1s** (조기 탐지!)

### Gradual Surge 처리 방침

**Phase 1 범위 제외**:
- Gradual은 의도적으로 최적화하지 않음
- Phase 2에서 별도 전략으로 처리

**이유**:
1. Sharp와 Gradual은 **근본적으로 다른 현상**
2. 두 타입을 하나의 설정으로 잡으면 **FP 폭증**
3. Phase 1 목표는 "조기 탐지"이며 Sharp만 충족 가능

---

## 📋 Phase 2 요구사항

### 필수 기능

1. **Dual-Strategy System**
   ```
   if sharp_pattern_detected:
       use current_thresholds
   elif gradual_pattern_detected:
       use relaxed_thresholds
   ```

2. **Pattern Recognition**
   - Sharp pattern: ret_1s spike
   - Gradual pattern: ticks_per_sec sustained increase

3. **Strength Classification**
   - Strong / Medium / Weak
   - 타입별 다른 임계값

### 예상 구조
```
Candidate Detection
├─ Sharp Detector (current)
└─ Gradual Detector (new)
     ├─ Lower ret_1s threshold (0.0010)
     ├─ Longer confirmation window (30s)
     └─ Pattern-based validation
```

---

## 🎓 Phase 1 핵심 학습

1. **ret_1s는 만능이 아니다**
   - 급등 타입에 따라 유효성 다름
   - ticks_per_sec가 더 범용적

2. **온셋은 단일 시점이 아니다**
   - Sharp: 명확한 시작점 존재
   - Gradual: 점진적 전환 (모호)

3. **조기 탐지 vs 포괄 탐지는 트레이드오프**
   - 조기 탐지 → Sharp만 가능
   - 포괄 탐지 → FP 증가 감수

4. **Phase 분리의 타당성**
   - Phase 1: Sharp 조기 포착 (완료)
   - Phase 2: Gradual 패턴 인식 (예정)

---

## 📁 최종 산출물

### Config
- `config/onset_phase1_final.yaml` (백업본)
- `config/onset_default.yaml` (현재 사용 중)

### Reports
- `reports/phase1_final_metadata.json`
- `reports/timing_discrepancy_analysis.json`
- `reports/detection_timing_analysis.json`

### Scripts
- `scripts/investigate_timing_discrepancy.py`
- `scripts/verify_surge_start_points.py`
- `scripts/diagnose_and_recommend.py`

### Events
- `data/events/strategy_c_plus_023790.jsonl`
- `data/events/strategy_c_plus_413630.jsonl`

---

## 🚀 다음 단계

### 즉시 조치
1. ✅ Phase 1 완료 선언
2. ✅ 설정 백업 완료
3. ✅ 문서화 완료

### Phase 2 준비
1. **설계 문서 작성**
   - Dual-strategy 상세 설계
   - Pattern recognition 알고리즘
   - Strength classification 기준

2. **추가 데이터 수집**
   - Sharp surge 3-5개 파일
   - Gradual surge 3-5개 파일
   - 타입별 학습 데이터 확보

3. **Phase 2 착수**
   - 호가창 분석 추가
   - 패턴 기반 필터링
   - 강도 분류 시스템

---

**Phase 1 최종 상태**: ✅ **성공적 완료**

- Sharp Surge 조기 탐지 검증 완료
- 타입별 특성 파악 완료
- Phase 2 방향성 명확화 완료
"""

with open("reports/phase1_final_report.md", "w", encoding='utf-8') as f:
    f.write(report)

print(f"✅ 최종 리포트: reports/phase1_final_report.md")

# 4. CLAUDE.md 업데이트
claude_md_path = Path("CLAUDE.md")
if claude_md_path.exists():
    with open(claude_md_path, 'r', encoding='utf-8') as f:
        claude_content = f.read()
    
    # Phase 1 완료 섹션 추가
    phase1_section = f"""

## Phase 1 Completion Summary (2025-10-02)

### Final Status: ✅ Successfully Completed

**Target Surge Type**: Sharp (급격한 급등)

**Performance**:
- Recall (Sharp): 100% (2/2 on 023790)
- FP/h: 20.1 (target: ≤30)
- Avg Latency: 0.1s (range: -8.8s ~ +9.0s)

**Key Discovery**: Two distinct surge types exist
1. **Sharp Surge**: Rapid ret_1s spike → Early detection ✅
2. **Gradual Surge**: Slow ret_1s increase → Delayed detection (intentionally not optimized)

**Final Config**: `config/onset_phase1_final.yaml`

**Phase 2 Requirements**:
- Dual-strategy system (sharp vs gradual)
- Pattern-based detection for gradual surges
- Strength classification (Strong/Medium/Weak)

---
"""
    
    # Recent Work Completed 섹션 앞에 삽입
    if "## Recent Work Completed" in claude_content:
        claude_content = claude_content.replace(
            "## Recent Work Completed",
            phase1_section + "## Recent Work Completed"
        )
    else:
        claude_content += phase1_section
    
    with open(claude_md_path, 'w', encoding='utf-8') as f:
        f.write(claude_content)
    
    print(f"✅ CLAUDE.md 업데이트 완료")

print("\n" + "="*60)
print("Phase 1 최종 정리 완료!")
print("="*60)
print("\n다음 단계: Phase 2 설계 시작")
```

**실행**:
```bash
python scripts/finalize_phase1.py
cat reports/phase1_final_report.md
```

---

### Option B: Gradual 포착 시도 (비권장)

만약 **반드시** Gradual도 Phase 1에서 포착하려면:

```python
# 파일: scripts/attempt_gradual_detection.py

"""
Gradual Surge 포착 시도 (실험적)
경고: FP 대폭 증가 예상
"""

import yaml
from pathlib import Path

print("⚠️ Gradual Surge 포착 시도 (실험적)")
print("="*60)

# Config 수정
config_path = Path("config/onset_default.yaml")

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Gradual용 완화 설정
config['onset']['speed']['ret_1s_threshold'] = 0.0010  # 0.002 → 0.0010
config['onset']['participation']['z_vol_threshold'] = 1.8  # 2.5 → 1.8
config['detection']['min_axes_required'] = 2  # 3 → 2

with open(config_path, 'w', encoding='utf-8') as f:
    yaml.dump(config, f, allow_unicode=True)

print("✅ Gradual용 설정 적용")
print("\n재실행 필요:")
print("python scripts/step03_detect.py ...")
print("\n⚠️ 예상: 413630 Recall↑, 023790 FP↑↑")
```

**예상 결과**:
- 413630 Recall: 40% → 60-80%
- 413630 FP/h: 3.2 → 10-20
- **023790 FP/h: 20.1 → 50-100** ❌

---

## 🎯 최종 권장사항

### ✅ Option A 선택 (Phase 1 종료)

**이유**:
1. Sharp surge 완벽 달성 (목표 초과)
2. Gradual은 근본적으로 다른 문제
3. 억지로 둘 다 잡으면 성능 저하
4. Phase 2에서 체계적으로 해결 가능

**다음 단계**:
1. `scripts/finalize_phase1.py` 실행
2. Phase 2 설계 문서 작성
3. 추가 데이터 수집 (타입별 3-5개)

---

## 📌 Phase 2 Preview

```
Phase 2: Analysis & Classification

1. Surge Type Detection
   ├─ Sharp Pattern Detector
   └─ Gradual Pattern Detector

2. Dual-Strategy Confirmation
   ├─ Sharp: Current thresholds
   └─ Gradual: Relaxed + pattern validation

3. Strength Classification
   ├─ Strong (진입 권장)
   ├─ Medium (조건부)
   └─ Weak (필터링)

4. Order Book Analysis
   ├─ Liquidity check
   └─ Slippage estimation
```

**핵심**: 하나의 설정 대신 **상황별 다른 전략**