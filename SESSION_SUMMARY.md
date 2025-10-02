# Phase 1+ 작업 요약 (2025-10-02)

## 현재 상황

### 문제 정의
- Phase 1 Strategy C+ (Recall 75%, FP/h 20.1)을 12개 파일로 확장 → Recall 45% 급락
- 급등 타입이 2가지 (Sharp vs Gradual)로 나뉨 → 단일 threshold로 불가능

### 시도한 접근법들

#### 1. Gate+Score System (Modify 3)
- **방법**: Cohen's d 기반 discriminative features 가중 점수
- **결과**: Recall 95%, FP/h 367.6
- **문제**: Noise 81.9%, Score만으로 Signal/Noise 구분 불가

#### 2. Strict Confirm Detector (Modify 4)
- **방법**: Delta+Persistent+Peak 3단계 검증
- **결과**: Recall 35%, Noise 83.5%
- **문제**: 너무 엄격해서 Recall 급락

#### 3. Dual-Pathway Detection (Modify 5) ⭐
- **방법**: Sharp/Gradual 급등을 별도 경로로 탐지
  - Sharp: ret_1s 중심 (가중치 60)
  - Gradual: ticks_per_sec 중심 (가중치 50)
- **결과**: Recall 90% (18/20) ✅
- **문제**: FP/h 208.7, **27,279개 중복 탐지** (온셋 개념 위반)

#### 4. State Machine Refractory (Modify 1 재작업) ⭐
- **방법**: 급등 생애주기 State Machine (IDLE→ONSET→PEAK→DECAY→IDLE)
- **결과**: 탐지 156개 (99.4% 감소), FP/h 1.9 ✅
- **문제**: Recall 40% ❌ (Gradual threshold 85로 상향 + 보수적 State Machine)

## 핵심 발견

1. **Dual-Pathway 필수**: Sharp와 Gradual은 완전히 다른 특성
2. **Refractory 필수**: State Machine 없이는 중복 탐지 불가피
3. **Trade-off 존재**: Recall ↑ → Noise/중복 ↑, Noise ↓ → Recall ↓

## 다음 단계 제안

### Option A: State Machine + Dual-Pathway 통합
```python
# State Machine 내부에서 Dual-Pathway 사용
# Gradual threshold 75로 복원 (85는 너무 높음)
# State Machine 파라미터 완화 (peak_detect_window, decay_threshold)
```

### Option B: 파일별 State Machine
```python
# 현재: 종목별 State Machine → 같은 파일 내 다른 급등 놓침
# 개선: (종목, 파일) 튜플로 State 관리
```

### Option C: Hybrid Refractory
```python
# State Machine + 시간 기반 Refractory 병행
# ONSET 등록 후 60초간 차단 (간단하지만 효과적)
```

## 주요 파일 위치

### 탐지 로직
- `onset_detection/src/detection/gate_score_detector.py`
- `onset_detection/src/detection/strict_confirm_detector.py`
- `onset_detection/src/detection/state_machine_refractory.py`

### 실행 스크립트
- `onset_detection/scripts/implement_dual_pathway.py`
- `onset_detection/scripts/validate_state_machine.py`

### 결과 파일
- `onset_detection/data/events/dual_pathway_confirmed.jsonl` (27,279개)
- `onset_detection/data/events/state_machine_confirmed.jsonl` (156개)
- `onset_detection/reports/dual_pathway_validation.json`
- `onset_detection/reports/state_machine_validation.json`

### 라벨 데이터
- `onset_detection/data/labels/all_surge_labels.json` (20개 급등, 12개 파일)

## 성능 비교표

| 방법 | 탐지 수 | Recall | FP/h | Noise | 문제점 |
|------|---------|--------|------|-------|--------|
| Gate+Score | 28,807 | 95% | 367.6 | 81.9% | 중복 과다, Noise 높음 |
| Strict Confirm | 249 | 35% | 2.8 | 83.5% | Recall 너무 낮음 |
| Dual-Pathway | 27,279 | 90% | 208.7 | 57.1% | 중복 과다 |
| State Machine | 156 | 40% | 1.9 | 93.6% | Recall 낮음, Gradual 놓침 |
| **목표** | **20-40** | **>70%** | **<15** | **<30%** | - |

## 데이터 특성

### 급등 타입별 특징
- **Sharp (4개)**: ret_1s P90=0.596, 빠른 가격 상승
- **Gradual (16개)**: ret_1s P90=0.323, 틱밀도 높음, 가격은 완만

### 병목 지표
- **spread**: 가장 큰 병목 (3.9% fulfillment), Cohen's d=0.972 (최고 discriminative power)
- **3-axis fulfillment**: 0.1-0.5% (너무 낮음)

## Modify 파일 내용

- **Modify 1.md**: State Machine Refractory (급등 생애주기 추적)
- **Modify 2.md**: Data-driven Analysis (급등 윈도우 실제 값 분석)
- **Modify 3.md**: Gate+Score System (discriminative features)
- **Modify 4.md**: Noise Pattern Analysis & Strict Confirm
- **Modify 5.md**: Dual-Pathway Detection (Sharp vs Gradual)
