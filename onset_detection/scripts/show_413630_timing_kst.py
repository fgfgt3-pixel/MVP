#!/usr/bin/env python
"""
413630 파일 급등 판단 시간 (한국시간 KST) 표시
"""

import pandas as pd
import json
from pathlib import Path

project_root = Path(__file__).parent.parent.parent

# Load CSV to get date
df = pd.read_csv(project_root / "onset_detection/data/raw/413630_44indicators_realtime_20250911_clean.csv")
if 'time' in df.columns:
    df = df.rename(columns={'time': 'ts'})

first_ts = df['ts'].min()
first_dt = pd.to_datetime(first_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')

print("="*70)
print(f"413630 File - Date: {first_dt.strftime('%Y-%m-%d')}")
print("="*70)

# Surge definitions
surges = [
    {'name': 'Surge 1', 'start': '09:09', 'end': '09:15', 'strength': 'medium', 'note': 'last 4min down'},
    {'name': 'Surge 2', 'start': '10:01', 'end': '10:14', 'strength': 'strong', 'note': 'last 4min down'},
    {'name': 'Surge 3', 'start': '11:46', 'end': '11:50', 'strength': 'weak', 'note': 'last 3min down'},
    {'name': 'Surge 4', 'start': '13:29', 'end': '13:37', 'strength': 'medium', 'note': 'last 3min down'},
    {'name': 'Surge 5', 'start': '14:09', 'end': '14:12', 'strength': 'weak', 'note': 'last 2min down'},
]

print("\nSURGE PERIODS (User-defined):")
print("-"*70)
for surge in surges:
    print(f"{surge['name']}: {surge['start']}~{surge['end']} ({surge['strength']}) - {surge['note']}")

# Load detection events
events = []
with open(project_root / "onset_detection/data/events/strategy_c_plus_413630.jsonl", 'r') as f:
    for line in f:
        events.append(json.loads(line))

print(f"\n\nDETECTED EVENTS (Total: {len(events)}):")
print("-"*70)

# Group events by surge window
for surge in surges:
    # Parse surge time
    start_h, start_m = map(int, surge['start'].split(':'))
    end_h, end_m = map(int, surge['end'].split(':'))

    surge_start_dt = first_dt.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    surge_end_dt = first_dt.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

    surge_start_ts = int(surge_start_dt.timestamp() * 1000)
    surge_end_ts = int(surge_end_dt.timestamp() * 1000)

    # Find events in window (±30s)
    window_start = surge_start_ts - 30000
    window_end = surge_end_ts + 30000

    surge_events = [e for e in events if window_start <= e['ts'] <= window_end]

    print(f"\n{surge['name']} ({surge['start']}~{surge['end']}, {surge['strength']}):")
    if surge_events:
        print(f"  DETECTED: {len(surge_events)} alerts")

        # Show first detection time
        first_evt = min(surge_events, key=lambda x: x['ts'])
        first_evt_dt = pd.to_datetime(first_evt['ts'], unit='ms', utc=True).tz_convert('Asia/Seoul')
        latency = (first_evt['ts'] - surge_start_ts) / 1000.0

        print(f"  First alert: {first_evt_dt.strftime('%H:%M:%S')}")
        print(f"  Latency: {latency:+.1f}s from surge start")

        # Show all alert times
        if len(surge_events) <= 5:
            print(f"  All alerts:")
            for evt in surge_events:
                evt_dt = pd.to_datetime(evt['ts'], unit='ms', utc=True).tz_convert('Asia/Seoul')
                print(f"    - {evt_dt.strftime('%H:%M:%S.%f')[:-3]}")
        else:
            print(f"  Sample alerts (first 3):")
            for evt in surge_events[:3]:
                evt_dt = pd.to_datetime(evt['ts'], unit='ms', utc=True).tz_convert('Asia/Seoul')
                print(f"    - {evt_dt.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"    ... and {len(surge_events)-3} more")
    else:
        print(f"  MISSED: No alerts detected")

print("\n" + "="*70)
print("SUMMARY:")
print("="*70)

detected = sum(1 for surge in surges if any(
    window_start <= e['ts'] <= window_end
    for e in events
    for window_start, window_end in [(
        int((first_dt.replace(hour=int(surge['start'].split(':')[0]),
                              minute=int(surge['start'].split(':')[1]),
                              second=0, microsecond=0)).timestamp() * 1000) - 30000,
        int((first_dt.replace(hour=int(surge['end'].split(':')[0]),
                              minute=int(surge['end'].split(':')[1]),
                              second=0, microsecond=0)).timestamp() * 1000) + 30000
    )]
))

print(f"Detected surges: {detected}/{len(surges)}")
print(f"Recall: {detected/len(surges)*100:.0f}%")
print(f"Total alerts: {len(events)}")
