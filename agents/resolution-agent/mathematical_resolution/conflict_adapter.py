"""
Conflict Adapter: Converts external conflict formats to internal Conflict dataclass.
Supports the nour.json conflict format with types:
- headway_violation
- delay_propagation_risk  
- high_risk_edge_stress
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np

from .data_structures import Conflict


# Mapping external conflict types to internal types
CONFLICT_TYPE_MAP = {
    "headway_violation": "headway",
    "delay_propagation_risk": "delay",
    "high_risk_edge_stress": "capacity",
    "platform_conflict": "platform",
    "track_occupation": "track",
}

# Severity string to float mapping
SEVERITY_MAP = {
    "critical": 0.95,
    "high": 0.75,
    "medium": 0.50,
    "low": 0.25,
}


def parse_timestamp(ts_string: str) -> float:
    """Convert ISO timestamp string to Unix timestamp."""
    try:
        dt = datetime.fromisoformat(ts_string)
        return dt.timestamp()
    except (ValueError, TypeError):
        return datetime.now().timestamp()


def extract_stations_from_location(location: Dict) -> List[str]:
    """Extract station IDs from location object."""
    stations = []
    
    # Edge format: "STATION_A--STATION_B"
    if location.get("edge_id"):
        edge_id = location["edge_id"]
        if "--" in edge_id:
            parts = edge_id.split("--")
            stations.extend(parts)
        else:
            stations.append(edge_id)
    
    # Node format: single station
    if location.get("node_id"):
        stations.append(location["node_id"])
    
    return stations


def extract_delays_from_metadata(
    involved_trains: List[str],
    metadata: Dict,
    conflict_type: str
) -> Dict[str, float]:
    """
    Extract delay values from metadata.
    Returns dict of train_id -> delay in MINUTES.
    """
    delays = {}
    
    # Direct delay in metadata (delay_propagation_risk)
    if "delay_seconds" in metadata:
        delay_min = metadata["delay_seconds"] / 60.0
        for train_id in involved_trains:
            delays[train_id] = delay_min
    
    # Headway violation - estimate delay from headway difference
    elif conflict_type == "headway_violation":
        actual = metadata.get("actual_headway_sec", 0)
        required = metadata.get("required_headway_sec", 180)
        if actual < required:
            # The deficit becomes the delay to resolve
            delay_min = (required - actual) / 60.0
            for train_id in involved_trains:
                delays[train_id] = delay_min
    
    # Weather stress - assume moderate delay risk
    elif conflict_type == "high_risk_edge_stress":
        weather = metadata.get("weather", "clear")
        speed = metadata.get("speed", 100)
        
        # Higher speed in bad weather = higher risk/delay
        weather_factor = {"storm": 3.0, "fog": 2.0, "snow": 2.5, "rain": 1.5}.get(weather, 1.0)
        estimated_delay = (speed / 100.0) * weather_factor * 2.0  # minutes
        
        for train_id in involved_trains:
            delays[train_id] = estimated_delay
    
    # Default: assign small delay to involved trains
    if not delays:
        for train_id in involved_trains:
            delays[train_id] = 2.0  # 2 minutes default
    
    return delays


def convert_conflict(raw: Dict) -> Conflict:
    """
    Convert a raw conflict dictionary to Conflict dataclass.
    Supports:
    1. Flat format (nour.json)
    2. Nested format (detected_conflicts.json from unified API)
    """
    # 1. Determine if it's nested
    is_nested = "metadata" in raw and "conflict" in raw
    
    # Extract sub-dicts based on format
    if is_nested:
        meta_section = raw.get("metadata", {})
        conflict_section = raw.get("conflict", {})
        trains_section = raw.get("affected_trains", [])
        location = conflict_section.get("location", {})
        
        # Conflict ID
        conflict_id = meta_section.get("conflict_id", f"conflict_{id(raw)}")
        
        # Type
        conflict_type_raw = conflict_section.get("type", "unknown")
        
        # Severity
        severity_raw = conflict_section.get("severity", "medium")
        
        # Timestamp
        timestamp_raw = meta_section.get("timestamp", "")
        
        # Train IDs
        # In nested format, trains are objects. We need to extract IDs.
        if trains_section and isinstance(trains_section[0], dict):
            train_ids = [t.get("train_id") for t in trains_section if t.get("train_id")]
        else:
            train_ids = trains_section if isinstance(trains_section, list) else []
            
        # Metadata for delay calculation
        # Combine meta and conflict sections
        metadata = {**meta_section, **conflict_section}
        
    else:
        # Flat format (nour.json)
        conflict_id = raw.get("conflict_id", f"conflict_{id(raw)}")
        conflict_type_raw = raw.get("conflict_type", "unknown")
        severity_raw = raw.get("severity", "medium")
        timestamp_raw = raw.get("timestamp", "")
        location = raw.get("location", {})
        train_ids = raw.get("involved_trains", [])
        metadata = raw.get("metadata", {})

    # 2. General processing (format independent)
    conflict_type = CONFLICT_TYPE_MAP.get(conflict_type_raw, conflict_type_raw)
    
    # Parse severity
    if isinstance(severity_raw, str):
        severity = SEVERITY_MAP.get(severity_raw, 0.5)
    else:
        severity = float(severity_raw)
        
    # Parse timestamp
    timestamp = parse_timestamp(timestamp_raw)
    
    # Extract stations from location
    if isinstance(location, str):
        # Handle string location like "STATION_A--STATION_B"
        station_ids = extract_stations_from_location({"edge_id": location})
    else:
        station_ids = extract_stations_from_location(location)
        
    # Extract delays (minutes)
    delay_values = extract_delays_from_metadata(train_ids, metadata, conflict_type_raw)
    
    # Affected rails
    affected_rails = None
    if isinstance(location, str):
        if "--" in location:
            affected_rails = [{"edge_id": location}]
    elif location.get("edge_id"):
        affected_rails = [{"edge_id": location["edge_id"]}]
        
    # Blocking behavior
    blocking_behavior = "hard" if severity >= 0.75 else "soft"
    
    # Priority trains
    priority_trains = [t for t in train_ids if isinstance(t, str) and t.startswith(("FR_", "IC_"))]
    
    return Conflict(
        conflict_id=conflict_id,
        station_ids=station_ids,
        train_ids=train_ids,
        delay_values=delay_values,
        timestamp=timestamp,
        severity=severity,
        conflict_type=conflict_type,
        embedding=None,
        affected_rails=affected_rails,
        blocking_behavior=blocking_behavior,
        priority_trains=priority_trains if priority_trains else None,
    )


def load_conflicts_from_json(filepath: str) -> List[Conflict]:
    """
    Load conflicts from a JSON file.
    Supports both a flat list of conflicts (nour.json format)
    and a dictionary with a "conflicts" key (detected_conflicts.json format).
    Returns list of Conflict objects ready for resolution.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON formats
    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        if "conflicts" in data:
            raw_list = data["conflicts"]
        elif "detections" in data: # Some variants might use detections
            raw_list = data["detections"]
        else:
            # Maybe it's a single conflict object?
            if "conflict_id" in data:
                raw_list = [data]
            else:
                print(f"Warning: JSON dictionary at {filepath} has no known conflict keys.")
                return []
    else:
        print(f"Warning: Unexpected data type in {filepath}: {type(data)}")
        return []
    
    conflicts = []
    for raw in raw_list:
        try:
            # Skip if raw is not a dictionary (e.g. if someone put a string in the list)
            if not isinstance(raw, dict):
                continue
                
            conflict = convert_conflict(raw)
            conflicts.append(conflict)
        except Exception as e:
            conflict_id = raw.get('conflict_id', 'unknown') if isinstance(raw, dict) else 'unknown'
            print(f"Warning: Failed to convert conflict {conflict_id}: {e}")
    
    return conflicts


def load_conflicts_from_dict(raw_list: List[Dict]) -> List[Conflict]:
    """
    Convert a list of raw conflict dicts to Conflict objects.
    """
    return [convert_conflict(raw) for raw in raw_list]


def enrich_conflicts_with_train_data(
    conflicts: List[Conflict],
    train_data: List[Dict]
) -> List[Conflict]:
    """
    Enrich conflicts with additional train information.
    Updates priority_trains based on actual train types.
    """
    # Build train lookup
    train_lookup = {t["train_id"]: t for t in train_data}
    
    # Priority order: high_speed > intercity > regional
    type_priority = {"high_speed": 3, "intercity": 2, "regional": 1}
    
    for conflict in conflicts:
        # Determine priority trains based on actual types
        train_priorities = []
        for tid in conflict.train_ids:
            train = train_lookup.get(tid)
            if train:
                train_type = train.get("train_type", "regional")
                priority = type_priority.get(train_type, 1)
                train_priorities.append((tid, priority))
        
        # Sort by priority (highest first)
        train_priorities.sort(key=lambda x: x[1], reverse=True)
        conflict.priority_trains = [t[0] for t in train_priorities if t[1] >= 2]
    
    return conflicts


# Summary functions for display
def summarize_conflict(conflict: Conflict) -> str:
    """Return a human-readable summary of a conflict."""
    delay_str = ", ".join(f"{tid}: {d:.1f}min" for tid, d in conflict.delay_values.items())
    return (
        f"[{conflict.conflict_id[:8]}] {conflict.conflict_type.upper()} "
        f"(severity: {conflict.severity:.2f})\n"
        f"  Trains: {', '.join(conflict.train_ids)}\n"
        f"  Stations: {', '.join(conflict.station_ids)}\n"
        f"  Delays: {delay_str}"
    )


def summarize_all_conflicts(conflicts: List[Conflict]) -> str:
    """Return summary of all conflicts."""
    lines = [f"=== {len(conflicts)} CONFLICTS LOADED ===\n"]
    for i, c in enumerate(conflicts, 1):
        lines.append(f"{i}. {summarize_conflict(c)}\n")
    return "\n".join(lines)
