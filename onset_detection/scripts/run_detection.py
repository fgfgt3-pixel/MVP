#!/usr/bin/env python
"""Run full onset detection pipeline on CSV data."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "onset_detection"))

from src.features import calculate_core_indicators
from src.detection.candidate_detector import CandidateDetector
from src.detection.confirm_detector import ConfirmDetector
from src.detection.refractory_manager import RefractoryManager
from src.config_loader import load_config

def run_detection():
    """Run full detection pipeline."""

    print("=" * 70)
    print("Onset Detection Pipeline")
    print("=" * 70)

    # 1. Load config
    config = load_config()
    print(f"\nConfig:")
    print(f"  persistent_n: {config.confirm.persistent_n}")
    print(f"  window_s: {config.confirm.window_s}")
    print(f"  min_axes: {config.confirm.min_axes}")
    print(f"  delta.ret_min: {config.confirm.delta.ret_min}")
    print(f"  delta.zvol_min: {config.confirm.delta.zvol_min}")
    print(f"  refractory_duration_s: {config.refractory.duration_s}")

    # 2. Load data
    csv_path = project_root / "onset_detection" / "data" / "features" / "023790_features_fixed_ret1s.csv"
    print(f"\nLoading data: {csv_path.name}")

    df = pd.read_csv(csv_path)
    print(f"  Total rows: {len(df):,}")
    print(f"  Columns: {', '.join(df.columns[:10])}")
    print(f"  Stock code type: {df['stock_code'].dtype}")
    print(f"  Stock code unique: {df['stock_code'].unique()}")

    # 3. Verify ret_1s
    print(f"\nret_1s statistics:")
    print(f"  Mean: {df['ret_1s'].mean():.6f}")
    print(f"  Std: {df['ret_1s'].std():.6f}")
    print(f"  Min: {df['ret_1s'].min():.6f}")
    print(f"  Max: {df['ret_1s'].max():.6f}")
    print(f"  Values > 0.1: {len(df[df['ret_1s'] > 0.1])}")
    print(f"  Values < -0.1: {len(df[df['ret_1s'] < -0.1])}")

    # 4. Candidate Detection
    print(f"\n" + "=" * 70)
    print("Stage 1: Candidate Detection")
    print("=" * 70)
    candidate_detector = CandidateDetector(config)
    candidates = candidate_detector.detect_candidates(df)
    print(f"Candidates detected: {len(candidates)}")

    if not candidates:
        print("\nNo candidates detected. Stopping pipeline.")
        return

    # Show first few candidates
    print(f"\nFirst 3 candidates:")
    for i, cand in enumerate(candidates[:3], 1):
        print(f"  {i}. ts={cand['ts']}, stock={cand['stock_code']}, score={cand['evidence'].get('onset_score', 0):.2f}")

    # 5. Refractory Filter
    print(f"\n" + "=" * 70)
    print("Stage 2: Refractory Filter")
    print("=" * 70)
    refractory_manager = RefractoryManager(config)

    filtered_candidates = []
    rejected_count = 0
    for cand in candidates:
        if refractory_manager.allow_candidate(cand['ts'], cand['stock_code']):
            filtered_candidates.append(cand)
        else:
            rejected_count += 1

    print(f"Candidates after refractory: {len(filtered_candidates)}")
    print(f"Rejected by refractory: {rejected_count}")

    # 6. Confirmation
    print(f"\n" + "=" * 70)
    print("Stage 3: Confirmation")
    print("=" * 70)
    confirm_detector = ConfirmDetector(config)
    confirmed_events = confirm_detector.confirm_candidates(df, filtered_candidates)

    print(f"Confirmed onsets: {len(confirmed_events)}")
    print(f"Confirmation rate: {len(confirmed_events) / len(filtered_candidates) * 100:.1f}%")

    # 7. Results
    print(f"\n" + "=" * 70)
    print("Pipeline Results")
    print("=" * 70)
    print(f"Total candidates: {len(candidates)}")
    print(f"After refractory: {len(filtered_candidates)}")
    print(f"Confirmed onsets: {len(confirmed_events)}")
    print(f"Overall confirmation rate: {len(confirmed_events) / len(candidates) * 100:.1f}%")

    if confirmed_events:
        print(f"\nConfirmed Events:")
        for i, event in enumerate(confirmed_events[:10], 1):
            print(f"  {i}. ts={event['ts']}, stock={event['stock_code']}")
            print(f"     axes={event['evidence']['axes']}")
            print(f"     strength={event['evidence']['onset_strength']:.2f}")
            print(f"     delta_ret={event['evidence']['delta_ret']:.6f}")
            print(f"     delta_zvol={event['evidence']['delta_zvol']:.2f}")

        # Save to file
        output_path = project_root / "onset_detection" / "data" / "events" / "confirmed_onsets.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        import json
        with open(output_path, 'w') as f:
            for event in confirmed_events:
                f.write(json.dumps(event) + '\n')

        print(f"\nResults saved to: {output_path}")
    else:
        print(f"\nNo confirmed onsets detected.")
        print(f"Possible reasons:")
        print(f"  - persistent_n too high ({config.confirm.persistent_n})")
        print(f"  - Delta thresholds too strict")
        print(f"  - No clear surge patterns in data")

    print("=" * 70)

if __name__ == "__main__":
    run_detection()
