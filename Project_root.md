Role: 수석 소프트웨어 아키텍트

아래는 **모듈 수를 최소화**하면서도 Phase별 확장이 쉬운 **루트 폴더 구조 제안**입니다. “작게 시작 → 점진 확장”에 맞춰 핵심 7모듈로 고정했습니다.

---

# 📁 프로젝트 루트 제안 (미니멀 7-모듈)

```
project-root/
├─ README.md
├─ pyproject.toml              # 패키징/의존성(pep621) 권장. (또는 requirements.txt)
├─ requirements.txt            # (선호 시) 간단 의존성 목록
├─ .env.example                # API 키/경로 등 예시
├─ .gitignore
├─ Makefile                    # 자주 쓰는 명령: run, replay, eval, tune 등
├─ config/
│  ├─ onset_default.yaml       # p95, 확인창(10–30s), 불응(90–120s), 가중치 등
│  ├─ profiles.yaml            # morning/lunch/afternoon 프로파일
│  ├─ paths.yaml               # 데이터/리포트 경로
├─ data/
│  ├─ raw/                     # 원본 CSV (1틱)
│  ├─ clean/                   # 정제본
│  ├─ features/                # 피처화 결과(47지표 또는 최소셋)
│  ├─ labels/                  # 사용자/자동 라벨
│  ├─ scores/                  # 온셋 점수/후보/확정
│  └─ events/                  # 알람/의사결정 이벤트 JSONL
├─ reports/
│  ├─ tuning/                  # tuning_summary.json 등
│  ├─ online_parity.json
│  └─ go_nogo_summary.json
├─ logs/
│  └─ app.log
├─ scripts/                    # 단일 파일 실행 진입점(Phase 스텝용)
│  ├─ step01_prep_clean.py     # 정제/검증(Phase0)
│  ├─ step02_features.py       # 최소셋/47지표 피처화
│  ├─ step03_detect.py         # **CPD 게이트 → 후보 → Δ확인 → 불응** 상태기계
│  ├─ step04_execute_guard.py  # 체결성/슬리피지 가드(로그만)
│  ├─ step05_eval_metrics.py   # 탐지/FP/h/TTA/체결성
│  ├─ step06_tune.py           # 임계/윈도우/가중치 스윕 + Stability Selection
│  ├─ step07_replay.py         # CSV 리플레이(온라인 동형성 대비)
│  └─ step08_online_stub.py    # 키움 스트림 스텁(실전 연결 전 인터페이스 합의) **← Post-Overview(Modify 아님)**
├─ src/
│  ├─ __init__.py
│  ├─ main.py                  # CLI 라우터 (replay/detect/eval 등)
│  ├─ config_loader.py         # YAML 로더 + config_hash 주입
│  ├─ io_utils.py              # tz-aware 파서, 누출 방지 컷, 경로/캐시
│  ├─ features_core.py         # **핵심 6–8개** 피처 계산(지연 최소)
│  ├─ features_ext.py          # 확장 47지표(Phase3 튜닝 시 사용)
│  ├─ detect_onset.py          # (후단) 후보 점수, Δ확인(가격축 필수+earliest-hit+연속성), 불응 FSM
│  ├─ execute_guard.py         # 체결성(spread/depth)/슬리피지 상한식
│  ├─ ingestion.py             # CSV 리플레이/키움 스트림 **공용 인터페이스**
│  ├─ metrics_eval.py          # In-window, FP/h, TTA p95, 체결성 통과율
│  └─ schemas.py               # 이벤트/레코드 스키마 (pydantic/dataclass)
│  ├─ detection/
│  │   └─ cpd_gate.py         # CPD 게이트(가격=CUSUM, 거래=Page–Hinkley) 통합
│  └─ cpd/                    # CPD 원자 모듈
│      ├─ online_cusum.py     # OnlineCUSUM(k,h).update(x)->bool
│      └─ page_hinkley.py     # PageHinkley(delta,lambda).update(x)->bool
└─ tests/
   ├─ test_leakage.py          # 임의 절단 재실행 동일성
   ├─ test_onset_fsm.py        # 상태기계 단위 테스트(CPD 게이트 포함)
   └─ test_cpd.py              # CUSUM/Page–Hinkley 단위 테스트
   └─ test_online_parity.py    # 리플레이=온라인 동형성(스텁)
```

---

## 🧩 역할 요약 (모듈 7개 + CPD 서브모듈)

1. `config_loader.py`

* 모든 설정(YAML) 로드, `config_hash` 생성 → 이벤트/리포트에 주입.

2. `io_utils.py`

* tz-aware, 정렬, 정규장 마스크, 임의 절단(누출 방지), I/O 경로 유틸.

3. `features_core.py`

* **최소셋(6–8개)** 즉시 사용: `ret_1s`, `ret_accel`, `z_vol_1s`, `ticks_per_sec`, `inter_trade_time`, `spread`, `spread_narrowing`, `microprice_momentum`.
* 스트리밍 계산 지연 최소화. (47지표는 `features_ext.py`로 분리)

4. `detection/cpd_gate.py` + `cpd/*`

* **앞단 게이트(필수)**: CUSUM(가격축), Page–Hinkley(거래축) 온라인 탐지
* 파라미터: k,h / delta,lambda / min_pre_s, cooldown_s
* 게이트 통과 시에만 후속 단계 진행

5. `detect_onset.py`

* **후단 단계**: 후보(세션 p-임계) → Δ확인(가격축 필수+earliest-hit+`persistent_n`) → 불응(60–180s)

6. `execute_guard.py`

* 체결성: `spread ≤ θ_spread`, `depth ≥ θ_qty`
* 슬리피지 상한: `α*spread + β/(depth)`
* MVP는 **로그만**(enter/skip/defer).

7. `ingestion.py`

* `ReplaySource(csv)` 와 `KiwoomSource(stream)` **동일 인터페이스** 제공.
* 나중에 실전 연동 시 `KiwoomSource`만 교체.

8. `metrics_eval.py`

* In-window 탐지율, FP/hour, **TTA p95**, 체결성 통과율, OOS 간단 체크.

> **주의(Modify 범위 안내)**: 시뮬레이터/실시간/리스크/최적화 등 **신규 기능 코드는 작성하지 않습니다.**
> 필요한 경우 `step08_online_stub.py`는 **인터페이스 합의용 스텁**만 유지하고 구현은 **Project Overview 변경 이후**로 이월합니다.
> **schemas.py**: 공통 이벤트/레코드 스키마(아래 참고)를 정의하여 전 단계 출력이 호환되도록 합니다.

---

## 🗂 이벤트/레코드 스키마 (JSONL 예시)

```json
{
  "ts": "2025-09-01T09:55:10.250+09:00",
  "stock": "023790",
  "type": "onset_candidate|onset_confirm|refractory_enter",
  "S_t": 3.21,
  "evidence": {"ret_window": 0.007, "z_vol_1m": 2.4, "microprice_slope": 0.9},
  "session": "morning",
  "config_hash": "b394...af2",
  "guard": {"spread": 1, "depth": 2500, "passed": true},
  "notes": "confirm@+14s"
}
```

---

## 🏃 실행 흐름(Phase ↔ scripts ↔ src 매핑)

* **Phase 0**: `scripts/step01_prep_clean.py` → `io_utils.py`
* **Phase 1**: `scripts/step03_detect.py` → `features_core.py` + `detect_onset.py`
* **Phase 2**: `scripts/step04_execute_guard.py` → `execute_guard.py`
* **Phase 3**: `scripts/step06_tune.py` → `features_ext.py` + `metrics_eval.py`
* **Phase 4**: `scripts/step07_replay.py` & `step08_online_stub.py` → `ingestion.py` + `metrics_eval.py`

---

## 🧪 Makefile 단축명령(예시)

```makefile
run-detect:
\tpython -m src.main detect --cfg config/onset_default.yaml --csv data/clean/sample.csv

replay:
\tpython -m src.main replay --cfg config/onset_default.yaml --csv data/clean/sample.csv

eval:
\tpython -m src.main eval --cfg config/onset_default.yaml --events data/events/*.jsonl

tune:
\tpython scripts/step06_tune.py --cfg config/onset_default.yaml --grid config/profiles.yaml
```

---

## 🧭 Claude Code 작업 가이드 (첫 스프린트)

1. **스캐폴딩**

* 위 트리 생성, `pyproject.toml` 또는 `requirements.txt`(pydantic/pyyaml/pandas/numpy/pyarrow) 추가.
* `config_loader.py`, `schemas.py`, `io_utils.py`에 최소 함수 시그니처만 먼저 생성.

2. **최소셋 피처 → CPD 게이트 → 탐지 FSM**

* `features_core.py`에 6–8개 피처 구현(롤링/누출금지).
* `cpd/online_cusum.py`, `cpd/page_hinkley.py`, `detection/cpd_gate.py` 구현.
* `step03_detect.py`에서 **CPD 게이트 → 후보(p-임계) → Δ확인 → 불응** 흐름으로 배선.

3. **리플레이-온라인 인터페이스**

* `ingestion.py`에 `ReplaySource`(CSV iterator) 완성, `KiwoomSource`는 스텁(동일 메서드 시그니처).

4. **메트릭/리포트**

* `metrics_eval.py`에 In-window, FP/h, TTA p95 구현.
* `reports/`에 JSON 요약 저장.

5. **유닛테스트 3종**

* 누출(`test_leakage.py`), FSM(`test_onset_fsm.py`), 동형성 스텁(`test_online_parity.py`).

> **원칙**: tz-aware, 결정적 재현(난수 고정), 스트리밍 상태에서 **시점 t까지만** 사용(누출 금지).

