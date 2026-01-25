"""
Data models for the conflict detection engine.
These are runtime representations used by the detection layer.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal
from enum import Enum
from datetime import datetime
import uuid


# =============================================================================
# Enums
# =============================================================================

class TrainType(Enum):
    REGIONAL = "regional"
    INTERCITY = "intercity"
    EUROCITY = "eurocity"
    FREIGHT = "freight"
    HIGH_SPEED = "high_speed"


class TrainStatus(Enum):
    ON_TIME = "on_time"
    DELAYED = "delayed"
    STOPPED = "stopped"
    HOLDING = "holding"
    EN_ROUTE = "en_route"


class BlockingBehavior(Enum):
    HARD = "hard"
    SOFT = "soft"


class SignalControl(Enum):
    LOCAL = "local"
    REGIONAL = "regional"
    CENTRALIZED = "centralized"


class CongestionLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskProfile(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentType(Enum):
    TECHNICAL = "technical"
    TRESPASSER = "trespasser"
    POLICE = "police"
    MAINTENANCE = "maintenance"
    SIGNAL_FAILURE = "signal_failure"
    OTHER = "other"


@dataclass
class Incident:
    """Represents an active disruption on the network."""
    incident_id: str
    type: IncidentType
    severity: float  # 0.0 to 100.0
    start_time: datetime
    is_blocking: bool = False
    description: str = ""


class ConflictType(Enum):
    # Edge-level
    EDGE_CAPACITY_OVERFLOW = "edge_capacity_overflow"
    HEADWAY_VIOLATION = "headway_violation"
    OPPOSITE_DIRECTION_CONFLICT = "opposite_direction_conflict"
    SPEED_INCOMPATIBILITY = "speed_incompatibility"
    SAFETY_VIOLATION = "safety_violation"  # New: Train in restricted zone
    
    # Station-level
    PLATFORM_OVERFLOW = "platform_overflow"
    SIMULTANEOUS_ARRIVAL_OVERFLOW = "simultaneous_arrival_overflow"
    DWELL_TIME_VIOLATION = "dwell_time_violation"
    BLOCKING_BEHAVIOR_VIOLATION = "blocking_behavior_violation"
    
    # Train-level
    PRIORITY_INVERSION = "priority_inversion"
    DELAY_PROPAGATION_RISK = "delay_propagation_risk"
    UNAUTHORIZED_HOLD = "unauthorized_hold"
    
    # Network-level
    CASCADING_CONGESTION = "cascading_congestion"
    HUB_SATURATION = "hub_saturation"
    HIGH_RISK_EDGE_STRESS = "high_risk_edge_stress"


# =============================================================================
# Station Model (Node)
# =============================================================================

@dataclass
class Station:
    """Runtime representation of a station node."""
    id: str
    name: str
    lat: float
    lon: float
    region: str
    
    # Capacity
    platforms: int
    max_trains_at_once: int
    max_simultaneous_arrivals: int
    
    # Operations
    min_dwell_time_sec: int
    blocking_behavior: BlockingBehavior
    signal_control: SignalControl
    has_switchyard: bool
    hold_allowed: bool
    max_hold_time_sec: int
    
    # Priority
    priority_station: bool
    priority_override_allowed: bool
    
    # Historical
    historical_congestion_level: CongestionLevel
    avg_delay_sec: int
    
    # Runtime state (mutable)
    current_trains: List[str] = field(default_factory=list)
    pending_arrivals: List[str] = field(default_factory=list)
    active_incidents: List[Incident] = field(default_factory=list)
    
    @property
    def current_occupancy(self) -> int:
        return len(self.current_trains)
    
    @property
    def is_at_capacity(self) -> bool:
        return self.current_occupancy >= self.max_trains_at_once


# =============================================================================
# Rail Segment Model (Edge)
# =============================================================================

@dataclass
class RailSegment:
    """Runtime representation of a rail edge."""
    source: str
    target: str
    edge_type: str
    
    # Physical
    distance_km: float
    travel_time_min: float
    max_speed_kmh: int
    
    # Capacity
    capacity: int
    current_load: int
    
    # Operations
    direction: str  # "bidirectional", "single_track"
    min_headway_sec: int
    reroutable: bool
    priority_access: List[str]
    
    # Risk
    risk_profile: RiskProfile
    historical_incidents: int
    
    # Runtime state
    trains_on_segment: List[str] = field(default_factory=list)
    last_train_entry_time: Optional[datetime] = None
    last_train_direction: Optional[str] = None  # source->target or target->source
    active_incidents: List[Incident] = field(default_factory=list)
    
    @property
    def edge_id(self) -> str:
        return f"{self.source}--{self.target}"
    
    @property
    def is_at_capacity(self) -> bool:
        return self.current_load >= self.capacity


# =============================================================================
# Train Model
# =============================================================================

@dataclass
class Train:
    """Runtime representation of a train."""
    train_id: str
    train_type: TrainType
    route_id: int
    
    # Route (ordered station list)
    route: List[Dict]  # [{station_name, station_order, lat, lon, distance_from_previous_km}]
    
    # Current state
    current_position_type: Literal["station", "edge"]
    current_station: Optional[str] = None
    current_edge: Optional[str] = None  # "SOURCE--TARGET"
    
    # Progress
    route_index: int = 0  # Current position in route
    progress_on_edge: float = 0.0  # 0.0 to 1.0
    
    # Timing
    scheduled_departure: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    scheduled_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    
    # Speed & delay
    current_speed_kmh: float = 0.0
    delay_seconds: int = 0
    
    # Status
    status: TrainStatus = TrainStatus.ON_TIME
    
    # Hold state
    hold_start_time: Optional[datetime] = None
    
    @property
    def priority(self) -> int:
        """Higher number = higher priority."""
        priorities = {
            TrainType.HIGH_SPEED: 5,
            TrainType.EUROCITY: 4,
            TrainType.INTERCITY: 3,
            TrainType.REGIONAL: 2,
            TrainType.FREIGHT: 1,
        }
        return priorities.get(self.train_type, 1)
    
    @property
    def next_station(self) -> Optional[str]:
        if self.route_index + 1 < len(self.route):
            return self.route[self.route_index + 1]["station_name"]
        return None
    
    @property
    def previous_station(self) -> Optional[str]:
        if self.route_index > 0:
            return self.route[self.route_index - 1]["station_name"]
        return None


# =============================================================================
# Conflict Event
# =============================================================================

@dataclass
class Conflict:
    """A detected conflict event."""
    conflict_id: str
    timestamp: datetime
    conflict_type: ConflictType
    severity: ConflictSeverity
    
    # Location
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    
    # Involved parties
    involved_trains: List[str] = field(default_factory=list)
    
    # Rule info
    rule_triggered: str = ""
    explanation: str = ""
    
    # Additional context
    metadata: Dict = field(default_factory=dict)
    
    @staticmethod
    def create(
        conflict_type: ConflictType,
        severity: ConflictSeverity,
        rule_triggered: str,
        explanation: str,
        node_id: Optional[str] = None,
        edge_id: Optional[str] = None,
        involved_trains: List[str] = None,
        metadata: Dict = None
    ) -> "Conflict":
        return Conflict(
            conflict_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            conflict_type=conflict_type,
            severity=severity,
            node_id=node_id,
            edge_id=edge_id,
            involved_trains=involved_trains or [],
            rule_triggered=rule_triggered,
            explanation=explanation,
            metadata=metadata or {}
        )
    
    def to_dict(self) -> Dict:
        return {
            "conflict_id": self.conflict_id,
            "timestamp": self.timestamp.isoformat(),
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "location": {
                "node_id": self.node_id,
                "edge_id": self.edge_id
            },
            "involved_trains": self.involved_trains,
            "rule_triggered": self.rule_triggered,
            "explanation": self.explanation,
            "metadata": self.metadata
        }
