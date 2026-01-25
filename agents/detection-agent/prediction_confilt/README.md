# 🚂 Rail-Mind Conflict Prediction Module

## ML-Based Conflict Prediction for Lombardy Rail Network

This module provides real-time conflict prediction for the Lombardy (Italy) rail region using an **XGBoost + Heuristics Ensemble** approach, integrated with the deterministic conflict detection system.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Why XGBoost + Heuristics Ensemble](#why-xgboost--heuristics-ensemble)
4. [Feature Engineering](#feature-engineering)
5. [Integration with Detection](#integration-with-detection)
6. [Conflict Types](#conflict-types)
7. [Risk Level Visualization](#risk-level-visualization)
8. [API Reference](#api-reference)
9. [Running the System](#running-the-system)
10. [Training the Model](#training-the-model)

---

## 🎯 Overview

### Problem Statement
In railway operations, conflicts occur when multiple trains compete for the same resources (platforms, track segments, time slots). Early prediction of these conflicts enables proactive resolution, reducing delays and improving network efficiency.

### Solution
We implement a **Unified Prediction + Detection System** that:

1. **Simulates train movements** - Trains operate on schedules with realistic delays
2. **Detects conflicts in real-time** - Rule-based detection catches conflicts as they happen
3. **Predicts 10-30 minutes ahead** - ML + Heuristics ensemble runs continuously
4. **Visualizes both** - Orange for predictions, Red for confirmed detections

### Key Innovation: Ensemble Approach

```
┌─────────────────────────────────────────────────────────────┐
│              ENSEMBLE PREDICTION (70/30 split)              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   XGBoost (70%)              Heuristics (30%)               │
│   ┌─────────────┐            ┌─────────────┐                │
│   │ Learns from │            │ Encodes     │                │
│   │ historical  │            │ domain      │                │
│   │ incident    │            │ knowledge   │                │
│   │ data        │            │             │                │
│   └──────┬──────┘            └──────┬──────┘                │
│          │                          │                       │
│          └──────────┬───────────────┘                       │
│                     ▼                                       │
│              Final Prediction                               │
│       (Robust even with limited data)                       │
└─────────────────────────────────────────────────────────────┘
```

### Why XGBoost over Graph Neural Networks?

| Aspect | XGBoost (Chosen) | GNN |
|--------|-----------------|-----|
| **Complexity** | Low | High |
| **Training Data** | Works with ~100 samples | Needs 10K+ samples |
| **Inference Speed** | <1ms per prediction | 10-50ms |
| **Interpretability** | Feature importance available | Black box |
| **Lombardy Scale** | Perfect for 50-100 trains | Overkill |
| **Graph-awareness** | Via engineered features | Native |

**Decision**: For Lombardy's network size (~50-100 simultaneous trains), XGBoost with heuristics provides the best balance of accuracy, speed, and robustness.

---

## 🤝 Why XGBoost + Heuristics Ensemble?

We use an **ensemble approach** combining machine learning with domain knowledge:

### XGBoost Component (70% weight)

**Strengths:**
- Learns patterns from **historical incident data**
- Captures complex non-linear relationships
- Identifies subtle risk factors humans might miss
- Improves with more training data

**Limitations:**
- Limited training data (only ~100 incidents, 7 in Lombardy)
- May overfit to historical patterns
- Cannot predict truly novel situations

### Heuristics Component (30% weight)

**Strengths:**
- Encodes **expert knowledge** about railway operations
- Handles edge cases not in training data
- Provides baseline safety rules
- Always available, even if ML fails

**Example Heuristic Rules:**

| Factor | Risk Contribution | Rationale |
|--------|------------------|-----------|
| Delay > 5 min | +0.15 | Delays cascade to create conflicts |
| Delay > 10 min | +0.25 | Severe delays nearly always cause issues |
| Major hub | +0.10 | Milano Centrale, Brescia have more interactions |
| Rush hour | +0.15 | 7-9 AM, 5-7 PM have peak congestion |
| Weekend | -0.05 | Lower traffic = lower risk |

### Ensemble Combination

```python
final_probability = 0.7 * ml_prediction + 0.3 * heuristic_prediction
```

**Why this works:**
- When both agree → High confidence
- When they disagree → Cautious prediction
- ML captures patterns, heuristics provide guardrails
- Robust even with limited training data

---

## 🔗 Integration with Deterministic Detection

The prediction module integrates with the rule-based detection system:

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED SYSTEM                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐          ┌─────────────────────────────┐  │
│  │   SIMULATION    │─────────>│  NETWORK STATE              │  │
│  │   (Train Data)  │          │  (Real-time positions)      │  │
│  └─────────────────┘          └───────────┬─────────────────┘  │
│                                           │                     │
│           ┌───────────────────────────────┴──────────────────┐ │
│           │                                                  │ │
│           v                                                  v │
│  ┌─────────────────┐                        ┌──────────────────┐│
│  │   PREDICTION    │                        │   DETECTION      ││
│  │   (XGBoost +    │                        │   (Rule-based)   ││
│  │   Heuristics)   │                        │                  ││
│  │   10-30 min     │                        │   Real-time      ││
│  └────────┬────────┘                        └────────┬─────────┘│
│           │                                          │         │
│           │   ┌──────────────────────────────┐       │         │
│           └──>│      UNIFIED API (Port 8002) │<──────┘         │
│               │  - Predictions (Orange)      │                 │
│               │  - Detections (Red)          │                 │
│               │  - Resolutions               │                 │
│               └──────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

### How They Work Together

1. **Prediction** runs every 5 ticks, looking 10-30 minutes ahead
2. **Detection** runs every tick, catching conflicts in real-time
3. Both are combined in the unified API response
4. Frontend shows both with different color coding

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     PREDICTION PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Simulation  │───▶│   Feature    │───▶│   XGBoost    │       │
│  │    State     │    │   Engine     │    │   Predictor  │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                    │               │
│         ▼                   ▼                    ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │    Smart     │    │   Network    │    │   Qdrant     │       │
│  │   Triggers   │    │    Graph     │    │   Memory     │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                        REST API (FastAPI)                        │
├─────────────────────────────────────────────────────────────────┤
│                        WebSocket Stream                          │
├─────────────────────────────────────────────────────────────────┤
│                      Frontend (React + TS)                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Network Map │    │  Alert Feed  │    │   KPI Cards  │       │
│  │  (Colored)   │    │  (Detailed)  │    │  (Summary)   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### Module Structure

```
prediction_confilt/
├── __init__.py           # Module exports
├── config.py             # Configuration settings
├── feature_engine.py     # Feature computation from network state
├── predictor.py          # XGBoost conflict predictor
├── qdrant_memory.py      # Similarity search for historical cases
├── prediction_api.py     # FastAPI service
├── requirements.txt      # Python dependencies
└── models/               # Saved model files (created on training)
```

---

## 🔧 Technology Stack

### Backend (Python)

| Component | Technology | Purpose |
|-----------|------------|---------|
| **ML Model** | XGBoost 2.0 | Conflict classification |
| **Features** | scikit-learn | Feature scaling, preprocessing |
| **Vector DB** | Qdrant | Similarity search for historical cases |
| **Embeddings** | sentence-transformers | Multilingual text embeddings |
| **API** | FastAPI | REST + WebSocket endpoints |
| **Validation** | Pydantic | Request/response validation |

### Frontend (TypeScript/React)

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | React 18 | UI components |
| **Build** | Vite | Fast development server |
| **Styling** | Tailwind CSS | Utility-first CSS |
| **State** | React Query | Server state management |
| **Visualization** | SVG + Canvas | Network map rendering |

---

## 📊 Prediction Strategy

### Smart Triggers (Recommended)

Instead of predicting every second, we trigger predictions when:

```python
SMART_TRIGGERS = {
    "delay_exceeded": train.delay > 120 seconds,
    "approaching_hub": train within 10 min of major station,
    "station_congested": station > 70% capacity,
    "periodic_check": every 2 minutes baseline
}
```

**Benefits:**
- ✅ 80% reduction in ML calls
- ✅ Catches all meaningful events
- ✅ CPU efficient for real-time use

### Continuous Mode (Optional)

For maximum accuracy with smaller networks:

```python
# Predict every simulation minute for every train
continuous_interval_sec = 60
```

---

## 🧮 Feature Engineering

### Feature Categories

#### 1. Train Features
```python
TRAIN_FEATURES = [
    "current_delay_sec",        # Current accumulated delay
    "delay_rate_per_km",        # Delay growth rate
    "distance_to_next_station", # Distance remaining
    "time_to_next_station_sec", # ETA to next stop
    "train_type_encoded",       # IC=4, REG=1, etc.
    "priority_level",           # Scheduling priority
    "remaining_stops",          # Stops until terminus
]
```

#### 2. Station Features (Graph-Aware)
```python
STATION_FEATURES = [
    "current_occupancy",        # trains / max_capacity
    "platform_utilization",     # occupied / total platforms
    "expected_arrivals_15min",  # Incoming trains
    "expected_departures_15min",# Outgoing trains
    "is_hub",                   # Junction station
    "is_major_hub",             # Milano Centrale, etc.
    "historical_congestion",    # Past congestion level
]
```

#### 3. Network Features (Graph-Propagated)
```python
NETWORK_FEATURES = [
    "segment_utilization",      # Trains on same segment
    "upstream_congestion",      # Congestion at previous stations
    "downstream_congestion",    # Congestion at next stations
    "competing_trains_count",   # Trains heading same direction
    "network_load_factor",      # Overall network utilization
]
```

#### 4. Temporal Features
```python
TEMPORAL_FEATURES = [
    "hour_of_day",              # 0-23
    "day_of_week",              # 0=Monday
    "is_peak_hour",             # Morning/evening rush
    "is_weekend",               # Saturday/Sunday
    "is_holiday",               # Italian holidays
]
```

#### 5. Interaction Features
```python
INTERACTION_FEATURES = [
    "delay_congestion_interaction",  # delay × congestion
    "hub_peak_interaction",          # hub × peak_hour
    "priority_station_interaction",  # priority × station_type
]
```

---

## ⚠️ Conflict Types

| Type | Description | Key Indicators |
|------|-------------|----------------|
| `platform_conflict` | Multiple trains need same platform | High platform utilization |
| `track_conflict` | Two trains on same segment | Segment utilization > 0 |
| `headway_violation` | Minimum headway not maintained | Competing trains + delay |
| `capacity_exceeded` | Station over capacity | Occupancy > 100% |
| `schedule_deviation` | Significant timetable drift | Delay > 5 minutes |
| `cascading_delay` | Delay propagating through network | Upstream congestion + delay |

---

## 🎨 Risk Level Visualization

### Color Coding

```
┌────────────────────────────────────────────┐
│  🟢 GREEN   Safe           prob < 0.3      │
│  🟡 YELLOW  Low Risk       0.3 ≤ prob < 0.5│
│  🟠 ORANGE  High Risk      0.5 ≤ prob < 0.8│
│  🔴 RED     Critical       prob ≥ 0.8      │
└────────────────────────────────────────────┘
```

### Visual Effects

- **Trains**: Colored dots with glow effect for non-safe levels
- **Stations**: Color changes when trains approach with risk
- **Pulsing**: Animation for high-risk and critical items
- **Tooltips**: Hover for probability and contributing factors

### Alert Panel

```
┌────────────────────────────────────────┐
│ 🟠 EC_150 - Platform Conflict Predicted│
│ Location: CHIASSO                      │
│ Time: In 8 minutes (12:02)             │
│ Probability: 78%                       │
│ Cause: 3 trains scheduled, 4 min delay │
│                                        │
│ Similar cases: 5 found                 │
│ Typical resolution: Delay 1 train      │
│                                        │
│ [VIEW DETAILS] [PREPARE RESOLUTION]    │
└────────────────────────────────────────┘
```

---

## 🔌 API Reference

### REST Endpoints

#### `POST /api/predict/batch`
Predict conflicts for entire network.

**Request:**
```json
{
  "simulation_time": "2026-01-25T14:30:00",
  "trains": {
    "IC_1539": {
      "train_id": "IC_1539",
      "train_type": "intercity",
      "current_station": "MILANO CENTRALE",
      "next_station": "MONZA",
      "current_delay_sec": 180,
      ...
    }
  },
  "stations": {...}
}
```

**Response:**
```json
{
  "timestamp": "2026-01-25T14:30:00",
  "predictions": [
    {
      "train_id": "IC_1539",
      "probability": 0.78,
      "risk_level": "high_risk",
      "color": "#f97316",
      "predicted_conflict_type": "platform_conflict",
      "predicted_time": "2026-01-25T14:38:00",
      "predicted_location": "CHIASSO",
      "contributing_factors": ["3 trains competing", "4 min delay"],
      "confidence": 0.85
    }
  ],
  "network_risk_score": 0.42,
  "high_risk_trains": ["IC_1539"],
  "critical_trains": [],
  "recommended_actions": ["Monitor IC_1539 approaching CHIASSO"]
}
```

#### `POST /api/memory/search`
Search for similar historical incidents.

#### `GET /api/demo/simulate`
Demo endpoint using Lombardy train data.

### WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/predictions');
ws.onmessage = (event) => {
  const batch = JSON.parse(event.data);
  updateMap(batch.predictions);
};
```

---

## 📦 Installation

### Backend

```bash
cd agents/detection-agent/prediction_confilt

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Qdrant (Optional)

```bash
# Using Docker
docker run -p 6333:6333 qdrant/qdrant
```

### Frontend

```bash
cd frontend
npm install
# or: bun install
```

---

## 🚀 Usage

### Start API Server

```bash
cd agents/detection-agent/prediction_confilt
python -m uvicorn prediction_api:app --reload --port 8001
```

### Start Frontend

```bash
cd frontend
npm run dev
```

### Access

- **API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **Frontend**: http://localhost:5173

---

## ⚙️ Configuration

### Environment Variables

```bash
# Frontend (.env)
VITE_PREDICTION_API_URL=http://localhost:8001
VITE_PREDICTION_WS_URL=ws://localhost:8001/ws/predictions
```

### Python Configuration

Edit `config.py`:

```python
# Prediction strategy
prediction_config.strategy = "smart"  # or "continuous"
prediction_config.prediction_horizon_min = 15
prediction_config.prediction_horizon_max = 30

# Smart trigger thresholds
prediction_config.trigger_delay_threshold_sec = 120
prediction_config.trigger_congestion_threshold = 0.7

# Risk thresholds
conflict_thresholds.safe_threshold = 0.3
conflict_thresholds.low_risk_threshold = 0.5
conflict_thresholds.high_risk_threshold = 0.8

# Qdrant
qdrant_config.mode = "local"  # or "cloud"
qdrant_config.host = "localhost"
qdrant_config.port = 6333
```

---

## 📈 Model Training

The predictor includes both trained ML mode and heuristic fallback:

```python
from prediction_confilt import ConflictPredictor

# Initialize predictor
predictor = ConflictPredictor()

# Train with historical data (if available)
X_train, y_train = load_training_data()
metrics = predictor.train(X_train, y_train)

# Save model
predictor.save_model()

# Model will auto-load on next initialization
```

---

## 🔮 Future Enhancements

1. **Graph Neural Network Option**: For larger networks (>200 trains)
2. **Reinforcement Learning**: For automated resolution suggestions
3. **Ensemble Methods**: Combine XGBoost with neural approaches
4. **Real-time Model Updates**: Online learning from new incidents

---

## 📄 License

Part of the Rail-Mind project for Lombardy rail network optimization.

---

## 👥 Contributors

Detection Agent Team - Conflict Prediction Module
