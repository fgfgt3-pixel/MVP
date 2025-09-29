# Modify\_6.md — 실전 매매 시뮬레이션 / 실시간 실행 플로우

> 목적: 학습된 모델(`onset_strength`)과 하이브리드 Confirm Detector를 활용하여 **실전 매매 시뮬레이션** 및 **실시간 실행 플로우**를 확장.
> 주의: 기존 Confirm / 백테스트 파이프라인과 충돌하지 않도록 **신규 모듈 + 최소 수정** 방식으로 작성.

---

## 0) 변경 범위

* 신규: `src/trading/simulator.py` (매매 시뮬레이션 엔진)
* 신규: `src/trading/live_runner.py` (실시간 실행 플로우)
* 신규: `scripts/run_simulation.py` (시뮬레이션 실행 스크립트)
* 신규: `scripts/run_live.py` (실시간 실행 스크립트)
* 수정: `config/onset_default.yaml` (실전 매매 관련 옵션 추가)
* 테스트: `tests/test_simulator.py`, `tests/test_live_runner.py`

---

## 1) Config 확장

`config/onset_default.yaml`에 아래 블록 추가:

```yaml
trading:
  simulator:
    capital: 10000000         # 초기 자본 (KRW)
    fee_rate: 0.0005          # 수수료 (왕복)
    slippage: 0.0002          # 슬리피지 가정
    hold_time_s: 60           # 보유 시간 (초)
    stop_loss_pct: 0.01       # 손절 기준 (1%)
    take_profit_pct: 0.02     # 익절 기준 (2%)
  live:
    api: kiwoom               # 실시간 API 종류 (kiwoom, dummy)
    account_no: "1234567890"  # 모의 계좌 번호
    risk_limit_pct: 0.05      # 계좌 자본 대비 1회 거래 최대 비중
```

**이유**

* 시뮬레이터: 현실적인 거래 비용·제한 조건을 반영해야 결과가 왜곡되지 않음
* 실시간: 어떤 API를 쓸지, 계좌와 리스크 한도를 명시적으로 관리해야 안전성 확보

---

## 2) 매매 시뮬레이션 (`src/trading/simulator.py`)

### 기능

* cand/confirm 이벤트 기반 매수 → hold\_time\_s 후 매도
* stop\_loss / take\_profit 조건 충족 시 조기 청산
* PnL(손익), MDD(최대낙폭), 승률 등 지표 계산

### 출력

* 시뮬레이션 결과 DataFrame (trade\_id, entry\_ts, exit\_ts, entry\_price, exit\_price, pnl, reason)
* 집계 리포트(dict): 총 수익률, 승률, Sharpe, MDD

---

## 3) 실시간 실행 플로우 (`src/trading/live_runner.py`)

### 기능

* 실시간 features 수신 → onset\_strength 예측 → confirm\_hybrid 판정
* 조건 충족 시 가상 주문(또는 API 주문) 실행
* 리스크 관리: position size = account\_capital \* risk\_limit\_pct
* 거래 로그를 `reports/live_trades.jsonl`에 기록

### 출력

* trade 이벤트 JSONL (entry/exit, pnl, reason, onset\_strength 기록)

**이유**

* 백테스트와 동일한 로직을 그대로 사용 → 신뢰성 확보
* API 모듈은 추후 교체 가능 (초기에는 dummy 실행으로 검증)

---

## 4) 실행 스크립트

### 시뮬레이션 실행

```bash
python scripts/run_simulation.py \
  --features data/features/023790_44indicators_realtime_20250902_withwin.csv \
  --events data/events/023790_confirmed.jsonl \
  --config config/onset_default.yaml
```

출력:

* `reports/simulation_trades.csv`
* `reports/simulation_summary.json`

### 실시간 실행

```bash
python scripts/run_live.py --config config/onset_default.yaml
```

출력:

* `reports/live_trades.jsonl` (실시간 업데이트)

---

## 5) 테스트

### `tests/test_simulator.py`

* 케이스1: 단순 상승 시뮬레이션 → pnl>0 확인
* 케이스2: stop\_loss 조건 충족 → exit\_reason="stop\_loss"

### `tests/test_live_runner.py`

* 케이스1: dummy API 사용 → 가상 주문 실행 기록 생성
* 케이스2: risk\_limit\_pct=0.05 초과 주문 → 차단되는지 확인

---

## 6) 실행·검증 (필수 단계만)

1. `pytest tests/test_simulator.py`
2. `pytest tests/test_live_runner.py`
3. `python scripts/run_simulation.py --features ... --events ... --config config/onset_default.yaml`

   * `simulation_trades.csv` 생성 여부 확인
   * summary.json에 총 수익률/승률/Sharpe 기록 확인

---

## 7) 완료 기준

* 시뮬레이터 실행 시 거래 단위별 pnl 계산 및 summary 출력
* 실시간 실행 시 조건 충족 시 trade 이벤트 JSONL 기록
* 기존 Confirm Detector 및 백테스트 파이프라인과 충돌 없음

---

👉 이 Modify\_6 적용 시, **데이터 → 학습 → 하이브리드 탐지 → 백테스트 → 시뮬레이션/실시간 실행**의 전체 사이클이 완성됩니다.