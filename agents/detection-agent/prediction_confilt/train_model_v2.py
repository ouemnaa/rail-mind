"""
XGBoost Model Training Script v2
================================

This script trains the XGBoost model using the SAME FeatureEngine class
that the predictor uses, ensuring feature consistency.

Key Improvements:
1. Uses FeatureEngine.compute_features() for BOTH training and prediction
2. Generates realistic training data from historical incidents
3. Creates synthetic conflict scenarios from normal operations
4. Properly handles all 28 features

Why XGBoost + Heuristics Ensemble?
----------------------------------
1. XGBoost learns patterns from historical data (data-driven)
2. Heuristics encode domain knowledge (expert-driven)
3. Ensemble combines both: robust even with limited data
4. When both agree → high confidence
5. When they disagree → cautious prediction

The ensemble approach is especially valuable because:
- Historical incident data is sparse (only 113 records, 7 in Lombardy)
- XGBoost alone may overfit or miss edge cases
- Heuristics provide baseline safety rules
- Combined, they catch both learned patterns AND known risk factors
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import warnings
import random

# ML imports
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, roc_auc_score, 
    precision_recall_curve, average_precision_score
)
import xgboost as xgb
import joblib

# Use local imports - same as predictor uses
from feature_engine import FeatureEngine, TrainState, StationState, NetworkState
from config import (
    MODEL_DIR, MODEL_FILE, SCALER_FILE, FEATURE_CONFIG_FILE,
    FAULT_DATA, OPERATION_DATA, STATION_DATA, SIMULATION_DATA,
    LOMBARDY_MAJOR_HUBS, INCIDENT_TYPES, xgboost_config
)


class TrainingDataGenerator:
    """
    Generates labeled training data for the conflict prediction model.
    
    Uses the SAME FeatureEngine as the predictor to ensure feature consistency.
    
    Approach:
    1. POSITIVE SAMPLES (conflict=1): 
       - Extract features from moments BEFORE historical incidents
       - These represent states that led to conflicts
       
    2. NEGATIVE SAMPLES (conflict=0):
       - Extract features from normal operations
       - Times when no incident occurred nearby
    """
    
    def __init__(self):
        """Initialize with same FeatureEngine as predictor."""
        self.feature_engine = FeatureEngine()
        self.incidents: List[Dict] = []
        self.operations: pd.DataFrame = pd.DataFrame()
        self.stations: pd.DataFrame = pd.DataFrame()
        self.simulation_data: Dict = {}
        
    def load_data(self) -> None:
        """Load all historical data sources."""
        print("Loading historical data...")
        
        # Load incidents (fault data)
        if FAULT_DATA.exists():
            with open(FAULT_DATA, 'r', encoding='utf-8') as f:
                self.incidents = json.load(f)
            print(f"  ✓ Loaded {len(self.incidents)} incident records")
        else:
            print(f"  ✗ Fault data not found at {FAULT_DATA}")
            
        # Load operations data
        if OPERATION_DATA.exists():
            self.operations = pd.read_csv(OPERATION_DATA, low_memory=False)
            print(f"  ✓ Loaded {len(self.operations)} operation records")
        else:
            print(f"  ✗ Operation data not found at {OPERATION_DATA}")
            
        # Load station data
        if STATION_DATA.exists():
            self.stations = pd.read_csv(STATION_DATA)
            print(f"  ✓ Loaded {len(self.stations)} station records")
        else:
            print(f"  ✗ Station data not found at {STATION_DATA}")
            
        # Load simulation data for realistic train routes
        if SIMULATION_DATA.exists():
            with open(SIMULATION_DATA, 'r', encoding='utf-8') as f:
                self.simulation_data = json.load(f)
            print(f"  ✓ Loaded simulation data with {len(self.simulation_data.get('trains', []))} train routes")
    
    def _create_train_state(
        self,
        train_id: str,
        station: str,
        next_station: str,
        delay_sec: float,
        train_type: str = "regional",
        route: List[Dict] = None
    ) -> TrainState:
        """Create a TrainState object for feature extraction."""
        if route is None:
            # Create minimal route
            route = [
                {"station_name": station, "lat": 45.4, "lon": 9.2, "distance_from_previous_km": 0},
                {"station_name": next_station, "lat": 45.5, "lon": 9.3, "distance_from_previous_km": 20}
            ]
        
        return TrainState(
            train_id=train_id,
            train_type=train_type,
            current_station=station,
            next_station=next_station,
            current_delay_sec=delay_sec,
            position_km=0,
            speed_kmh=80 if delay_sec < 120 else 40,
            route=route,
            current_stop_index=0,
            scheduled_time=datetime.now(),
            actual_time=datetime.now() + timedelta(seconds=delay_sec)
        )
    
    def _create_network_state(
        self,
        trains: Dict[str, TrainState],
        stations: Dict[str, StationState] = None,
        simulation_time: datetime = None
    ) -> NetworkState:
        """Create a NetworkState object for feature extraction."""
        return NetworkState(
            simulation_time=simulation_time or datetime.now(),
            trains=trains,
            stations=stations or {},
            active_conflicts=[]
        )
    
    def generate_positive_samples(self, lookback_minutes: int = 15) -> Tuple[List[np.ndarray], List[int]]:
        """
        Generate positive samples (conflict=1) from historical incidents.
        
        For each incident:
        - Create train state at various points BEFORE the incident
        - Extract features using the SAME FeatureEngine as predictor
        - Label as conflict=1
        """
        samples = []
        labels = []
        
        print(f"\nGenerating POSITIVE samples (lookback={lookback_minutes} min)...")
        
        # Filter for Lombardy incidents
        lombardy_incidents = [
            inc for inc in self.incidents
            if (inc.get('matched_region') == 'Lombardy' or
                any(hub.upper() in (inc.get('matched_station') or '').upper() 
                    for hub in LOMBARDY_MAJOR_HUBS))
        ]
        
        print(f"  Found {len(lombardy_incidents)} Lombardy incidents")
        
        # Get train routes from simulation data
        train_routes = {t['train_id']: t.get('route', []) 
                       for t in self.simulation_data.get('trains', [])}
        
        for inc in lombardy_incidents:
            try:
                # Parse incident time
                inc_time = pd.to_datetime(inc.get('incident_datetime'))
                station = inc.get('matched_station', 'MILANO CENTRALE')
                inc_type = inc.get('mapped_incident_type', 'other')
                
                # Get a route that passes through this station
                route = None
                for tid, r in train_routes.items():
                    if any(s.get('station_name', '').upper() == station.upper() for s in r):
                        route = r
                        break
                
                if route is None:
                    # Use generic route
                    route = [
                        {"station_name": station, "lat": 45.4, "lon": 9.2, "distance_from_previous_km": 0},
                        {"station_name": "NEXT_STATION", "lat": 45.5, "lon": 9.3, "distance_from_previous_km": 25}
                    ]
                
                # Create samples at different lookback times
                for minutes_before in [5, 10, 15]:
                    if minutes_before > lookback_minutes:
                        continue
                    
                    # Simulate increasing delay as incident approaches
                    delay_progression = [60, 180, 300][min(2, minutes_before // 5)]
                    
                    # Create train state
                    train_id = f"TRAIN_{inc.get('id', 'UNK')}"
                    train = self._create_train_state(
                        train_id=train_id,
                        station=station,
                        next_station=route[1]['station_name'] if len(route) > 1 else "NEXT",
                        delay_sec=delay_progression,
                        train_type="regional",
                        route=route
                    )
                    
                    # Create network state
                    network = self._create_network_state(
                        trains={train_id: train},
                        simulation_time=inc_time - timedelta(minutes=minutes_before)
                    )
                    
                    # Extract features using SAME engine as predictor
                    features = self.feature_engine.compute_features(train, network, 15)
                    feature_array = self.feature_engine.features_to_array(features)
                    
                    samples.append(feature_array)
                    labels.append(1)  # Conflict = 1
                    
            except Exception as e:
                print(f"  ✗ Error processing incident: {e}")
                continue
        
        print(f"  Created {len(samples)} positive samples (conflict=1)")
        return samples, labels
    
    def generate_negative_samples(self, num_samples: int = 100) -> Tuple[List[np.ndarray], List[int]]:
        """
        Generate negative samples (conflict=0) from normal operations.
        
        For each sample:
        - Create train state with normal/low delay
        - Ensure time is NOT near any incident
        - Extract features using SAME FeatureEngine
        - Label as conflict=0
        """
        samples = []
        labels = []
        
        print(f"\nGenerating NEGATIVE samples (target={num_samples})...")
        
        # Get incident times to avoid
        incident_times = []
        for inc in self.incidents:
            try:
                t = pd.to_datetime(inc.get('incident_datetime'))
                incident_times.append(t)
            except:
                pass
        
        # Get train routes from simulation data
        train_list = self.simulation_data.get('trains', [])
        if not train_list:
            print("  ✗ No train data available for negative samples")
            return samples, labels
        
        # Generate samples from normal operations
        attempts = 0
        max_attempts = num_samples * 10
        
        while len(samples) < num_samples and attempts < max_attempts:
            attempts += 1
            
            try:
                # Pick random train
                train_data = random.choice(train_list)
                route = train_data.get('route', [])
                if len(route) < 2:
                    continue
                
                # Pick random station along route
                stop_idx = random.randint(0, len(route) - 2)
                station = route[stop_idx]['station_name']
                next_station = route[stop_idx + 1]['station_name']
                
                # Generate random time (avoid incident windows)
                random_hour = random.randint(6, 22)
                random_day = random.randint(1, 28)
                sample_time = datetime(2024, 1, random_day, random_hour, 
                                      random.randint(0, 59))
                
                # Check if too close to any incident (within 30 min)
                too_close = False
                for inc_time in incident_times:
                    try:
                        diff = abs((sample_time - inc_time).total_seconds() / 60)
                        if diff < 30:
                            too_close = True
                            break
                    except:
                        pass
                
                if too_close:
                    continue
                
                # Create train state with LOW delay (normal operation)
                delay = random.choice([0, 0, 0, 30, 60, 90])  # Mostly on time
                train_id = f"NORMAL_{len(samples)}"
                
                train = self._create_train_state(
                    train_id=train_id,
                    station=station,
                    next_station=next_station,
                    delay_sec=delay,
                    train_type=train_data.get('train_type', 'regional'),
                    route=route
                )
                
                # Create network state
                network = self._create_network_state(
                    trains={train_id: train},
                    simulation_time=sample_time
                )
                
                # Extract features using SAME engine as predictor
                features = self.feature_engine.compute_features(train, network, 15)
                feature_array = self.feature_engine.features_to_array(features)
                
                samples.append(feature_array)
                labels.append(0)  # No conflict = 0
                
            except Exception as e:
                continue
        
        print(f"  Created {len(samples)} negative samples (conflict=0)")
        return samples, labels
    
    def generate_training_data(
        self,
        lookback_minutes: int = 15,
        negative_ratio: float = 3.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate complete training dataset.
        
        Args:
            lookback_minutes: How far before incidents to extract features
            negative_ratio: Ratio of negative to positive samples
            
        Returns:
            Tuple of (X, y) - features and labels
        """
        print("\n" + "="*60)
        print("GENERATING TRAINING DATA")
        print("="*60)
        
        # Generate positive samples
        pos_samples, pos_labels = self.generate_positive_samples(lookback_minutes)
        
        # Calculate how many negative samples we need
        num_negative = max(int(len(pos_samples) * negative_ratio), 50)
        
        # Generate negative samples
        neg_samples, neg_labels = self.generate_negative_samples(num_negative)
        
        # Combine
        all_samples = pos_samples + neg_samples
        all_labels = pos_labels + neg_labels
        
        if not all_samples:
            raise ValueError("No training samples generated!")
        
        X = np.vstack(all_samples)
        y = np.array(all_labels)
        
        print(f"\n{'='*60}")
        print("TRAINING DATA SUMMARY")
        print("="*60)
        print(f"  Total samples: {len(y)}")
        print(f"  Positive (conflict=1): {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
        print(f"  Negative (conflict=0): {len(y)-sum(y)} ({(len(y)-sum(y))/len(y)*100:.1f}%)")
        print(f"  Features: {X.shape[1]}")
        print(f"  Feature names: {', '.join(self.feature_engine.get_feature_names()[:10])}...")
        
        return X, y


def train_model(X: np.ndarray, y: np.ndarray) -> Tuple[xgb.XGBClassifier, StandardScaler, Dict]:
    """
    Train XGBoost model with proper validation.
    
    Returns trained model, scaler, and metrics.
    """
    print(f"\n{'='*60}")
    print("TRAINING XGBOOST MODEL")
    print("="*60)
    
    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"  Training samples: {len(y_train)}")
    print(f"  Validation samples: {len(y_val)}")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    # Configure XGBoost
    model = xgb.XGBClassifier(
        n_estimators=xgboost_config.n_estimators,
        max_depth=xgboost_config.max_depth,
        learning_rate=xgboost_config.learning_rate,
        subsample=xgboost_config.subsample,
        colsample_bytree=xgboost_config.colsample_bytree,
        min_child_weight=xgboost_config.min_child_weight,
        gamma=xgboost_config.gamma,
        reg_alpha=xgboost_config.reg_alpha,
        reg_lambda=xgboost_config.reg_lambda,
        scale_pos_weight=len(y_train[y_train==0]) / max(1, len(y_train[y_train==1])),
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    # Train with early stopping
    model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_val_scaled, y_val)],
        verbose=False
    )
    
    # Evaluate
    y_pred_proba = model.predict_proba(X_val_scaled)[:, 1]
    y_pred = model.predict(X_val_scaled)
    
    # Compute metrics
    try:
        roc_auc = roc_auc_score(y_val, y_pred_proba)
    except:
        roc_auc = 0.5
        
    try:
        avg_precision = average_precision_score(y_val, y_pred_proba)
    except:
        avg_precision = 0.0
    
    metrics = {
        'roc_auc': roc_auc,
        'avg_precision': avg_precision,
        'train_samples': len(y_train),
        'val_samples': len(y_val),
        'n_features': X.shape[1]
    }
    
    print(f"\n{'='*60}")
    print("TRAINING RESULTS")
    print("="*60)
    print(f"  ROC-AUC Score: {roc_auc:.4f}")
    print(f"  Avg Precision: {avg_precision:.4f}")
    
    # Feature importance
    importance = model.feature_importances_
    feature_names = FeatureEngine().get_feature_names()
    
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': importance
    }).sort_values('importance', ascending=False)
    
    print(f"\n  Top 10 Most Important Features:")
    for i, row in importance_df.head(10).iterrows():
        print(f"    {i+1:2d}. {row['feature']:<35} {row['importance']:.4f}")
    
    return model, scaler, metrics


def save_model(model: xgb.XGBClassifier, scaler: StandardScaler, metrics: Dict) -> None:
    """Save trained model, scaler, and config."""
    print(f"\n{'='*60}")
    print("SAVING MODEL")
    print("="*60)
    
    # Ensure directory exists
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save model
    joblib.dump(model, MODEL_FILE)
    print(f"  ✓ Model saved to: {MODEL_FILE}")
    
    # Save scaler
    joblib.dump(scaler, SCALER_FILE)
    print(f"  ✓ Scaler saved to: {SCALER_FILE}")
    
    # Save feature config
    feature_engine = FeatureEngine()
    config = {
        "feature_names": feature_engine.get_feature_names(),
        "n_features": len(feature_engine.get_feature_names()),
        "training_metrics": metrics,
        "trained_at": datetime.now().isoformat(),
        "model_type": "XGBoost + Heuristics Ensemble",
        "ensemble_reason": (
            "XGBoost learns patterns from historical data while heuristics "
            "encode domain knowledge. Combined, they provide robust predictions "
            "even with limited training data. When both agree, confidence is boosted."
        )
    }
    
    with open(FEATURE_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"  ✓ Config saved to: {FEATURE_CONFIG_FILE}")


def main():
    """Main training pipeline."""
    print("\n" + "="*70)
    print("RAIL-MIND CONFLICT PREDICTOR - MODEL TRAINING v2")
    print("Using FeatureEngine for consistent 28-feature extraction")
    print("="*70)
    
    # Generate training data
    generator = TrainingDataGenerator()
    generator.load_data()
    
    X, y = generator.generate_training_data(
        lookback_minutes=15,
        negative_ratio=3.0
    )
    
    # Train model
    model, scaler, metrics = train_model(X, y)
    
    # Save everything
    save_model(model, scaler, metrics)
    
    # Test prediction
    print(f"\n{'='*60}")
    print("TESTING TRAINED MODEL")
    print("="*60)
    
    # Create test sample
    feature_engine = FeatureEngine()
    test_train = TrainState(
        train_id="TEST_001",
        train_type="regional",
        current_station="MILANO CENTRALE",
        next_station="PAVIA",
        current_delay_sec=300,  # 5 min delay
        position_km=0,
        speed_kmh=60,
        route=[
            {"station_name": "MILANO CENTRALE", "lat": 45.486, "lon": 9.204, "distance_from_previous_km": 0},
            {"station_name": "PAVIA", "lat": 45.188, "lon": 9.144, "distance_from_previous_km": 33.4}
        ],
        current_stop_index=0,
        scheduled_time=datetime.now(),
        actual_time=datetime.now() + timedelta(seconds=300)
    )
    
    test_network = NetworkState(
        simulation_time=datetime.now(),
        trains={"TEST_001": test_train},
        stations={},
        active_conflicts=[]
    )
    
    test_features = feature_engine.compute_features(test_train, test_network, 15)
    test_array = feature_engine.features_to_array(test_features).reshape(1, -1)
    test_scaled = scaler.transform(test_array)
    
    pred_proba = model.predict_proba(test_scaled)[0, 1]
    print(f"  Test train: MILANO CENTRALE → PAVIA, 5 min delay")
    print(f"  ML Prediction: {pred_proba*100:.1f}% conflict probability")
    
    # Risk level
    if pred_proba < 0.3:
        risk = "SAFE (Green)"
    elif pred_proba < 0.5:
        risk = "LOW RISK (Yellow)"
    elif pred_proba < 0.8:
        risk = "HIGH RISK (Orange)"
    else:
        risk = "CRITICAL (Red)"
    print(f"  Risk Level: {risk}")
    
    print("\n" + "="*70)
    print("✓ TRAINING COMPLETE - Model ready for ensemble predictions!")
    print("="*70)


if __name__ == "__main__":
    main()
