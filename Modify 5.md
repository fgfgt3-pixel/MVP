# Modify\_5.md — 백테스트 및 리포트 확장

> 목적: 룰 기반/하이브리드 Confirm 결과와 학습된 ML 모델을 활용하여 **백테스트 실행 및 결과 리포트**를 확장.
> 주의: 기존 데이터 로딩/이벤트 저장 구조와 충돌하지 않도록 **신규 스크립트 추가 + 최소 수정** 방식으로 작성.

---

## 0) 변경 범위

* 신규: `src/backtest/backtester.py` (백테스트 엔진)
* 신규: `src/backtest/report.py` (리포트 생성기)
* 신규: `scripts/backtest_run.py` (실행 스크립트)
* 수정: `config/onset_default.yaml` (백테스트 관련 옵션 추가)
* 테스트: `tests/test_backtester.py`, `tests/test_report.py`

---

## 1) Config 확장

`config/onset_default.yaml`에 아래 블록 추가:

```yaml
backtest:
  start_date: "2025-09-01"
  end_date: "2025-09-30"
  use_hybrid_confirm: true   # 하이브리드 Confirm 결과 사용 여부
  report_dir: reports/       # 리포트 저장 경로
```

**이유**

* 기간(start\_date, end\_date)으로 범위를 지정해야 백테스트 대상 데이터 관리가 용이함
* use\_hybrid\_confirm는 기존 룰 기반 confirm과 하이브리드 confirm 선택을 명시적으로 제어하기 위함
* report\_dir 지정으로 산출물이 한 곳에 모여 관리됨

---

## 2) 백테스트 엔진 (`src/backtest/backtester.py`)

### 기능

* 입력: features 파일, 이벤트(cand/confirm) JSONL, config
* 출력: 백테스트 결과 dict (precision, recall, confirm\_rate 등)

### 로직

1. 기간 필터링: config.start\_date \~ config.end\_date
2. cand/confirm 이벤트 로드 → 라벨과 매칭
3. 평가 지표 계산:

   * 이벤트 단위 precision/recall (onset 단위 평가, row 단위 아님)
   * confirm\_rate
   * TTA (time-to-alert) p50/p95
   * FP/h (시간당 false positive)
4. dict 결과 반환

**이유**

* 이벤트 단위 평가를 해야 실전 매매에서 유의미한 성능 확인 가능
* confirm\_rate, TTA, FP/h는 실제 신호 품질을 정량화하는 핵심 지표

---

## 3) 리포트 생성기 (`src/backtest/report.py`)

### 기능

* 입력: backtester 결과 dict
* 출력: JSON, CSV, PNG 플롯

### 산출물

1. JSON: 모든 지표 기록 (`reports/backtest_summary.json`)
2. CSV: 이벤트 단위 매칭 결과 (cand, confirm, label 여부 등)
3. PNG:

   * confirm\_rate / FP/h / TTA 분포 히스토그램
   * 라벨 vs 예측 이벤트 비교 차트

**이유**

* JSON/CSV → 구조적 분석 가능
* PNG → 사용자 친화적 시각화

---

## 4) 실행 스크립트 (`scripts/backtest_run.py`)

예시 실행 방식:

```bash
python scripts/backtest_run.py \
  --features data/features/023790_44indicators_realtime_20250902_withwin.csv \
  --events data/events/023790_candidates.jsonl \
  --config config/onset_default.yaml
```

출력:

* `reports/backtest_summary.json`
* `reports/backtest_events.csv`
* `reports/backtest_charts.png`

---

## 5) 테스트

### `tests/test_backtester.py`

* 케이스1: cand=10, confirm=5, 라벨=5 → precision=1.0, recall=1.0 확인
* 케이스2: confirm=0 → recall=0, precision=0

### `tests/test_report.py`

* 케이스1: dict 입력 → JSON/CSV/PNG 파일 생성 확인
* 케이스2: report\_dir 지정 → 해당 디렉토리에 산출물 존재 확인

---

## 6) 실행·검증 (필수 단계만)

1. `pytest tests/test_backtester.py`
2. `pytest tests/test_report.py`
3. `python scripts/backtest_run.py --features ... --events ... --config config/onset_default.yaml`

   * `reports/backtest_summary.json` 생성 여부 확인
   * confirm\_rate, precision, recall 값이 출력되는지 확인

---

## 7) 완료 기준

* 백테스트 실행 시 JSON/CSV/PNG 리포트 정상 생성
* 이벤트 단위 precision/recall, confirm\_rate, TTA, FP/h 출력
* 기존 Confirm Detector와 충돌 없음 (플래그로 제어 가능)

---

👉 이 Modify\_5까지 적용하면 **룰 기반 → ML 하이브리드 → 백테스트/리포트 전체 사이클**이 완성됩니다.

