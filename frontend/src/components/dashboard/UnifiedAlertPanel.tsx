/**
 * Unified Alert Panel
 * ====================
 *
 * Combined panel showing:
 * - PREDICTIONS (Orange/Yellow) - "⚠️ POTENTIAL CONFLICT" with probability
 * - DETECTIONS (Red) - "🚨 ACTUAL CONFLICT" with details and resolutions
 */

import { useState } from 'react';
import { AlertTriangle, MapPin, ChevronDown, ChevronUp, CheckCircle2, XCircle } from 'lucide-react';
import type { UnifiedConflict } from '../../hooks/useUnifiedSimulation';

interface UnifiedAlertPanelProps {
  predictions: UnifiedConflict[];
  detections: UnifiedConflict[];
  tickNumber?: number;
  simulationTime?: string;
}

// Severity colors for predictions (orange/yellow)
const PREDICTION_STYLES = {
  low: {
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500',
    text: 'text-yellow-500',
    icon: '📊',
    label: 'Low Risk',
  },
  medium: {
    bg: 'bg-orange-500/10',
    border: 'border-orange-500',
    text: 'text-orange-500',
    icon: '⚠️',
    label: 'POTENTIAL CONFLICT',
  },
  high: {
    bg: 'bg-orange-600/10',
    border: 'border-orange-600',
    text: 'text-orange-600',
    icon: '⚠️',
    label: 'HIGH RISK',
  },
  critical: {
    bg: 'bg-red-500/10',
    border: 'border-red-500',
    text: 'text-red-500',
    icon: '🚨',
    label: 'CRITICAL RISK',
  },
};

// Detection styles (always red - actual conflicts)
const DETECTION_STYLES = {
  low: {
    bg: 'bg-red-500/10',
    border: 'border-red-400',
    text: 'text-red-400',
    icon: '🔴',
    label: 'CONFLICT DETECTED',
  },
  medium: {
    bg: 'bg-red-500/15',
    border: 'border-red-500',
    text: 'text-red-500',
    icon: '🚨',
    label: 'ACTIVE CONFLICT',
  },
  high: {
    bg: 'bg-red-600/20',
    border: 'border-red-600',
    text: 'text-red-600',
    icon: '🚨',
    label: 'SEVERE CONFLICT',
  },
  critical: {
    bg: 'bg-red-700/25',
    border: 'border-red-700',
    text: 'text-red-700',
    icon: '💥',
    label: 'CRITICAL CONFLICT',
  },
};

const CONFLICT_TYPE_LABELS: Record<string, string> = {
  edge_capacity_overflow: '🚂 EDGE OVERLOAD',
  headway_violation: '⏱️ HEADWAY VIOLATION',
  platform_conflict: '🚉 PLATFORM CONFLICT',
  track_conflict: '🛤️ TRACK CONFLICT',
  station_congestion: '🏢 STATION CONGESTION',
  schedule_deviation: '📅 SCHEDULE DEVIATION',
  cascading_delay: '🔗 CASCADING DELAY',
  capacity_exceeded: '📈 CAPACITY EXCEEDED',
};

function getConflictTypeLabel(type: string): string {
  return CONFLICT_TYPE_LABELS[type] || `⚠️ ${type.replace(/_/g, ' ').toUpperCase()}`;
}

function PredictionCard({ conflict, isExpanded, onToggle }: { 
  conflict: UnifiedConflict; 
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const severity = conflict.severity || 'medium';
  const styles = PREDICTION_STYLES[severity] || PREDICTION_STYLES.medium;
  const probability = Math.round(conflict.probability * 100);
  
  // Extract time horizon from explanation if available
  const horizonMatch = conflict.explanation?.match(/(\d+)\s*min/);
  const horizon = horizonMatch ? horizonMatch[1] : '10-30';

  return (
    <div className={`rounded-lg border-l-4 ${styles.border} ${styles.bg} transition-all duration-200`}>
      <div 
        className="p-3 cursor-pointer hover:bg-white/5"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-2">
            <span className="text-lg">{styles.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`font-semibold text-sm ${styles.text}`}>
                  {styles.label}
                </span>
                <span className="text-xs text-slate-400">
                  {probability}% risk in {horizon}min
                </span>
              </div>
              <div className="text-xs text-slate-300 mt-1">
                {conflict.involved_trains.slice(0, 2).join(', ')}
                {conflict.involved_trains.length > 2 && ` +${conflict.involved_trains.length - 2} more`}
              </div>
              {conflict.location && (
                <div className="flex items-center gap-1 text-xs text-slate-400 mt-1">
                  <MapPin className="w-3 h-3" />
                  <span>{conflict.location}</span>
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={`text-lg font-bold ${styles.text}`}>
              {probability}%
            </div>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </div>
        </div>
      </div>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-slate-700/50">
          <div className="pt-2 space-y-2">
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
          </div>
        </div>
      )}
    </div>
  );
}

function DetectionCard({ conflict, isExpanded, onToggle }: { 
  conflict: UnifiedConflict; 
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const severity = conflict.severity || 'medium';
  const styles = DETECTION_STYLES[severity] || DETECTION_STYLES.medium;

  return (
    <div className={`rounded-lg border-l-4 ${styles.border} ${styles.bg} transition-all duration-200 ring-2 ring-red-500/30`}>
      <div 
        className="p-3 cursor-pointer hover:bg-white/5"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-2">
            <span className="text-xl animate-pulse">{styles.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`font-bold text-sm ${styles.text} uppercase`}>
                  {styles.label}
                </span>
              </div>
              <div className={`text-sm font-semibold ${styles.text} mt-1`}>
                {getConflictTypeLabel(conflict.conflict_type)}
              </div>
              {conflict.location && (
                <div className="flex items-center gap-1 text-xs text-slate-300 mt-1">
                  <MapPin className="w-3 h-3" />
                  <span className="font-medium">{conflict.location}</span>
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

      {/* Expanded details with resolutions */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-red-500/30">
          <div className="pt-3 space-y-3">
            {/* Conflict Details */}
            <div className="space-y-1">
              <div className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
                Conflict Details
              </div>
              <div className="text-xs text-slate-400">
                <strong>Trains Involved:</strong> {conflict.involved_trains.join(', ')}
              </div>
              <div className="text-xs text-slate-400">
                <strong>Location:</strong> {conflict.location}
              </div>
            </div>

            {/* Explanation */}
            {conflict.explanation && (
              <div className="bg-red-900/20 border border-red-500/30 p-2 rounded">
                <div className="text-xs text-red-300">
                  {conflict.explanation}
                </div>
              </div>
            )}

            {/* Resolution Suggestions */}
            
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

  // Sort predictions by probability (highest first)
  const sortedPredictions = [...predictions]
    .filter(p => p.probability >= 0.3) 
    .sort((a, b) => b.probability - a.probability);

  // High risk predictions (>=50%)
  const highRiskPredictions = sortedPredictions.filter(p => p.probability >= 0.5);
  const otherPredictions = sortedPredictions.filter(p => p.probability < 0.5);

  // Display predictions
  const displayPredictions = showAllPredictions 
    ? sortedPredictions.slice(0, 15) 
    : highRiskPredictions.slice(0, 5);

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
        <div className="flex gap-2">
          {detections.length > 0 && (
            <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full animate-pulse font-semibold">
              {detections.length} Active
            </span>
          )}
          {highRiskPredictions.length > 0 && (
            <span className="text-xs bg-orange-500/20 text-orange-400 px-2 py-1 rounded-full">
              {highRiskPredictions.length} High Risk
            </span>
          )}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        
        {/* DETECTIONS SECTION - Always on top, always visible */}
        {detections.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-500" />
              <span className="text-xs font-bold text-red-400 uppercase tracking-wider">
                🚨 Active Conflicts ({detections.length})
              </span>
            </div>
            <div className="space-y-2">
              {detections.map((detection) => (
                <DetectionCard
                  key={detection.conflict_id}
                  conflict={detection}
                  isExpanded={expandedDetection === detection.conflict_id}
                  onToggle={() => setExpandedDetection(
                    expandedDetection === detection.conflict_id ? null : detection.conflict_id
                  )}
                />
              ))}
            </div>
          </div>
        )}

        {/* Divider if both exist */}
        {detections.length > 0 && displayPredictions.length > 0 && (
          <div className="border-t border-slate-700 my-3" />
        )}

        {/* PREDICTIONS SECTION */}
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
              {displayPredictions.map((prediction) => (
                <PredictionCard
                  key={prediction.conflict_id}
                  conflict={prediction}
                  isExpanded={expandedPrediction === prediction.conflict_id}
                  onToggle={() => setExpandedPrediction(
                    expandedPrediction === prediction.conflict_id ? null : prediction.conflict_id
                  )}
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

      {/* Summary footer */}
      <div className="mt-3 pt-3 border-t border-slate-700">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              Detections: {detections.length}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-orange-500"></span>
              Predictions: {sortedPredictions.length}
            </span>
          </div>
          <span className="text-slate-500">
            ML: XGBoost + Heuristics
          </span>
        </div>
      </div>
    </div>
  );
}

export default UnifiedAlertPanel;
