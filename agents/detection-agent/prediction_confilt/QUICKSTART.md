# 🚀 Quick Start Guide: Prediction API

## Starting the API

### Method 1: Using the Launcher (Recommended)
```bash
cd agents/detection-agent/prediction_confilt
python start_api.py
```

### Method 2: Using uvicorn directly
```bash
cd agents/detection-agent/prediction_confilt
python -m uvicorn prediction_api:app --port 8002
```

The API will start on **http://localhost:8002**

You should see:
```
[RAIL-MIND] Starting Conflict Prediction API...
[OK] Loaded XGBoost model
[INFO] Using ENSEMBLE mode: 70% ML + 30% Heuristics
[INFO] Agreement boost: 1.15x when both predict risk > 60%
[OK] Conflict predictor initialized
[RAIL-MIND] API ready!
INFO:     Uvicorn running on http://0.0.0.0:8002
```

## Testing the API

### 1. Check Model Info
```bash
curl http://localhost:8002/api/model/info
```

Returns detailed information about:
- Model type (XGBoost Classifier)
- Conflict types it detects
- Risk levels and thresholds
- Lombardy coverage area

### 2. Check System Status
```bash
curl http://localhost:8002/api/status
```

Returns:
- Model loaded status
- Qdrant connection status
- Prediction strategy
- Active WebSocket connections

### 3. Get Configuration
```bash
curl http://localhost:8002/api/config
```

Returns current prediction configuration including:
- Strategy (continuous or smart triggers)
- Prediction horizon (15-30 minutes)
- Trigger thresholds

## Using from Frontend

The frontend (running on port 8081) connects automatically to the API at port 8002.

1. **Start the backend first:**
   ```bash
   cd agents/detection-agent/prediction_confilt
   python start_api.py
   ```

2. **Then start the frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Open browser:** http://localhost:8081

The frontend will:
- Display the Lombardy rail network map
- Show real-time conflict predictions
- Color-code trains based on risk level (green → yellow → orange → red)
- Display conflict probabilities and types

## API Endpoints

### Core Prediction Endpoints

- `POST /api/predict` - Predict conflict for a single train
- `POST /api/predict/batch` - Predict conflicts for all trains in network
- `POST /api/memory/search` - Find similar historical cases

### Information Endpoints

- `GET /api/model/info` - Model capabilities and coverage
- `GET /api/status` - System health status
- `GET /api/config` - Current configuration
- `GET /api/thresholds` - Risk level thresholds

### Testing Endpoints

- `GET /api/demo/simulate` - Simulate predictions with Lombardy trains (for testing frontend without full simulation)

### WebSocket

- `ws://localhost:8002/ws/predictions` - Real-time prediction stream

## Troubleshooting

### API won't start

**Issue:** Port 8002 already in use

**Solution:**
```bash
# Stop existing process
Get-Process | Where-Object {$_.Path -like '*rail-mind\.venv*'} | Stop-Process -Force

# Or use a different port
python -m uvicorn prediction_api:app --port 8003
```

### Model not loading

**Issue:** Model files not found

**Solution:** Train the model first:
```bash
cd agents/detection-agent/prediction_confilt
python train_model.py
```

This will create:
- `models/conflict_predictor_xgb.joblib` - Trained XGBoost model
- `models/feature_scaler.joblib` - Feature normalization scaler
- `models/feature_config.json` - Feature configuration

### Import errors

**Issue:** `ModuleNotFoundError` or relative import errors

**Solution:** Use the `start_api.py` launcher script which handles paths correctly.

### CORS errors in frontend

**Issue:** Frontend can't connect to API

**Solution:** The API is configured to allow all origins in development. Make sure:
1. API is running on port 8002
2. Frontend `.env` or config points to correct API URL
3. Check browser console for specific CORS errors

## Model Information

The prediction system uses an **ensemble approach**:

- **70% XGBoost ML predictions** - Learned patterns from historical incidents
- **30% Heuristic rules** - Domain knowledge about delays, congestion, peak hours
- **Agreement boost** - When both ML and heuristics agree on high risk (>60%), confidence increases by 15%

This hybrid approach ensures:
- ✅ Learns from limited historical data
- ✅ Robust predictions even with small training set
- ✅ Incorporates expert railway knowledge
- ✅ Higher confidence when methods align

## Retraining the Model

To retrain with new incident data:

```bash
cd agents/detection-agent/prediction_confilt
python train_model.py
```

The script will:
1. Load historical fault/incident data
2. Load operation data (delays, schedules)
3. Generate labeled training samples
4. Train XGBoost model
5. Save trained model files

After retraining, restart the API to load the new model.
