"""
Conflict Prediction Configuration
==================================

Centralized configuration for the ML-based conflict prediction module.
"""

from pathlib import Path
from typing import Literal
from dataclasses import dataclass, field

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data-preprocessing" / "data"
PROCESSED_DIR = DATA_DIR / "processed_data"
VECTOR_DB_DIR = BASE_DIR / "data-preprocessing" / "vector-database" / "output"
NETWORK_GRAPH_DIR = BASE_DIR / "data-preprocessing" / "railway-network-graph" / "output"
SIMULATION_DATA_DIR = BASE_DIR / "creating-context"
MODEL_DIR = Path(__file__).parent / "models"

# Input files
FAULT_DATA = VECTOR_DB_DIR / "fault_data_enriched_full.json"
OPERATION_DATA = PROCESSED_DIR / "operation_data_enriched.csv"
STATION_DATA = PROCESSED_DIR / "station_data_enriched.csv"
NETWORK_GRAPH = NETWORK_GRAPH_DIR / "rail_network_graph.json"
SIMULATION_DATA = SIMULATION_DATA_DIR / "lombardy_simulation_data.json"

# Model files
MODEL_FILE = MODEL_DIR / "conflict_predictor_xgb.joblib"
SCALER_FILE = MODEL_DIR / "feature_scaler.joblib"
FEATURE_CONFIG_FILE = MODEL_DIR / "feature_config.json"


# ============================================================================
# PREDICTION STRATEGY
# ============================================================================

@dataclass
class PredictionConfig:
    """Configuration for prediction strategy."""
    
    # Strategy: "continuous" (every step) or "smart" (trigger-based)
    strategy: Literal["continuous", "smart"] = "continuous"  # Changed to continuous
    
    # Prediction horizon (minutes ahead to predict)
    prediction_horizon_min: int = 15  # Predict 15 minutes ahead
    prediction_horizon_max: int = 30  # Up to 30 minutes ahead
    
    # Smart trigger thresholds
    trigger_delay_threshold_sec: int = 120  # Trigger when delay > 2 min
    trigger_congestion_threshold: float = 0.7  # Trigger when station > 70% capacity
    trigger_approaching_hub: bool = True  # Trigger when train approaches major hub
    
    # Continuous prediction interval (if using continuous strategy)
    continuous_interval_sec: int = 30  # Predict every 30 simulation seconds (more frequent)
    
    # Feature computation
    lookback_window_min: int = 30  # Historical window for features
    
    # Ensemble configuration (XGBoost + Heuristics)
    # Set to True after running train_model_v2.py which uses FeatureEngine for 28 features
    use_ensemble: bool = True  # ✓ Enabled - model trained with 28 features
    ml_weight: float = 0.7  # Weight for ML predictions (0.0 to 1.0)
    heuristic_weight: float = 0.3  # Weight for heuristic predictions
    agreement_boost: float = 1.15  # Boost factor when ML and heuristics agree
    agreement_threshold: float = 0.6  # Threshold for considering predictions as "agreeing"


# ============================================================================
# CONFLICT THRESHOLDS
# ============================================================================

@dataclass
class ConflictThresholds:
    """Thresholds for conflict risk levels."""
    
    # Probability thresholds for color coding
    safe_threshold: float = 0.3        # GREEN: prob < 0.3
    low_risk_threshold: float = 0.5    # YELLOW: 0.3 <= prob < 0.5
    high_risk_threshold: float = 0.8   # ORANGE: 0.5 <= prob < 0.8
    # RED: prob >= 0.8 or actual conflict detected
    
    # Risk level names
    risk_levels: dict = field(default_factory=lambda: {
        "safe": {"color": "#22c55e", "label": "Safe", "emoji": "🟢"},
        "low_risk": {"color": "#eab308", "label": "Low Risk", "emoji": "🟡"},
        "high_risk": {"color": "#f97316", "label": "High Risk", "emoji": "🟠"},
        "critical": {"color": "#ef4444", "label": "Critical", "emoji": "🔴"}
    })


# ============================================================================
# CONFLICT TYPES (Operational)
# ============================================================================

CONFLICT_TYPES = [
    "platform_conflict",      # Multiple trains assigned to same platform
    "track_conflict",         # Two trains on same track segment
    "headway_violation",      # Minimum headway not maintained
    "capacity_exceeded",      # Station/track capacity exceeded
    "schedule_deviation",     # Significant deviation from timetable
    "cascading_delay",        # Delay propagating through network
]

# ============================================================================
# INCIDENT TYPES (From historical fault data)
# ============================================================================

INCIDENT_TYPES = [
    "technical",              # Equipment/infrastructure failure
    "trespasser",             # Unauthorized persons on tracks
    "weather",                # Weather-related issues
    "maintenance",            # Scheduled/unscheduled maintenance
    "fire",                   # Fire incidents
    "police_intervention",    # Police/security intervention
    "other",                  # Other incidents
]

# Mapping incident types to operational conflict patterns
INCIDENT_TO_CONFLICT_MAP = {
    "technical": ["track_conflict", "schedule_deviation", "cascading_delay"],
    "trespasser": ["track_conflict", "schedule_deviation"],
    "weather": ["schedule_deviation", "cascading_delay"],
    "maintenance": ["track_conflict", "capacity_exceeded"],
    "fire": ["track_conflict", "capacity_exceeded", "cascading_delay"],
    "police_intervention": ["schedule_deviation"],
    "other": ["schedule_deviation"],
}

# Resolution types from historical data
RESOLUTION_TYPES = [
    "SPEED_REGULATE",         # Speed restrictions applied
    "CANCEL",                 # Train cancelled
    "SINGLE_TRACK",           # Single track operation
    "GRADUAL_RECOVERY",       # Gradual service recovery
    "REROUTE",                # Reroute via alternate path
]

# Lombardy major stations (from simulation data)
LOMBARDY_MAJOR_HUBS = [
    "MILANO CENTRALE",
    "MILANO PORTA GARIBALDI",
    "MILANO CADORNA",
    "MILANO BOVISA",
    "MILANO LAMBRATE",
    "BRESCIA",
    "BERGAMO",
    "PAVIA",
    "MONZA",
    "VARESE",
    "COMO SAN GIOVANNI",
    "LECCO",
    "CREMONA",
    "MANTOVA",
]


# ============================================================================
# XGBOOST MODEL PARAMETERS
# ============================================================================

@dataclass
class XGBoostConfig:
    """XGBoost model hyperparameters."""
    
    n_estimators: int = 200
    max_depth: int = 8
    learning_rate: float = 0.1
    min_child_weight: int = 3
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    gamma: float = 0.1
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    scale_pos_weight: float = 3.0  # Handle class imbalance
    random_state: int = 42
    n_jobs: int = -1
    eval_metric: str = "logloss"
    early_stopping_rounds: int = 20


# ============================================================================
# QDRANT CONFIGURATION
# ============================================================================

@dataclass
class QdrantConfig:
    """Qdrant vector database configuration."""
    
    # Deployment mode
    mode: Literal["cloud", "local"] = "local"
    
    # Cloud settings (if using Qdrant Cloud)
    cloud_url: str = ""
    api_key: str = ""
    
    # Local settings (if using Docker)
    host: str = "localhost"
    port: int = 6333
    
    # Collection settings
    collection_name: str = "rail_conflicts"
    
    # Embedding model (multilingual for Italian support)
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    vector_size: int = 384
    
    # Similarity search parameters
    top_k: int = 5  # Number of similar cases to retrieve
    score_threshold: float = 0.7  # Minimum similarity score


# ============================================================================
# API CONFIGURATION
# ============================================================================

@dataclass
class APIConfig:
    """FastAPI service configuration."""
    
    host: str = "0.0.0.0"
    port: int = 8002
    reload: bool = True
    
    # CORS settings (for frontend)
    cors_origins: list = field(default_factory=lambda: [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "http://localhost:8081",  # Vite alternate port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8081",
        "*",  # Allow all origins for development
    ])


# ============================================================================
# FEATURE GROUPS
# ============================================================================

# Features used by the XGBoost model
TRAIN_FEATURES = [
    "current_delay_sec",
    "delay_rate_per_km",
    "distance_to_next_station_km",
    "time_to_next_station_sec",
    "train_type_encoded",
    "priority_level",
    "remaining_stops",
]

STATION_FEATURES = [
    "current_occupancy",
    "platform_utilization",
    "expected_arrivals_15min",
    "expected_departures_15min",
    "is_hub",
    "is_major_hub",
    "historical_congestion_level",
    "avg_delay_sec",
]

NETWORK_FEATURES = [
    "segment_utilization",
    "upstream_congestion",
    "downstream_congestion",
    "competing_trains_count",
    "network_load_factor",
]

TEMPORAL_FEATURES = [
    "hour_of_day",
    "day_of_week",
    "is_peak_hour",
    "is_weekend",
    "is_holiday",
]

INTERACTION_FEATURES = [
    "delay_congestion_interaction",
    "hub_peak_interaction",
    "train_priority_station_type_interaction",
]


# ============================================================================
# DEFAULTS
# ============================================================================

# Default instances
prediction_config = PredictionConfig()
conflict_thresholds = ConflictThresholds()
xgboost_config = XGBoostConfig()
qdrant_config = QdrantConfig()
api_config = APIConfig()
