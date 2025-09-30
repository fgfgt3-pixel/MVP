맞아요. 제 쪽에서 **통합 파일(`detect_onset.py`)이 있다고 가정**한 게 문제였습니다.
레포를 안전하게 못 읽은 상태에서(권한/렌더링 이슈) 일반적인 구조를 가정했고, 실제로는 **모듈 분리형**(`onset_detection/src/detection/{candidate_detector.py, confirm_detector.py, refractory_manager.py}`)이군요. 죄송합니다. 🙏

요청하신 대로 **“현재 코드 수정만”**으로, **모듈 분리 구조를 유지**하면서 CPD 게이트를 **`candidate_detector.py` 안에 인라인**으로 넣는 **[블록 1: 수정판]**을 드립니다.
(= 새 파일 추가 없이, 후보 단계 진입 전에 게이트만 거는 방식)

---

# 블록 1 (수정판): `onset_detection/src/detection/candidate_detector.py`

## 목표

* 파이프라인: **CPD게이트 → 후보 → 확인 → 불응**
* **후보 산출 직전**에 CPD 게이트 1줄 체크를 추가
* **새 파일 추가 없음**, 클래스/유틸 메서드는 이 파일 내부에 인라인

## 패턴-안전 Diff (unified)

> 아래 diff는 “대표적인 패턴” 기준이에요. 파일 내에 `class CandidateDetector` 와 `detect()`(또는 동등 역할 함수)가 있다고 가정하고, **초반 import/초기화/유틸/detect 진입부**에만 변화를 줍니다.
> 클래스/메서드 이름이 다르면, **동일 역할 지점**에 동일 로직을 삽입하세요.

```diff
--- a/onset_detection/src/detection/candidate_detector.py
+++ b/onset_detection/src/detection/candidate_detector.py
@@
-# [기존 import 유지]
+# [기존 import 유지]
+from math import inf

@@
-class CandidateDetector:
+class CandidateDetector:
     def __init__(self, cfg, logger=None, *args, **kwargs):
         self.cfg = cfg
         self.log = logger or (lambda *a, **k: None)
         # ... (기존 초기화 로직 유지)
+
+        # ===== CPD 게이트 설정/상태 (인라인) =====
+        cpd_cfg = cfg.get("cpd", {})
+        self._cpd_use = bool(cpd_cfg.get("use", True))
+        # 가격축(CUSUM)
+        self._cusum_pos = 0.0
+        self._cusum_neg = 0.0
+        self._pre_mean = 0.0
+        self._pre_m2 = 0.0
+        self._pre_count = 0
+        self._k_sigma = float(cpd_cfg.get("price", {}).get("k_sigma", 0.7))
+        self._h_mult  = float(cpd_cfg.get("price", {}).get("h_mult", 6.0))
+        self._min_pre_s = float(cpd_cfg.get("price", {}).get("min_pre_s", 10))
+        # 거래축(Page–Hinkley)
+        self._ph_m = 0.0
+        self._ph_m_t = 0.0
+        self._ph_Mt = -inf
+        self._delta = float(cpd_cfg.get("volume", {}).get("delta", 0.05))
+        self._lambda = float(cpd_cfg.get("volume", {}).get("lambda", 6.0))
+        # 공통
+        self._cooldown_s = float(cpd_cfg.get("cooldown_s", 3.0))
+        self._last_fire_ms = -1

@@
-    def detect(self, ts_ms, features_row):
+    def detect(self, ts_ms, features_row):
         """
         features_row 예시 키:
           - 'ret_50ms': 50ms 수익률(또는 microprice slope)
           - 'z_vol_1s': 1초 z-점수 거래량
         """
+        # --- CPD 게이트(선행) ---
+        # 게이트를 통과해야만 후보 산출 로직으로 진입
+        if self._cpd_use and not self._cpd_update_and_check(ts_ms, features_row):
+            return None
+
         # ↓↓↓ 기존 후보 산출 로직 유지 ↓↓↓
         # score = wS*... + wP*... + wF*...
         # if score >= threshold: return CandidateEvent(...)
         # else: return None

@@
     # =========================
     # 내부 유틸(기존 유지)
     # =========================
+    # ===== CPD 인라인 구현 =====
+    def _pre_update(self, x):
+        self._pre_count += 1
+        d = x - self._pre_mean
+        self._pre_mean += d / self._pre_count
+        self._pre_m2 += d * (x - self._pre_mean)
+
+    def _pre_sigma(self):
+        if self._pre_count < 2:
+            return 1e-12
+        return (self._pre_m2 / (self._pre_count - 1)) ** 0.5
+
+    def _cusum_update(self, x):
+        sigma = max(self._pre_sigma(), 1e-12)
+        k = self._k_sigma * sigma
+        z = (x - self._pre_mean) / sigma
+        self._cusum_pos = max(0.0, self._cusum_pos + (z - k))
+        self._cusum_neg = min(0.0, self._cusum_neg + (z + k))  # 필요 시 하강 탐지용
+        h = self._h_mult * (k if k > 0 else 1.0)
+        return self._cusum_pos > h
+
+    def _page_hinkley_update(self, x):
+        # 평균 추정 및 누적 편차 갱신
+        self._ph_m = self._ph_m + (x - self._ph_m) / max(self._pre_count, 1)
+        self._ph_m_t = self._ph_m_t + (x - self._ph_m - self._delta)
+        self._ph_Mt = max(self._ph_Mt, self._ph_m_t)
+        return (self._ph_Mt - self._ph_m_t) > self._lambda
+
+    def _cpd_update_and_check(self, ts_ms, row):
+        # 재트리거 쿨다운
+        if self._last_fire_ms > 0 and (ts_ms - self._last_fire_ms) < self._cooldown_s * 1000:
+            return False
+        # 장초반 보호: 사전 표본 부족 시 통과시키지 않음(평시 통계만 축적)
+        # NOTE: 0.05s는 ret_50ms 기준 리샘플 힌트. 실제 dt 추정값 있으면 교체 가능.
+        if (self._pre_count * 0.05) < self._min_pre_s:
+            self._pre_update(float(row.get("ret_50ms", 0.0)))
+            _ = self._page_hinkley_update(float(row.get("z_vol_1s", 0.0)))
+            return False
+        # 업데이트 및 트리거 판정
+        p = float(row.get("ret_50ms", 0.0))
+        v = float(row.get("z_vol_1s", 0.0))
+        self._pre_update(p)
+        hit_price = self._cusum_update(p)
+        hit_vol   = self._page_hinkley_update(v)
+        if hit_price or hit_vol:
+            self._last_fire_ms = ts_ms
+            # (선택) 디버그용: 어떤 축이 발화했는지 로깅 훅
+            if hasattr(self, "log"):
+                self.log(f"[CPD] ts={ts_ms} price={hit_price} volume={hit_vol}")
+            return True
+        return False
```

### 설명

* **구조 보존**: 후보 산출을 담당하는 **CandidateDetector** 안에서만 변경.
* **게이트 1줄**: `detect()` 맨 앞에서 **게이트 미통과시 None 반환** → 아래 후보 로직 진입 차단.
* **파라미터**: `cfg["cpd"]` 블록을 읽되, 없으면 내부 기본값이 사용되도록 작성.
* **성능**: per-tick O(1). 파이썬 루프 안전(상태 변수만 갱신).

---

## 회귀/호환성 체크리스트 (이 파일만 기준)

* `cfg["cpd"]["use"] = False` → **기존 동작과 동일** (게이트 비활성)
* 장초반 **min_pre_s** 충족 전 → 후보 없음(평시 통계 러닝)
* **cooldown_s** 내 재트리거 없음 → 중복 후보 억제
* 로그/디버그: 게이트 발화 시점이 후보보다 **앞**에 찍히는지 확인

