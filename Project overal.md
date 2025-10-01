# 🎯 목적

## 최종 목적(End Goal)

**현재 진행 단계는 '급등 포착(Detection Only)'에 한정**된다.
이 구간의 목표는 아래와 같다:

- 급등 발생을 최대한 놓치지 않고(Recall 우선)
- 5~12초 이내로 빠르게 경보(Alert) 발생
- FP(FP/h)는 이후 분석 단계에서 제거하므로 현재는 허용
- 매매/체결성/호가분석/수익률은 다음 Phase에서 처리

**즉, 지금은 '탐지까지(Output: Alert Event)'가 전부이며,
분석·매매는 범위 밖이다.**

이후 Phase 2~3~4에서는 분석(호가/강도/패턴)과 매매결정,
확장 지표·ML·전략화를 점진적으로 진행한다.

## 중간 목적(MVP/포착 전용 스코프)

* 라벨/학습 없이도 작동 가능한 **급등 포착 전용 룰 기반 탐지**를 우선 구축한다.
  * 핵심 지표는 6~8개 수준(속도·참여·마찰 중심)만 사용한다.
  * 47개 확장 지표, ML, 분류·강도예측은 Phase 2 이후로 이관한다.
  * 리플레이(과거 CSV)와 실시간(키움 등)의 동형성은 필수 유지한다.

> **Modify 범위 고지:** 본 문서에서 "수정(Modify)"는 **기존 로직/구조 보강**만 포함합니다.
> **시뮬레이션/실시간/리스크/최적화 등 신규 기능은 Modify 범위가 아니며**, 추후 **Project Overview 변경 후 별도 Phase**에서 진행합니다.

## 성과지표(Detection Only 단계)
* Recall (>= 65~80%)  → 놓침 최소화
* Alert Latency p50 (<= 8~12초)
* FP/hour (20~50까지 허용) → 이후 단계에서 필터링
* Precision은 참고용 (목표 40~60%)
* 손익, 체결성, 슬리피지는 평가하지 않음 (다음 Phase)

---

# ⚡️ ‘급등’에 대한 사용자 정의(Working Definition) — “고정값 아님”

> 아래 정의는 **당신이 설명한 현실적 현상**을 **운영에 쓰기 좋게 정리**한 **작업용(가변) 정의**입니다.
> **고정된 규격이 아니며**, 데이터/검증 결과에 따라 **윈도우·임계·지표 구성이 바뀔 수 있음**을 전제로 합니다.

## 핵심 개념

* **급등**은 **평시**에서 **수초\~수십초** 사이에 **거래량과 가격의 가속이 동시**에 **비정상적으로 커지며**, **새로운 레짐으로 진입**하는 **시작점**(온셋)을 갖는 현상이다.
* 이후 **수분\~수십분** 동안 **관성적으로 이어질 수** 있으며, **강도와 지속시간은 종목·상황별로 매우 상이**하다.

## 최소 기준(초기 가정값, 튜닝 대상)

* (예시) **온셋 이후 2분간 상승**, 1분틱 기준 **틱당 ≥ +1%** 수준의 가속/지속이면 **"최소 급등"**으로 간주하되,
  **보조 확인 룰**로 **거래량 z-score(세션 기준) ≥ 2** 및 **스프레드 임계(종목 틱가 반영)** 충족을 권장한다.
* 이 최소 기준은 **운영 중 조정**한다(시장·종목·세션별로 다를 수 있음).

## 온셋(Onset)의 의미(Detection Only 관점)

* 온셋은 '평시 → 급등'으로 바뀌는 순간을 **일단 놓치지 않고 잡는 것**이다.
* 포착 후 매매·분석은 하지 않으며, 다음 조건만 만족하면 Alert 발령으로 종료한다:
  1) 핵심 3축(속도·참여·마찰) 중 2축 이상이 낮은 임계치를 초과
  2) 8~15초 내 짧은 확인창에서 연속성(persistent_n) 충족
  3) 가격이 역전(급락)되지 않는 수준의 확인만 수행
* 이후의 체결성, 슬리피지, 강도 판정 등은 다음 Phase에 위임한다.

## 노이즈(Noise) 처리 (Detection Only 관점)

* Noise는 '포착 후 필터링' 대상으로 간주한다.
* 현재 단계에서는 FP(거짓 경보)가 발생하더라도 허용한다.
* 확인창 역시 8~15초 이내로 짧게 가져가며, 완전한 분류나 패턴 라벨링은 하지 않는다.
* 후속 강도 분석/패턴 분류/익절·손절 판단은 Phase2~3에 위임한다.

## 지표 사용에 대한 원칙

* 현재 **47개 지표**를 활용 가능하나, **처음부터 전부 고정**하지 않는다.
* **핵심 최소셋(6–8개)**으로 시작하고, 이후 **피처 랭킹/안정성 선택(Stability Selection)**으로 **Top-k**를 **의무적으로** 채택한다.
  - 급등 구간 vs 평시: KS, Cliff's δ, 단변량 AUC/효과크기
  - L1-Logit/GBT + 부트스트랩 **Stability Selection**
  - **합격선(예시)**: 반복 샘플링에서 Top-k **선정 안정성 ≥ 70%**

## 전체 47개 지표 목록

### 기본 데이터 (4개)
`time`, `stock_code`, `current_price`, `volume`

### 기술적 지표 (11개)
`ma5`, `rsi14`, `disparity`, `stoch_k`, `stoch_d`, `vol_ratio`, `z_vol`, `obv_delta`, `spread`, `bid_ask_imbalance`, `accel_delta`

### 수익률/변화율 지표 (2개)
`ret_1s`, `ret_accel`

### 호가 데이터 (10개)
`ask1`, `ask2`, `ask3`, `ask4`, `ask5`, `bid1`, `bid2`, `bid3`, `bid4`, `bid5`

### 호가 수량 데이터 (10개)
`ask1_qty`, `ask2_qty`, `ask3_qty`, `ask4_qty`, `ask5_qty`, `bid1_qty`, `bid2_qty`, `bid3_qty`, `bid4_qty`, `bid5_qty`

### 고급 지표 (10개)
`z_vol_1s`, `mid_price`, `ticks_per_sec`, `inter_trade_time`, `microprice`, `microprice_slope`, `up_tape_ratio`, `imbalance_1s`, `spread_narrowing`, `OFI_1s`

---

> 이 문서는 \*\*목적과 ‘급등’의 사용자 정의를 오해 없이 고정해두기 위한 “베이스”\*\*입니다.
> 다음 단계에서 이 정의를 기반으로 \*\*MVP 큰 틀(모듈 구성, 데이터 흐름, 튜닝·검증 계획, 산출물 스키마, 키움 실시간 연계)\*\*을 인수인계 문서로 정리해 드리겠습니다.

=======================================================================================

# 🧭 MVP 큰 틀 (Phase 순서 제안 — “확정 아님” 항목은 명시)

> 목표: **1틱 CSV 리플레이 ≒ 실시간(키움) 동등** 환경에서
> **온셋(급등 시작) 포착 → 짧은 확인 → 실행 가능성 판단**까지 “작동하는 최소제품” 완성.

---

## Phase 0 — 베이스라인 & 동형성(Parity) 확보

**목적**: 오프라인(CSV)과 온라인(키움)이 **같은 규격/논리**로 돌아가게 만드는 토대.

* **입력/계약(불변)**

  * 타임존 `Asia/Seoul`, 정렬된 `ts`(ms 가능), 최소 스키마: `ts,last,vol,bid1,ask1,bid_qty1,ask_qty1`.
  * **이벤트 타임스탬프 표준:** 저장 시 `ts`는 **epoch_ms(int)** 로 통일(파이프라인 전 구간 동일 규격).
  * (있으면) 추가 호가 레벨/체결 방향/기존 47지표.
* **모듈**

  * `data_loader`: CSV/JSONL → DataFrame 변환 (timezone-aware, 정렬 보장)
  * `features/core_indicators`: DataFrame 기반 피처 계산 (streaming-compatible)
  * `config_loader`: YAML 기반 설정 로딩 (Pydantic 모델, `config_hash` 주입)
  * `logging+version`: `metadata/versions.json`, `config_hash` 주입.
* **산출물**

  * 최소 리플레이 로그, 샘플 플롯(가격+마커), 스모크 테스트.
* **확정 아님**

  * (키움 어댑터 상세, 실거래 훅) **MVP 단계에서 연결**하되 이 Phase에서는 인터페이스만 정의.

---

## Phase 1 — 온셋 탐지 엔진 v3 (CPD→Δ확인→불응, ML 필터)

**목적**: "사람이 차트에서 느끼는 급등 시작"을 **속도/참여/마찰** 세 축으로 수치화하여 **첫 관통**을 포착.

* **입력 구조**: CSV/JSONL 기반 DataFrame (배치 처리)
* **파이프라인**: `OnsetPipelineDF.run_batch(features_df)` → confirmed events

* **피처 계산(DataFrame 기반, streaming-compatible)**

  * **Speed**: `ret_1s`, `Δret_1s`, (선택) 1초 캔들 바디/윅 비율.
  * **Participation**: `z_vol_1s`, `ticks_per_sec`, **체결 간격↓**, `up_tape_ratio`, (가능 시) `OFI_1s`.
  * **Friction**: `spread`, `spread_narrowing`, `bid_ask_imbalance`, `micro_price_momentum`.
  * **표준화**: **숏/롱 롤링**(값은 Phase 3에서 스윕) + **세션별 퍼센타일**(오전/점심/오후).
* **탐지 로직(4단계 구조)**
  * **(1) CPD 게이트(선택, 기본 비활성)**:
    - 가격축: **CUSUM**(입력: `ret_1s`) with `k`=0.5~1.0×평시σ(MAD 기반), `h`=4~8×k
    - 거래축: **Page–Hinkley**(입력: `z_vol_1s`) with `delta`≈0.05–0.1, `lambda`≈5–10
    - **게이트 통과 시에만** 후속 단계 진행(장초반 `min_pre_s` 확보, `cooldown_s` 적용).
    - 설정: `cpd.use: false` (기본값)
  * **(2) 후보 산출 (CandidateDetector)**: 절대 임계 기반 trigger_axes 평가
    - `ret_1s > 0.0008`, `z_vol_1s > 1.8`, `spread_narrowing < 0.75`
    - `min_axes_required: 2` (기본값)
  * **(3) 확인 (ConfirmDetector)**: **상대 개선(Δ) 기반 + 가격 축 필수 + earliest-hit + 연속성(persistent_n)**
    - Pre-window (5초) vs Confirm-window (12초) 비교
    - 가격 축(필수): `delta_ret ≥ 0.0001` OR `delta_microprice_slope ≥ 0.0001`
    - 거래 축: `delta_zvol ≥ 0.1`
    - 마찰 축: `delta_spread (pre - now) ≥ 0.0001`
    - 최종 판정: 가격 축 필수 + **min_axes=2 이상**이 **연속 persistent_n=4개** 충족되는 **최초 시점(earliest-hit)**
    - 설정: `confirm.window_s: 12`, `confirm.persistent_n: 4`, `confirm.exclude_cand_point: true`
  * **(4) 불응(RefractoryManager)**: 20초 (Detection Only 단축)
    - 종목별(stock_code) 관리
    - 설정: `refractory.duration_s: 20`, `refractory.extend_on_confirm: true`
  * **확장(옵션) — 온셋 구간(시작→Peak) 세그먼터**: confirm 시점부터 시작하며, (i) 롤링 고점이 더 이상 갱신되지 않거나, (ii) 고점대비 드로다운 ≥ *dd_stop_pct* (예: 0.8–1.5%), (iii) 거래/마찰이 평시로 복귀(z_vol↓, spread↑) 중 먼저 오는 조건에서 **종료**(안전장치 *max_hold_s* 적용).
  * **이벤트 단계 타입 표준**: `onset_candidate` → `onset_confirm_inprogress` → `onset_confirmed` → `refractory_enter/exit` (시각화·리포팅 동일 키 사용).
* **산출물**

  * `event_store/onsets.parquet`(후보/확정/불응, 임계·가중치 메타 포함),
  * `reports/onset_quality.json` (Alert/h, TTA p95, in-window 탐지율, FP/h),
  * (옵션) `notebooks/review.ipynb`에서 동일 CSV를 불러 **포인트/구간/단계** 시각화 재현
  * 플롯/시각화:
    - **포인트 모드(point)**: 온셋 확정 시점을 **마커**로 표기.
    - **구간 모드(span)**: 온셋 시작→Peak 구간을 **반투명 음영**으로 표기(세그먼터 ON일 때).
    - **단계별 레이어(옵션)**: candidate=연한색, confirm in-progress=중간 명도, confirmed=진한색; 하단 **Event Timeline** 보조 패널 추가 가능.
    - **디버그 라벨(옵션)**: 마커 옆에 `S_t`/증거 타입(`[price|vol|microprice]`) 표기.
    - 산출 경로: `reports/plots/<종목>_<날짜>_onset.png` (또는 HTML), 스크립트: `scripts/step05_plot_onset.py`.
* **확정 아님**

  * **가중치/임계/윈도우/CPD 파라미터 값은 고정 아님**(Phase 3에서 스윕·랭킹으로 결정).

---

### 시각화/세그먼터 설정(초안 YAML)
```yaml
visual:
  mode: point       # point | span
  show_stages: true # cand./confirm/confirmed 단계별 색/명도 구분
  debug_labels: false
  timeline_panel: true  # 하단 Event Timeline 보조 패널

segmenter:          # span 모드일 때만 사용
  dd_stop_pct: 0.012   # 고점대비 1.2% 드로다운에서 종료
  vol_norm_z: 1.0      # 거래량 z가 1.0 이하로 복귀하면 종료 후보
  max_hold_s: 180      # 안전장치: 구간 최대 길이(초)
```

## Phase 2 — 실행 가능성 가드(체결성/슬리피지) + 정책 훅

**목적**: 알람이 떠도 **체결할 수 있어야** 의미 있음. 한국시장 특수(틱/스프레드/심도/MM) 반영.

* **체커**

  * **Liquidity**: `spread ≤ θ_spread`, `depth_bid1/ask1 ≥ θ_qty`, (선택) MM 여부 가중.
  * **슬리피지 추정**: `α*spread + β/(depth)` 보수 추정, 한도 초과 시 **보류/부분체결 정책**.
* **정책 훅**

  * `enter/skip/defer/scale/exit` 의사결정 **로깅만**(MVP는 실제 주문 없이도 OK).
* **산출물**

  * `event_store/action_log.parquet`(체커 통과율, 보류 사유),
  * `reports/execution_readiness.json`.
* **확정 아님**

  * α,β, 한계치(종목·세션별)는 **Phase 3 스윕**으로 조정.

---

## Phase 3 — 랭킹 & 튜닝(47지표/CPD 파라미터) + 스윕

**목적**: 47개 중 **상위 지표/가중치/윈도우/임계**를 **데이터로 채택**(고정 아님).

* **피처 랭킹**

  * EDA(급등구간 vs 평시 분포 차이: KS/Cliff’s δ),
  * 단변량 AUC/효과크기, L1-Logit/GBT **Stability Selection**(부트스트랩) → **Top-k** 제안.
* **스윕(그리드/베이지안)**

  * 숏윈도우(30/60/90/120/180s), 롱윈도우(10/15/20/30/45/60m), 임계(p90–p98),
  * 불응(60–180s), 확인창(10/20/30s), 가중치(wS/wP/wF),
  * **CPD 파라미터**: CUSUM(k,h), Page–Hinkley(delta, lambda), `min_pre_s`, `cooldown_s`.
* **평가 메트릭**

  * **In-window 탐지율**, **FP/h**, **TTA p95**, **Precision\@alert**,
  * **체결성 통과율**(Phase 2), (선택) 보수적 PnL.
* **산출물**

  * `reports/tuning_summary.json`, `config/onset_best.yaml`(추천 설정), 비교 플롯.
* **확정 아님**

  * 상위 지표·가중치는 **데이터 따라 바뀜**(고정 X).

---

## Phase 4 — 온라인 준비(키움) & Go/No-Go **(Post-Overview: Modify 범위 아님)**

**목적**: **키움 실시간**으로 **동일 논리**가 돈다는 걸 검증. 운영 안전장치 확인.

* **키움 어댑터 연결**

  * CSV 리플레이와 **필드/시계/정렬/타임존 동등성 테스트**(동일 입력 → 동일 의사결정).
* **SLA/안전장치**

  * **Confirm p95 ≤ 2s**(틱 인입→확정 기록), 재연결·백프레셔, 설정 핫스왑/롤백, 로그/모니터링.
* **Go/No-Go 기준(예시)**

  * 사용자 지정 **두 급등 구간 내 ≥1건** 탐지, 구간 밖 **FP/h ≤ N**,
  * **체결성 통과율 ≥ X%**, **TTA p95 ≤ Y초**.
* **산출물**

  * `reports/online_parity.json`, `reports/go_nogo_summary.json`.

---

### 부록 — 이후(선택) Phase

* **(P5) 온셋 후 분석**: 강도/타입/패턴 스냅샷(47지표 풀活용), 간이 클러스터 태깅 → 전략 맵.
* **(P6) 백테스트 고도화**: 슬리피지·체결확률 모델 정교화, 정책 최적화.
* **(P7) 운영 견고화**: 경보 피로 관리, 대시보드, 회귀/스모크 자동화, 버전 롤백.

---

## 전체 원칙(공통)

* **미래 미사용(누출 금지)**, **세션별 적응 임계**, **CPD→후보→확인→불응 4단계(ML 필터 결합)**,
* **지표·윈도우·임계는 고정값 아님**(Phase 3에서 데이터로 채택),
* **CSV 리플레이 = 키움 실시간 동형성** 확보가 MVP의 생명.

> 위 구조로 가면 “확정 안 된 요소는 Phase 3에서 데이터로 결정”하되,
> **Phase 1–2만으로도** 실전형 MVP가 **즉시 작동**합니다.

====================================================================================
좋아, **Phase 0\~4**를 “검증 체크리스트 중심”으로 정리했어.
현재 **지표 36개** → **47개(추가 11개)** 확장 및 **시계열/슬라이딩 윈도우(스트리밍)** 반영 필요사항도 각 Phase에 녹였어.
(코드는 다음 단계에서—여긴 **검증 포인트/통과 기준/산출물** 위주)

---

# ✅ Phase 0 — 베이스라인 & 동형성(Parity) 확보

**목적**: 오프라인(CSV 리플레이)와 온라인(키움 실시간)이 **동일한 입력/출력 계약**과 **동일한 의사결정**을 보장.

### 검증 항목

1. **타임존·정렬**

   * KST tz-aware, `ts` 오름차순, ms 정밀 유지.
   * 정규장 마스크(09:00–15:30) 적용 확인.
   * **통과 기준**: 잘린 구간(임의 시작점)에서도 동일 결과(누출 없음).
2. **최소 스키마 & NaN**

   * 필수: `ts,last,vol,bid1,ask1,bid_qty1,ask_qty1` 존재/유효.
   * 결측/이상치 처리 규칙 로그 기록.
   * **통과 기준**: 필수 컬럼 결측 0%, 이상치 플래그링 보고.
3. **리플레이 스트리밍 엔진**

   * **1틱 순차 처리** → **1초 리샘플 스트림** 생성(미래 미사용).
   * 중간 재시작(임의 오프셋) = 동일 결과.
   * **통과 기준**: 오프셋 바꿔도 동일 알람/결과.
4. **36→47 지표 확장(추가 11개) 준비**

   * 추가 11개는 **기존 컬럼으로 계산 가능**해야 함(예: `ticks_per_sec`, `inter_trade_time`, `spread_narrowing`, `microprice_momentum`, `z_ofi_1s(근사 가능)`, `up_tape_ratio`, `imbalance_1s`, `ret_accel(Δret_1s)` 등).
   * 계산은 **슬라이딩 윈도우 기반**(미래 미사용).
   * **통과 기준**: 47개 모두 시점 t에서 t까지의 정보만으로 산출.

### 산출물

* `reports/parity_smoketest.json` (타임존/리플레이/누출 테스트 결과)
* `metadata/versions.json` (config\_hash 포함)
* 샘플 플롯(가격·체결량·스프레드)

---

# ✅ Phase 1 — 온셋 탐지 엔진 v2 (후보→확인→불응)

**목적**: **“가능한 빠르되, 충분한 증거로 안전하게”** 급등 상태로 넘어가는 **상황**을 포착.

### 검증 항목

1. **스트리밍 피처(초단위) 계산**

   * Speed: `ret_1s`, `Δret_1s(=ret_accel)`, (선택) 1초 캔들 바디/윅 비율
   * Participation: `z_vol_1s`, `ticks_per_sec`, `inter_trade_time↓`, `up_tape_ratio`, (가능시) `OFI_1s`
   * Friction: `spread`, `spread_narrowing`, `bid_ask_imbalance`, `micro_price_momentum`
   * **통과 기준**: 47개 중 **MVP 핵심 6\~8개**가 안정적으로 계산(누출 X)
2. **표준화 & 세션 적응**

   * 롱/숏 롤링(MAD-z 권장, 길이는 Phase 3에서 스윕), 오전/점심/오후 **퍼센타일 임계 분리**
   * **통과 기준**: 세션 경계(점심 시간대)에서 임계 리셋/적응 정상
3. **탐지 로직**

   * 후보: `S_t = wS*Speed + wP*Participation + wF*Friction` ≥ **세션별 p-임계**
     (+옵션) 단측 CUSUM(S\_t) > h (지속적 양(+) 드리프트)
   * 확인(확정): **확인창**(예: 10–30s)에서 **상대 개선(Δ) 기반 + 가격 축 필수 + earliest-hit + `persistent_n` 연속성**
   * 불응: 60–180s(가변)
   * **통과 기준**: 사용자 지정 **급등 2구간(09:55–09:56, 10:26–10:28) 내 ≥1건**, 구간 밖 FP ≤ N(임시 기준)
4. **누출·중복 방지**

   * 후보→확정→불응 **상태기계** 동작 로그 검증
   * **통과 기준**: 동일 사이클 중복알람 없음

### 산출물

* `event_store/onsets.parquet` (후보/확정/불응, 임계/가중치 메타 포함)
* `reports/onset_quality.json` (Alert/h, in-window 탐지율, FP/h, TTA p95)
* 플롯(가격 + 후보/확정 마커)

---

# ✅ Phase 2 — 실행 가능성 가드(체결성/슬리피지) + 정책 훅

**목적**: 알람이 떠도 **체결 가능**해야 의미가 있음(한국시장 특수 반영).

### 검증 항목

1. **체결성 체크**

   * `spread ≤ θ_spread`, `depth_bid1/ask1 ≥ θ_qty`, (선택) MM 여부 가중
   * **통과 기준**: 온셋 확정 중 **체커 통과율 ≥ X%** (임시 X=70% 등)
2. **슬리피지 추정**

   * `slippage_est = α*spread + β/(depth)` 보수 추정
   * **통과 기준**: 알람 중 과도 슬리피지 예상 비율 ≤ Y% (임시 Y=20% 등)
3. **정책 훅/로깅**

   * `enter/skip/defer/scale/exit` 판단은 **로깅**만(MVP 단계)
   * **통과 기준**: 스킵/보류 사유가 일관된 규칙에 의해 기록

### 산출물

* `event_store/action_log.parquet` (체커 결과, 슬리피지 추정, 의사결정)
* `reports/execution_readiness.json` (체결성 통과율, 스킵 사유 통계)

---

# ✅ Phase 3 — 랭킹 & 튜닝(36→47, 윈도우/임계/가중치 스윕)

**목적**: **고정값 아님**. 36→47 확장과 함께 **데이터로 상위 지표/파라미터를 선택**.

### 검증 항목

1. **36→47 지표 확장 검증**

   * 추가 11개가 **기존 컬럼만으로 시점 t에서 계산**되는지(미래 미사용)
   * **통과 기준**: 47개 전부 누락/NaN 0%, 계산 지연 없이 스트리밍 가능
2. **피처 랭킹/안정성 선택**

   * 급등 구간 vs 평시: KS, Cliff’s δ, 단변량 AUC/효과크기
   * L1-Logit/GBT + 부트스트랩 **Stability Selection** → **Top-k** 추천
   * **통과 기준**: 반복 샘플링에서 Top-k의 **선정 안정성 ≥ Z%**(임시 Z=70% 등)
3. **스윕(그리드/베이지안)**

   * 롱/숏 윈도우 후보(예: 10–60m / 30–180s), 임계 p90–p98, 확인창 10/20/30s, 불응 60–180s, 가중치(wS/wP/wF), CUSUM(k,h)
   * **통과 기준**:
     - in-window 탐지율↑, FP/h↓, **TTA p95 ≤ 2초**, 체결성 통과율 유지/개선
     - 전일/타일에서도 **성능 붕괴 없음**(간단 OOS 확인)
4. **노이즈 라벨·정책 보정**

   * 확정 후 60–120s 내 반납 이벤트 태깅 → 임계/확인창 자동 상향 제안
   * **통과 기준**: 노이즈 비중 하락(전/후 비교)

### 산출물

* `reports/tuning_summary.json` (Top-k 지표, 최적 파라미터, 전/후 비교)
* `config/onset_best.yaml` (추천 설정 세트)
* 비교 플롯/테이블

---

# ✅ Phase 4 — 온라인(키움) 동작 검증 & Go/No-Go

**목적**: **CSV 리플레이 = 키움 실시간** 의사결정 동형성 확인 + 운영 안전장치.

### 검증 항목

1. **동형성 테스트**

   * 동일 종목·동일 시각 범위: 리플레이 vs 키움 스트림 → **동일 알람/결정**
   * 재연결/백프레셔/결측 틱 처리를 포함
   * **통과 기준**: 이벤트 타임스탬프/개수/결정이 허용 오차 내 동일
2. **SLA/지연**: Confirm p95 ≤ **2초**(틱 인입→확정 기록)
**통과 기준**: p95 목표 충족, 피크 타임 안정성 확인
3. **Go/No-Go**

* 사용자 급등 2구간 내 ≥ 1건, 구간 밖 **FP/h ≤ 1**
* **체결성 통과율 ≥ 70%**, **TTA p95 ≤ 2초**
   * **통과 기준**: 사전 합의 KPI 달성

### 산출물

* `reports/online_parity.json`
* `reports/go_nogo_summary.json`

---

## 🧩 보조 체크(공통)
- **누출 테스트**: 파일 임의 시점에서 잘라 재실행 → 동일 결과
- **설정 주도형**: 모든 임계/윈도우/불응/확인창/가중치가 `config/*.yaml`에서만 변경
- **버전화**: `config_hash`를 이벤트/리포트에 주입 (CPD 파라미터 포함)
- **플롯**: 가격 + 후보/확정 마커, 체결성 상태 오버레이

---

## 📌 정리 — 36 → 47 지표 확장 요령

* **추가 11개**는 **현 보유 컬럼**으로 **시점 t까지** 계산(미래 미사용).
* 추천 후보(예시):

  * `ticks_per_sec`, `inter_trade_time`, `spread_narrowing`, `microprice_momentum`,
  * `imbalance_1s(잔량 불균형 초평균)`, `up_tape_ratio`, `OFI_1s(근사 가능)`, `ret_accel(Δret_1s)`
* **Phase 1**에선 **핵심 6\~8개**로 탐지 엔진 가동 → **Phase 3**에서 47개로 랭킹·교체.
* 모든 계산은 **슬라이딩 윈도우**(롱/숏) 기반 & **스트리밍 누출 금지**.

---

원하면, 위 체크리스트를 **vscode에게 그대로 실행 지시**할 수 있게 “체크 항목 → 명령/출력 파일명”까지 붙인 버전으로 다듬어줄게.
