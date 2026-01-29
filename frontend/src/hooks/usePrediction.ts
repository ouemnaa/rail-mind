/**
 * Prediction API Hook
 * ===================
 *
 * React hook for interacting with the conflict prediction API.
 * Supports both REST calls and WebSocket subscriptions.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  BatchPrediction,
  ConflictPrediction,
  NetworkState,
  MemorySearchResult,
  SystemStatus,
  ConflictAlert,
  ConflictType,
} from '../types/prediction';

const API_BASE_URL = import.meta.env.VITE_API_URL
const WS_URL = import.meta.env.VITE_WS_URL

interface UsePredictionOptions {
  autoConnect?: boolean;
  enableWebSocket?: boolean;
  pollingInterval?: number; // ms, for demo mode
}

interface UsePredictionReturn {
  // State
  predictions: BatchPrediction | null;
  alerts: ConflictAlert[];
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
  status: SystemStatus | null;

  // Actions
  connect: () => void;
  disconnect: () => void;
  fetchPredictions: () => Promise<void>;
  searchSimilarCases: (prediction: ConflictPrediction) => Promise<MemorySearchResult | null>;
  getSystemStatus: () => Promise<SystemStatus | null>;

  // Helpers
  getTrainPrediction: (trainId: string) => ConflictPrediction | undefined;
  getHighRiskAlerts: () => ConflictAlert[];
  getCriticalAlerts: () => ConflictAlert[];
}

export function usePrediction(options: UsePredictionOptions = {}): UsePredictionReturn {
  const {
    autoConnect = true,
    enableWebSocket = true,
    pollingInterval = 0,
  } = options;

  const [predictions, setPredictions] = useState<BatchPrediction | null>(null);
  const [alerts, setAlerts] = useState<ConflictAlert[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Convert predictions to alerts
  const updateAlerts = useCallback((batch: BatchPrediction) => {
    const newAlerts: ConflictAlert[] = batch.predictions
      .filter((p) => p.risk_level !== 'safe')
      .map((p) => ({
        id: `alert-${p.train_id}-${Date.now()}`,
        train_id: p.train_id,
        type: (p.predicted_conflict_type || 'unknown') as ConflictType | 'unknown',
        title: p.predicted_conflict_type
          ? getConflictTypeLabel(p.predicted_conflict_type)
          : 'Potential Conflict',
        location: p.predicted_location || 'Unknown',
        time: formatTimeUntil(p.predicted_time),
        predictedTime: p.predicted_time ? new Date(p.predicted_time) : null,
        probability: p.probability,
        severity: p.risk_level,
        contributingFactors: p.contributing_factors,
        similarCasesCount: 0,
        suggestedResolution: null,
        confidence: p.confidence,
      }))
      .sort((a, b) => b.probability - a.probability);

    setAlerts(newAlerts);
  }, []);

  // WebSocket connection
  const connect = useCallback(() => {
    if (!enableWebSocket || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      wsRef.current = new WebSocket(WS_URL);

      wsRef.current.onopen = () => {
        console.log('🔌 Prediction WebSocket connected');
        setIsConnected(true);
        setError(null);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as BatchPrediction;
          setPredictions(data);
          updateAlerts(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      wsRef.current.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('WebSocket connection error');
      };

      wsRef.current.onclose = () => {
        console.log('🔌 Prediction WebSocket disconnected');
        setIsConnected(false);

        // Auto-reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          if (enableWebSocket) {
            connect();
          }
        }, 5000);
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      setError('Failed to connect to prediction service');
    }
  }, [enableWebSocket, updateAlerts]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }
    setIsConnected(false);
  }, []);

  // REST API calls
  const fetchPredictions = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Use new unified API endpoint
      const response = await fetch(`${API_BASE_URL}/api/simulation/tick`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();

      // Transform unified API response to BatchPrediction format
      const transformedData: BatchPrediction = {
        timestamp: data.simulation_time,
        predictions: data.trains.map((train: any) => {
          // Find any predictions for this train
          const trainPrediction = data.predictions?.find((p: any) =>
            p.involved_trains?.includes(train.train_id)
          );
          const trainDetection = data.detections?.find((d: any) =>
            d.involved_trains?.includes(train.train_id)
          );

          // Get model_used from prediction
          const modelUsed = trainPrediction?.model_used ??
            trainDetection?.model_used ??
            'xgboost_ensemble';

          const prob = trainDetection?.probability ?? trainPrediction?.probability ?? (train.delay_sec > 120 ? 0.4 : 0.15);
          const riskLevel = trainDetection ? 'critical' :
            trainPrediction?.severity ??
            (prob >= 0.5 ? 'high_risk' : prob >= 0.3 ? 'low_risk' : 'safe');

          return {
            train_id: train.train_id,
            probability: prob,
            risk_level: riskLevel,
            predicted_conflict_type: trainDetection?.conflict_type ?? trainPrediction?.conflict_type ?? null,
            predicted_time: trainPrediction?.timestamp ?? null,
            predicted_location: train.current_station || train.next_station,
            contributing_factors: trainPrediction?.resolution_suggestions ?? [],
            confidence: trainPrediction?.probability ?? 0.8,
            model_used: modelUsed,
            color: riskLevel === 'critical' ? '#dc2626' :
              riskLevel === 'high_risk' ? '#f97316' :
                riskLevel === 'low_risk' ? '#f59e0b' : '#10b981',
            emoji: riskLevel === 'critical' ? '🔴' :
              riskLevel === 'high_risk' ? '🟠' :
                riskLevel === 'low_risk' ? '🟡' : '🟢',
          };
        }),
        network_risk_score: Math.min(0.95, (data.predictions?.length ?? 0) / Math.max(1, data.trains?.length ?? 1) * 2),
        high_risk_trains: data.trains?.filter((t: any) => t.delay_sec > 300).map((t: any) => t.train_id) ?? [],
        critical_trains: data.detections?.flatMap((d: any) => d.involved_trains) ?? [],
        recommended_actions: data.predictions?.flatMap((p: any) => p.resolution_suggestions ?? []).slice(0, 5) ?? [],
        model_used: data.predictions?.[0]?.model_used ?? 'xgboost_ensemble',
        strategy: 'continuous',
      };

      setPredictions(transformedData);
      updateAlerts(transformedData);
    } catch (e) {
      console.error('Failed to fetch predictions:', e);
      setError('Failed to fetch predictions');
    } finally {
      setIsLoading(false);
    }
  }, [updateAlerts]);

  const searchSimilarCases = useCallback(
    async (prediction: ConflictPrediction): Promise<MemorySearchResult | null> => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/memory/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(prediction),
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return (await response.json()) as MemorySearchResult;
      } catch (e) {
        console.error('Failed to search similar cases:', e);
        return null;
      }
    },
    []
  );

  const getSystemStatus = useCallback(async (): Promise<SystemStatus | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/status`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as SystemStatus;
      setStatus(data);
      return data;
    } catch (e) {
      console.error('Failed to get system status:', e);
      return null;
    }
  }, []);

  // Helpers
  const getTrainPrediction = useCallback(
    (trainId: string): ConflictPrediction | undefined => {
      return predictions?.predictions.find((p) => p.train_id === trainId);
    },
    [predictions]
  );

  const getHighRiskAlerts = useCallback(() => {
    return alerts.filter((a) => a.severity === 'high_risk' || a.severity === 'critical');
  }, [alerts]);

  const getCriticalAlerts = useCallback(() => {
    return alerts.filter((a) => a.severity === 'critical');
  }, [alerts]);

  // Auto-connect and polling
  useEffect(() => {
    if (autoConnect) {
      if (enableWebSocket) {
        connect();
      }
      // Initial fetch
      fetchPredictions();
      getSystemStatus();
    }

    // Set up polling if configured
    if (pollingInterval > 0) {
      pollingRef.current = setInterval(fetchPredictions, pollingInterval);
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, enableWebSocket, pollingInterval, connect, disconnect, fetchPredictions, getSystemStatus]);

  return {
    predictions,
    alerts,
    isConnected,
    isLoading,
    error,
    status,
    connect,
    disconnect,
    fetchPredictions,
    searchSimilarCases,
    getSystemStatus,
    getTrainPrediction,
    getHighRiskAlerts,
    getCriticalAlerts,
  };
}

// Helper functions
function getConflictTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    platform_conflict: 'Platform Conflict',
    track_conflict: 'Track Conflict',
    headway_violation: 'Headway Violation',
    capacity_exceeded: 'Capacity Exceeded',
    schedule_deviation: 'Schedule Deviation',
    cascading_delay: 'Cascading Delay',
  };
  return labels[type] || 'Potential Conflict';
}

function formatTimeUntil(predictedTime: string | null): string {
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

export default usePrediction;
