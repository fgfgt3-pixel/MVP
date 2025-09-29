"""Online onset strength scoring using trained ML models."""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Union
import logging

from ..config_loader import Config, load_config
from ..ml.model_store import load_model

logger = logging.getLogger(__name__)


class OnsetScorer:
    """
    Score onset strength using trained ML model.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize onset scorer.

        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()
        self.model = None
        self.model_loaded = False

        # Get ML configuration
        ml_config = getattr(self.config, 'ml', None)
        if ml_config is None:
            logger.warning("No ML configuration found. ML scoring will be disabled.")
            self.enabled = False
            return

        self.enabled = getattr(ml_config, 'enabled', True)
        self.model_path = getattr(ml_config, 'model_path', 'models/onset_model.pkl')
        self.threshold = getattr(ml_config, 'threshold', 0.6)

        # Get feature configuration for dropping columns
        try:
            # Load ML config for drop columns
            from ..ml.labeler import load_ml_config
            ml_full_config = load_ml_config()
            features_config = ml_full_config.get('features', {})
            self.drop_columns = features_config.get('drop_columns', [])
        except Exception as e:
            logger.warning(f"Could not load ML config for drop columns: {e}")
            self.drop_columns = ['stock_code', 'ts', 'ts_sec', 'epoch_sec']

        if self.enabled:
            self._load_model()

    def _load_model(self):
        """Load the trained ML model."""
        if self.model_loaded:
            return

        try:
            model_path = Path(self.model_path)
            if not model_path.exists():
                logger.error(f"ML model not found: {model_path}")
                self.enabled = False
                return

            self.model = load_model(model_path)
            self.model_loaded = True
            logger.info(f"Loaded ML model from: {model_path}")

        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            self.enabled = False

    def predict_onset_strength(self, features_df: pd.DataFrame) -> np.ndarray:
        """
        Predict onset strength for features.

        Args:
            features_df: DataFrame with features.

        Returns:
            Array of onset strength scores (0-1).
        """
        if not self.enabled or not self.model_loaded:
            # Return neutral scores if ML is disabled
            return np.full(len(features_df), 0.5)

        try:
            # Prepare features by dropping specified columns
            X = features_df.copy()

            # Drop specified columns that exist in the DataFrame
            available_drop_columns = [col for col in self.drop_columns if col in X.columns]
            if available_drop_columns:
                X = X.drop(columns=available_drop_columns)

            # Get prediction probabilities
            if hasattr(self.model, 'predict_proba'):
                # Use probability for positive class
                proba = self.model.predict_proba(X)
                if proba.shape[1] > 1:
                    onset_strength = proba[:, 1]  # Positive class probability
                else:
                    onset_strength = proba.flatten()
            else:
                # Fallback to predict for models without predict_proba
                predictions = self.model.predict(X)
                onset_strength = predictions.astype(float)

            logger.debug(f"Predicted onset strength for {len(features_df)} samples")
            return onset_strength

        except Exception as e:
            logger.error(f"Failed to predict onset strength: {e}")
            # Return neutral scores on error
            return np.full(len(features_df), 0.5)

    def add_onset_strength(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add onset_strength column to features DataFrame.

        Args:
            features_df: Input features DataFrame.

        Returns:
            DataFrame with onset_strength column added.
        """
        df_with_strength = features_df.copy()

        if not self.enabled:
            # Add neutral scores if ML is disabled
            df_with_strength['onset_strength'] = 0.5
            logger.debug("ML disabled, added neutral onset_strength scores")
        else:
            # Predict onset strength
            strength_scores = self.predict_onset_strength(features_df)
            df_with_strength['onset_strength'] = strength_scores
            logger.info(f"Added onset_strength scores: mean={strength_scores.mean():.3f}, "
                       f"max={strength_scores.max():.3f}, min={strength_scores.min():.3f}")

        return df_with_strength


def add_onset_strength(
    features_df: pd.DataFrame,
    config: Optional[Config] = None
) -> pd.DataFrame:
    """
    Convenience function to add onset strength scores to features DataFrame.

    Args:
        features_df: Input features DataFrame.
        config: Configuration object. If None, loads default config.

    Returns:
        DataFrame with onset_strength column added.
    """
    scorer = OnsetScorer(config)
    return scorer.add_onset_strength(features_df)


if __name__ == "__main__":
    # Demo/test the onset scorer
    import sys
    from pathlib import Path

    # Add project root to Python path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    print("Onset Scorer Demo")
    print("=" * 40)

    # Create sample features data
    sample_data = {
        'ts': pd.date_range('2025-01-01', periods=10, freq='1s', tz='Asia/Seoul'),
        'stock_code': ['005930'] * 10,
        'price': 1000 + np.random.randn(10) * 10,
        'ret_1s': np.random.randn(10) * 0.001,
        'z_vol_1s': np.random.randn(10),
        'spread': np.random.uniform(0.001, 0.01, 10),
        'microprice_slope': np.random.randn(10) * 0.0001,
        # Add some window features
        'price_mean_1s': 1000 + np.random.randn(10) * 5,
        'ret_1s_std_2s': np.random.uniform(0.0001, 0.001, 10)
    }

    features_df = pd.DataFrame(sample_data)
    print(f"Sample features shape: {features_df.shape}")
    print(f"Features: {list(features_df.columns)}")

    # Test onset scorer
    try:
        scorer = OnsetScorer()
        print(f"Scorer enabled: {scorer.enabled}")
        print(f"Model loaded: {scorer.model_loaded}")

        # Add onset strength
        df_with_strength = scorer.add_onset_strength(features_df)
        print(f"Result shape: {df_with_strength.shape}")

        if 'onset_strength' in df_with_strength.columns:
            strength_scores = df_with_strength['onset_strength']
            print(f"Onset strength stats:")
            print(f"  Mean: {strength_scores.mean():.3f}")
            print(f"  Min: {strength_scores.min():.3f}")
            print(f"  Max: {strength_scores.max():.3f}")
            print(f"  Above threshold ({scorer.threshold}): {(strength_scores >= scorer.threshold).sum()}")
        else:
            print("onset_strength column not found")

    except Exception as e:
        print(f"Error: {e}")