"""
XGBoost Model Training Script
==============================

Trains a conflict prediction model using historical incident and operation data.

Training Data Creation:
1. Extract features from operation data around incident times
2. Label moments before incidents as "conflict=1" 
3. Label normal operations as "conflict=0"
4. Train XGBoost classifier
5. Save model for deployment

Usage:
    python train_model.py
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import warnings

try:
    from config import (
        FAULT_DATA, OPERATION_DATA, STATION_DATA,
        MODEL_FILE, SCALER_FILE, FEATURE_CONFIG_FILE,
        xgboost_config, LOMBARDY_MAJOR_HUBS
    )
    from predictor import ConflictPredictor
    from feature_engine import FeatureEngine, TrainState, NetworkState
except ImportError:
    from .config import (
        FAULT_DATA, OPERATION_DATA, STATION_DATA,
        MODEL_FILE, SCALER_FILE, FEATURE_CONFIG_FILE,
        xgboost_config, LOMBARDY_MAJOR_HUBS
    )
    from .predictor import ConflictPredictor
    from .feature_engine import FeatureEngine, TrainState, NetworkState


class ConflictDataGenerator:
    """
    Generate labeled training data from historical incidents and operations.
    """
    
    def __init__(self):
        self.feature_engine = FeatureEngine()
        self.incidents = None
        self.operations = None
        self.stations = None
        
    def load_data(self):
        """Load historical incident and operation data."""
        print("Loading historical data...")
        
        # Load fault/incident data
        if FAULT_DATA.exists():
            with open(FAULT_DATA, 'r', encoding='utf-8') as f:
                self.incidents = json.load(f)
            print(f"  ✓ Loaded {len(self.incidents)} incident records")
        else:
            print(f"  ✗ Fault data not found: {FAULT_DATA}")
            self.incidents = []
        
        # Load operation data
        if OPERATION_DATA.exists():
            self.operations = pd.read_csv(OPERATION_DATA)
            print(f"  ✓ Loaded {len(self.operations)} operation records")
        else:
            print(f"  ✗ Operation data not found: {OPERATION_DATA}")
            self.operations = pd.DataFrame()
        
        # Load station data
        if STATION_DATA.exists():
            self.stations = pd.read_csv(STATION_DATA)
            print(f"  ✓ Loaded {len(self.stations)} station records")
        else:
            print(f"  ✗ Station data not found: {STATION_DATA}")
            self.stations = pd.DataFrame()
    
    def create_conflict_samples(self, lookback_minutes: int = 15) -> Tuple[List[Dict], List[int]]:
        """
        Create positive samples (conflict=1) from incidents.
        
        Extract features from operation data X minutes before incidents.
        
        Args:
            lookback_minutes: How many minutes before incident to sample
            
        Returns:
            Tuple of (features_list, labels_list)
        """
        samples = []
        labels = []
        
        print(f"\nCreating conflict samples (lookback={lookback_minutes} min)...")
        
        # Filter for Lombardy incidents only
        lombardy_incidents = [
            inc for inc in self.incidents 
            if inc.get('matched_region') == 'Lombardy' or 
               any(hub in (inc.get('matched_station') or '') for hub in LOMBARDY_MAJOR_HUBS)
        ]
        
        print(f"  Found {len(lombardy_incidents)} Lombardy incidents")
        
        for incident in lombardy_incidents:
            try:
                # Parse incident time
                incident_time_str = incident.get('incident_datetime')
                if not incident_time_str:
                    continue
                
                incident_time = pd.to_datetime(incident_time_str)
                
                # Create feature snapshot at lookback time
                sample_time = incident_time - pd.Timedelta(minutes=lookback_minutes)
                
                # Extract features
                features = self._extract_features_at_time(
                    sample_time, 
                    incident.get('matched_station'),
                    incident.get('incident_type'),
                    incident.get('delay_duration_min', 0)
                )
                
                if features:
                    samples.append(features)
                    labels.append(1)  # Conflict = 1
                    
            except Exception as e:
                continue
        
        print(f"  Created {len(samples)} positive samples (conflict=1)")
        return samples, labels
    
    def create_normal_samples(self, num_samples: int = None) -> Tuple[List[Dict], List[int]]:
        """
        Create negative samples (conflict=0) from normal operations.
        
        Sample from operation data where no incident occurred.
        
        Args:
            num_samples: Number of normal samples to create (default: 3x conflicts)
            
        Returns:
            Tuple of (features_list, labels_list)
        """
        samples = []
        labels = []
        
        print(f"\nCreating normal operation samples...")
        
        if self.operations.empty:
            print("  ✗ No operation data available")
            return samples, labels
        
        # Convert incident times to set for fast lookup
        incident_datetimes = []
        for inc in self.incidents:
            try:
                t = pd.to_datetime(inc.get('incident_datetime'))
                incident_datetimes.append(t)
            except:
                continue
        
        # Sample random rows from operations
        # We'll sample more than needed and filter
        sample_size = min((num_samples or 1000) * 3, len(self.operations))
        sampled_ops = self.operations.sample(n=sample_size, random_state=42)
        
        print(f"  Sampled {len(sampled_ops)} operations to process...")
        
        for idx, row in sampled_ops.iterrows():
            if len(samples) >= (num_samples or 1000):
                break
                
            try:
                # Parse timestamp from actual arrival time
                date_str = row.get('date')
                time_str = row.get('actual_arrival_time')
                
                if pd.isna(date_str) or pd.isna(time_str):
                    continue
                
                sample_time = pd.to_datetime(f"{date_str} {time_str}")
                
                # Skip if within 30 minutes of any incident
                too_close = False
                for inc_time in incident_datetimes:
                    time_diff = abs((sample_time - inc_time).total_seconds() / 60)
                    if time_diff < 30:
                        too_close = True
                        break
                
                if too_close:
                    continue
                
                # Parse delay - handle both string 'N' and numeric values
                delay_val = row.get('arrival_delay_min', 0)
                if pd.isna(delay_val):
                    delay_val = 0
                else:
                    try:
                        delay_val = float(delay_val)
                    except:
                        delay_val = 0
                
                # Extract features
                features = self._extract_features_at_time(
                    sample_time,
                    row.get('station_name'),
                    None,  # No incident type for normal operations
                    delay_val
                )
                
                if features:
                    samples.append(features)
                    labels.append(0)  # No conflict = 0
                    
            except Exception as e:
                # print(f"  ✗ Error processing row: {e}")
                continue
        
        print(f"  Created {len(samples)} negative samples (conflict=0)")
        return samples, labels
    
    def _extract_features_at_time(
        self, 
        timestamp: pd.Timestamp, 
        station: str, 
        incident_type: str = None,
        delay_minutes: float = 0
    ) -> Dict[str, float]:
        """
        Extract feature vector at a specific timestamp.
        
        Simulates what features would be available for prediction.
        """
        features = {}
        
        try:
            # Temporal features
            features['hour_of_day'] = timestamp.hour
            features['day_of_week'] = timestamp.dayofweek
            features['is_weekend'] = 1 if timestamp.dayofweek >= 5 else 0
            features['is_peak_hour'] = 1 if timestamp.hour in [7, 8, 9, 17, 18, 19] else 0
            
            # Delay features
            features['current_delay_sec'] = delay_minutes * 60
            features['delay_category'] = (
                3 if delay_minutes > 10 else
                2 if delay_minutes > 5 else
                1 if delay_minutes > 2 else 0
            )
            
            # Station features
            if station:
                features['is_major_hub'] = 1 if station in LOMBARDY_MAJOR_HUBS else 0
                features['station_hash'] = hash(station) % 100 / 100  # Normalize
            else:
                features['is_major_hub'] = 0
                features['station_hash'] = 0.5
            
            # Incident type encoding (for conflict samples)
            incident_types = ['technical', 'trespasser', 'weather', 'maintenance', 'fire', 'police_intervention', 'other']
            for i, inc_type in enumerate(incident_types):
                features[f'incident_type_{inc_type}'] = 1 if incident_type == inc_type else 0
            
            # Network context (simplified)
            features['network_hour_delay_avg'] = delay_minutes  # Proxy for network state
            features['competing_trains_estimate'] = min(10, int(delay_minutes / 2))  # Heuristic
            
            # Speed/progress features
            features['estimated_speed_kmh'] = max(0, 100 - delay_minutes * 5)  # Slower with delay
            features['progress_factor'] = np.random.uniform(0.3, 0.9)  # Random progress
            
            return features
            
        except Exception as e:
            return {}
    
    def generate_training_data(self, lookback_minutes: int = 15) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate complete training dataset.
        
        Returns:
            Tuple of (X_features, y_labels)
        """
        print("\n" + "="*60)
        print("GENERATING TRAINING DATA")
        print("="*60)
        
        # Create conflict samples
        conflict_samples, conflict_labels = self.create_conflict_samples(lookback_minutes)
        
        # Create 3x more normal samples for class balance
        num_normal = len(conflict_samples) * 3
        normal_samples, normal_labels = self.create_normal_samples(num_normal)
        
        # Combine
        all_samples = conflict_samples + normal_samples
        all_labels = conflict_labels + normal_labels
        
        if not all_samples:
            raise ValueError("No training samples generated!")
        
        # Convert to numpy arrays
        feature_names = sorted(all_samples[0].keys())
        X = np.array([[sample.get(fname, 0) for fname in feature_names] for sample in all_samples])
        y = np.array(all_labels)
        
        print(f"\n{'='*60}")
        print(f"TRAINING DATA SUMMARY")
        print(f"{'='*60}")
        print(f"  Total samples: {len(X)}")
        print(f"  Positive (conflict=1): {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
        print(f"  Negative (conflict=0): {len(y)-sum(y)} ({(len(y)-sum(y))/len(y)*100:.1f}%)")
        print(f"  Features: {len(feature_names)}")
        print(f"  Feature names: {', '.join(feature_names[:10])}...")
        
        return X, y


def main():
    """Main training pipeline."""
    print("\n" + "="*70)
    print("RAIL-MIND CONFLICT PREDICTOR - MODEL TRAINING")
    print("="*70)
    
    # Step 1: Generate training data
    generator = ConflictDataGenerator()
    generator.load_data()
    
    X, y = generator.generate_training_data(lookback_minutes=15)
    
    # Step 2: Train model
    print(f"\n{'='*60}")
    print("TRAINING XGBOOST MODEL")
    print(f"{'='*60}")
    
    predictor = ConflictPredictor(auto_load=False)
    metrics = predictor.train(X, y, validation_split=0.2)
    
    print(f"\n{'='*60}")
    print("TRAINING RESULTS")
    print(f"{'='*60}")
    print(f"  ROC-AUC Score: {metrics['roc_auc']:.4f}")
    print(f"  Avg Precision: {metrics['avg_precision']:.4f}")
    print(f"  Training samples: {metrics['train_samples']}")
    print(f"  Validation samples: {metrics['val_samples']}")
    
    # Classification report
    report = metrics['classification_report']
    print(f"\n  Classification Report:")
    print(f"    Precision (conflict=1): {report['1']['precision']:.3f}")
    print(f"    Recall (conflict=1):    {report['1']['recall']:.3f}")
    print(f"    F1-Score (conflict=1):  {report['1']['f1-score']:.3f}")
    
    # Top features
    print(f"\n  Top 10 Most Important Features:")
    for i, (feat, importance) in enumerate(list(metrics['feature_importance'].items())[:10], 1):
        print(f"    {i:2d}. {feat:30s} {importance:.4f}")
    
    # Step 3: Save model
    print(f"\n{'='*60}")
    print("SAVING MODEL")
    print(f"{'='*60}")
    
    predictor.save_model()
    print(f"  ✓ Model saved to: {MODEL_FILE}")
    print(f"  ✓ Scaler saved to: {SCALER_FILE}")
    print(f"  ✓ Config saved to: {FEATURE_CONFIG_FILE}")
    
    # Step 4: Test prediction
    print(f"\n{'='*60}")
    print("TESTING TRAINED MODEL")
    print(f"{'='*60}")
    
    # Create a test scenario
    test_features = X[0].reshape(1, -1)
    test_label = y[0]
    
    # Scale and predict
    test_scaled = predictor.scaler.transform(test_features)
    test_proba = predictor.model.predict_proba(test_scaled)[0, 1]
    
    print(f"  Test sample label: {test_label} (actual)")
    print(f"  Model prediction: {test_proba:.3f} probability")
    print(f"  Risk level: {'CONFLICT' if test_proba > 0.5 else 'SAFE'}")
    
    print(f"\n{'='*70}")
    print("✓ TRAINING COMPLETE - Model ready for deployment!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
