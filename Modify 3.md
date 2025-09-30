알겠다. **설명 없이 바로 Claude Code에 붙여서 작업할 수 있는 형태**로만 출력한다.
Block **3 + 4**에 해당하는 두 파일 전체 수정본을 아래에 제공한다.

---

# ✅ File 1: `onset_detection/src/detection/confirm_detector.py`

```python
# confirm_detector.py (Modified for DetectionOnly mode)

class ConfirmDetector:
    def __init__(self):
        # DetectionOnly 기준값 (config 연동 전 임시 고정)
        self.confirm_window_sec = 12   # 기존 10~30초 → 12초 고정
        self.persistent_n = 38         # 기존 값보다 완화된 기준

    def check_confirmation(self, tick_buffer):
        """
        tick_buffer: 최근 ticks 리스트 (timestamp 순서 보장)
        기존 Δ, 가격축 조건 유지하되 시간/연속성 기준만 변경
        """
        if not tick_buffer:
            return False, None

        window_ticks = self._get_recent_ticks(tick_buffer, self.confirm_window_sec)
        if len(window_ticks) < self.persistent_n:
            return False, None

        axes_ok = self._check_axes_persistence(window_ticks)
        price_ok = self._check_price_not_falling(window_ticks)

        if axes_ok and price_ok:
            return True, {
                "confirmed_axes": self._get_confirm_axes(window_ticks),
                "duration_sec": self.confirm_window_sec
            }
        return False, None

    def _get_recent_ticks(self, tick_buffer, sec_window):
        latest_ts = tick_buffer[-1].ts
        return [t for t in tick_buffer if (latest_ts - t.ts).total_seconds() <= sec_window]

    def _check_axes_persistence(self, ticks):
        return len(ticks) >= self.persistent_n

    def _check_price_not_falling(self, ticks):
        return ticks[-1].price >= ticks[0].price

    def _get_confirm_axes(self, ticks):
        # 필요 시 실제 축 확인 로직 연결, 임시 필드
        return ["speed", "participation", "friction"]
```

---

# ✅ File 2: `onset_detection/src/detection/refractory_manager.py`

```python
# refractory_manager.py (Modified for DetectionOnly mode)

import time

class RefractoryManager:
    def __init__(self):
        # DetectionOnly 기준값 (짧은 재탐지 허용)
        self.refractory_sec = 20   # 기존 60~180초 → 20초 고정
        self.last_trigger_ts = None

    def enter_refractory(self):
        self.last_trigger_ts = time.time()

    def is_refractory(self):
        if self.last_trigger_ts is None:
            return False
        elapsed = time.time() - self.last_trigger_ts
        return elapsed < self.refractory_sec

    def remaining_time(self):
        if self.last_trigger_ts is None:
            return 0
        elapsed = time.time() - self.last_trigger_ts
        remain = self.refractory_sec - elapsed
        return remain if remain > 0 else 0
```

---

# ✅ Block 3+4 검토 결과 및 수정 방안

## ⚠️ 검토 결과

위 File 1, File 2의 단순 버전은 **현재 구현과 큰 차이**가 있음:

### 현재 실제 파일 상태:
1. **confirm_detector.py** (356줄)
   - Config, EventStore 완전 연동
   - DataFrame 기반 처리
   - Delta-based 상대 개선 분석 (Pre vs Now window)
   - pre_window_s, persistent_n, window_s 모두 config에서 로드
   - `persistent_n: 4` (Block1에서 이미 config 수정 완료)

2. **refractory_manager.py** (356줄)
   - Config, EventStore 완전 연동
   - 주식별(stock_code) refractory 추적
   - process_events() 배치 처리 로직
   - `duration_s: 20` (Block1에서 이미 config 수정 완료)

### Block 1에서 이미 완료된 작업:
```yaml
confirm:
  window_s: 12              # ✅ 완료
  persistent_n: 4           # ✅ 완료

refractory:
  duration_s: 20            # ✅ 완료
```

## ✅ 최종 결론: 추가 작업 불필요

**이유:**
1. Block1에서 config 파일 수정 완료
2. 현재 코드는 config 값을 읽어서 사용:
   - `self.window_s = self.config.confirm.window_s`  → 12 자동 반영
   - `self.persistent_n = self.config.confirm.persistent_n`  → 4 자동 반영
   - `self.duration_s = self.config.refractory.duration_s`  → 20 자동 반영
3. 기존 완전한 구현을 단순 stub으로 교체하면 **기능 손실** 발생

## ✅ Block 3+4 작업 지시사항 (최종)

```
[작업 불필요]

confirm_detector.py와 refractory_manager.py는 수정하지 않는다.

이유:
- Block1에서 config 파일(onset_default.yaml) 수정 완료
- window_s: 12, persistent_n: 4, duration_s: 20 모두 설정됨
- 현재 코드는 config에서 값을 로드하므로 자동 반영됨
- 기존 완전한 구현 유지가 더 나음

Block 3+4는 Skip하고 다음 Block으로 진행.
```

