# Modify\_4.md — 온라인 추론 및 하이브리드 Confirm 결합

> 목적: 학습된 ML 모델(`onset_strength`)을 실시간 파이프라인에 결합하여, 기존 룰 기반 Confirm Detector와 **하이브리드 방식**으로 동작하도록 확장.
> 주의: 기존 Confirm Detector·학습 모듈과 충돌하지 않도록 **새 모듈 추가 및 최소 수정**으로만 구현.

---

## 0) 변경 범위

* 신규: `src/online/score_onset.py` (실시간 추론)
* 신규: `src/detection/confirm_hybrid.py` (하이브리드 Confirm Detector)
* 수정: `config/onset_default.yaml` (ML 관련 옵션 추가)
* 테스트: `tests/test_confirm_hybrid.py`

---

## 1) Config 확장

`config/onset_default.yaml`에 아래 블록 추가:

```yaml
ml:
  model_path: models/lgbm.pkl     # 학습된 모델 경로
  threshold: 0.6                  # onset_strength ≥ threshold → 유효
  use_hybrid_confirm: true        # true → confirm_hybrid 사용
```

**이유**

* 모델 파일 경로 지정 필요
* threshold는 onset\_strength 기반 필터를 추가할지 결정하는 핵심
* use\_hybrid\_confirm 플래그로 기존 confirm\_detector와의 충돌 방지

---

## 2) 온라인 추론 모듈 (`src/online/score_onset.py`)

### 기능

* 입력: features DataFrame (윈도우 피처 포함)
* 출력: onset\_strength (0\~1) 컬럼 추가

### 로직

1. 모델 로드: `model = model_store.load_model(cfg.ml.model_path)`
2. features drop: config에 정의된 drop\_columns 사용
3. `onset_strength = model.predict_proba(X)[:,1]`
4. DataFrame에 `onset_strength` 컬럼 추가 후 반환

**이유**

* 예측 확률 기반으로 onset 강도를 수치화
* 기존 DataFrame 확장 방식으로 호환성 유지

---

## 3) 하이브리드 Confirm Detector (`src/detection/confirm_hybrid.py`)

### 기능

* 룰 기반 Confirm Detector 결과에 ML onset\_strength 조건 추가

### 로직

1. cand 이벤트 시점 이후 window\_s 내 features+onset\_strength 확보
2. 기존 룰 기반 축 판정 결과(hit 여부) 확인
3. onset\_strength ≥ cfg.ml.threshold 조건 추가
4. 최종 조건:

   * 가격 축 충족 (필수)
   * min\_axes 이상 충족
   * onset\_strength ≥ threshold

### 출력 이벤트 필드

* 기존 confirm 이벤트 구조 동일
* `onset_strength` 필드 추가
* `hybrid_used: true` 플래그 기록

**이유**

* 하위 호환성 유지: 기존 confirm 이벤트 처리 로직 그대로 동작
* 추가 필드로만 ML 확률을 노출

---

## 4) 테스트 (`tests/test_confirm_hybrid.py`)

* 케이스1: 룰 충족 + onset\_strength ≥ threshold → 확정 이벤트 생성
* 케이스2: 룰 충족 + onset\_strength < threshold → 미확정
* 케이스3: 가격 축 미충족 → onset\_strength 높아도 미확정
* 케이스4: use\_hybrid\_confirm=false → 기존 confirm\_detector와 동일 결과

---

## 5) 실행·검증 (필수 단계만)

1. 모델 학습/저장 완료된 상태에서 실행:

   ```bash
   python scripts/confirm_test.py \
     --features data/features/sample_withwin.csv \
     --cands data/events/sample_candidates.jsonl \
     --config config/onset_default.yaml
   ```
2. 결과 이벤트 JSONL에서:

   * `onset_strength` 필드 존재 여부 확인
   * confirm 수가 threshold 조정에 따라 변동하는지 확인

---

## 6) 완료 기준

* onset\_strength 컬럼 정상 생성 (`0~1` 확률값)
* 하이브리드 Confirm 실행 시 threshold 값에 따라 confirm 수 변화 확인
* 기존 confirm\_detector와 충돌 없음 (플래그로 제어 가능)

---

👉 이 Modify\_4까지 적용하면 **실시간 추론 + 하이브리드 Confirm 구조**가 완성됩니다.
