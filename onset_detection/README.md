# Onset Detection MVP

한국 주식 1틱 데이터 기반 급등 시작점(온셋) 탐지 시스템

## 프로젝트 개요

현재 단계는 **'급등 포착(Detection Only)' 전용 MVP**이다.
즉, 목표는 **놓치지 않는 빠른 탐지(Recall 우선)와 경보(Alert Event) 생성**까지이며,
체결성·슬리피지·호가분석·매매결정은 이후 Phase에서 다룬다.

### ✅ 지금 하는 일

1) CSV 또는 JSONL 데이터 기반 DataFrame 처리
2) 핵심 지표(6~8개) 기반 후보 탐지
3) 짧은 확인창(12초) 내 연속성 확인 (Delta-based validation)
4) 경보 이벤트(confirmed onset, JSONL 또는 stdout) 출력

### ❌ 지금 안 하는 일

- 매매/체결 시뮬레이션
- 호가창 기반 강도/패턴 분류
- 전략 진입/비중/청산
- 슬리피지·체결성 평가

## 디렉토리 구조

```
onset_detection/
├── src/                    # 메인 코드
│   ├── detection/          # 탐지 모듈
│   │   ├── candidate_detector.py      # 후보 탐지
│   │   ├── confirm_detector.py        # Delta-based 확인
│   │   ├── refractory_manager.py      # 불응기 관리
│   │   └── onset_pipeline.py          # 통합 파이프라인
│   ├── features/           # 피처 계산
│   ├── config_loader.py    # 설정 로더
│   └── event_store.py      # 이벤트 저장
├── scripts/                # 실행 스크립트
│   └── step03_detect.py    # Detection Only 실행
├── config/                 # 설정 YAML
│   └── onset_default.yaml  # 기본 설정
├── reports/                # 산출물(리포트/플롯)
├── data/                   # 데이터 저장소
│   ├── raw/                # 원본 CSV
│   ├── clean/              # 정제된 CSV
│   ├── features/           # 파생 지표
│   └── events/             # 이벤트/온셋 로그
├── tests/                  # 단위 테스트
└── logs/                   # 실행 로그
```

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 환경변수 설정
```

### 3. 실행 예시 (Detection Only)

#### 📌 전체 실행 흐름

1) CSV/JSONL 로딩 → features_df 생성
2) `OnsetPipelineDF.run_batch(features_df)` 호출
3) Confirmed 이벤트 리스트 반환
4) stdout/JSONL 출력 (Detection Only)

#### Features CSV로부터 Detection 실행

```bash
python scripts/step03_detect.py \
  --input data/features/sample.csv \
  --config config/onset_default.yaml \
  > alerts.jsonl
```

#### Clean CSV로부터 Features 생성 후 Detection

```bash
python scripts/step03_detect.py \
  --input data/clean/sample.csv \
  --generate-features \
  --config config/onset_default.yaml \
  > alerts.jsonl
```

#### 통계와 함께 실행

```bash
python scripts/step03_detect.py \
  --input data/features/sample.csv \
  --stats \
  > alerts.jsonl
```

#### 스트리밍 모드 (JSONL stdin)

```bash
# CSV를 JSONL로 변환 후 스트리밍 detection
python scripts/csv_replay.py --csv data/clean/sample.csv | \
  python scripts/step03_detect.py --stream --config config/onset_default.yaml

# 또는 저장된 JSONL 파일 사용
cat data/sample.jsonl | python scripts/step03_detect.py --stream
```

#### CSV → JSONL 변환 유틸리티

```bash
# CSV를 JSONL로 변환
python scripts/csv_replay.py --csv data/sample.csv --out data/sample.jsonl

# stdout으로 출력 (파이프 가능)
python scripts/csv_replay.py --csv data/sample.csv
```

※ 출력은 confirmed onset 이벤트(JSONL)만 생성되며, 추가 매매·분류 로직은 호출되지 않음.

### 실행 모드 비교

| 모드 | 명령 | 용도 |
|------|------|------|
| **배치** | `--input file.csv` | 전체 데이터 일괄 처리 |
| **스트리밍** | `--stream` (stdin) | 실시간/리플레이 tick-by-tick 처리 |

## Phase 개요 (재정의)

### ✅ Phase 0
- CSV/실시간 입력 경로, config, 경량 피처 로딩

### ✅ Phase 1 (현재 범위)
- Detection Only 급등 포착
  - features_df 기반 후보 탐지 (절대 임계, trigger_axes)
  - 12초 확인창 + Delta-based 상대 개선 검증 + persistent_n=4
  - CPD 게이트 (선택, 기본 비활성)
  - Refractory period (20초) 중복 방지
  - FP 허용, Recall ≥ 65~80% 목표
  - Confirmed onset 이벤트 출력 후 종료

### ⏩ Phase 2 이후 (추후)
- 분석(호가/강도/패턴 분류)
- 47개 지표·ML 반영
- 체결성/슬리피지/노이즈 필터링
- 전략/매매 연동

## 주요 파일

- **src/detection/candidate_detector.py**: 후보 탐지 (절대 임계, trigger_axes)
- **src/detection/confirm_detector.py**: Delta-based 확인 (상대 개선 검증)
- **src/detection/refractory_manager.py**: 불응기 관리 (중복 방지)
- **src/detection/onset_pipeline.py**: 통합 파이프라인 (OnsetPipelineDF 클래스)
- **scripts/step03_detect.py**: CLI 실행 스크립트

## 출력 예시

Detection Only 단계에서는 confirmed onset 이벤트만 출력한다:

```json
{
  "ts": 1704067212500,
  "event_type": "onset_confirmed",
  "stock_code": "005930",
  "confirmed_from": 1704067205000,
  "evidence": {
    "axes": ["price", "volume"],
    "onset_strength": 0.67,
    "ret_1s": 0.0012,
    "z_vol_1s": 2.5,
    "spread": 50,
    "delta_ret": 0.0008,
    "delta_zvol": 1.2
  }
}
```

※ 호가창 스냅샷/체결성/매매 시그널은 Phase2+

## 성과 지표 (Detection Only 기준)

* Recall ≥ 65~80% (놓침 최소화)
* Alert Latency p50 ≤ 8~12초
* FP/hour ≤ 20~50 (허용 범위, 이후 단계에서 필터링)
* Precision ≥ 40~60% (참고용)

※ 손익, 체결성, 슬리피지는 평가 제외

## 이후 개발 계획

✅ (Phase 2) 경보 후 분석 모듈
✅ (Phase 3) ML·확장 지표·필터링
✅ (Phase 4) 매매 전략/체결/슬리피지 반영

📌 현재는 "탐지→경보까지"를 최우선으로 완성 중

## 라이선스

MIT License