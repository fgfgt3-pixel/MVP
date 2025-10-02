"""
Gate + Weighted Scoring 기반 후보 탐지
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from ..config_loader import Config, load_config
from ..event_store import create_event


class GateScoreDetector:
    """
    2단계 탐지:
    1. Gate: 필수 조건 (가격 상승)
    2. Scoring: 가중 점수 시스템

    데이터 분석 결과:
    - spread가 가장 변별력 높음 (d=0.972)
    - microprice_slope 두 번째 (d=0.599)
    - 기존 z_vol, ticks_per_sec은 변별력 낮음
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or load_config()

        # Gate 조건
        self.gate_ret_min = 0.0005  # 최소 상승

        # Scoring 가중치 (discriminative_analysis.json 기반)
        self.weights = {
            # Primary (변별력 highest)
            'spread_low': 50,  # spread가 낮을수록 좋음
            'microprice_slope': 40,

            # Secondary
            'ret_1s_magnitude': 20,
            'z_vol_1s': 15,

            # Tertiary
            'ticks_per_sec': 10
        }

        # Threshold
        self.score_threshold = 70  # 70점 이상 = Candidate

    def detect_candidates(self, features_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """후보 탐지"""

        if features_df.empty:
            return []

        candidates = []

        for idx, row in features_df.iterrows():
            # Step 1: Gate Check
            ret_1s = row.get('ret_1s', 0)

            if ret_1s <= self.gate_ret_min:
                continue  # 가격 상승 없음 → 즉시 종료

            # Step 2: Scoring
            score = self._calculate_score(row)

            # Step 3: Threshold
            if score >= self.score_threshold:
                candidate = create_event(
                    timestamp=int(row['ts']),
                    event_type="onset_candidate",
                    stock_code=str(row.get('stock_code', 'UNKNOWN')),
                    score=float(score),
                    evidence={
                        "ret_1s": float(ret_1s),
                        "spread": float(row.get('spread', 0)),
                        "microprice_slope": float(row.get('microprice_slope', 0)),
                        "z_vol_1s": float(row.get('z_vol_1s', 0)),
                        "ticks_per_sec": int(row.get('ticks_per_sec', 0)),
                        "scoring_details": self._get_scoring_details(row)
                    }
                )
                candidates.append(candidate)

        return candidates

    def _calculate_score(self, row: pd.Series) -> float:
        """가중 점수 계산"""

        score = 0.0

        # spread (Primary) - 낮을수록 좋음
        spread = row.get('spread', 999)
        if spread < 2.0:
            score += self.weights['spread_low']
        elif spread < 5.0:
            score += self.weights['spread_low'] * 0.8
        elif spread < 10.0:
            score += self.weights['spread_low'] * 0.5
        elif spread < 20.0:
            score += self.weights['spread_low'] * 0.3

        # microprice_slope (Primary)
        slope = row.get('microprice_slope', 0)
        if slope > 0.001:
            score += self.weights['microprice_slope']
        elif slope > 0.0005:
            score += self.weights['microprice_slope'] * 0.7
        elif slope > 0.0002:
            score += self.weights['microprice_slope'] * 0.4

        # ret_1s magnitude (Secondary)
        ret_1s = row.get('ret_1s', 0)
        if ret_1s > 0.003:
            score += self.weights['ret_1s_magnitude']
        elif ret_1s > 0.002:
            score += self.weights['ret_1s_magnitude'] * 0.7
        elif ret_1s > 0.001:
            score += self.weights['ret_1s_magnitude'] * 0.4

        # z_vol_1s (Secondary)
        z_vol = row.get('z_vol_1s', 0)
        if z_vol > 3.0:
            score += self.weights['z_vol_1s']
        elif z_vol > 2.5:
            score += self.weights['z_vol_1s'] * 0.8
        elif z_vol > 2.0:
            score += self.weights['z_vol_1s'] * 0.5

        # ticks_per_sec (Tertiary)
        ticks = row.get('ticks_per_sec', 0)
        if ticks > 70:
            score += self.weights['ticks_per_sec']
        elif ticks > 50:
            score += self.weights['ticks_per_sec'] * 0.8
        elif ticks > 30:
            score += self.weights['ticks_per_sec'] * 0.5

        return score

    def _get_scoring_details(self, row: pd.Series) -> Dict[str, Any]:
        """점수 상세 (디버깅용)"""

        details = {}

        details['spread'] = {
            'value': float(row.get('spread', 0)),
            'max_weight': self.weights['spread_low']
        }

        details['microprice_slope'] = {
            'value': float(row.get('microprice_slope', 0)),
            'max_weight': self.weights['microprice_slope']
        }

        details['ret_1s'] = {
            'value': float(row.get('ret_1s', 0)),
            'max_weight': self.weights['ret_1s_magnitude']
        }

        details['z_vol_1s'] = {
            'value': float(row.get('z_vol_1s', 0)),
            'max_weight': self.weights['z_vol_1s']
        }

        details['ticks_per_sec'] = {
            'value': int(row.get('ticks_per_sec', 0)),
            'max_weight': self.weights['ticks_per_sec']
        }

        return details
