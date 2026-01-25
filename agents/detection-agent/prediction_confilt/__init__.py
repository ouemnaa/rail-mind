"""
Rail-Mind Conflict Prediction Module
=====================================

ML-based conflict prediction for Lombardy rail network with:
- XGBoost classifier with graph-aware features
- Smart prediction triggers (continuous + event-based)
- Qdrant similarity search for operational memory
- Real-time prediction API

Architecture:
    predictor.py       - Main XGBoost conflict predictor
    feature_engine.py  - Feature engineering pipeline
    qdrant_memory.py   - Similarity search for historical cases
    prediction_api.py  - FastAPI service for real-time predictions
    config.py          - Configuration settings
"""

from .predictor import ConflictPredictor
from .feature_engine import FeatureEngine
from .qdrant_memory import OperationalMemory

__all__ = ['ConflictPredictor', 'FeatureEngine', 'OperationalMemory']
__version__ = '1.0.0'
