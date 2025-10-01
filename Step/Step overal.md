Role: 수석 소프트웨어 아키텍트

아래는 **Claude Code가 한 번에 처리하기 적당한 단위**로 쪼갠 **Phase별 Step 설계**입니다.
각 Step은 “무엇을 구현/정리해야 하는가(작업 내용)”에 초점을 맞추었고, **입력/출력(산출물)과 완료 기준**만 적었습니다. 세부 코드 가이드는 의도적으로 제외했습니다.

---

# Phase 0 — 스캐폴딩 & 파이프 스모크 (총 5 Steps)

**Step 0-1 | 프로젝트 스캐폴딩 최소 세트**

* 작업: 폴더 구조 생성, `pyproject.toml`/`requirements.txt`, `.env.example`, `.gitignore`, `README.md` 골격 작성.
* 산출물: 기본 트리 + 의존성 파일.
* 완료 기준: `pip install -r requirements.txt` 성공, README에 실행 명령 섹션(초안) 존재.

**Step 0-2 | 설정 로더 & 경로 정의**

* 작업: `config/`(onset\_default.yaml, profiles.yaml, paths.yaml) 초안 작성, `src/config_loader.py`에서 YAML 로드 + `config_hash` 생성.
* 산출물: 설정 파일 3개 + 로더 유틸.
* 완료 기준: 임의 YAML 수정 시 `config_hash`가 이벤트/로그에 주입 가능.

**Step 0-3 | I/O 유틸 & 스키마**

* 작업: `src/io_utils.py`(tz-aware 파싱, 정렬, 정규장 마스크, 임의 절단) + `src/schemas.py`(레코드/이벤트 데이터클래스).
* 산출물: 유틸/스키마 파일.
* 완료 기준: 샘플 CSV 1개로 tz/정렬/절단 테스트 스크립트 통과.

**Step 0-4 | 데이터 스모크 테스트**

* 작업: `scripts/step01_prep_clean.py`(간단 정제), 로깅 기본 설정, `logs/app.log` 생성 검증.
* 산출물: `data/clean/` 샘플 출력.
* 완료 기준: 원본 1틱 CSV → clean CSV 생성, 결측/정렬 경고 로그 출력.

**Step 0-5 | CLI 엔트리 라우터**

* 작업: `src/main.py`에 `detect/replay/eval/tune` 명령 라우팅(파라미터만 바인딩).
* 산출물: `python -m src.main --help` 동작.
* 완료 기준: 각 서브커맨드 도움말 표기.

---

# Phase 1 — 온셋 탐지(3중 구조: CPD→Δ확인→불응) (총 7 Steps)

**Step 1-1 | 최소셋 피처 계산기**

* 작업: `src/features_core.py`에 **핵심 6–8개** 피처(스트리밍 지연 최소) 계산 파이프.
* 산출물: `data/features/` 샘플 생성.
* 완료 기준: 시점 t까지만 사용(누출 없음) 단위 테스트 통과.

**Step 1-2 | 세션 퍼센타일 임계(p95±) 계산**

* 작업: 세션 분류(오전/점심/오후), 피처 기반 임계(p95±) 산출/캐싱.
* 산출물: 세션별 임계 캐시(메모리/파일).
* 완료 기준: 다른 세션 입력 시 임계 자동 전환.

**Step 1-3 (신규 앞단) | CPD 게이트 모듈**

* 작업: `detection/candidate_detector.py` 내 inline CPD 게이트 구현
  - 가격축(CUSUM): 입력 `ret_1s`, 파라미터 `k,h`
  - 거래축(Page–Hinkley): 입력 `z_vol_1s`, 파라미터 `delta, lambda`
  - 운영 상수: `min_pre_s`(장초반 보호), `cooldown_s`(재트리거 억제)
  - 설정: `cpd.use: false` (기본 비활성, 하위 호환성 유지)
* 산출물: CPD 게이트 로직 통합, 설정 기반 활성화
* 완료 기준: 장초반 10s 미만 무효화, 게이트 통과 후 N초 이내 재발화 억제, 비활성 시 기존 로직 유지

**Step 1-4 | 온셋 스코어 & 후보 트리거**

* 작업: `detection/candidate_detector.py`에서 절대 임계 기반 `trigger_axes` 평가
  - Speed axis: `ret_1s > 0.0008`
  - Participation axis: `z_vol_1s > 1.8`
  - Friction axis: `spread_narrowing < 0.75`
  - `min_axes_required: 2` 충족 시 **candidate** 이벤트 발생
* 제약: **CPD 게이트 활성화 시에만** 게이트 통과 후 평가 (기본은 게이트 비활성)
* 산출물: `onset_candidate` 이벤트 (trigger_axes, evidence 포함)
* 완료 기준: features_df 입력 → candidate events 리스트 반환

**Step 1-5 | 확인창(12s) & 확정 로직 (Delta-based)**

* 작업: `detection/confirm_detector.py`에서 상대 개선(Δ) 기반 확정
  - Pre-window (5s) baseline 계산
  - Confirm-window (12s) 내 Delta 검증
  - 가격 축 필수 + min_axes=2 + persistent_n=4 연속 충족
  - Earliest-hit 방식으로 최초 시점 확정
* 산출물: `onset_confirmed` 이벤트 (axes, onset_strength, delta 값 포함)
* 완료 기준: features_df + candidate_events 입력 → confirmed_events 리스트 반환

**Step 1-6 | 불응(Refractory) 상태기계**

* 작업: `detection/refractory_manager.py`에서 종목별 불응기 관리
  - Duration: 20초 (Detection Only 단축)
  - 종목별(stock_code) 분리 관리
  - `extend_on_confirm: true` 설정
* 산출물: `onset_rejected_refractory` 이벤트 (차단된 candidate)
* 완료 기준: 동일 종목 내 refractory 기간 중 candidate 차단 확인

**Step 1-7 | (선택) ML 임계 결합**

* 작업: 룰 기반 확정 후 `onset_strength` 또는 ML 확률로 최종 필터
* 산출물: 필터링 후 이벤트 집합, 임계/사유 로그
* 완료 기준: FP/h 하락, in-window 탐지율 유지

---

# Phase 2 — 체결성/슬리피지 가드 (총 3 Steps)

**Step 2-1 | 체결성 체크(분리된 모듈)**

* 작업: `src/execute_guard.py`에 `spread ≤ θ_spread`, `depth ≥ θ_qty` 평가(탐지와 분리).
* 산출물: 이벤트에 `guard.passed` 필드 추가(로깅 우선).
* 완료 기준: confirm 시점 guard 평가 로그 남김.

**Step 2-2 | 슬리피지 상한식**

* 작업: `slip_max = α*spread + β/(depth)` 계산 모듈.
* 산출물: `guard.slippage` 필드 기록.
* 완료 기준: 임계 초과 시 `enter/skip/defer` 결정 로그.

**Step 2-3 | 의사결정 이벤트 통합**

* 작업: 탐지 이벤트 + guard 결과를 하나의 이벤트 스트림으로 병합(실거래 아님).
* 산출물: `data/events/merged.jsonl`.
* 완료 기준: confirm 발생 시점마다 guard 필드가 일관 기록.

---

# Phase 3 — 평가/튜닝/지표 확장 (총 5 Steps)

**Step 3-1 | 메트릭 집계 파이프**

* 작업: `src/metrics_eval.py`에 In-window 탐지율, FP/hour, **TTA p95**, 체결성 통과율 계산.
* 산출물: `reports/eval_summary.json`.
* 완료 기준: 샘플 데이터에서 지표 수치 출력.

**Step 3-2 | 스윕 러너(윈도우/임계/불응/가중치)**

* 작업: 그리드/베이지안 스윕 러너(입력: YAML, 출력: 성능표).
* 산출물: `reports/tuning/tuning_summary.json`.
* 완료 기준: 최소 6\~12개 조합 비교표 생성.

**Step 3-3 | 안정성 선택(Stability Selection)**

* 작업: 부트스트랩 기반 Top-k 피처 안정성 평가(≥70% 예시 기준).
* 산출물: Top-k 리스트, 중요도 표.
* 완료 기준: 반복 실행에서 Top-k 선정 변동률 보고.

**Step 3-4 | 47지표 확장 연결**

* 작업: `src/features_ext.py`로 47지표 계산 연결(미래값 미사용 보증).
* 산출물: `data/features/` 확장본.
* 완료 기준: NaN 0%, 지연 경고 0건.

**Step 3-5 | 최적 설정 스냅샷**

* 작업: `config/onset_best.yaml` 생성(최적 파라미터/가중치/윈도우).
* 산출물: 베스트 설정 파일 + 비교 리포트.
* 완료 기준: 베스트 설정으로 재실행 시 성능 재현.

---

# Phase 4 — 리플레이/온라인 동형성 & Go/No-Go (총 4 Steps)

**Step 4-1 | 리플레이 파이프**

* 작업: `scripts/step07_replay.py` + `src/ingestion.py(ReplaySource)`: CSV를 실시간처럼 스트리밍.
* 산출물: 리플레이 이벤트 스트림.
* 완료 기준: 실시간 흉내(지연/배치 크기 설정) 정상 동작.

**Step 4-2 | 온라인 스텁 인터페이스**

* 작업: `src/ingestion.py(KiwoomSource stub)` 정의 — 실전 연결 전 동일 시그니처로 이벤트 공급.
* 산출물: 온라인 스텁 이벤트 스트림.
* 완료 기준: `ReplaySource`와 동일 API/타입으로 교체 가능.

**Step 4-3 | 동형성 테스트 & SLA 측정**

* 작업: 동일 종목/시간 범위에서 **리플레이=온라인** 이벤트 일치성 비교, **Confirm p95 ≤ 2s** 측정.
* 산출물: `reports/online_parity.json`.
* 완료 기준: 타임스탬프/개수/결정 **허용오차 내 동일**, p95 목표 충족.

**Step 4-4 | Go/No-Go 보고서**

* 작업: 사용자 급등 2구간 내 ≥1건, 구간 밖 **FP/h ≤ 1**, **체결성 ≥ 70%**, **TTA p95 ≤ 2s** 종합 판단.
* 산출물: `reports/go_nogo_summary.json`.
* 완료 기준: 합/부 결정 + 근거 수치 명시.

---

## 의존성 매트릭스(요지)

* Phase 1은 Phase 0의 설정/스키마/I-O가 **선행**.
* Phase 2는 Phase 1의 **confirm 이벤트**가 선행.
* Phase 3은 Phase 1(탐지) + Phase 2(guard) 산출물을 입력으로 사용.
* Phase 4는 Phase 1\~3 산출물과 ingestion 인터페이스를 재사용.

---

## 권장 작업 흐름(Claude 지시 예시)

1. “**Step 0-1부터 0-3까지**를 순서대로 구현하고, 테스트 로그와 생성 파일 목록을 출력해줘.”
2. "**Step 1-1\~1-4**: 최소셋 피처 + p95 임계 + **CPD 게이트** + 후보 이벤트 생성. 누출 테스트 포함."
3. "**Step 1-5\~1-6**: 확인창 확정 + 불응 FSM. 샘플 CSV로 candidate→confirm→refractory 로그(게이트 연동) 보여줘."
4. “**Step 2-1\~2-3**: guard/슬리피지/의사결정 병합(로그 전용).”
5. "**Step 3-1\~3-2**: 메트릭/스윕 러너, 리포트 산출(여기에 **CPD 파라미터(k,h,delta,lambda,min_pre_s,cooldown_s)** 포함)."
6. "**Step 3-3\~3-5**: 안정성 선택→47지표 확장 연결→best 설정 스냅샷."
7. “**Step 4-1\~4-4**: 리플레이/온라인 스텁→동형성/SLA→Go/No-Go 보고.”

