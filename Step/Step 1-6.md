좋습니다 👍 이제 \*\*Step 1-6 (시각화 보고서)\*\*를 Claude Code 실행 프롬프트로 정리해드리겠습니다. 이 단계는 Step 1-5까지 산출된 이벤트(cand./confirm/refractory)를 **차트로 표현**하여 사람이 직관적으로 검증할 수 있게 하는 단계입니다.

---

# 📌 Step 1-6 실행 프롬프트 (Claude Code용, 최종版)

````
작업: Step 1-6 — 시각화 보고서 (cand./confirm/refractory 이벤트 차트화)

요구사항:

1. src/reporting/plot_report.py 작성
   - 기능:
     a) 가격 데이터(DataFrame) 불러오기
     b) EventStore에서 cand./confirm/refractory 이벤트 불러오기
     c) 라벨 CSV(optional) 불러오기
     d) matplotlib으로 차트 생성
   - 표시 규칙:
     - cand. 이벤트: 주황색 점 (△ 마커)
     - confirm 이벤트: 빨간색 ● 마커
     - refractory 거부된 cand.: 회색 ✕ 마커
     - (옵션) 라벨 구간: 파란색 음영(span)
   - 출력:
     - PNG 저장: reports/plots/<종목>_<날짜>_report.png
     - (옵션) HTML 저장: reports/plots/<종목>_<날짜>_report.html

2. scripts/plot_report_test.py 작성
   - 실행 예:
     ```bash
     python scripts/plot_report_test.py --csv data/clean/sample.csv --events data/events/sample_confirms.jsonl --labels data/labels/sample.csv --out reports/plots/sample_report.png
     ```
   - 동작:
     - 데이터 + 이벤트 + 라벨 불러오기
     - plot_report 실행
     - PNG 저장 후 콘솔에 “cand=X, confirm=Y, rejected=Z” 출력

3. tests/test_plot_report.py 작성
   - PNG 파일 생성 여부 확인
   - cand./confirm 이벤트 수와 마커 수 일치하는지 검증
   - 라벨 span이 포함된 경우 차트에 음영 처리 여부 확인

조건:
- Python 3.10 기준
- matplotlib, seaborn 활용
- EventStore 사용
- requirements.txt 추가 패키지 없음

완료 기준:
- plot_report_test.py 실행 시 PNG 파일 생성
- reports/plots/ 하위에 cand./confirm/refractory가 시각적으로 구분된 차트 출력
- pytest 실행 시 test_plot_report.py 통과
````

---

✅ 이 Step 1-6이 완료되면, 숫자(JSON)뿐만 아니라 **시각화된 리포트 차트**로도 온셋 탐지 성능을 검증할 수 있습니다.
