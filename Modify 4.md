확인해 본 결과, **Step overal.md** 상에서 Phase 1 정의가 이미 존재하고 있으며, 그 안에 후보→확인→불응 3단계 흐름이 기록되어 있습니다. 따라서 CPD 게이트를 반영하려면 이 Phase 1에 새로운 Step을 추가해야 합니다.

---

## 제안: Block 4 (Step overal.md 수정)

### 변경 포인트

1. **Phase 1 — 온셋 탐지(룰 기반)** 서두에
   기존 “총 5 Steps” → “총 6 Steps”로 수정.
2. **Step 1-3** (온셋 스코어 & 후보 트리거) 앞에 **Step 1-2.5 (CPD 게이트)**를 신설.

   * 내용: 온라인 변화점 탐지(CUSUM, Page-Hinkley)로 **평시→급등 전환 게이트** 설정.
   * 산출물: `cpd_trigger` 플래그, 로그 기록.
   * 완료 기준: 장초반/드리프트 상황에서 오경보 차단, FP/h 개선.
3. 이후 Step 번호 전부 +1씩 밀림 (1-3 → 1-4, 1-4 → 1-5 …).

---

### Diff 가이드 (Step overal.md)

```diff
- # Phase 1 — 온셋 탐지(룰 기반) (총 5 Steps)
+ # Phase 1 — 온셋 탐지(룰 기반) (총 6 Steps)

@@
- **Step 1-2 | 세션 퍼센타일 임계(p95±) 계산**
+ **Step 1-2 | 세션 퍼센타일 임계(p95±) 계산**
+
+ **Step 1-2.5 | CPD 게이트 (Change Point Detection)**
+ * 작업: `src/cpd/online_cusum.py`, `src/cpd/page_hinkley.py` 활용.
+   - 입력: `ret_50ms`(가격축), `z_vol_1s`(거래축).
+   - 방법: CUSUM(k,h), Page-Hinkley(δ,λ) → 평시 대비 상태변화 탐지.
+ * 산출물: 이벤트에 `cpd_trigger` 필드 추가, 로그 기록.
+ * 완료 기준:
+   - 장 초반 Pre 데이터 부족 시 skip.
+   - 오경보↓, 탐지율 유지, FP/h 개선 수치 리포트 포함.

- **Step 1-3 | 온셋 스코어 & 후보 트리거**
+ **Step 1-4 | 온셋 스코어 & 후보 트리거**

- **Step 1-4 | 확인창 확정**
+ **Step 1-5 | 확인창 확정**

- **Step 1-5 | 불응 FSM**
+ **Step 1-6 | 불응 FSM**
```

---

### 충돌/주의사항

* **번호 변경**: Phase 1의 Step 전체 번호가 하나씩 밀리므로, 이후 Phase 문서에서 이 Step을 참조하는 경우 동기화 필요.
* **산출물 경로**: `reports/` 산출물 파일명 충돌 없음 (신규 `cpd_trigger` 로그만 추가).
* **실행 스크립트 영향**: `scripts/step03_detect.py`가 이 CPD 모듈을 호출해야 하므로, Step 정의와 코드 수정이 반드시 짝을 이뤄야 함.

---

👉 이렇게 하면 Step overal.md 상에서 Phase 1이 **CPD 게이트 → 후보 → 확인 → 불응**으로 확장됩니다.
