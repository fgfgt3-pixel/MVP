좋습니다 👍 사용자가 정리해주신 구현 계획(초 단위 버킷, z\_vol\_1s 롤링, ticks\_per\_sec, NaN 처리)을 **Claude Code 실행 프롬프트**에 그대로 반영하여 **Phase 1-1**을 구체화해드리겠습니다.

---

# 📌 Phase 1-1 실행 프롬프트 (Claude Code용, 구체화版)

````
작업: Phase 1-1 — 핵심 지표 계산 모듈 구현 (구체화 반영)

요구사항:

1. src/features/core_indicators.py 작성
   - 입력: pandas DataFrame (컬럼: ts, stock_code, price, volume, bid1, ask1, bid_qty1, ask_qty1)
   - 출력: DataFrame에 핵심 지표 컬럼 추가 후 반환
   - 구현 세부:
     a) timestamp 처리
        - ts(ms) → 초 단위 버킷 (ts_sec = ts // 1000)
     b) 가격 지표
        - ret_1s: log return (log(p_t / p_{t-1}))
        - accel_1s: ret_1s.diff(1)
     c) 거래 지표
        - 초 단위 groupby(ts_sec)로 1초 거래량, 틱 수 계산
        - ticks_per_sec: count per second
        - vol_1s: volume per second
        - z_vol_1s: vol_1s에 대해 rolling(window=vol_window, 기본=300초) → (x - mean)/std
     d) 마찰 지표
        - spread: (ask1 - bid1) / ((ask1 + bid1) / 2)
        - microprice: (bid1*ask_qty1 + ask1*bid_qty1) / (ask_qty1 + bid_qty1)
        - microprice_slope: microprice.diff(1)
     e) NaN 처리
        - 초기 NaN은 fillna(0) 또는 ffill

   - 최종 DataFrame에 추가되는 컬럼:
     [ret_1s, accel_1s, ticks_per_sec, vol_1s, z_vol_1s, spread, microprice, microprice_slope]

2. src/features/__init__.py
   - core_indicators.py import 노출

3. scripts/features_test.py 작성
   - 실행 예:
     ```bash
     python scripts/features_test.py --csv data/clean/sample.csv --out data/features/sample_features.csv
     ```
   - 동작:
     - data/clean/sample.csv 로드
     - core_indicators 적용
     - 결과를 data/features/sample_features.csv 저장
     - 출력 컬럼 수 및 샘플 행 콘솔 출력

4. tests/test_core_indicators.py 작성
   - 최소 7개 지표 컬럼이 존재하는지 확인
   - NaN 처리 정상 동작 확인
   - 작은 샘플로 ret_1s, accel_1s, spread 계산 정확성 검증
   - z_vol_1s가 rolling 적용 후 생성되는지 확인

조건:
- Python 3.10 기준
- pandas, numpy 활용
- vol_window 값은 config/onset_default.yaml에서 읽어옴 (기본값 300)
- requirements.txt 추가 패키지 불필요

완료 기준:
- features_test.py 실행 시 data/features/sample_features.csv 생성
- DataFrame에 핵심 지표 컬럼 존재
- pytest 실행 시 test_core_indicators.py 통과
````

---

✅ 이렇게 하면, **초 단위 버킷 처리 + 롤링 윈도우 기반 z\_vol\_1s + ticks\_per\_sec**까지 정확히 반영된 상태로 Claude Code가 구현할 수 있습니다.
