"""
Network State Tracker
Maintains real-time state of the railway network including:
- Station occupancy
- Edge loads
- Train positions
- Timing information
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from models import (
    Station, RailSegment, Train, TrainStatus, TrainType,
    BlockingBehavior, SignalControl, CongestionLevel, RiskProfile
)


@dataclass
class NetworkState:
    """
    Central state container for the railway network.
    Tracks all stations, edges, and trains in real-time.
    """
    
    # Core data structures
    stations: Dict[str, Station] = field(default_factory=dict)
    edges: Dict[str, RailSegment] = field(default_factory=dict)  # key: "SOURCE--TARGET"
    trains: Dict[str, Train] = field(default_factory=dict)
    
    # Adjacency for graph traversal
    adjacency: Dict[str, List[str]] = field(default_factory=dict)  # station -> [neighbor stations]
    
    # Time tracking
    current_time: datetime = field(default_factory=datetime.now)
    weather: str = "clear"  # "clear", "rain", "snow", "fog", "storm"
    
    # Event history (for headway calculations)
    edge_entry_history: Dict[str, List[Tuple[str, datetime, str]]] = field(default_factory=dict)
    # edge_id -> [(train_id, entry_time, direction)]
    
    station_arrival_history: Dict[str, List[Tuple[str, datetime]]] = field(default_factory=dict)
    # station_id -> [(train_id, arrival_time)]
    
    def get_edge_key(self, source: str, target: str) -> str:
        """Get normalized edge key (alphabetically ordered for undirected lookup)."""
        return f"{source}--{target}"
    
    def get_edge(self, source: str, target: str) -> Optional[RailSegment]:
        """Get edge by source/target, checking both directions."""
        key1 = f"{source}--{target}"
        key2 = f"{target}--{source}"
        return self.edges.get(key1) or self.edges.get(key2)
    
    def get_trains_at_station(self, station_id: str) -> List[Train]:
        """Get all trains currently at a station."""
        return [
            t for t in self.trains.values()
            if t.current_position_type == "station" and t.current_station == station_id
        ]
    
    def get_trains_on_edge(self, edge_id: str) -> List[Train]:
        """Get all trains currently on an edge."""
        return [
            t for t in self.trains.values()
            if t.current_position_type == "edge" and t.current_edge == edge_id
        ]
    
    def get_recent_edge_entries(
        self, edge_id: str, window_seconds: int = 600
    ) -> List[Tuple[str, datetime, str]]:
        """Get edge entries within time window."""
        cutoff = self.current_time - timedelta(seconds=window_seconds)
        entries = self.edge_entry_history.get(edge_id, [])
        return [(tid, t, d) for tid, t, d in entries if t >= cutoff]
    
    def get_recent_station_arrivals(
        self, station_id: str, window_seconds: int = 60
    ) -> List[Tuple[str, datetime]]:
        """Get station arrivals within time window."""
        cutoff = self.current_time - timedelta(seconds=window_seconds)
        arrivals = self.station_arrival_history.get(station_id, [])
        return [(tid, t) for tid, t in arrivals if t >= cutoff]


class StateTracker:
    """
    Manages the network state and processes updates.
    """
    
    def __init__(self):
        self.state = NetworkState()
    
    def load_from_json(self, data_or_path) -> None:
        """
        Load network data from lombardy_simulation_data.json.
        
        Args:
            data_or_path: Either a dict of data or a path to JSON file
        """
        if isinstance(data_or_path, dict):
            data = data_or_path
        else:
            with open(data_or_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        # Load stations
        for node in data.get("stations", []):
            station = self._parse_station(node)
            self.state.stations[station.id] = station
        
        # Load edges
        for edge in data.get("rails", []):
            segment = self._parse_edge(edge)
            self.state.edges[segment.edge_id] = segment
            
            # Build adjacency
            if segment.source not in self.state.adjacency:
                self.state.adjacency[segment.source] = []
            if segment.target not in self.state.adjacency:
                self.state.adjacency[segment.target] = []
            
            self.state.adjacency[segment.source].append(segment.target)
            self.state.adjacency[segment.target].append(segment.source)
        
        # Load trains
        for train_data in data.get("trains", []):
            train = self._parse_train(train_data)
            self.state.trains[train.train_id] = train
        
        print(f"[StateTracker] Loaded {len(self.state.stations)} stations, "
              f"{len(self.state.edges)} edges, {len(self.state.trains)} trains")
    
    def _parse_station(self, node: Dict) -> Station:
        """Parse station from JSON node."""
        return Station(
            id=node["id"],
            name=node.get("name", node["id"]),
            lat=node.get("lat", 0.0),
            lon=node.get("lon", 0.0),
            region=node.get("region", "Lombardy"),
            platforms=node.get("platforms", 2),
            max_trains_at_once=node.get("max_trains_at_once", 2),
            max_simultaneous_arrivals=node.get("max_simultaneous_arrivals", 1),
            min_dwell_time_sec=node.get("min_dwell_time_sec", 60),
            blocking_behavior=BlockingBehavior(node.get("blocking_behavior", "soft")),
            signal_control=SignalControl(node.get("signal_control", "local")),
            has_switchyard=node.get("has_switchyard", False),
            hold_allowed=node.get("hold_allowed", True),
            max_hold_time_sec=node.get("max_hold_time_sec", 300),
            priority_station=node.get("priority_station", False),
            priority_override_allowed=node.get("priority_override_allowed", False),
            historical_congestion_level=CongestionLevel(
                node.get("historical_congestion_level", "low")
            ),
            avg_delay_sec=node.get("avg_delay_sec", 0)
        )
    
    def _parse_edge(self, edge: Dict) -> RailSegment:
        """Parse edge from JSON."""
        return RailSegment(
            source=edge["source"],
            target=edge["target"],
            edge_type=edge.get("edge_type", "regional"),
            distance_km=edge.get("distance_km", 10.0),
            travel_time_min=edge.get("travel_time_min", 10.0),
            max_speed_kmh=edge.get("max_speed_kmh", 120),
            capacity=edge.get("capacity", 2),
            current_load=edge.get("current_load", 0),
            direction=edge.get("direction", "bidirectional"),
            min_headway_sec=edge.get("min_headway_sec", 180),
            reroutable=edge.get("reroutable", False),
            priority_access=edge.get("priority_access", ["passenger"]),
            risk_profile=RiskProfile(edge.get("risk_profile", "low")),
            historical_incidents=edge.get("historical_incidents", 0)
        )
    
    def _parse_train(self, train_data: Dict) -> Train:
        """Parse train from JSON."""
        train_type_str = train_data.get("train_type", "regional")
        train_type_map = {
            "regional": TrainType.REGIONAL,
            "intercity": TrainType.INTERCITY,
            "eurocity": TrainType.EUROCITY,
            "freight": TrainType.FREIGHT,
            "high_speed": TrainType.HIGH_SPEED,
        }
        
        train = Train(
            train_id=train_data["train_id"],
            train_type=train_type_map.get(train_type_str, TrainType.REGIONAL),
            route_id=train_data.get("route_id", 0),
            route=train_data.get("route", []),
            current_position_type="station",
            current_station=train_data["route"][0]["station_name"] if train_data.get("route") else None,
        )
        return train
    
    # =========================================================================
    # State Update Methods (called by simulator)
    # =========================================================================
    
    def update_time(self, new_time: datetime) -> None:
        """Advance simulation time."""
        self.state.current_time = new_time
    
    def update_weather(self, weather: str) -> None:
        """Update network weather conditions."""
        self.state.weather = weather
    
    def train_arrives_at_station(self, train_id: str, station_id: str) -> None:
        """Record train arrival at station."""
        train = self.state.trains.get(train_id)
        station = self.state.stations.get(station_id)
        
        if not train or not station:
            return
        
        # Update train state
        train.current_position_type = "station"
        train.current_station = station_id
        train.current_edge = None
        train.actual_arrival = self.state.current_time
        
        # Update station state
        if train_id not in station.current_trains:
            station.current_trains.append(train_id)
        if train_id in station.pending_arrivals:
            station.pending_arrivals.remove(train_id)
        
        # Record arrival history
        if station_id not in self.state.station_arrival_history:
            self.state.station_arrival_history[station_id] = []
        self.state.station_arrival_history[station_id].append(
            (train_id, self.state.current_time)
        )
    
    def train_departs_station(self, train_id: str, next_station_id: str) -> None:
        """Record train departure from station onto edge."""
        train = self.state.trains.get(train_id)
        if not train or not train.current_station:
            return
        
        current_station = self.state.stations.get(train.current_station)
        if current_station and train_id in current_station.current_trains:
            current_station.current_trains.remove(train_id)
        
        # Determine edge
        edge = self.state.get_edge(train.current_station, next_station_id)
        if edge:
            edge_id = edge.edge_id
            direction = f"{train.current_station}->{next_station_id}"
            
            # Update train
            train.current_position_type = "edge"
            train.current_edge = edge_id
            train.progress_on_edge = 0.0
            train.actual_departure = self.state.current_time
            
            # Update edge
            edge.current_load += 1
            if train_id not in edge.trains_on_segment:
                edge.trains_on_segment.append(train_id)
            edge.last_train_entry_time = self.state.current_time
            edge.last_train_direction = direction
            
            # Record entry history
            if edge_id not in self.state.edge_entry_history:
                self.state.edge_entry_history[edge_id] = []
            self.state.edge_entry_history[edge_id].append(
                (train_id, self.state.current_time, direction)
            )
        
        # Advance route index
        train.route_index += 1
        train.current_station = None
    
    def train_exits_edge(self, train_id: str) -> None:
        """Record train leaving an edge (before arriving at station)."""
        train = self.state.trains.get(train_id)
        if not train or not train.current_edge:
            return
        
        edge = self.state.edges.get(train.current_edge)
        if edge:
            edge.current_load = max(0, edge.current_load - 1)
            if train_id in edge.trains_on_segment:
                edge.trains_on_segment.remove(train_id)
    
    def update_train_position_on_edge(self, train_id: str, progress: float) -> None:
        """Update train's progress along edge (0.0 to 1.0)."""
        train = self.state.trains.get(train_id)
        if train:
            train.progress_on_edge = min(1.0, max(0.0, progress))
    
    def update_train_speed(self, train_id: str, speed_kmh: float) -> None:
        """Update train's current speed."""
        train = self.state.trains.get(train_id)
        if train:
            train.current_speed_kmh = speed_kmh
    
    def update_train_delay(self, train_id: str, delay_seconds: int) -> None:
        """Update train's delay."""
        train = self.state.trains.get(train_id)
        if train:
            train.delay_seconds = delay_seconds
            if delay_seconds > 60:
                train.status = TrainStatus.DELAYED
    
    def set_train_holding(self, train_id: str, holding: bool) -> None:
        """Set train holding status."""
        train = self.state.trains.get(train_id)
        if train:
            if holding:
                train.status = TrainStatus.HOLDING
                train.hold_start_time = self.state.current_time
            else:
                train.status = TrainStatus.ON_TIME
                train.hold_start_time = None
    
    def add_pending_arrival(self, station_id: str, train_id: str) -> None:
        """Mark train as pending arrival at station."""
        station = self.state.stations.get(station_id)
        if station and train_id not in station.pending_arrivals:
            station.pending_arrivals.append(train_id)
    
    def get_snapshot(self) -> Dict:
        """Get current state snapshot for debugging."""
        return {
            "time": self.state.current_time.isoformat(),
            "trains_at_stations": {
                sid: [t for t in s.current_trains]
                for sid, s in self.state.stations.items()
                if s.current_trains
            },
            "edge_loads": {
                eid: e.current_load
                for eid, e in self.state.edges.items()
                if e.current_load > 0
            },
            "train_positions": {
                tid: {
                    "type": t.current_position_type,
                    "location": t.current_station or t.current_edge,
                    "status": t.status.value,
                    "delay": t.delay_seconds
                }
                for tid, t in self.state.trains.items()
            }
        }
