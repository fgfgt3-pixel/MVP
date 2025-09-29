# Onset Detection MVP

한국 주식 1틱 데이터 기반 급등 시작점(온셋) 탐지 시스템

## 프로젝트 개요

실시간 1틱 데이터를 처리하여 급등의 시작점을 **늦지 않게** 포착하고, 체결 가능성과 슬리피지를 고려한 자동 의사결정을 수행하는 실전형 파이프라인입니다.

### 주요 기능

- **룰 기반 온셋 탐지**: 후보→확인→불응 3단계 프로세스
- **실시간 처리**: CSV 리플레이와 키움 실시간 동등 환경
- **시각화 지원**: 포인트/구간 모드, 단계별 레이어, Event Timeline
- **체결성 검증**: 스프레드, 호가 심도, 슬리피지 추정

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

### 3. 실행 예시

```bash
# 온셋 탐지 실행
python -m src.main detect

# 설정 파일 기반 실행
python -m src.main detect --config config/onset_best.yaml

# 시각화 생성
python scripts/step05_plot_onset.py --symbol 005930 --date 2025-01-15
```

## Phase별 개발 계획

- **Phase 0**: 베이스라인 & 동형성 확보
- **Phase 1**: 온셋 탐지 엔진 v2 (후보→확인→불응)  
- **Phase 2**: 실행 가능성 가드(체결성/슬리피지) + 정책 훅
- **Phase 3**: 랭킹 & 튜닝(47지표 활용) + 스윕
- **Phase 4**: 온라인 준비(키움) & Go/No-Go

## 성과 지표

- **정확도**: In-window 탐지율, FP/hour, Precision@alert, TTA p95 ≤ 2초
- **실행성**: 체결성 통과율 ≥ 70%, 슬리피지 상한
- **수익/리스크**: PnL 분포, MaxDD, 칼마 비율

## 라이선스

MIT License