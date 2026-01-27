"""
Unified Integration Engine
==========================

This module bridges the ML-based prediction system with the 
deterministic rule-based detection system.

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                    INTEGRATION ENGINE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐          ┌─────────────────────────────┐  │
│  │   SIMULATION    │─────────>│  NETWORK STATE              │  │
│  │   (Train Data)  │          │  (Real-time positions)      │  │
│  └─────────────────┘          └───────────┬─────────────────┘  │
│                                           │                     │
│           ┌───────────────────────────────┴──────────────────┐ │
│           │                                                  │ │
│           v                                                  v │
│  ┌─────────────────┐                        ┌──────────────────┐│
│  │   PREDICTION    │                        │   DETECTION      ││
│  │   (ML + Heur.)  │                        │   (Rules)        ││
│  │   10-30 min     │                        │   Real-time      ││
│  └────────┬────────┘                        └────────┬─────────┘│
│           │                                          │         │
│           │   ┌──────────────────────────────┐       │         │
│           └──>│      UNIFIED OUTPUT          │<──────┘         │
│               │  - Predictions (Orange)      │                 │
│               │  - Detections (Red)          │                 │
│               │  - Resolutions               │                 │
│               └──────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘

Why This Architecture?
---------------------
1. **Continuous Prediction**: ML predicts conflicts 10-30 min ahead
2. **Real-time Detection**: Rules catch conflicts as they happen
3. **Combined Visibility**: Frontend shows both prediction AND detection
4. **No Concept Changes**: Each system maintains its own logic
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import json
import random

# Add paths for imports
# BASE_DIR is backend folder, detection modules are in agents/detection-agent/
BASE_DIR = Path(__file__).resolve().parent.parent  # backend folder
PROJECT_ROOT = BASE_DIR.parent  # rail-mind folder
DETECTION_AGENT_DIR = PROJECT_ROOT / "agents" / "detection-agent"
sys.path.insert(0, str(DETECTION_AGENT_DIR / "prediction_confilt"))
sys.path.insert(0, str(DETECTION_AGENT_DIR / "deterministic-detection"))

# Prediction imports
from predictor import ConflictPredictor
from feature_engine import TrainState, StationState, NetworkState as PredictionNetworkState
from config import PredictionConfig

# Detection imports (using relative imports based on file structure)
try:
    from state_tracker import StateTracker, NetworkState as DetectionNetworkState
    from engine import DetectionEngine, ConflictEmitter
    from models import (
        Conflict as DetectedConflict, 
        ConflictType, ConflictSeverity,
        Train as DetectionTrain, Station as DetectionStation,
        TrainStatus, TrainType as DetTrainType,
        RailSegment, BlockingBehavior, SignalControl,
        CongestionLevel, RiskProfile
    )
except ImportError as e:
    print(f"Warning: Could not import detection modules: {e}")
    DetectionNetworkState = None
    DetectionEngine = None


@dataclass
class TrainPosition:
    """Represents a train's current position and state."""
    train_id: str
    train_type: str
    current_station: Optional[str]
    next_station: Optional[str]
    current_edge: Optional[str]
    position_km: float
    speed_kmh: float
    delay_sec: float
    status: str  # "at_station", "en_route", "delayed", "stopped"
    lat: float
    lon: float
    route: List[Dict]
    current_stop_index: int
    scheduled_departure: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "train_id": self.train_id,
            "train_type": self.train_type,
            "current_station": self.current_station,
            "next_station": self.next_station,
            "current_edge": self.current_edge,
            "position_km": self.position_km,
            "speed_kmh": self.speed_kmh,
            "delay_sec": self.delay_sec,
            "status": self.status,
            "lat": self.lat,
            "lon": self.lon,
            "route": self.route,
            "current_stop_index": self.current_stop_index
        }


@dataclass
class UnifiedConflict:
    """
    Unified representation of conflicts from both systems.
    
    source: "prediction" or "detection"
    """
    conflict_id: str
    source: str  # "prediction" or "detection"
    conflict_type: str
    severity: str  # "low", "medium", "high", "critical"
    probability: float  # 0.0-1.0 for predictions, 1.0 for detections
    location: str
    location_type: str  # "station" or "edge"
    involved_trains: List[str]
    explanation: str
    timestamp: datetime
    prediction_horizon_min: Optional[int] = None  # For predictions
    resolution_suggestions: List[str] = field(default_factory=list)
    lat: Optional[float] = None
    lon: Optional[float] = None
    model_used: str = "unknown"  # "xgboost_ensemble", "heuristic", "detection"
    
    def to_dict(self) -> Dict:
        return {
            "conflict_id": self.conflict_id,
            "source": self.source,
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "probability": self.probability,
            "location": self.location,
            "location_type": self.location_type,
            "involved_trains": self.involved_trains,
            "explanation": self.explanation,
            "timestamp": self.timestamp.isoformat(),
            "prediction_horizon_min": self.prediction_horizon_min,
            "resolution_suggestions": self.resolution_suggestions,
            "lat": self.lat,
            "lon": self.lon,
            "model_used": self.model_used
        }


@dataclass
class SimulationState:
    """Complete simulation state for the frontend."""
    simulation_time: datetime
    tick_number: int
    trains: List[TrainPosition]
    predictions: List[UnifiedConflict]
    detections: List[UnifiedConflict]
    statistics: Dict
    
    def to_dict(self) -> Dict:
        return {
            "simulation_time": self.simulation_time.isoformat(),
            "tick_number": self.tick_number,
            "trains": [t.to_dict() for t in self.trains],
            "predictions": [p.to_dict() for p in self.predictions],
            "detections": [d.to_dict() for d in self.detections],
            "statistics": self.statistics
        }


class IntegrationEngine:
    """
    Unified engine that combines ML prediction with deterministic detection.
    
    Usage:
        engine = IntegrationEngine()
        engine.initialize()
        
        # Run simulation ticks
        for _ in range(100):
            state = engine.tick()
            # state contains trains, predictions, and detections
    """
    
    def __init__(self, config: Optional[PredictionConfig] = None):
        """
        Initialize the integration engine.
        
        Args:
            config: Optional predictor configuration
        """
        self.config = config or PredictionConfig()
        
        # Initialize predictor (ML + heuristics)
        self.predictor = ConflictPredictor()
        
        # Initialize detection state tracker
        self.state_tracker = StateTracker()
        
        # Initialize detection engine
        self.detection_emitter = ConflictEmitter(enable_console=False)
        self.detection_engine = None  # Created after loading data
        
        # Simulation state
        self.simulation_time = datetime.now().replace(hour=6, minute=0, second=0)
        self.tick_number = 0
        self.tick_interval_sec = 60  # 1 minute per tick
        
        # Train positions
        self.trains: Dict[str, TrainPosition] = {}
        
        # Station data cache
        self.stations: Dict[str, Dict] = {}
        self.network_data: Dict = {}
        
        # Prediction cache
        self.last_predictions: List[UnifiedConflict] = []
        self.prediction_interval = 1  # Predict EVERY tick for continuous mode
        
        # Conflict scenario generation
        self.scenario_active = False
        self.scenario_tick = 0
        
        # CONFLICT PERSISTENCE: Keep conflicts visible for multiple ticks
        self.active_detections: Dict[str, UnifiedConflict] = {}  # conflict_id -> conflict
        self.detection_ttl: Dict[str, int] = {}  # conflict_id -> ticks remaining
        self.CONFLICT_PERSISTENCE_TICKS = 10  # Keep conflicts visible for 10 ticks (10 minutes)
        
    def initialize(self, simulation_data_path: Optional[Path] = None) -> None:
        """
        Initialize the engine with network data.
        
        Args:
            simulation_data_path: Path to lombardy_simulation_data.json
        """
        print("\n[Integration] Initializing unified engine...")
        
        # Default data path - PROJECT_ROOT is rail-mind folder
        if simulation_data_path is None:
            # Try multiple possible locations
            possible_paths = [
                PROJECT_ROOT / "creating-context" / "lombardy_simulation_data.json",
                Path(__file__).resolve().parent.parent.parent / "creating-context" / "lombardy_simulation_data.json",
            ]
            simulation_data_path = None
            for p in possible_paths:
                if p.exists():
                    simulation_data_path = p
                    break
            if simulation_data_path is None:
                simulation_data_path = possible_paths[0]  # Use first for error message
        
        # Load network data
        if simulation_data_path.exists():
            with open(simulation_data_path, 'r', encoding='utf-8') as f:
                self.network_data = json.load(f)
            print(f"  [+] Loaded network data: {len(self.network_data.get('stations', []))} stations, {len(self.network_data.get('trains', []))} train routes")
        else:
            print(f"  [!] Warning: Simulation data not found at {simulation_data_path}")
            self._generate_default_data()
        
        # Initialize stations
        self._init_stations()
        
        # Initialize trains
        self._init_trains()
        
        # Initialize detection state tracker
        self._init_detection_state()
        
        # Create detection engine
        from rules import ALL_RULES
        self.detection_engine = DetectionEngine(
            state_tracker=self.state_tracker,
            rules=ALL_RULES,
            emitter=self.detection_emitter
        )
        
        print(f"  [+] Engine initialized with {len(self.trains)} active trains")
        print(f"  [+] Prediction interval: every {self.prediction_interval} ticks")
        print(f"  [+] Tick interval: {self.tick_interval_sec} seconds")
    
    def _generate_default_data(self) -> None:
        """Generate default Lombardy network data if file not found."""
        self.network_data = {
            "stations": [
                {"id": "MI_CENTRALE", "name": "MILANO CENTRALE", "lat": 45.486, "lon": 9.204, "region": "Lombardy", "platforms": 24},
                {"id": "MI_PORTA_GARIBALDI", "name": "MILANO PORTA GARIBALDI", "lat": 45.484, "lon": 9.188, "region": "Lombardy", "platforms": 12},
                {"id": "MI_CADORNA", "name": "MILANO CADORNA", "lat": 45.466, "lon": 9.175, "region": "Lombardy", "platforms": 10},
                {"id": "MONZA", "name": "MONZA", "lat": 45.582, "lon": 9.275, "region": "Lombardy", "platforms": 6},
                {"id": "BERGAMO", "name": "BERGAMO", "lat": 45.691, "lon": 9.675, "region": "Lombardy", "platforms": 8},
                {"id": "BRESCIA", "name": "BRESCIA", "lat": 45.532, "lon": 10.212, "region": "Lombardy", "platforms": 10},
                {"id": "PAVIA", "name": "PAVIA", "lat": 45.188, "lon": 9.144, "region": "Lombardy", "platforms": 6},
                {"id": "COMO", "name": "COMO SAN GIOVANNI", "lat": 45.808, "lon": 9.077, "region": "Lombardy", "platforms": 5},
                {"id": "LECCO", "name": "LECCO", "lat": 45.857, "lon": 9.387, "region": "Lombardy", "platforms": 4},
                {"id": "VARESE", "name": "VARESE", "lat": 45.817, "lon": 8.832, "region": "Lombardy", "platforms": 5},
            ],
            "trains": [
                {"train_id": "R_2161", "train_type": "regional", "route": ["MI_CENTRALE", "MONZA", "LECCO"]},
                {"train_id": "R_2163", "train_type": "regional", "route": ["MI_CENTRALE", "BERGAMO"]},
                {"train_id": "R_2165", "train_type": "regional", "route": ["MI_CENTRALE", "BRESCIA"]},
                {"train_id": "R_2167", "train_type": "regional", "route": ["MI_CENTRALE", "PAVIA"]},
                {"train_id": "R_2169", "train_type": "regional", "route": ["MI_PORTA_GARIBALDI", "COMO", "VARESE"]},
                {"train_id": "IC_505", "train_type": "intercity", "route": ["MI_CENTRALE", "BRESCIA"]},
            ]
        }
    
    def _init_stations(self) -> None:
        """Initialize station lookup."""
        for station in self.network_data.get('stations', []):
            station_id = station.get('id', station.get('name', 'UNKNOWN'))
            self.stations[station_id] = station
            # Also map by name for lookup
            name = station.get('name', station_id)
            self.stations[name.upper()] = station
    
    def _init_trains(self) -> None:
        """Initialize trains at their starting positions."""
        for train_data in self.network_data.get('trains', [])[:30]:  # Limit to 30 trains
            train_id = train_data['train_id']
            route = train_data.get('route', [])
            
            if not route or len(route) < 2:
                continue
            
            # Route is already a list of dicts with station_name, lat, lon
            first_stop = route[0]
            second_stop = route[1] if len(route) > 1 else route[0]
            
            # Get station names
            first_station_name = first_stop.get('station_name', 'UNKNOWN')
            second_station_name = second_stop.get('station_name', 'UNKNOWN')
            
            self.trains[train_id] = TrainPosition(
                train_id=train_id,
                train_type=train_data.get('train_type', 'regional'),
                current_station=first_station_name,
                next_station=second_station_name,
                current_edge=None,
                position_km=0,
                speed_kmh=0,
                delay_sec=0,
                status="at_station",
                lat=first_stop.get('lat', 45.4),
                lon=first_stop.get('lon', 9.2),
                route=route,
                current_stop_index=0,
                scheduled_departure=self.simulation_time + timedelta(minutes=random.randint(0, 30))
            )
    
    def _init_detection_state(self) -> None:
        """Initialize the detection system's network state."""
        # Load stations into state tracker
        for station_data in self.network_data.get('stations', []):
            station_id = station_data.get('id', station_data.get('name', 'UNKNOWN'))
            station = DetectionStation(
                id=station_id,
                name=station_data.get('name', station_id),
                lat=station_data.get('lat', 45.4),
                lon=station_data.get('lon', 9.2),
                region=station_data.get('region', 'Lombardy'),
                platforms=station_data.get('platforms', 5),
                max_trains_at_once=station_data.get('platforms', 5),
                max_simultaneous_arrivals=2,
                min_dwell_time_sec=60,
                blocking_behavior=BlockingBehavior.SOFT,
                signal_control=SignalControl.REGIONAL,
                has_switchyard=station_data.get('platforms', 5) > 8,
                hold_allowed=True,
                max_hold_time_sec=300,
                priority_station=station_data.get('platforms', 5) > 10,
                priority_override_allowed=True,
                historical_congestion_level=CongestionLevel.MEDIUM,
                avg_delay_sec=60
            )
            self.state_tracker.state.stations[station_id] = station
        
        # Create edges between connected stations (route is list of dicts with station_name)
        for train_data in self.network_data.get('trains', [])[:30]:
            route = train_data.get('route', [])
            for i in range(len(route) - 1):
                # Route items are dicts with station_name, lat, lon
                source_stop = route[i]
                target_stop = route[i + 1]
                source = source_stop.get('station_name', 'UNKNOWN')
                target = target_stop.get('station_name', 'UNKNOWN')
                edge_key = f"{source}--{target}"
                
                if edge_key not in self.state_tracker.state.edges:
                    # Calculate distance from route data if available
                    distance_km = target_stop.get('distance_from_previous_km', 20)
                    
                    edge = RailSegment(
                        source=source,
                        target=target,
                        edge_type="main",
                        distance_km=distance_km,
                        travel_time_min=distance_km / 1.2,  # ~72 km/h average
                        max_speed_kmh=120,
                        capacity=3,
                        current_load=0,
                        direction="bidirectional",
                        min_headway_sec=180,
                        reroutable=True,
                        priority_access=[],
                        risk_profile=RiskProfile.LOW,
                        historical_incidents=0
                    )
                    self.state_tracker.state.edges[edge_key] = edge
    
    def tick(self) -> SimulationState:
        """
        Advance simulation by one tick.
        
        Returns:
            SimulationState with current trains, predictions, and detections
        """
        self.tick_number += 1
        self.simulation_time += timedelta(seconds=self.tick_interval_sec)
        self.state_tracker.state.current_time = self.simulation_time
        
        # 0. Generate conflict scenarios periodically to demonstrate detection
        self._generate_conflict_scenarios()
        
        # 1. Update train positions
        self._update_trains()
        
        # 2. Sync detection state
        self._sync_detection_state()
        
        # 3. Run detection (every tick)
        new_detections = self._run_detection()
        
        # 3.1. Auto-save detected conflicts for resolution agent
        if new_detections:
            self._save_detected_conflicts(new_detections)
        
        # 3.2. CONFLICT PERSISTENCE with DEDUPLICATION
        # Create unique key based on conflict content (not ID)
        for detection in new_detections:
            # Unique key: type + location + sorted trains
            unique_key = f"{detection.conflict_type}_{detection.location}_{'_'.join(sorted(detection.involved_trains))}"
            
            # Update or add conflict with this unique key
            self.active_detections[unique_key] = detection
            self.detection_ttl[unique_key] = self.CONFLICT_PERSISTENCE_TICKS
        
        # 3.3. Decrement TTL and remove expired conflicts
        expired_keys = []
        for unique_key in self.detection_ttl:
            self.detection_ttl[unique_key] -= 1
            if self.detection_ttl[unique_key] <= 0:
                expired_keys.append(unique_key)
        for unique_key in expired_keys:
            del self.active_detections[unique_key]
            del self.detection_ttl[unique_key]
        
        # Get all active detections (persistent and deduplicated)
        all_detections = list(self.active_detections.values())
        
        # 4. Run prediction (EVERY tick for continuous mode)
        self.last_predictions = self._run_prediction()
        
        # 5. Build state object
        return SimulationState(
            simulation_time=self.simulation_time,
            tick_number=self.tick_number,
            trains=list(self.trains.values()),
            predictions=self.last_predictions,
            detections=all_detections,  # Use persistent detections
            statistics=self._get_statistics()
        )
    
    def _generate_conflict_scenarios(self) -> None:
        """
        Generate conflict scenarios to demonstrate the detection system.
        Creates realistic situations like:
        - Multiple trains at same station (platform overflow)
        - Trains on same edge (headway violation) - CAPACITY OVERFLOW
        - High delays cascading through network
        """
        # Every 5 ticks, create a conflict scenario (more frequent for demo)
        if self.tick_number % 5 == 0:
            train_list = list(self.trains.values())
            if len(train_list) >= 2:
                # Scenario 1: Add significant delays to several trains (300-900 sec = 5-15 min)
                num_delayed = min(5, len(train_list))  # Delay up to 5 trains
                delayed_trains = random.sample(train_list, num_delayed)
                for delayed_train in delayed_trains:
                    delayed_train.delay_sec = random.randint(300, 900)  # 5-15 min delay
                    delayed_train.status = "delayed"
                
                # Scenario 2: Put 4+ trains on same edge to EXCEED CAPACITY (capacity=3)
                # This will trigger EDGE_CAPACITY_OVERFLOW detection
                en_route_trains = [t for t in train_list if t.current_edge]
                if len(en_route_trains) >= 4:
                    # Move 4 trains to same edge - exceeds capacity of 3
                    target_edge = en_route_trains[0].current_edge
                    for i, train in enumerate(en_route_trains[1:4]):  # Move 3 more trains
                        train.current_edge = target_edge
                        train.status = "en_route"
                        train.position_km = en_route_trains[0].position_km + (i + 1) * 0.5
        
        # Every 8 ticks, create platform congestion
        if self.tick_number % 8 == 0:
            # Find a hub station
            hub_stations = [s for s in self.stations.values() if s.get('platforms', 1) >= 6]
            if hub_stations:
                hub = random.choice(hub_stations)
                hub_name = hub.get('name', hub.get('id', 'UNKNOWN'))
                # Move 4-5 trains to this station with delays
                trains_to_move = random.sample(list(self.trains.values()), min(5, len(self.trains)))
                for train in trains_to_move[:4]:
                    train.current_station = hub_name
                    train.status = "at_station"
                    train.current_edge = None  # Clear edge when at station
                    train.lat = hub.get('lat', 45.4)
                    train.lon = hub.get('lon', 9.2)
                    train.delay_sec = random.randint(120, 480)  # 2-8 min delay at station
    
    def _update_trains(self) -> None:
        """Update train positions and states."""
        for train_id, train in self.trains.items():
            if train.status == "at_station":
                # Check if it's time to depart
                if train.scheduled_departure and self.simulation_time >= train.scheduled_departure:
                    self._depart_train(train)
            
            elif train.status == "en_route":
                # Move train along route
                self._move_train(train)
            
            # Randomly introduce delays
            if random.random() < 0.02:  # 2% chance per tick
                delay_increase = random.randint(30, 180)
                train.delay_sec += delay_increase
                train.status = "delayed" if train.delay_sec > 120 else train.status
    
    def _depart_train(self, train: TrainPosition) -> None:
        """Handle train departure from station."""
        if train.current_stop_index >= len(train.route) - 1:
            # End of route, restart
            train.current_stop_index = 0
            first_stop = train.route[0]
            train.current_station = first_stop.get('station_name', 'UNKNOWN')
            train.lat = first_stop.get('lat', 45.4)
            train.lon = first_stop.get('lon', 9.2)
            train.scheduled_departure = self.simulation_time + timedelta(minutes=random.randint(10, 30))
            return
        
        # Move to next segment
        train.status = "en_route"
        current_stop = train.route[train.current_stop_index]
        next_stop = train.route[train.current_stop_index + 1]
        train.current_station = None
        train.next_station = next_stop.get('station_name', 'UNKNOWN')
        train.current_edge = f"{current_stop.get('station_name', 'UNKNOWN')}--{train.next_station}"
        train.speed_kmh = 80 if train.train_type == "regional" else 120
        train.position_km = 0
    
    def _move_train(self, train: TrainPosition) -> None:
        """Move train along current edge."""
        distance_per_tick = (train.speed_kmh / 3600) * self.tick_interval_sec
        train.position_km += distance_per_tick
        
        # Get edge distance (default 30km if missing or zero)
        edge_distance = train.route[train.current_stop_index + 1].get('distance_from_previous_km', 30)
        if not edge_distance or edge_distance <= 0:
            edge_distance = 30  # Default 30km between stations
        
        # Interpolate position
        progress = min(1.0, train.position_km / edge_distance)
        start = train.route[train.current_stop_index]
        end = train.route[train.current_stop_index + 1]
        train.lat = start['lat'] + (end['lat'] - start['lat']) * progress
        train.lon = start['lon'] + (end['lon'] - start['lon']) * progress
        
        # Check if arrived
        if train.position_km >= edge_distance:
            self._arrive_train(train)
    
    def _arrive_train(self, train: TrainPosition) -> None:
        """Handle train arrival at station."""
        train.current_stop_index += 1
        
        # Safety check - ensure we don't go out of bounds
        if train.current_stop_index >= len(train.route):
            train.current_stop_index = 0  # Loop back to start
            
        current_stop = train.route[train.current_stop_index]
        train.current_station = current_stop.get('station_name', 'UNKNOWN')
        
        # Get next station if available
        if train.current_stop_index < len(train.route) - 1:
            train.next_station = train.route[train.current_stop_index + 1].get('station_name')
        else:
            train.next_station = None
            
        train.current_edge = None
        train.status = "at_station"
        train.speed_kmh = 0
        train.position_km = 0
        train.lat = current_stop.get('lat', 45.4)
        train.lon = current_stop.get('lon', 9.2)
        
        # Schedule next departure
        dwell_time = 120 if train.train_type == "regional" else 180
        train.scheduled_departure = self.simulation_time + timedelta(seconds=dwell_time + train.delay_sec)
    
    def _sync_detection_state(self) -> None:
        """Sync train positions to detection state."""
        # Clear old train positions
        for station in self.state_tracker.state.stations.values():
            station.current_trains.clear()
        for edge in self.state_tracker.state.edges.values():
            edge.trains_on_segment.clear()
            edge.current_load = 0
        
        # Add current positions
        for train_id, train in self.trains.items():
            if train.current_station:
                station = self.state_tracker.state.stations.get(train.current_station)
                if station:
                    station.current_trains.append(train_id)
            
            if train.current_edge:
                edge = self.state_tracker.state.edges.get(train.current_edge)
                if edge:
                    edge.trains_on_segment.append(train_id)
                    edge.current_load += 1
    
    def _run_detection(self) -> List[UnifiedConflict]:
        """Run deterministic detection rules."""
        if not self.detection_engine:
            return []
        
        # Evaluate all rules
        conflicts = self.detection_engine.evaluate_all_rules()
        
        # Convert to unified format
        unified = []
        for conflict in conflicts:
            location = conflict.node_id or conflict.edge_id or "network"
            location_type = "station" if conflict.node_id else "edge" if conflict.edge_id else "network"
            
            # Get coordinates
            lat, lon = None, None
            if conflict.node_id and conflict.node_id in self.stations:
                lat = self.stations[conflict.node_id].get('lat')
                lon = self.stations[conflict.node_id].get('lon')
            
            # DETECTION: Show detailed conflict information with resolution
            conflict_type_labels = {
                "edge_capacity_overflow": "🚨 EDGE OVERLOAD",
                "headway_violation": "🚨 HEADWAY VIOLATION",
                "platform_overflow": "🚨 PLATFORM OVERFLOW",
                "scheduling_conflict": "🚨 SCHEDULING CONFLICT",
            }
            type_label = conflict_type_labels.get(conflict.conflict_type.value, "🚨 CONFLICT DETECTED")
            trains_info = f"Trains involved: {', '.join(conflict.involved_trains[:3])}"
            if len(conflict.involved_trains) > 3:
                trains_info += f" (+{len(conflict.involved_trains)-3} more)"
            
            unified.append(UnifiedConflict(
                conflict_id=conflict.conflict_id,
                source="detection",
                conflict_type=conflict.conflict_type.value,
                severity=conflict.severity.value,
                probability=1.0,  # Detected = 100% certainty
                location=location,
                location_type=location_type,
                involved_trains=conflict.involved_trains,
                explanation=f"{type_label} at {location} | {trains_info} | {conflict.explanation}",
                timestamp=conflict.timestamp,
                resolution_suggestions=self._generate_resolutions(conflict),
                lat=lat,
                lon=lon,
                model_used="detection"
            ))
        
        return unified
    
    def _save_detected_conflicts(self, detections: List[UnifiedConflict]) -> None:
        """
        Auto-save detected conflicts to a single JSON file for resolution agent.
        
        All conflicts are appended to 'detected_conflicts.json' with:
        - Conflict details (type, location, severity)
        - Affected trains with full state
        - Network context (stations, edges involved)
        - Timestamp and tick number
        
        Args:
            detections: List of detected conflicts
        """
        if not detections:
            return
        
        # Build output directory path (in integration folder)
        output_dir = Path(__file__).parent / "detected_conflicts"
        output_dir.mkdir(exist_ok=True)
        
        # Single file for all conflicts
        filepath = output_dir / "detected_conflicts.json"
        
        # Load existing conflicts if file exists
        existing_conflicts = []
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    existing_conflicts = data.get('conflicts', [])
            except (json.JSONDecodeError, KeyError):
                existing_conflicts = []
        
        # Process each detection
        new_conflicts = []
        for detection in detections:
            # Get affected trains
            affected_trains = []
            for train_id in detection.involved_trains:
                if train_id in self.trains:
                    train = self.trains[train_id]
                    affected_trains.append({
                        "train_id": train.train_id,
                        "train_type": train.train_type,
                        "current_station": train.current_station,
                        "next_station": train.next_station,
                        "current_edge": train.current_edge,
                        "position_km": train.position_km,
                        "speed_kmh": train.speed_kmh,
                        "delay_sec": train.delay_sec,
                        "status": train.status,
                        "lat": train.lat,
                        "lon": train.lon,
                        "route": train.route,
                        "current_stop_index": train.current_stop_index
                    })
            
            # Get network context (stations/edges involved)
            network_context = {}
            if detection.location_type == "station" and detection.location in self.stations:
                station = self.stations[detection.location]
                network_context = {
                    "type": "station",
                    "name": station.get('name', detection.location),
                    "id": detection.location,
                    "lat": station.get('lat'),
                    "lon": station.get('lon'),
                    "platforms": station.get('platforms', 3),
                    "connections": station.get('connections', [])
                }
            elif detection.location_type == "edge":
                # Find edge info from network data
                for edge in self.network_data.get('edges', []):
                    edge_id = f"{edge['from']}-{edge['to']}"
                    if edge_id == detection.location:
                        network_context = {
                            "type": "edge",
                            "id": detection.location,
                            "from": edge['from'],
                            "to": edge['to'],
                            "distance_km": edge.get('distance_km', 0),
                            "capacity": edge.get('capacity', 3),
                            "max_speed_kmh": edge.get('max_speed_kmh', 120)
                        }
                        break
            
            # Build conflict entry
            conflict_entry = {
                "metadata": {
                    "conflict_id": detection.conflict_id,
                    "timestamp": detection.timestamp.isoformat(),
                    "tick_number": self.tick_number,
                    "simulation_time": self.simulation_time.isoformat()
                },
                "conflict": {
                    "type": detection.conflict_type,
                    "severity": detection.severity,
                    "probability": detection.probability,
                    "location": detection.location,
                    "location_type": detection.location_type,
                    "explanation": detection.explanation,
                    "resolution_suggestions": detection.resolution_suggestions
                },
                "affected_trains": affected_trains,
                "network_context": network_context,
                "status": "unresolved"
            }
            
            new_conflicts.append(conflict_entry)
            print(f"  [CONFLICT SAVED] Tick {self.tick_number} | {detection.conflict_type} at {detection.location} | {len(affected_trains)} trains")
        
        # Combine existing and new conflicts
        all_conflicts = existing_conflicts + new_conflicts
        
        # Save to single file with metadata
        output_data = {
            "file_info": {
                "description": "All detected conflicts from simulation",
                "last_updated": datetime.now().isoformat(),
                "total_conflicts": len(all_conflicts),
                "unresolved_count": len([c for c in all_conflicts if c.get('status') == 'unresolved']),
                "resolved_count": len([c for c in all_conflicts if c.get('status') == 'resolved'])
            },
            "conflicts": all_conflicts
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"  [FILE UPDATED] detected_conflicts.json | Total: {len(all_conflicts)} conflicts ({len(new_conflicts)} new)")
    
    def _run_prediction(self) -> List[UnifiedConflict]:
        """Run ML + heuristics prediction for all trains (CONTINUOUS mode)."""
        predictions = []
        debug_count = 0
        
        for train_id, train in self.trains.items():
            # Skip if no next station
            if not train.next_station and not train.current_station:
                continue
            
            # Create TrainState for prediction
            train_state = TrainState(
                train_id=train.train_id,
                train_type=train.train_type,
                current_station=train.current_station or train.route[train.current_stop_index]['station_name'],
                next_station=train.next_station or (train.route[train.current_stop_index + 1]['station_name'] if train.current_stop_index < len(train.route) - 1 else None),
                current_delay_sec=train.delay_sec,
                position_km=train.position_km,
                speed_kmh=train.speed_kmh,
                route=train.route,
                current_stop_index=train.current_stop_index,
                scheduled_time=self.simulation_time,
                actual_time=self.simulation_time + timedelta(seconds=train.delay_sec)
            )
            
            # Create NetworkState for prediction
            pred_network = PredictionNetworkState(
                simulation_time=self.simulation_time,
                trains={train.train_id: train_state},
                stations={},
                active_conflicts=[c.to_dict() for c in self.last_predictions if c.source == "detection"]
            )
            
            # Predict for 10 minute horizon only to reduce output
            horizon_min = 10
            try:
                result = self.predictor.predict(train_state, pred_network, horizon_minutes=horizon_min)
                
                # Debug: print first few predictions on tick 5 and 10
                if self.tick_number in [5, 10] and debug_count < 3:
                    print(f"  [DEBUG] Train {train_id}: delay={train.delay_sec}s, prob={result.probability:.3f}, model={result.model_used}")
                    debug_count += 1
                
                # Include predictions with any risk (lowered threshold to 0.1 to show more predictions)
                if result.probability >= 0.1:
                    station = self.stations.get(train.current_station or train.next_station, {})
                    
                    # PREDICTION: Show as "Potential Conflict" with probability
                    risk_label = "⚠️ POTENTIAL CONFLICT" if result.probability >= 0.5 else "📊 Risk Assessment"
                    factors_text = ', '.join(result.contributing_factors[:2]) if result.contributing_factors else "monitoring"
                    
                    predictions.append(UnifiedConflict(
                        conflict_id=f"PRED_{train_id}_{horizon_min}_{self.tick_number}",
                        source="prediction",
                        conflict_type=result.predicted_conflict_type or "delay_risk",
                        severity=self._prob_to_severity(result.probability),
                        probability=result.probability,
                        location=train.current_station or train.next_station or "en_route",
                        location_type="station" if train.current_station else "edge",
                        involved_trains=[train_id],
                        explanation=f"{risk_label} ({int(result.probability*100)}% risk in {horizon_min}min) | {factors_text}",
                        timestamp=self.simulation_time,
                        prediction_horizon_min=horizon_min,
                        resolution_suggestions=result.contributing_factors,
                        lat=station.get('lat'),
                        lon=station.get('lon'),
                        model_used=result.model_used
                    ))
            except Exception as e:
                # Log ALL failed predictions for debugging
                print(f"[ERROR] Prediction failed for {train_id}: {type(e).__name__}: {e}")
        
        return predictions
    
    def _prob_to_severity(self, prob: float) -> str:
        """Convert probability to severity level."""
        if prob >= 0.8:
            return "critical"
        elif prob >= 0.6:
            return "high"
        elif prob >= 0.4:
            return "medium"
        else:
            return "low"
    
    def _generate_resolutions(self, conflict: DetectedConflict) -> List[str]:
        """Generate resolution suggestions for a detected conflict."""
        resolutions = []
        
        if conflict.conflict_type == ConflictType.EDGE_CAPACITY_OVERFLOW:
            resolutions = [
                "Hold trains at previous station",
                "Reroute via alternative track",
                "Reduce speed to create spacing"
            ]
        elif conflict.conflict_type == ConflictType.HEADWAY_VIOLATION:
            resolutions = [
                "Increase speed of leading train",
                "Reduce speed of following train",
                "Hold following train at platform"
            ]
        elif conflict.conflict_type == ConflictType.PLATFORM_OVERFLOW:
            resolutions = [
                "Divert to alternate platform",
                "Hold incoming trains",
                "Expedite departures"
            ]
        else:
            resolutions = [
                "Review and assess situation",
                "Contact control center",
                "Implement contingency plan"
            ]
        
        return resolutions
    
    def _get_statistics(self) -> Dict:
        """Get current simulation statistics."""
        trains_at_station = sum(1 for t in self.trains.values() if t.status == "at_station")
        trains_en_route = sum(1 for t in self.trains.values() if t.status == "en_route")
        trains_delayed = sum(1 for t in self.trains.values() if t.delay_sec > 120)
        
        return {
            "tick_number": self.tick_number,
            "simulation_time": self.simulation_time.isoformat(),
            "trains_total": len(self.trains),
            "trains_at_station": trains_at_station,
            "trains_en_route": trains_en_route,
            "trains_delayed": trains_delayed,
            "active_predictions": len(self.last_predictions),
            "detection_emitter_stats": self.detection_emitter.get_statistics()
        }
    
    def get_predictions_for_region(self, region: str) -> List[UnifiedConflict]:
        """Get predictions for a specific region."""
        region_stations = [
            s['id'] for s in self.network_data.get('stations', [])
            if s.get('region', '').upper() == region.upper()
        ]
        
        return [
            p for p in self.last_predictions
            if p.location in region_stations
        ]
    
    def get_predictions_for_station(self, station_id: str) -> List[UnifiedConflict]:
        """Get predictions for a specific station."""
        return [
            p for p in self.last_predictions
            if p.location == station_id or p.location == self.stations.get(station_id, {}).get('name')
        ]


# Demo usage
if __name__ == "__main__":
    print("\n" + "="*60)
    print("INTEGRATION ENGINE DEMO")
    print("="*60)
    
    engine = IntegrationEngine()
    engine.initialize()
    
    print("\n[Running 10 simulation ticks...]")
    for i in range(10):
        state = engine.tick()
        print(f"\nTick {state.tick_number}: {state.simulation_time.strftime('%H:%M')}")
        print(f"  Trains: {state.statistics['trains_total']} total, {state.statistics['trains_en_route']} en route, {state.statistics['trains_delayed']} delayed")
        print(f"  Predictions: {len(state.predictions)}, Detections: {len(state.detections)}")
        
        if state.predictions:
            print("  Top predictions:")
            for p in state.predictions[:3]:
                print(f"    - {p.conflict_type} @ {p.location}: {p.probability*100:.0f}% ({p.prediction_horizon_min} min)")
        
        if state.detections:
            print("  Active detections:")
            for d in state.detections:
                print(f"    - [{d.severity.upper()}] {d.conflict_type} @ {d.location}")
