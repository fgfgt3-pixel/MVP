
* **기존 44개 지표**: 기술적 지표(11) + 호가데이터(8) + 호가수량(8) + 고급지표(6) + 기본컬럼(11쯤 포함).
* **새로 확인된 47개 지표**: 기존 44개는 그대로 포함하면서, 추가 계산 중 **衍生 지표 3개**가 더 붙은 상태예요.
  → 보통은 슬라이딩 윈도우, Δ(변화율), 혹은 조합 지표가 자동으로 추가되면서 컬럼 수가 늘어납니다.
  → 실제로 이번 csv 헤더를 보면 `inter_trade_time`, `imbalance_1s`, `OFI_1s` 같은 컬럼이 새롭게 붙은 걸로 보입니다.

---

## 2. 문제 없는가?

* **문제 없음**: 기존 44개를 모두 포함하면서, 추가된 3개가 새롭게 들어온 상황.
* 단, 중요한 건 “코드/설계 문서(Project_root.md, Step overal.md 등)”와 실제 csv의 컬럼 수가 불일치할 수 있다는 점이에요.

  * 문서에는 44개 기준으로 적혀 있는데, 실제 데이터는 47개 → 혼동 위험.
  * ML 학습 시 feature importance 계산 시에 "예상치 못한 컬럼"으로 경고 나올 수 있음.

---

## 3. 권장 방향

1. **문서 업데이트**

   * Project_root.md, Step overal.md에 “총 47개 지표(기존 44 + 신규 3)”로 업데이트 필요.
   * 신규 3개를 명확히 표기: `inter_trade_time`, `imbalance_1s`, `OFI_1s`.

2. **코드 영향 점검**

   * `src/prep.py` 또는 feature 생성 모듈에서 hard-coded feature list(44개 고정)로 되어있다면 수정 필요.
   * 자동으로 `df.columns`에서 feature 추출하는 구조라면 그대로 둬도 문제 없음.

3. **학습/백테스트 영향**

   * 지표가 늘어난 건 긍정적이에요 → 더 풍부한 신호.
   * 다만 기존 모델과 결과 비교할 때 “44 vs 47 지표” 차이를 기록해야 추적 가능.

---

✅ **정리 결론**

* 큰 문제 없음 → 47개 지표로 진행해도 됩니다.
* 다만 문서와 코드에서 “44개”라고 고정된 부분은 반드시 업데이트해야 합니다.
* 신규 3개는 온셋 탐지에서 중요한 후보 지표가 될 수 있으므로 유지 권장.

---

최종 47개 지표 내역
time stock_code current_price volume ma5 rsi14 disparity stoch_k stoch_d vol_ratio z_vol obv_delta spread bid_ask_imbalance accel_delta ret_1s ask1 ask2 ask3 ask4 ask5 bid1 bid2 bid3 bid4 bid5 ask1_qty ask2_qty ask3_qty ask4_qty ask5_qty bid1_qty bid2_qty bid3_qty bid4_qty bid5_qty z_vol_1s mid_price ticks_per_sec inter_trade_time microprice microprice_slope up_tape_ratio imbalance_1s spread_narrowing OFI_1s ret_accel