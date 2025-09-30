미안해요. 제가 파일 경계를 혼동했어요. 이미 `candidate_detector.py`가 반영된 상태 기준으로, **나머지 연결·확인·불응·출력만 정리하는 지시문** 바로 드립니다.

```
[Block2-REVISE: DetectOnly 파이프라인 연결 수정]

🎯 목표
- candidate_detector.py 변경사항 그대로 유지
- detect_onset.py/step03_detect.py에서 후보→확인→경보→불응 FSM만 정리
- config 키 현재 구조(A안) 기준(…window_s, …persistent_n, …duration_s) 사용
- 이벤트 스키마에 trigger_axes 전달

🗂 대상 파일
1) src/detect_onset.py
2) scripts/step03_detect.py
3) (옵션) src/utils/rolling.py  # spread_baseline fallback 유틸 없으면 추가
4) tests/test_detect_only.py    # 최소 단위 테스트

────────────────────────────────────────────────────────────────

[1] src/detect_onset.py 변경

A) 클래스 분리/초기화
- OnsetDetector.__init__(cfg):
  self.confirm_window = cfg["confirm"]["window_s"]          # int(sec)
  self.persistent_n   = cfg["confirm"]["persistent_n"]      # 3~5
  self.refractory_s   = cfg["refractory"]["duration_s"]     # 20
  self.min_axes_req   = cfg.get("detection", {}).get("min_axes_required", 2)
  self.last_alert_ts  = None
  상태: "idle" | "confirming" | "refractory"

B) 후보 판정(호출만)
- detect_candidate(tick, features):
  from candidate_detector import detect as cand_detect
  ok, trigger_axes = cand_detect(tick, cfg["detection"])
  return ok, trigger_axes

C) 확인 로직
- confirm(window_ticks):
  # 연속성 계산: features 또는 tick 플래그 기준으로 연속 카운트
  consecutive = count_persistent(window_ticks)   # 기존 유틸 재사용
  price_ok = not is_falling(window_ticks)        # 기존/동등 함수 재사용
  return (consecutive >= self.persistent_n) and price_ok

D) refractory 처리
- in_refractory(now_ts):
  return (self.last_alert_ts is not None) and (now_ts - self.last_alert_ts < self.refractory_s * 1000)

E) 이벤트 출력
- emit_alert(tick, trigger_axes):
  return {
    "timestamp": tick.ts,
    "stock_code": tick.code,
    "composite_score": calc_score_safe(tick),  # weights 없을 때 0.0 반환
    "trigger_axes": trigger_axes,
    "price": tick.price,
    "volume": getattr(tick, "volume", None),
  }

F) 스코어 안전화
- calc_score_safe(tick):
  try: return self.calc_score(tick)
  except: return 0.0

G) spread_baseline fallback (필요 시)
- get_spread_baseline(tick):
  if hasattr(tick, "spread_baseline"): return tick.spread_baseline
  else: return rolling_median_spread(last_n=300)  # 없으면 utils에서 안전 기본값(e.g. 3) 반환

H) run_step(tick):
  if in_refractory(tick.ts): return None
  ok, axes = detect_candidate(tick, features)
  if not ok or len(axes) < self.min_axes_req: return None
  open_confirm_window()  # 내부 버퍼 시작
  if confirm(window_ticks): 
      event = emit_alert(tick, axes)
      self.last_alert_ts = tick.ts
      enter_refractory()
      return event
  return None

────────────────────────────────────────────────────────────────

[2] scripts/step03_detect.py 변경

- cfg 로드 후 객체 구성:
  det = OnsetDetector(cfg)

- 스트림 루프:
  for tick in stream:
    evt = det.run_step(tick)
    if evt:
      print_json(evt)           # stdout 또는 JSONL append
      flush_if_needed()

- 종료: 없음 (DetectionOnly는 Alert까지만)

────────────────────────────────────────────────────────────────

[3] (옵션) src/utils/rolling.py 추가 또는 보완

- rolling_median_spread(last_n=300) 구현
  내부 버퍼 deque(maxlen=300) 사용, 값 없으면 기본 3 반환
- count_persistent(window_ticks) 유틸 없으면 여기로 이동
- is_falling(window_ticks): 최근 N틱 단조하락 판정(간단 기준)

────────────────────────────────────────────────────────────────

[4] tests/test_detect_only.py (최소)

- test_confirm_persistence:
  persistent_n=4, 8초 창에서 연속 4틱 충족 → True

- test_refractory_blocks_retrigger:
  refractory_s=20 설정 후, 10초 내 재후보 발생해도 Alert 없음

- test_event_schema_contains_axes:
  emit_alert 결과에 trigger_axes 포함/배열/빈배열아님 검증

────────────────────────────────────────────────────────────────

📌 주의/충돌 방지 이유

- candidate_detector.py는 이미 하드코딩/trigger_axes/min_axes=2 완비 → 재수정 금지
- detect_onset.py는 “호출/확인/불응/출력”만 담당 → 책임 분리로 충돌 최소화
- config 키는 A안 구조(window_s/persistent_n/duration_s)만 참조 → 기존 호환
- score 계산 실패 대비 calc_score_safe → 런타임 안전
- spread_baseline 미정 대비 rolling fallback → 즉시 실험 가능

완료 후:
- README/Project_* 문서대로 Alert만 발생하는지 확인
- Block3(이벤트 경로/로그/리포트 최소 보강) 필요 시 후속 지시 예정
```
