"""
Core data structures for rail network conflict resolution.
Assumes embeddings and conflicts are pre-given.
Designed for Lombardy rail network data format.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
import numpy as np


class ActionType(Enum):
    HOLD = "hold"
    REROUTE = "reroute"
    CANCEL = "cancel"
    SPEED_ADJUST = "speed_adjust"
    PLATFORM_CHANGE = "platform_change"


@dataclass
class Conflict:
    """Pre-given conflict snapshot."""
    conflict_id: str
    station_ids: List[str]
    train_ids: List[str]
    delay_values: Dict[str, float]  # train_id -> delay in minutes
    timestamp: float
    severity: float  # 0-1 scale
    conflict_type: str  # "platform", "track", "headway", "capacity", "delay", "collision", "route_conflict", "signal"
    
    # Pre-computed embedding (given)
    embedding: Optional[np.ndarray] = None
    
    # Additional Lombardy-specific fields
    affected_rails: Optional[List[Dict]] = None  # rails involved in conflict
    blocking_behavior: Optional[str] = None  # "hard" or "soft"
    priority_trains: Optional[List[str]] = None  # high_speed > intercity > regional


@dataclass
class HistoricalConflict:
    """
    A past conflict with known resolution and outcome.
    Used for case-based reasoning / retrieval.
    """
    conflict: Conflict
    resolution_applied: List['Resolution']  # what was done
    outcome_delay: float  # actual total delay after resolution
    outcome_passenger_impact: float
    outcome_propagation: int  # how many trains affected
    success_score: float  # 0-1, how well it worked
    
    # Pre-computed embedding for similarity search
    embedding: Optional[np.ndarray] = None


@dataclass
class SimilarCase:
    """
    A retrieved similar conflict with similarity score.
    """
    historical: HistoricalConflict
    similarity: float  # 0-1, how similar to current conflict
    
    def get_suggested_actions(self) -> List['Resolution']:
        """Return what worked in this similar case."""
        return self.historical.resolution_applied


@dataclass
class Context:
    """Operational context at time of conflict."""
    time_of_day: float  # 0-24
    day_of_week: int  # 0-6
    is_peak_hour: bool
    weather_condition: str  # "clear", "rain", "snow", "fog"
    network_load: float  # 0-1
    
    def to_vector(self) -> np.ndarray:
        weather_map = {"clear": 0, "rain": 1, "snow": 2, "fog": 3}
        return np.array([
            self.time_of_day / 24.0,
            self.day_of_week / 6.0,
            float(self.is_peak_hour),
            weather_map.get(self.weather_condition, 0) / 3.0,
            self.network_load
        ])


@dataclass
class Resolution:
    """A proposed resolution action."""
    action_type: ActionType
    target_train_id: str
    parameters: Dict  # action-specific params
    
    def to_vector(self) -> np.ndarray:
        action_idx = list(ActionType).index(self.action_type)
        return np.array([action_idx / len(ActionType)])


@dataclass
class ResolutionPlan:
    """Complete resolution plan with fitness scores."""
    actions: List[Resolution]
    total_delay: float
    passenger_impact: float
    propagation_depth: int
    recovery_smoothness: float
    overall_fitness: float
    solver_used: str


@dataclass
class RailGraph:
    """Graph representation of rail network for GNN - matches Lombardy format."""
    node_features: np.ndarray  # (num_nodes, node_feat_dim)
    edge_index: np.ndarray     # (2, num_edges) - source, target pairs
    edge_features: Optional[np.ndarray] = None  # (num_edges, edge_feat_dim)
    node_ids: Optional[List[str]] = None  # station IDs
    
    # Lombardy-specific lookups
    station_data: Optional[Dict[str, Dict]] = None  # station_id -> full station dict
    rail_data: Optional[List[Dict]] = None  # list of rail edge dicts


@dataclass 
class LombardyStation:
    """Station data matching the Lombardy JSON format."""
    id: str
    name: str
    lat: float
    lon: float
    platforms: int
    max_trains_at_once: int
    max_simultaneous_arrivals: int
    min_dwell_time_sec: int
    blocking_behavior: str  # "hard" or "soft"
    signal_control: str
    has_switchyard: bool
    hold_allowed: bool
    max_hold_time_sec: int
    priority_station: bool
    historical_congestion_level: str  # "low", "medium", "high"
    avg_delay_sec: float
    degree: int  # number of connections
    is_hub: bool
    is_major_hub: bool


@dataclass
class LombardyRail:
    """Rail edge data matching the Lombardy JSON format."""
    source: str
    target: str
    edge_type: str  # "regional", "intercity", "high_speed"
    distance_km: float
    travel_time_min: float
    capacity: int
    current_load: int
    direction: str  # "bidirectional" or "single_track"
    min_headway_sec: int
    max_speed_kmh: int
    reroutable: bool
    priority_access: List[str]
    risk_profile: str  # "low", "medium", "high"
    historical_incidents: int


@dataclass
class LombardyTrain:
    """Train data matching the Lombardy JSON format."""
    train_id: str
    train_type: str  # "high_speed", "intercity", "regional"
    route_id: int
    route: List[Dict]  # list of station stops with order, lat, lon, distance
