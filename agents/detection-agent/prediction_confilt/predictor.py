"""
XGBoost Conflict Predictor
==========================

Main ML model for predicting railway conflicts.
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import warnings

try:
    import xgboost as xgb
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        classification_report, roc_auc_score, 
        precision_recall_curve, average_precision_score
    )
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    warnings.warn("scikit-learn and xgboost not installed. Training disabled.")

try:
    from .config import (
        xgboost_config, conflict_thresholds, prediction_config,
        MODEL_FILE, SCALER_FILE, FEATURE_CONFIG_FILE, MODEL_DIR, CONFLICT_TYPES
    )
    from .feature_engine import FeatureEngine, TrainState, StationState, NetworkState
except ImportError:
    from config import (
        xgboost_config, conflict_thresholds, prediction_config,
        MODEL_FILE, SCALER_FILE, FEATURE_CONFIG_FILE, MODEL_DIR, CONFLICT_TYPES
    )
    from feature_engine import FeatureEngine, TrainState, StationState, NetworkState


@dataclass
class ConflictPrediction:
    """Prediction result for a single train."""
    train_id: str
    probability: float
    risk_level: str
    color: str
    emoji: str
    predicted_conflict_type: Optional[str]
    predicted_time: Optional[datetime]
    predicted_location: Optional[str]
    contributing_factors: List[str]
    confidence: float
    model_used: str = "unknown"  # "xgboost_ensemble", "heuristic", or "fallback"


@dataclass
class PredictionBatch:
    """Batch of predictions for the entire network."""
    timestamp: datetime
    predictions: List[ConflictPrediction]
    network_risk_score: float
    high_risk_trains: List[str]
    critical_trains: List[str]
    recommended_actions: List[str]


class ConflictPredictor:
    """
    XGBoost-based conflict predictor with smart trigger system.
    
    Strategy:
    - SMART TRIGGERS: Predicts when specific conditions are met
      - Train delay exceeds threshold
      - Station approaching capacity
      - Train approaching hub station
      - Periodic baseline check every N minutes
      
    - CONTINUOUS: Predicts every simulation minute (optional)
    
    Features:
    - Graph-aware features capture network topology effects
    - Temporal features model time-of-day patterns
    - Historical patterns from training data
    """
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        scaler_path: Optional[Path] = None,
        auto_load: bool = True
    ):
        """
        Initialize the conflict predictor.
        
        Args:
            model_path: Path to trained XGBoost model
            scaler_path: Path to fitted scaler
            auto_load: Whether to automatically load saved model
        """
        self.model_path = model_path or MODEL_FILE
        self.scaler_path = scaler_path or SCALER_FILE
        
        self.model = None
        self.scaler = None
        self.feature_engine = FeatureEngine()
        self.thresholds = conflict_thresholds
        self.config = prediction_config
        
        # Track last prediction time for smart triggers
        self.last_prediction_time: Dict[str, datetime] = {}
        self.prediction_cache: Dict[str, ConflictPrediction] = {}
        
        # Ensure model directory exists
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
        if auto_load and self.model_path.exists():
            self.load_model()
    
    def _should_predict(
        self,
        train: TrainState,
        network_state: NetworkState
    ) -> Tuple[bool, str]:
        """
        Determine if prediction should run for this train (smart trigger).
        
        Returns:
            Tuple of (should_predict, reason)
        """
        if self.config.strategy == "continuous":
            return True, "continuous_mode"
            
        # Smart trigger checks
        reasons = []
        
        # 1. Delay threshold exceeded
        if train.current_delay_sec > self.config.trigger_delay_threshold_sec:
            reasons.append(f"delay_exceeded_{train.current_delay_sec}s")
            
        # 2. Approaching hub station
        if self.config.trigger_approaching_hub and train.next_station:
            station_props = self.feature_engine.station_properties.get(train.next_station, {})
            if station_props.get("is_major_hub", False):
                # Check if within 5 minutes of arrival
                if train.speed_kmh > 0:
                    next_stop = train.route[train.current_stop_index + 1] if train.current_stop_index < len(train.route) - 1 else None
                    if next_stop:
                        distance = next_stop.get("distance_from_previous_km", 0)
                        time_to_arrival = (distance / train.speed_kmh) * 60  # minutes
                        if time_to_arrival < 10:
                            reasons.append(f"approaching_hub_{train.next_station}")
        
        # 3. Station congestion threshold
        if train.next_station:
            station_state = network_state.stations.get(train.next_station)
            if station_state:
                station_props = self.feature_engine.station_properties.get(train.next_station, {})
                max_trains = station_props.get("max_trains_at_once", 2)
                occupancy = len(station_state.current_trains) / max(max_trains, 1)
                if occupancy > self.config.trigger_congestion_threshold:
                    reasons.append(f"station_congested_{occupancy:.1%}")
        
        # 4. Periodic check (every N minutes)
        last_check = self.last_prediction_time.get(train.train_id)
        if last_check is None:
            reasons.append("initial_prediction")
        else:
            time_since_last = (network_state.simulation_time - last_check).total_seconds()
            if time_since_last >= self.config.continuous_interval_sec * 2:
                reasons.append("periodic_check")
        
        if reasons:
            return True, "|".join(reasons)
        return False, "no_trigger"
    
    def predict(
        self,
        train: TrainState,
        network_state: NetworkState,
        force: bool = False,
        horizon_minutes: Optional[int] = None
    ) -> ConflictPrediction:
        """
        Predict conflict probability for a single train.
        
        Args:
            train: Current train state
            network_state: Current network state
            force: Force prediction even if smart trigger not met
            horizon_minutes: Override prediction horizon (minutes ahead)
            
        Returns:
            ConflictPrediction with probability and risk level
        """
        # Check smart trigger
        should_predict, trigger_reason = self._should_predict(train, network_state)
        
        if not should_predict and not force:
            # Return cached prediction if available
            if train.train_id in self.prediction_cache:
                return self.prediction_cache[train.train_id]
            # Otherwise return safe default
            return self._create_safe_prediction(train)
        
        # Use provided horizon or default
        horizon = horizon_minutes or self.config.prediction_horizon_min
        
        # Compute features
        features = self.feature_engine.compute_features(
            train, network_state, horizon
        )
        feature_array = self.feature_engine.features_to_array(features)
        
        # ENSEMBLE APPROACH: Combine XGBoost + Heuristics
        # Only use ML if ensemble is enabled, model exists, and features match
        use_ml = (
            self.config.use_ensemble and
            self.model is not None and 
            SKLEARN_AVAILABLE and 
            self.scaler is not None
        )
        
        model_used = "heuristic"
        
        if use_ml:
            try:
                # Try to use ML model with ensemble
                feature_array_scaled = self.scaler.transform(feature_array.reshape(1, -1))
                ml_probability = float(self.model.predict_proba(feature_array_scaled)[0, 1])
                heuristic_probability = self._heuristic_probability(features)
                
                # ENSEMBLE: Weighted combination
                probability = (self.config.ml_weight * ml_probability + 
                             self.config.heuristic_weight * heuristic_probability)
                
                # Boost if both agree on high risk
                if (ml_probability > self.config.agreement_threshold and 
                    heuristic_probability > self.config.agreement_threshold):
                    probability = min(0.95, probability * self.config.agreement_boost)
                
                model_used = "xgboost_ensemble"
            except Exception as e:
                # Fallback to heuristics if ML fails (feature mismatch, etc.)
                print(f"[WARN] ML prediction failed, using heuristics only: {e}")
                probability = self._heuristic_probability(features)
                model_used = "heuristic_fallback"
        else:
            # Use pure heuristics (ensemble disabled or model unavailable)
            probability = self._heuristic_probability(features)
            model_used = "heuristic"
        
        # Determine risk level and color
        risk_level, color, emoji = self._get_risk_level(probability)
        
        # Determine predicted conflict type based on features
        conflict_type = self._predict_conflict_type(features, probability)
        
        # Get contributing factors
        contributing_factors = self._get_contributing_factors(features, probability)
        
        # Estimate conflict time
        predicted_time = None
        if probability > self.thresholds.low_risk_threshold:
            minutes_ahead = self.config.prediction_horizon_min * (1 - probability)
            predicted_time = network_state.simulation_time + timedelta(minutes=minutes_ahead)
        
        prediction = ConflictPrediction(
            train_id=train.train_id,
            probability=probability,
            risk_level=risk_level,
            color=color,
            emoji=emoji,
            predicted_conflict_type=conflict_type,
            predicted_time=predicted_time,
            predicted_location=train.next_station,
            contributing_factors=contributing_factors,
            confidence=self._calculate_confidence(features, probability),
            model_used=model_used
        )
        
        # Update tracking
        self.last_prediction_time[train.train_id] = network_state.simulation_time
        self.prediction_cache[train.train_id] = prediction
        
        return prediction
    
    def predict_batch(self, network_state: NetworkState) -> PredictionBatch:
        """
        Predict conflicts for all trains in the network.
        
        Args:
            network_state: Current state of the entire network
            
        Returns:
            PredictionBatch with all predictions and summary
        """
        predictions = []
        
        for train_id, train in network_state.trains.items():
            prediction = self.predict(train, network_state)
            predictions.append(prediction)
        
        # Calculate network-level metrics
        if predictions:
            probabilities = [p.probability for p in predictions]
            network_risk_score = np.mean(probabilities)
        else:
            network_risk_score = 0.0
        
        high_risk_trains = [
            p.train_id for p in predictions 
            if p.risk_level in ["high_risk", "critical"]
        ]
        
        critical_trains = [
            p.train_id for p in predictions 
            if p.risk_level == "critical"
        ]
        
        # Generate recommended actions
        recommended_actions = self._generate_recommendations(predictions, network_state)
        
        return PredictionBatch(
            timestamp=network_state.simulation_time,
            predictions=predictions,
            network_risk_score=network_risk_score,
            high_risk_trains=high_risk_trains,
            critical_trains=critical_trains,
            recommended_actions=recommended_actions
        )
    
    def _get_risk_level(self, probability: float) -> Tuple[str, str, str]:
        """
        Determine risk level, color, and emoji from probability.
        
        Returns:
            Tuple of (risk_level_name, hex_color, emoji)
        """
        levels = self.thresholds.risk_levels
        
        if probability < self.thresholds.safe_threshold:
            level = levels["safe"]
            return "safe", level["color"], level["emoji"]
        elif probability < self.thresholds.low_risk_threshold:
            level = levels["low_risk"]
            return "low_risk", level["color"], level["emoji"]
        elif probability < self.thresholds.high_risk_threshold:
            level = levels["high_risk"]
            return "high_risk", level["color"], level["emoji"]
        else:
            level = levels["critical"]
            return "critical", level["color"], level["emoji"]
    
    def _heuristic_probability(self, features: Dict[str, float]) -> float:
        """
        Calculate conflict probability using heuristics when model unavailable.
        
        This provides reasonable predictions based on domain knowledge.
        """
        prob = 0.1  # Base probability
        
        # Delay contributes significantly
        delay_sec = features.get("current_delay_sec", 0)
        if delay_sec > 300:  # > 5 min
            prob += 0.25
        elif delay_sec > 120:  # > 2 min
            prob += 0.15
        elif delay_sec > 60:  # > 1 min
            prob += 0.05
        
        # Station congestion
        occupancy = features.get("current_occupancy", 0)
        prob += occupancy * 0.2
        
        # Platform utilization
        platform_util = features.get("platform_utilization", 0)
        if platform_util > 0.8:
            prob += 0.15
        
        # Competing trains
        competing = features.get("competing_trains_count", 0)
        prob += min(competing * 0.05, 0.2)
        
        # Peak hour amplifies everything
        if features.get("is_peak_hour", 0):
            prob *= 1.3
        
        # Hub stations are riskier
        if features.get("is_major_hub", 0):
            prob *= 1.2
        
        # Upstream congestion propagates
        upstream = features.get("upstream_congestion", 0)
        prob += upstream * 0.1
        
        return min(prob, 0.99)
    
    def _predict_conflict_type(
        self,
        features: Dict[str, float],
        probability: float
    ) -> Optional[str]:
        """Predict the most likely conflict type based on features."""
        if probability < self.thresholds.safe_threshold:
            return None
        
        # Score each conflict type
        type_scores = {}
        
        # Platform conflict: high platform utilization + multiple expected arrivals
        type_scores["platform_conflict"] = (
            features.get("platform_utilization", 0) * 0.5 +
            min(features.get("expected_arrivals_15min", 0) / 3, 1) * 0.5
        )
        
        # Track conflict: high segment utilization
        type_scores["track_conflict"] = features.get("segment_utilization", 0)
        
        # Headway violation: competing trains + delay
        type_scores["headway_violation"] = (
            min(features.get("competing_trains_count", 0) / 3, 1) * 0.6 +
            min(features.get("current_delay_sec", 0) / 300, 1) * 0.4
        )
        
        # Capacity exceeded: high occupancy
        type_scores["capacity_exceeded"] = features.get("current_occupancy", 0)
        
        # Schedule deviation: high delay
        type_scores["schedule_deviation"] = min(
            features.get("current_delay_sec", 0) / 600, 1
        )
        
        # Cascading delay: upstream congestion + delay
        type_scores["cascading_delay"] = (
            features.get("upstream_congestion", 0) * 0.5 +
            min(features.get("current_delay_sec", 0) / 300, 1) * 0.5
        )
        
        # Return highest scoring type
        if type_scores:
            return max(type_scores, key=type_scores.get)
        return None
    
    def _get_contributing_factors(
        self,
        features: Dict[str, float],
        probability: float
    ) -> List[str]:
        """Identify key factors contributing to conflict risk."""
        factors = []
        
        if features.get("current_delay_sec", 0) > 120:
            delay_min = features["current_delay_sec"] / 60
            factors.append(f"Train delayed by {delay_min:.0f} minutes")
        
        occupancy = features.get("current_occupancy", 0)
        if occupancy > 0.7:
            factors.append(f"Station at {occupancy:.0%} capacity")
        
        if features.get("platform_utilization", 0) > 0.8:
            factors.append("Limited platform availability")
        
        competing = features.get("competing_trains_count", 0)
        if competing > 0:
            factors.append(f"{competing} trains competing for same destination")
        
        if features.get("upstream_congestion", 0) > 0.5:
            factors.append("Upstream congestion detected")
        
        if features.get("is_peak_hour", 0):
            factors.append("Peak hour traffic")
        
        if features.get("is_major_hub", 0):
            factors.append("Approaching major hub station")
        
        arrivals = features.get("expected_arrivals_15min", 0)
        if arrivals > 2:
            factors.append(f"{arrivals} trains expected in next 15 minutes")
        
        return factors[:5]  # Limit to top 5 factors
    
    def _calculate_confidence(
        self,
        features: Dict[str, float],
        probability: float
    ) -> float:
        """Calculate confidence score for the prediction."""
        # Base confidence from model calibration
        if self.model is not None:
            base_confidence = 0.85
        else:
            base_confidence = 0.6  # Lower for heuristic
        
        # Reduce confidence at probability boundaries
        prob_distance = min(
            abs(probability - 0.3),
            abs(probability - 0.5),
            abs(probability - 0.8)
        )
        boundary_penalty = max(0, 0.1 - prob_distance) * 2
        
        # Reduce confidence when features have extreme values
        feature_confidence = 1.0
        if features.get("current_delay_sec", 0) > 600:
            feature_confidence -= 0.1  # Very high delays are harder to predict
        
        return min(base_confidence - boundary_penalty, feature_confidence)
    
    def _create_safe_prediction(self, train: TrainState) -> ConflictPrediction:
        """Create a safe (green) prediction for trains without triggers."""
        level = self.thresholds.risk_levels["safe"]
        return ConflictPrediction(
            train_id=train.train_id,
            probability=0.1,
            risk_level="safe",
            color=level["color"],
            emoji=level["emoji"],
            predicted_conflict_type=None,
            predicted_time=None,
            predicted_location=None,
            contributing_factors=[],
            confidence=0.9
        )
    
    def _generate_recommendations(
        self,
        predictions: List[ConflictPrediction],
        network_state: NetworkState
    ) -> List[str]:
        """Generate actionable recommendations based on predictions."""
        recommendations = []
        
        critical = [p for p in predictions if p.risk_level == "critical"]
        high_risk = [p for p in predictions if p.risk_level == "high_risk"]
        
        if critical:
            recommendations.append(
                f"🔴 IMMEDIATE: {len(critical)} trains require immediate attention"
            )
            for p in critical[:3]:
                if p.predicted_conflict_type == "platform_conflict":
                    recommendations.append(
                        f"  → {p.train_id}: Reassign platform at {p.predicted_location}"
                    )
                elif p.predicted_conflict_type == "track_conflict":
                    recommendations.append(
                        f"  → {p.train_id}: Hold or reroute to avoid track conflict"
                    )
                else:
                    recommendations.append(
                        f"  → {p.train_id}: Review schedule at {p.predicted_location}"
                    )
        
        if high_risk:
            recommendations.append(
                f"🟠 WARNING: Monitor {len(high_risk)} high-risk trains"
            )
        
        # Check for station-level issues
        congested_stations = set()
        for p in predictions:
            if p.predicted_location and p.probability > 0.5:
                congested_stations.add(p.predicted_location)
        
        if congested_stations:
            recommendations.append(
                f"📍 Stations requiring attention: {', '.join(list(congested_stations)[:3])}"
            )
        
        return recommendations
    
    # =========================================================================
    # MODEL TRAINING (requires sklearn and xgboost)
    # =========================================================================
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2
    ) -> Dict[str, Any]:
        """
        Train the XGBoost model on historical data.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (0=no conflict, 1=conflict)
            validation_split: Fraction for validation
            
        Returns:
            Dictionary with training metrics
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn and xgboost required for training")
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=42, stratify=y
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # Create and train model
        self.model = xgb.XGBClassifier(
            n_estimators=xgboost_config.n_estimators,
            max_depth=xgboost_config.max_depth,
            learning_rate=xgboost_config.learning_rate,
            min_child_weight=xgboost_config.min_child_weight,
            subsample=xgboost_config.subsample,
            colsample_bytree=xgboost_config.colsample_bytree,
            gamma=xgboost_config.gamma,
            reg_alpha=xgboost_config.reg_alpha,
            reg_lambda=xgboost_config.reg_lambda,
            scale_pos_weight=xgboost_config.scale_pos_weight,
            random_state=xgboost_config.random_state,
            n_jobs=xgboost_config.n_jobs,
            eval_metric=xgboost_config.eval_metric,
            early_stopping_rounds=xgboost_config.early_stopping_rounds,
            use_label_encoder=False
        )
        
        self.model.fit(
            X_train_scaled, y_train,
            eval_set=[(X_val_scaled, y_val)],
            verbose=False
        )
        
        # Evaluate
        y_pred_proba = self.model.predict_proba(X_val_scaled)[:, 1]
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        metrics = {
            "roc_auc": roc_auc_score(y_val, y_pred_proba),
            "avg_precision": average_precision_score(y_val, y_pred_proba),
            "classification_report": classification_report(y_val, y_pred, output_dict=True),
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "positive_rate_train": y_train.mean(),
            "positive_rate_val": y_val.mean()
        }
        
        # Feature importance
        feature_names = self.feature_engine.get_feature_names()
        importance = dict(zip(feature_names, self.model.feature_importances_))
        metrics["feature_importance"] = dict(
            sorted(importance.items(), key=lambda x: x[1], reverse=True)
        )
        
        return metrics
    
    def save_model(self, model_path: Optional[Path] = None, scaler_path: Optional[Path] = None):
        """Save trained model and scaler to disk."""
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn required for saving models")
        
        model_path = model_path or self.model_path
        scaler_path = scaler_path or self.scaler_path
        
        if self.model is not None:
            joblib.dump(self.model, model_path)
            
        if self.scaler is not None:
            joblib.dump(self.scaler, scaler_path)
        
        # Save feature config
        feature_config = {
            "feature_names": self.feature_engine.get_feature_names(),
            "thresholds": asdict(self.thresholds),
            "prediction_config": asdict(self.config)
        }
        with open(FEATURE_CONFIG_FILE, 'w') as f:
            json.dump(feature_config, f, indent=2, default=str)
    
    def load_model(self, model_path: Optional[Path] = None, scaler_path: Optional[Path] = None):
        """Load trained model and scaler from disk."""
        if not SKLEARN_AVAILABLE:
            warnings.warn("scikit-learn not available, using heuristic predictions")
            return
        
        model_path = model_path or self.model_path
        scaler_path = scaler_path or self.scaler_path
        
        if model_path.exists():
            self.model = joblib.load(model_path)
            print(f"[OK] Loaded XGBoost model from {model_path}")
            
            # Print prediction mode
            if self.config.use_ensemble:
                print(f"[INFO] Using ENSEMBLE mode: {self.config.ml_weight:.0%} ML + {self.config.heuristic_weight:.0%} Heuristics")
                print(f"[INFO] Agreement boost: {self.config.agreement_boost}x when both predict risk > {self.config.agreement_threshold:.0%}")
            else:
                print("[INFO] Using PURE ML mode (XGBoost only)")
        else:
            print(f"[WARN] Model file not found at {model_path}")
            print("[INFO] Using PURE HEURISTICS mode (no ML)")
        
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
            print(f"[OK] Loaded feature scaler from {scaler_path}")


# Convenience function for batch prediction
def predict_conflicts(
    network_state: NetworkState,
    predictor: Optional[ConflictPredictor] = None
) -> PredictionBatch:
    """
    Convenience function to predict conflicts for entire network.
    
    Args:
        network_state: Current state of the rail network
        predictor: Optional pre-initialized predictor
        
    Returns:
        PredictionBatch with all predictions
    """
    if predictor is None:
        predictor = ConflictPredictor()
    
    return predictor.predict_batch(network_state)
