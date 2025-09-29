알겠습니다 👍 이제 \*\*Step 1-5 (Phase 1 산출물 통합 + 리포트 출력)\*\*을 Claude Code 실행 프롬프트로 정리해드리겠습니다. 이 단계는 cand. → confirm → refractory까지 만들어진 이벤트들을 하나로 통합하고, **품질 리포트(JSON) 산출**까지 진행하는 단계입니다.

---

# 📌 Step 1-5 실행 프롬프트 (Claude Code용, 최종版)

````
작업: Step 1-5 — Phase 1 산출물 통합 + 리포트 출력

요구사항:

1. src/reporting/quality_report.py 작성
   - 기능:
     a) EventStore에서 cand./confirm/refractory 이벤트 불러오기
     b) config/onset_default.yaml 기반으로 평가 지표 계산
        - cand. 수, confirm 수, rejected(불응) 수
        - confirm 비율 (%)
        - cand.→confirm TTA (평균/중앙값/p95)
     c) 결과 dict → JSON 저장
   - 출력 예시:
     {
       "n_candidates": 120,
       "n_confirms": 40,
       "n_rejected": 30,
       "confirm_rate": 0.33,
       "tta_avg": 1.5,
       "tta_p95": 3.2
     }

2. reports/onset_quality.json 생성
   - quality_report.py 실행 시 자동 저장
   - 저장 경로: reports/onset_quality.json

3. scripts/quality_test.py 작성
   - 실행 예:
     ```bash
     python scripts/quality_test.py --events data/events/sample_confirms.jsonl --out reports/onset_quality.json
     ```
   - 동작:
     - 이벤트 파일 로드
     - quality_report 실행
     - reports/onset_quality.json 저장
     - 콘솔에 confirm 비율, TTA p95 출력

4. tests/test_quality_report.py 작성
   - 이벤트 샘플 주어졌을 때 지표 계산이 정상 동작하는지 확인
   - JSON 저장 파일 존재 여부 확인
   - confirm_rate, TTA 계산 로직 검증

조건:
- Python 3.10 기준
- pandas, numpy 활용
- EventStore 사용
- requirements.txt 추가 패키지 없음

완료 기준:
- quality_test.py 실행 시 reports/onset_quality.json 생성
- JSON 안에 cand/confirm/rejected 수, confirm_rate, TTA 포함
- pytest 실행 시 test_quality_report.py 통과
````

---

✅ 이 Step 1-5가 끝나면, Phase 1의 전 과정을 거쳐 나온 이벤트들을 바탕으로 \*\*숫자 리포트(JSON)\*\*를 확보할 수 있습니다.
즉, Step 1-1 \~ Step 1-5까지가 **MVP의 “룰 기반 온셋 탐지 엔진” 최소 완성**이라고 보시면 됩니다.
