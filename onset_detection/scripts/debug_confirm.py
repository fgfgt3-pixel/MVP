#!/usr/bin/env python
"""Confirm      """

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
from src.config_loader import load_config

def debug_confirm():
    """Confirm    """

    print("=" * 70)
    print("Confirm Detection Debugging")
    print("=" * 70)

    # 1. Config  
    config = load_config()
    print(f"\n  Config    :")
    print(f"   persistent_n: {config.confirm.persistent_n}")
    print(f"   window_s: {config.confirm.window_s}")
    print(f"   min_axes: {config.confirm.min_axes}")
    print(f"   delta.ret_min: {config.confirm.delta.ret_min}")
    print(f"   delta.zvol_min: {config.confirm.delta.zvol_min}")
    print(f"   delta.spread_drop: {config.confirm.delta.spread_drop}")

    # 2.    
    csv_path = project_root / "onset_detection" / "data" / "features" / "023790_features_mapped.csv"
    print(f"\n     : {csv_path.name}")

    df = pd.read_csv(csv_path)
    print(f"   Total rows: {len(df):,}")

    # 3. ret_1s    
    print(f"\n  ret_1s  :")
    print(f"   Mean: {df['ret_1s'].mean():.6f}")
    print(f"   Std: {df['ret_1s'].std():.6f}")
    print(f"   Min: {df['ret_1s'].min():.6f}")
    print(f"   Max: {df['ret_1s'].max():.6f}")
    print(f"   Values > 0.1: {len(df[df['ret_1s'] > 0.1])} (should be 0 after clipping)")
    print(f"   Values < -0.1: {len(df[df['ret_1s'] < -0.1])} (should be 0 after clipping)")

    # 4. Candidate  
    print(f"\n  Candidate Detection:")
    candidate_detector = CandidateDetector(config)
    candidates = candidate_detector.detect_candidates(df)
    print(f"   Candidates detected: {len(candidates)}")

    if not candidates:
        print("  Candidate   . Detection    !")
        return

    # 5.   3  Candidate    
    print(f"\n  Candidate     (  3 ):")

    confirm_detector = ConfirmDetector(config)

    for i, cand in enumerate(candidates[:3], 1):
        cand_ts = cand['ts']
        stock_code = cand['stock_code']

        print(f"\n--- Candidate {i} ---")
        print(f"   Timestamp: {cand_ts}")
        print(f"   Stock: {stock_code}")
        print(f"   Evidence: {cand['evidence']}")

        # Confirm    
        if isinstance(cand_ts, (int, float)):
            if cand_ts < 1e10:
                cand_dt = pd.to_datetime(cand_ts, unit='s', utc=True).tz_convert('Asia/Seoul')
            else:
                cand_dt = pd.to_datetime(cand_ts, unit='ms', utc=True).tz_convert('Asia/Seoul')
        else:
            cand_dt = pd.to_datetime(cand_ts)

        # Pre-window
        pre_window_start = cand_dt - pd.Timedelta(seconds=config.confirm.pre_window_s)
        pre_window_end = cand_dt - pd.Timedelta(milliseconds=1)

        # Confirm window
        window_start = cand_dt + pd.Timedelta(milliseconds=1) if config.confirm.exclude_cand_point else cand_dt
        window_end = cand_dt + pd.Timedelta(seconds=config.confirm.window_s)

        # Extract windows (handle both datetime and numeric ts)
        if pd.api.types.is_datetime64_any_dtype(df['ts']):
            pre_window_df = df[
                (df['ts'] > pre_window_start) &
                (df['ts'] <= pre_window_end) &
                (df['stock_code'].astype(str) == str(stock_code))
            ]
            window_df = df[
                (df['ts'] > window_start) &
                (df['ts'] <= window_end) &
                (df['stock_code'].astype(str) == str(stock_code))
            ]
        else:
            pre_start_ms = int(pre_window_start.timestamp() * 1000)
            pre_end_ms = int(pre_window_end.timestamp() * 1000)
            win_start_ms = int(window_start.timestamp() * 1000)
            win_end_ms = int(window_end.timestamp() * 1000)

            pre_window_df = df[
                (df['ts'] > pre_start_ms) &
                (df['ts'] <= pre_end_ms) &
                (df['stock_code'].astype(str) == str(stock_code))
            ]
            window_df = df[
                (df['ts'] > win_start_ms) &
                (df['ts'] <= win_end_ms) &
                (df['stock_code'].astype(str) == str(stock_code))
            ]

        print(f"   Pre-window rows: {len(pre_window_df)}")
        print(f"   Confirm window rows: {len(window_df)}")

        if pre_window_df.empty or window_df.empty:
            print(f"     Window    ")
            continue

        # Delta  
        pre_ret = pre_window_df['ret_1s'].mean()
        win_ret = window_df['ret_1s'].mean()
        delta_ret = win_ret - pre_ret

        pre_zvol = pre_window_df['z_vol_1s'].mean()
        win_zvol = window_df['z_vol_1s'].mean()
        delta_zvol = win_zvol - pre_zvol

        print(f"   Pre-window ret_1s: {pre_ret:.6f}")
        print(f"   Confirm window ret_1s: {win_ret:.6f}")
        print(f"   Delta ret: {delta_ret:.6f} (threshold: {config.confirm.delta.ret_min})")

        print(f"   Pre-window z_vol_1s: {pre_zvol:.4f}")
        print(f"   Confirm window z_vol_1s: {win_zvol:.4f}")
        print(f"   Delta zvol: {delta_zvol:.4f} (threshold: {config.confirm.delta.zvol_min})")

        # Persistent check
        ret_satisfied = (window_df['ret_1s'] - pre_ret) >= config.confirm.delta.ret_min
        zvol_satisfied = (window_df['z_vol_1s'] - pre_zvol) >= config.confirm.delta.zvol_min

        print(f"   Ticks satisfying ret threshold: {ret_satisfied.sum()}")
        print(f"   Ticks satisfying zvol threshold: {zvol_satisfied.sum()}")

        # Check consecutive
        consecutive_count = 0
        max_consecutive = 0
        for val in ret_satisfied:
            if val:
                consecutive_count += 1
                max_consecutive = max(max_consecutive, consecutive_count)
            else:
                consecutive_count = 0

        print(f"   Max consecutive ret_satisfied: {max_consecutive} (need {config.confirm.persistent_n})")

        if max_consecutive >= config.confirm.persistent_n:
            print(f"     Would CONFIRM!")
        else:
            print(f"     Failed persistent_n requirement")

    print(f"\n{'='*70}")
    print("   :")
    print(f"   - Candidates: {len(candidates)}")
    print(f"   -   3     ")
    print(f"   - persistent_n={config.confirm.persistent_n}       ")
    print(f"\n   : persistent_n=1    Delta threshold    ")
    print(f"{'='*70}")

if __name__ == "__main__":
    debug_confirm()
