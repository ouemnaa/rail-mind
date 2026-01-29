# Backend

This directory contains the backend integration engine that combines ML-based conflict prediction with deterministic detection for real-time railway conflict management, plus integration with the Resolution Orchestrator for AI-powered conflict resolution.

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
    ├── conflict_results/       # Manual snapshots
    │   └── orchestrator_outputs/  # Resolution orchestrator results
    └── tests/                  # Integration tests
        └── test_resolve_endpoint.py
```

## Quick Start

```powershell
# From rail-mind root directory
cd c:\rail-mind

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Set required environment variables (for LLM judge)
$env:GROQ_API_KEY = "your-groq-api-key"

# Start API server
python backend\integration\unified_api.py

# Server runs on: http://localhost:8002
```

## Environment Variables

| Variable             | Required       | Description                                   |
| -------------------- | -------------- | --------------------------------------------- |
| `GROQ_API_KEY`       | For LLM judge  | Groq API key for LLM-based resolution ranking |
| `OPENROUTER_API_KEY` | Alternative    | OpenRouter API key (alternative to Groq)      |
| `QDRANT_URL`         | For Hybrid RAG | Qdrant vector DB URL                          |
| `QDRANT_API_KEY`     | For Hybrid RAG | Qdrant API key                                |

## API Endpoints

### Simulation Endpoints

| Endpoint                | Method | Description                         |
| ----------------------- | ------ | ----------------------------------- |
| `/api/simulation/tick`  | GET    | Advance simulation by 1 minute      |
| `/api/simulation/state` | GET    | Get current state without advancing |
| `/api/simulation/start` | POST   | Reset simulation                    |
| `/api/trains`           | GET    | Get all train positions             |
| `/api/stations`         | GET    | Get all stations                    |

### Conflict Detection Endpoints

| Endpoint                         | Method | Description                    |
| -------------------------------- | ------ | ------------------------------ |
| `/api/conflicts/save`            | POST   | Save current conflicts to file |
| `/api/conflicts/list`            | GET    | List saved conflict files      |
| `/api/conflicts/latest`          | GET    | Get latest saved conflicts     |
| `/api/conflicts/load/{filename}` | GET    | Load specific conflict file    |

### Resolution Endpoints (NEW)

| Endpoint                                   | Method | Description                       |
| ------------------------------------------ | ------ | --------------------------------- |
| `/api/conflicts/resolve`                   | POST   | **Run Resolution Orchestrator**   |
| `/api/conflicts/resolve/outputs`           | GET    | List orchestrator output files    |
| `/api/conflicts/resolve/output/{filename}` | GET    | Load specific orchestrator output |

### Resolution API Usage

```bash
# Resolve a conflict directly
curl -X POST http://localhost:8002/api/conflicts/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "conflict": {
      "conflict_id": "CONF-001",
      "conflict_type": "headway",
      "station_ids": ["MILANO CENTRALE", "PAVIA"],
      "train_ids": ["REG_001", "FR_002"],
      "severity": 0.75
    },
    "timeout": 60
  }'

# Resolve from a saved file
curl -X POST http://localhost:8002/api/conflicts/resolve \
  -H "Content-Type: application/json" \
  -d '{"filename": "conflicts_20260129_100000.json"}'

# Pass a detection (auto-converted)
curl -X POST http://localhost:8002/api/conflicts/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "detection": {
      "conflict_id": "DET-001",
      "conflict_type": "edge_capacity_overflow",
      "location": "MILANO--PAVIA",
      "involved_trains": ["REG_001", "FR_002"],
      "severity": "high"
    }
  }'

# With API key in header
curl -X POST http://localhost:8002/api/conflicts/resolve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_GROQ_API_KEY" \
  -d '{"conflict": {...}}'
```

### Resolution Response Format

```json
{
  "success": true,
  "filepath": "conflict_results/orchestrator_outputs/orchestrator_CONF-001_20260129_100000.json",
  "filename": "orchestrator_CONF-001_20260129_100000.json",
  "conflict_id": "CONF-001",
  "output": {
    "status": "ok",
    "total_execution_ms": 5000,
    "agents": {
      "hybrid_rag": {"status": "ok", "execution_ms": 100, "normalized_count": 3},
      "mathematical": {"status": "ok", "execution_ms": 3000, "normalized_count": 1}
    },
    "llm_judge": {
      "status": "ok",
      "execution_ms": 1500,
      "ranked_resolutions": [
        {"rank": 1, "resolution_id": "...", "overall_score": 85, ...}
      ]
    }
  }
}
```

## Dependencies

The integration engine imports ML modules from:

- `agents/detection-agent/prediction_confilt/` - ML prediction (XGBoost)
- `agents/detection-agent/deterministic-detection/` - Rule-based detection
- `agents/resolution-agent/resolution_orchestrator.py` - Resolution orchestrator

## Data Sources

- **Input**: `creating-context/lombardy_simulation_data.json`
- **Output**: `backend/integration/detected_conflicts/detected_conflicts.json`
- **Resolutions**: `backend/integration/conflict_results/orchestrator_outputs/`

## Color Coding (Frontend)

- 🟢 **Green**: Safe (no risk)
- 🟡 **Yellow**: Low risk (probability < 0.5)
- 🟠 **Orange**: High risk (probability >= 0.5) - ML Prediction
- 🔴 **Red**: Active conflict (detected) - Rule Detection

## Testing

```powershell
# Run backend tests
cd backend/integration
pytest tests/ -v
```

## See Also

- [Conflict Workflow](integration/CONFLICT_WORKFLOW.md)
- [Detected Conflicts](integration/detected_conflicts/README.md)
- [Detection Agent](../agents/detection-agent/README.md)
- [Resolution Agent](../agents/resolution-agent/README.md)
