# 수정사항 제안 (Diff 형식)

## Block 1: config_loader.py - ConfirmConfig 기본값 수정

```diff
--- onset_detection/src/config_loader.py
+++ onset_detection/src/config_loader.py

@@ -88,9 +88,9 @@ class SegmenterConfig(BaseModel):
 
 class ConfirmConfig(BaseModel):
     """Confirmation configuration."""
-    window_s: int = Field(default=18)
+    window_s: int = Field(default=12)
     min_axes: int = Field(default=1)
     vol_z_min: float = Field(default=1.0)
     spread_max: float = Field(default=0.03)
-    persistent_n: int = Field(default=2)
+    persistent_n: int = Field(default=38)
     exclude_cand_point: bool = Field(default=True)
+    require_price_axis: bool = Field(default=True)
+    pre_window_s: int = Field(default=5)
+
+
+class ConfirmDeltaConfig(BaseModel):
+    """Confirmation delta thresholds."""
+    ret_min: float = Field(default=0.0001)
+    zvol_min: float = Field(default=0.1)
+    spread_drop: float = Field(default=0.0001)
```

---

## Block 2: config_loader.py - OnsetConfig 기본값 및 중첩 구조 추가

```diff
--- onset_detection/src/config_loader.py
+++ onset_detection/src/config_loader.py

@@ -36,11 +36,29 @@ class ThresholdsConfig(BaseModel):
     min_return_pct: float = Field(default=0.005)
 
 
+class SpeedConfig(BaseModel):
+    """Speed axis configuration."""
+    ret_1s_threshold: float = Field(default=0.0008)
+
+
+class ParticipationConfig(BaseModel):
+    """Participation axis configuration."""
+    z_vol_threshold: float = Field(default=2.0)
+
+
+class FrictionConfig(BaseModel):
+    """Friction axis configuration."""
+    spread_narrowing_pct: float = Field(default=0.75)
+
+
 class OnsetConfig(BaseModel):
     """Onset detection configuration model."""
-    refractory_s: int = Field(default=120)
-    confirm_window_s: int = Field(default=20)
+    refractory_s: int = Field(default=20)
+    confirm_window_s: int = Field(default=12)
     score_threshold: float = Field(default=2.0)
     weights: WeightsConfig = Field(default_factory=WeightsConfig)
     thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
+    speed: SpeedConfig = Field(default_factory=SpeedConfig)
+    participation: ParticipationConfig = Field(default_factory=ParticipationConfig)
+    friction: FrictionConfig = Field(default_factory=FrictionConfig)
```

---

## Block 3: config_loader.py - DetectionConfig에 min_axes_required 추가

```diff
--- onset_detection/src/config_loader.py
+++ onset_detection/src/config_loader.py

@@ -78,6 +78,7 @@ class DetectionConfig(BaseModel):
     score_threshold: float = Field(default=2.0)
     vol_z_min: float = Field(default=2.0)
     ticks_min: int = Field(default=2)
+    min_axes_required: int = Field(default=2)
     weights: Dict[str, float] = Field(default_factory=lambda: {
         "ret": 1.0,
         "accel": 1.0,
```

---

## Block 4: config_loader.py - ConfirmConfig delta 필드 추가

```diff
--- onset_detection/src/config_loader.py
+++ onset_detection/src/config_loader.py

@@ -95,6 +107,7 @@ class ConfirmConfig(BaseModel):
     persistent_n: int = Field(default=38)
     exclude_cand_point: bool = Field(default=True)
+    delta: ConfirmDeltaConfig = Field(default_factory=ConfirmDeltaConfig)
```

---

## Block 5: config_loader.py - RefractoryConfig 기본값 수정

```diff
--- onset_detection/src/config_loader.py
+++ onset_detection/src/config_loader.py

@@ -99,7 +112,7 @@ class ConfirmConfig(BaseModel):
 
 class RefractoryConfig(BaseModel):
     """Refractory configuration."""
-    duration_s: int = Field(default=120)
+    duration_s: int = Field(default=20)
     extend_on_confirm: bool = Field(default=True)
```

---

## Block 6: config_loader.py - Config 메인 클래스에 confirm delta 포함

```diff
--- onset_detection/src/config_loader.py
+++ onset_detection/src/config_loader.py

@@ -149,6 +162,7 @@ class Config(BaseModel):
     detection: DetectionConfig = Field(default_factory=DetectionConfig)
     confirm: ConfirmConfig = Field(default_factory=ConfirmConfig)
     refractory: RefractoryConfig = Field(default_factory=RefractoryConfig)
     cpd: CPDConfig = Field(default_factory=CPDConfig)
     logging: LoggingConfig = Field(default_factory=LoggingConfig)
```

---

## Block 7: onset_default.yaml - persistent_n 값 수정

```diff
--- onset_detection/config/onset_default.yaml
+++ onset_detection/config/onset_default.yaml

@@ -79,7 +79,7 @@ detection:
 # Confirmation settings
 confirm:
   window_s: 12        # Confirmation window length (seconds) after candidate - Detection Only
   min_axes: 2         # Minimum number of axes that must be satisfied (price is mandatory)
   vol_z_min: 1.0      # Volume z-score threshold for confirmation (legacy, kept for compatibility)
   spread_max: 0.03    # Maximum spread threshold (legacy, kept for compatibility)
-  persistent_n: 4     # Minimum consecutive ticks that must satisfy conditions - Detection Only (relaxed for Recall)
+  persistent_n: 38    # Minimum consecutive ticks that must satisfy conditions (초당 30틱 × 1.2초분)
   exclude_cand_point: true  # Exclude candidate point from confirmation window
```

---

## Block 8: confirm_detector.py - Delta config 접근 방식 단순화

```diff
--- onset_detection/src/detection/confirm_detector.py
+++ onset_detection/src/detection/confirm_detector.py

@@ -37,17 +37,11 @@ class ConfirmDetector:
         self.pre_window_s = getattr(self.config.confirm, 'pre_window_s', 5)
 
         # Delta thresholds
-        delta_config = getattr(self.config.confirm, 'delta', {})
-        if hasattr(delta_config, 'ret_min'):
-            # Pydantic model
-            self.delta_ret_min = delta_config.ret_min
-            self.delta_zvol_min = delta_config.zvol_min
-            self.delta_spread_drop = delta_config.spread_drop
-        else:
-            # Dict
-            self.delta_ret_min = delta_config.get('ret_min', 0.0005)
-            self.delta_zvol_min = delta_config.get('zvol_min', 0.5)
-            self.delta_spread_drop = delta_config.get('spread_drop', 0.0005)
+        delta_config = self.config.confirm.delta
+        self.delta_ret_min = delta_config.ret_min
+        self.delta_zvol_min = delta_config.zvol_min
+        self.delta_spread_drop = delta_config.spread_drop
```

---

## 적용 방법

1. 위 내용을 `MODIFICATIONS.md` 파일로 저장
2. Claude Code에게 다음과 같이 지시:

```
MODIFICATIONS.md 파일의 Block 1~8 diff를 순서대로 적용해줘.
각 블록 적용 후 syntax check 실행하고 다음 블록으로 진행해.
```

---

## 검증 체크리스트

수정 완료 후 다음 명령으로 검증:

```bash
# 1. Syntax check
python -m py_compile onset_detection/src/config_loader.py
python -m py_compile onset_detection/src/detection/confirm_detector.py

# 2. Config 로딩 테스트
python -c "from onset_detection.src.config_loader import load_config; c = load_config(); print('OK')"

# 3. 설정값 확인
python -c "from onset_detection.src.config_loader import load_config; c = load_config(); print(f'persistent_n={c.confirm.persistent_n}, refractory={c.refractory.duration_s}')"
```

기대 출력:
```
persistent_n=38, refractory=20
```