좋아요. **CPD 게이트(+ Δ 확인 + ML) 3중 구조**를 최상위 3개 문서에 반영하는 **unified diff 지시안**을 준비했어요.
아래 패치를 **그대로 Claude Code에 붙여넣어 적용**하면 됩니다. (파일명/섹션은 현재 버전 기준이며, 원문 근거는 각 문서에 인용표시로 달았습니다.)

---

# 1) `Project overal.md` 패치

(온셋 정의·Phase1 파이프라인·KPI에 CPD 게이트를 정식 반영: “선택” → **기본 채택**)

```diff
--- a/Project overal.md
+++ b/Project overal.md
@@
-## 중간 목적(MVP/초기 스코프)
-* **라벨/학습 없이도** 작동 가능한 **룰 기반 온셋 탐지**를 먼저 세우고(후보→확인→불응),
+## 중간 목적(MVP/초기 스코프)
+* **라벨/학습 없이도** 작동 가능한 **온셋 탐지**를 세우되, 이제부터는
+  **앞단 CPD 게이트(온라인 CUSUM/Page–Hinkley) → Δ-축 확인(가격축 필수) → ML 임계**의
+  **3중 구조**를 **기본 파이프라인**으로 채택한다.
   * 사용 가능한 **기성 지표(현재 44개)** 중 **핵심 최소셋**으로 시작하되,
   * **지표 랭킹·튜닝 프레임워크**로 상위 지표·윈도우·임계를 **지속 교정**하며,
   * \*\*리플레이(오프라인)\*\*와 \*\*키움 실시간(온라인)\*\*에서 **동일 논리**로 돌아가는 것을 1차 목표로 한다.
@@
-## 온셋(Onset)의 의미(개념적 정의)
-* **온셋**은 **'평시 → 급등' 상태 전환을 가능한 빠르게 포착**하되, **짧은 확인창(세션별 10–30초 가변)**에서 지속성 증거로 **확정**하는 운영 개념이다.
+## 온셋(Onset)의 의미(개념적 정의)
+* **온셋**은 **'평시 → 급등' 상태 전환을 가능한 빠르게 포착**하되, **짧은 확인창(세션별 10–30초 가변)**에서 지속성 증거로 **확정**한다.
+  이때 **포착 순서**는 다음과 같다:
+  1) **CPD 게이트**(온라인 CUSUM=가격축, Page–Hinkley=거래축 중 1~2개)로 상태변화 신호를 1차 거르고,
+  2) **Δ-축 확인**(가격축 필수 + 참여/마찰 중 ≥1, earliest-hit + `persistent_n`)으로 확정,
+  3) (있다면) **ML 임계**로 최종 필터링.
@@
-## 노이즈(Noise)와의 구분(운영 규칙)
+## 노이즈(Noise)와의 구분(운영 규칙)
 * **Noise**: 초기에 급등처럼 보이나 **1분 이내에 1~4% 반짝** 후 **거래가 식고** 되돌리는 패턴.
-* 온셋 **확정 전**에는 **짧은 확인창(10–30초, 세션 가변)**에서 **지속성 증거(가격/거래/호가)**를 요구하고,
+* 온셋 **확정 전**에는 **CPD 게이트 통과 + 짧은 확인창(10–30초, 세션 가변)**에서
+  **지속성 증거(가격/거래/호가)**를 요구하고,
   **확정 후**에도 **지속성/되돌림 태깅**을 통해 **강도·패턴 라벨링**을 부여하여 \*\*후속 의사결정(익절·손절·보류)\*\*에 활용한다.
@@
-## Phase 1 — 온셋 탐지 엔진 v2 (후보→확인→불응)
+## Phase 1 — 온셋 탐지 엔진 v3 (CPD→Δ확인→불응, ML 필터)
@@
-* **탐지 로직(확인 로직 보강)**
-  * **트리거(후보)**: `S_t = wS*Speed + wP*Participation + wF*Friction` ≥ **세션별 p-임계**
-    (+ 옵션) **단측 CUSUM(S_t)** > h 로 "지속적 양(+) 드리프트"만 허용.
+* **탐지 로직(3중 구조)**
+  * **(1) CPD 게이트(필수)**:
+    - 가격축: **CUSUM**(입력 예: `ret_50ms` 또는 `microprice_slope`) with `k`=0.5~1.0×평시σ(MAD 기반), `h`=4~8×k
+    - 거래축: **Page–Hinkley**(입력 예: `z_vol_1s`) with `delta`≈0.05–0.1, `lambda`≈5–10
+    - **게이트 통과 시에만** 후속 단계 진행(장초반 `min_pre_s` 확보, `cooldown_s` 적용).
+  * **(2) 후보 산출**: `S_t = wS*Speed + wP*Participation + wF*Friction` ≥ **세션별 p-임계**
   * **확인(확정)**: **절대 임계 기반**에서 **상대 개선(Δ) 기반 + 가격 축 필수 + earliest-hit + 연속성(persistent_n)**으로 전환.
@@
-* **확정 아님**
-  * **가중치/임계/윈도우 값은 고정 아님**(Phase 3에서 스윕·랭킹으로 결정).
+* **확정 아님**
+  * **가중치/임계/윈도우/CPD 파라미터 값은 고정 아님**(Phase 3에서 스윕·랭킹으로 결정).
@@
-## Phase 2 — 실행 가능성 가드(체결성/슬리피지) + 정책 훅
+## Phase 2 — 실행 가능성 가드(체결성/슬리피지) + 정책 훅
   * **체커**
@@
-## Phase 3 — 랭킹 & 튜닝(44지표 활용) + 스윕
+## Phase 3 — 랭킹 & 튜닝(44지표/CPD 파라미터) + 스윕
@@
-* **스윕(그리드/베이지안)**
-  * 숏윈도우(30/60/90/120/180s), 롱윈도우(10/15/20/30/45/60m), 임계(p90–p98),
-  * 불응(60–180s), 확인창(10/20/30s), 가중치(wS/wP/wF), CUSUM(k,h).
+* **스윕(그리드/베이지안)**
+  * 숏윈도우(30/60/90/120/180s), 롱윈도우(10/15/20/30/45/60m), 임계(p90–p98),
+  * 불응(60–180s), 확인창(10/20/30s), 가중치(wS/wP/wF),
+  * **CPD 파라미터**: CUSUM(k,h), Page–Hinkley(delta, lambda), `min_pre_s`, `cooldown_s`.
@@
-## 전체 원칙(공통)
-* **미래 미사용(누출 금지)**, **세션별 적응 임계**, **후보→확인→불응 3단계**,
+## 전체 원칙(공통)
+* **미래 미사용(누출 금지)**, **세션별 적응 임계**, **CPD→후보→확인→불응 4단계(ML 필터 결합)**,
   * **지표·윈도우·임계는 고정값 아님**(Phase 3에서 데이터로 채택),
   * **CSV 리플레이 = 키움 실시간 동형성** 확보가 MVP의 생명.
@@
-## 🧩 보조 체크(공통)
+## 🧩 보조 체크(공통)
 - **누출 테스트**: 파일 임의 시점에서 잘라 재실행 → 동일 결과
 - **설정 주도형**: 모든 임계/윈도우/불응/확인창/가중치가 `config/*.yaml`에서만 변경
-- **버전화**: `config_hash`를 이벤트/리포트에 주입
+- **버전화**: `config_hash`를 이벤트/리포트에 주입 (CPD 파라미터 포함)
 - **플롯**: 가격 + 후보/확정 마커, 체결성 상태 오버레이
```

근거(현행 구조·원칙·Phase 정의): `Project overal.md`의 기존 범위/탐지·가드·튜닝 기술서술.

---

# 2) `Project_root.md` 패치

(모듈·스크립트에 CPD 폴더/게이트 추가, 매핑·Make 타깃 보강)

```diff
--- a/Project_root.md
+++ b/Project_root.md
@@
 project-root/
@@
 ├─ src/
 │  ├─ __init__.py
 │  ├─ main.py                  # CLI 라우터 (replay/detect/eval 등)
 │  ├─ config_loader.py         # YAML 로더 + config_hash 주입
 │  ├─ io_utils.py              # tz-aware 파서, 누출 방지 컷, 경로/캐시
 │  ├─ features_core.py         # **핵심 6–8개** 피처 계산(지연 최소)
 │  ├─ features_ext.py          # 확장 44지표(Phase3 튜닝 시 사용)
-│  ├─ detect_onset.py          # 온셋 점수, p95 임계, 확인창(10–30s), 불응 FSM(확인=Δ기반+가격축 필수+earliest-hit+연속성)
+│  ├─ detect_onset.py          # (후단) 후보 점수, Δ확인(가격축 필수+earliest-hit+연속성), 불응 FSM
 │  ├─ execute_guard.py         # 체결성(spread/depth)/슬리피지 상한식
 │  ├─ ingestion.py             # CSV 리플레이/키움 스트림 **공용 인터페이스**
 │  ├─ metrics_eval.py          # In-window, FP/h, TTA p95, 체결성 통과율
 │  └─ schemas.py               # 이벤트/레코드 스키마 (pydantic/dataclass)
+│  ├─ detection/
+│  │   └─ cpd_gate.py         # CPD 게이트(가격=CUSUM, 거래=Page–Hinkley) 통합
+│  └─ cpd/                    # CPD 원자 모듈
+│      ├─ online_cusum.py     # OnlineCUSUM(k,h).update(x)->bool
+│      └─ page_hinkley.py     # PageHinkley(delta,lambda).update(x)->bool
@@
 ├─ scripts/                    # 단일 파일 실행 진입점(Phase 스텝용)
@@
-│  ├─ step03_detect.py         # 후보→확인→불응 상태기계(확인: Δ기반+가격축 필수+earliest-hit+연속성)
+│  ├─ step03_detect.py         # **CPD 게이트 → 후보 → Δ확인 → 불응** 상태기계
@@
 └─ tests/
    ├─ test_leakage.py          # 임의 절단 재실행 동일성
-   ├─ test_onset_fsm.py        # 상태기계 단위 테스트
+   ├─ test_onset_fsm.py        # 상태기계 단위 테스트(CPD 게이트 포함)
+   └─ test_cpd.py              # CUSUM/Page–Hinkley 단위 테스트
@@
-## 🧩 역할 요약 (모듈 7개 고정)
+## 🧩 역할 요약 (모듈 7개 + CPD 서브모듈)
@@
-4. `detect_onset.py`
-* 온셋 스코어 $S_t = w_S f_S + w_P f_P + w_F f_F$
-* **세션 퍼센타일(p95±)** 임계로 후보
-* **확인창(10–30s)**: **상대 개선(Δ) 기반 + 가격 축 필수 + earliest-hit + `persistent_n` 연속성**
-* 그 후 **불응(60–180s)**
-* (옵션) 단측 CUSUM 훅.
+4. `detection/cpd_gate.py` + `cpd/*`
+* **앞단 게이트(필수)**: CUSUM(가격축), Page–Hinkley(거래축) 온라인 탐지
+* 파라미터: k,h / delta,lambda / min_pre_s, cooldown_s
+* 게이트 통과 시에만 후속 단계 진행
+
+5. `detect_onset.py`
+* **후단 단계**: 후보(세션 p-임계) → Δ확인(가격축 필수+earliest-hit+`persistent_n`) → 불응(60–180s)
@@
-## 🧭 Claude Code 작업 가이드 (첫 스프린트)
+## 🧭 Claude Code 작업 가이드 (첫 스프린트)
@@
-2. **최소셋 피처 → 탐지 FSM**
-* `features_core.py`에 6–8개 피처 구현(롤링 윈도우/지연 체크).
-* `detect_onset.py`에서 p95 임계 후보 → **Δ기반 확인(가격 축 필수, earliest-hit, `persistent_n`)** → 불응(90s) FSM 구현.
+2. **최소셋 피처 → CPD 게이트 → 탐지 FSM**
+* `features_core.py`에 6–8개 피처 구현(롤링/누출금지).
+* `cpd/online_cusum.py`, `cpd/page_hinkley.py`, `detection/cpd_gate.py` 구현.
+* `step03_detect.py`에서 **CPD 게이트 → 후보(p-임계) → Δ확인 → 불응** 흐름으로 배선.
```

근거(현 루트 트리/모듈 책임/스크립트 매핑): `Project_root.md`의 7-모듈 구조와 step 매핑.

---

# 3) `Step overal.md` 패치

(Phase1에 CPD 관련 **신규 Step** 추가, 의존성/평가/완료 기준 반영)

```diff
--- a/Step overal.md
+++ b/Step overal.md
@@
-# Phase 1 — 온셋 탐지(룰 기반) (총 5 Steps)
+# Phase 1 — 온셋 탐지(3중 구조: CPD→Δ확인→불응) (총 7 Steps)
@@
-**Step 1-1 | 최소셋 피처 계산기**
+**Step 1-1 | 최소셋 피처 계산기**
@@
-**Step 1-2 | 세션 퍼센타일 임계(p95±) 계산**
+**Step 1-2 | 세션 퍼센타일 임계(p95±) 계산**
@@
-**Step 1-3 | 온셋 스코어 & 후보 트리거**
+**Step 1-3 (신규 앞단) | CPD 게이트 모듈**
+* 작업: `cpd/online_cusum.py`, `cpd/page_hinkley.py`, `detection/cpd_gate.py`
+  - 가격축(CUSUM): 입력 `ret_50ms`(또는 `microprice_slope`), 파라미터 `k,h`
+  - 거래축(Page–Hinkley): 입력 `z_vol_1s`, 파라미터 `delta, lambda`
+  - 운영 상수: `min_pre_s`(장초반 보호), `cooldown_s`(재트리거 억제)
+* 산출물: 게이트 통과 시각 로그, `cpd_trigger` 플래그(이벤트 필드)
+* 완료 기준: 장초반 10s 미만 무효화, 게이트 통과 후 N초 이내 재발화 억제 로그 확인
+
+**Step 1-4 | 온셋 스코어 & 후보 트리거**
 * 작업: `src/detect_onset.py`에서 $S_t = w_S f_S + w_P f_P + w_F f_F$ 계산, p95 임계 초과 시 **candidate** 이벤트 발생.
-* 산출물: `data/scores/` 또는 `data/events/*.jsonl`(candidate).
-* 완료 기준: 후보 이벤트 타임스탬프/개수 로그 확인.
+* 제약: **CPD 게이트 통과 시에만** 후보를 평가
+* 산출물: `data/scores/` 또는 `data/events/*.jsonl`(candidate)
+* 완료 기준: 후보 이벤트 타임스탬프/개수 로그(게이트 연동) 확인.
 
-**Step 1-4 | 확인창(10–30s) & 확정 로직**
+**Step 1-5 | 확인창(10–30s) & 확정 로직**
 * 작업: 확인창 윈도우 내 **지속성 증거(가격/거래/호가)** ≥1 만족 시 **confirm** 이벤트로 승격.
 * 산출물: `onset_confirm` 이벤트 JSONL.
 * 완료 기준: 사용자가 지정한 급등 구간 내 최소 1회 confirm 발생(샘플 데이터 기준).
 
-**Step 1-5 | 불응(Refractory) 상태기계**
+**Step 1-6 | 불응(Refractory) 상태기계**
 * 작업: confirm 후 **중복 알람 억제(60–180s)** 상태기계.
 * 산출물: `refractory_enter/exit` 이벤트, 상태 로그.
 * 완료 기준: 동일 구간 중복 알람 없음.
+
+**Step 1-7 | (선택) ML 임계 결합**
+* 작업: 룰 기반 확정 후 `onset_strength` 또는 ML 확률로 최종 필터
+* 산출물: 필터링 후 이벤트 집합, 임계/사유 로그
+* 완료 기준: FP/h 하락, in-window 탐지율 유지
@@
-## 권장 작업 흐름(Claude 지시 예시)
+## 권장 작업 흐름(Claude 지시 예시)
 1. “**Step 0-1부터 0-3까지**를 순서대로 구현하고, 테스트 로그와 생성 파일 목록을 출력해줘.”
-2. “**Step 1-1~1-3**을 한 번에 처리: 최소셋 피처 + p95 임계 + 후보 이벤트 생성. 누출 테스트 포함.”
-3. “**Step 1-4~1-5**: 확인창 확정 + 불응 FSM. 샘플 CSV로 candidate→confirm→refractory 로그 보여줘.”
+2. “**Step 1-1~1-4**: 최소셋 피처 + p95 임계 + **CPD 게이트** + 후보 이벤트 생성. 누출 테스트 포함.”
+3. “**Step 1-5~1-6**: 확인창 확정 + 불응 FSM. 샘플 CSV로 candidate→confirm→refractory 로그(게이트 연동) 보여줘.”
 4. “**Step 2-1~2-3**: guard/슬리피지/의사결정 병합(로그 전용).”
-5. “**Step 3-1~3-2**: 메트릭/스윕 러너, 리포트 산출.”
+5. “**Step 3-1~3-2**: 메트릭/스윕 러너, 리포트 산출(여기에 **CPD 파라미터(k,h,delta,lambda,min_pre_s,cooldown_s)** 포함).”
 6. “**Step 3-3~3-5**: 안정성 선택→44지표 확장 연결→best 설정 스냅샷.”
 7. “**Step 4-1~4-4**: 리플레이/온라인 스텁→동형성/SLA→Go/No-Go 보고.”
```

근거(현 Step 체계·입출력·완료기준): `Step overal.md`의 Phase/Step 정의와 권장 흐름.

---

## 적용 순서(요약)

1. `Project overal.md` 먼저 패치 → 파이프라인 원칙을 “CPD 기본”으로 승격
2. `Project_root.md` 패치 → **cpd 모듈/게이트** 추가 및 스크립트/테스트 매핑 갱신
3. `Step overal.md` 패치 → **Phase1에 CPD 신규 Step 1-3** 도입, 이후 단계 인덱스 재배열
