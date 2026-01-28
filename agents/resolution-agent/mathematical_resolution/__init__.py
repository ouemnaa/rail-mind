"""
Rail Brain - Intelligent Rail Network Conflict Resolution

A streamlined implementation with:
- data_structures.py: Core data types
- math.py: All mathematical models and optimization algorithms
- gnn.py: Graph Neural Network for embeddings
- solver_selector.py: AI model for solver selection
- orchestrator.py: Main coordination logic
"""

from .data_structures import (
    ActionType,
    Conflict,
    Context,
    Resolution,
    ResolutionPlan,
    RailGraph,
    HistoricalConflict,
    SimilarCase,
    LombardyStation,
    LombardyRail,
    LombardyTrain,
)

from .math import (
    DelayParams,
    DelayPropagation,
    FitnessWeights,
    FitnessEvaluator,
    ConflictAwareActionGenerator,
    ActionValidator,
    GreedySolver,
    LargeNeighborhoodSearch,
    SimulatedAnnealing,
    GeneticAlgorithm,
    NSGAII,
)

from .gnn import (
    GNNConfig,
    MessagePassingLayer,
    GraphEncoder,
    GNNEmbedder,
    build_rail_graph,
)

from .solver_selector import (
    SolverType,
    SolverPerformance,
    SolverSelectorNetwork,
    EnsembleSolverSelector,
)

from .orchestrator import (
    OrchestratorConfig,
    ResolutionOrchestrator,
    resolve_conflict,
)

from .conflict_adapter import (
    load_conflicts_from_json,
    load_conflicts_from_dict,
    enrich_conflicts_with_train_data,
    summarize_conflict,
    summarize_all_conflicts,
    convert_conflict,
)

__all__ = [
    # Data structures
    "ActionType",
    "Conflict",
    "Context", 
    "Resolution",
    "ResolutionPlan",
    "RailGraph",
    "HistoricalConflict",
    "SimilarCase",
    "LombardyStation",
    "LombardyRail",
    "LombardyTrain",
    # Math
    "DelayParams",
    "DelayPropagation",
    "FitnessWeights",
    "FitnessEvaluator",
    "GreedySolver",
    "LargeNeighborhoodSearch",
    "SimulatedAnnealing",
    "GeneticAlgorithm",
    "NSGAII",
    # GNN
    "GNNConfig",
    "MessagePassingLayer",
    "GraphEncoder",
    "GNNEmbedder",
    "build_rail_graph",
    # Solver selector
    "SolverType",
    "SolverPerformance",
    "SolverSelectorNetwork",
    "EnsembleSolverSelector",
    # Orchestrator
    "OrchestratorConfig",
    "ResolutionOrchestrator",
    "resolve_conflict",
    # Conflict Adapter
    "load_conflicts_from_json",
    "load_conflicts_from_dict",
    "enrich_conflicts_with_train_data",
    "summarize_conflict",
    "summarize_all_conflicts",
    "convert_conflict",
]
