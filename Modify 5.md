좋습니다 👍 이제 마지막 **Block 5** 제안 드리겠습니다.
Block 5는 전체 정리 단계로, **Project overal.md** 수정 + **실행 엔트리(블록 3 대체 경로)** 문제까지 포함해서 “문서와 코드/실행 경로 불일치”를 해결하는 것이 목적입니다.

---

# 🔧 Block 5: Project overal.md + 실행 엔트리 정합화

## 🎯 변경 목적

1. **Project overal.md** (최상위 개념 문서)에 **온셋 탐지 방식**을 최신 구조(4단계)로 명확히 기록

   * 기존: 후보→확인→불응
   * 변경: CPD게이트→후보→확인→불응 (+ ML 필터)
   * 문서와 코드/Step 정의 간 불일치 제거

2. **실행 엔트리 파일 문제 해결**

   * `scripts/step03_detect.py`가 존재하지 않는 상태 → 실제 실행 루트 파일(예: `Step/Phase1_runner.py`, `scripts/run_phase1.py`, 혹은 노트북)이 CPD를 호출해야 함.
   * 따라서 Project overal.md에 “실행 엔트리 위치 및 CPD 호출 방식”을 명시해야 혼선 방지 가능.

---

## 📑 Diff 제안 (Project overal.md)

```diff
--- a/Project overal.md
+++ b/Project overal.md
@@
- ## Phase 1 — 온셋 탐지 파이프라인
- 기존 3단계 구조: 후보 → 확인 → 불응
-
- * 후보: 세션 퍼센타일 기반(p-임계)
- * 확인: Δ-축 + 가격축 필수 + 지속성 조건
- * 불응: FSM으로 재트리거 억제
+ ## Phase 1 — 온셋 탐지 파이프라인
+ **최신 4단계 구조**: CPD게이트 → 후보 → 확인 → 불응 (+ ML 필터)
+
+ * **CPD 게이트**: 온라인 CUSUM(가격축), Page–Hinkley(거래축) 기반.  
+   - 입력: `ret_50ms`, `z_vol_1s`  
+   - 운영 상수: `min_pre_s`, `cooldown_s`  
+   - 산출물: `cpd_trigger` 플래그, 로그
+ * **후보**: 세션 퍼센타일 기반(p-임계) → candidate 이벤트 생성
+ * **확인**: Δ-축 + 가격축 필수 + earliest-hit + 지속성 조건
+ * **불응**: FSM으로 재트리거 억제
+ * (선택) ML 필터: onset_strength ≥ θ_ml
+
+ ⚠️ 주의: CPD 단계가 비활성(use=false)일 경우 기존 3단계 구조와 동일하게 동작
```

---

## 🛠️ 실행 엔트리 문제 해결 가이드

1. **실행 루트 위치 확인**

   * 현재 `scripts/step03_detect.py`는 없음 → 실제 Phase 1 실행은

     * `Step/Step1_xxx.py`, 또는
     * `scripts/run_phase1.py`, 혹은
     * 노트북(`notebooks/phase1.ipynb`)일 가능성이 높음.

2. **수정 포인트**

   * CandidateDetector를 호출하기 전에 `cpd_gate.should_pass(row)` 체크가 반드시 들어가야 함.
   * Project overal.md 문서에 다음과 같이 명시:

     ````md
     ### 실행 엔트리
     * Phase 1 실행 엔트리는 현재 `scripts/` 또는 `Step/` 폴더 내 실행 스크립트에 따라 상이할 수 있음.
     * 후보 산출 전 `CPDGate` 호출이 필수:
       ```python
       if cpd.should_pass(row):
           candidate = cand.update(row)
     ````

     * CPD 블록이 비활성(use=false)일 경우 → 무조건 통과(True 반환)

     ```
     ```

3. **테스트/지표 반영**

   * FP/h, TTA p95 계산 시, **CPD 필터링 후의 이벤트 수**를 기준으로 한다고 Project overal.md에 기록.
   * 이렇게 해야 연구/튜닝 단계에서 혼선이 없습니다.

---

## ⚠️ 충돌/주의사항

* 문서 상에는 CPD를 **별도 모듈(cpd/online_cusum.py)**로 나눈다고 되어 있지만, 실제 구현은 CandidateDetector 인라인.

  * **선택지**:

    1. 문서에서 “인라인 구현으로 통합”이라고 갱신
    2. 또는 코드 리팩토링 시 별도 모듈 분리
  * 현재는 ①번(문서 갱신)이 더 안전합니다.

* 실행 엔트리가 `scripts/step03_detect.py`가 아닌 다른 파일일 수 있으므로, Project overal.md에는 **“구체 파일명은 다를 수 있음, 공통 규칙은 CPD 선행 호출”**로 명시하는 것이 바람직합니다.

---

## ✅ Block 5 결론

1. **Project overal.md 업데이트** → 최신 4단계 구조 기록
2. **실행 엔트리 규칙 명시** → CPD 호출 선행 보장
3. **문서 vs 코드 일치화** → 현재는 CandidateDetector 인라인 구현 기준으로 정리

