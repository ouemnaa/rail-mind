/**
 * Predictive Alert Feed
 * =====================
 *
 * Real-time feed of conflict predictions with color-coded alerts.
 */

import { useState } from 'react';
import { AlertTriangle, Clock, Train, MapPin, ChevronRight, TrendingUp } from 'lucide-react';
import { ConflictAlertPanel } from './ConflictAlertPanel';
import type { ConflictAlert, BatchPrediction, RiskLevel, MemorySearchResult, ConflictType } from '../../types/prediction';

interface PredictiveAlertFeedProps {
  predictions: BatchPrediction | null;
  onAlertClick?: (alert: ConflictAlert) => void;
  onSearchSimilar?: (alert: ConflictAlert) => Promise<MemorySearchResult | null>;
  maxAlerts?: number;
}

const SEVERITY_STYLES: Record<RiskLevel, string> = {
  safe: 'border-l-green-500 bg-green-500/5 hover:bg-green-500/10',
  low_risk: 'border-l-yellow-500 bg-yellow-500/5 hover:bg-yellow-500/10',
  high_risk: 'border-l-orange-500 bg-orange-500/5 hover:bg-orange-500/10',
  critical: 'border-l-red-500 bg-red-500/5 hover:bg-red-500/10',
};

const SEVERITY_TEXT: Record<RiskLevel, string> = {
  safe: 'text-green-500',
  low_risk: 'text-yellow-500',
  high_risk: 'text-orange-500',
  critical: 'text-red-500',
};

export function PredictiveAlertFeed({
  predictions,
  onAlertClick,
  onSearchSimilar,
  maxAlerts = 10,
}: PredictiveAlertFeedProps) {
  const [expandedAlert, setExpandedAlert] = useState<string | null>(null);
  const [similarCases, setSimilarCases] = useState<Record<string, MemorySearchResult>>({});
  const [loadingSimilar, setLoadingSimilar] = useState<string | null>(null);

  // Convert predictions to alerts
  const alerts: ConflictAlert[] = predictions
    ? predictions.predictions
        .filter((p) => p.risk_level !== 'safe')
        .map((p) => ({
          id: `alert-${p.train_id}`,
          train_id: p.train_id,
          type: (p.predicted_conflict_type || 'unknown') as ConflictType | 'unknown',
          title: getConflictTypeLabel(p.predicted_conflict_type),
          location: p.predicted_location || 'Unknown',
          time: formatTimeUntil(p.predicted_time),
          predictedTime: p.predicted_time ? new Date(p.predicted_time) : null,
          probability: p.probability,
          severity: p.risk_level as RiskLevel,
          contributingFactors: p.contributing_factors,
          similarCasesCount: 0,
          suggestedResolution: null,
          confidence: p.confidence,
        }))
        .sort((a, b) => b.probability - a.probability)
        .slice(0, maxAlerts)
    : [];

  const criticalCount = alerts.filter((a) => a.severity === 'critical').length;
  const highRiskCount = alerts.filter((a) => a.severity === 'high_risk').length;

  const handleAlertExpand = async (alert: ConflictAlert) => {
    if (expandedAlert === alert.id) {
      setExpandedAlert(null);
      return;
    }

    setExpandedAlert(alert.id);

    // Search for similar cases if not already loaded
    if (!similarCases[alert.id] && onSearchSimilar) {
      setLoadingSimilar(alert.id);
      const result = await onSearchSimilar(alert);
      if (result) {
        setSimilarCases((prev) => ({ ...prev, [alert.id]: result }));
      }
      setLoadingSimilar(null);
    }
  };

  const getIcon = (type: string, severity: RiskLevel) => {
    const colorClass = SEVERITY_TEXT[severity];
    switch (type) {
      case 'platform_conflict':
        return <Train className={`w-4 h-4 ${colorClass}`} />;
      case 'track_conflict':
      case 'headway_violation':
        return <Clock className={`w-4 h-4 ${colorClass}`} />;
      case 'capacity_exceeded':
        return <TrendingUp className={`w-4 h-4 ${colorClass}`} />;
      default:
        return <AlertTriangle className={`w-4 h-4 ${colorClass}`} />;
    }
  };

  if (!predictions) {
    return (
      <div className="glass-panel p-4 h-full flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Predictions Loading...
          </h3>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-pulse text-muted-foreground">
            Connecting to prediction service...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel p-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Conflict Predictions
        </h3>
        <div className="flex gap-2">
          {criticalCount > 0 && (
            <span className="text-xs bg-red-500/20 text-red-500 px-2 py-1 rounded-full">
              {criticalCount} Critical
            </span>
          )}
          {highRiskCount > 0 && (
            <span className="text-xs bg-orange-500/20 text-orange-500 px-2 py-1 rounded-full">
              {highRiskCount} High Risk
            </span>
          )}
        </div>
      </div>

      {/* Network Summary */}
      <div className="mb-4 p-3 bg-slate-800/50 rounded-lg">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Network Risk Score</span>
          <span
            className={`font-bold ${
              predictions.network_risk_score > 0.5
                ? 'text-red-500'
                : predictions.network_risk_score > 0.3
                ? 'text-orange-500'
                : 'text-green-500'
            }`}
          >
            {(predictions.network_risk_score * 100).toFixed(0)}%
          </span>
        </div>
        <div className="mt-2 h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              predictions.network_risk_score > 0.5
                ? 'bg-red-500'
                : predictions.network_risk_score > 0.3
                ? 'bg-orange-500'
                : 'bg-green-500'
            }`}
            style={{ width: `${predictions.network_risk_score * 100}%` }}
          />
        </div>
      </div>

      {/* Alerts List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <div className="text-4xl mb-2">🟢</div>
            <p>No conflicts predicted</p>
            <p className="text-xs mt-1">Network operating normally</p>
          </div>
        ) : (
          alerts.map((alert) => {
            const isExpanded = expandedAlert === alert.id;

            return (
              <div key={alert.id}>
                {isExpanded ? (
                  <ConflictAlertPanel
                    alert={alert}
                    similarCases={similarCases[alert.id]}
                    isExpanded={true}
                    onClose={() => setExpandedAlert(null)}
                    onViewDetails={() => onAlertClick?.(alert)}
                  />
                ) : (
                  <div
                    onClick={() => handleAlertExpand(alert)}
                    className={`p-3 rounded-lg border-l-4 cursor-pointer transition-all duration-200 ${SEVERITY_STYLES[alert.severity]}`}
                  >
                    <div className="flex items-start gap-3">
                      {getIcon(alert.type, alert.severity)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${SEVERITY_TEXT[alert.severity]}`}>
                            {alert.train_id}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {Math.round(alert.probability * 100)}%
                          </span>
                        </div>
                        <p className="text-sm truncate">{alert.title}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                          <MapPin className="w-3 h-3" />
                          <span className="truncate">{alert.location}</span>
                          <span>•</span>
                          <span>{alert.time}</span>
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Recommended Actions */}
      {predictions.recommended_actions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-700">
          <h4 className="text-xs font-semibold text-muted-foreground mb-2">
            Recommended Actions
          </h4>
          <div className="space-y-1 text-xs">
            {predictions.recommended_actions.slice(0, 3).map((action, i) => (
              <p key={i} className="text-slate-300">
                {action}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Helper functions
function getConflictTypeLabel(type: string | null): string {
  const labels: Record<string, string> = {
    platform_conflict: 'Platform Conflict Predicted',
    track_conflict: 'Track Conflict Predicted',
    headway_violation: 'Headway Violation Risk',
    capacity_exceeded: 'Capacity Warning',
    schedule_deviation: 'Schedule Deviation',
    cascading_delay: 'Cascading Delay Risk',
  };
  return type ? labels[type] || 'Potential Conflict' : 'Potential Conflict';
}

function formatTimeUntil(predictedTime: string | null): string {
  if (!predictedTime) return 'Soon';

  const predicted = new Date(predictedTime);
  const now = new Date();
  const diffMs = predicted.getTime() - now.getTime();
  const diffMin = Math.round(diffMs / 60000);

  if (diffMin <= 0) return 'Now';
  if (diffMin === 1) return 'In 1 min';
  if (diffMin < 60) return `In ${diffMin} min`;

  const hours = Math.floor(diffMin / 60);
  const mins = diffMin % 60;
  return `In ${hours}h ${mins}m`;
}

export default PredictiveAlertFeed;
