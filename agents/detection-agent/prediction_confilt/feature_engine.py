"""
Feature Engineering Pipeline
============================

Computes features for conflict prediction from simulation state.
Includes train, station, network, and temporal features with 
graph-aware computations for capturing network topology effects.
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    from .config import (
        TRAIN_FEATURES, STATION_FEATURES, NETWORK_FEATURES,
        TEMPORAL_FEATURES, INTERACTION_FEATURES, NETWORK_GRAPH
    )
except ImportError:
    from config import (
        TRAIN_FEATURES, STATION_FEATURES, NETWORK_FEATURES,
        TEMPORAL_FEATURES, INTERACTION_FEATURES, NETWORK_GRAPH
    )


@dataclass
class TrainState:
    """Current state of a train in simulation."""
    train_id: str
    train_type: str
    current_station: str
    next_station: Optional[str]
    current_delay_sec: float
    position_km: float
    speed_kmh: float
    route: List[Dict]
    current_stop_index: int
    scheduled_time: datetime
    actual_time: datetime
    
    
@dataclass
class StationState:
    """Current state of a station in simulation."""
    station_id: str
    name: str
    current_trains: List[str]
    platform_occupancy: Dict[int, Optional[str]]
    expected_arrivals: List[Tuple[str, datetime]]
    expected_departures: List[Tuple[str, datetime]]


@dataclass
class NetworkState:
    """Current state of the rail network."""
    simulation_time: datetime
    trains: Dict[str, TrainState]
    stations: Dict[str, StationState]
    active_conflicts: List[Dict]
    

class FeatureEngine:
    """
    Feature engineering pipeline for conflict prediction.
    
    Computes features from current simulation state including:
    - Train-level features (delay, speed, position, priority)
    - Station-level features (occupancy, congestion)
    - Network-level features (segment utilization, cascading effects)
    - Temporal features (hour, peak times, weekday/weekend)
    - Interaction features (combined effects)
    """
    
    def __init__(self, network_graph_path: Optional[Path] = None):
        """
        Initialize feature engine with network graph.
        
        Args:
            network_graph_path: Path to the rail network graph JSON
        """
        self.network_graph_path = network_graph_path or NETWORK_GRAPH
        self.graph = self._load_network_graph()
        self.station_properties = self._extract_station_properties()
        self.adjacency = self._build_adjacency_matrix()
        
        # Train type encoding
        self.train_type_map = {
            "high_speed": 4,
            "intercity": 3, 
            "regional_express": 2,
            "regional": 1,
            "suburban": 0
        }
        
        # Peak hour definitions for Italy
        self.morning_peak = (7, 9)  # 7:00 - 9:00
        self.evening_peak = (17, 19)  # 17:00 - 19:00
        
        # Italian holidays 2026 (example)
        self.holidays = {
            datetime(2026, 1, 1),   # New Year
            datetime(2026, 1, 6),   # Epiphany
            datetime(2026, 4, 5),   # Easter Sunday
            datetime(2026, 4, 6),   # Easter Monday
            datetime(2026, 4, 25),  # Liberation Day
            datetime(2026, 5, 1),   # Labour Day
            datetime(2026, 6, 2),   # Republic Day
            datetime(2026, 8, 15),  # Ferragosto
            datetime(2026, 11, 1),  # All Saints
            datetime(2026, 12, 8),  # Immaculate Conception
            datetime(2026, 12, 25), # Christmas
            datetime(2026, 12, 26), # St. Stephen
        }
        
    def _load_network_graph(self) -> Dict:
        """Load the rail network graph from JSON."""
        try:
            with open(self.network_graph_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Network graph not found at {self.network_graph_path}")
            return {"nodes": [], "edges": []}
            
    def _extract_station_properties(self) -> Dict[str, Dict]:
        """Extract station properties from network graph."""
        properties = {}
        for node in self.graph.get("nodes", []):
            properties[node["id"]] = {
                "name": node.get("name", node["id"]),
                "lat": node.get("lat", 0),
                "lon": node.get("lon", 0),
                "region": node.get("region", "Unknown"),
                "platforms": node.get("platforms", 2),
                "max_trains_at_once": node.get("max_trains_at_once", 2),
                "is_hub": node.get("is_hub", "False") == "True",
                "is_major_hub": node.get("is_major_hub", False),
                "historical_congestion_level": node.get("historical_congestion_level", "low"),
                "avg_delay_sec": node.get("avg_delay_sec", 60),
                "degree": node.get("degree", 2)
            }
        return properties
        
    def _build_adjacency_matrix(self) -> Dict[str, List[str]]:
        """Build adjacency list from network edges."""
        adjacency = {}
        for edge in self.graph.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                if source not in adjacency:
                    adjacency[source] = []
                if target not in adjacency:
                    adjacency[target] = []
                adjacency[source].append(target)
                adjacency[target].append(source)
        return adjacency
    
    def compute_features(
        self,
        train: TrainState,
        network_state: NetworkState,
        prediction_horizon_min: int = 15
    ) -> Dict[str, float]:
        """
        Compute all features for a single train at current simulation time.
        
        Args:
            train: Current state of the train
            network_state: Current state of the entire network
            prediction_horizon_min: How far ahead to predict (minutes)
            
        Returns:
            Dictionary of feature names to values
        """
        features = {}
        
        # Train features
        features.update(self._compute_train_features(train, network_state))
        
        # Station features (for next station)
        features.update(self._compute_station_features(train, network_state))
        
        # Network features (graph-aware)
        features.update(self._compute_network_features(train, network_state))
        
        # Temporal features
        features.update(self._compute_temporal_features(network_state.simulation_time))
        
        # Interaction features
        features.update(self._compute_interaction_features(features))
        
        return features
    
    def _compute_train_features(
        self,
        train: TrainState,
        network_state: NetworkState
    ) -> Dict[str, float]:
        """Compute train-level features."""
        features = {}
        
        # Current delay
        features["current_delay_sec"] = train.current_delay_sec
        
        # Delay rate (delay accumulated per km traveled)
        if train.position_km > 0:
            features["delay_rate_per_km"] = train.current_delay_sec / train.position_km
        else:
            features["delay_rate_per_km"] = 0.0
            
        # Distance and time to next station
        if train.next_station and train.current_stop_index < len(train.route) - 1:
            next_stop = train.route[train.current_stop_index + 1]
            features["distance_to_next_station_km"] = next_stop.get("distance_from_previous_km", 0)
            
            # Estimated time to next station based on current speed
            if train.speed_kmh > 0:
                features["time_to_next_station_sec"] = (
                    features["distance_to_next_station_km"] / train.speed_kmh * 3600
                )
            else:
                # Use a large but finite value instead of infinity (1 hour max)
                features["time_to_next_station_sec"] = 3600.0
        else:
            features["distance_to_next_station_km"] = 0.0
            features["time_to_next_station_sec"] = 0.0
            
        # Train type encoded
        features["train_type_encoded"] = self.train_type_map.get(train.train_type, 1)
        
        # Priority level (based on train type)
        features["priority_level"] = features["train_type_encoded"]
        
        # Remaining stops
        features["remaining_stops"] = len(train.route) - train.current_stop_index - 1
        
        return features
    
    def _compute_station_features(
        self,
        train: TrainState,
        network_state: NetworkState
    ) -> Dict[str, float]:
        """Compute station-level features for the next station."""
        features = {}
        
        next_station = train.next_station
        if not next_station:
            # Return defaults if no next station
            return {
                "current_occupancy": 0.0,
                "platform_utilization": 0.0,
                "expected_arrivals_15min": 0,
                "expected_departures_15min": 0,
                "is_hub": 0,
                "is_major_hub": 0,
                "historical_congestion_level": 0,
                "avg_delay_sec": 60,
            }
        
        # Get station properties
        station_props = self.station_properties.get(next_station, {})
        
        # Get station state if available
        station_state = network_state.stations.get(next_station)
        
        if station_state:
            # Current occupancy (trains at station / max capacity)
            max_trains = station_props.get("max_trains_at_once", 2)
            features["current_occupancy"] = len(station_state.current_trains) / max(max_trains, 1)
            
            # Platform utilization
            total_platforms = station_props.get("platforms", 2)
            occupied_platforms = sum(1 for p in station_state.platform_occupancy.values() if p is not None)
            features["platform_utilization"] = occupied_platforms / max(total_platforms, 1)
            
            # Expected arrivals/departures in next 15 minutes
            sim_time = network_state.simulation_time
            horizon = sim_time + timedelta(minutes=15)
            
            features["expected_arrivals_15min"] = sum(
                1 for _, t in station_state.expected_arrivals if t <= horizon
            )
            features["expected_departures_15min"] = sum(
                1 for _, t in station_state.expected_departures if t <= horizon
            )
        else:
            features["current_occupancy"] = 0.0
            features["platform_utilization"] = 0.0
            features["expected_arrivals_15min"] = 0
            features["expected_departures_15min"] = 0
        
        # Static station properties
        features["is_hub"] = 1 if station_props.get("is_hub", False) else 0
        features["is_major_hub"] = 1 if station_props.get("is_major_hub", False) else 0
        
        # Historical congestion level (encoded)
        congestion_map = {"low": 0, "medium": 1, "high": 2}
        features["historical_congestion_level"] = congestion_map.get(
            station_props.get("historical_congestion_level", "low"), 0
        )
        
        features["avg_delay_sec"] = station_props.get("avg_delay_sec", 60)
        
        return features
    
    def _compute_network_features(
        self,
        train: TrainState,
        network_state: NetworkState
    ) -> Dict[str, float]:
        """
        Compute network-level features using graph topology.
        
        This is where we capture spatial dependencies without a full GNN:
        - Aggregate information from neighboring stations
        - Track segment utilization
        - Cascading congestion effects
        """
        features = {}
        
        current_station = train.current_station
        next_station = train.next_station
        
        # Segment utilization (trains on same segment)
        segment_trains = 0
        for other_id, other_train in network_state.trains.items():
            if other_id == train.train_id:
                continue
            # Check if on same segment (between same two stations)
            if (other_train.current_station == current_station and 
                other_train.next_station == next_station):
                segment_trains += 1
            elif (other_train.current_station == next_station and 
                  other_train.next_station == current_station):
                segment_trains += 1
        features["segment_utilization"] = min(segment_trains, 5) / 5.0  # Normalize
        
        # Upstream congestion (stations before current in network)
        upstream_congestion = 0.0
        upstream_stations = self.adjacency.get(current_station, [])
        for upstream in upstream_stations:
            station_state = network_state.stations.get(upstream)
            if station_state:
                props = self.station_properties.get(upstream, {})
                max_trains = props.get("max_trains_at_once", 2)
                upstream_congestion += len(station_state.current_trains) / max(max_trains, 1)
        if upstream_stations:
            features["upstream_congestion"] = upstream_congestion / len(upstream_stations)
        else:
            features["upstream_congestion"] = 0.0
            
        # Downstream congestion (stations after next in network)
        downstream_congestion = 0.0
        if next_station:
            downstream_stations = self.adjacency.get(next_station, [])
            for downstream in downstream_stations:
                if downstream == current_station:
                    continue  # Skip where we came from
                station_state = network_state.stations.get(downstream)
                if station_state:
                    props = self.station_properties.get(downstream, {})
                    max_trains = props.get("max_trains_at_once", 2)
                    downstream_congestion += len(station_state.current_trains) / max(max_trains, 1)
            if len(downstream_stations) > 1:
                features["downstream_congestion"] = downstream_congestion / (len(downstream_stations) - 1)
            else:
                features["downstream_congestion"] = 0.0
        else:
            features["downstream_congestion"] = 0.0
        
        # Competing trains (trains heading to same next station)
        competing_trains = 0
        for other_id, other_train in network_state.trains.items():
            if other_id == train.train_id:
                continue
            if other_train.next_station == next_station:
                competing_trains += 1
        features["competing_trains_count"] = competing_trains
        
        # Network load factor (overall network congestion)
        total_trains = len(network_state.trains)
        total_capacity = sum(
            p.get("max_trains_at_once", 2) 
            for p in self.station_properties.values()
        )
        features["network_load_factor"] = total_trains / max(total_capacity, 1)
        
        return features
    
    def _compute_temporal_features(self, sim_time: datetime) -> Dict[str, float]:
        """Compute temporal features from simulation time."""
        features = {}
        
        features["hour_of_day"] = sim_time.hour
        features["day_of_week"] = sim_time.weekday()  # 0=Monday, 6=Sunday
        
        # Peak hour indicator
        is_morning_peak = self.morning_peak[0] <= sim_time.hour < self.morning_peak[1]
        is_evening_peak = self.evening_peak[0] <= sim_time.hour < self.evening_peak[1]
        features["is_peak_hour"] = 1 if (is_morning_peak or is_evening_peak) else 0
        
        # Weekend indicator
        features["is_weekend"] = 1 if sim_time.weekday() >= 5 else 0
        
        # Holiday indicator
        date_only = datetime(sim_time.year, sim_time.month, sim_time.day)
        features["is_holiday"] = 1 if date_only in self.holidays else 0
        
        return features
    
    def _compute_interaction_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """Compute interaction features from base features."""
        interaction_features = {}
        
        # Delay * Congestion interaction
        interaction_features["delay_congestion_interaction"] = (
            features.get("current_delay_sec", 0) / 300 *  # Normalize delay to ~minutes
            features.get("current_occupancy", 0)
        )
        
        # Hub * Peak hour interaction
        interaction_features["hub_peak_interaction"] = (
            features.get("is_hub", 0) * features.get("is_peak_hour", 0)
        )
        
        # Train priority * Station type interaction
        interaction_features["train_priority_station_type_interaction"] = (
            features.get("priority_level", 1) * features.get("is_major_hub", 0)
        )
        
        return interaction_features
    
    def get_feature_names(self) -> List[str]:
        """Get ordered list of all feature names."""
        return (
            TRAIN_FEATURES + 
            STATION_FEATURES + 
            NETWORK_FEATURES + 
            TEMPORAL_FEATURES + 
            INTERACTION_FEATURES
        )
    
    def features_to_array(self, features: Dict[str, float]) -> np.ndarray:
        """Convert feature dictionary to numpy array in correct order."""
        feature_names = self.get_feature_names()
        return np.array([features.get(name, 0.0) for name in feature_names])
    
    def compute_batch_features(
        self,
        network_state: NetworkState,
        prediction_horizon_min: int = 15
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Compute features for all trains in the network.
        
        Args:
            network_state: Current state of the entire network
            prediction_horizon_min: How far ahead to predict
            
        Returns:
            Tuple of (feature matrix, list of train IDs)
        """
        all_features = []
        train_ids = []
        
        for train_id, train in network_state.trains.items():
            features = self.compute_features(train, network_state, prediction_horizon_min)
            all_features.append(self.features_to_array(features))
            train_ids.append(train_id)
            
        if all_features:
            return np.vstack(all_features), train_ids
        else:
            return np.array([]).reshape(0, len(self.get_feature_names())), []
