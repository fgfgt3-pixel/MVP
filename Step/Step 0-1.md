알겠습니다. 이전 의문사항을 반영해 \*\*Step 0-1 (프로젝트 스캐폴딩)\*\*을 다시 정리해드리겠습니다. Claude Code에게 바로 전달할 수 있도록 지시문 형태로 작성합니다.

---

# 📌 Step 0-1 — 프로젝트 스캐폴딩

**Phase**: Phase 0 (사전 준비)
**목표**: onset\_detection MVP 개발을 위한 기본 디렉토리/환경을 세팅

---

## 1. 작업 디렉토리

* 루트 경로:

  ```
  C:\Users\fgfgt\OneDrive\바탕 화면\MVP\onset_detection\
  ```
* `onset_detection` 폴더 안을 **Git init + 코드 루트**로 사용

---

## 2. 폴더 생성

아래 디렉토리를 모두 생성 (초기에는 일부만 사용하지만, 미리 만들어두면 추후 코드 실행 오류 방지)

```
src/           # 메인 코드
scripts/       # 실행 스크립트
config/        # 설정 YAML
reports/       # 산출물(리포트/플롯)
data/raw/      # 원본 CSV
data/clean/    # 정제된 CSV
data/features/ # 파생 지표
data/labels/   # 라벨 파일
data/scores/   # 평가 스코어
data/events/   # 이벤트/온셋 로그
tests/         # 단위 테스트
logs/          # 실행 로그
notebooks/     # 주피터 리뷰/시각화 (옵션)
```

---

## 3. 파일 생성

* `README.md` : 프로젝트 개요 + 실행 방법 초안
* `requirements.txt` : 기본 패키지 (버전은 느슨하게, >= 로만)

  ```txt
  pandas>=2.0
  numpy>=1.24
  matplotlib>=3.7
  seaborn>=0.12
  pyyaml>=6.0
  pydantic>=2.0
  pyarrow>=12.0
  ```
* `.gitignore` : `data/*`, `logs/*`, `.env` 등 제외
* `.env.example` : 환경변수 예시(API 키, 데이터 경로)
* `pyproject.toml` (선택): 프로젝트 메타/의존성 선언

---

## 4. Python 환경

* Python **3.10.x** 권장 (PyTorch 등 확장 가능성을 고려)
* `pip install -r requirements.txt`로 의존성 설치 확인

---

## 5. 완료 기준

* 모든 디렉토리 및 초기 파일 생성됨
* `requirements.txt` 설치 성공 로그 확인
* `README.md` 안에 **실행 예시 초안** 기재
  (예: `python -m src.main detect`)

---

👉 이 Step이 완료되면, \*\*Step 0-2 (설정 로더 & 경로 정의)\*\*로 진행할 수 있습니다.

---

원하시면 제가 Claude Code에게 바로 전달 가능한 **실행 프롬프트** 형태로 바꿔드릴까요?
