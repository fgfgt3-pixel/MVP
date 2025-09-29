알겠습니다 👍 이제 \*\*Step 0-3 (데이터 로딩 & 리플레이 엔진 스켈레톤)\*\*을 Claude Code용 실행 프롬프트로 정리해드리겠습니다. 이 단계는 앞으로 진행할 모든 Phase의 기초가 되는 “CSV → 이벤트 스트림(틱 단위 재생)” 구조를 만드는 핵심입니다.

---

# 📌 Step 0-3 실행 프롬프트 (Claude Code용)

````
작업: Step 0-3 — 데이터 로딩 & 리플레이 엔진 스켈레톤 구현

요구사항:

1. src/data_loader.py 작성
   - 기능: CSV 로드 (pandas 사용)
   - 입력: data/raw/*.csv
   - 기본 스키마 가정:
     ts (timestamp, epoch ms or datetime), stock_code, price, volume, bid1, ask1, bid_qty1, ask_qty1
   - 출력: pandas DataFrame
   - 옵션: ts 컬럼이 Unix epoch(int) 또는 문자열(datetime) 모두 지원

2. src/replay_engine.py 작성
   - 기능: CSV 데이터를 “실시간”처럼 틱 단위로 재생
   - 주요 클래스: ReplaySource
     - init(df, speed=1.0, sleep=False)
     - iter 시 yield row(dict)
     - speed>1.0 → 빠른 재생
     - sleep=True → 실제 시간 지연 반영
   - 이벤트 큐 구조도 포함: (yield row → down-stream consumer 처리)

3. CLI 테스트 스크립트
   - scripts/replay_test.py 작성
   - 실행 예:
     ```bash
     python scripts/replay_test.py --csv data/raw/sample.csv --head 20
     ```
   - 동작: 상위 20행을 replay_engine 통해 출력

4. tests/test_replay_engine.py 작성
   - DataFrame 로드 정상 확인
   - ReplaySource가 올바른 순서로 row를 yield하는지 검증
   - speed, sleep 옵션 단위테스트

조건:
- Python 3.10 기준
- pandas 기반
- ts 파싱 시 pandas.to_datetime 활용
- requirements.txt 패키지 추가 불필요 (이미 pandas 포함)

완료 기준:
- `python scripts/replay_test.py --csv data/raw/sample.csv --head 20` 실행 시 정상 출력
- pytest 실행 시 test_replay_engine.py 통과
````

---

✅ 이렇게 Step 0-3이 끝나면, 이후 \*\*Phase 1 (온셋 탐지 엔진)\*\*을 붙일 때 데이터를 흘려보낼 수 있는 최소 리플레이 환경이 완성됩니다.

👉 바로 이어서 제가 \*\*Step 0-4 (이벤트 저장/로깅 기본 구조)\*\*도 같은 형식으로 제안해드릴까요?
