"""Model storage and loading utilities."""

import os
import json
import pickle
import joblib
from pathlib import Path
from typing import Any, Dict, Optional, Union
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class ModelStore:
    """
    Handle model saving, loading, and metadata management.
    """

    def __init__(self, base_path: Union[str, Path] = "models"):
        """
        Initialize model store.

        Args:
            base_path: Base directory for storing models.
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model: Any,
        model_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        method: str = "joblib"
    ) -> Path:
        """
        Save model with metadata.

        Args:
            model: Trained model object.
            model_name: Name for the model (without extension).
            metadata: Optional metadata dictionary.
            method: Serialization method ('joblib' or 'pickle').

        Returns:
            Path: Path to saved model file.
        """
        if method == "joblib":
            model_path = self.base_path / f"{model_name}.pkl"
            joblib.dump(model, model_path)
        elif method == "pickle":
            model_path = self.base_path / f"{model_name}.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
        else:
            raise ValueError(f"Unknown serialization method: {method}")

        logger.info(f"Saved model to: {model_path}")

        # Save metadata if provided
        if metadata:
            metadata_path = self.base_path / f"{model_name}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            logger.info(f"Saved metadata to: {metadata_path}")

        return model_path

    def load_model(
        self,
        model_name: str,
        method: str = "joblib"
    ) -> Any:
        """
        Load saved model.

        Args:
            model_name: Name of the model (without extension).
            method: Serialization method ('joblib' or 'pickle').

        Returns:
            Loaded model object.
        """
        model_path = self.base_path / f"{model_name}.pkl"

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        if method == "joblib":
            model = joblib.load(model_path)
        elif method == "pickle":
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
        else:
            raise ValueError(f"Unknown serialization method: {method}")

        logger.info(f"Loaded model from: {model_path}")
        return model

    def load_metadata(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Load model metadata.

        Args:
            model_name: Name of the model.

        Returns:
            Metadata dictionary or None if not found.
        """
        metadata_path = self.base_path / f"{model_name}_metadata.json"

        if not metadata_path.exists():
            logger.warning(f"Metadata file not found: {metadata_path}")
            return None

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        logger.info(f"Loaded metadata from: {metadata_path}")
        return metadata

    def list_models(self) -> list:
        """
        List all available models.

        Returns:
            List of model names (without extensions).
        """
        model_files = list(self.base_path.glob("*.pkl"))
        model_names = [f.stem for f in model_files if not f.stem.endswith('_metadata')]

        return sorted(model_names)

    def delete_model(self, model_name: str) -> bool:
        """
        Delete model and its metadata.

        Args:
            model_name: Name of the model to delete.

        Returns:
            bool: True if deletion was successful.
        """
        model_path = self.base_path / f"{model_name}.pkl"
        metadata_path = self.base_path / f"{model_name}_metadata.json"

        success = True

        if model_path.exists():
            model_path.unlink()
            logger.info(f"Deleted model: {model_path}")
        else:
            logger.warning(f"Model file not found: {model_path}")
            success = False

        if metadata_path.exists():
            metadata_path.unlink()
            logger.info(f"Deleted metadata: {metadata_path}")

        return success

    def save_feature_importance(
        self,
        importance: Dict[str, float],
        model_name: str,
        save_csv: bool = True
    ) -> Optional[Path]:
        """
        Save feature importance scores.

        Args:
            importance: Dictionary of feature names and importance scores.
            model_name: Name of the associated model.
            save_csv: Whether to save as CSV file.

        Returns:
            Path to saved file or None.
        """
        if not importance:
            logger.warning("No feature importance to save")
            return None

        # Create DataFrame
        importance_df = pd.DataFrame([
            {"feature": feature, "importance": score}
            for feature, score in importance.items()
        ]).sort_values("importance", ascending=False)

        if save_csv:
            csv_path = self.base_path / f"{model_name}_feature_importance.csv"
            importance_df.to_csv(csv_path, index=False)
            logger.info(f"Saved feature importance to: {csv_path}")
            return csv_path

        return None


# Convenience functions
def save_model(
    model: Any,
    model_path: Union[str, Path],
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Simple model saving function.

    Args:
        model: Trained model object.
        model_path: Path to save the model.
        metadata: Optional metadata dictionary.
    """
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    # Save model
    joblib.dump(model, model_path)
    logger.info(f"Saved model to: {model_path}")

    # Save metadata if provided
    if metadata:
        metadata_path = model_path.with_suffix('.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        logger.info(f"Saved metadata to: {metadata_path}")


def load_model(model_path: Union[str, Path]) -> Any:
    """
    Simple model loading function.

    Args:
        model_path: Path to the saved model.

    Returns:
        Loaded model object.
    """
    model_path = Path(model_path)

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    model = joblib.load(model_path)
    logger.info(f"Loaded model from: {model_path}")
    return model


if __name__ == "__main__":
    # Demo/test the model store functionality
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.datasets import make_classification

    print("Model Store Demo")
    print("=" * 40)

    # Create sample model
    X, y = make_classification(n_samples=100, n_features=10, random_state=42)
    model = RandomForestClassifier(random_state=42)
    model.fit(X, y)

    # Initialize model store
    store = ModelStore("models_demo")

    # Create sample metadata
    metadata = {
        "model_type": "RandomForestClassifier",
        "n_features": X.shape[1],
        "n_samples": X.shape[0],
        "accuracy": model.score(X, y),
        "created_at": "2025-01-01T00:00:00"
    }

    # Save model
    model_path = store.save_model(model, "demo_model", metadata)
    print(f"Model saved to: {model_path}")

    # Save feature importance
    feature_names = [f"feature_{i}" for i in range(X.shape[1])]
    importance_dict = dict(zip(feature_names, model.feature_importances_))
    importance_path = store.save_feature_importance(importance_dict, "demo_model")
    print(f"Feature importance saved to: {importance_path}")

    # List models
    models = store.list_models()
    print(f"Available models: {models}")

    # Load model and metadata
    loaded_model = store.load_model("demo_model")
    loaded_metadata = store.load_metadata("demo_model")

    print(f"Loaded model type: {type(loaded_model)}")
    print(f"Loaded metadata: {loaded_metadata}")

    # Test prediction
    predictions = loaded_model.predict(X[:5])
    print(f"Sample predictions: {predictions}")

    # Clean up
    store.delete_model("demo_model")
    print("Demo model deleted")