/**
 * Unified Simulation Hook
 * =======================
 *
 * React hook for interacting with the unified API that combines
 * ML prediction with deterministic detection.
 *
 * This hook provides:
 * - Real-time train positions
 * - Predictions (10-30 min ahead, shown in orange)
 * - Detections (real-time conflicts, shown in red)
 * - Automatic polling for continuous updates
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// =============================================================================
// Types
// =============================================================================

export interface TrainData {
  train_id: string;
  train_type: string;
  current_station: string | null;
  next_station: string | null;
  current_edge: string | null;
  position_km: number;
  speed_kmh: number;
  delay_sec: number;
  status: string;
  lat: number;
  lon: number;
  route: Array<{
    station_name: string;
    lat: number;
    lon: number;
    distance_from_previous_km?: number;
  }>;
  current_stop_index: number;
}

export interface UnifiedConflict {
  conflict_id: string;
  source: 'prediction' | 'detection';
  conflict_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  probability: number;
  location: string;
  location_type: 'station' | 'edge' | 'network';
  involved_trains: string[];
  explanation: string;
  timestamp: string;
  prediction_horizon_min?: number;
  resolution_suggestions: string[];
  lat?: number;
  lon?: number;
}

export interface SimulationState {
  simulation_time: string;
  tick_number: number;
  trains: TrainData[];
  predictions: UnifiedConflict[];
  detections: UnifiedConflict[];
  statistics: {
    trains_total: number;
    trains_at_station: number;
    trains_en_route: number;
    trains_delayed: number;
    active_predictions: number;
    tick_number: number;
    simulation_time: string;
  };
}

export interface StationPredictions {
  station_id: string;
  station_info: {
    id: string;
    name: string;
    lat: number;
    lon: number;
    region: string;
    platforms: number;
  } | null;
  predictions: UnifiedConflict[];
  trains: TrainData[];
  risk_level: {
    level: 'safe' | 'low' | 'medium' | 'high' | 'critical';
    color: string;
    max_probability: number;
  };
}

export interface RegionData {
  region: string;
  stations: Array<{
    id: string;
    name: string;
    lat: number;
    lon: number;
    region: string;
    platforms: number;
  }>;
  trains: TrainData[];
  predictions: UnifiedConflict[];
  summary: {
    total_stations: number;
    total_trains: number;
    active_predictions: number;
    high_risk_count: number;
  };
}

interface UseUnifiedSimulationOptions {
  autoStart?: boolean;
  tickInterval?: number; // ms between ticks
  apiUrl?: string;
}

interface UseUnifiedSimulationReturn {
  // State
  state: SimulationState | null;
  trains: TrainData[];
  predictions: UnifiedConflict[];
  detections: UnifiedConflict[];
  isRunning: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  start: () => void;
  stop: () => void;
  tick: () => Promise<void>;
  multiTick: (count: number) => Promise<void>;
  reset: () => Promise<void>;

  // Queries
  getStationPredictions: (stationId: string) => Promise<StationPredictions | null>;
  getRegionData: (region: string) => Promise<RegionData | null>;

  // Helpers
  getTrainById: (trainId: string) => TrainData | undefined;
  getConflictsForTrain: (trainId: string) => UnifiedConflict[];
  getConflictsForStation: (stationId: string) => UnifiedConflict[];
}

// =============================================================================
// Hook Implementation
// =============================================================================

const DEFAULT_API_URL = 'http://localhost:8002';

export function useUnifiedSimulation(
  options: UseUnifiedSimulationOptions = {}
): UseUnifiedSimulationReturn {
  const {
    autoStart = true,
    tickInterval = 1000,
    apiUrl = import.meta.env.VITE_PREDICTION_API_URL || DEFAULT_API_URL,
  } = options;

  const [state, setState] = useState<SimulationState | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch a single tick
  const tick = useCallback(async () => {
    try {
      abortControllerRef.current = new AbortController();
      
      const response = await fetch(`${apiUrl}/api/simulation/tick`, {
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: SimulationState = await response.json();
      setState(data);
      setError(null);
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
        console.error('Tick error:', err);
      }
    }
  }, [apiUrl]);

  // Fetch multiple ticks at once
  const multiTick = useCallback(async (count: number) => {
    try {
      setIsLoading(true);
      const response = await fetch(`${apiUrl}/api/simulation/multi-tick/${count}`);
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: SimulationState = await response.json();
      setState(data);
      setError(null);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl]);

  // Reset simulation
  const reset = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${apiUrl}/api/simulation/start`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      // Fetch initial state
      await tick();
      setError(null);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl, tick]);

  // Start continuous simulation
  const start = useCallback(() => {
    if (isRunning) return;
    
    setIsRunning(true);
    intervalRef.current = setInterval(() => {
      tick();
    }, tickInterval);
  }, [isRunning, tick, tickInterval]);

  // Stop simulation
  const stop = useCallback(() => {
    setIsRunning(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  // Get predictions for a station
  const getStationPredictions = useCallback(async (stationId: string): Promise<StationPredictions | null> => {
    try {
      const response = await fetch(`${apiUrl}/api/prediction/${encodeURIComponent(stationId)}`);
      if (!response.ok) return null;
      return await response.json();
    } catch {
      return null;
    }
  }, [apiUrl]);

  // Get data for a region
  const getRegionData = useCallback(async (region: string): Promise<RegionData | null> => {
    try {
      const response = await fetch(`${apiUrl}/api/region/${encodeURIComponent(region)}`);
      if (!response.ok) return null;
      return await response.json();
    } catch {
      return null;
    }
  }, [apiUrl]);

  // Helper: get train by ID
  const getTrainById = useCallback((trainId: string): TrainData | undefined => {
    return state?.trains.find(t => t.train_id === trainId);
  }, [state]);

  // Helper: get conflicts for a train
  const getConflictsForTrain = useCallback((trainId: string): UnifiedConflict[] => {
    const allConflicts = [...(state?.predictions || []), ...(state?.detections || [])];
    return allConflicts.filter(c => c.involved_trains.includes(trainId));
  }, [state]);

  // Helper: get conflicts for a station
  const getConflictsForStation = useCallback((stationId: string): UnifiedConflict[] => {
    const allConflicts = [...(state?.predictions || []), ...(state?.detections || [])];
    return allConflicts.filter(c => 
      c.location === stationId || 
      c.location.toUpperCase().includes(stationId.toUpperCase())
    );
  }, [state]);

  // Auto-start if enabled
  useEffect(() => {
    if (autoStart) {
      // Initial fetch
      tick().then(() => {
        start();
      });
    }

    return () => {
      stop();
    };
  }, [autoStart]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    // State
    state,
    trains: state?.trains || [],
    predictions: state?.predictions || [],
    detections: state?.detections || [],
    isRunning,
    isLoading,
    error,

    // Actions
    start,
    stop,
    tick,
    multiTick,
    reset,

    // Queries
    getStationPredictions,
    getRegionData,

    // Helpers
    getTrainById,
    getConflictsForTrain,
    getConflictsForStation,
  };
}

export default useUnifiedSimulation;
