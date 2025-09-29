좋습니다 👍 이제 \*\*Step 0-6 (시각화 기본 모듈)\*\*을 Claude Code용 실행 프롬프트로 정리해드리겠습니다. 이 단계는 지금까지 만든 이벤트/라벨/메트릭을 차트 상에서 직관적으로 확인할 수 있는 최소 시각화 기능을 구현하는 단계입니다.

---

# 📌 Step 0-6 실행 프롬프트 (Claude Code용)

````
작업: Step 0-6 — 시각화 기본 모듈 (온셋 포인트/구간 표시)

요구사항:

1. src/plot_onset.py 작성
   - 기능: 가격 데이터(DataFrame) + 이벤트(EventStore) + 라벨(Label CSV)를 시각화
   - 출력: matplotlib 기반 PNG
   - 모드 지원:
     - point 모드: onset 확정 이벤트를 scatter marker(빨강 ●)로 표시
     - span 모드: onset 시작~Peak 구간을 반투명 음영 영역으로 표시
   - 옵션:
     - show_stages: cand(연한색) / confirm in-progress(중간 명도) / confirmed(진한색)
     - debug_labels: 마커 옆에 score, 증거 타입 텍스트 표시
     - timeline_panel: 하단에 Event Timeline 보조 패널 추가 (cand→confirm→확정 흐름)

2. scripts/plot_test.py 작성
   - 실행 예:
     ```bash
     python scripts/plot_test.py --csv data/raw/sample.csv --events data/events/sample.jsonl --labels data/labels/sample.csv --mode point
     ```
   - 동작:
     - data_loader로 CSV 불러오기
     - event_store에서 이벤트 불러오기
     - labels CSV 읽기
     - plot_onset.py 실행하여 PNG 저장 (reports/plots/sample_onset.png)

3. reports/plots/ 출력
   - 파일명 형식: reports/plots/<종목>_<날짜>_onset.png
   - point 모드: onset 확정 시점에 빨간 점
   - span 모드: onset 시작~Peak 음영 처리

4. tests/test_plot_onset.py 작성
   - PNG 파일 생성 여부 확인
   - point / span 모드 모두 동작 확인
   - events와 labels가 주어졌을 때 표시 수량 일치 확인

조건:
- Python 3.10 기준
- matplotlib, seaborn 활용
- requirements.txt 추가 패키지 불필요 (기존 포함)

완료 기준:
- `python scripts/plot_test.py ...` 실행 시 PNG 파일 생성
- reports/plots/ 하위에 정상 이미지 출력
- pytest 실행 시 test_plot_onset.py 통과
````

---

✅ 이 Step 0-6을 완료하면, cand→confirm→확정 과정을 색상/명도로 구분하거나 구간(span)을 음영 처리하여 **시각적으로 온셋 탐지 과정을 검증**할 수 있습니다.
