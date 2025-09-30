✅ 확인 완료. 지금부터 **Block 2(candiate_detector.py 수정)** 바로 진행할 수 있도록, Claude Code에 넘길 **작업용 지시문 + 구현 스펙**을 최종 형태로 제공한다.

⚠️ 주의:

* **해당 파일만 수정한다.**
* 다른 파일(config, confirm, refractory)은 언급하지 않는다.
* 기존 코드(세션 임계, CPD 로직, 이벤트 처리)는 유지한다.

---

# ✅ ✅ Claude Code 전달용 작업 요청서 (Block 2 전용)

```
[대상 파일]
onset_detection/src/detection/candidate_detector.py

[작업 형태]
🔹 기존 코드를 유지하면서 "기능 추가" 방식으로 수정한다.
🔹 전체 교체 금지, 다른 파일 수정 금지.

[반영할 기능]

1️⃣ 절대 임계값 조건 추가 (config 미사용, 하드코딩 OK)

absolute_thresholds = {
    "ret_1s": 0.0008,
    "z_vol": 1.8,
    "spread_narrowing_pct": 0.75
}

2️⃣ trigger_axes 리스트 생성 및 조건 충족 시 추가

trigger_axes = []
조건 예시:
if ret_1s > 0.0008 → trigger_axes.append("speed")
if z_vol > 1.8 → trigger_axes.append("participation")
if spread < baseline*0.75 → trigger_axes.append("friction")

spread 값은 다음 우선순위로 판단:
1) tick.spread 있으면 사용
2) tick.best_ask - tick.best_bid로 계산
3) 불가하면 friction 체크 skip

3️⃣ min_axes_required = 2 적용

if len(trigger_axes) >= 2:
    is_candidate = True
else:
    is_candidate = False

4️⃣ 기존 session 기반 / CPD 기반 흐름은 삭제하지 않는다.
- 절대 임계는 "추가 조건"으로만 작동
- CPD가 True면 절대임계 체크도 실행
- 기존 p95 임계 로직은 유지

5️⃣ 반환 또는 emit 시 trigger_axes 포함
예:
return {
    "is_candidate": is_candidate,
    "trigger_axes": trigger_axes,
    ...
}

6️⃣ confirm_detector.py, refractory_manager.py, config 파일은 수정하지 않는다.
이 파일 하나만 수정한다.

[출력 형식]
- candidate_detector.py "전체 수정본"으로 출력 (diff 아님)
```

---
