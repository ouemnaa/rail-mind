"""
Mock Real-Time Simulator
Generates time-stepped network state updates for testing the detection engine.

This simulator:
- Does NOT pre-label conflicts (detection layer decides)
- Generates realistic train movements
- Introduces delays, congestion, and edge cases
- Produces configurable scenarios
"""

import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass
from enum import Enum

from state_tracker import StateTracker
from models import Train, TrainStatus, TrainType, Incident, IncidentType


class ScenarioType(Enum):
    """Types of simulation scenarios."""
    NORMAL = "normal"           # Regular operations
    RUSH_HOUR = "rush_hour"     # High traffic
    DISRUPTION = "disruption"   # Delays and incidents
    STRESS_TEST = "stress_test" # Maximum load


@dataclass
class SimulationConfig:
    """Configuration for the simulator."""
    tick_interval_seconds: int = 10
    max_ticks: int = 100
    scenario: ScenarioType = ScenarioType.NORMAL
    random_seed: Optional[int] = None
    
    # Probability settings (0.0 to 1.0)
    delay_probability: float = 0.1
    speed_variation: float = 0.2
    train_spawn_rate: float = 0.3
    
    # Limits
    max_active_trains: int = 50
    max_delay_seconds: int = 600


class MockSimulator:
    """
    Generates realistic railway network updates.
    Feeds the StateTracker with time-stepped data.
    """
    
    def __init__(self, state_tracker: StateTracker, config: Optional[SimulationConfig] = None):
        self.tracker = state_tracker
        self.config = config or SimulationConfig()
        
        if self.config.random_seed:
            random.seed(self.config.random_seed)
        
        self.current_time = datetime.now()
        self.tick_count = 0
        
        # Track active trains (trains currently in simulation)
        self.active_trains: List[str] = []
        self.completed_trains: List[str] = []
        
        # Scenario-specific adjustments
        self._apply_scenario_config()
        
        # New: Tracking active incidents
        self.active_incidents_registry: Dict[str, Incident] = {}
        self.incident_probability = 0.05
    
    def _apply_scenario_config(self) -> None:
        """Adjust config based on scenario type."""
        if self.config.scenario == ScenarioType.RUSH_HOUR:
            self.config.train_spawn_rate = 0.6
            self.config.delay_probability = 0.2
            self.config.max_active_trains = 80
            self.incident_probability = 0.08
        
        elif self.config.scenario == ScenarioType.DISRUPTION:
            self.config.delay_probability = 0.4
            self.config.max_delay_seconds = 1200
            self.incident_probability = 0.3
        
        elif self.config.scenario == ScenarioType.STRESS_TEST:
            self.config.train_spawn_rate = 0.8
            self.config.max_active_trains = 100
            self.config.delay_probability = 0.3
            self.incident_probability = 0.15
    
    def initialize_trains(self, count: int = 10) -> None:
        """Initialize some trains at their starting stations."""
        available_trains = list(self.tracker.state.trains.values())
        
        if not available_trains:
            print("[Simulator] No trains available in state")
            return
        
        # Select random subset
        selected = random.sample(available_trains, min(count, len(available_trains)))
        
        for train in selected:
            if train.route and len(train.route) > 0:
                start_station = train.route[0]["station_name"]
                
                # Position train at start
                train.current_position_type = "station"
                train.current_station = start_station
                train.route_index = 0
                train.status = TrainStatus.ON_TIME
                train.delay_seconds = 0
                
                # Update station state
                station = self.tracker.state.stations.get(start_station)
                if station and train.train_id not in station.current_trains:
                    station.current_trains.append(train.train_id)
                
                self.active_trains.append(train.train_id)
        
        print(f"[Simulator] Initialized {len(self.active_trains)} trains")
    
    def tick(self) -> Dict:
        """
        Advance simulation by one tick.
        Returns summary of changes made.
        """
        self.tick_count += 1
        self.current_time += timedelta(seconds=self.config.tick_interval_seconds)
        self.tracker.update_time(self.current_time)
        
        changes = {
            "tick": self.tick_count,
            "time": self.current_time.isoformat(),
            "departures": [],
            "arrivals": [],
            "delays_added": [],
            "speed_changes": [],
            "trains_spawned": [],
            "incidents_started": [],
            "incidents_resolved": [],
            "weather": self.tracker.state.weather,
        }
        
        # New: Randomly change weather
        self._update_weather(changes)
        
        # Process active incidents (cleanup expired)
        self._update_incidents(changes)
        
        # Maybe spawn new incident
        self._maybe_spawn_incident(changes)
        
        # Process each active train
        for train_id in list(self.active_trains):
            train = self.tracker.state.trains.get(train_id)
            if not train:
                continue
            
            if train.current_position_type == "station":
                # Maybe depart
                if self._should_train_depart(train):
                    next_station = train.next_station
                    if next_station:
                        # Check for blocking incident on edge
                        edge = self.tracker.state.get_edge(train.current_station, next_station)
                        if edge and any(inc.is_blocking for inc in edge.active_incidents):
                            # Cannot depart, edge blocked
                            continue
                            
                        self.tracker.train_departs_station(train_id, next_station)
                        changes["departures"].append({
                            "train": train_id,
                            "from": train.route[train.route_index - 1]["station_name"],
                            "to": next_station
                        })
            
            elif train.current_position_type == "edge":
                # Progress along edge
                self._progress_train_on_edge(train, changes)
        
        # Maybe introduce delays
        self._introduce_random_delays(changes)
        
        # Maybe spawn new trains
        self._maybe_spawn_trains(changes)
        
        return changes
    
    def _should_train_depart(self, train: Train) -> bool:
        """Decide if train should depart current station."""
        # Check if route has more stations
        if train.route_index >= len(train.route) - 1:
            return False
        
        # Random chance based on config
        base_chance = 0.3 + (self.config.train_spawn_rate * 0.3)
        
        # Higher priority trains depart more reliably
        priority_bonus = train.priority * 0.05
        
        return random.random() < (base_chance + priority_bonus)
    
    def _progress_train_on_edge(self, train: Train, changes: Dict) -> None:
        """Progress train along its current edge."""
        if not train.current_edge:
            return
        
        edge = self.tracker.state.edges.get(train.current_edge)
        if not edge:
            return
        
        # Check for blocking incident - train stops mid-edge
        if any(inc.is_blocking for inc in edge.active_incidents):
            if train.current_speed_kmh > 0:
                self.tracker.update_train_speed(train.train_id, 0)
                changes["speed_changes"].append({"train": train.train_id, "speed": 0})
            return

        # Calculate progress increment based on speed and travel time
        base_speed = edge.max_speed_kmh
        
        # Apply speed variation
        speed_factor = 1.0 + (random.random() - 0.5) * self.config.speed_variation * 2
        
        # Weather impact on speed
        if self.tracker.state.weather in ["snow", "storm", "fog"]:
            speed_factor *= 0.8
        elif self.tracker.state.weather == "rain":
            speed_factor *= 0.95

        actual_speed = base_speed * speed_factor * (1 - train.delay_seconds / 3600)
        actual_speed = max(20, min(actual_speed, edge.max_speed_kmh))
        
        # Update speed
        if abs(train.current_speed_kmh - actual_speed) > 5:
            self.tracker.update_train_speed(train.train_id, actual_speed)
            changes["speed_changes"].append({
                "train": train.train_id,
                "speed": actual_speed
            })
        
        # Calculate progress
        travel_time_seconds = edge.travel_time_min * 60
        progress_per_tick = self.config.tick_interval_seconds / travel_time_seconds
        
        new_progress = train.progress_on_edge + progress_per_tick
        
        if new_progress >= 1.0:
            # Train arrived at next station
            self._train_arrives(train, changes)
        else:
            self.tracker.update_train_position_on_edge(train.train_id, new_progress)
    
    def _train_arrives(self, train: Train, changes: Dict) -> None:
        """Handle train arrival at station."""
        if train.route_index >= len(train.route):
            # End of route
            self._complete_train(train)
            return
        
        next_station_name = train.route[train.route_index]["station_name"]
        
        # Exit edge first
        self.tracker.train_exits_edge(train.train_id)
        
        # Arrive at station
        self.tracker.train_arrives_at_station(train.train_id, next_station_name)
        
        changes["arrivals"].append({
            "train": train.train_id,
            "station": next_station_name
        })
        
        # Check if this is the last station
        if train.route_index >= len(train.route) - 1:
            self._complete_train(train)
    
    def _complete_train(self, train: Train) -> None:
        """Mark train as completed its route."""
        if train.train_id in self.active_trains:
            self.active_trains.remove(train.train_id)
        self.completed_trains.append(train.train_id)
        train.status = TrainStatus.STOPPED
    
    def _introduce_random_delays(self, changes: Dict) -> None:
        """Randomly introduce delays to trains."""
        if random.random() > self.config.delay_probability:
            return
        
        if not self.active_trains:
            return
        
        # Pick a random active train
        train_id = random.choice(self.active_trains)
        train = self.tracker.state.trains.get(train_id)
        
        if not train:
            return
        
        # Add delay
        delay_increase = random.randint(30, self.config.max_delay_seconds // 3)
        new_delay = train.delay_seconds + delay_increase
        new_delay = min(new_delay, self.config.max_delay_seconds)
        
        self.tracker.update_train_delay(train_id, new_delay)
        
        changes["delays_added"].append({
            "train": train_id,
            "delay_seconds": new_delay
        })
        
        # Maybe set to holding if at station and significant delay
        if train.current_position_type == "station" and new_delay > 180:
            if random.random() < 0.3:
                self.tracker.set_train_holding(train_id, True)
    
    def _maybe_spawn_trains(self, changes: Dict) -> None:
        """Maybe add more trains to simulation."""
        if len(self.active_trains) >= self.config.max_active_trains:
            return
        
        if random.random() > self.config.train_spawn_rate * 0.2:
            return
        
        # Find inactive trains
        inactive = [
            tid for tid in self.tracker.state.trains.keys()
            if tid not in self.active_trains and tid not in self.completed_trains
        ]
        
        if not inactive:
            return
        
        # Spawn one
        train_id = random.choice(inactive)
        train = self.tracker.state.trains.get(train_id)
        
        if train and train.route:
            start_station = train.route[0]["station_name"]
            train.current_position_type = "station"
            train.current_station = start_station
            train.route_index = 0
            train.status = TrainStatus.ON_TIME
            train.delay_seconds = 0
            
            station = self.tracker.state.stations.get(start_station)
            if station and train_id not in station.current_trains:
                station.current_trains.append(train_id)
            
            self.active_trains.append(train_id)
            changes["trains_spawned"].append(train_id)
    
    def _update_incidents(self, changes: Dict) -> None:
        """Update lifecycle of active incidents."""
        to_resolve = []
        for inc_id, incident in self.active_incidents_registry.items():
            # Randomly resolve incidents based on duration
            age_ticks = (self.current_time - incident.start_time).total_seconds() / self.config.tick_interval_seconds
            
            # Base resolution chance increases with age
            resolve_chance = 0.05 + (age_ticks * 0.01)
            if random.random() < resolve_chance:
                to_resolve.append(inc_id)
        
        for inc_id in to_resolve:
            incident = self.active_incidents_registry.pop(inc_id)
            
            # Remove from state
            for edge in self.tracker.state.edges.values():
                edge.active_incidents = [i for i in edge.active_incidents if i.incident_id != inc_id]
            for station in self.tracker.state.stations.values():
                station.active_incidents = [i for i in station.active_incidents if i.incident_id != inc_id]
            
            changes["incidents_resolved"].append(inc_id)

    def _maybe_spawn_incident(self, changes: Dict) -> None:
        """Randomly introduce disruptions based on real fault data patterns."""
        if random.random() > self.incident_probability:
            return
        
        # Pick a target (Edge or Station)
        is_edge = random.random() < 0.7
        
        incident_type = random.choice(list(IncidentType))
        severity = random.uniform(20, 95)
        is_blocking = severity > 70
        
        incident = Incident(
            incident_id=f"INC_{self.tick_count}_{random.randint(100, 999)}",
            type=incident_type,
            severity=severity,
            start_time=self.current_time,
            is_blocking=is_blocking,
            description=f"Generated {incident_type.value} incident"
        )
        
        if is_edge and self.tracker.state.edges:
            edge_id = random.choice(list(self.tracker.state.edges.keys()))
            self.tracker.state.edges[edge_id].active_incidents.append(incident)
            self.active_incidents_registry[incident.incident_id] = incident
            changes["incidents_started"].append({"id": incident.incident_id, "location": edge_id})
        elif self.tracker.state.stations:
            station_id = random.choice(list(self.tracker.state.stations.keys()))
            self.tracker.state.stations[station_id].active_incidents.append(incident)
            self.active_incidents_registry[incident.incident_id] = incident
            changes["incidents_started"].append({"id": incident.incident_id, "location": station_id})

            changes["incidents_started"].append({"id": incident.incident_id, "location": station_id})

    def _update_weather(self, changes: Dict) -> None:
        """Randomly cycle weather conditions."""
        if random.random() > 0.05:  # 5% chance to change weather each tick
            return
            
        weathers = ["clear", "rain", "snow", "fog", "storm"]
        new_weather = random.choice(weathers)
        
        if new_weather != self.tracker.state.weather:
            self.tracker.update_weather(new_weather)
            changes["weather"] = new_weather
            # Increase incident probability if weather is bad
            if new_weather in ["snow", "storm"]:
                self.incident_probability *= 1.5
            else:
                self.incident_probability = 0.05 + (0.1 if self.config.scenario == ScenarioType.DISRUPTION else 0)

    def run(self, callback=None) -> Generator[Dict, None, None]:
        """
        Run simulation as a generator.
        Yields changes each tick.
        """
        while self.tick_count < self.config.max_ticks:
            changes = self.tick()
            
            if callback:
                callback(changes)
            
            yield changes

    def run_realtime(self, tick_real_seconds: int = 30, callback=None) -> None:
        """
        Run the simulator in real time, calling `tick()` and then sleeping
        for `tick_real_seconds` between iterations. The callback (if provided)
        will be invoked with the `changes` dict after each tick. This is useful
        to simulate receiving data every `tick_real_seconds` seconds and
        forwarding it to the detection layer.
        """
        while self.tick_count < self.config.max_ticks:
            changes = self.tick()
            if callback:
                try:
                    callback(changes)
                except Exception:
                    # swallow callback errors to keep realtime loop running
                    pass
            time.sleep(tick_real_seconds)
    
    def get_summary(self) -> Dict:
        """Get simulation summary."""
        return {
            "ticks_completed": self.tick_count,
            "active_trains": len(self.active_trains),
            "completed_trains": len(self.completed_trains),
            "current_time": self.current_time.isoformat(),
            "scenario": self.config.scenario.value
        }


def create_scenario_simulator(
    state_tracker: StateTracker,
    scenario: str,
    ticks: int = 100,
    seed: Optional[int] = None
) -> MockSimulator:
    """Factory function to create a simulator for a specific scenario."""
    scenario_type = ScenarioType(scenario) if scenario in [s.value for s in ScenarioType] else ScenarioType.NORMAL
    
    config = SimulationConfig(
        max_ticks=ticks,
        scenario=scenario_type,
        random_seed=seed
    )
    
    return MockSimulator(state_tracker, config)
