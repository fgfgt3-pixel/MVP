"""Candidate detector for onset detection."""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..config_loader import Config, load_config
from ..event_store import EventStore, create_event


class CandidateDetector:
    """
    Detect onset candidates based on calculated features.
    
    Uses rule-based detection logic to identify potential onset signals
    by analyzing price, volume, and friction indicators.
    """
    
    def __init__(self, config: Optional[Config] = None, event_store: Optional[EventStore] = None):
        """
        Initialize candidate detector.
        
        Args:
            config: Configuration object. If None, loads default config.
            event_store: EventStore instance. If None, creates default one.
        """
        self.config = config or load_config()
        self.event_store = event_store or EventStore()
        
        # Extract detection parameters
        self.score_threshold = self.config.detection.score_threshold
        self.vol_z_min = self.config.detection.vol_z_min
        self.ticks_min = self.config.detection.ticks_min
        self.weights = self.config.detection.weights
    
    def detect_candidates(self, features_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detect onset candidates from features DataFrame.
        
        Args:
            features_df: DataFrame with calculated features from core_indicators.
        
        Returns:
            List[Dict]: List of onset candidate events.
        """
        if features_df.empty:
            return []
        
        candidates = []
        
        # Required columns check
        required_cols = ['ts', 'stock_code', 'ret_1s', 'accel_1s', 'z_vol_1s', 'ticks_per_sec']
        missing_cols = set(required_cols) - set(features_df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns for detection: {missing_cols}")
        
        for idx, row in features_df.iterrows():
            # Extract indicators
            ret_1s = row['ret_1s']
            accel_1s = row['accel_1s']
            z_vol_1s = row['z_vol_1s']
            ticks_per_sec = row['ticks_per_sec']
            
            # Skip if any indicator is NaN or invalid
            if pd.isna(ret_1s) or pd.isna(accel_1s) or pd.isna(z_vol_1s) or pd.isna(ticks_per_sec):
                continue
            
            # Calculate weighted score
            score = (
                self.weights["ret"] * ret_1s +
                self.weights["accel"] * accel_1s +
                self.weights["z_vol"] * z_vol_1s +
                self.weights["ticks"] * ticks_per_sec
            )
            
            # Apply detection conditions
            conditions_met = (
                score >= self.score_threshold and
                z_vol_1s >= self.vol_z_min and
                ticks_per_sec >= self.ticks_min
            )
            
            if conditions_met:
                # Create candidate event
                candidate_event = create_event(
                    timestamp=row['ts'],
                    event_type="onset_candidate",
                    stock_code=str(row['stock_code']),
                    score=float(score),
                    evidence={
                        "ret_1s": float(ret_1s),
                        "accel_1s": float(accel_1s),
                        "z_vol_1s": float(z_vol_1s),
                        "ticks_per_sec": int(ticks_per_sec)
                    }
                )
                
                candidates.append(candidate_event)
        
        return candidates
    
    def save_candidates(self, candidates: List[Dict[str, Any]], filename: Optional[str] = None) -> bool:
        """
        Save candidate events to EventStore.
        
        Args:
            candidates: List of candidate events.
            filename: Optional filename for saving events.
        
        Returns:
            bool: True if all events saved successfully.
        """
        if not candidates:
            return True
        
        success_count = 0
        for event in candidates:
            if self.event_store.save_event(event, filename=filename):
                success_count += 1
        
        return success_count == len(candidates)
    
    def detect_and_save(self, features_df: pd.DataFrame, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Detect candidates and save them in one operation.
        
        Args:
            features_df: DataFrame with calculated features.
            filename: Optional filename for saving events.
        
        Returns:
            Dict: Summary with candidate count and save status.
        """
        candidates = self.detect_candidates(features_df)
        
        if candidates:
            save_success = self.save_candidates(candidates, filename)
        else:
            save_success = True
        
        return {
            "candidates_detected": len(candidates),
            "save_success": save_success,
            "events": candidates
        }
    
    def get_detection_stats(self, features_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get detection statistics without saving events.
        
        Args:
            features_df: DataFrame with calculated features.
        
        Returns:
            Dict: Detection statistics.
        """
        if features_df.empty:
            return {
                "total_rows": 0,
                "candidates_detected": 0,
                "detection_rate": 0.0,
                "score_stats": {},
                "condition_stats": {}
            }
        
        candidates = self.detect_candidates(features_df)
        
        # Calculate statistics for all rows (not just candidates)
        scores = []
        vol_z_conditions = 0
        ticks_conditions = 0
        
        for idx, row in features_df.iterrows():
            if pd.isna(row.get('ret_1s')) or pd.isna(row.get('accel_1s')) or pd.isna(row.get('z_vol_1s')) or pd.isna(row.get('ticks_per_sec')):
                continue
            
            # Calculate score
            score = (
                self.weights["ret"] * row['ret_1s'] +
                self.weights["accel"] * row['accel_1s'] +
                self.weights["z_vol"] * row['z_vol_1s'] +
                self.weights["ticks"] * row['ticks_per_sec']
            )
            scores.append(score)
            
            # Count condition satisfaction
            if row['z_vol_1s'] >= self.vol_z_min:
                vol_z_conditions += 1
            if row['ticks_per_sec'] >= self.ticks_min:
                ticks_conditions += 1
        
        total_valid_rows = len(scores)
        detection_rate = len(candidates) / total_valid_rows if total_valid_rows > 0 else 0.0
        
        score_stats = {}
        if scores:
            score_stats = {
                "mean": float(np.mean(scores)),
                "std": float(np.std(scores)),
                "min": float(np.min(scores)),
                "max": float(np.max(scores)),
                "p95": float(np.percentile(scores, 95))
            }
        
        return {
            "total_rows": len(features_df),
            "valid_rows": total_valid_rows,
            "candidates_detected": len(candidates),
            "detection_rate": detection_rate,
            "score_stats": score_stats,
            "condition_stats": {
                "vol_z_satisfied": vol_z_conditions,
                "ticks_satisfied": ticks_conditions,
                "score_threshold": self.score_threshold,
                "vol_z_min": self.vol_z_min,
                "ticks_min": self.ticks_min
            }
        }


def detect_candidates(features_df: pd.DataFrame, config: Optional[Config] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to detect onset candidates.
    
    Args:
        features_df: DataFrame with calculated features.
        config: Optional configuration object.
    
    Returns:
        List[Dict]: List of onset candidate events.
    """
    detector = CandidateDetector(config)
    return detector.detect_candidates(features_df)


if __name__ == "__main__":
    # Demo/test the candidate detector
    from ..features import calculate_core_indicators
    import time
    
    print("Candidate Detector Demo")
    print("=" * 40)
    
    # Create sample data with features that should trigger detection
    sample_data = {
        'ts': [1704067200000 + i * 1000 for i in range(20)],
        'stock_code': ['005930'] * 20,
        'price': [74000 + i * 100 for i in range(20)],  # Strong price movement
        'volume': [1000 + i * 500 for i in range(20)],  # Increasing volume
        'bid1': [73950 + i * 100 for i in range(20)],
        'ask1': [74050 + i * 100 for i in range(20)],
        'bid_qty1': [500] * 20,
        'ask_qty1': [300] * 20,
    }
    
    df = pd.DataFrame(sample_data)
    print(f"Sample data shape: {df.shape}")
    
    # Calculate features first
    features_df = calculate_core_indicators(df)
    print(f"Features DataFrame shape: {features_df.shape}")
    
    # Detect candidates
    detector = CandidateDetector()
    candidates = detector.detect_candidates(features_df)
    
    print(f"\nCandidates detected: {len(candidates)}")
    
    if candidates:
        print("Sample candidate events:")
        for i, candidate in enumerate(candidates[:3]):
            print(f"  {i+1}. Timestamp: {candidate['ts']}, Score: {candidate['score']:.3f}")
            print(f"     Evidence: ret_1s={candidate['evidence']['ret_1s']:.4f}, "
                  f"z_vol_1s={candidate['evidence']['z_vol_1s']:.2f}")
    
    # Get detection stats
    stats = detector.get_detection_stats(features_df)
    print(f"\nDetection Statistics:")
    print(f"  Detection rate: {stats['detection_rate']:.2%}")
    print(f"  Score stats: mean={stats['score_stats'].get('mean', 0):.3f}, "
          f"max={stats['score_stats'].get('max', 0):.3f}")
    print(f"  Condition stats: vol_z_satisfied={stats['condition_stats']['vol_z_satisfied']}, "
          f"ticks_satisfied={stats['condition_stats']['ticks_satisfied']}")