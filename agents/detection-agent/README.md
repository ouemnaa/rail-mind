# 🔍 Detection Agent

The Detection Agent is responsible for identifying and predicting conflicts in the Lombardy rail network using machine learning.

## Components

### 1. Conflict Prediction Module (`prediction_confilt/`)

ML-based conflict prediction system that:
- **Continuously monitors** train positions and network state
- **Predicts conflicts** 10-30 minutes ahead using XGBoost
- **Finds similar cases** in operational memory via Qdrant
- **Visualizes risk levels** with color-coded trains/stations

See [prediction_confilt/README.md](prediction_confilt/README.md) for detailed documentation.

## Architecture Overview

```
Detection Agent
├── prediction_confilt/        # ML Conflict Prediction
│   ├── predictor.py           # XGBoost classifier
│   ├── feature_engine.py      # Feature engineering
│   ├── qdrant_memory.py       # Similarity search
│   └── prediction_api.py      # REST/WebSocket API
│
└── [Future modules]
    ├── anomaly_detection/     # Anomaly detection
    └── pattern_recognition/   # Historical patterns
```

## Quick Start

```bash
# Install dependencies (from rail-mind root directory)
cd rail-mind
pip install -r requirements.txt

# Start Unified API Server (Prediction + Detection + Simulation)
python .venv/Scripts/python.exe agents/detection-agent/integration/unified_api.py
# Or from Windows PowerShell:
.venv\Scripts\python.exe agents\detection-agent\integration\unified_api.py

# Server runs on: http://localhost:8002

# Test endpoints
curl http://localhost:8002/api/simulation/tick
curl http://localhost:8002/api/simulation/state
```

## Integration Points

- **Simulator Agent**: Receives network state updates
- **Resolution Agent**: Sends conflict predictions for resolution
- **Frontend**: Real-time visualization via WebSocket

## Key Features

- 🎯 **Smart Triggers**: Predicts only when meaningful events occur
- 🌐 **Graph-Aware**: Features capture network topology effects
- 🔍 **Similarity Search**: Finds relevant historical cases
- 📊 **Risk Levels**: Green → Yellow → Orange → Red color coding
- ⚡ **Real-time**: <1ms prediction latency with XGBoost

## Technologies

- **ML**: XGBoost, scikit-learn
- **Vector DB**: Qdrant with sentence-transformers
- **API**: FastAPI with WebSocket support
- **Visualization**: React + TypeScript frontend
