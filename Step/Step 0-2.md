알겠습니다 👍 앞서 지적해주신 사항(📌 `python-dotenv`, `pytest`, Pydantic 스키마, CLI 옵션)을 반영해서 **Step 0-2 실행 프롬프트**를 다시 제안드립니다.

---

# 📌 Step 0-2 실행 프롬프트 (Claude Code용, 수정 반영版)

````
작업: Step 0-2 — 설정 로더 & 경로 정의 구현

요구사항:

1. config/onset_default.yaml 생성
   - 아래 기본 내용 포함:
     paths:
       data_raw: data/raw
       data_clean: data/clean
       reports: reports
       plots: reports/plots
     onset:
       refractory_s: 120
       confirm_window_s: 20
       score_threshold: 2.0

2. src/config_loader.py 작성
   - 기능: YAML 불러오기, dict 또는 Pydantic BaseModel로 반환
   - .env 값 병합 지원 (python-dotenv 사용)
   - Pydantic 스키마 구조:
     ```python
     from pydantic import BaseModel

     class Paths(BaseModel):
         data_raw: str
         data_clean: str
         reports: str
         plots: str

     class Onset(BaseModel):
         refractory_s: int
         confirm_window_s: int
         score_threshold: float

     class Config(BaseModel):
         paths: Paths
         onset: Onset
     ```
   - CLI 옵션:
     - `python -m src.config_loader --print` 실행 시 현재 설정(YAML + .env 병합)을 출력
     - argparse + pprint 활용
   - 엔트리포인트: `if __name__ == "__main__":` 블록에서 CLI 처리

3. src/utils/paths.py 작성
   - 기능: 상대경로를 절대경로로 변환
   - 디렉토리가 없으면 자동 생성 (`os.makedirs(exist_ok=True)`)

4. tests/test_config_loader.py 작성
   - onset_default.yaml 불러오기 테스트
   - .env 병합 테스트
   - paths 유틸리티 자동 생성 확인

조건:
- Python 3.10 기준
- requirements.txt 업데이트 필요:
````

pandas>=2.0
numpy>=1.24
matplotlib>=3.7
seaborn>=0.12
pyyaml>=6.0
pydantic>=2.0
pyarrow>=12.0
python-dotenv>=1.0
pytest>=7.0

```

완료 기준:
- `python -m src.config_loader --print` 실행 시 정상적으로 YAML + .env 병합 출력
- pytest 실행 시 모든 테스트 통과
```

---

✅ 이렇게 정리하면, Claude Code는 설정 로더, 경로 유틸리티, 테스트까지 한 번에 구현할 수 있습니다.

👉 다음 Step은 \*\*Step 0-3 (데이터 로딩 & 리플레이 엔진 스켈레톤)\*\*인데, 이 단계도 같은 포맷으로 이어서 정리해드릴까요?
