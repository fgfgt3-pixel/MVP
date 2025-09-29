# Modify\_3.md — 라벨링 및 ML 학습 파이프라인

> 목적: 온셋을 학습 가능한 형태로 만들기 위해 **라벨링 모듈**과 **학습/추론 파이프라인**을 추가.
> 주의: 기존 Confirm Detector·윈도우 피처 파이프라인과 충돌하지 않도록 **신규 모듈 추가** 방식으로만 작성.

---

## 0) 변경 범위

* 신규: `src/ml/labeler.py` (라벨링 유틸리티)
* 신규: `src/ml/train.py` (학습 엔트리포인트)
* 신규: `src/ml/model_store.py` (모델 저장/로드)
* 신규: `config/ml.yaml` (학습 파라미터)
* 테스트: `tests/test_labeler.py`, `tests/test_train.py`

---

## 1) Config 설계 (`config/ml.yaml`)

```yaml
ml:
  label:
    span_s: 60           # 온셋 시작 ~ +60초까지 양성
    max_span_s: 90       # 상한 (Peak이 길더라도 90초까지만)
    forecast_s: 10       # 앞으로 10초 내 온셋 발생 여부 (보조 라벨)
    pre_buffer_s: 30     # 온셋 전 최소 음성 확보 구간
  train:
    model_type: lightgbm
    n_estimators: 500
    learning_rate: 0.05
    max_depth: -1
    test_size: 0.2
    random_state: 42
  features:
    drop_columns:
      - stock_code
      - ts
      - ts_sec
      - epoch_sec
```

**이유**

* span/forecast 라벨을 동시에 생성 → 조기 탐지 + 안정성 보완
* pre\_buffer\_s: 개장 직후/온셋 직전의 하드 네거티브를 확보하기 위함
* stock\_code, ts 등 모델 입력에 불필요한 열은 drop

---

## 2) 라벨링 모듈 (`src/ml/labeler.py`)

### 기능

* 입력: cand/confirm 이벤트 JSONL + features DataFrame
* 출력: 학습용 DataFrame(X, y\_span, y\_forecast)

### 로직

1. cand/confirm 이벤트에서 **온셋 시작 시점** 확보
2. 각 이벤트에 대해:

   * `span` 라벨: onset\_ts \~ onset\_ts+span\_s (최대 max\_span\_s) 구간 → y\_span=1
   * `forecast` 라벨: onset\_ts-pre\_buffer\_s \~ onset\_ts → 그 시점에서 onset\_ts+forecast\_s 내 급등 발생하면 y\_forecast=1
   * 나머지 → 음성(0)
3. 클래스 불균형 보정: 음성:양성 비율 로그 출력 (후처리는 train.py에서)

---

## 3) 학습 모듈 (`src/ml/train.py`)

### 기능

* 입력: 라벨링된 DataFrame
* 출력: 학습된 모델 + 중요도 리포트

### 로직

1. features drop → `X`, `y_span`, `y_forecast` 분리
2. `train_test_split(test_size=cfg.ml.train.test_size)`
3. 모델 학습: LightGBM (기본, config에서 교체 가능)

   * loss: binary logloss
   * metrics: AUC, F1, precision/recall
4. 중요도 산출: `lgbm.feature_importances_` → CSV/JSON 저장
5. 모델 저장: `src/ml/model_store.py` 사용 (`pickle` 또는 `joblib`)

**이유**

* LightGBM은 피처 중요도 해석 가능 + 시계열/윈도우 피처에도 강함
* 추후 L1 로지스틱으로 간단한 baseline도 가능 (option)

---

## 4) 모델 저장/로드 (`src/ml/model_store.py`)

```python
import joblib, os

def save_model(model, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)

def load_model(path):
    return joblib.load(path)
```

---

## 5) 테스트 설계

### `tests/test_labeler.py`

* 케이스1: cand 이벤트 시점 → span 구간 y\_span=1 확인
* 케이스2: onset 전 구간 → y\_forecast=1 여부 확인
* 케이스3: max\_span\_s 넘어서는 경우 라벨=0

### `tests/test_train.py`

* 케이스1: 소규모 샘플 학습 → 모델 파일 저장 성공 여부
* 케이스2: feature\_importances\_ shape=입력 feature 개수 확인

---

## 6) 실행·검증 (최소 단계만)

1. `pytest tests/test_labeler.py`
2. `pytest tests/test_train.py`
3. `python src/ml/train.py --features data/features/sample_withwin.csv --labels data/events/sample_events.jsonl --out models/lgbm.pkl`

출력 확인:

* 모델 파일 (`models/lgbm.pkl`) 존재
* 중요도 리포트 CSV/JSON 생성
* 학습 로그에 AUC/F1 출력

---

## 7) 완료 기준

* 라벨링 → y\_span, y\_forecast 두 열이 정상 생성
* 학습 → 모델 저장 및 중요도 리포트 출력
* 기존 파이프라인 호출 시 충돌 없음

---

👉 이 Modify\_3 적용 후, 결과를 기반으로 \*\*Modify\_4(온라인 추론·하이브리드 Confirm 결합)\*\*으로 진행 가능합니다.
