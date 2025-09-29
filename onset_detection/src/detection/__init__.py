"""Detection module for onset candidate identification and confirmation."""

from .candidate_detector import CandidateDetector, detect_candidates
from .confirm_detector import ConfirmDetector, confirm_candidates
from .refractory_manager import RefractoryManager, process_refractory_events

__all__ = [
    'CandidateDetector',
    'detect_candidates',
    'ConfirmDetector', 
    'confirm_candidates',
    'RefractoryManager',
    'process_refractory_events'
]