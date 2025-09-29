"""Training pipeline for onset detection models."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union
import json

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score, f1_score, precision_score, recall_score
from sklearn.linear_model import LogisticRegression

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from .labeler import load_ml_config, create_training_dataset, prepare_training_data
from .model_store import ModelStore

logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.warning("LightGBM not available. Using logistic regression as fallback.")


def create_model(config: Dict[str, Any]) -> Any:
    """
    Create model based on configuration.

    Args:
        config: ML configuration dictionary.

    Returns:
        Initialized model object.
    """
    train_config = config.get('train', {})
    model_type = train_config.get('model_type', 'lightgbm')
    random_state = train_config.get('random_state', 42)

    if model_type == 'lightgbm' and LIGHTGBM_AVAILABLE:
        model = lgb.LGBMClassifier(
            n_estimators=train_config.get('n_estimators', 500),
            learning_rate=train_config.get('learning_rate', 0.05),
            max_depth=train_config.get('max_depth', -1),
            random_state=random_state,
            class_weight=train_config.get('class_weight', 'balanced'),
            verbose=-1  # Suppress LightGBM output
        )
        logger.info("Created LightGBM classifier")

    elif model_type == 'logistic':
        model = LogisticRegression(
            random_state=random_state,
            class_weight=train_config.get('class_weight', 'balanced'),
            max_iter=1000
        )
        logger.info("Created Logistic Regression classifier")

    else:
        # Fallback to logistic regression
        logger.warning(f"Unknown or unavailable model type '{model_type}'. Using logistic regression.")
        model = LogisticRegression(
            random_state=random_state,
            class_weight=train_config.get('class_weight', 'balanced'),
            max_iter=1000
        )

    return model


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    config: Dict[str, Any]
) -> Tuple[Any, Dict[str, Any]]:
    """
    Train model and evaluate performance.

    Args:
        X_train: Training features.
        y_train: Training targets.
        X_test: Test features.
        y_test: Test targets.
        config: ML configuration dictionary.

    Returns:
        Tuple: (trained_model, metrics_dict).
    """
    logger.info(f"Training model with {X_train.shape[0]} samples, {X_train.shape[1]} features")

    # Create model
    model = create_model(config)

    # Train model
    model.fit(X_train, y_train)
    logger.info("Model training completed")

    # Make predictions
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]  # Probability for positive class

    # Calculate metrics
    metrics = {
        'accuracy': model.score(X_test, y_test),
        'auc': roc_auc_score(y_test, y_pred_proba),
        'f1': f1_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'n_features': X_train.shape[1]
    }

    # Cross-validation scores
    train_config = config.get('train', {})
    cv_folds = train_config.get('cv_folds', 5)

    if len(X_train) > cv_folds * 10:  # Only do CV if we have enough samples
        cv_scores = cross_val_score(model, X_train, y_train, cv=cv_folds, scoring='roc_auc')
        metrics['cv_auc_mean'] = cv_scores.mean()
        metrics['cv_auc_std'] = cv_scores.std()
        logger.info(f"Cross-validation AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    logger.info(f"Test metrics - AUC: {metrics['auc']:.4f}, F1: {metrics['f1']:.4f}")
    logger.info(f"Precision: {metrics['precision']:.4f}, Recall: {metrics['recall']:.4f}")

    return model, metrics


def extract_feature_importance(model: Any, feature_names: list) -> Dict[str, float]:
    """
    Extract feature importance from trained model.

    Args:
        model: Trained model object.
        feature_names: List of feature names.

    Returns:
        Dict: Feature importance scores.
    """
    importance_dict = {}

    if hasattr(model, 'feature_importances_'):
        # Tree-based models (LightGBM, RandomForest, etc.)
        importances = model.feature_importances_
        importance_dict = dict(zip(feature_names, importances))
        logger.info(f"Extracted feature importances from {type(model).__name__}")

    elif hasattr(model, 'coef_'):
        # Linear models (LogisticRegression, etc.)
        coefficients = np.abs(model.coef_[0])  # Take absolute values
        importance_dict = dict(zip(feature_names, coefficients))
        logger.info(f"Extracted coefficients as feature importance from {type(model).__name__}")

    else:
        logger.warning("Model does not have feature importance or coefficients")

    return importance_dict


def train_pipeline(
    features_file: Union[str, Path],
    events_file: Union[str, Path],
    output_model_name: str = "onset_model",
    target_column: str = "y_span",
    config_path: Optional[Union[str, Path]] = None
) -> Tuple[Any, Dict[str, Any]]:
    """
    Complete training pipeline from features and events to trained model.

    Args:
        features_file: Path to features CSV file.
        events_file: Path to events JSONL file.
        output_model_name: Name for saved model.
        target_column: Target column name ('y_span' or 'y_forecast').
        config_path: Path to ML config file.

    Returns:
        Tuple: (trained_model, training_metrics).
    """
    logger.info("Starting training pipeline")

    # Load configuration
    config = load_ml_config(config_path) if config_path else load_ml_config()

    # Create training dataset
    logger.info("Creating labeled dataset")
    labeled_df = create_training_dataset(
        features_file=features_file,
        events_file=events_file,
        config=config
    )

    # Prepare training data
    logger.info("Preparing training data")
    X, y = prepare_training_data(labeled_df, config, target_column)

    # Check class balance
    class_dist = y.value_counts()
    logger.info(f"Class distribution: {dict(class_dist)}")

    if len(class_dist) < 2:
        raise ValueError("Need at least 2 classes for training")

    positive_rate = class_dist.get(1, 0) / len(y)
    if positive_rate < 0.01 or positive_rate > 0.99:
        logger.warning(f"Extreme class imbalance detected: {positive_rate:.4f} positive rate")

    # Train/test split
    train_config = config.get('train', {})
    test_size = train_config.get('test_size', 0.2)
    random_state = train_config.get('random_state', 42)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    logger.info(f"Split data - Train: {len(X_train)}, Test: {len(X_test)}")

    # Train model
    model, metrics = train_model(X_train, y_train, X_test, y_test, config)

    # Extract feature importance
    importance = extract_feature_importance(model, list(X.columns))

    # Save model and results
    model_store = ModelStore()

    # Create metadata
    metadata = {
        'model_type': type(model).__name__,
        'target_column': target_column,
        'n_features': X.shape[1],
        'n_samples': X.shape[0],
        'positive_rate': positive_rate,
        'config': config,
        'metrics': metrics,
        'feature_names': list(X.columns)
    }

    # Save model
    model_path = model_store.save_model(model, output_model_name, metadata)
    logger.info(f"Saved model to: {model_path}")

    # Save feature importance
    if importance:
        importance_path = model_store.save_feature_importance(importance, output_model_name)
        logger.info(f"Saved feature importance to: {importance_path}")

    return model, metrics


def main():
    """Main training script entry point."""
    parser = argparse.ArgumentParser(description="Train onset detection model")

    parser.add_argument("--features", type=str, required=True, help="Features CSV file")
    parser.add_argument("--events", type=str, required=True, help="Events JSONL file")
    parser.add_argument("--output", type=str, default="onset_model", help="Output model name")
    parser.add_argument("--target", type=str, default="y_span",
                       choices=["y_span", "y_forecast"], help="Target column")
    parser.add_argument("--config", type=str, help="ML config YAML file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        logger.info("Starting onset detection model training")

        # Run training pipeline
        model, metrics = train_pipeline(
            features_file=args.features,
            events_file=args.events,
            output_model_name=args.output,
            target_column=args.target,
            config_path=args.config
        )

        # Print summary
        print("\n" + "="*50)
        print("TRAINING COMPLETED")
        print("="*50)
        print(f"Model type: {type(model).__name__}")
        print(f"Target: {args.target}")
        print(f"Test AUC: {metrics['auc']:.4f}")
        print(f"Test F1: {metrics['f1']:.4f}")
        print(f"Features used: {metrics['n_features']}")
        print(f"Training samples: {metrics['train_samples']}")
        print(f"Model saved as: {args.output}")

        logger.info("Training pipeline completed successfully")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


if __name__ == "__main__":
    main()