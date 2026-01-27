"""
Rail-Mind Integration Module
============================

This module bridges the ML-based prediction system with the 
deterministic rule-based detection system.

Main Components:
- IntegrationEngine: Unified engine combining prediction + detection
- UnifiedConflict: Common conflict representation
- SimulationState: Complete simulation state for API responses

Usage:
    from integration import IntegrationEngine
    
    engine = IntegrationEngine()
    engine.initialize()
    
    # Run simulation ticks
    state = engine.tick()
    
    # state contains:
    # - trains: list of train positions
    # - predictions: ML + heuristics predictions (10-30 min ahead)
    # - detections: rule-based detections (real-time)
    # - statistics: simulation metrics
"""

from .integration_engine import (
    IntegrationEngine,
    UnifiedConflict,
    SimulationState,
    TrainPosition
)

__all__ = [
    'IntegrationEngine',
    'UnifiedConflict', 
    'SimulationState',
    'TrainPosition'
]
