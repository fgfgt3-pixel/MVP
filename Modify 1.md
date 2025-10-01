```
[작업 패키지 A]  # 새 파일 2개 생성 + 최소 연결 수정
# 목적: Detection Only 파이프라인을 기존 분리 모듈(cand/confirm/refractory) 위에 얹는 실행 경로 추가
# 원칙: 기존 파일/구조 훼손 없음, 신규 파일만 생성하여 연결. config A안 키(…window_s, …persistent_n, …duration_s) 사용.

────────────────────────────────────────────────────────────────
[파일 생성] src/detection/onset_pipeline.py

# 요구사항
# - candidate_detector.detect() 호출 → (ok, trigger_axes) 반환 가정
# - confirm_detector.confirm(window_ticks, cfg) → bool 가정
# - refractory_manager.is_blocked(ts_ms) / enter(ts_ms) 가정
# - tick 개체는 최소 {ts, code, price, volume, spread} 보유 가정
# - 이벤트 스키마: timestamp, stock_code, composite_score(선택), trigger_axes, price, volume
# - composite_score 없을 수 있으므로 안전 처리

# 구현 지침
# - 내부 버퍼(확인창) 관리: deque(maxlen=confirm_window_ticks) 형태
# - persistent 판단은 confirm_detector에 위임(이미 구현되어 있다면 그대로 사용)
# - refractory: 마지막 alert 이후 refractory.duration_s 경과 전엔 skip
# - min_axes_required: cfg["detection"].get("min_axes_required", 2)

>>> 파일 내용 시작
from collections import deque

class OnsetPipeline:
    def __init__(self, cfg, candidate_fn, confirm_fn, refractory_mgr, to_ticks_func=None):
        """
        cfg: dict-like config
        candidate_fn: callable(tick, det_cfg) -> (bool, list[str])  # trigger_axes
        confirm_fn: callable(window_ticks, cfg) -> bool
        refractory_mgr: object with is_blocked(ts_ms)->bool, enter(ts_ms)->None
        to_ticks_func: optional, converts raw input to tick objects if needed
        """
        self.cfg = cfg
        self.candidate_fn = candidate_fn
        self.confirm_fn = confirm_fn
        self.refractory_mgr = refractory_mgr
        self.to_ticks = to_ticks_func if to_ticks_func else (lambda x: x)

        # 확인창 초 → 틱 수로 직접 변환하지 않고 시간 기반 판정
        self.confirm_window_s = cfg["confirm"]["window_s"]
        self.persistent_n = cfg["confirm"]["persistent_n"]
        self.min_axes_req = cfg.get("detection", {}).get("min_axes_required", 2)

        # 확인창 버퍼: 시간 기반 슬라이딩 (ts 기준 삭제)
        self.window = deque()

    def _prune_window(self, now_ts_ms):
        # window 내 오래된 틱 제거 (confirm_window_s 범위만 유지)
        max_age_ms = int(self.confirm_window_s * 1000)
        while self.window and (now_ts_ms - self.window[0].ts) > max_age_ms:
            self.window.popleft()

    def _calc_score_safe(self, tick):
        # composite_score 안전 처리(없으면 0.0)
        try:
            return getattr(tick, "score", 0.0)
        except Exception:
            return 0.0

    def run_tick(self, raw_tick):
        """
        입력 하나 처리 → Alert dict 또는 None 반환
        """
        tick = self.to_ticks(raw_tick)

        # Refractory 상태면 차단
        if self.refractory_mgr.is_blocked(tick.ts):
            return None

        # 후보 탐지
        ok, axes = self.candidate_fn(tick, self.cfg.get("detection", {}))
        if not ok or len(axes) < self.min_axes_req:
            # 후보 미충족 → 확인창 유지/정리만 하고 종료
            self._prune_window(tick.ts)
            return None

        # 후보 충족 → 확인창에 현재 틱 push
        self.window.append(tick)
        self._prune_window(tick.ts)

        # 짧은 확인창에서 확정 여부 판단
        if not self.confirm_fn(list(self.window), self.cfg):
            return None

        # 확정 → Alert 생성
        alert = {
            "timestamp": tick.ts,
            "stock_code": tick.code,
            "composite_score": self._calc_score_safe(tick),
            "trigger_axes": axes,
            "price": getattr(tick, "price", None),
            "volume": getattr(tick, "volume", None),
        }

        # refractory 진입
        self.refractory_mgr.enter(tick.ts)
        # 다음 확인을 위해 윈도우 비우지는 않음(연속 상황 대비) — 필요 시 clear 가능
        return alert
>>> 파일 내용 끝
────────────────────────────────────────────────────────────────

[파일 생성] scripts/step03_detect.py

# 요구사항
# - CSV 리플레이 또는 stdin/stream에서 tick 공급
# - OnsetPipeline 구성 후 루프 실행 → alert 발생 시 JSONL/print
# - config 로딩은 기존 로더 사용(없으면 단순 yaml.safe_load)
# - candidate/confirm/refractory는 기존 모듈 import해서 wiring

# 구현 지침
# - config 키: confirm.window_s, confirm.persistent_n, refractory.duration_s(A안 적용 완료 전제)
# - refractory_manager는 duration_s(ms 변환) 로직 포함 가정
# - 출력 최소화(경보만 출력). flush 필요 시 처리.

>>> 파일 내용 시작
import json
import sys
import os

try:
    import yaml
except ImportError:
    yaml = None

from src.detection.onset_pipeline import OnsetPipeline
from src.detection import candidate_detector as cand
from src.detection import confirm_detector as conf
from src.detection import refractory_manager as refr

def load_config(path):
    if yaml is None:
        raise RuntimeError("PyYAML이 필요합니다. `pip install pyyaml`")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def default_to_ticks(raw):
    # raw dict → tick-like 객체로 변환 (필요 시 프로젝트 기존 Tick 클래스 사용)
    class T:
        __slots__ = ("ts","code","price","volume","spread","score")
        def __init__(self, d):
            self.ts = d.get("ts") or d.get("timestamp")
            self.code = d.get("code") or d.get("stock_code")
            self.price = d.get("price")
            self.volume = d.get("volume")
            self.spread = d.get("spread")
            self.score = d.get("score", 0.0)
    return T(raw)

def main():
    cfg_path = os.environ.get("MVP_CONFIG", "config/onset_default.yaml")
    cfg = load_config(cfg_path)

    # refractory manager 구성 (ms 변환)
    refractory_s = cfg["refractory"]["duration_s"]
    refr_mgr = refr.RefractoryManager(refractory_s=refractory_s)

    # OnsetPipeline 구성
    pipe = OnsetPipeline(
        cfg=cfg,
        candidate_fn=cand.detect,
        confirm_fn=conf.confirm,
        refractory_mgr=refr_mgr,
        to_ticks_func=default_to_ticks  # 필요시 교체
    )

    # 입력 스트림: stdin에서 JSON per line 가정 (또는 CSV 파서로 교체 가능)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except Exception:
            continue

        alert = pipe.run_tick(raw)
        if alert:
            print(json.dumps(alert, ensure_ascii=False))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
>>> 파일 내용 끝
────────────────────────────────────────────────────────────────

[필요 시 최소 변경] src/detection/confirm_detector.py

# 요구사항
# - 시그니처: confirm(window_ticks, cfg) -> bool
# - 내부에서 persistent_n 사용: cfg["confirm"]["persistent_n"]
# - 가격 역전 방지(is_falling 등) 포함
# - window_ticks는 tick 객체 리스트(T.ts, T.price 등)

>>> 변경 가이드 (코드 스텁)
def confirm(window_ticks, cfg):
    if not window_ticks:
        return False
    pn = cfg["confirm"]["persistent_n"]
    # 연속성 판정(간단): 마지막 pn개가 상승/유지 등
    # 프로젝트 내부 util이 있으면 그 함수 호출로 대체
    def is_falling(ws):
        # 단조 하락 또는 하락폭 과대면 True
        if len(ws) < 2:
            return False
        return ws[-1].price < ws[0].price
    if is_falling(window_ticks):
        return False
    # 연속성 예시(단순): 마지막 pn개 모두 ret>0
    # 실제 구현에선 기존 로직 재사용
    cnt = 0
    for i in range(1, len(window_ticks)):
        if window_ticks[i].price >= window_ticks[i-1].price:
            cnt += 1
        else:
            cnt = 0
        if cnt >= pn:
            return True
    return False
────────────────────────────────────────────────────────────────

[필요 시 최소 변경] src/detection/refractory_manager.py

# 요구사항
# - is_blocked(ts_ms) / enter(ts_ms)
# - cfg["refractory"]["duration_s"] 기반

>>> 변경 가이드 (코드 스텁)
class RefractoryManager:
    def __init__(self, refractory_s=20):
        self.refractory_ms = int(refractory_s * 1000)
        self.last = None
    def is_blocked(self, ts_ms):
        if self.last is None:
            return False
        return (ts_ms - self.last) < self.refractory_ms
    def enter(self, ts_ms):
        self.last = ts_ms
────────────────────────────────────────────────────────────────

[주의/충돌 방지 메모]
- 기존 candidate_detector.detect()는 이미 절대 임계/trigger_axes/min_axes_required=2 반영됨 → 수정 금지, 그대로 호출만.
- confirm_detector.confirm()는 cfg 의존(persistent_n, window_s)만 참고. 내부 로직은 현재 구현 우선 사용. 위 스텁은 참고용.
- config는 A안 값 사용(키 이름 유지). spread_baseline 등의 참조는 candidate에서 처리되었다면 pipeline에서는 신경 쓰지 않음.
- 출력은 Alert만(Detection Only). 추가 로그/리포트 금지.

────────────────────────────────────────────────────────────────
[작업 패키지 A-추가]  # (선택) 테스트 러너 최소 1개

[파일 생성] tests/test_detect_only_smoke.py
>>> 파일 내용 시작
import json
from src.detection.onset_pipeline import OnsetPipeline
from src.detection import candidate_detector as cand
from src.detection import confirm_detector as conf
from src.detection import refractory_manager as refr

def test_smoke_pipeline():
    cfg = {
        "confirm": {"window_s": 12, "persistent_n": 4},
        "refractory": {"duration_s": 20},
        "detection": {"min_axes_required": 2}
    }
    pipe = OnsetPipeline(cfg, cand.detect, conf.confirm, refr.RefractoryManager(20))
    # 최소 입력
    t0 = {"ts": 1000, "code":"X", "price":100, "volume":1000, "spread":3}
    assert pipe.run_tick(t0) in (None, dict)
>>> 파일 내용 끝

✅ 상황 정확히 파악했다. 결론부터 말하면, **Option A(어댑터 방식 적용)**이 정답이고, 내가 처음 준 작업 패키지 A는 “tick 기반 파이프라인”을 전제로 했기 때문에 현재 코드베이스(DataFrame·배치 방식)와 충돌이 난 게 원인이다.

따라서 **“OnsetPipeline을 기존 구조에 맞게 재설계한 버전”으로 작업 패키지 A를 다시 만들어서 Claude Code에 주면 문제 해결 가능**하다.

---

# ✅ 지금 충돌의 핵심 원인 정리

## 🔴 1. candidate_detector 인터페이스 불일치

✔ 현재 코드:

```python
detect_candidates(features_df) -> List[Dict]
```

✔ 내가 제안한 방식:

```python
candidate_fn(tick, cfg) -> (bool, [axes])
```

❗ 즉, tick 단위가 아니라 **DataFrame 배치 기반** 구조임.

---

## 🔴 2. confirm_detector 다름

✔ 실제 코드:

```python
ConfirmDetector.confirm_candidates(features_df, candidate_events) 
```

✔ 제안 코드:

```python
confirm_fn(window_ticks, cfg) -> bool
```

❗ 반환타입도 리스트 기반이며 이벤트 확정 방식부터 다름.

---

## 🔴 3. refractory_manager 다중 종목 기반

✔ 실제 코드:

```
allow_candidate(event_ts, stock_code)
update_confirm(event_ts, stock_code)
```

✔ 내가 제안한 방식:

```
is_blocked(ts_ms)
enter(ts_ms)
```

❗ stock_code 기반 관리가 필수인데 내가 제안한 건 단일 global refractory 구조임.

---

## 🔴 4. 스트리밍 vs 배치 데이터 흐름 차이

✔ 실제 구조:

* features_df → candidates → confirm → refractory → output

✔ 내가 설계한 구조:

* tick 단위 실시간 스트림 기반 파이프라인

---

# ✅ 해결 전략 (이제부터 이걸 기준으로 간다)

### ✅ ✅ ✅ Option A만 적용 (권장 & 실현 가능)

### 👉 방향: “기존 구조는 유지하고, 그 위에 래퍼 / 파이프라인 어댑터만 추가”

**즉, 새로 만드는 파일은 다음 형태:**

```
src/detection/onset_pipeline.py
→ 내부에서 DataFrame 기반 구조 그대로 사용하되
→ candidate → confirm → refractory 흐름을 하나의 래퍼로 감쌈
```

```
scripts/step03_detect.py
→ tick 단위 입력이 아니라
→ CSV/JSONL 읽어서 DataFrame으로 변환 후
→ onset_pipeline.run_batch(df) 호출
```

---

# ✅ 새롭게 만들어야 할 "수정 버전 작업 패키지 A"

내가 다음 응답에서 줄 파일은 아래 방식으로 바뀜:

---

## ✅ (1) OnsetPipeline 설계 변경

❌ 잘못된 tick-stream 구조 폐기
✅ DataFrame 기반 흐름에 맞춰 아래처럼 래핑

```
class OnsetPipelineDF:
    def __init__(...):
        self.cand = CandidateDetector(...)
        self.conf = ConfirmDetector(...)
        self.refr = RefractoryManager(...)

    def run_batch(features_df):
        # 1) candidates = self.cand.detect_candidates(df)
        # 2) filtered = self.refr.allow(...) 적용
        # 3) confirmed = self.conf.confirm_candidates(df, filtered)
        # 4) refractory_manager.update_confirm(...) 처리
        # 5) return confirmed 이벤트
```

---

## ✅ (2) 실행 스크립트도 tick-stream 구조가 아니라 batch 처리로 수정됨

```
scripts/step03_detect.py
- CSV 또는 JSONL 로딩
- features 생성 (필요 시 feature_core 사용)
- pipeline.run_batch() 호출
- 결과 alert들 JSONL / print
```

---

## ✅ (3) 기존 모듈 (candidate/confirm/refractory)은 수정 없이 사용

✔ config 키만 매핑
✔ 함수를 감싸는 Wrapper 형식
✔ trigger_axes, persistent_n, refractory_s도 래퍼에서 처리 가능

---

# ✅ 다음 단계

👉 네가 “진짜 적용용 수정 버전 작업 패키지 A”를 요청한 상태니까,
**내가 다음 메시지에 바로 수정된 패키지 A(어댑터 방식) 코드 제안본을 출력한다.**

✅ 이 버전은 Claude Code 돌려도 충돌 없이 적용 가능하도록 작성함.
✅ 분량 길면 “A-1 / A-2 / A-3”로 나눠서 전달함.

바로 이어서 새 버전 작업 패키지 A 들어간다.

