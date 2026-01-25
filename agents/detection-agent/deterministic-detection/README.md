# RailMind Detection Layer

**Deterministic, rule-based conflict detection for railway networks.**

This module detects operational conflicts in real-time without machine learning. It evaluates network state against predefined rules and emits structured conflict events for downstream consumption.

---

## Quick Start

The fastest way to run the simulation is using the local launcher:

```bash
# Run a standard simulation
python run_local.py --ticks 100 --seed 42

# Run a stress test (recommended for seeing more conflicts)
python run_local.py --scenario stress_test --ticks 100

# Run in real-time mode (simulates 30s delay between 10s ticks)
python run_local.py --realtime --ticks 50
```

---

## Verification & Testing

To ensure the detection engine and your data environment are working correctly:

### 1. Functional Smoke Test
Verify that detection rules (like platform overflow) are triggering correctly using a controlled scenario:
```bash
python smoke_test.py
```
*Expected: Minimal output confirming detection of platform overflow and simultaneous arrivals.*

### 2. Data Integrity Check
Verify that the `lombardy_simulation_data.json` is loaded correctly and check for any initial static capacity violations:
```bash
python check_data.py
```

### 3. Full Simulation Verification
Run a high-load scenario to confirm the engine handles large-scale data and outputs results:
```bash
python run_local.py --scenario stress_test --ticks 50
```
Check the output in `detection/output/conflicts.json`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Detection Layer                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  Simulator   │───▶│ StateTracker │───▶│   DetectionEngine    │  │
│  │              │    │              │    │                      │  │
│  │ Time-stepped │    │ Maintains:   │    │ Evaluates 15 rules   │  │
│  │ train/network│    │ - Trains     │    │ across 4 levels:     │  │
│  │ updates      │    │ - Stations   │    │ - Edge               │  │
│  │              │    │ - Edges      │    │ - Station            │  │
│  │              │    │ - Occupancy  │    │ - Train              │  │
│  └──────────────┘    └──────────────┘    │ - Network            │  │
│                                          └──────────┬───────────┘  │
│                                                     │              │
│                                          ┌──────────▼───────────┐  │
│                                          │   ConflictEmitter    │  │
│                                          │                      │  │
│                                          │ Outputs structured   │  │
│                                          │ JSON conflict events │  │
│                                          └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Module Structure

| File               | Purpose                                                |
| ------------------ | ------------------------------------------------------ |
| `models.py`        | Data classes for Station, RailSegment, Train, Conflict |
| `state_tracker.py` | Real-time network state management                     |
| `rules.py`         | 15 conflict detection rules                            |
| `engine.py`        | DetectionEngine orchestrator + ConflictEmitter         |
| `simulator.py`     | Mock real-time simulator for testing                   |
| `run_detection.py` | CLI entry point                                        |

---

## Conflict Detection Rules

### Edge-Level (4 rules)

| Rule ID    | Name                        | Trigger Condition                                    |
| ---------- | --------------------------- | ---------------------------------------------------- |
| `EDGE_001` | Edge Capacity Overflow      | Trains on edge > edge capacity                       |
| `EDGE_002` | Headway Violation           | Time between trains < minimum headway                |
| `EDGE_003` | Opposite Direction Conflict | Trains traveling opposite directions on single-track |
| `EDGE_004` | Speed Incompatibility       | Mixed traffic with speed variance > 40 km/h          |

### Station-Level (4 rules)

| Rule ID   | Name                          | Trigger Condition                         |
| --------- | ----------------------------- | ----------------------------------------- |
| `STN_001` | Platform Overflow             | Trains at station > platform capacity     |
| `STN_002` | Simultaneous Arrival Overflow | Concurrent arrivals > available platforms |
| `STN_003` | Dwell Time Violation          | Dwell time < minimum or > maximum allowed |
| `STN_004` | Blocking Behavior Violation   | Train at station > 30 min (blocking)      |

### Train-Level (3 rules)

| Rule ID   | Name                   | Trigger Condition                           |
| --------- | ---------------------- | ------------------------------------------- |
| `TRN_001` | Priority Inversion     | Lower priority train delays higher priority |
| `TRN_002` | Delay Propagation Risk | Delayed train may cause cascade             |
| `TRN_003` | Unauthorized Hold      | Train holding beyond authorized limits      |

### Network-Level (4 rules)

| Rule ID   | Name                  | Trigger Condition                        |
| --------- | --------------------- | ---------------------------------------- |
| `NET_001` | Cascading Congestion  | Adjacent nodes/edges all congested       |
| `NET_002` | Hub Saturation        | Major hub station at >80% capacity       |
| `NET_003` | High-Risk Edge Stress | Risk-flagged edge at capacity            |
| `NET_004` | Regional Overload     | Regional train density exceeds threshold |

---

## Conflict Event Schema

```json
{
  "conflict_id": "CNF-1734567890123-001",
  "timestamp": "2024-12-18T15:30:00.000Z",
  "conflict_type": "EDGE_CAPACITY_OVERFLOW",
  "severity": "high",
  "location": {
    "node_id": null,
    "edge_id": "EDGE_Milano_Centrale_Monza"
  },
  "involved_trains": ["FR9601", "REG2045"],
  "rule_triggered": "EDGE_001",
  "explanation": "Edge Milano_Centrale→Monza has 3 trains but capacity is 2",
  "metadata": {
    "current_load": 3,
    "capacity": 2,
    "excess": 1
  }
}
```

### Conflict Types

- `EDGE_CAPACITY_OVERFLOW`
- `HEADWAY_VIOLATION`
- `OPPOSITE_DIRECTION_CONFLICT`
- `SPEED_INCOMPATIBILITY`
- `SAFETY_VIOLATION`
- `PLATFORM_OVERFLOW`
- `SIMULTANEOUS_ARRIVAL_OVERFLOW`
- `DWELL_TIME_VIOLATION`
- `BLOCKING_BEHAVIOR_VIOLATION`
- `PRIORITY_INVERSION`
- `DELAY_PROPAGATION_RISK`
- `UNAUTHORIZED_HOLD`
- `CASCADING_CONGESTION`
- `HUB_SATURATION`
- `HIGH_RISK_EDGE_STRESS`
- `REGIONAL_OVERLOAD`

### Severity Levels

| Level      | Description                                  |
| ---------- | -------------------------------------------- |
| `critical` | Immediate safety concern or major disruption |
| `high`     | Significant operational impact               |
| `medium`   | Moderate impact, action recommended          |
| `low`      | Minor issue, advisory only                   |

---

## Simulation Scenarios

| Scenario      | Description         | Train Density | Delay Rate |
| ------------- | ------------------- | ------------- | ---------- |
| `normal`      | Regular operations  | Medium        | Low        |
| `rush_hour`   | Peak traffic        | High          | Medium     |
| `disruption`  | Incident simulation | Medium        | High       |
| `stress_test` | Maximum load        | Maximum       | High       |

---

## CLI Reference

```
python -m detection.run_detection [OPTIONS]

Options:
  -d, --data PATH       Path to simulation data JSON
                        (default: creating-context/lombardy_simulation_data.json)

  -s, --scenario NAME   Simulation scenario
                        Choices: normal, rush_hour, disruption, stress_test
                        (default: normal)

  -t, --ticks N         Number of simulation ticks
                        (default: 100)

  -r, --realtime        Run simulation in realtime mode
                        (sleeps 30s between 10s simulation ticks)

  -o, --output PATH     Output path for conflict log
                        (default: detection/output/conflicts.json)

  --seed N              Random seed for reproducibility

  -q, --quiet           Suppress progress output
```

---

## Programmatic Usage

```python
from pathlib import Path
from detection.state_tracker import StateTracker
from detection.engine import DetectionEngine
from detection.simulator import MockSimulator, SimulationConfig, ScenarioType

# Setup
tracker = StateTracker()
tracker.load_from_json(your_data_dict)

engine = DetectionEngine(
    state_tracker=tracker,
    output_file="output/conflicts.json"
)

config = SimulationConfig(
    max_ticks=100,
    scenario=ScenarioType.RUSH_HOUR,
    random_seed=42
)

simulator = MockSimulator(tracker, config)
simulator.initialize_trains(20)

# Run
for changes in simulator.run():
    conflicts = engine.tick()

    for conflict in conflicts:
        print(f"[{conflict.severity.value}] {conflict.explanation}")

# Results
stats = engine.get_statistics()
print(f"Total conflicts: {stats['total_conflicts']}")
```

---

## Run locally from this folder

If you prefer to run the detection runner while located in this folder, use the provided `run_local.py` launcher. It will add the repository root to `sys.path` and forward CLI args to the detection module.

```powershell
# from this directory
# activate your venv if needed
python run_local.py --ticks 100 --seed 42
```

Or set `PYTHONPATH` to the repo root and run the module directly:

```powershell
$env:PYTHONPATH = "C:\\vectors-in-orbit"
python -m detection.run_detection --ticks 100 --seed 42
```

---

## Output Files

After running, the following files are created in `detection/output/`:

| File                      | Content                               |
| ------------------------- | ------------------------------------- |
| `conflicts.json`          | Array of all detected conflict events |
| `simulation_summary.json` | Run metadata and statistics           |

---

## Design Principles

1. **Deterministic** — Same input always produces same output (with seed)
2. **Rule-based** — No ML, no probabilistic models
3. **Detection only** — Does not resolve conflicts or optimize schedules
4. **Modular** — Each component can be tested/replaced independently
5. **Streaming** — Processes time-stepped updates, not batch data

---

## Non-Goals

This module explicitly does NOT:

- Resolve detected conflicts
- Optimize train schedules
- Use machine learning
- Access the vector database
- Make probabilistic predictions

These concerns are handled by other layers in the RailMind system.
