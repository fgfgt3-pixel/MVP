좋습니다 👍 이제 \*\*Step 1-4 (불응 구간, refractory 로직)\*\*을 Claude Code 실행 프롬프트로 정리해드리겠습니다. 이 단계는 cand.와 confirm 이벤트가 지나치게 근접해서 중복 탐지되는 것을 방지하기 위한 **쿨다운(불응 구간)** 로직을 추가하는 단계입니다.

---

# 📌 Step 1-4 실행 프롬프트 (Claude Code용, 최종版)

````
작업: Step 1-4 — 불응 구간(refractory) 로직 구현

요구사항:

1. config/onset_default.yaml 업데이트
   - refractory 섹션 추가:
     refractory:
       duration_s: 120   # 불응 구간 기본 길이 (초)
       extend_on_confirm: true  # confirm 발생 시 불응 구간 갱신 여부

2. src/detection/refractory_manager.py 작성
   - RefractoryManager 클래스 구현
   - 기능:
     a) 마지막 confirm 이벤트 시각(last_confirm_ts) 기록
     b) 새로운 cand. 이벤트 발생 시, cand.ts가 (last_confirm_ts + refractory.duration_s) 이전이면 "무효 처리"
     c) confirm 이벤트 발생 시 last_confirm_ts 갱신
   - 인터페이스:
     - allow_candidate(event_ts) → bool (cand. 허용 여부 반환)
     - update_confirm(event_ts) → last_confirm_ts 갱신
   - cand.가 무효 처리되면 onset_candidate 이벤트 대신 `event_type: "onset_rejected_refractory"` 이벤트로 기록

3. scripts/refractory_test.py 작성
   - 실행 예:
     ```bash
     python scripts/refractory_test.py --cands data/events/sample_candidates.jsonl --confirms data/events/sample_confirms.jsonl --out data/events/sample_refractory.jsonl
     ```
   - 동작:
     - cand.와 confirm 이벤트 불러오기
     - RefractoryManager 적용
     - 결과 JSONL 저장 (허용 cand. + confirm 유지, 거부된 cand.는 onset_rejected_refractory로 기록)
     - 콘솔에 허용 cand. 수 vs 거부 cand. 수 출력

4. tests/test_refractory_manager.py 작성
   - confirm 이후 refractory 기간 안에 발생한 cand.가 차단되는지 확인
   - refractory 기간이 지나면 cand.가 정상 허용되는지 확인
   - extend_on_confirm 옵션에 따라 동작이 달라지는지 검증

조건:
- Python 3.10 기준
- pandas, numpy 활용
- EventStore 사용
- requirements.txt 추가 패키지 없음

완료 기준:
- refractory_test.py 실행 시 onset_rejected_refractory 이벤트 JSONL 생성
- 허용/거부 cand. 개수가 config.refractory 설정에 따라 달라지는지 확인
- pytest 실행 시 test_refractory_manager.py 통과
````

---

✅ 이렇게 하면 Step 1-4에서는 **cand. 난립 억제 및 중복 탐지 방지 로직**이 완성됩니다.
즉, Phase 1은 cand. → confirm → refractory까지 기본 탐지 사이클이 모두 구축되는 셈입니다.
