# Conflict Detection and Resolution Workflow

## Overview

The system now **automatically saves detected conflicts** to JSON files that your resolution agent can process.

## How It Works

### 1. Simulation Running (Every Tick = 1 minute)

```
unified_api.py (Port 8002)
    ↓
integration_engine.py
    ↓
┌──────────────────────────────────────┐
│  1. Move trains                      │
│  2. Update positions                 │
│  3. Run ML predictions (orange)      │
│  4. Run detection rules (red)        │  ← **IF CONFLICT FOUND**
│     ↓                                │       ↓
│     IF detections.length > 0:        │       Auto-save to file!
│        _save_detected_conflicts()    │
└──────────────────────────────────────┘
```

### 2. Data Sources

**Input (Simulation Data):**
```
📁 creating-context/lombardy_simulation_data.json
   - 50+ stations in Lombardy
   - 26+ train routes
   - Network topology (edges, distances, capacities)
```

**Output (Auto-Saved Conflicts):**
```
📁 agents/detection-agent/integration/detected_conflicts/
   └─ conflict_<type>_tick<N>_<id>.json
      - Conflict details
      - Affected trains (full state)
      - Network context (stations/edges)
      - Resolution suggestions
```

### 3. Conflict File Structure

Each auto-saved file contains everything your resolution agent needs:

```json
{
  "metadata": {
    "conflict_id": "unique-uuid",
    "timestamp": "2026-01-25T21:26:33",
    "tick_number": 20,
    "simulation_time": "2026-01-25T06:20:00"
  },
  "conflict": {
    "type": "edge_capacity_overflow",
    "severity": "medium",
    "probability": 1.0,
    "location": "BISUSCHIO VIGGIU--ARCISATE",
    "location_type": "edge",
    "explanation": "Edge has 4 trains but capacity is 3",
    "resolution_suggestions": [
      "Hold trains at previous station",
      "Reroute via alternative track",
      "Reduce speed to create spacing"
    ]
  },
  "affected_trains": [
    {
      "train_id": "REG_2553",
      "train_type": "regional",
      "current_station": null,
      "next_station": "ARCISATE",
      "current_edge": "BISUSCHIO VIGGIU--ARCISATE",
      "position_km": 6.67,
      "speed_kmh": 80,
      "delay_sec": 0,
      "status": "en_route",
      "lat": 45.863,
      "lon": 8.872,
      "route": [...],
      "current_stop_index": 1
    },
    // ... more trains
  ],
  "network_context": {
    "type": "edge",
    "id": "BISUSCHIO VIGGIU--ARCISATE",
    "from": "BISUSCHIO VIGGIU",
    "to": "ARCISATE",
    "distance_km": 2.5,
    "capacity": 3,
    "max_speed_kmh": 120
  },
  "status": "unresolved"
}
```

## Conflict Types and Resolutions

### 1. Edge Capacity Overflow
**Problem:** Too many trains on same track segment (exceeds capacity)

**Detection:** `edge.current_load > edge.capacity`

**Example Resolution:**
```python
def resolve_edge_overflow(trains, edge, network):
    # Option 1: Slow down trailing trains
    for train in trains[1:]:
        reduce_speed(train, percentage=20)
    
    # Option 2: Hold train at previous station
    hold_train_at_station(trains[-1], duration_min=5)
    
    # Option 3: Reroute via alternative path
    alternative_route = find_alternative_route(
        trains[0].current_station,
        trains[0].next_station,
        network
    )
    if alternative_route:
        reroute_train(trains[0], alternative_route)
```

### 2. Platform Overflow
**Problem:** Too many trains at station (exceeds platform count)

**Detection:** `station.current_trains.length > station.platforms`

**Example Resolution:**
```python
def resolve_platform_overflow(trains, station, network):
    # Option 1: Delay incoming trains
    for train in trains[3:]:  # Keep first 3, delay rest
        delay_arrival(train, delay_min=10)
    
    # Option 2: Speed up departures
    for train in trains[:3]:
        if train.status == "at_station":
            reduce_dwell_time(train, reduction_min=2)
    
    # Option 3: Redirect to nearby station
    nearby_stations = find_nearby_stations(station, radius_km=5)
    redirect_train(trains[-1], nearby_stations[0])
```

### 3. Headway Violation
**Problem:** Trains too close together on same track

**Detection:** Distance between trains < minimum_headway

**Example Resolution:**
```python
def resolve_headway_violation(train1, train2, edge):
    # Slow down trailing train
    if train2.speed_kmh > train1.speed_kmh:
        reduce_speed(train2, target_kmh=train1.speed_kmh * 0.8)
    
    # Or hold at previous station
    if train2.status == "at_station":
        extend_dwell_time(train2, additional_min=3)
```

## Testing the System

### Run Simulation Until Conflict Detected:

```powershell
# Start API server
cd c:\Users\dongm\OneDrive\Desktop\rail-mind
Start-Job { .venv\Scripts\python.exe backend\integration\unified_api.py }
Start-Sleep -Seconds 8

# Run simulation
for ($i = 1; $i -le 30; $i++) {
    $r = Invoke-WebRequest -Uri "http://localhost:8002/api/simulation/tick" -UseBasicParsing
    $j = $r.Content | ConvertFrom-Json
    
    Write-Output "Tick $($j.tick_number): D=$($j.detections.Count)"
    
    if ($j.detections.Count -gt 0) {
        Write-Output "CONFLICT DETECTED!"
        break
    }
}

# Check auto-saved files
Get-ChildItem "backend\integration\detected_conflicts\*.json"
```

### View Latest Conflict:

```powershell
$latest = Get-ChildItem "backend\integration\detected_conflicts\*.json" | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -First 1

Get-Content $latest.FullName | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

## Directory Structure

```
rail-mind/
├── creating-context/
│   └── lombardy_simulation_data.json  ← Input: Network data
│
├── agents/
│   ├── detection-agent/
│   │   ├── prediction_confilt/        ← ML models
│   │   └── deterministic-detection/   ← Rule engine
│   │
│   └── resolution-agent/              ← Your resolution agent
│       └── resolve_conflicts.py       ← Processes detected_conflicts/
│
├── backend/
│   └── integration/
│       ├── unified_api.py             ← API server (PORT 8002)
│       ├── integration_engine.py      ← Core logic
│       ├── detected_conflicts/        ← Auto-saved files
│       │   ├── README.md
│       │   └── detected_conflicts.json
│       └── conflict_results/          ← Manual snapshots
│
└── frontend/                          ← Visualization
    └── src/
        └── components/
            └── UnifiedAlertPanel.tsx  ← Shows predictions + detections
```

## Key Differences: Predictions vs Detections

| Aspect | Predictions (ML) | Detections (Rules) |
|--------|------------------|-------------------|
| **When** | 10-30 min ahead | Real-time (now) |
| **Source** | XGBoost + Heuristics | Deterministic rules |
| **Probability** | 0.0 - 1.0 | Always 1.0 (confirmed) |
| **Color** | Orange/Yellow | Red |
| **Purpose** | Early warning | Immediate action |
| **Saved?** | In full snapshots | Auto-saved individually |
| **For Resolution?** | Preventive actions | Active conflict resolution |

## Benefits of This Approach

1. **Automatic**: No manual API calls needed to save conflicts
2. **Focused**: Each file contains only relevant data (not all 26 trains)
3. **Ready**: Files have everything resolution agent needs
4. **Trackable**: Status field tracks resolution progress
5. **Context-Rich**: Includes network topology, routes, positions
6. **Timestamped**: Know when conflict occurred and at which tick

## Next Steps

1. **Create Resolution Agent** in `agents/resolution-agent/`
2. **Implement Resolution Logic** for each conflict type
3. **Add API Endpoints** to apply resolutions (slow down, reroute, delay)
4. **Monitor & Resolve** conflicts in real-time
5. **Measure Effectiveness** by tracking resolved vs unresolved conflicts

Your resolution agent has all the data it needs in the `detected_conflicts/` directory!
