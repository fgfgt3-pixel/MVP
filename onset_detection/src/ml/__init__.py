"""Machine Learning module for onset detection."""

from .window_features import generate_window_features
from .labeler import create_training_dataset, create_labels, prepare_training_data
from .train import train_pipeline
from .model_store import ModelStore, save_model, load_model

__all__ = [
    'generate_window_features',
    'create_training_dataset',
    'create_labels',
    'prepare_training_data',
    'train_pipeline',
    'ModelStore',
    'save_model',
    'load_model'
]