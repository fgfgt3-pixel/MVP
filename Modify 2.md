

# ✅ Block 2 최종 확정 버전 (candidate_detector.py만 수정)

📌 **수정 대상 파일 (딱 1개만 작업):**
`onset_detection/src/detection/candidate_detector.py`

📌 **다른 파일(config, confirm, refractory 등은 언급/수정 금지)**
→ 이 파일 하나만 수정하는 전제로 작성

---

## ✅ 적용해야 할 변경사항 (Claude Code용 그대로 전달 가능)

```
다른 파일은 건드리지 말고 아래 파일만 수정해.

[대상 파일]
onset_detection/src/detection/candidate_detector.py

[수정 목표]
기존 session 기반 또는 CPD inline 구조는 유지하되,
DetectionOnly 기준의 "절대 임계 + trigger_axes" 방식을 추가 적용한다.

[수정 내용]

1️⃣ 절대 임계값 하드코딩(임시):
absolute_thresholds = {
    "ret_1s": 0.0008,
    "z_vol": 1.8,
    "spread_narrowing_pct": 0.75
}

2️⃣ trigger_axes 리스트 추가:
trigger_axes = []
조건 충족 시 다음 방식으로 append:
- speed : ret_1s > 0.0008
- participation : z_vol > 1.8
- friction : spread_narrowing_pct > 0.75

spread 값은 아래 우선순위로 사용:
- tick.spread 있으면 사용
- 없으면 (tick.best_ask - tick.best_bid)
- 둘 다 없으면 friction 체크는 skip

3️⃣ min_axes_required = 2 (하드코딩)
trigger_axes 길이가 2 이상이면 후보 True, 아니면 False

4️⃣ CPD inline 로직이 이미 포함되어 있다면 구조를 유지하되,
   CPD 통과 후 절대 임계 방식도 동시에 적용되도록 분기만 추가한다.
(= 기존 흐름 삭제 금지, 추가 조건만 붙이기)

5️⃣ 반환값(또는 emit 구조)에 trigger_axes 포함:
예: return { "is_candidate": True/False, "trigger_axes": trigger_axes, ... }

6️⃣ confirm_detector.py, refractory_manager.py, config 파일 등은 수정하지 마라.
이 파일만 수정하면 된다.

위 조건대로 candidate_detector.py 전체 수정본 또는 diff를 출력해.
```

---

## ✅ 이렇게 하면 해결되는 문제들

✔ 기존 구조 유지 (파일 분리 유지)
✔ CPD 훅과 충돌 없음
✔ absolute threshold + trigger_axes만 추가
✔ min_axes_required 바로 반영
✔ config 없는 상태에서도 동작 가능
✔ Claude Code가 불필요한 Block 3,4로 확장 못함

---
