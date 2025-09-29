좋습니다 👍 이제 \*\*Step 1-3 (확인창 confirm 로직)\*\*을, 앞서 Step 1-2에서 다뤘던 config 구조/스케일 문제까지 고려한 최종版 실행 프롬프트로 다시 정리해드리겠습니다.

---

# 📌 Step 1-3 실행 프롬프트 (Claude Code용, 최종版)

````
작업: Step 1-3 — 확인창(confirm) 로직 구현

요구사항:

1. config/onset_default.yaml 업데이트
   - confirm 섹션 추가:
     confirm:
       window_s: 20        # cand. 이후 확인창 길이 (초)
       min_axes: 1         # 충족해야 하는 최소 축 개수
       vol_z_min: 2.0      # 거래량 확인 기준
       spread_max: 0.02    # 스프레드 상한 (옵션)

2. src/detection/confirm_detector.py 작성
   - ConfirmDetector 클래스 구현
   - 입력:
     - features DataFrame (Step 1-1 출력)
     - cand. 이벤트 리스트 (Step 1-2 출력)
   - 로직:
     a) cand. 발생 시점부터 window_s 초 동안의 features 윈도우 추출
     b) cand. 증거 축 중 최소 min_axes 개가 확인창에서 강화되는지 확인
        - 가격 축: ret_1s > 0 유지 OR microprice_slope > 0
        - 거래 축: z_vol_1s >= confirm.vol_z_min
        - 마찰 축: spread <= confirm.spread_max
     c) 조건 충족 시 onset_confirmed 이벤트 생성
   - 이벤트 포맷:
     {
       "ts": <확정 시각>,
       "stock_code": ...,
       "event_type": "onset_confirmed",
       "confirmed_from": <cand_ts>,
       "evidence": {
         "axes": ["price", "volume"],
         "ret_1s": ...,
         "z_vol_1s": ...,
         "spread": ...
       }
     }
   - EventStore.save_event() 활용하여 JSONL 저장

3. scripts/confirm_test.py 작성
   - 실행 예:
     ```bash
     python scripts/confirm_test.py --features data/features/sample_features.csv --cands data/events/sample_candidates.jsonl --out data/events/sample_confirms.jsonl
     ```
   - 동작:
     - features + cand. 이벤트 불러오기
     - ConfirmDetector 실행
     - onset_confirmed 이벤트 JSONL 저장
     - cand. 대비 confirm 비율, 평균 TTA 콘솔 출력

4. tests/test_confirm_detector.py 작성
   - cand. 이벤트 주어졌을 때 confirm이 최소 1개 이상 생성되는지 확인
   - window_s 값 변경 시 결과가 달라지는지 검증
   - evidence 축(가격/거래/마찰) 필드 존재 여부 확인
   - confirmed_from이 cand. ts와 올바르게 연결되는지 확인

조건:
- Python 3.10 기준
- pandas, numpy 활용
- EventStore 사용
- requirements.txt 추가 패키지 없음
- 초기 구현은 단순 규칙 기반, Phase 2에서 조건 튜닝/정규화 검토 예정

완료 기준:
- confirm_test.py 실행 시 onset_confirmed JSONL 생성
- cand. 대비 confirm 비율 및 TTA 콘솔 출력
- pytest 실행 시 test_confirm_detector.py 통과
````
