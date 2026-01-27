# Backend

This directory contains the backend integration engine that combines ML-based conflict prediction with deterministic detection for real-time railway conflict management.

## Structure

```
backend/
└── integration/
    ├── unified_api.py          # FastAPI server (PORT 8002)
    ├── integration_engine.py   # Core simulation and detection logic
    ├── __init__.py             # Module exports
    ├── CONFLICT_WORKFLOW.md    # Workflow documentation
    ├── detected_conflicts/     # Auto-saved conflict files
    │   ├── README.md
    │   └── detected_conflicts.json
    └── conflict_results/       # Manual snapshots
```

## Quick Start

```powershell
# From rail-mind root directory
cd c:\Users\dongm\OneDrive\Desktop\rail-mind

# Start API server
.venv\Scripts\python.exe backend\integration\unified_api.py

# Server runs on: http://localhost:8002
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/simulation/tick` | GET | Advance simulation by 1 minute |
| `/api/simulation/state` | GET | Get current state without advancing |
| `/api/simulation/start` | POST | Reset simulation |
| `/api/trains` | GET | Get all train positions |
| `/api/stations` | GET | Get all stations |
| `/api/conflicts/save` | POST | Save current conflicts to file |
| `/api/conflicts/latest` | GET | Get latest saved conflicts |

## Dependencies

The integration engine imports ML modules from:
- `agents/detection-agent/prediction_confilt/` - ML prediction (XGBoost)
- `agents/detection-agent/deterministic-detection/` - Rule-based detection

## Data Sources

- **Input**: `creating-context/lombardy_simulation_data.json`
- **Output**: `backend/integration/detected_conflicts/detected_conflicts.json`

## Color Coding (Frontend)

- 🟢 **Green**: Safe (no risk)
- 🟡 **Yellow**: Low risk (probability < 0.5)
- 🟠 **Orange**: High risk (probability >= 0.5) - ML Prediction
- 🔴 **Red**: Active conflict (detected) - Rule Detection

## See Also

- [Conflict Workflow](integration/CONFLICT_WORKFLOW.md)
- [Detected Conflicts](integration/detected_conflicts/README.md)
- [Detection Agent](../agents/detection-agent/README.md)
