```
[📋 작업 패키지 C - 최종 실행 계획]

──────────────────────────────────────────────
⚠️ 문제 정리
- 현재 step03_detect.py: DataFrame 배치 처리 전용 (--input file.csv)
- Modify 4.md 요구: JSONL line-by-line → run_tick(raw) 방식
- OnsetPipelineDF: run_batch()만 있고 run_tick() 없음

──────────────────────────────────────────────
🔧 대응 방안 선택

Option A: 최소 수정
- csv_replay.py 생성 (CSV → JSONL 변환)
- step03_detect.py는 기존 DataFrame 배치 방식 유지
- Detection 실행은 여전히 “--input file.csv → features_df → pipeline.run_batch()”
- 장점: 안정성, 변경 최소화
- 단점: Modify 4 요구(스트리밍)는 불완전 충족

Option B: 스트리밍 지원 추가 (**권장**)
- OnsetPipelineDF에 run_tick() 메서드 추가
  → 내부적으로 window 유지 → candidate/confirm/refractory 호출
- step03_detect.py에 모드 추가 (--stream)
  → stdin/JSONL line-by-line 읽어 pipe.run_tick(raw) 호출
- README.md에 두 모드 문서화:
  * 배치 모드 (--input CSV/JSONL → run_batch)
  * 스트리밍 모드 (--stream stdin → run_tick)
- 장점: Modify 4 요구사항 충족, 실시간/리플레이 가능
- 단점: 구현 복잡도 증가

──────────────────────────────────────────────
✅ 실행 계획 (Option B 적용)

1. **scripts/csv_replay.py**
   - CSV → JSONL 변환기 (완료)

2. **src/detection/onset_pipeline_df.py**
   - run_batch(df) 기존 유지
   - run_tick(raw) 추가 구현 (tick 단위)
   - 내부 버퍼 관리 + candidate/confirm/refractory 호출

3. **scripts/step03_detect.py**
   - --input file.csv/jsonl → run_batch()
   - --stream → stdin 읽기, run_tick(raw) 호출

4. **README.md**
   - CSV → JSONL 변환 예시
   - step03_detect.py 배치 모드 / 스트리밍 모드 실행 예시 추가

5. **tests/test_step03_stdin.py**
   - stdin 가짜 입력 → run_tick() 스트리밍 동작 확인

──────────────────────────────────────────────
📌 최종 목표
- 배치 & 스트리밍 모드 모두 지원
- CSV/JSONL → batch
- JSONL stdin → stream
- Modify 4 요구사항 완전 충족
```
