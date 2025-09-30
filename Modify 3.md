좋습니다 👍 블록 3는 **Phase 1 실행 스크립트(`scripts/step03_detect.py`) 수정** 단계예요.
현재 구조상 이 스크립트는 후보→확인→불응 상태기계를 실행하는 메인 엔트리입니다. 여기에 **CPD 게이트**를 배선하는 변경이 필요합니다.

---

# 🔧 블록 3: `scripts/step03_detect.py` 수정

## 🎯 변경 목적

* 후보 단계 **이전**에 CPD 게이트 검사를 삽입
* `config["cpd"]` 설정을 불러와 `CPDGate`를 초기화
* CPD가 꺼져 있으면 기존과 동일하게 동작(레거시 호환 보장)

---

## 📑 Diff 제안 (패턴 기반)

```diff
--- a/scripts/step03_detect.py
+++ b/scripts/step03_detect.py
@@
 from src.config_loader import load_config
 from src.features_core import FeatureCalculator
 from src.detect_onset import CandidateDetector, ConfirmDetector, RefractoryManager
+from src.detect_onset import CPDGate
@@
 def main(cfg_path: str, csv_path: str):
     cfg = load_config(cfg_path)
     features = FeatureCalculator(cfg)
-    cand = CandidateDetector(cfg)
+    # --- CPD 게이트 추가 ---
+    cpd = CPDGate(cfg.get("cpd", {}))
+    cand = CandidateDetector(cfg)
     conf = ConfirmDetector(cfg)
     refr = RefractoryManager(cfg)
@@
     for row in features.run(csv_path):
-        if cand.update(row):
-            if conf.update(row):
-                event = refr.update(row)
-                if event:
-                    log_event(event)
+        # ① CPD 게이트 확인
+        if cpd.should_pass(row):
+            # ② 후보 → 확인 → 불응 순차 실행
+            if cand.update(row):
+                if conf.update(row):
+                    event = refr.update(row)
+                    if event:
+                        log_event(event)
```

---

## 🛠️ 수정 가이드

1. **임포트**

   * `CPDGate`를 `src/detect_onset.py` 또는 `src/detection/cpd_gate.py`에 구현해두고 불러옵니다.

2. **초기화**

   * `cfg.get("cpd", {})`로 안전하게 로딩 (없으면 빈 dict → 비활성).

3. **실행 흐름**

   * 기존 로직(`cand→conf→refr`) 앞에 `if cpd.should_pass(row):` 추가.
   * CPD가 off이거나 조건 불충족이면 → 후보 탐지 skip.

4. **호환성**

   * `cpd.use=false`일 때는 항상 True 반환 → 기존 코드 그대로 동작.

---

## ⚠️ 주의사항

* `log_event(event)` 부분은 그대로 유지. CPD 통과 여부 자체도 이벤트로 남기고 싶다면 `row["cpd_trigger"]` 같은 필드를 추가할 수 있음.
* `CPDGate`가 내부적으로 가격/거래 축 입력(`ret_50ms`, `z_vol_1s`)을 필요로 하므로 `features.run()`이 해당 피처를 제공하는지 확인 필요.
* Phase 1 단계 순서 문서(`Step overal.md`)도 **Step 1-0 (CPD 게이트)**를 추가해야 일관성 유지됨 → 블록 4에서 다룸.


