좋습니다 👍 블록 2는 **config 파라미터 확장** 단계입니다.
현재 프로젝트에서는 `config/onset_default.yaml`이 임계값(p95, 확인창, 불응 등)을 정의하고 있어요. 여기에 **cpd 블록**을 추가하면 됩니다.

---

# 🔧 블록 2: `config/onset_default.yaml` 수정

## 🎯 변경 목적

* CPD 게이트 관련 파라미터를 YAML 설정에 추가
* 기존 키(`p95`, `confirm_window`, `refractory`)와 충돌 없이, 새로운 블록(`cpd`)으로만 확장
* `CandidateDetector`(블록 1 수정판)에서 바로 참조 가능

---

## 📑 Diff 제안 (패턴 기반)

```diff
--- a/config/onset_default.yaml
+++ b/config/onset_default.yaml
@@
 # 온셋 탐지 기본 파라미터
 confirm_window_s: 20        # 확인창 길이(초)
 refractory_s: 90            # 불응 기간(초)
 p_threshold: 0.95           # p-임계 (세션별 계산)
+
+# --- CPD 게이트 (변화점 탐지) ---
+cpd:
+  use: true                  # CPD 게이트 활성화 여부
+  price:                     # 가격축 (CUSUM)
+    k_sigma: 0.7             # drift = σ * k_sigma
+    h_mult: 6.0              # 임계 = drift * h_mult
+    min_pre_s: 10            # 장초반 보호용 최소 프리 윈도우(sec)
+  volume:                    # 거래축 (Page–Hinkley)
+    delta: 0.05              # 허용 변화치
+    lambda: 6.0              # 임계
+  cooldown_s: 3.0            # 발화 후 재트리거 최소 대기시간(sec)
```

---

## 🛠️ 수정 가이드

1. **cpd 블록 추가**

   * `use`: 게이트 on/off
   * `price`: CUSUM 파라미터(k_sigma, h_mult, min_pre_s)
   * `volume`: Page–Hinkley 파라미터(delta, lambda)
   * `cooldown_s`: 발화 후 재트리거 보호

2. **기존 키 보존**

   * `confirm_window_s`, `refractory_s`, `p_threshold` 등 기존 값은 그대로 둡니다.
   * CPD 관련 키를 완전히 독립 블록으로 추가했기 때문에 충돌 없음.

3. **호환성**

   * 블록 1에서 `cfg.get("cpd", {})`로 읽기 때문에,
     기존 YAML에 `cpd` 블록이 없으면 자동으로 **비활성 모드(use=False)**로 동작 → 레거시 코드 영향 없음.

---

## ⚠️ 주의사항

* 실제 YAML에는 **들여쓰기**가 중요합니다. `cpd:` 블록은 루트 레벨(탑 레벨 키)로 추가해야 합니다.
* 스펙상 float/int 혼용 가능하지만, 불필요한 따옴표는 붙이지 않는 게 안전합니다.

---
