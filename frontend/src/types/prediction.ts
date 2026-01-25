/**
 * Conflict Prediction Types
 * =========================
 *
 * TypeScript types for the ML-based conflict prediction system.
 */

// Risk levels with color coding
export type RiskLevel = 'safe' | 'low_risk' | 'high_risk' | 'critical';

export interface RiskLevelConfig {
  color: string;
  label: string;
  emoji: string;
}

export const RISK_LEVELS: Record<RiskLevel, RiskLevelConfig> = {
  safe: { color: '#10b981', label: 'Safe', emoji: '🟢' },
  low_risk: { color: '#f59e0b', label: 'Low Risk', emoji: '🟡' },
  high_risk: { color: '#f97316', label: 'High Risk', emoji: '🟠' },
  critical: { color: '#dc2626', label: 'Critical', emoji: '🔴' },
};

// Operational conflict types
export type ConflictType =
  | 'platform_conflict'
  | 'track_conflict'
  | 'headway_violation'
  | 'capacity_exceeded'
  | 'schedule_deviation'
  | 'cascading_delay';

// Incident types (from historical data)
export type IncidentType =
  | 'technical'
  | 'trespasser'
  | 'weather'
  | 'maintenance'
  | 'fire'
  | 'police_intervention'
  | 'other';

export const CONFLICT_TYPE_LABELS: Record<ConflictType, string> = {
  platform_conflict: 'Platform Conflict',
  track_conflict: 'Track Conflict',
  headway_violation: 'Headway Violation',
  capacity_exceeded: 'Capacity Exceeded',
  schedule_deviation: 'Schedule Deviation',
  cascading_delay: 'Cascading Delay',
};

export const INCIDENT_TYPE_LABELS: Record<IncidentType, string> = {
  technical: 'Technical Failure',
  trespasser: 'Trespasser Alert',
  weather: 'Weather Event',
  maintenance: 'Maintenance Work',
  fire: 'Fire Incident',
  police_intervention: 'Police Intervention',
  other: 'Other Incident',
};

export const INCIDENT_TYPE_ICONS: Record<IncidentType, string> = {
  technical: '⚙️',
  trespasser: '🚷',
  weather: '🌧️',
  maintenance: '🔧',
  fire: '🔥',
  police_intervention: '👮',
  other: '⚠️',
};

// Prediction for a single train
export interface ConflictPrediction {
  train_id: string;
  probability: number;
  risk_level: RiskLevel;
  color: string;
  emoji: string;
  predicted_conflict_type: ConflictType | null;
  predicted_incident_type?: IncidentType | null;  // New: underlying incident cause
  predicted_time: string | null; // ISO datetime
  predicted_location: string | null;
  contributing_factors: string[];
  confidence: number;
  model_used?: string;  // "xgboost_ensemble" | "heuristic" | "detection"
}

// Batch prediction response
export interface BatchPrediction {
  timestamp: string; // ISO datetime
  predictions: ConflictPrediction[];
  network_risk_score: number;
  high_risk_trains: string[];
  critical_trains: string[];
  recommended_actions: string[];
  model_used?: string;   // Primary model used
  strategy?: string;     // "continuous" | "smart"
}

// Similar historical case from Qdrant
export interface SimilarCase {
  case_id: string;
  similarity_score: number;
  date: string;
  line: string;
  location: string;
  incident_type: string;
  delay_duration_min: number;
  affected_trains: number;
  resolution_types: string[];
  resolution_description: string;
  time_of_day: string;
  severity_score: number;
}

// Memory search response
export interface MemorySearchResult {
  query_train_id: string;
  query_conflict_type: string;
  query_location: string;
  similar_cases: SimilarCase[];
  suggested_resolution: string | null;
  typical_delay_min: number;
  confidence: number;
}

// Train state for simulation
export interface TrainState {
  train_id: string;
  train_type: string;
  current_station: string;
  next_station: string | null;
  current_delay_sec: number;
  position_km: number;
  speed_kmh: number;
  route: RouteStop[];
  current_stop_index: number;
  scheduled_time: string;
  actual_time: string;
}

export interface RouteStop {
  station_name: string;
  station_order: number;
  lat: number;
  lon: number;
  distance_from_previous_km: number;
}

// Station state
export interface StationState {
  station_id: string;
  name: string;
  current_trains: string[];
  platform_occupancy: Record<number, string | null>;
  expected_arrivals: Array<{ train_id: string; time: string }>;
  expected_departures: Array<{ train_id: string; time: string }>;
}

// Network state for API request
export interface NetworkState {
  simulation_time: string;
  trains: Record<string, TrainState>;
  stations: Record<string, StationState>;
  active_conflicts: any[];
}

// API status
export interface SystemStatus {
  status: string;
  model_loaded: boolean;
  qdrant_connected: boolean;
  prediction_strategy: string;
  active_websockets: number;
  last_prediction_time: string | null;
}

// Prediction thresholds
export interface PredictionThresholds {
  safe_threshold: number;
  low_risk_threshold: number;
  high_risk_threshold: number;
  risk_levels: Record<RiskLevel, RiskLevelConfig>;
}

// Alert for UI
export interface ConflictAlert {
  id: string;
  train_id: string;
  type: ConflictType | 'unknown';
  title: string;
  location: string;
  time: string; // Display time (e.g., "In 8 minutes")
  predictedTime: Date | null;
  probability: number;
  severity: RiskLevel;
  contributingFactors: string[];
  similarCasesCount: number;
  suggestedResolution: string | null;
  confidence: number;
}

// Helper functions
export function getRiskLevel(probability: number): RiskLevel {
  if (probability < 0.3) return 'safe';
  if (probability < 0.5) return 'low_risk';
  if (probability < 0.8) return 'high_risk';
  return 'critical';
}

export function formatTimeUntil(predictedTime: string | null): string {
  if (!predictedTime) return 'Unknown';
  
  const predicted = new Date(predictedTime);
  const now = new Date();
  const diffMs = predicted.getTime() - now.getTime();
  const diffMin = Math.round(diffMs / 60000);
  
  if (diffMin <= 0) return 'Now';
  if (diffMin === 1) return 'In 1 minute';
  if (diffMin < 60) return `In ${diffMin} minutes`;
  
  const hours = Math.floor(diffMin / 60);
  return `In ${hours}h ${diffMin % 60}m`;
}

export function predictionToAlert(
  prediction: ConflictPrediction,
  similarCasesCount: number = 0,
  suggestedResolution: string | null = null
): ConflictAlert {
  return {
    id: `alert-${prediction.train_id}-${Date.now()}`,
    train_id: prediction.train_id,
    type: prediction.predicted_conflict_type || 'unknown',
    title: prediction.predicted_conflict_type
      ? CONFLICT_TYPE_LABELS[prediction.predicted_conflict_type]
      : 'Potential Conflict',
    location: prediction.predicted_location || 'Unknown',
    time: formatTimeUntil(prediction.predicted_time),
    predictedTime: prediction.predicted_time ? new Date(prediction.predicted_time) : null,
    probability: prediction.probability,
    severity: prediction.risk_level,
    contributingFactors: prediction.contributing_factors,
    similarCasesCount,
    suggestedResolution,
    confidence: prediction.confidence,
  };
}
