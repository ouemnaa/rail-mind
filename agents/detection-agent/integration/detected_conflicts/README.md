# Detected Conflicts Directory

This directory contains **auto-saved conflicts** in a single consolidated file that is updated whenever the simulation detects actual conflicts (not predictions).

## Purpose

The `detected_conflicts.json` file is designed for the **Resolution Agent** to:
1. Read all detected conflicts from one place
2. Load context from `lombardy_simulation_data.json`
3. Generate resolution strategies
4. Apply solutions to resolve conflicts
5. Update conflict status (unresolved → resolved)

## File Structure

**Single File:** `detected_conflicts.json`

All conflicts are accumulated in this one file, making it easy to:
- Track all conflicts in chronological order
- Filter by status (unresolved/resolved)
- Process multiple conflicts in batch
- Monitor conflict history over time

## File Structure

**Single File:** `detected_conflicts.json`

All conflicts are accumulated in this one file, making it easy to:
- Track all conflicts in chronological order
- Filter by status (unresolved/resolved)
- Process multiple conflicts in batch
- Monitor conflict history over time

### JSON Structure

```json
{
  "file_info": {
    "description": "All detected conflicts from simulation",
    "last_updated": "2026-01-25T21:38:04.503376",
    "total_conflicts": 16,
    "unresolved_count": 16,
    "resolved_count": 0
  },
  "conflicts": [
    {
      "metadata": {
        "conflict_id": "uuid",
        "timestamp": "2026-01-25T14:38:21.895220",
        "tick_number": 23,
        "simulation_time": "2026-01-25T14:38:21.895220"
      },
      "conflict": {
        "type": "edge_capacity_overflow",
        "severity": "high",
        "probability": 1.0,
        "location": "MILANO CENTRALE-MILANO ROGOREDO",
        "location_type": "edge",
        "explanation": "Edge has 4 trains but capacity is 3",
        "resolution_suggestions": [...]
      },
      "affected_trains": [...],
      "network_context": {...},
      "status": "unresolved"
    },
    // ... more conflicts
  ]
}
```

```json
{
  "metadata": {
    "conflict_id": "CON_23_145",
    "timestamp": "2026-01-25T14:38:21.895220",
    "tick_number": 23,
    "simulation_time": "2026-01-25T14:38:21.895220"
  },
  "conflict": {
    "type": "edge_capacity_overflow",
    "severity": "high",
    "probability": 1.0,
    "location": "MILANO CENTRALE-MILANO ROGOREDO",
    "location_type": "edge",
    "explanation": "Edge has 4 trains but capacity is 3",
    "resolution_suggestions": [
      "Slow down train FR_9700 by 20%",
      "Reroute train REG_2014 to alternative path",
      "Hold train IC_1539 at previous station for 5 minutes"
    ]
  },
  "affected_trains": [
    {
      "train_id": "FR_9700",
      "train_type": "high_speed",
      "current_station": null,
      "next_station": "MILANO ROGOREDO",
      "current_edge": "MILANO CENTRALE-MILANO ROGOREDO",
      "position_km": 2.5,
      "speed_kmh": 80,
      "delay_sec": 120,
      "status": "en_route",
      "lat": 45.48,
      "lon": 9.21,
      "route": [...],
      "current_stop_index": 2
    },
    ...
  ],
  "network_context": {
    "type": "edge",
    "id": "MILANO CENTRALE-MILANO ROGOREDO",
    "from": "MILANO CENTRALE",
    "to": "MILANO ROGOREDO",
    "distance_km": 5.2,
    "capacity": 3,
    "max_speed_kmh": 120
  },
  "status": "unresolved"
}
```

## Fields Explanation

### File Info
- **description**: Purpose of the file
- **last_updated**: Last time a conflict was added
- **total_conflicts**: Total number of conflicts recorded
- **unresolved_count**: Conflicts waiting for resolution
- **resolved_count**: Conflicts that have been resolved

### Metadata (per conflict)
- **conflict_id**: Unique identifier (format: `CON_<tick>_<random>`)
- **timestamp**: When conflict was detected (ISO 8601)
- **tick_number**: Simulation tick when detected
- **simulation_time**: Simulation time (not real time)

### Conflict
- **type**: Conflict type (`edge_capacity_overflow`, `platform_overflow`, `headway_violation`, `scheduling_conflict`)
- **severity**: `low`, `medium`, `high`, `critical`
- **probability**: Always 1.0 (detected = confirmed)
- **location**: Station name or edge ID where conflict occurred
- **location_type**: `station` or `edge`
- **explanation**: Human-readable description
- **resolution_suggestions**: Array of possible solutions

### Affected Trains
Array of trains involved in the conflict with complete state:
- Current position (station/edge)
- Speed, delay, status
- Full route information
- Geographic coordinates

### Network Context
Information about the location where conflict occurred:
- **Station**: name, ID, platforms, connections, coordinates
- **Edge**: from/to stations, distance, capacity, max speed

### Status
- **unresolved**: Conflict waiting for resolution
- **resolved**: After resolution agent processes it
- **failed**: If resolution attempt failed

## Resolution Agent Usage

```python
import json
from pathlib import Path

# 1. Load the consolidated conflicts file
conflict_file = Path("detected_conflicts/detected_conflicts.json")
with open(conflict_file) as f:
    data = json.load(f)

# 2. Get file info
print(f"Total conflicts: {data['file_info']['total_conflicts']}")
print(f"Unresolved: {data['file_info']['unresolved_count']}")

# 3. Filter unresolved conflicts
unresolved = [c for c in data['conflicts'] if c['status'] == 'unresolved']

# 4. Load network context (once)
with open("../../creating-context/lombardy_simulation_data.json") as f:
    network_data = json.load(f)

# 5. Process each conflict
for conflict in unresolved:
    conflict_type = conflict["conflict"]["type"]
    affected_trains = conflict["affected_trains"]
    location = conflict["conflict"]["location"]
    
    # Generate resolution strategy
    resolution = generate_resolution(conflict, network_data)
    
    # Apply resolution
    apply_resolution(resolution)
    
    # Mark as resolved
    conflict["status"] = "resolved"
    conflict["resolution_applied"] = resolution
    conflict["resolved_at"] = datetime.now().isoformat()

# 6. Update counts
data['file_info']['unresolved_count'] = len([c for c in data['conflicts'] if c['status'] == 'unresolved'])
data['file_info']['resolved_count'] = len([c for c in data['conflicts'] if c['status'] == 'resolved'])
data['file_info']['last_updated'] = datetime.now().isoformat()

# 7. Save updated file
with open(conflict_file, 'w') as f:
    json.dump(data, f, indent=2)
```

## Conflict Types

1. **edge_capacity_overflow**: Too many trains on same track segment
   - Resolution: Slow down, reroute, or hold trains

2. **platform_overflow**: Too many trains at station
   - Resolution: Redirect to different platforms, delay arrivals

3. **headway_violation**: Trains too close together
   - Resolution: Increase spacing, adjust speeds

4. **scheduling_conflict**: Timetable conflicts
   - Resolution: Adjust departure/arrival times

## Auto-Generation

Conflicts are automatically appended to `detected_conflicts.json` when:
- Detection engine finds a conflict
- Simulation advances one tick
- File is updated with new conflict entry

No manual API call needed!

## Benefits of Single File Approach

1. **Centralized**: All conflicts in one place
2. **Easy Tracking**: Monitor conflict history and trends
3. **Batch Processing**: Process multiple conflicts at once
4. **Status Management**: Filter by resolved/unresolved
5. **Simple Integration**: Resolution agent reads one file
6. **Atomic Updates**: File info updates automatically

## Integration with Resolution Agent

Resolution agent workflow:
```
1. Load detected_conflicts.json
2. Filter conflicts where status="unresolved"
3. Load lombardy_simulation_data.json for context
4. For each unresolved conflict:
   - Analyze conflict and affected trains
   - Generate resolution strategy
   - Apply resolution via API
   - Update conflict status to "resolved"
5. Save updated detected_conflicts.json
6. Repeat periodically (e.g., every 10 seconds)
```
