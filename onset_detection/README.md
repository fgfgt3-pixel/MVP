# Onset Detection MVP

한국 주식 1틱 데이터 기반 급등 시작점(온셋) 탐지 시스템

## 프로젝트 개요

현재 단계는 **'급등 포착(Detection Only)' 전용 MVP**이다.
즉, 목표는 **놓치지 않는 빠른 탐지(Recall 우선)와 경보(Alert Event) 생성**까지이며,
체결성·슬리피지·호가분석·매매결정은 이후 Phase에서 다룬다.

### ✅ 지금 하는 일

1) 실시간(또는 CSV 리플레이) 1틱 스트림 감지
2) 핵심 지표(6~8개) 기반 후보 탐지
3) 짧은 확인창(8~15초) 내 연속성 확인
4) 경보 이벤트(JSONL 또는 stdout) 출력

### ❌ 지금 안 하는 일

- 매매/체결 시뮬레이션
- 호가창 기반 강도/패턴 분류
- 전략 진입/비중/청산
- 슬리피지·체결성 평가

## 디렉토리 구조

```
onset_detection/
├── src/           # 메인 코드
├── scripts/       # 실행 스크립트  
├── config/        # 설정 YAML
├── reports/       # 산출물(리포트/플롯)
├── data/          # 데이터 저장소
│   ├── raw/       # 원본 CSV
│   ├── clean/     # 정제된 CSV
│   ├── features/  # 파생 지표
│   ├── labels/    # 라벨 파일
│   ├── scores/    # 평가 스코어
│   └── events/    # 이벤트/온셋 로그
├── tests/         # 단위 테스트
├── logs/          # 실행 로그
└── notebooks/     # 주피터 리뷰/시각화
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

```bash
# 온셋 탐지 실행
python scripts/step03_detect.py \
  --config config/onset_default.yaml
```

※ 출력은 경보 이벤트(JSONL 또는 stdout)까지만 발생하며,
추가 매매·분류 로직은 호출되지 않음.

## Phase 개요 (재정의)

### ✅ Phase 0
- CSV/실시간 입력 경로, config, 경량 피처 로딩

### ✅ Phase 1 (현재 범위)
- Detection Only 급등 포착
  - 임계 기반 후보 탐지(절대 또는 p-임계)
  - 8~15초 확인창 + 연속성 기준(persistent_n)
  - FP 허용, Recall ≥ 65~80% 목표
  - 경보 이벤트 발생 후 종료

### ⏩ Phase 2 이후 (추후)
- 분석(호가/강도/패턴 분류)
- 47개 지표·ML 반영
- 체결성/슬리피지/노이즈 필터링
- 전략/매매 연동

## 출력 예시

Detection Only 단계에서는 아래 정보만 포함한다:

```json
{
  "timestamp": "...",
  "stock_code": "...",
  "composite_score": 3.21,
  "trigger_axes": ["price", "volume"],
  "price": 12500,
  "volume": 45000,
  "spread": 10
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