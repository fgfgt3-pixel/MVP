#!/usr/bin/env python3
"""
Dual-Pathway Detection 구현
Sharp와 Gradual을 서로 다른 기준으로 동시 탐지
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Any
import sys

# 프로젝트 루트 추가
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

class DualPathwayDetector:
    """
    두 가지 급등 타입을 별도 경로로 탐지
    """

    def __init__(self):
        # Pathway 1: Sharp Surge (가격 중심)
        self.sharp_config = {
            'gate_ret_min': 0.001,
            'ret_1s_weight': 60,      # 가격 중심
            'z_vol_weight': 30,
            'threshold': 85,
            'confirm_window_s': 10,   # 짧은 확인
            'persistent_n': 10,
            'refractory_s': 45
        }

        # Pathway 2: Gradual Surge (틱밀도 중심)
        self.gradual_config = {
            'gate_ret_min': 0.0003,   # 완화
            'ticks_weight': 50,       # 틱밀도 중심
            'z_vol_weight': 40,
            'ret_supplement': 20,     # 보조
            'threshold': 75,          # 낮은 threshold
            'confirm_window_s': 20,   # 긴 확인
            'persistent_n': 25,       # 더 긴 지속성
            'refractory_s': 60
        }

    def detect_candidates(self, features_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """두 경로 모두 실행"""

        candidates = []

        for idx, row in features_df.iterrows():
            # Sharp pathway
            sharp_result = self._check_sharp(row)
            if sharp_result:
                candidates.append({
                    'ts': row['ts'],
                    'stock_code': row['stock_code'],
                    'pathway': 'sharp',
                    'score': sharp_result['score'],
                    'evidence': sharp_result['evidence']
                })
                continue  # Sharp 감지 시 Gradual 건너뜀

            # Gradual pathway
            gradual_result = self._check_gradual(row)
            if gradual_result:
                candidates.append({
                    'ts': row['ts'],
                    'stock_code': row['stock_code'],
                    'pathway': 'gradual',
                    'score': gradual_result['score'],
                    'evidence': gradual_result['evidence']
                })

        return candidates

    def _check_sharp(self, row) -> Dict[str, Any]:
        """Sharp pathway 체크"""

        ret_1s = row.get('ret_1s', 0)

        # Gate
        if ret_1s <= self.sharp_config['gate_ret_min']:
            return None

        # Scoring
        score = 0

        # ret_1s (가격 중심)
        if ret_1s > 0.003:
            score += self.sharp_config['ret_1s_weight']
        elif ret_1s > 0.002:
            score += self.sharp_config['ret_1s_weight'] * 0.7
        elif ret_1s > 0.001:
            score += self.sharp_config['ret_1s_weight'] * 0.4

        # z_vol (보조)
        z_vol = row.get('z_vol_1s', 0)
        if z_vol > 3.0:
            score += self.sharp_config['z_vol_weight']
        elif z_vol > 2.5:
            score += self.sharp_config['z_vol_weight'] * 0.7
        elif z_vol > 2.0:
            score += self.sharp_config['z_vol_weight'] * 0.4

        if score >= self.sharp_config['threshold']:
            return {
                'score': score,
                'evidence': {
                    'ret_1s': float(ret_1s),
                    'z_vol_1s': float(z_vol)
                }
            }

        return None

    def _check_gradual(self, row) -> Dict[str, Any]:
        """Gradual pathway 체크"""

        ret_1s = row.get('ret_1s', 0)

        # Gate (완화됨)
        if ret_1s <= self.gradual_config['gate_ret_min']:
            return None

        # Scoring
        score = 0

        # ticks_per_sec (틱밀도 중심)
        ticks = row.get('ticks_per_sec', 0)
        if ticks > 80:
            score += self.gradual_config['ticks_weight']
        elif ticks > 60:
            score += self.gradual_config['ticks_weight'] * 0.8
        elif ticks > 40:
            score += self.gradual_config['ticks_weight'] * 0.5

        # z_vol (중요)
        z_vol = row.get('z_vol_1s', 0)
        if z_vol > 2.5:
            score += self.gradual_config['z_vol_weight']
        elif z_vol > 2.0:
            score += self.gradual_config['z_vol_weight'] * 0.7
        elif z_vol > 1.5:
            score += self.gradual_config['z_vol_weight'] * 0.4

        # ret_1s (보조)
        if ret_1s > 0.002:
            score += self.gradual_config['ret_supplement']
        elif ret_1s > 0.001:
            score += self.gradual_config['ret_supplement'] * 0.6

        if score >= self.gradual_config['threshold']:
            return {
                'score': score,
                'evidence': {
                    'ret_1s': float(ret_1s),
                    'z_vol_1s': float(z_vol),
                    'ticks_per_sec': int(ticks)
                }
            }

        return None


class DualPathwayConfirm:
    """Pathway별 맞춤 확인"""

    def __init__(self, detector: DualPathwayDetector):
        self.detector = detector

    def confirm_candidates(
        self,
        features_df: pd.DataFrame,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        confirmed = []

        for cand in candidates:
            pathway = cand['pathway']

            if pathway == 'sharp':
                result = self._confirm_sharp(features_df, cand)
            else:
                result = self._confirm_gradual(features_df, cand)

            if result:
                confirmed.append(result)

        return confirmed

    def _confirm_sharp(self, df, cand):
        """Sharp: 짧고 빠른 확인"""

        config = self.detector.sharp_config
        cand_ts = cand['ts']
        stock_code = cand['stock_code']

        window_start = cand_ts
        window_end = cand_ts + config['confirm_window_s'] * 1000

        window = df[
            (df['ts'] >= window_start) &
            (df['ts'] <= window_end) &
            (df['stock_code'] == stock_code)
        ]

        if len(window) < config['persistent_n']:
            return None

        # 지속적 상승
        positive = (window['ret_1s'] > 0).sum()
        if positive >= config['persistent_n'] * 0.7:  # 70% 양수
            # persistent_n 위치 또는 마지막 행
            confirm_idx = min(config['persistent_n'], len(window) - 1)
            return {
                'ts': int(window.iloc[confirm_idx]['ts']),
                'stock_code': str(stock_code),
                'event_type': 'onset_confirmed',
                'pathway': 'sharp',
                'confirmed_from': int(cand_ts)
            }

        return None

    def _confirm_gradual(self, df, cand):
        """Gradual: 길고 꼼꼼한 확인"""

        config = self.detector.gradual_config
        cand_ts = cand['ts']
        stock_code = cand['stock_code']

        window_start = cand_ts
        window_end = cand_ts + config['confirm_window_s'] * 1000

        window = df[
            (df['ts'] >= window_start) &
            (df['ts'] <= window_end) &
            (df['stock_code'] == stock_code)
        ]

        if len(window) < config['persistent_n']:
            return None

        # 틱밀도 + 방향성
        avg_ticks = window['ticks_per_sec'].mean()
        positive = (window['ret_1s'] > 0).sum()

        if avg_ticks > 40 and positive >= config['persistent_n'] * 0.6:
            # persistent_n 위치 또는 마지막 행
            confirm_idx = min(config['persistent_n'], len(window) - 1)
            return {
                'ts': int(window.iloc[confirm_idx]['ts']),
                'stock_code': str(stock_code),
                'event_type': 'onset_confirmed',
                'pathway': 'gradual',
                'confirmed_from': int(cand_ts)
            }

        return None


# 배치 실행
if __name__ == "__main__":
    # 라벨 로드
    labels_path = project_root / "onset_detection/data/labels/all_surge_labels.json"
    with open(labels_path, encoding='utf-8') as f:
        labels = json.load(f)

    files = list(set([l['file'] for l in labels]))

    detector = DualPathwayDetector()
    confirmer = DualPathwayConfirm(detector)

    all_confirmed = []

    data_dir = project_root / "onset_detection/data/raw"

    for filename in files:
        print(f"Processing {filename}")

        filepath = data_dir / filename
        if not filepath.exists():
            print(f"  [SKIP] File not found")
            continue

        df = pd.read_csv(filepath)

        # 컬럼명 통일
        rename_map = {}
        if 'time' in df.columns and 'ts' not in df.columns:
            rename_map['time'] = 'ts'
        if 'ret_accel' in df.columns and 'accel_1s' not in df.columns:
            rename_map['ret_accel'] = 'accel_1s'
        if 'current_price' in df.columns and 'price' not in df.columns:
            rename_map['current_price'] = 'price'
        if rename_map:
            df = df.rename(columns=rename_map)

        features_df = df

        # Detect
        candidates = detector.detect_candidates(features_df)
        print(f"  Candidates: {len(candidates)}")

        # Confirm
        confirmed = confirmer.confirm_candidates(features_df, candidates)

        # 파일명 추가
        for event in confirmed:
            event['file'] = filename

        all_confirmed.extend(confirmed)

        print(f"  Confirmed: {len(confirmed)}")

    # 저장
    output_path = project_root / "onset_detection/data/events/dual_pathway_confirmed.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for event in all_confirmed:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')

    print(f"\nTotal confirmed: {len(all_confirmed)}")
    print(f"Saved to: {output_path.relative_to(project_root)}")
