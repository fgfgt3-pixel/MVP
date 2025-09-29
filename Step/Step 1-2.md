알겠습니다 👍 앞서 논의된 의문사항(📌 config 구조, 스케일 차이, threshold 적용 위치)을 반영하여 **Step 1-2 (온셋 후보 이벤트 탐지)** 실행 프롬프트를 다시 정리해드리겠습니다.

---

# 📌 Step 1-2 실행 프롬프트 (Claude Code용, 최종版)

````
작업: Step 1-2 — 온셋 후보 이벤트 탐지 (cand.) 구현

요구사항:

1. config/onset_default.yaml 업데이트
   - detection 섹션 추가:
     detection:
       score_threshold: 2.0
       vol_z_min: 2.0
       ticks_min: 2
       weights:
         ret: 1.0
         accel: 1.0
         z_vol: 1.0
         ticks: 0.5

2. src/detection/candidate_detector.py 작성
   - CandidateDetector 클래스 구현
   - 입력: features DataFrame (Step 1-1 출력)
   - 로직:
     a) 각 row별로 지표 추출 (ret_1s, accel_1s, z_vol_1s, ticks_per_sec)
     b) score 계산:
        score = w1*ret_1s + w2*accel_1s + w3*z_vol_1s + w4*ticks_per_sec
        (w는 config.detection.weights에서 로드)
     c) 조건:
        - score >= config.detection.score_threshold
        - z_vol_1s >= config.detection.vol_z_min
        - ticks_per_sec >= config.detection.ticks_min
     d) 위 조건 충족 시 onset_candidate 이벤트 생성
   - 이벤트 포맷:
     {
       "ts": ...,
       "stock_code": ...,
       "event_type": "onset_candidate",
       "score": float,
       "evidence": {
         "ret_1s": ...,
         "accel_1s": ...,
         "z_vol_1s": ...,
         "ticks_per_sec": ...
       }
     }
   - EventStore.save_event() 활용하여 JSONL 저장

3. scripts/candidate_test.py 작성
   - 실행 예:
     ```bash
     python scripts/candidate_test.py --features data/features/sample_features.csv --out data/events/sample_candidates.jsonl
     ```
   - 동작:
     - features CSV 불러오기
     - CandidateDetector 실행
     - onset_candidate 이벤트 JSONL 저장
     - cand. 개수 및 샘플 5개 이벤트 콘솔 출력

4. tests/test_candidate_detector.py 작성
   - 샘플 features CSV를 이용해 cand. 이벤트가 최소 1개 이상 생성되는지 확인
   - score 계산식 검증
   - threshold 값 조정 시 cand. 개수 변동 확인
   - 이벤트 evidence 필드(ret_1s, accel_1s, z_vol_1s, ticks_per_sec) 존재 확인

조건:
- Python 3.10 기준
- pandas, numpy 활용
- EventStore 사용 (src/event_store.py)
- requirements.txt 추가 패키지 없음
- 지표 스케일 차이는 초기에는 가중치 조합으로 처리 (Phase 2에서 정규화/튜닝 예정)

완료 기준:
- candidate_test.py 실행 시 onset_candidate JSONL 생성
- events 디렉토리에 cand. 이벤트 파일 생성
- pytest 실행 시 test_candidate_detector.py 통과
````

---

✅ 요약

* **config.detection** 섹션 신설
* **CandidateDetector 클래스** 구현 → 가중합 기반 score 계산
* EventStore로 onset\_candidate 이벤트 기록
* CLI + pytest 검증 포함
