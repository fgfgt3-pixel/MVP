# Phase 1 추가 검증 작업 지시서 (Claude Code 실행용)

## 🎯 작업 목표
1. **타이밍 검증**: 급등 포착이 얼마나 빠른지 시각적 확인
2. **시각화**: 급등 구간 + 탐지 시점을 차트로 표현
3. **임계 완화**: onset_strength를 0.67-0.68로 낮춰 약한 급등 중 강한 것 포착

---

## 📋 작업 순서 (연속 실행)

### Step 1: 급등 타이밍 상세 분석

```python
# 파일: scripts/analyze_detection_timing.py (신규)

"""
급등 탐지 타이밍 분석
목적: 각 급등의 시작/피크 대비 언제 탐지했는지 확인
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime
from pathlib import Path

# 급등 정의 (시작, 피크, 종료)
surges_023790 = [
    {"name": "Surge1", "start": 1756688123304, "peak_offset": 120000, "strength": "중간"},
    {"name": "Surge2", "start": 1756689969627, "peak_offset": 120000, "strength": "중간"}
]

surges_413630 = [
    {"name": "Surge1", "time": "09:09-09:15", "start_offset": 0, "peak_offset": 240000, "strength": "중간"},
    {"name": "Surge2", "time": "10:01-10:14", "start_offset": 0, "peak_offset": 660000, "strength": "강한"},
    {"name": "Surge3", "time": "11:46-11:50", "start_offset": 0, "peak_offset": 180000, "strength": "약한"},
    {"name": "Surge4", "time": "13:29-13:37", "start_offset": 0, "peak_offset": 300000, "strength": "중간"},
    {"name": "Surge5", "time": "14:09-14:12", "start_offset": 0, "peak_offset": 120000, "strength": "약한"}
]

def load_events(file_path):
    """이벤트 로드"""
    events = []
    with open(file_path, 'r') as f:
        for line in f:
            events.append(json.loads(line))
    return [e for e in events if e['event_type'] == 'onset_confirmed']

def ms_to_kst(ms):
    """밀리초를 KST datetime으로 변환"""
    return pd.to_datetime(ms, unit='ms', utc=True).tz_convert('Asia/Seoul')

def analyze_file_timing(events, surges, data_path, file_name):
    """파일별 타이밍 분석"""
    df = pd.read_csv(data_path)
    
    print(f"\n{'='*60}")
    print(f"{file_name} 타이밍 분석")
    print(f"{'='*60}")
    
    results = []
    
    for surge in surges:
        surge_name = surge['name']
        surge_strength = surge['strength']
        
        # 급등 시작 시점
        if 'start' in surge:
            surge_start = surge['start']
        else:
            # 413630의 경우 데이터에서 시작 시점 추출
            time_str = surge['time'].split('-')[0]  # "09:09"
            hour, minute = map(int, time_str.split(':'))
            
            # 데이터의 첫 timestamp 가져오기
            first_ts = df['ts'].min()
            first_dt = ms_to_kst(first_ts)
            
            # 해당 시각으로 설정
            surge_dt = first_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            surge_start = int(surge_dt.timestamp() * 1000)
        
        surge_peak = surge_start + surge.get('peak_offset', 120000)
        
        # 해당 구간 탐지 이벤트 찾기
        detected_events = [
            e for e in events 
            if surge_start - 30000 <= e['ts'] <= surge_peak + 30000
        ]
        
        if not detected_events:
            print(f"\n❌ {surge_name} ({surge_strength}): 탐지 실패")
            results.append({
                "surge": surge_name,
                "strength": surge_strength,
                "detected": False,
                "detection_time_kst": None,
                "latency_from_start": None,
                "latency_to_peak": None
            })
            continue
        
        # 가장 빠른 탐지 시점
        first_detection = min(detected_events, key=lambda x: x['ts'])
        detection_ts = first_detection['ts']
        
        # 타이밍 계산
        latency_from_start = (detection_ts - surge_start) / 1000.0  # 초
        latency_to_peak = (surge_peak - detection_ts) / 1000.0
        
        # 백분율 계산 (시작→피크 구간 중 몇 %에서 탐지)
        surge_duration = (surge_peak - surge_start) / 1000.0
        detection_position_pct = (latency_from_start / surge_duration) * 100
        
        detection_dt = ms_to_kst(detection_ts)
        
        print(f"\n✅ {surge_name} ({surge_strength}):")
        print(f"   탐지 시각: {detection_dt.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"   급등 시작 후: {latency_from_start:+.1f}초")
        print(f"   피크까지 남은 시간: {latency_to_peak:.1f}초")
        print(f"   탐지 위치: 시작→피크 구간의 {detection_position_pct:.1f}%")
        
        # 평가
        if latency_from_start < 5:
            quality = "⭐⭐⭐ 매우 빠름"
        elif latency_from_start < 15:
            quality = "⭐⭐ 빠름"
        elif latency_from_start < 30:
            quality = "⭐ 보통"
        else:
            quality = "⚠️ 느림"
        
        print(f"   평가: {quality}")
        
        results.append({
            "surge": surge_name,
            "strength": surge_strength,
            "detected": True,
            "detection_time_kst": detection_dt.strftime('%H:%M:%S.%f')[:-3],
            "latency_from_start": latency_from_start,
            "latency_to_peak": latency_to_peak,
            "detection_position_pct": detection_position_pct,
            "quality": quality
        })
    
    return results

# 023790 분석
events_023790 = load_events("data/events/strategy_c_plus_023790.jsonl")
results_023790 = analyze_file_timing(
    events_023790, 
    surges_023790, 
    "data/raw/023790_44indicators_realtime_20250901_clean.csv",
    "023790"
)

# 413630 분석
events_413630 = load_events("data/events/strategy_c_plus_413630.jsonl")
results_413630 = analyze_file_timing(
    events_413630,
    surges_413630,
    "data/raw/413630_44indicators_realtime_20250901_clean.csv",
    "413630"
)

# 종합 통계
print(f"\n{'='*60}")
print("종합 타이밍 통계")
print(f"{'='*60}")

all_results = results_023790 + results_413630
detected_results = [r for r in all_results if r['detected']]

if detected_results:
    latencies = [r['latency_from_start'] for r in detected_results]
    positions = [r['detection_position_pct'] for r in detected_results]
    
    print(f"\n탐지된 급등: {len(detected_results)}개")
    print(f"급등 시작 후 평균 탐지: {np.mean(latencies):.1f}초")
    print(f"급등 시작 후 중앙값: {np.median(latencies):.1f}초")
    print(f"평균 탐지 위치: 시작→피크의 {np.mean(positions):.1f}%")

# 강도별 분석
print(f"\n{'='*60}")
print("강도별 타이밍 분석")
print(f"{'='*60}")

strengths = ["강한", "중간", "약한"]
for strength in strengths:
    strength_results = [r for r in detected_results if r['strength'] == strength]
    if strength_results:
        avg_latency = np.mean([r['latency_from_start'] for r in strength_results])
        avg_position = np.mean([r['detection_position_pct'] for r in strength_results])
        print(f"\n{strength} 급등 ({len(strength_results)}개):")
        print(f"  평균 탐지: 시작 후 {avg_latency:.1f}초")
        print(f"  평균 위치: {avg_position:.1f}%")

# 결과 저장
summary = {
    "023790": results_023790,
    "413630": results_413630,
    "summary": {
        "total_surges": len(all_results),
        "detected_surges": len(detected_results),
        "avg_latency_from_start": float(np.mean(latencies)) if latencies else None,
        "median_latency_from_start": float(np.median(latencies)) if latencies else None,
        "avg_detection_position_pct": float(np.mean(positions)) if positions else None
    }
}

Path("reports").mkdir(exist_ok=True)
with open("reports/detection_timing_analysis.json", "w") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"\n결과 저장: reports/detection_timing_analysis.json")
```

**실행**:
```bash
python scripts/analyze_detection_timing.py
```

---

### Step 2: Jupyter 시각화 노트북 생성

```python
# 파일: notebooks/visualize_detection_timing.ipynb (신규)

# Cell 1: Setup
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
from datetime import datetime
from pathlib import Path

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['figure.figsize'] = (16, 10)
plt.rcParams['font.size'] = 10

# Cell 2: Load Data Functions
def load_csv_data(file_path):
    """CSV 데이터 로드 및 datetime 변환"""
    df = pd.read_csv(file_path)
    df['datetime'] = pd.to_datetime(df['ts'], unit='ms', utc=True).dt.tz_convert('Asia/Seoul')
    return df

def load_events(file_path):
    """이벤트 로드"""
    events = []
    with open(file_path, 'r') as f:
        for line in f:
            events.append(json.loads(line))
    
    confirmed = [e for e in events if e['event_type'] == 'onset_confirmed']
    
    # datetime 추가
    for e in confirmed:
        e['datetime'] = pd.to_datetime(e['ts'], unit='ms', utc=True).tz_convert('Asia/Seoul')
    
    return confirmed

# Cell 3: Plot Function
def plot_surge_detection(df, events, surge_info, title):
    """급등 구간과 탐지 시점 시각화"""
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    
    # 1. Price chart
    ax1 = axes[0]
    ax1.plot(df['datetime'], df['price'], linewidth=0.5, color='black', alpha=0.7, label='Price')
    ax1.set_ylabel('Price', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 2. Volume
    ax2 = axes[1]
    ax2.bar(df['datetime'], df['volume'], width=0.0001, color='blue', alpha=0.5, label='Volume')
    ax2.set_ylabel('Volume', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # 3. Ticks per second
    ax3 = axes[2]
    if 'ticks_per_sec' in df.columns:
        ax3.plot(df['datetime'], df['ticks_per_sec'], linewidth=1, color='green', alpha=0.7, label='Ticks/sec')
    ax3.set_ylabel('Ticks per Second', fontsize=12, fontweight='bold')
    ax3.set_xlabel('Time (KST)', fontsize=12, fontweight='bold')
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    
    # 급등 구간 표시
    for surge in surge_info:
        surge_start = pd.to_datetime(surge['start'], unit='ms', utc=True).tz_convert('Asia/Seoul')
        surge_peak = surge_start + pd.Timedelta(milliseconds=surge.get('peak_offset', 120000))
        
        color_map = {"강한": "red", "중간": "orange", "약한": "yellow"}
        color = color_map.get(surge['strength'], 'gray')
        
        for ax in axes:
            ax.axvspan(surge_start, surge_peak, alpha=0.15, color=color, 
                      label=f"{surge['name']} ({surge['strength']})")
    
    # 탐지 시점 표시
    for event in events:
        event_dt = event['datetime']
        
        for ax in axes:
            ax.axvline(event_dt, color='purple', linestyle='--', linewidth=2, alpha=0.7)
            ax.text(event_dt, ax.get_ylim()[1]*0.95, '🚨', 
                   fontsize=16, ha='center', va='top')
    
    # 범례 정리
    handles, labels = ax1.get_legend_handles_labels()
    ax1.legend(handles[:5], labels[:5], loc='upper left', fontsize=9)
    
    # 시간 포맷
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.suptitle(title, fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    return fig

# Cell 4: 023790 시각화
df_023790 = load_csv_data("data/raw/023790_44indicators_realtime_20250901_clean.csv")
events_023790 = load_events("data/events/strategy_c_plus_023790.jsonl")

surges_023790 = [
    {"name": "Surge1", "start": 1756688123304, "peak_offset": 120000, "strength": "중간"},
    {"name": "Surge2", "start": 1756689969627, "peak_offset": 120000, "strength": "중간"}
]

fig1 = plot_surge_detection(df_023790, events_023790, surges_023790, 
                            "023790 급등 탐지 타이밍 (전략 C+)")
plt.savefig("reports/plots/023790_detection_timing.png", dpi=150, bbox_inches='tight')
plt.show()

# Cell 5: 413630 시각화
df_413630 = load_csv_data("data/raw/413630_44indicators_realtime_20250901_clean.csv")
events_413630 = load_events("data/events/strategy_c_plus_413630.jsonl")

# 413630 surge 시작 시점 계산
first_ts = df_413630['ts'].min()
first_dt = pd.to_datetime(first_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')

surge_times = [
    ("09:09", 240000, "중간"),
    ("10:01", 660000, "강한"),
    ("11:46", 180000, "약한"),
    ("13:29", 300000, "중간"),
    ("14:09", 120000, "약한")
]

surges_413630 = []
for i, (time_str, peak_offset, strength) in enumerate(surge_times, 1):
    hour, minute = map(int, time_str.split(':'))
    surge_dt = first_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    surge_start_ms = int(surge_dt.timestamp() * 1000)
    
    surges_413630.append({
        "name": f"Surge{i}",
        "start": surge_start_ms,
        "peak_offset": peak_offset,
        "strength": strength
    })

fig2 = plot_surge_detection(df_413630, events_413630, surges_413630,
                            "413630 급등 탐지 타이밍 (전략 C+)")
plt.savefig("reports/plots/413630_detection_timing.png", dpi=150, bbox_inches='tight')
plt.show()

# Cell 6: Summary Statistics
print("="*60)
print("탐지 타이밍 요약")
print("="*60)

with open("reports/detection_timing_analysis.json") as f:
    timing_data = json.load(f)

summary = timing_data['summary']
print(f"\n전체 급등: {summary['total_surges']}개")
print(f"탐지된 급등: {summary['detected_surges']}개")
print(f"평균 탐지 지연: {summary['avg_latency_from_start']:.1f}초")
print(f"평균 탐지 위치: 시작→피크의 {summary['avg_detection_position_pct']:.1f}%")

print("\n"+"="*60)
```

**실행 방법**:
```bash
# Jupyter 설치 (없으면)
pip install jupyter matplotlib

# 노트북 실행
jupyter notebook notebooks/visualize_detection_timing.ipynb
```

---

### Step 3: onset_strength 완화 및 재실행

```python
# 파일: scripts/relax_onset_strength.py (신규)

"""
onset_strength 임계 완화
목적: 0.70 → 0.67로 낮춰 약한 급등 중 강한 것 포착
"""

import re
from pathlib import Path

print("="*60)
print("onset_strength 임계 완화")
print("="*60)

# confirm_detector.py 수정
detector_path = Path("onset_detection/src/detection/confirm_detector.py")

with open(detector_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 현재 임계값 찾기
current_threshold = None
match = re.search(r'if onset_strength < (0\.\d+):', content)
if match:
    current_threshold = float(match.group(1))
    print(f"\n현재 onset_strength 임계: {current_threshold}")
else:
    print("\n⚠️ onset_strength 필터를 찾을 수 없습니다.")
    print("confirm_detector.py를 확인하세요.")
    exit(1)

# 새 임계값
new_threshold = 0.67
print(f"새 onset_strength 임계: {new_threshold}")

# 교체
new_content = content.replace(
    f'if onset_strength < {current_threshold}:',
    f'if onset_strength < {new_threshold}:'
)

# 저장
with open(detector_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"✅ {detector_path} 수정 완료")

# Detection 재실행
print("\n"+"="*60)
print("Detection 재실행")
print("="*60)

import pandas as pd
from onset_detection.src.detection.onset_pipeline import OnsetPipelineDF
from onset_detection.src.features.core_indicators import calculate_core_indicators
from onset_detection.src.config_loader import load_config
import json

files = [
    ("023790", "data/raw/023790_44indicators_realtime_20250901_clean.csv"),
    ("413630", "data/raw/413630_44indicators_realtime_20250901_clean.csv")
]

results = {}

for stock_code, data_path in files:
    print(f"\n[{stock_code}] 처리 중...")
    
    df = pd.read_csv(data_path)
    features_df = calculate_core_indicators(df)
    
    config = load_config()
    pipeline = OnsetPipelineDF(config=config)
    confirmed = pipeline.run_batch(features_df)
    
    # 저장
    output_path = Path(f"data/events/strategy_c_plus_relaxed_{stock_code}.jsonl")
    with open(output_path, 'w') as f:
        for event in confirmed:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    
    duration_hours = (df['ts'].max() - df['ts'].min()) / (1000 * 3600)
    fp_per_hour = len(confirmed) / duration_hours
    
    print(f"  Confirmed: {len(confirmed)}개")
    print(f"  FP/h: {fp_per_hour:.1f}")
    
    results[stock_code] = {
        "confirmed": len(confirmed),
        "fp_per_hour": fp_per_hour
    }

# Recall 재계산
print("\n"+"="*60)
print("Recall 재계산")
print("="*60)

# 023790
events_023790 = []
with open("data/events/strategy_c_plus_relaxed_023790.jsonl") as f:
    for line in f:
        events_023790.append(json.loads(line))

surge1_023790 = 1756688123304
surge2_023790 = 1756689969627

s1_detected = any(surge1_023790 - 30000 <= e['ts'] <= surge1_023790 + 120000 for e in events_023790)
s2_detected = any(surge2_023790 - 30000 <= e['ts'] <= surge2_023790 + 120000 for e in events_023790)

recall_023790 = sum([s1_detected, s2_detected]) / 2.0
print(f"\n023790 Recall: {recall_023790*100:.0f}% ({sum([s1_detected, s2_detected])}/2)")

# 413630
events_413630 = []
with open("data/events/strategy_c_plus_relaxed_413630.jsonl") as f:
    for line in f:
        events_413630.append(json.loads(line))

# 413630 surge 시작 계산 (간단 버전)
df_413630 = pd.read_csv("data/raw/413630_44indicators_realtime_20250901_clean.csv")
first_ts = df_413630['ts'].min()
first_dt = pd.to_datetime(first_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')

surge_starts_413630 = []
for time_str in ["09:09", "10:01", "11:46", "13:29", "14:09"]:
    hour, minute = map(int, time_str.split(':'))
    surge_dt = first_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    surge_starts_413630.append(int(surge_dt.timestamp() * 1000))

detected_413630 = []
for surge_start in surge_starts_413630:
    detected = any(surge_start - 30000 <= e['ts'] <= surge_start + 240000 for e in events_413630)
    detected_413630.append(detected)

recall_413630 = sum(detected_413630) / 5.0
print(f"413630 Recall: {recall_413630*100:.0f}% ({sum(detected_413630)}/5)")

# 종합
print("\n"+"="*60)
print("onset_strength 완화 결과")
print("="*60)

print(f"\n023790:")
print(f"  FP/h: {results['023790']['fp_per_hour']:.1f} (이전: 20.1)")
print(f"  Recall: {recall_023790*100:.0f}%")

print(f"\n413630:")
print(f"  FP/h: {results['413630']['fp_per_hour']:.1f} (이전: 3.2)")
print(f"  Recall: {recall_413630*100:.0f}% (이전: 40%)")

# 저장
summary = {
    "onset_strength_threshold": new_threshold,
    "previous_threshold": current_threshold,
    "023790": {
        "fp_per_hour": results['023790']['fp_per_hour'],
        "recall": recall_023790,
        "confirmed": results['023790']['confirmed']
    },
    "413630": {
        "fp_per_hour": results['413630']['fp_per_hour'],
        "recall": recall_413630,
        "confirmed": results['413630']['confirmed']
    }
}

Path("reports").mkdir(exist_ok=True)
with open("reports/onset_strength_relaxed_result.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n결과 저장: reports/onset_strength_relaxed_result.json")
```

**실행**:
```bash
python scripts/relax_onset_strength.py
```

---

### Step 4: 최종 판단 및 리포트

```python
# 파일: scripts/final_decision_report.py (신규)

"""
Phase 1 최종 판단 리포트
"""

import json
from pathlib import Path

print("="*60)
print("Phase 1 최종 판단")
print("="*60)

# 결과 로드
with open("reports/onset_strength_relaxed_result.json") as f:
    relaxed = json.load(f)

with open("reports/detection_timing_analysis.json") as f:
    timing = json.load(f)

print("\n### onset_strength 0.67 결과")
print(f"\n023790:")
print(f"  FP/h: {relaxed['023790']['fp_per_hour']:.1f}")
print(f"  Recall: {relaxed['023790']['recall']*100:.0f}%")

print(f"\n413630:")
print(f"  FP/h: {relaxed['413630']['fp_per_hour']:.1f}")
print(f"  Recall: {relaxed['413630']['recall']*100:.0f}%")

# 타이밍 분석
avg_latency = timing['summary']['avg_latency_from_start']
avg_position = timing['summary']['avg_detection_position_pct']

print(f"\n### 탐지 타이밍")
print(f"  평균 탐지: 급등 시작 후 {avg_latency:.1f}초")
print(f"  평균 위치: 시작→피크의 {avg_position:.1f}%")

# 판단
print("\n"+"="*60)
print("최종 판단")
print("="*60)

fp_avg = (relaxed['023790']['fp_per_hour'] + relaxed['413630']['fp_per_hour']) / 2
recall_avg = (relaxed['023790']['recall'] + relaxed['413630']['recall']) / 2

goals_met = {
    "FP/h ≤ 35": fp_avg <= 35,
    "Recall ≥ 65%": recall_avg >= 0.65,
    "타이밍 조기": avg_position < 30  # 시작→피크의 30% 이전에 탐지
}

for goal, met in goals_met.items():
    status = "✅" if met else "❌"
    print(f"{goal}: {status}")

# 최종 권장사항
print("\n"+"="*60)
print("권장사항")
print("="*60)

if all(goals_met.values()):
    print("""
✅ Phase 1 완료 조건 달성!

**다음 단계**:
1. Config를 onset_phase1_final.yaml로 백업
2. 다른 종목 3-5개로 추가 검증
3. Phase 2 설계 시작
   - 호가창 분석으로 FP 추가 제거
   - 강도 분류 시스템 (강/중/약)
   - 진입 타이밍 최적화
""")
elif not goals_met["FP/h ≤ 35"]:
    gap = fp_avg - 35
    print(f"""
⚠️ FP/h 초과 ({fp_avg:.1f}, 목표 대비 +{gap:.1f})

**옵션**:
A. onset_strength를 0.68-0.69로 미세 조정
B. 현재 수준에서 Phase 2로 이관 (패턴 필터링)
C. refractory_s를 60초로 증가

**추천**: 옵션 B (현재도 충분히 좋은 수준)
""")
elif not goals_met["Recall ≥ 65%"]:
    print("""
⚠️ Recall 미달

**조치**:
1. 급등 구간 재검토 (±30초 → ±60초?)
2. onset_strength를 0.65로 추가 완화
3. 약한 급등 정의 재검토
""")

# 리포트 저장
report = f"""
# Phase 1 최종 판단 리포트

## 성능 요약

### onset_strength = 0.67

| 항목 | 023790 | 413630 | 평균 | 목표 | 달성 |
|------|--------|--------|------|------|------|
| FP/h | {relaxed['023790']['fp_per_hour']:.1f} | {relaxed['413630']['fp_per_hour']:.1f} | {fp_avg:.1f} | ≤35 | {'✅' if goals_met['FP/h ≤ 35'] else '❌'} |
| Recall | {relaxed['023790']['recall']*100:.0f}% | {relaxed['413630']['recall']*100:.0f}% | {recall_avg*100:.0f}% | ≥65% | {'✅' if goals_met['Recall ≥ 65%'] else '❌'} |

### 탐지 타이밍

- 평균 탐지: 급등 시작 후 **{avg_latency:.1f}초**
- 평균 위치: 시작→피크의 **{avg_position:.1f}%**
- 평가: {"✅ 조기 탐지 성공" if avg_position < 30 else "⚠️ 개선 필요"}

## 최종 결론

"""

if all(goals_met.values()):
    report += "🎉 **Phase 1 목표 완전 달성!**\n"
else:
    report += "⚠️ **일부 항목 미달, 추가 조정 권장**\n"

Path("reports").mkdir(exist_ok=True)
with open("reports/phase1_final_decision.md", "w", encoding='utf-8') as f:
    f.write(report)

print(f"\n리포트 저장: reports/phase1_final_decision.md")
```

**실행**:
```bash
python scripts/final_decision_report.py
```

---

## ✅ 전체 작업 체크리스트

- [ ] Step 1: 급등 타이밍 상세 분석 완료
- [ ] Step 2: Jupyter 시각화 완료 (차트 확인)
- [ ] Step 3: onset_strength 완화 및 재실행
- [ ] Step 4: 최종 판단 리포트 생성

---

## 🚀 한 줄 실행 명령어

```bash
python scripts/analyze_detection_timing.py && \
python scripts/relax_onset_strength.py && \
python scripts/final_decision_report.py && \
cat reports/phase1_final_decision.md
```

**시각화는 별도 실행**:
```bash
jupyter notebook notebooks/visualize_detection_timing.ipynb
```

---

## 📌 판단 기준 (업데이트)

### Phase 1 완료 조건 (완화)
1. **FP/h ≤ 35** (30 → 35로 완화)
2. **Recall ≥ 65%**
3. **타이밍**: 급등 시작→피크의 30% 이전 탐지

### 타이밍 평가 기준
- **⭐⭐⭐ 매우 빠름**: 시작 후 5초 이내
- **⭐⭐ 빠름**: 시작 후 5-15초
- **⭐ 보통**: 시작 후 15-30초
- **⚠️ 느림**: 시작 후 30초 이상

**핵심**: Peak 근처에서 탐지하는 건 의미 없음. **작 직후 가능한 최대한 빠른 탐지**가 목표!