import { useState, useEffect } from 'react';
import { AlertTriangle, MapPin, ChevronDown, ChevronUp, CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import type { UnifiedConflict } from '../../hooks/useUnifiedSimulation';

interface UnifiedAlertPanelProps {
  predictions: UnifiedConflict[];
  detections: UnifiedConflict[];
  tickNumber?: number;
  simulationTime?: string;
  onPause?: () => void;
  onResume?: () => void;
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
          {/* Resolution Button */}
          <div className="mt-2 flex justify-end">
            <Button
              onClick={() => {
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
  onPause,
  onResume,
}: UnifiedAlertPanelProps) {
  const [expandedPrediction, setExpandedPrediction] = useState<string | null>(null);
  const [expandedDetection, setExpandedDetection] = useState<string | null>(null);
  const [showAllPredictions, setShowAllPredictions] = useState(false);
  const [riskFilter, setRiskFilter] = useState<'all' | 'critical' | 'high' | 'medium' | 'low'>('all');

  // Local state to hold the conflicts so they don't jump around while being inspected
  const [localPredictions, setLocalPredictions] = useState(predictions);
  const [localDetections, setLocalDetections] = useState(detections);

  useEffect(() => {
    // Only update the list if the user isn't currently inspecting a conflict
    if (!expandedPrediction && !expandedDetection) {
      setLocalPredictions(predictions);
      setLocalDetections(detections);
    }
  }, [predictions, detections, expandedPrediction, expandedDetection]);

  // Handle auto-pausing the simulation for critical inspection
  useEffect(() => {
    if (expandedPrediction || expandedDetection) {
      onPause?.();
    } else {
      onResume?.();
    }
  }, [expandedPrediction, expandedDetection, onPause, onResume]);

  const filteredPredictions = localPredictions.filter(p => {
    if (riskFilter === 'all') return p.probability >= 0.3;
    return p.severity === riskFilter;
  });

  const sortedPredictions = [...filteredPredictions]
    .sort((a, b) => b.probability - a.probability);

  const filteredDetections = localDetections.filter(d => {
    if (riskFilter === 'all') return true;
    return d.severity === riskFilter;
  });

  const highRiskPredictions = sortedPredictions.filter(p => p.probability >= 0.5 || riskFilter !== 'all');
  const otherPredictions = sortedPredictions.filter(p => p.probability < 0.5 && riskFilter === 'all');
  const displayPredictions = (showAllPredictions || riskFilter !== 'all') ? sortedPredictions.slice(0, 15) : highRiskPredictions.slice(0, 5);

  return (
    <div className="glass-panel p-4 h-full flex flex-col">
      <div className="flex flex-col gap-4 mb-6">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Conflict Monitor
          </h3>
          {tickNumber !== undefined && (
            <div className="text-[10px] text-slate-500 font-mono">
              TICK #{tickNumber}
            </div>
          )}
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap gap-1.5">
          {[
            { id: 'all', label: 'All', color: 'bg-slate-700', active: 'bg-slate-600 text-white ring-1 ring-slate-400' },
            { id: 'critical', label: 'Critical', color: 'bg-red-500/20 text-red-400', active: 'bg-red-600 text-white shadow-lg shadow-red-600/20' },
            { id: 'high', label: 'High', color: 'bg-orange-600/20 text-orange-400', active: 'bg-orange-600 text-white shadow-lg shadow-orange-600/20' },
            { id: 'medium', label: 'Med', color: 'bg-orange-500/20 text-orange-300', active: 'bg-orange-500 text-white shadow-lg shadow-orange-500/20' },
            { id: 'low', label: 'Low', color: 'bg-yellow-500/20 text-yellow-400', active: 'bg-yellow-500 text-slate-900 shadow-lg shadow-yellow-500/20' },
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setRiskFilter(f.id as any)}
              className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-tighter transition-all duration-200 border border-transparent ${
                riskFilter === f.id ? f.active : `${f.color} hover:bg-white/5`
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {/* Detections */}
        {filteredDetections.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-500" />
              <span className="text-xs font-bold text-red-400 uppercase tracking-wider">
                🚨 {riskFilter === 'all' ? 'Active Conflicts' : `${riskFilter.toUpperCase()} Conflicts`} ({filteredDetections.length})
              </span>
            </div>
            <div className="space-y-2">
              {filteredDetections.map(d => (
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
        {filteredDetections.length > 0 && displayPredictions.length > 0 && (
          <div className="border-t border-slate-700 my-3" />
        )}

        {/* Predictions */}
        {displayPredictions.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-orange-500" />
                <span className="text-xs font-semibold text-orange-400 uppercase tracking-wider">
                  {riskFilter === 'all' ? 'Potential Conflicts' : `${riskFilter.toUpperCase()} Predictions`} ({sortedPredictions.length})
                </span>
              </div>
              {riskFilter === 'all' && otherPredictions.length > 0 && (
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
        {filteredDetections.length === 0 && displayPredictions.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-8">
            <CheckCircle2 className="w-12 h-12 mb-3 text-emerald-500/50" />
            <div className="text-sm font-medium">No {riskFilter !== 'all' ? riskFilter : ''} Conflicts</div>
            <div className="text-xs mt-1">
              {riskFilter === 'all' 
                ? 'Network Operating Normally' 
                : `No ${riskFilter} risks detected in current scan`}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default UnifiedAlertPanel;
