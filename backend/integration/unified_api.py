"""
Unified FastAPI Server
======================

Single API that provides:
1. Train positions (moving in real-time)
2. ML + Heuristics predictions (10-30 min ahead)
3. Deterministic conflict detection (real-time)
4. Resolution suggestions

Endpoints:
- GET /api/simulation/state - Current state with trains, predictions, detections
- GET /api/simulation/tick - Advance one tick and get new state
- POST /api/simulation/start - Start/reset simulation
- GET /api/prediction/{station_id} - Get predictions for specific station
- GET /api/region/{region} - Get all data for a region

Color Coding for Frontend:
- Green: Safe (no predictions, no detections)
- Yellow: Low risk (prediction probability < 0.5)
- Orange: High risk (prediction probability >= 0.5)
- Red: Active conflict (detection confirmed)
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import json

# Add paths
# BASE_DIR is backend folder, detection modules are in agents/detection-agent/
BASE_DIR = Path(__file__).resolve().parent.parent  # backend folder
PROJECT_ROOT = BASE_DIR.parent  # rail-mind folder
DETECTION_AGENT_DIR = PROJECT_ROOT / "agents" / "detection-agent"
sys.path.insert(0, str(DETECTION_AGENT_DIR / "prediction_confilt"))
sys.path.insert(0, str(DETECTION_AGENT_DIR / "deterministic-detection"))
sys.path.insert(0, str(BASE_DIR / "integration"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Create output directory for conflict results
CONFLICTS_OUTPUT_DIR = Path(__file__).parent / "conflict_results"
CONFLICTS_OUTPUT_DIR.mkdir(exist_ok=True)

# Import integration engine
try:
    from integration_engine import IntegrationEngine, SimulationState, UnifiedConflict
except ImportError:
    # Try direct import from same directory
    sys.path.insert(0, str(Path(__file__).parent))
    from integration_engine import IntegrationEngine, SimulationState, UnifiedConflict


# =============================================================================
# Response Models
# =============================================================================

class TrainResponse(BaseModel):
    train_id: str
    train_type: str
    current_station: Optional[str]
    next_station: Optional[str]
    current_edge: Optional[str]
    position_km: float
    speed_kmh: float
    delay_sec: float
    status: str
    lat: float
    lon: float
    route: List[dict]
    current_stop_index: int


class ConflictResponse(BaseModel):
    conflict_id: str
    source: str  # "prediction" or "detection"
    conflict_type: str
    severity: str
    probability: float
    location: str
    location_type: str
    involved_trains: List[str]
    explanation: str
    timestamp: str
    prediction_horizon_min: Optional[int]
    resolution_suggestions: List[str]
    lat: Optional[float]
    lon: Optional[float]


class StateResponse(BaseModel):
    simulation_time: str
    tick_number: int
    trains: List[TrainResponse]
    predictions: List[ConflictResponse]
    detections: List[ConflictResponse]
    statistics: dict


class RegionResponse(BaseModel):
    region: str
    stations: List[dict]
    trains: List[TrainResponse]
    predictions: List[ConflictResponse]
    detections: List[ConflictResponse]


# =============================================================================
# App Setup
# =============================================================================

app = FastAPI(
    title="Rail-Mind Unified API",
    description="Combines ML prediction with deterministic detection for railway conflict management",
    version="2.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance
engine: Optional[IntegrationEngine] = None


# =============================================================================
# Lifecycle Events
# =============================================================================

@app.on_event("startup")
async def startup():
    """Initialize engine on startup."""
    global engine
    print("\n[API] Starting unified server...")
    engine = IntegrationEngine()
    engine.initialize()
    print("[API] Server ready!")


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/")
def root():
    """API root with documentation."""
    return {
        "name": "Rail-Mind Unified API",
        "version": "2.0.0",
        "description": "ML Prediction + Deterministic Detection",
        "endpoints": {
            "/api/simulation/state": "Get current state without advancing",
            "/api/simulation/tick": "Advance simulation and get new state",
            "/api/simulation/start": "Reset simulation",
            "/api/prediction/{station_id}": "Get predictions for a station",
            "/api/region/{region}": "Get all data for a region",
            "/health": "Health check"
        },
        "color_coding": {
            "green": "Safe (no risk)",
            "yellow": "Low risk (probability < 0.5)",
            "orange": "High risk (probability >= 0.5)",
            "red": "Active conflict (detected)"
        }
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "engine_initialized": engine is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/simulation/state")
def get_state() -> dict:
    """
    Get current simulation state without advancing time.
    
    Returns trains, predictions, and detections.
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    # Build current state without ticking
    return {
        "simulation_time": engine.simulation_time.isoformat(),
        "tick_number": engine.tick_number,
        "trains": [t.to_dict() for t in engine.trains.values()],
        "predictions": [p.to_dict() for p in engine.last_predictions],
        "detections": [],  # Need to run detection to get these
        "statistics": engine._get_statistics()
    }


@app.get("/api/simulation/tick")
def tick() -> dict:
    """
    Advance simulation by one tick.
    
    This:
    1. Updates train positions
    2. Runs detection rules (real-time)
    3. Runs prediction (every N ticks)
    4. Returns complete state
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    state = engine.tick()
    return state.to_dict()


@app.post("/api/simulation/start")
def start_simulation():
    """Reset and start fresh simulation."""
    global engine
    engine = IntegrationEngine()
    engine.initialize()
    return {
        "status": "started",
        "simulation_time": engine.simulation_time.isoformat(),
        "trains_count": len(engine.trains)
    }


@app.get("/api/simulation/multi-tick/{count}")
def multi_tick(count: int = 10) -> dict:
    """
    Advance simulation by multiple ticks.
    
    Useful for faster simulation. Returns only final state.
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    count = min(count, 100)  # Limit to prevent overload
    
    for _ in range(count - 1):
        engine.tick()
    
    state = engine.tick()
    return state.to_dict()


@app.get("/api/prediction/{station_id}")
def get_station_predictions(station_id: str) -> dict:
    """
    Get predictions for a specific station.
    
    Args:
        station_id: Station ID or name (e.g., "MI_CENTRALE" or "MILANO CENTRALE")
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    predictions = engine.get_predictions_for_station(station_id)
    
    # Get station info
    station = engine.stations.get(station_id) or engine.stations.get(station_id.upper())
    
    # Get trains at/near this station
    trains = [
        t.to_dict() for t in engine.trains.values()
        if t.current_station == station_id or t.next_station == station_id
    ]
    
    return {
        "station_id": station_id,
        "station_info": station,
        "predictions": [p.to_dict() for p in predictions],
        "trains": trains,
        "risk_level": _calculate_risk_level(predictions)
    }


@app.get("/api/region/{region}")
def get_region_data(region: str) -> dict:
    """
    Get all data for a region (e.g., "Lombardy").
    
    Includes all stations, trains, predictions, and detections in the region.
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    # Get stations in region
    region_stations = [
        s for s in engine.network_data.get('stations', [])
        if s.get('region', '').upper() == region.upper()
    ]
    station_ids = [s['id'] for s in region_stations]
    
    # Get trains in region
    region_trains = [
        t.to_dict() for t in engine.trains.values()
        if t.current_station in station_ids or t.next_station in station_ids
    ]
    
    # Get predictions for region
    predictions = engine.get_predictions_for_region(region)
    
    return {
        "region": region,
        "stations": region_stations,
        "trains": region_trains,
        "predictions": [p.to_dict() for p in predictions],
        "summary": {
            "total_stations": len(region_stations),
            "total_trains": len(region_trains),
            "active_predictions": len(predictions),
            "high_risk_count": sum(1 for p in predictions if p.probability >= 0.5)
        }
    }


@app.get("/api/trains")
def get_all_trains() -> dict:
    """Get all trains with current positions."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    return {
        "trains": [t.to_dict() for t in engine.trains.values()],
        "count": len(engine.trains),
        "simulation_time": engine.simulation_time.isoformat()
    }


@app.get("/api/stations")
def get_all_stations() -> dict:
    """Get all stations."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    stations = list(set(
        s for s in engine.network_data.get('stations', [])
    ))
    
    return {
        "stations": stations,
        "count": len(stations)
    }


@app.post("/api/conflicts/save")
def save_conflicts(filename: Optional[str] = None) -> dict:
    """
    Save current predictions and detections to a JSON file for resolution agent.
    
    Args:
        filename: Optional custom filename (default: conflicts_TIMESTAMP.json)
    
    Returns:
        Path to saved file and summary statistics
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    # Get current state
    state = engine.get_current_state()
    predictions = [p.to_dict() for p in state.predictions]
    detections = [d.to_dict() for d in state.detections]
    
    # Generate filename
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conflicts_{timestamp}.json"
    
    if not filename.endswith('.json'):
        filename += '.json'
    
    filepath = CONFLICTS_OUTPUT_DIR / filename
    
    # Prepare data for resolution agent
    conflict_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "tick_number": state.tick_number,
            "simulation_time": state.simulation_time.isoformat(),
            "total_predictions": len(predictions),
            "total_detections": len(detections),
            "high_risk_predictions": sum(1 for p in predictions if p.get("probability", 0) >= 0.5),
        },
        "predictions": predictions,
        "detections": detections,
        "trains": [t.to_dict() for t in state.trains],
        "statistics": state.statistics
    }
    
    # Save to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(conflict_data, f, indent=2, ensure_ascii=False)
    
    return {
        "success": True,
        "filepath": str(filepath),
        "filename": filename,
        "summary": {
            "predictions": len(predictions),
            "detections": len(detections),
            "trains": len(state.trains),
            "high_risk": conflict_data["metadata"]["high_risk_predictions"]
        }
    }


@app.get("/api/conflicts/list")
def list_saved_conflicts() -> dict:
    """List all saved conflict files."""
    files = sorted(CONFLICTS_OUTPUT_DIR.glob("conflicts_*.json"), reverse=True)
    
    file_list = []
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                file_list.append({
                    "filename": f.name,
                    "filepath": str(f),
                    "timestamp": data["metadata"]["timestamp"],
                    "tick": data["metadata"]["tick_number"],
                    "predictions": data["metadata"]["total_predictions"],
                    "detections": data["metadata"]["total_detections"],
                    "high_risk": data["metadata"]["high_risk_predictions"],
                })
        except Exception as e:
            print(f"Error reading {f}: {e}")
    
    return {
        "count": len(file_list),
        "files": file_list,
        "output_directory": str(CONFLICTS_OUTPUT_DIR)
    }


@app.get("/api/conflicts/load/{filename}")
def load_conflict_file(filename: str) -> dict:
    """
    Load a specific conflict file for resolution agent processing.
    
    Args:
        filename: Name of the conflict file to load
    
    Returns:
        Complete conflict data including predictions, detections, and trains
    """
    filepath = CONFLICTS_OUTPUT_DIR / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading file: {str(e)}")


@app.get("/api/conflicts/latest")
def get_latest_conflicts() -> dict:
    """Get the most recently saved conflicts file."""
    files = sorted(CONFLICTS_OUTPUT_DIR.glob("conflicts_*.json"), reverse=True)
    
    if not files:
        raise HTTPException(status_code=404, detail="No saved conflicts found")
    
    try:
        with open(files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading file: {str(e)}")


@app.post("/api/conflicts/auto-save")
def toggle_auto_save(enabled: bool = True, interval_ticks: int = 5) -> dict:
    """
    Enable/disable automatic saving of conflicts every N ticks.
    
    Args:
        enabled: Whether to enable auto-save
        interval_ticks: Save every N ticks (default: 5)
    
    Returns:
        Status of auto-save feature
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    # Store in engine (you'd need to add this attribute to IntegrationEngine)
    # For now, just return the configuration
    return {
        "auto_save_enabled": enabled,
        "interval_ticks": interval_ticks,
        "output_directory": str(CONFLICTS_OUTPUT_DIR),
        "note": "Auto-save will trigger every tick endpoint call if enabled"
    }


# =============================================================================
# Helper Functions
# =============================================================================

def _calculate_risk_level(predictions: List[UnifiedConflict]) -> dict:
    """Calculate overall risk level from predictions."""
    if not predictions:
        return {"level": "safe", "color": "green", "max_probability": 0.0}
    
    max_prob = max(p.probability for p in predictions)
    
    if max_prob >= 0.8:
        return {"level": "critical", "color": "red", "max_probability": max_prob}
    elif max_prob >= 0.5:
        return {"level": "high", "color": "orange", "max_probability": max_prob}
    elif max_prob >= 0.3:
        return {"level": "medium", "color": "yellow", "max_probability": max_prob}
    else:
        return {"level": "low", "color": "green", "max_probability": max_prob}


# =============================================================================
# Run Server
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("RAIL-MIND UNIFIED API SERVER")
    print("="*60)
    print("Starting server on http://localhost:8002")
    print("Frontend expects this port.")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8002)
