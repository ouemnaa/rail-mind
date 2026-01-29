import { useState, useEffect } from 'react';
import { AlertTriangle, MapPin, ChevronDown, ChevronUp, CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import type { UnifiedConflict } from '../../hooks/useUnifiedSimulation';

// API base URL for image requests
const API_BASE_URL = import.meta.env.VITE_PREDICTION_API_URL || 'http://localhost:8002';

interface UnifiedAlertPanelProps {
  predictions: UnifiedConflict[];
  detections: UnifiedConflict[];
  tickNumber?: number;
  simulationTime?: string;
}

// Styles for severity levels
const PREDICTION_STYLES = {
  low: { bg: 'bg-yellow-500/10', border: 'border-yellow-500', text: 'text-yellow-500', icon: '📊', label: 'Low Risk' },
  medium: { bg: 'bg-orange-500/10', border: 'border-orange-500', text: 'text-orange-500', icon: '⚠️', label: 'POTENTIAL CONFLICT' },
  high: { bg: 'bg-orange-600/10', border: 'border-orange-600', text: 'text-orange-600', icon: '⚠️', label: 'HIGH RISK' },
  critical: { bg: 'bg-red-500/10', border: 'border-red-500', text: 'text-red-500', icon: '🚨', label: 'CRITICAL RISK' },
};

const DETECTION_STYLES = {
  low: { bg: 'bg-red-500/10', border: 'border-red-400', text: 'text-red-400', icon: '🔴', label: 'CONFLICT DETECTED' },
  medium: { bg: 'bg-red-500/15', border: 'border-red-500', text: 'text-red-500', icon: '🚨', label: 'ACTIVE CONFLICT' },
  high: { bg: 'bg-red-600/20', border: 'border-red-600', text: 'text-red-600', icon: '🚨', label: 'SEVERE CONFLICT' },
  critical: { bg: 'bg-red-700/25', border: 'border-red-700', text: 'text-red-700', icon: '💥', label: 'CRITICAL CONFLICT' },
};

// Conflict type labels
const CONFLICT_TYPE_LABELS: Record<string, string> = {
  edge_capacity_overflow: '🚂 EDGE OVERLOAD',
  headway_violation: '⏱️ HEADWAY VIOLATION',
  platform_conflict: '🚉 PLATFORM CONFLICT',
  track_conflict: '🛤️ TRACK CONFLICT',
  track_fault: '🛤️ TRACK FAULT DETECTED',
  station_congestion: '🏢 STATION CONGESTION',
  schedule_deviation: '📅 SCHEDULE DEVIATION',
  cascading_delay: '🔗 CASCADING DELAY',
  capacity_exceeded: '📈 CAPACITY EXCEEDED',
};

function getConflictTypeLabel(type: string) {
  return CONFLICT_TYPE_LABELS[type] || `⚠️ ${type.replace(/_/g, ' ').toUpperCase()}`;
}

// Generic Card component for both predictions & detections
function ConflictCard({
  conflict,
  isExpanded,
  onToggle,
  type = 'prediction', // 'prediction' or 'detection'
}: {
  conflict: UnifiedConflict;
  isExpanded: boolean;
  onToggle: () => void;
  type?: 'prediction' | 'detection';
}) {
  const navigate = useNavigate();
  const severity = conflict.severity || 'medium';
  const styles = type === 'prediction'
    ? PREDICTION_STYLES[severity] || PREDICTION_STYLES.medium
    : DETECTION_STYLES[severity] || DETECTION_STYLES.medium;
  const probability = Math.round(conflict.probability * 100);

  return (
    <div className={`rounded-lg border-l-4 ${styles.border} ${styles.bg} transition-all duration-200 ${type === 'detection' ? 'ring-2 ring-red-500/30' : ''}`}>
      <div className="p-3 cursor-pointer hover:bg-white/5" onClick={onToggle}>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-2">
            <span className={`text-lg ${type === 'detection' ? 'animate-pulse text-xl' : 'text-lg'}`}>{styles.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`font-semibold ${type === 'prediction' ? 'text-sm' : 'text-sm font-bold uppercase'} ${styles.text}`}>
                  {styles.label}
                </span>
                {type === 'prediction' && (
                  <span className="text-xs text-slate-400">{probability}% risk</span>
                )}
              </div>
              <div className="text-xs text-slate-300 mt-1">
                {conflict.involved_trains.join(', ')}
              </div>
              {conflict.location && (
                <div className="flex items-center gap-1 text-xs text-slate-400 mt-1">
                  <MapPin className="w-3 h-3" />
                  <span>{conflict.location}</span>
                </div>
              )}
            </div>
          </div>
          <div>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </div>
        </div>
      </div>

      {isExpanded && (
        <div className="px-3 pb-3 border-t border-slate-700/50 pt-2 space-y-2">
          <div className="text-xs text-slate-400">
            <strong>Type:</strong> {getConflictTypeLabel(conflict.conflict_type)}
          </div>
          <div className="text-xs text-slate-400">
            <strong>Trains:</strong> {conflict.involved_trains.join(', ')}
          </div>
          {conflict.explanation && (
            <div className="text-xs text-slate-300 bg-slate-800/50 p-2 rounded">
              {conflict.explanation}
            </div>
          )}

          {/* Track Fault Image - Vision AI Detection */}
          {conflict.image_url && conflict.conflict_type === 'track_fault' && (
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-purple-400 uppercase tracking-wider">
                <span>📷</span>
                <span>Vision AI Detection</span>
              </div>
              <div className="relative rounded-lg overflow-hidden border-2 border-red-500/50 bg-slate-900/50">
                <img
                  src={`${API_BASE_URL}${conflict.image_url}`}
                  alt="Defective track detected by Vision AI"
                  className="w-full h-auto object-cover"
                  onError={(e) => {
                    // Fallback if image fails to load
                    console.error('Failed to load track image:', `${API_BASE_URL}${conflict.image_url}`);
                    e.currentTarget.style.display = 'none';
                  }}
                />
                <div className="absolute top-2 left-2 bg-red-600/90 text-white text-xs font-bold px-2 py-1 rounded">
                  🚨 TRACK DEFECTIVE
                </div>
                <div className="absolute bottom-2 right-2 bg-slate-900/90 text-white text-xs px-2 py-1 rounded">
                  Confidence: {Math.round(conflict.probability * 100)}%
                </div>
              </div>
            </div>
          )}

          {/* Resolution Suggestions */}
          {conflict.resolution_suggestions && conflict.resolution_suggestions.length > 0 && (
            <div className="mt-3 space-y-1">
              <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                💡 Suggested Resolutions
              </div>
              <div className="space-y-1">
                {conflict.resolution_suggestions.map((suggestion, idx) => (
                  <div key={idx} className="text-xs text-slate-300 bg-slate-800/30 px-2 py-1 rounded flex items-start gap-2">
                    <span className="text-emerald-500 mt-0.5">→</span>
                    <span className="flex-1">{suggestion}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Resolution Button */}
          <div className="mt-2 flex justify-end">
            <Button
              onClick={(e) => {
                e.stopPropagation(); // Prevent card from collapsing
                const severityMap = {
                  low: 0.25,
                  medium: 0.5,
                  high: 0.75,
                  critical: 0.95,
                };

                // Mock delay values
                const delay_values: Record<string, number> = {};
                conflict.involved_trains.forEach((t) => {
                  delay_values[t] = Math.round((Math.random() * 5 + 1) * 10) / 10;
                });

                const conflictData = {
                  conflict_id: conflict.conflict_id,
                  conflict_type: conflict.conflict_type,
                  station_ids: [conflict.location],
                  train_ids: conflict.involved_trains,
                  delay_values,
                  timestamp: Date.now() / 1000,
                  severity: severityMap[conflict.severity as keyof typeof severityMap] || 0.5,
                  blocking_behavior: "soft",
                };

                navigate(`/resolution/${conflict.conflict_id}`, {
                  state: { activeConflict: conflictData },
                });
              }}
              size="sm"
              className="bg-blue-600 hover:bg-blue-700"
            >
              Go to Resolution
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function UnifiedAlertPanel({
  predictions,
  detections,
  tickNumber,
  simulationTime,
}: UnifiedAlertPanelProps) {
  const [expandedPrediction, setExpandedPrediction] = useState<string | null>(null);
  const [expandedDetection, setExpandedDetection] = useState<string | null>(null);
  const [showAllPredictions, setShowAllPredictions] = useState(false);

  const sortedPredictions = [...predictions]
    .filter(p => p.probability >= 0.3)
    .sort((a, b) => b.probability - a.probability);

  const highRiskPredictions = sortedPredictions.filter(p => p.probability >= 0.5);
  const otherPredictions = sortedPredictions.filter(p => p.probability < 0.5);
  const displayPredictions = showAllPredictions ? sortedPredictions.slice(0, 15) : highRiskPredictions.slice(0, 5);

  // Keep expanded state only if the conflict still exists in the current data
  useEffect(() => {
    if (expandedDetection && !detections.find(d => d.conflict_id === expandedDetection)) {
      setExpandedDetection(null);
    }
  }, [detections, expandedDetection]);

  useEffect(() => {
    if (expandedPrediction && !displayPredictions.find(p => p.conflict_id === expandedPrediction)) {
      // Only clear if the conflict doesn't exist in the full sorted list
      if (!sortedPredictions.find(p => p.conflict_id === expandedPrediction)) {
        setExpandedPrediction(null);
      }
    }
  }, [displayPredictions, expandedPrediction, sortedPredictions]);

  return (
    <div className="glass-panel p-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Conflict Monitor
          </h3>
          {tickNumber !== undefined && (
            <div className="text-xs text-slate-500">
              Tick #{tickNumber} • {simulationTime || 'Running'}
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {/* Detections */}
        {detections.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-500" />
              <span className="text-xs font-bold text-red-400 uppercase tracking-wider">
                🚨 Active Conflicts ({detections.length})
              </span>
            </div>
            <div className="space-y-2">
              {detections.map(d => (
                <ConflictCard
                  key={d.conflict_id}
                  conflict={d}
                  type="detection"
                  isExpanded={expandedDetection === d.conflict_id}
                  onToggle={() => setExpandedDetection(expandedDetection === d.conflict_id ? null : d.conflict_id)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Divider */}
        {detections.length > 0 && displayPredictions.length > 0 && (
          <div className="border-t border-slate-700 my-3" />
        )}

        {/* Predictions */}
        {displayPredictions.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-orange-500" />
                <span className="text-xs font-semibold text-orange-400 uppercase tracking-wider">
                  Potential Conflicts ({sortedPredictions.length})
                </span>
              </div>
              {otherPredictions.length > 0 && (
                <button
                  onClick={() => setShowAllPredictions(!showAllPredictions)}
                  className="text-xs text-slate-400 hover:text-white transition-colors"
                >
                  {showAllPredictions ? 'Show High Risk Only' : `Show All (${sortedPredictions.length})`}
                </button>
              )}
            </div>
            <div className="space-y-2">
              {displayPredictions.map(p => (
                <ConflictCard
                  key={p.conflict_id}
                  conflict={p}
                  type="prediction"
                  isExpanded={expandedPrediction === p.conflict_id}
                  onToggle={() => setExpandedPrediction(expandedPrediction === p.conflict_id ? null : p.conflict_id)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {detections.length === 0 && displayPredictions.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-8">
            <CheckCircle2 className="w-12 h-12 mb-3 text-emerald-500/50" />
            <div className="text-sm font-medium">Network Operating Normally</div>
            <div className="text-xs mt-1">No conflicts detected or predicted</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default UnifiedAlertPanel;
