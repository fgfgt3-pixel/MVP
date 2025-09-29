알겠습니다 👍 이제 \*\*Step 0-5 (백테스트 메트릭 수집 스켈레톤)\*\*을 Claude Code용 실행 프롬프트로 정리해드리겠습니다. 이 단계는 이벤트가 기록된 후, 이를 집계하여 탐지 성능을 평가할 수 있는 최소 뼈대를 만드는 목적입니다.

---

# 📌 Step 0-5 실행 프롬프트 (Claude Code용)

````
작업: Step 0-5 — 백테스트 메트릭 수집 스켈레톤 구현

요구사항:

1. src/metrics.py 작성
   - 주요 함수:
     - compute_in_window(events, labels) → 라벨 구간 내 탐지율(Recall)
     - compute_fp_rate(events, labels, trading_hours) → 시간당 FP/h
     - compute_tta(events, labels) → 탐지 지연(TTA, sec) p50/p95
   - 입력:
     - events: EventStore에서 불러온 dict 리스트
     - labels: 라벨 파일(data/labels/*.csv, 구간 [start, end]) DataFrame
   - 출력: dict { "recall": float, "fp_per_hour": float, "tta_p95": float }

2. reports/eval_summary.json 산출
   - metrics.py 결과를 JSON으로 저장
   - 키: { "recall", "fp_per_hour", "tta_p95", "n_events" }

3. scripts/eval_test.py 작성
   - 실행 예:
     ```bash
     python scripts/eval_test.py --events data/events/sample.jsonl --labels data/labels/sample.csv
     ```
   - 동작:
     - events + labels 불러오기
     - metrics.py로 집계
     - eval_summary.json 저장 + 콘솔 출력

4. tests/test_metrics.py 작성
   - 샘플 이벤트/라벨 기반으로 Recall, FP/h, TTA 계산 검증
   - JSON 파일 저장 여부 확인

조건:
- Python 3.10 기준
- pandas, numpy 활용
- 기존 src/event_store.py, data/labels/*.csv 활용
- requirements.txt 추가 패키지 불필요

완료 기준:
- `python scripts/eval_test.py --events ... --labels ...` 실행 시 JSON 및 콘솔 결과 출력
- reports/eval_summary.json 정상 생성
- pytest 실행 시 test_metrics.py 통과
````

---

✅ 이 Step 0-5가 완료되면, **라벨 데이터와 이벤트 데이터 간 매칭**을 통한 \*\*성능 지표(Recall, FP/h, TTA)\*\*를 확인할 수 있게 됩니다.
👉 이후 \*\*Step 0-6 (시각화 기본 모듈: 온셋 포인트/구간 표시)\*\*로 이어지면, 지금까지 만든 이벤트 + 메트릭을 차트로 바로 확인할 수 있습니다.