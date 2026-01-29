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
import os
import asyncio
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
from concurrent.futures import ThreadPoolExecutor

# Add paths
# BASE_DIR is backend folder, detection modules are in agents/detection-agent/
BASE_DIR = Path(__file__).resolve().parent.parent  # backend folder
PROJECT_ROOT = BASE_DIR.parent  # rail-mind folder
RESOLUTION_AGENT_DIR = PROJECT_ROOT / "agents" / "resolution-agent"
sys.path.insert(0, str(RESOLUTION_AGENT_DIR))
DETECTION_AGENT_DIR = PROJECT_ROOT / "agents" / "detection-agent"
sys.path.insert(0, str(DETECTION_AGENT_DIR / "prediction_confilt"))
sys.path.insert(0, str(DETECTION_AGENT_DIR / "deterministic-detection"))
sys.path.insert(0, str(BASE_DIR / "integration"))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# Create output directory for conflict results
CONFLICTS_OUTPUT_DIR = Path(__file__).parent / "conflict_results"
CONFLICTS_OUTPUT_DIR.mkdir(exist_ok=True)

# Create orchestrator output directory
ORCHESTRATOR_OUTPUT_DIR = CONFLICTS_OUTPUT_DIR / "orchestrator_outputs"
ORCHESTRATOR_OUTPUT_DIR.mkdir(exist_ok=True)

# Track images directory
TRACK_IMAGES_DIR = PROJECT_ROOT / "agents" / "detection-agent" / "Vision-Based Track Fault Detection" / "images"

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
    image_url: Optional[str] = None  # Track fault images


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
        "version": "2.1.0",
        "description": "ML Prediction + Deterministic Detection + Resolution Orchestration",
        "endpoints": {
            "/api/simulation/state": "Get current state without advancing",
            "/api/simulation/tick": "Advance simulation and get new state",
            "/api/simulation/start": "Reset simulation",
            "/api/prediction/{station_id}": "Get predictions for a station",
            "/api/region/{region}": "Get all data for a region",
            "/api/track-images/{filename}": "Get track fault images",
            "/api/conflicts/save": "Save current conflicts to file",
            "/api/conflicts/list": "List saved conflict files",
            "/api/conflicts/resolve": "POST - Resolve a conflict using orchestrator",
            "/api/conflicts/resolve/outputs": "List orchestrator output files",
            "/health": "Health check"
        },
        "color_coding": {
            "green": "Safe (no risk)",
            "yellow": "Low risk (probability < 0.5)",
            "orange": "High risk (probability >= 0.5)",
            "red": "Active conflict (detected)"
        },
        "resolution_api": {
            "description": "POST to /api/conflicts/resolve with conflict JSON",
            "body_options": [
                "{ conflict: {...} } - Direct conflict object",
                "{ detection: {...} } - Detection from this API (auto-converted)",
                "{ filename: 'file.json' } - Load from saved file"
            ],
            "optional_params": ["llm_api_key", "timeout", "context"],
            "env_vars": ["GROQ_API_KEY - For LLM judge"]
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


@app.get("/api/track-images/{filename}")
def get_track_image(filename: str):
    """
    Serve track fault images for display in frontend.
    
    Used to show detected defective track images in alert panel.
    """
    image_path = TRACK_IMAGES_DIR / filename
    print(f"[API] Serving track image: {image_path}")
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {filename}")
    return FileResponse(
        path=str(image_path),
        media_type="image/jpeg",
        filename=filename
    )


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
# Resolution Orchestrator Integration
# =============================================================================

# Simple rate limiter for orchestrator calls
_rate_limit_store: Dict[str, tuple] = {}  # ip -> (last_time, count)
RATE_LIMIT_CALLS = 5
RATE_LIMIT_WINDOW_SEC = 60

# Thread pool for orchestrator (limited to 2 concurrent resolutions)
_orchestrator_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="orchestrator")


def _check_rate_limit(client_ip: str) -> bool:
    """Check if client is rate limited. Returns True if request should be blocked."""
    now = time.time()
    if client_ip in _rate_limit_store:
        last_time, count = _rate_limit_store[client_ip]
        if now - last_time < RATE_LIMIT_WINDOW_SEC:
            if count >= RATE_LIMIT_CALLS:
                return True
            _rate_limit_store[client_ip] = (last_time, count + 1)
        else:
            _rate_limit_store[client_ip] = (now, 1)
    else:
        _rate_limit_store[client_ip] = (now, 1)
    return False


def _run_orchestrator_sync(conflict: Dict[str, Any], context: Optional[Dict], timeout: float, api_key: Optional[str]) -> Dict[str, Any]:
    """
    Run the orchestrator synchronously (called in thread pool).
    Handles the import and invocation of orchestrator.orchestrate().
    """
    try:
        # Import orchestrator module
        import resolution_orchestrator as orchestrator_module
        
        # Call orchestrate function
        result = orchestrator_module.orchestrate(
            conflict=conflict,
            context=context,
            timeout=timeout,
            api_key=api_key
        )
        return result
    except ImportError as e:
        return {
            "status": "error",
            "error": f"Failed to import resolution_orchestrator: {str(e)}",
            "traceback": traceback.format_exc()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        }


def _convert_detection_to_orchestrator_format(detection: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a detection/prediction from unified_api format to orchestrator conflict format.
    
    The orchestrator expects:
    - conflict_id
    - conflict_type
    - station_ids (list of station names)
    - train_ids (list of train IDs)
    - delay_values (dict of train_id -> delay)
    - timestamp
    - severity (0-1 float)
    - blocking_behavior
    """
    # Extract trains from involved_trains
    train_ids = detection.get("involved_trains", [])
    
    # Parse location to get station IDs
    location = detection.get("location", "")
    if "--" in location:
        station_ids = location.split("--")
    else:
        station_ids = [location] if location else []
    
    # Map severity string to float
    severity_map = {"low": 0.3, "medium": 0.5, "high": 0.75, "critical": 0.95}
    severity_str = detection.get("severity", "medium")
    severity = severity_map.get(severity_str, 0.5)
    
    # Build delay values from any available data
    delay_values = {}
    for train_id in train_ids:
        delay_values[train_id] = 2.0  # Default delay estimate
    
    return {
        "conflict_id": detection.get("conflict_id", f"CONF-{datetime.now().strftime('%Y%m%d%H%M%S')}"),
        "conflict_type": detection.get("conflict_type", "unknown"),
        "station_ids": station_ids,
        "train_ids": train_ids,
        "delay_values": delay_values,
        "timestamp": datetime.now().timestamp(),
        "severity": severity,
        "blocking_behavior": "soft",
        # Preserve original data for reference
        "original_detection": detection
    }


@app.post("/api/conflicts/resolve")
async def resolve_conflict(request: Request):
    """
    Resolve a conflict using the Resolution Orchestrator.
    
    Accepts either:
    - JSON body with "conflict" object (in orchestrator format)
    - JSON body with "detection" object (from unified_api detection format, will be converted)
    - JSON body with "filename" to load a saved conflict file
    
    Optional parameters:
    - llm_api_key: API key for LLM judge (or use GROQ_API_KEY env var)
    - timeout: Per-agent timeout in seconds (default: 60)
    - context: Optional operational context
    
    Returns:
    - success: boolean
    - filepath: path to saved output file
    - output: complete orchestrator output with agent results, timings, and rankings
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_CALLS} calls per {RATE_LIMIT_WINDOW_SEC} seconds."
        )
    
    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {str(e)}")
    
    # Validate payload size (max 1MB)
    content_length = request.headers.get("content-length", 0)
    if int(content_length) > 1_000_000:
        raise HTTPException(status_code=413, detail="Payload too large (max 1MB)")
    
    # Extract parameters
    llm_api_key = body.get("llm_api_key") or request.headers.get("Authorization", "").replace("Bearer ", "") or None
    timeout = float(body.get("timeout", 60))
    context = body.get("context")
    
    # Get conflict from body, detection, or filename
    conflict = body.get("conflict")
    detection = body.get("detection")
    filename = body.get("filename")
    
    # If detection provided, convert to orchestrator format
    if detection and not conflict:
        conflict = _convert_detection_to_orchestrator_format(detection)
    
    # If filename provided, load from file
    if filename and not conflict:
        # Security: only allow loading from CONFLICTS_OUTPUT_DIR, no path traversal
        safe_filename = Path(filename).name
        filepath = CONFLICTS_OUTPUT_DIR / safe_filename
        
        if not filepath.exists():
            raise HTTPException(status_code=404, detail=f"Conflict file not found: {safe_filename}")
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                file_data = json.load(f)
            
            # Check if this is a saved conflicts file (has predictions/detections) or direct conflict
            if "predictions" in file_data or "detections" in file_data:
                # Get first high-risk detection or prediction
                detections = file_data.get("detections", [])
                predictions = file_data.get("predictions", [])
                
                # Prefer detections (confirmed conflicts)
                if detections:
                    conflict = _convert_detection_to_orchestrator_format(detections[0])
                elif predictions:
                    # Get highest probability prediction
                    sorted_preds = sorted(predictions, key=lambda p: p.get("probability", 0), reverse=True)
                    conflict = _convert_detection_to_orchestrator_format(sorted_preds[0])
                else:
                    raise HTTPException(status_code=400, detail="No conflicts found in file")
            else:
                # Direct conflict format
                conflict = file_data
                
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in file: {str(e)}")
    
    if not conflict:
        raise HTTPException(status_code=400, detail="No conflict provided. Send 'conflict', 'detection', or 'filename' in request body.")
    
    # Run orchestrator in thread pool to avoid blocking the event loop
    # The orchestrator uses asyncio.run() internally, so we must run it in a separate thread
    loop = asyncio.get_running_loop()
    
    try:
        result = await loop.run_in_executor(
            _orchestrator_executor,
            _run_orchestrator_sync,
            conflict,
            context,
            timeout,
            llm_api_key
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestrator execution failed: {str(e)}")
    
    # Save orchestrator output
    conflict_id = conflict.get("conflict_id", "unknown")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_filename = f"orchestrator_{conflict_id}_{ts}.json"
    output_path = ORCHESTRATOR_OUTPUT_DIR / output_filename
    
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"[API] Warning: Failed to save orchestrator output: {e}")
    
    # Return response
    return {
        "success": result.get("status") in ["ok", "partial"],
        "filepath": str(output_path),
        "filename": output_filename,
        "conflict_id": conflict_id,
        "output": result
    }


@app.get("/api/conflicts/resolve/outputs")
def list_orchestrator_outputs() -> dict:
    """List all saved orchestrator output files."""
    files = sorted(ORCHESTRATOR_OUTPUT_DIR.glob("orchestrator_*.json"), reverse=True)
    
    file_list = []
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                file_list.append({
                    "filename": f.name,
                    "filepath": str(f),
                    "conflict_id": data.get("conflict_id", "unknown"),
                    "status": data.get("status", "unknown"),
                    "total_execution_ms": data.get("total_execution_ms", 0),
                    "started_at": data.get("started_at", ""),
                    "has_rankings": bool(data.get("llm_judge", {}).get("ranked_resolutions")),
                })
        except Exception as e:
            print(f"Error reading {f}: {e}")
    
    return {
        "count": len(file_list),
        "files": file_list,
        "output_directory": str(ORCHESTRATOR_OUTPUT_DIR)
    }


@app.get("/api/conflicts/resolve/output/{filename}")
def get_orchestrator_output(filename: str) -> dict:
    """Load a specific orchestrator output file."""
    safe_filename = Path(filename).name
    filepath = ORCHESTRATOR_OUTPUT_DIR / safe_filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Output file not found: {safe_filename}")
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading file: {str(e)}")


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
