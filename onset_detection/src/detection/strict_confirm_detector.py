"""
Noise 제거를 위한 강화된 확인 로직
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from ..event_store import create_event


class StrictConfirmDetector:
    """
    3단계 확인:
    1. Pre-window 대비 개선 확인
    2. Persistent 지속성 (더 길게)
    3. Peak 검증 (급등 진행 중인가?)
    """

    def __init__(self, config=None):
        # 완화된 파라미터 (Recall 개선)
        self.pre_window_s = 5   # 5초 유지
        self.confirm_window_s = 15  # 20 → 15초 (더 빠른 확인)
        self.persistent_n = 15  # 30 → 15 (1.5초분)

        # Delta 완화
        self.delta_ret_min = 0.0003  # 0.001 → 0.0003
        self.delta_zvol_min = 0.3    # 0.5 → 0.3

        # Peak 검증 비활성화 (너무 엄격)
        self.require_peak_progress = False

    def confirm_candidates(
        self,
        features_df: pd.DataFrame,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """후보 확인"""

        confirmed = []

        for cand in candidates:
            cand_ts = cand['ts']
            stock_code = cand.get('stock_code', 'UNKNOWN')

            # Window 추출
            pre_start = cand_ts - self.pre_window_s * 1000
            pre_end = cand_ts

            conf_start = cand_ts
            conf_end = cand_ts + self.confirm_window_s * 1000

            pre_window = features_df[
                (features_df['ts'] >= pre_start) &
                (features_df['ts'] < pre_end)
            ].copy()

            conf_window = features_df[
                (features_df['ts'] >= conf_start) &
                (features_df['ts'] <= conf_end)
            ].copy()

            if pre_window.empty or conf_window.empty:
                continue

            # 1단계: Delta 확인
            delta_result = self._check_delta(pre_window, conf_window)
            if not delta_result['passed']:
                continue

            # 2단계: Persistent 확인
            persist_result = self._check_persistent(conf_window)
            if not persist_result['confirmed']:
                continue

            # 3단계: Peak 검증
            if self.require_peak_progress:
                peak_result = self._check_peak_progress(conf_window)
                if not peak_result['passed']:
                    continue
            else:
                peak_result = {'passed': True, 'progress_pct': 0}

            # 확정
            confirmed_event = create_event(
                timestamp=int(persist_result['confirm_ts']),
                event_type='onset_confirmed',
                stock_code=str(stock_code),
                confirmed_from=int(cand_ts),
                evidence={
                    'delta': delta_result['deltas'],
                    'persistent_rate': persist_result['evidence']['persistent_rate'],
                    'peak_progress': peak_result['progress_pct'],
                    'candidate_score': cand.get('score', 0)
                }
            )

            confirmed.append(confirmed_event)

        return confirmed

    def _check_delta(self, pre_df, conf_df):
        """Pre 대비 개선"""
        pre_ret = pre_df['ret_1s'].median()
        pre_zvol = pre_df['z_vol_1s'].median()

        conf_ret = conf_df['ret_1s'].median()
        conf_zvol = conf_df['z_vol_1s'].median()

        delta_ret = conf_ret - pre_ret
        delta_zvol = conf_zvol - pre_zvol

        passed = (delta_ret >= self.delta_ret_min and
                  delta_zvol >= self.delta_zvol_min)

        return {
            'passed': passed,
            'deltas': {
                'ret': float(delta_ret),
                'zvol': float(delta_zvol)
            }
        }

    def _check_persistent(self, conf_df):
        """지속성 확인"""
        if len(conf_df) < self.persistent_n:
            return {'confirmed': False}

        # ret_1s > 0 (상승 중)
        positive_ret = (conf_df['ret_1s'] > 0).astype(int)

        # Rolling sum
        rolling_sum = positive_ret.rolling(
            window=self.persistent_n,
            min_periods=self.persistent_n
        ).sum()

        # persistent_n 중 60% 이상 양수 (완화)
        threshold = self.persistent_n * 0.6
        persistent_ok = rolling_sum >= threshold

        if not persistent_ok.any():
            return {'confirmed': False}

        # 최초 충족 시점
        first_idx = persistent_ok.idxmax()
        confirm_ts = conf_df.loc[first_idx, 'ts']

        return {
            'confirmed': True,
            'confirm_ts': int(confirm_ts),
            'evidence': {
                'persistent_rate': float(positive_ret.sum() / len(conf_df))
            }
        }

    def _check_peak_progress(self, conf_df):
        """Peak 진행 확인 (가격이 계속 오르는가?)"""
        if 'price' not in conf_df.columns:
            return {'passed': True, 'progress_pct': 0}

        prices = conf_df['price'].values

        # 최근 1/3 구간의 평균 > 초반 1/3 구간의 평균
        third = len(prices) // 3

        if third < 3:
            return {'passed': True, 'progress_pct': 0}  # 너무 짧으면 통과

        early_mean = np.mean(prices[:third])
        late_mean = np.mean(prices[-third:])

        progress_pct = (late_mean - early_mean) / early_mean * 100

        passed = late_mean > early_mean * 1.005  # 0.5% 이상 상승

        return {
            'passed': passed,
            'progress_pct': float(progress_pct)
        }
