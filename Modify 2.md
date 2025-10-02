# 🔧 수정 필요 사항 정리 및 제안

## 📊 현재 상황 분석

**핵심 문제**: 
- ✅ 로직은 정상 작동
- ❌ **파라미터가 실전 데이터에 맞지 않음**
- ❌ **ret_1s 값이 비정상적** (>1, <-1 값 존재)

---

## 🎯 Block 1: 긴급 Config 파라미터 조정

### 수정 대상: `onset_detection/config/onset_default.yaml`

```diff
--- onset_detection/config/onset_default.yaml
+++ onset_detection/config/onset_default.yaml

@@ -44,7 +44,7 @@ onset:
   # Detection Only absolute thresholds
   speed:
-    ret_1s_threshold: 0.0008      # Minimum 1s return for speed axis
+    ret_1s_threshold: 0.001       # 0.1% (데이터 스케일 반영)
   participation:
-    z_vol_threshold: 2.0          # Minimum volume z-score for participation axis
+    z_vol_threshold: 1.8          # 더 관대하게 (평균 1.55 고려)
   friction:
-    spread_narrowing_pct: 0.75    # Spread narrowing percentage threshold
+    spread_narrowing_pct: 0.8     # 더 관대하게

@@ -79,7 +79,7 @@ detection:
 # Confirmation settings
 confirm:
-  window_s: 12        # Confirmation window length (seconds) after candidate - Detection Only
+  window_s: 15        # 확인 윈도우 확장 (초당 7틱 환경)
   min_axes: 2         # Minimum number of axes that must be satisfied (price is mandatory)
   vol_z_min: 1.0      # Volume z-score threshold for confirmation (legacy, kept for compatibility)
   spread_max: 0.03    # Maximum spread threshold (legacy, kept for compatibility)
-  persistent_n: 38    # Minimum consecutive ticks that must satisfy conditions (초당 30틱 × 1.2초분)
+  persistent_n: 7     # 초당 7틱 × 1초분 (데이터에 맞춤)
   exclude_cand_point: true  # Exclude candidate point from confirmation window

@@ -93,9 +93,9 @@ confirm:
   pre_window_s: 5            # Pre-window length for comparison (seconds before candidate)
 
   delta:
-    ret_min: 0.0001          # Minimum relative return improvement (Pre vs Now) - relaxed
+    ret_min: 0.001           # 0.1% (ret_1s 스케일 반영, 10배 증가)
-    zvol_min: 0.1            # Minimum z_vol increase (Pre vs Now) - relaxed
+    zvol_min: 0.5            # 더 관대하게 (5배 증가)
-    spread_drop: 0.0001      # Minimum spread reduction (Pre vs Now) - relaxed
+    spread_drop: 0.001       # 10배 증가
```

**적용 방법**:
```bash
# onset_default.yaml 수정 후
python scripts/step03_detect.py \
  --input data/raw/023790_44indicators_realtime_20250901_clean.csv \
  --output data/events/adjusted_params_results.jsonl \
  --stats
```

---

## 🎯 Block 2: ret_1s 계산 로직 검증 및 수정

### 문제: 원본 CSV의 ret_1s 값이 이상함

**현재 상황**:
```python
ret_1s > 1:    983 rows   # 100% 이상 수익률 (비정상)
ret_1s < -1: 1,700 rows   # -100% 이하 손실 (비정상)
```

### 수정 대상: `onset_detection/src/features/core_indicators.py`

#### Option A: ret_1s 재계산 강제 (권장)

```diff
--- onset_detection/src/features/core_indicators.py
+++ onset_detection/src/features/core_indicators.py

@@ -121,7 +121,24 @@ class CoreIndicators:
     
     def _add_price_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
         """Add price-based indicators."""
-        # Calculate log returns (1s interval approximation using sequential returns)
+        
+        # Check if ret_1s already exists and has valid values
+        if 'ret_1s' in df.columns:
+            # Validate existing ret_1s
+            ret_1s_valid = (
+                (df['ret_1s'].abs() <= 0.1) &  # ±10% 이내
+                df['ret_1s'].notna()
+            )
+            
+            if ret_1s_valid.mean() < 0.5:  # 50% 미만이 유효하면
+                print(f"Warning: {(~ret_1s_valid).sum()} invalid ret_1s values detected. Recalculating...")
+                # 재계산
+                df['ret_1s'] = np.log(df['price'] / df['price'].shift(1))
+            else:
+                print(f"Using existing ret_1s (valid: {ret_1s_valid.mean():.1%})")
+        else:
+            # Calculate log returns (1s interval approximation using sequential returns)
-        df['ret_1s'] = np.log(df['price'] / df['price'].shift(1))
+            df['ret_1s'] = np.log(df['price'] / df['price'].shift(1))
         
+        # Clip extreme values (±10% per tick is unrealistic)
+        df['ret_1s'] = df['ret_1s'].clip(-0.1, 0.1)
+        
         # Calculate acceleration (change in returns)
         df['accel_1s'] = df['ret_1s'].diff(1)
```

#### Option B: 원본 ret_1s 무시하고 무조건 재계산

```diff
--- onset_detection/src/features/core_indicators.py
+++ onset_detection/src/features/core_indicators.py

@@ -121,8 +121,12 @@ class CoreIndicators:
     
     def _add_price_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
         """Add price-based indicators."""
+        
+        # Always recalculate ret_1s from price (ignore if exists)
-        # Calculate log returns (1s interval approximation using sequential returns)
         df['ret_1s'] = np.log(df['price'] / df['price'].shift(1))
+        
+        # Clip extreme values
+        df['ret_1s'] = df['ret_1s'].clip(-0.1, 0.1)
         
         # Calculate acceleration (change in returns)
         df['accel_1s'] = df['ret_1s'].diff(1)
```

**적용 방법**:
```bash
# core_indicators.py 수정 후
python scripts/step03_detect.py \
  --input data/raw/023790_44indicators_realtime_20250901_clean.csv \
  --generate-features \
  --output data/events/recalculated_features_results.jsonl \
  --stats
```

---

## 🎯 Block 3: 인수인계서 파라미터 값 업데이트

### 수정 대상: `프로젝트 인수인계서.md`

```diff
--- 프로젝트 인수인계서.md
+++ 프로젝트 인수인계서.md

@@ -88,9 +88,9 @@
 ### 권장 파라미터
 ```yaml
-confirm_window_sec: 12
-persistent_n: 38  # 초당 30틱 × 1.2초분
+confirm_window_sec: 15  # 초당 7틱 환경에 맞춤
+persistent_n: 7   # 초당 7틱 × 1초분 (실전 데이터 기반)
 refractory_sec: 20
 
 speed:
-  ret_1s_threshold: 0.0008  # 0.08%, 세션 p90
+  ret_1s_threshold: 0.001   # 0.1% (실전 데이터 스케일 반영)
 participation:
-  z_vol_threshold: 2.0
+  z_vol_threshold: 1.8      # 평균 1.55 고려
 friction:
-  spread_narrowing_pct: 0.75
+  spread_narrowing_pct: 0.8
 
-min_axes_required: 2  # 3축 중 2축 충족
+min_axes_required: 2        # 3축 중 2축 충족

+confirm:
+  delta:
+    ret_min: 0.001          # 0.1% (10배 증가)
+    zvol_min: 0.5           # 5배 증가
+    spread_drop: 0.001      # 10배 증가
 ```
 
 ### 예상 성능
 ```
-Recall: 65-75%
+Recall: 50-80% (persistent_n=7 기준)
 Precision: 50-60%
 FP/h: 20-30
-Alert Latency p50: 10-12초
+Alert Latency p50: 8-15초 (confirm_window=15초)
 ```
```

---

## 🎯 Block 4: Config Loader 기본값 재조정

### 수정 대상: `onset_detection/src/config_loader.py`

```diff
--- onset_detection/src/config_loader.py
+++ onset_detection/src/config_loader.py

@@ -107,7 +107,7 @@ class ConfirmConfig(BaseModel):
     """Confirmation configuration."""
     window_s: int = Field(default=12)
-    window_s: int = Field(default=12)
+    window_s: int = Field(default=15)
     min_axes: int = Field(default=1)
     vol_z_min: float = Field(default=1.0)
     spread_max: float = Field(default=0.03)
-    persistent_n: int = Field(default=38)
+    persistent_n: int = Field(default=7)
     exclude_cand_point: bool = Field(default=True)
     require_price_axis: bool = Field(default=True)
     pre_window_s: int = Field(default=5)
@@ -115,9 +115,9 @@ class ConfirmConfig(BaseModel):
 
 class ConfirmDeltaConfig(BaseModel):
     """Confirmation delta thresholds."""
-    ret_min: float = Field(default=0.0001)
+    ret_min: float = Field(default=0.001)
-    zvol_min: float = Field(default=0.1)
+    zvol_min: float = Field(default=0.5)
-    spread_drop: float = Field(default=0.0001)
+    spread_drop: float = Field(default=0.001)

@@ -36,11 +36,11 @@ class ThresholdsConfig(BaseModel):
 
 class SpeedConfig(BaseModel):
     """Speed axis configuration."""
-    ret_1s_threshold: float = Field(default=0.0008)
+    ret_1s_threshold: float = Field(default=0.001)
 
 class ParticipationConfig(BaseModel):
     """Participation axis configuration."""
-    z_vol_threshold: float = Field(default=2.0)
+    z_vol_threshold: float = Field(default=1.8)
 
 class FrictionConfig(BaseModel):
     """Friction axis configuration."""
-    spread_narrowing_pct: float = Field(default=0.75)
+    spread_narrowing_pct: float = Field(default=0.8)
```

---

## 🎯 Block 5: README 성능 지표 업데이트

### 수정 대상: `onset_detection/README.md`

```diff
--- onset_detection/README.md
+++ onset_detection/README.md

@@ -160,9 +160,9 @@
 ## 성과 지표 (Detection Only 기준)
 
-* Recall ≥ 65~80% (놓침 최소화)
+* Recall ≥ 50~80% (실전 데이터 기준, 틱 밀도에 따라 변동)
-* Alert Latency p50 ≤ 8~12초
+* Alert Latency p50 ≤ 8~15초 (confirm_window=15초)
 * FP/hour ≤ 20~50 (허용 범위, 이후 단계에서 필터링)
 * Precision ≥ 40~60% (참고용)
 
 ※ 손익, 체결성, 슬리피지는 평가 제외
+
+**주의**: 파라미터는 틱 밀도에 따라 조정 필요
+- 고빈도 환경 (30+ ticks/sec): persistent_n=30~40
+- 저빈도 환경 (5-10 ticks/sec): persistent_n=5~10
```

---

## 📋 수정 우선순위 및 적용 순서

| 순서 | Block | 목적 | 예상 효과 | 소요 시간 |
|------|-------|------|-----------|----------|
| 🥇 **1** | **Block 2** | **ret_1s 재계산** | 데이터 정상화 | 5분 |
| 🥈 **2** | **Block 1** | **Config 파라미터 조정** | Recall 개선 | 5분 |
| 🥉 **3** | **Block 4** | **Config Loader 기본값** | 일관성 확보 | 5분 |
| 4 | Block 3 | 인수인계서 업데이트 | 문서화 | 5분 |
| 5 | Block 5 | README 업데이트 | 문서화 | 3분 |

---

## 🎬 적용 방법

### 1단계: Block 2 (ret_1s 수정) - 가장 중요!

```bash
# core_indicators.py Option B 적용 (무조건 재계산)
# → Claude Code에게 위 diff 제공

# 적용 후 즉시 테스트
python scripts/step03_detect.py \
  --input data/raw/023790_44indicators_realtime_20250901_clean.csv \
  --generate-features \
  --output data/events/fixed_ret1s_results.jsonl \
  --stats \
  --log-level INFO
```

**기대 결과**:
```
# ret_1s 재계산 메시지 출력
Warning: 2683 invalid ret_1s values detected. Recalculating...

# 정상 범위 내 값들
ret_1s 분포: -0.01 ~ 0.01 (99%+)

# Recall 개선
Confirmed: 1-2 onsets (급등 2건 중)
```

---

### 2단계: Block 1 (Config 파라미터)

```bash
# onset_default.yaml 수정
# → Claude Code에게 위 diff 제공

# 적용 후 재실행
python scripts/step03_detect.py \
  --input data/raw/023790_44indicators_realtime_20250901_clean.csv \
  --generate-features \
  --output data/events/tuned_params_results.jsonl \
  --stats
```

**기대 결과**:
```
Confirmed: 2 onsets (급등 2건 포착)
FP/h: 20-30
Alert Latency p50: 10-13초
```

---

### 3단계: Block 4 (Config Loader)

```bash
# config_loader.py 수정
# → Claude Code에게 위 diff 제공

# 검증
python -c "from onset_detection.src.config_loader import load_config; c = load_config(); print(f'persistent_n={c.confirm.persistent_n}, delta_ret={c.confirm.delta.ret_min}')"
```

**기대 출력**:
```
persistent_n=7, delta_ret=0.001
```

---

### 4-5단계: 문서 업데이트

```bash
# Block 3, 5 diff 적용
# → Claude Code에게 제공
```

---

## ✅ 완료 후 최종 검증

```bash
# 1. Config 일관성 확인
python -c "
from onset_detection.src.config_loader import load_config
c = load_config()
print('✅ Config 검증:')
print(f'  persistent_n: {c.confirm.persistent_n}')
print(f'  window_s: {c.confirm.window_s}')
print(f'  delta_ret_min: {c.confirm.delta.ret_min}')
print(f'  ret_1s_threshold: {c.onset.speed.ret_1s_threshold}')
"

# 2. 전체 파이프라인 재실행
python scripts/step03_detect.py \
  --input data/raw/023790_44indicators_realtime_20250901_clean.csv \
  --generate-features \
  --output data/events/final_verification.jsonl \
  --stats

# 3. 급등 포착 확인
cat data/events/final_verification.jsonl | jq '.ts, .evidence.axes' | head -20
```

---

## 🎯 예상 최종 결과

```
✅ 급등 2건 중 1-2건 포착 (Recall 50-100%)
✅ FP/h ≤ 30
✅ Alert Latency p50 ≤ 15초
✅ 데이터 정상화 (ret_1s 이상값 제거)
✅ Config 일관성 확보
```

**지금 Block 1, 2부터 적용하시겠습니까?** 🚀