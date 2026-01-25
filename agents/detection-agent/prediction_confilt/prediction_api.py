"""
Conflict Prediction API
=======================

FastAPI service for real-time conflict prediction.
Provides REST endpoints for:
- Single train prediction
- Batch network prediction
- Similar case search
- System status
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

try:
    from .config import api_config, prediction_config, conflict_thresholds, SIMULATION_DATA
    from .predictor import ConflictPredictor, ConflictPrediction, PredictionBatch
    from .feature_engine import TrainState, StationState, NetworkState
    from .qdrant_memory import OperationalMemory, MemorySearchResult
except ImportError:
    from config import api_config, prediction_config, conflict_thresholds, SIMULATION_DATA
    from predictor import ConflictPredictor, ConflictPrediction, PredictionBatch
    from feature_engine import TrainState, StationState, NetworkState
    from qdrant_memory import OperationalMemory, MemorySearchResult


# ============================================================================
# PYDANTIC MODELS (API Request/Response)
# ============================================================================

class TrainStateRequest(BaseModel):
    """Request model for train state."""
    train_id: str
    train_type: str = "regional"
    current_station: str
    next_station: Optional[str] = None
    current_delay_sec: float = 0
    position_km: float = 0
    speed_kmh: float = 60
    route: List[Dict] = Field(default_factory=list)
    current_stop_index: int = 0
    scheduled_time: str = ""  # ISO format
    actual_time: str = ""  # ISO format


class StationStateRequest(BaseModel):
    """Request model for station state."""
    station_id: str
    name: str
    current_trains: List[str] = Field(default_factory=list)
    platform_occupancy: Dict[int, Optional[str]] = Field(default_factory=dict)
    expected_arrivals: List[Dict] = Field(default_factory=list)
    expected_departures: List[Dict] = Field(default_factory=list)


class NetworkStateRequest(BaseModel):
    """Request model for network state."""
    simulation_time: str  # ISO format
    trains: Dict[str, TrainStateRequest]
    stations: Dict[str, StationStateRequest] = Field(default_factory=dict)
    active_conflicts: List[Dict] = Field(default_factory=list)


class PredictionResponse(BaseModel):
    """Response model for single prediction."""
    train_id: str
    probability: float
    risk_level: str
    color: str
    emoji: str
    predicted_conflict_type: Optional[str]
    predicted_time: Optional[str]
    predicted_location: Optional[str]
    contributing_factors: List[str]
    confidence: float


class BatchPredictionResponse(BaseModel):
    """Response model for batch prediction."""
    timestamp: str
    predictions: List[PredictionResponse]
    network_risk_score: float
    high_risk_trains: List[str]
    critical_trains: List[str]
    recommended_actions: List[str]


class SimilarCaseResponse(BaseModel):
    """Response model for similar case."""
    case_id: str
    similarity_score: float
    date: str
    line: str
    location: str
    incident_type: str
    delay_duration_min: float
    affected_trains: int
    resolution_types: List[str]
    resolution_description: str
    time_of_day: str
    severity_score: float


class MemorySearchResponse(BaseModel):
    """Response model for memory search."""
    query_train_id: str
    query_conflict_type: str
    query_location: str
    similar_cases: List[SimilarCaseResponse]
    suggested_resolution: Optional[str]
    typical_delay_min: float
    confidence: float


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    status: str
    model_loaded: bool
    qdrant_connected: bool
    prediction_strategy: str
    active_websockets: int
    last_prediction_time: Optional[str]


# ============================================================================
# API APPLICATION
# ============================================================================

app = FastAPI(
    title="Rail-Mind Conflict Prediction API",
    description="ML-based conflict prediction for Lombardy rail network",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
predictor: Optional[ConflictPredictor] = None
memory: Optional[OperationalMemory] = None
active_websockets: List[WebSocket] = []
last_prediction_time: Optional[datetime] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_train_state(req: TrainStateRequest) -> TrainState:
    """Convert request model to TrainState dataclass."""
    return TrainState(
        train_id=req.train_id,
        train_type=req.train_type,
        current_station=req.current_station,
        next_station=req.next_station,
        current_delay_sec=req.current_delay_sec,
        position_km=req.position_km,
        speed_kmh=req.speed_kmh,
        route=req.route,
        current_stop_index=req.current_stop_index,
        scheduled_time=datetime.fromisoformat(req.scheduled_time) if req.scheduled_time else datetime.now(),
        actual_time=datetime.fromisoformat(req.actual_time) if req.actual_time else datetime.now()
    )


def parse_station_state(req: StationStateRequest) -> StationState:
    """Convert request model to StationState dataclass."""
    expected_arrivals = [
        (a["train_id"], datetime.fromisoformat(a["time"]))
        for a in req.expected_arrivals
    ]
    expected_departures = [
        (d["train_id"], datetime.fromisoformat(d["time"]))
        for d in req.expected_departures
    ]
    
    return StationState(
        station_id=req.station_id,
        name=req.name,
        current_trains=req.current_trains,
        platform_occupancy=req.platform_occupancy,
        expected_arrivals=expected_arrivals,
        expected_departures=expected_departures
    )


def parse_network_state(req: NetworkStateRequest) -> NetworkState:
    """Convert request model to NetworkState dataclass."""
    trains = {
        train_id: parse_train_state(train_req)
        for train_id, train_req in req.trains.items()
    }
    
    stations = {
        station_id: parse_station_state(station_req)
        for station_id, station_req in req.stations.items()
    }
    
    return NetworkState(
        simulation_time=datetime.fromisoformat(req.simulation_time),
        trains=trains,
        stations=stations,
        active_conflicts=req.active_conflicts
    )


def prediction_to_response(pred: ConflictPrediction) -> PredictionResponse:
    """Convert prediction dataclass to response model."""
    return PredictionResponse(
        train_id=pred.train_id,
        probability=pred.probability,
        risk_level=pred.risk_level,
        color=pred.color,
        emoji=pred.emoji,
        predicted_conflict_type=pred.predicted_conflict_type,
        predicted_time=pred.predicted_time.isoformat() if pred.predicted_time else None,
        predicted_location=pred.predicted_location,
        contributing_factors=pred.contributing_factors,
        confidence=pred.confidence
    )


def batch_to_response(batch: PredictionBatch) -> BatchPredictionResponse:
    """Convert batch prediction to response model."""
    return BatchPredictionResponse(
        timestamp=batch.timestamp.isoformat(),
        predictions=[prediction_to_response(p) for p in batch.predictions],
        network_risk_score=batch.network_risk_score,
        high_risk_trains=batch.high_risk_trains,
        critical_trains=batch.critical_trains,
        recommended_actions=batch.recommended_actions
    )


def memory_result_to_response(result: MemorySearchResult) -> MemorySearchResponse:
    """Convert memory search result to response model."""
    return MemorySearchResponse(
        query_train_id=result.query_train_id,
        query_conflict_type=result.query_conflict_type,
        query_location=result.query_location,
        similar_cases=[
            SimilarCaseResponse(
                case_id=c.case_id,
                similarity_score=c.similarity_score,
                date=c.date,
                line=c.line,
                location=c.location,
                incident_type=c.incident_type,
                delay_duration_min=c.delay_duration_min,
                affected_trains=c.affected_trains,
                resolution_types=c.resolution_types,
                resolution_description=c.resolution_description,
                time_of_day=c.time_of_day,
                severity_score=c.severity_score
            )
            for c in result.similar_cases
        ],
        suggested_resolution=result.suggested_resolution,
        typical_delay_min=result.typical_delay_min,
        confidence=result.confidence
    )


# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global predictor, memory
    
    print("[RAIL-MIND] Starting Conflict Prediction API...")
    
    # Initialize predictor
    predictor = ConflictPredictor(auto_load=True)
    print("  [OK] Conflict predictor initialized")
    
    # Initialize operational memory (optional)
    try:
        memory = OperationalMemory(initialize=True)
        if memory.collection_ready:
            print("  [OK] Operational memory connected")
        else:
            print("  [WARN] Operational memory: collection not ready")
    except Exception as e:
        print(f"  [WARN] Operational memory not available: {e}")
        memory = None
    
    print(f"  [INFO] Prediction strategy: {prediction_config.strategy}")
    print(f"  [INFO] Prediction horizon: {prediction_config.prediction_horizon_min}-{prediction_config.prediction_horizon_max} min")
    print("[RAIL-MIND] API ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global active_websockets
    
    # Close all WebSocket connections
    for ws in active_websockets:
        try:
            await ws.close()
        except:
            pass
    
    print("[RAIL-MIND] API shutdown complete")


# ============================================================================
# REST ENDPOINTS
# ============================================================================

@app.get("/", response_model=Dict)
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Rail-Mind Conflict Prediction API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "predict": "/api/predict",
            "predict_batch": "/api/predict/batch",
            "search_similar": "/api/memory/search",
            "status": "/api/status",
            "websocket": "/ws/predictions"
        }
    }


@app.get("/api/status", response_model=SystemStatusResponse)
async def get_status():
    """Get system status."""
    return SystemStatusResponse(
        status="running",
        model_loaded=predictor.model is not None if predictor else False,
        qdrant_connected=memory.collection_ready if memory else False,
        prediction_strategy=prediction_config.strategy,
        active_websockets=len(active_websockets),
        last_prediction_time=last_prediction_time.isoformat() if last_prediction_time else None
    )


@app.post("/api/predict", response_model=PredictionResponse)
async def predict_single(train: TrainStateRequest, network: NetworkStateRequest):
    """
    Predict conflict for a single train.
    
    This endpoint is called when a specific train needs prediction,
    typically triggered by smart triggers.
    """
    global predictor, last_prediction_time
    
    if predictor is None:
        raise HTTPException(status_code=500, detail="Predictor not initialized")
    
    # Parse states
    train_state = parse_train_state(train)
    network_state = parse_network_state(network)
    
    # Make prediction
    prediction = predictor.predict(train_state, network_state, force=True)
    
    last_prediction_time = datetime.now()
    
    return prediction_to_response(prediction)


@app.post("/api/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(network: NetworkStateRequest):
    """
    Predict conflicts for all trains in the network.
    
    This is the main endpoint for continuous prediction mode,
    called every simulation minute.
    """
    global predictor, last_prediction_time
    
    if predictor is None:
        raise HTTPException(status_code=500, detail="Predictor not initialized")
    
    # Parse network state
    network_state = parse_network_state(network)
    
    # Make batch prediction
    batch = predictor.predict_batch(network_state)
    
    last_prediction_time = datetime.now()
    
    # Broadcast to WebSocket clients
    response = batch_to_response(batch)
    await broadcast_predictions(response.dict())
    
    return response


@app.post("/api/memory/search", response_model=MemorySearchResponse)
async def search_similar_cases(prediction: PredictionResponse):
    """
    Search for similar historical cases.
    
    Used when a conflict is predicted to find past incidents
    with similar characteristics for resolution suggestions.
    """
    global memory
    
    if memory is None:
        # Return fallback response
        return MemorySearchResponse(
            query_train_id=prediction.train_id,
            query_conflict_type=prediction.predicted_conflict_type or "unknown",
            query_location=prediction.predicted_location or "unknown",
            similar_cases=[],
            suggested_resolution="Monitor situation and apply standard procedures",
            typical_delay_min=5.0,
            confidence=0.3
        )
    
    # Convert response back to ConflictPrediction
    pred = ConflictPrediction(
        train_id=prediction.train_id,
        probability=prediction.probability,
        risk_level=prediction.risk_level,
        color=prediction.color,
        emoji=prediction.emoji,
        predicted_conflict_type=prediction.predicted_conflict_type,
        predicted_time=datetime.fromisoformat(prediction.predicted_time) if prediction.predicted_time else None,
        predicted_location=prediction.predicted_location,
        contributing_factors=prediction.contributing_factors,
        confidence=prediction.confidence
    )
    
    # Search operational memory
    result = memory.search_similar(pred)
    
    return memory_result_to_response(result)


@app.get("/api/thresholds", response_model=Dict)
async def get_thresholds():
    """Get current conflict thresholds and risk levels."""
    return {
        "safe_threshold": conflict_thresholds.safe_threshold,
        "low_risk_threshold": conflict_thresholds.low_risk_threshold,
        "high_risk_threshold": conflict_thresholds.high_risk_threshold,
        "risk_levels": conflict_thresholds.risk_levels
    }


@app.get("/api/config", response_model=Dict)
async def get_config():
    """Get current prediction configuration."""
    return {
        "strategy": prediction_config.strategy,
        "prediction_horizon_min": prediction_config.prediction_horizon_min,
        "prediction_horizon_max": prediction_config.prediction_horizon_max,
        "trigger_delay_threshold_sec": prediction_config.trigger_delay_threshold_sec,
        "trigger_congestion_threshold": prediction_config.trigger_congestion_threshold,
        "continuous_interval_sec": prediction_config.continuous_interval_sec
    }


@app.get("/api/model/info", response_model=Dict)
async def get_model_info():
    """
    Get detailed information about how the ML model works.
    
    Useful for understanding and verifying the prediction system.
    """
    global predictor
    
    model_info = {
        "model_type": "XGBoost Classifier" if predictor and predictor.model else "Heuristic Rules",
        "model_loaded": predictor.model is not None if predictor else False,
        "prediction_strategy": prediction_config.strategy,
        "description": """
The Rail-Mind Conflict Prediction system uses machine learning to predict 
potential conflicts before they occur. The model analyzes:

1. TRAIN STATE FEATURES:
   - Current delay (seconds)
   - Speed relative to schedule
   - Distance to next station
   - Train type/priority

2. STATION FEATURES:
   - Platform utilization
   - Current occupancy
   - Expected arrivals/departures
   - Is major hub station

3. NETWORK FEATURES:
   - Upstream congestion
   - Segment utilization
   - Competing trains on same route

4. TEMPORAL FEATURES:
   - Is peak hour
   - Day of week
   - Time since last incident
        """.strip(),
        "conflict_types": [
            {"type": "platform_conflict", "description": "Multiple trains assigned to same platform"},
            {"type": "track_conflict", "description": "Two trains on same track segment"},
            {"type": "headway_violation", "description": "Minimum headway not maintained"},
            {"type": "capacity_exceeded", "description": "Station/track capacity exceeded"},
            {"type": "schedule_deviation", "description": "Significant deviation from timetable"},
            {"type": "cascading_delay", "description": "Delay propagating through network"},
        ],
        "incident_types_from_data": [
            {"type": "technical", "description": "Equipment/infrastructure failure"},
            {"type": "trespasser", "description": "Unauthorized persons on tracks"},
            {"type": "weather", "description": "Weather-related issues"},
            {"type": "maintenance", "description": "Scheduled/unscheduled maintenance"},
            {"type": "fire", "description": "Fire incidents"},
            {"type": "police_intervention", "description": "Police/security intervention"},
        ],
        "risk_levels": {
            "safe": {"threshold": "<0.3", "color": "#22c55e", "emoji": "🟢"},
            "low_risk": {"threshold": "0.3-0.5", "color": "#eab308", "emoji": "🟡"},
            "high_risk": {"threshold": "0.5-0.8", "color": "#f97316", "emoji": "🟠"},
            "critical": {"threshold": ">0.8", "color": "#ef4444", "emoji": "🔴"},
        },
        "smart_triggers": {
            "delay_threshold": f">{prediction_config.trigger_delay_threshold_sec}s",
            "congestion_threshold": f">{prediction_config.trigger_congestion_threshold*100}%",
            "approaching_hub": prediction_config.trigger_approaching_hub,
        },
        "lombardy_coverage": {
            "region": "Lombardy, Italy",
            "major_hubs": [
                "Milano Centrale", "Milano Porta Garibaldi", "Milano Cadorna",
                "Brescia", "Bergamo", "Pavia", "Monza", "Varese", "Como", "Lecco"
            ],
        }
    }
    
    return model_info


@app.get("/api/model/test", response_model=Dict)
async def test_model_prediction():
    """
    Test the model with a sample prediction.
    
    Returns a detailed breakdown of how the model arrived at its prediction.
    """
    global predictor
    
    if predictor is None:
        raise HTTPException(status_code=500, detail="Predictor not initialized")
    
    # Create a test train state with some delay
    test_train = TrainState(
        train_id="TEST_001",
        train_type="regional",
        current_station="PAVIA",
        next_station="MILANO CENTRALE",
        current_delay_sec=180,  # 3 minutes delay
        position_km=20.0,
        speed_kmh=60,
        route=[
            {"station_name": "PAVIA", "lat": 45.188843, "lon": 9.144674, "distance_from_previous_km": 0},
            {"station_name": "MILANO CENTRALE", "lat": 45.486347, "lon": 9.204528, "distance_from_previous_km": 33.4}
        ],
        current_stop_index=0,
        scheduled_time=datetime.now(),
        actual_time=datetime.now() + timedelta(seconds=180)
    )
    
    # Create minimal network state
    test_network = NetworkState(
        simulation_time=datetime.now(),
        trains={"TEST_001": test_train},
        stations={},
        active_conflicts=[]
    )
    
    # Get prediction
    prediction = predictor.predict(test_train, test_network, force=True)
    
    # Get features for explanation
    features = predictor.feature_engine.compute_features(
        test_train, test_network, prediction_config.prediction_horizon_min
    )
    
    return {
        "test_input": {
            "train_id": "TEST_001",
            "current_station": "PAVIA",
            "next_station": "MILANO CENTRALE",
            "delay_minutes": 3,
            "train_type": "regional",
        },
        "prediction_result": {
            "probability": prediction.probability,
            "risk_level": prediction.risk_level,
            "color": prediction.color,
            "emoji": prediction.emoji,
            "predicted_conflict_type": prediction.predicted_conflict_type,
            "contributing_factors": prediction.contributing_factors,
            "confidence": prediction.confidence,
        },
        "feature_breakdown": {
            "delay_sec": features.get("current_delay_sec", 0),
            "is_major_hub": features.get("is_major_hub", 0),
            "is_peak_hour": features.get("is_peak_hour", 0),
            "competing_trains": features.get("competing_trains_count", 0),
            "station_occupancy": features.get("current_occupancy", 0),
        },
        "explanation": f"""
The model predicted {prediction.risk_level.upper()} risk ({prediction.probability*100:.1f}%) because:
{chr(10).join('- ' + f for f in prediction.contributing_factors) if prediction.contributing_factors else '- No significant risk factors detected'}

The train is heading to {test_train.next_station} (major hub) with a {test_train.current_delay_sec/60:.0f} minute delay.
Using prediction strategy: {prediction_config.strategy}
Model type: {'XGBoost' if predictor.model else 'Heuristic rules'}
        """.strip()
    }


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

async def broadcast_predictions(data: Dict):
    """Broadcast predictions to all connected WebSocket clients."""
    global active_websockets
    
    disconnected = []
    for ws in active_websockets:
        try:
            await ws.send_json(data)
        except:
            disconnected.append(ws)
    
    # Remove disconnected clients
    for ws in disconnected:
        active_websockets.remove(ws)


@app.websocket("/ws/predictions")
async def websocket_predictions(websocket: WebSocket):
    """
    WebSocket endpoint for real-time predictions.
    
    Clients connect here to receive continuous prediction updates.
    """
    global active_websockets
    
    await websocket.accept()
    active_websockets.append(websocket)
    
    print(f"  [WS] WebSocket client connected. Total: {len(active_websockets)}")
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            
            # Handle ping/pong
            if data == "ping":
                await websocket.send_text("pong")
            
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
        print(f"  [WS] WebSocket client disconnected. Total: {len(active_websockets)}")


# ============================================================================
# DEMO ENDPOINT
# ============================================================================

@app.get("/api/demo/simulate", response_model=BatchPredictionResponse)
async def demo_simulate():
    """
    Demo endpoint that simulates predictions using train data from any region.
    
    Loads simulation data and creates realistic predictions.
    Useful for testing the frontend without a full simulation.
    """
    global predictor
    
    if predictor is None:
        raise HTTPException(status_code=500, detail="Predictor not initialized")
    
    try:
        # Load simulation data
        if not SIMULATION_DATA.exists():
            raise HTTPException(status_code=404, detail="Simulation data not found")
        
        with open(SIMULATION_DATA, 'r', encoding='utf-8') as f:
            sim_data = json.load(f)
        
        # Create demo network state
        trains = {}
        current_time = datetime.now()
        
        # Limit trains for demo (20 trains maximum)
        train_list = sim_data.get("trains", [])[:20]
        
        for train_data in train_list:
            try:
                train_id = train_data["train_id"]
                route = train_data.get("route", [])
                
                # Skip if route is too short
                if len(route) < 2:
                    continue
                
                # Simulate realistic delays (most trains on time, some delayed)
                import random
                delay = random.choice([0, 0, 0, 0, 60, 120, 180, 300])  # 50% on time
                
                # Create train state
                trains[train_id] = TrainState(
                    train_id=train_id,
                    train_type=train_data.get("train_type", "regional"),
                    current_station=route[0]["station_name"],
                    next_station=route[1]["station_name"] if len(route) > 1 else None,
                    current_delay_sec=delay,
                    position_km=route[0].get("distance_from_previous_km", 0),
                    speed_kmh=80 if delay < 120 else 40,  # Slower when delayed
                    route=route,
                    current_stop_index=0,
                    scheduled_time=current_time,
                    actual_time=current_time + timedelta(seconds=delay)
                )
            except Exception as e:
                # Skip trains with data issues
                print(f"[WARN] Skipping train {train_data.get('train_id', 'unknown')}: {e}")
                continue
        
        # Create network state
        network_state = NetworkState(
            simulation_time=current_time,
            trains=trains,
            stations={},
            active_conflicts=[]
        )
        
        # Make predictions
        batch = predictor.predict_batch(network_state)
        
        return batch_to_response(batch)
        
    except Exception as e:
        print(f"[ERROR] Demo simulate failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def run_server():
    """Run the FastAPI server."""
    uvicorn.run(
        "prediction_confilt.prediction_api:app",
        host=api_config.host,
        port=api_config.port,
        reload=api_config.reload
    )


if __name__ == "__main__":
    run_server()
