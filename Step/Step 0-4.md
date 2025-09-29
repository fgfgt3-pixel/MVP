알겠습니다 👍 이어서 \*\*Step 0-4 (이벤트 저장/로깅 기본 구조)\*\*를 Claude Code용 실행 프롬프트로 정리했습니다. 이 단계는 이후 온셋 탐지·백테스트 결과를 안정적으로 쌓을 수 있는 최소 이벤트 로깅 시스템을 만드는 목적입니다.

---

# 📌 Step 0-4 실행 프롬프트 (Claude Code용)

```
작업: Step 0-4 — 이벤트 저장/로깅 기본 구조 구현

요구사항:

1. src/event_store.py 작성
   - EventStore 클래스 설계
     - init(path="data/events")
     - save_event(event: dict) → 이벤트를 JSONL(append 모드)로 저장
     - load_events(limit=None) → JSONL에서 이벤트 로드 (최대 limit 개)
   - 이벤트 필드 예시:
     {
       "ts": 1720000000,        # unix timestamp
       "stock_code": "005930",
       "event_type": "onset_candidate",
       "score": 2.3,
       "extra": {"spread": 0.05}
     }
   - 저장 포맷: JSON Lines (1행=1이벤트)

2. src/logger.py 작성
   - 기본 로깅 설정(logging 모듈)
   - 로그 레벨: INFO 이상
   - 출력: 콘솔 + logs/app.log 파일
   - 로그 메시지 예시: [2025-09-24 10:00:00] INFO replay row=...

3. scripts/event_test.py 작성
   - 예시 이벤트 생성 후 EventStore.save_event() 호출
   - load_events()로 다시 불러와 콘솔에 출력
   - 로그 메시지 확인 (logger 사용)

4. tests/test_event_store.py 작성
   - save_event 후 파일 생성 여부 확인
   - load_events()가 저장된 dict 리스트 반환하는지 확인
   - limit 옵션 동작 검증

조건:
- Python 3.10 기준
- json, pathlib, logging 표준 라이브러리 활용
- requirements.txt 추가 불필요

완료 기준:
- `python scripts/event_test.py` 실행 시 이벤트 JSONL에 기록되고 정상 출력
- logs/app.log 파일 생성 및 로그 기록 확인
- pytest 실행 시 test_event_store.py 통과
```

---

✅ 이 Step 0-4가 완료되면, Phase 1에서 cand./confirm 이벤트가 발생했을 때 이를 `EventStore`에 기록하고, 백테스트 리포트에서도 재활용할 수 있는 뼈대가 마련됩니다.
