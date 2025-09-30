✅ 이해 완료. 이제 **Block1(✅ config 수정)**부터 Claude Code가 바로 작업할 수 있는 형태로 **지시문 패키지** 만들어서 줄게.

---

# ✅ Block1 작업 대상

📌 **파일:**
`config/onset_default.yaml`
(또는 현재 사용 중인 동일 역할의 config 파일)

📌 **목표:**
Detection Only 모드에 맞게 **파라미터 수정 + 구조 안정화**
→ 기존 구조는 유지하면서 값만 변경

---

# ✅ Claude Code 지시문 (그대로 복사해서 전달하면 됨)

```
[Block1 수정 요청]

📌 대상 파일:
config/onset_default.yaml

📌 수정 목적:
Detection Only (급등 포착 전용) 설정 반영.
Recall 우선 / 빠른 감지 / 낮은 임계 / 짧은 불응 / 짧은 확인창 기준으로 값 수정.

📌 아래 항목만 변경 또는 추가:

1) 확인창 (기존 10~30s → 10~15s 기준으로 축소)
confirm_window_sec: 12
confirm_window_min_sec: 8
confirm_window_max_sec: 15

2) 연속 틱 기준 완화
persistent_n: 38

3) 불응 시간 단축
refractory_sec: 20

4) 절대 임계 기반 후보 탐지값 반영
speed:
  ret_1s_threshold: 0.0008
participation:
  z_vol_threshold: 2.0
friction:
  spread_narrowing_pct: 0.75

5) 축 판정 조건
min_axes_required: 2

6) 출력 필드 유지 (기존 값 보존)
alert_output:
  - timestamp
  - stock_code
  - composite_score
  - trigger_axes
  - current_price
  - current_volume
```

⚠️ **주의:**

* 기존 config 구조 변경 ❌
* 값만 overwrite ✅
* 추가 키는 indentation 유지 ✅

