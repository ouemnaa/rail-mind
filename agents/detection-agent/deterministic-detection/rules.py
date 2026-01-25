"""
Conflict Rules Engine
Deterministic rule-based detection of railway conflicts.

Each rule:
- Has a unique identifier
- Checks a specific condition
- Returns zero or more Conflict objects
- Is stateless (operates on current NetworkState)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import timedelta

from models import (
    Conflict, ConflictType, ConflictSeverity,
    Station, RailSegment, Train, TrainStatus,
    BlockingBehavior, RiskProfile, CongestionLevel
)
from state_tracker import NetworkState


class ConflictRule(ABC):
    """Base class for all conflict detection rules."""
    
    rule_id: str
    description: str
    
    @abstractmethod
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        """Evaluate rule against current state. Returns list of conflicts."""
        pass


# =============================================================================
# EDGE-LEVEL RULES
# =============================================================================

class EdgeCapacityOverflowRule(ConflictRule):
    """
    Rule: EDGE_CAPACITY_001
    Detects when edge load exceeds capacity.
    
    Trigger: current_load > capacity
    Severity: HIGH if 150%+ over, MEDIUM otherwise
    """
    
    rule_id = "EDGE_CAPACITY_001"
    description = "Edge capacity overflow detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for edge_id, edge in state.edges.items():
            if edge.current_load > edge.capacity:
                overflow_ratio = edge.current_load / edge.capacity
                severity = ConflictSeverity.HIGH if overflow_ratio >= 1.5 else ConflictSeverity.MEDIUM
                
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.EDGE_CAPACITY_OVERFLOW,
                    severity=severity,
                    rule_triggered=self.rule_id,
                    explanation=(
                        f"Edge {edge_id} has {edge.current_load} trains but capacity is {edge.capacity}. "
                        f"Overflow ratio: {overflow_ratio:.1f}x"
                    ),
                    edge_id=edge_id,
                    involved_trains=list(edge.trains_on_segment),
                    metadata={"current_load": edge.current_load, "capacity": edge.capacity}
                ))
        
        return conflicts


class HeadwayViolationRule(ConflictRule):
    """
    Rule: EDGE_HEADWAY_001
    Detects when trains enter edge too close together.
    
    Trigger: time_since_last_entry < min_headway_sec
    Severity: CRITICAL if < 50% headway, HIGH if < 75%, MEDIUM otherwise
    """
    
    rule_id = "EDGE_HEADWAY_001"
    description = "Headway violation detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for edge_id, edge in state.edges.items():
            recent_entries = state.get_recent_edge_entries(edge_id, window_seconds=edge.min_headway_sec * 2)
            
            if len(recent_entries) < 2:
                continue
            
            # Sort by time
            recent_entries.sort(key=lambda x: x[1])
            
            for i in range(1, len(recent_entries)):
                prev_train, prev_time, prev_dir = recent_entries[i - 1]
                curr_train, curr_time, curr_dir = recent_entries[i]
                
                # Only check same-direction entries
                if prev_dir != curr_dir:
                    continue
                
                time_diff = (curr_time - prev_time).total_seconds()
                
                if time_diff < edge.min_headway_sec:
                    headway_ratio = time_diff / edge.min_headway_sec
                    
                    if headway_ratio < 0.5:
                        severity = ConflictSeverity.CRITICAL
                    elif headway_ratio < 0.75:
                        severity = ConflictSeverity.HIGH
                    else:
                        severity = ConflictSeverity.MEDIUM
                    
                    conflicts.append(Conflict.create(
                        conflict_type=ConflictType.HEADWAY_VIOLATION,
                        severity=severity,
                        rule_triggered=self.rule_id,
                        explanation=(
                            f"Headway violation on {edge_id}: {curr_train} entered {time_diff:.0f}s "
                            f"after {prev_train}, minimum is {edge.min_headway_sec}s"
                        ),
                        edge_id=edge_id,
                        involved_trains=[prev_train, curr_train],
                        metadata={
                            "actual_headway_sec": time_diff,
                            "required_headway_sec": edge.min_headway_sec,
                            "direction": curr_dir
                        }
                    ))
        
        return conflicts


class OppositeDirectionConflictRule(ConflictRule):
    """
    Rule: EDGE_DIRECTION_001
    Detects opposing trains on single-track or bidirectional segment.
    
    Trigger: Two trains on same edge moving in opposite directions
    Severity: CRITICAL (collision risk)
    """
    
    rule_id = "EDGE_DIRECTION_001"
    description = "Opposite direction conflict detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for edge_id, edge in state.edges.items():
            if len(edge.trains_on_segment) < 2:
                continue
            
            # Get trains and their directions
            trains_on_edge = [state.trains.get(tid) for tid in edge.trains_on_segment]
            trains_on_edge = [t for t in trains_on_edge if t is not None]
            
            if len(trains_on_edge) < 2:
                continue
            
            # Check for opposing directions
            directions = set()
            for train in trains_on_edge:
                # Determine direction from route
                if train.route_index > 0 and train.route_index < len(train.route):
                    prev_station = train.route[train.route_index - 1]["station_name"]
                    curr_station = train.route[train.route_index]["station_name"]
                    direction = f"{prev_station}->{curr_station}"
                    directions.add(direction)
            
            # If we have opposing directions (simplified check)
            if len(directions) >= 2:
                # Check if directions are actually opposite
                dir_list = list(directions)
                for i in range(len(dir_list)):
                    for j in range(i + 1, len(dir_list)):
                        d1_parts = dir_list[i].split("->")
                        d2_parts = dir_list[j].split("->")
                        
                        if (d1_parts[0] == d2_parts[1] and d1_parts[1] == d2_parts[0]):
                            conflicts.append(Conflict.create(
                                conflict_type=ConflictType.OPPOSITE_DIRECTION_CONFLICT,
                                severity=ConflictSeverity.CRITICAL,
                                rule_triggered=self.rule_id,
                                explanation=(
                                    f"CRITICAL: Opposing trains on edge {edge_id}. "
                                    f"Directions: {dir_list[i]} vs {dir_list[j]}"
                                ),
                                edge_id=edge_id,
                                involved_trains=list(edge.trains_on_segment),
                                metadata={"directions": list(directions)}
                            ))
        
        return conflicts


class SpeedIncompatibilityRule(ConflictRule):
    """
    Rule: EDGE_SPEED_001
    Detects catch-up risk from speed differential.
    
    Trigger: Faster train behind slower train, closing distance
    Severity: HIGH if closing fast, MEDIUM otherwise
    """
    
    rule_id = "EDGE_SPEED_001"
    description = "Speed incompatibility and catch-up risk detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for edge_id, edge in state.edges.items():
            if len(edge.trains_on_segment) < 2:
                continue
            
            # Get trains with their progress
            trains_data = []
            for tid in edge.trains_on_segment:
                train = state.trains.get(tid)
                if train and train.current_position_type == "edge":
                    trains_data.append({
                        "train": train,
                        "progress": train.progress_on_edge,
                        "speed": train.current_speed_kmh
                    })
            
            if len(trains_data) < 2:
                continue
            
            # Sort by progress (position on edge)
            trains_data.sort(key=lambda x: x["progress"])
            
            # Check each pair (rear train vs front train)
            for i in range(len(trains_data) - 1):
                rear = trains_data[i]
                front = trains_data[i + 1]
                
                # Is rear train faster?
                speed_diff = rear["speed"] - front["speed"]
                
                if speed_diff > 20:  # km/h threshold
                    progress_gap = front["progress"] - rear["progress"]
                    
                    # If gap is small and speed diff is high
                    if progress_gap < 0.3:  # Less than 30% of edge apart
                        severity = ConflictSeverity.HIGH if speed_diff > 40 else ConflictSeverity.MEDIUM
                        
                        conflicts.append(Conflict.create(
                            conflict_type=ConflictType.SPEED_INCOMPATIBILITY,
                            severity=severity,
                            rule_triggered=self.rule_id,
                            explanation=(
                                f"Catch-up risk on {edge_id}: {rear['train'].train_id} "
                                f"({rear['speed']:.0f}km/h) closing on {front['train'].train_id} "
                                f"({front['speed']:.0f}km/h), gap {progress_gap:.0%}"
                            ),
                            edge_id=edge_id,
                            involved_trains=[rear["train"].train_id, front["train"].train_id],
                            metadata={
                                "speed_differential_kmh": speed_diff,
                                "progress_gap": progress_gap
                            }
                        ))
        
        return conflicts


# =============================================================================
# STATION-LEVEL RULES
# =============================================================================

class PlatformOverflowRule(ConflictRule):
    """
    Rule: STATION_PLATFORM_001
    Detects when station has more trains than max_trains_at_once.
    
    Trigger: current_trains > max_trains_at_once
    Severity: HIGH
    """
    
    rule_id = "STATION_PLATFORM_001"
    description = "Platform overflow detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for station_id, station in state.stations.items():
            if station.current_occupancy > station.max_trains_at_once:
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.PLATFORM_OVERFLOW,
                    severity=ConflictSeverity.HIGH,
                    rule_triggered=self.rule_id,
                    explanation=(
                        f"Station {station_id} has {station.current_occupancy} trains "
                        f"but max allowed is {station.max_trains_at_once}"
                    ),
                    node_id=station_id,
                    involved_trains=list(station.current_trains),
                    metadata={
                        "current": station.current_occupancy,
                        "max": station.max_trains_at_once
                    }
                ))
        
        return conflicts


class SimultaneousArrivalOverflowRule(ConflictRule):
    """
    Rule: STATION_ARRIVAL_001
    Detects too many simultaneous arrivals.
    
    Trigger: arrivals in last 60s > max_simultaneous_arrivals
    Severity: MEDIUM
    """
    
    rule_id = "STATION_ARRIVAL_001"
    description = "Simultaneous arrival overflow detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for station_id, station in state.stations.items():
            recent_arrivals = state.get_recent_station_arrivals(station_id, window_seconds=60)
            
            if len(recent_arrivals) > station.max_simultaneous_arrivals:
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.SIMULTANEOUS_ARRIVAL_OVERFLOW,
                    severity=ConflictSeverity.MEDIUM,
                    rule_triggered=self.rule_id,
                    explanation=(
                        f"Station {station_id} had {len(recent_arrivals)} arrivals in last 60s, "
                        f"max is {station.max_simultaneous_arrivals}"
                    ),
                    node_id=station_id,
                    involved_trains=[tid for tid, _ in recent_arrivals],
                    metadata={
                        "arrival_count": len(recent_arrivals),
                        "max_allowed": station.max_simultaneous_arrivals
                    }
                ))
        
        return conflicts


class DwellTimeViolationRule(ConflictRule):
    """
    Rule: STATION_DWELL_001
    Detects trains departing before minimum dwell time.
    
    Trigger: actual_dwell < min_dwell_time_sec
    Severity: LOW (operational concern)
    """
    
    rule_id = "STATION_DWELL_001"
    description = "Dwell time violation detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for train_id, train in state.trains.items():
            # Check trains that just departed (on edge with low progress)
            if (train.current_position_type == "edge" and 
                train.progress_on_edge < 0.1 and
                train.actual_departure and train.actual_arrival):
                
                dwell_time = (train.actual_departure - train.actual_arrival).total_seconds()
                
                # Get previous station
                if train.route_index > 0:
                    prev_station_name = train.route[train.route_index - 1]["station_name"]
                    station = state.stations.get(prev_station_name)
                    
                    if station and dwell_time < station.min_dwell_time_sec:
                        conflicts.append(Conflict.create(
                            conflict_type=ConflictType.DWELL_TIME_VIOLATION,
                            severity=ConflictSeverity.LOW,
                            rule_triggered=self.rule_id,
                            explanation=(
                                f"Train {train_id} departed {prev_station_name} after "
                                f"{dwell_time:.0f}s, minimum is {station.min_dwell_time_sec}s"
                            ),
                            node_id=prev_station_name,
                            involved_trains=[train_id],
                            metadata={
                                "actual_dwell_sec": dwell_time,
                                "required_dwell_sec": station.min_dwell_time_sec
                            }
                        ))
        
        return conflicts


class BlockingBehaviorViolationRule(ConflictRule):
    """
    Rule: STATION_BLOCKING_001
    Detects violations of station blocking behavior.
    
    Trigger: Station is full (hard blocking) but train is trying to enter
    Severity: HIGH for hard blocking violations
    """
    
    rule_id = "STATION_BLOCKING_001"
    description = "Blocking behavior violation detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for station_id, station in state.stations.items():
            # Check if station is at capacity with hard blocking
            if (station.blocking_behavior == BlockingBehavior.HARD and 
                station.is_at_capacity and 
                station.pending_arrivals):
                
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.BLOCKING_BEHAVIOR_VIOLATION,
                    severity=ConflictSeverity.HIGH,
                    rule_triggered=self.rule_id,
                    explanation=(
                        f"Station {station_id} has hard blocking enabled and is at capacity "
                        f"({station.current_occupancy}/{station.max_trains_at_once}), "
                        f"but {len(station.pending_arrivals)} trains pending arrival"
                    ),
                    node_id=station_id,
                    involved_trains=station.current_trains + station.pending_arrivals,
                    metadata={
                        "pending_arrivals": station.pending_arrivals,
                        "blocking_behavior": station.blocking_behavior.value
                    }
                ))
        
        return conflicts


# =============================================================================
# TRAIN-LEVEL RULES
# =============================================================================

class PriorityInversionRule(ConflictRule):
    """
    Rule: TRAIN_PRIORITY_001
    Detects low-priority train blocking high-priority train.
    
    Trigger: Lower priority train ahead of higher priority train on same edge/station
    Severity: MEDIUM normally, HIGH if significant priority gap
    """
    
    rule_id = "TRAIN_PRIORITY_001"
    description = "Priority inversion detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        # Check stations
        for station_id, station in state.stations.items():
            if len(station.current_trains) < 2:
                continue
            
            trains = [state.trains.get(tid) for tid in station.current_trains]
            trains = [t for t in trains if t is not None]
            
            # Find priority inversions
            for i, t1 in enumerate(trains):
                for t2 in trains[i + 1:]:
                    priority_diff = abs(t1.priority - t2.priority)
                    
                    if priority_diff >= 2:  # Significant priority gap
                        higher = t1 if t1.priority > t2.priority else t2
                        lower = t2 if t1.priority > t2.priority else t1
                        
                        # Check if lower priority is blocking higher
                        if lower.status == TrainStatus.HOLDING or lower.delay_seconds > 120:
                            severity = ConflictSeverity.HIGH if priority_diff >= 3 else ConflictSeverity.MEDIUM
                            
                            conflicts.append(Conflict.create(
                                conflict_type=ConflictType.PRIORITY_INVERSION,
                                severity=severity,
                                rule_triggered=self.rule_id,
                                explanation=(
                                    f"Priority inversion at {station_id}: {lower.train_id} "
                                    f"(priority {lower.priority}) blocking {higher.train_id} "
                                    f"(priority {higher.priority})"
                                ),
                                node_id=station_id,
                                involved_trains=[higher.train_id, lower.train_id],
                                metadata={
                                    "higher_priority_train": higher.train_id,
                                    "lower_priority_train": lower.train_id,
                                    "priority_gap": priority_diff
                                }
                            ))
        
        return conflicts


class DelayPropagationRiskRule(ConflictRule):
    """
    Rule: TRAIN_DELAY_001
    Detects trains with excessive delay that may propagate.
    
    Trigger: delay > threshold AND train on busy route
    Severity: Based on delay magnitude and position
    """
    
    rule_id = "TRAIN_DELAY_001"
    description = "Delay propagation risk detection"
    
    DELAY_THRESHOLD_MEDIUM = 180  # 3 minutes
    DELAY_THRESHOLD_HIGH = 300    # 5 minutes
    DELAY_THRESHOLD_CRITICAL = 600  # 10 minutes
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for train_id, train in state.trains.items():
            if train.delay_seconds < self.DELAY_THRESHOLD_MEDIUM:
                continue
            
            # Determine severity
            if train.delay_seconds >= self.DELAY_THRESHOLD_CRITICAL:
                severity = ConflictSeverity.CRITICAL
            elif train.delay_seconds >= self.DELAY_THRESHOLD_HIGH:
                severity = ConflictSeverity.HIGH
            else:
                severity = ConflictSeverity.MEDIUM
            
            # Check if at congested location
            location = train.current_station or train.current_edge
            location_type = train.current_position_type
            
            # Higher priority trains with delay are more concerning
            if train.priority >= 3:  # Intercity or higher
                if severity == ConflictSeverity.MEDIUM:
                    severity = ConflictSeverity.HIGH
            
            conflicts.append(Conflict.create(
                conflict_type=ConflictType.DELAY_PROPAGATION_RISK,
                severity=severity,
                rule_triggered=self.rule_id,
                explanation=(
                    f"Train {train_id} ({train.train_type.value}) has {train.delay_seconds}s delay "
                    f"at {location_type} {location}. Risk of downstream propagation."
                ),
                node_id=train.current_station,
                edge_id=train.current_edge,
                involved_trains=[train_id],
                metadata={
                    "delay_seconds": train.delay_seconds,
                    "train_priority": train.priority,
                    "remaining_stops": len(train.route) - train.route_index
                }
            ))
        
        return conflicts


class UnauthorizedHoldRule(ConflictRule):
    """
    Rule: TRAIN_HOLD_001
    Detects trains holding where not permitted.
    
    Trigger: train.status == HOLDING AND station.hold_allowed == False
    Severity: HIGH
    """
    
    rule_id = "TRAIN_HOLD_001"
    description = "Unauthorized hold detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for train_id, train in state.trains.items():
            if train.status != TrainStatus.HOLDING:
                continue
            
            if train.current_position_type == "station" and train.current_station:
                station = state.stations.get(train.current_station)
                
                if station and not station.hold_allowed:
                    conflicts.append(Conflict.create(
                        conflict_type=ConflictType.UNAUTHORIZED_HOLD,
                        severity=ConflictSeverity.HIGH,
                        rule_triggered=self.rule_id,
                        explanation=(
                            f"Train {train_id} is holding at {train.current_station} "
                            f"but holding is not permitted at this station"
                        ),
                        node_id=train.current_station,
                        involved_trains=[train_id],
                        metadata={"station_hold_allowed": False}
                    ))
                
                # Also check max hold time
                elif station and train.hold_start_time:
                    hold_duration = (state.current_time - train.hold_start_time).total_seconds()
                    if hold_duration > station.max_hold_time_sec:
                        conflicts.append(Conflict.create(
                            conflict_type=ConflictType.UNAUTHORIZED_HOLD,
                            severity=ConflictSeverity.MEDIUM,
                            rule_triggered=self.rule_id,
                            explanation=(
                                f"Train {train_id} has been holding at {train.current_station} "
                                f"for {hold_duration:.0f}s, max is {station.max_hold_time_sec}s"
                            ),
                            node_id=train.current_station,
                            involved_trains=[train_id],
                            metadata={
                                "hold_duration_sec": hold_duration,
                                "max_hold_sec": station.max_hold_time_sec
                            }
                        ))
        
        return conflicts


# =============================================================================
# NETWORK-LEVEL RULES
# =============================================================================

class CascadingCongestionRule(ConflictRule):
    """
    Rule: NETWORK_CASCADE_001
    Detects risk of cascading congestion across connected elements.
    
    Trigger: Multiple adjacent stations/edges at high load
    Severity: HIGH to CRITICAL
    """
    
    rule_id = "NETWORK_CASCADE_001"
    description = "Cascading congestion risk detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        # Find stations at >80% capacity
        congested_stations = [
            sid for sid, s in state.stations.items()
            if s.current_occupancy >= s.max_trains_at_once * 0.8
        ]
        
        # Check for clusters of congestion
        for station_id in congested_stations:
            neighbors = state.adjacency.get(station_id, [])
            congested_neighbors = [n for n in neighbors if n in congested_stations]
            
            if len(congested_neighbors) >= 2:
                involved_stations = [station_id] + congested_neighbors
                
                # Get all trains in the cluster
                involved_trains = []
                for sid in involved_stations:
                    station = state.stations.get(sid)
                    if station:
                        involved_trains.extend(station.current_trains)
                
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.CASCADING_CONGESTION,
                    severity=ConflictSeverity.HIGH,
                    rule_triggered=self.rule_id,
                    explanation=(
                        f"Cascading congestion risk: {station_id} and {len(congested_neighbors)} "
                        f"adjacent stations are near capacity. Cluster: {involved_stations}"
                    ),
                    node_id=station_id,
                    involved_trains=list(set(involved_trains)),
                    metadata={
                        "congested_cluster": involved_stations,
                        "cluster_size": len(involved_stations)
                    }
                ))
        
        return conflicts


class HubSaturationRule(ConflictRule):
    """
    Rule: NETWORK_HUB_001
    Detects major hub approaching or at saturation.
    
    Trigger: priority_station at >90% capacity
    Severity: CRITICAL (hubs affect entire network)
    """
    
    rule_id = "NETWORK_HUB_001"
    description = "Hub saturation detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for station_id, station in state.stations.items():
            if not station.priority_station:
                continue
            
            saturation = station.current_occupancy / station.max_trains_at_once
            
            if saturation >= 0.9:
                severity = ConflictSeverity.CRITICAL if saturation >= 1.0 else ConflictSeverity.HIGH
                
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.HUB_SATURATION,
                    severity=severity,
                    rule_triggered=self.rule_id,
                    explanation=(
                        f"Major hub {station_id} at {saturation:.0%} saturation "
                        f"({station.current_occupancy}/{station.max_trains_at_once}). "
                        f"Network-wide impact possible."
                    ),
                    node_id=station_id,
                    involved_trains=list(station.current_trains),
                    metadata={
                        "saturation": saturation,
                        "is_priority_hub": True
                    }
                ))
        
        return conflicts


class HighRiskEdgeStressRule(ConflictRule):
    """
    Rule: NETWORK_RISK_001
    Detects high-risk edges under stress.
    
    Trigger: risk_profile == HIGH AND current_load > 0
    Severity: Based on load and incident history
    """
    
    rule_id = "NETWORK_RISK_001"
    description = "High-risk edge stress detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        for edge_id, edge in state.edges.items():
            if edge.risk_profile != RiskProfile.HIGH:
                continue
            
            if edge.current_load == 0:
                continue
            
            # Calculate stress level
            load_ratio = edge.current_load / edge.capacity
            incident_factor = min(edge.historical_incidents / 5, 1.0)  # Cap at 5 incidents
            stress_score = load_ratio * (1 + incident_factor)
            
            if stress_score > 0.5:
                severity = ConflictSeverity.HIGH if stress_score > 0.8 else ConflictSeverity.MEDIUM
                
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.HIGH_RISK_EDGE_STRESS,
                    severity=severity,
                    rule_triggered=self.rule_id,
                    explanation=(
                        f"High-risk edge {edge_id} under stress: {edge.current_load} trains, "
                        f"{edge.historical_incidents} historical incidents, "
                        f"stress score {stress_score:.2f}"
                    ),
                    edge_id=edge_id,
                    involved_trains=list(edge.trains_on_segment),
                    metadata={
                        "stress_score": stress_score,
                        "historical_incidents": edge.historical_incidents,
                        "load_ratio": load_ratio
                    }
                ))
        
        return conflicts


class ActiveNetworkIncidentRule(ConflictRule):
    """
    Rule: NETWORK_SAFETY_001
    Detects trains in presence of active technical/safety incidents.
    
    Trigger: train on edge/station with active_incidents
    Severity: CRITICAL for blocking incidents, HIGH otherwise
    """
    
    rule_id = "NETWORK_SAFETY_001"
    description = "Active network incident impact detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        
        # Check all active trains for incident proximity
        for tid, train in state.trains.items():
            if train.status == TrainStatus.STOPPED:
                continue
                
            location_id = train.current_station or train.current_edge
            if not location_id:
                continue
                
            incidents = []
            if train.current_position_type == "station":
                station = state.stations.get(train.current_station)
                if station: incidents = station.active_incidents
            else:
                edge = state.edges.get(train.current_edge)
                if edge: incidents = edge.active_incidents
                
            for inc in incidents:
                severity = ConflictSeverity.CRITICAL if inc.is_blocking else ConflictSeverity.HIGH
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.SAFETY_VIOLATION,
                    severity=severity,
                    rule_triggered=self.rule_id,
                    explanation=(
                        f"Train {tid} in proximity of active {inc.type.value} incident "
                        f"at {location_id}. Impact: {'Blocked' if inc.is_blocking else 'Slowing'}. "
                        f"Description: {inc.description}"
                    ),
                    node_id=train.current_station,
                    edge_id=train.current_edge,
                    involved_trains=[tid],
                    metadata={
                        "incident_id": inc.incident_id,
                        "incident_type": inc.type.value,
                        "is_blocking": inc.is_blocking
                    }
                ))
        
        return conflicts


class WeatherImpactRule(ConflictRule):
    """
    Rule: NETWORK_WEATHER_001
    Detects safety risks due to severe weather conditions.
    
    Trigger: Severe weather AND (high speed OR high delay)
    Severity: HIGH
    """
    
    rule_id = "NETWORK_WEATHER_001"
    description = "Weather-related operational risk detection"
    
    def evaluate(self, state: NetworkState) -> List[Conflict]:
        conflicts = []
        if state.weather == "clear":
            return []
            
        is_severe = state.weather in ["storm", "snow", "fog"]
        
        for tid, train in state.trains.items():
            if train.status == TrainStatus.STOPPED:
                continue
                
            risk_triggered = False
            reason = ""
            
            if is_severe and train.current_speed_kmh > 100:
                risk_triggered = True
                reason = f"High speed ({train.current_speed_kmh:.0f}km/h) in severe weather ({state.weather})"
            elif state.weather == "fog" and train.current_speed_kmh > 60:
                 risk_triggered = True
                 reason = f"Speed exceeds safety limit for fog"
            elif train.delay_seconds > 600:
                 risk_triggered = True
                 reason = f"Significant delay accumulated during {state.weather} conditions"
                 
            if risk_triggered:
                conflicts.append(Conflict.create(
                    conflict_type=ConflictType.HIGH_RISK_EDGE_STRESS, # Reusing similar type
                    severity=ConflictSeverity.MEDIUM if not is_severe else ConflictSeverity.HIGH,
                    rule_triggered=self.rule_id,
                    explanation=f"Weather risk for Train {tid}: {reason}",
                    node_id=train.current_station,
                    edge_id=train.current_edge,
                    involved_trains=[tid],
                    metadata={"weather": state.weather, "speed": train.current_speed_kmh}
                ))
        
        return conflicts


# =============================================================================
# RULE REGISTRY
# =============================================================================

ALL_RULES: List[ConflictRule] = [
    # Edge-level
    EdgeCapacityOverflowRule(),
    HeadwayViolationRule(),
    OppositeDirectionConflictRule(),
    SpeedIncompatibilityRule(),
    
    # Station-level
    PlatformOverflowRule(),
    SimultaneousArrivalOverflowRule(),
    DwellTimeViolationRule(),
    BlockingBehaviorViolationRule(),
    
    # Train-level
    PriorityInversionRule(),
    DelayPropagationRiskRule(),
    UnauthorizedHoldRule(),
    
    # Network-level
    CascadingCongestionRule(),
    HubSaturationRule(),
    HighRiskEdgeStressRule(),
    ActiveNetworkIncidentRule(),
    WeatherImpactRule(),
]


def get_rule_by_id(rule_id: str) -> Optional[ConflictRule]:
    """Get a specific rule by its ID."""
    for rule in ALL_RULES:
        if rule.rule_id == rule_id:
            return rule
    return None
