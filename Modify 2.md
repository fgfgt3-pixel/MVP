```
[작업 패키지 B]  # 문서 및 실행 환경 정비

──────────────────────────────────────────────
[파일 수정] README.md

>>> diff
- 주요 파일: src/detect_onset.py
- 실행 예시: python scripts/step03_detect.py --config config/onset_default.yaml
+ 주요 파일: src/detection/candidate_detector.py, src/detection/confirm_detector.py,
+            src/detection/refractory_manager.py, src/detection/onset_pipeline_df.py
+ 실행 예시:
+   python scripts/step03_detect.py --csv data/sample.csv --config config/onset_default.yaml > alerts.jsonl
+   cat data/ticks.jsonl | python scripts/step03_detect.py --config config/onset_default.yaml

- 출력: tick 단위 Alert
+ 출력: Confirmed 이벤트(JSONL, stdout)

──────────────────────────────────────────────
[파일 수정] Project_overal.md

>>> diff
- 입력 구조: Tick Stream
+ 입력 구조: CSV 또는 JSONL 기반 DataFrame

- Phase 1: tick 기반 후보 → 확인 → 불응 → 경보
+ Phase 1: features_df 기반 후보 → 확인 → 불응 → 경보

- confirm_window_sec / refractory_sec
+ confirm.window_s / refractory.duration_s

──────────────────────────────────────────────
[파일 수정] Step_overal.md

>>> diff
- Step 1-3: tick 받아서 candidate → confirm → 불응
+ Step 1-3: features_df 받아서 candidate → confirm → refractory 처리 후 confirmed 이벤트 반환

- detect_onset.py 호출
+ onset_pipeline_df.run_batch(features_df) 호출

- 출력: tick 단일 alert
+ 출력: confirmed 이벤트 리스트(JSONL, trigger_axes 포함)

──────────────────────────────────────────────
[파일 수정] config/onset_default.yaml (주석/키명 보정)

>>> diff
- confirm_window_sec: 12
- persistent_n: 4
- refractory_sec: 20
+ confirm:
+   window_s: 12
+   persistent_n: 4
+ refractory:
+   duration_s: 20

- speed:
-   ret_1s_threshold: 0.0008
- participation:
-   z_vol_threshold: 2.0
- friction:
-   spread_narrowing_pct: 0.75
+ detection:
+   ret_1s_threshold: 0.0008
+   z_vol_threshold: 2.0
+   spread_narrowing_pct: 0.75
+   min_axes_required: 2

──────────────────────────────────────────────
[실행 흐름 문서 보강]

README.md / Project_overal.md 공통에 아래 삽입:

📌 전체 실행 흐름
1) CSV/JSONL 로딩 → features_df 생성
2) onset_pipeline_df.run_batch(features_df) 호출
3) confirmed 이벤트 리스트 반환
4) stdout/jsonl 출력 (Detection Only)

예시:
```

python scripts/step03_detect.py --csv input.csv --config config/onset_default.yaml > alerts.jsonl

```
```

cat ticks.jsonl | python scripts/step03_detect.py --config config/onset_default.yaml

```
──────────────────────────────────────────────
```
