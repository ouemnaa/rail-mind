/**
 * Conflict Alert Panel
 * ====================
 *
 * UI panel showing predicted conflicts with detailed information.
 * Displays risk level, contributing factors, similar cases, and suggested resolutions.
 */

import { useState } from 'react';
import {
  AlertTriangle,
  Clock,
  MapPin,
  TrendingUp,
  History,
  Lightbulb,
  ChevronDown,
  ChevronUp,
  X,
  Train,
  Zap,
} from 'lucide-react';
import type { ConflictAlert, RiskLevel, MemorySearchResult, SimilarCase } from '../../types/prediction';

interface ConflictAlertPanelProps {
  alert: ConflictAlert;
  similarCases?: MemorySearchResult | null;
  onClose?: () => void;
  onViewDetails?: () => void;
  onPrepareResolution?: () => void;
  isExpanded?: boolean;
}

const RISK_COLORS: Record<RiskLevel, { bg: string; border: string; text: string; icon: string }> = {
  safe: {
    bg: 'bg-green-500/10',
    border: 'border-green-500',
    text: 'text-green-500',
    icon: '🟢',
  },
  low_risk: {
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500',
    text: 'text-yellow-500',
    icon: '🟡',
  },
  high_risk: {
    bg: 'bg-orange-500/10',
    border: 'border-orange-500',
    text: 'text-orange-500',
    icon: '🟠',
  },
  critical: {
    bg: 'bg-red-500/10',
    border: 'border-red-500',
    text: 'text-red-500',
    icon: '🔴',
  },
};

const CONFLICT_TYPE_ICONS: Record<string, React.ReactNode> = {
  platform_conflict: <Train className="w-4 h-4" />,
  track_conflict: <Zap className="w-4 h-4" />,
  headway_violation: <Clock className="w-4 h-4" />,
  capacity_exceeded: <TrendingUp className="w-4 h-4" />,
  schedule_deviation: <Clock className="w-4 h-4" />,
  cascading_delay: <AlertTriangle className="w-4 h-4" />,
};

export function ConflictAlertPanel({
  alert,
  similarCases,
  onClose,
  onViewDetails,
  onPrepareResolution,
  isExpanded: initialExpanded = false,
}: ConflictAlertPanelProps) {
  const [isExpanded, setIsExpanded] = useState(initialExpanded);
  const colors = RISK_COLORS[alert.severity];
  const icon = CONFLICT_TYPE_ICONS[alert.type] || <AlertTriangle className="w-4 h-4" />;

  return (
    <div
      className={`rounded-lg border-l-4 ${colors.border} ${colors.bg} 
                  backdrop-blur-sm transition-all duration-300 overflow-hidden`}
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <span className="text-2xl">{colors.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`font-semibold ${colors.text}`}>{alert.train_id}</span>
                <span className="text-sm text-muted-foreground">-</span>
                <span className="text-sm font-medium">{alert.title}</span>
              </div>

              <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  <span>{alert.location}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  <span>{alert.time}</span>
                </div>
              </div>

              {/* Probability bar */}
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Probability</span>
                  <span className={`font-semibold ${colors.text}`}>
                    {Math.round(alert.probability * 100)}%
                  </span>
                </div>
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${colors.border.replace('border', 'bg')} transition-all duration-500`}
                    style={{ width: `${alert.probability * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 hover:bg-slate-700 rounded transition-colors"
            >
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="p-1 hover:bg-slate-700 rounded transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Contributing Factors (always visible) */}
        {alert.contributingFactors.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-700/50">
            <p className="text-xs text-muted-foreground mb-2">Cause:</p>
            <p className="text-sm">{alert.contributingFactors.slice(0, 2).join(', ')}</p>
          </div>
        )}
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-slate-700/50">
          {/* All Contributing Factors */}
          {alert.contributingFactors.length > 2 && (
            <div className="pt-3">
              <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                All Contributing Factors
              </p>
              <ul className="text-sm space-y-1">
                {alert.contributingFactors.map((factor, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-muted-foreground">•</span>
                    <span>{factor}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Similar Cases */}
          <div className="pt-3">
            <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
              <History className="w-3 h-3" />
              Similar Historical Cases
            </p>
            {similarCases && similarCases.similar_cases.length > 0 ? (
              <div className="space-y-2">
                {similarCases.similar_cases.slice(0, 3).map((case_, i) => (
                  <SimilarCaseCard key={i} case_={case_} />
                ))}
                <p className="text-xs text-muted-foreground">
                  {similarCases.similar_cases.length} similar cases found
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {alert.similarCasesCount > 0
                  ? `${alert.similarCasesCount} similar cases found`
                  : 'Searching for similar cases...'}
              </p>
            )}
          </div>

          {/* Suggested Resolution */}
          <div className="pt-3">
            <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
              <Lightbulb className="w-3 h-3" />
              Typical Resolution
            </p>
            <p className="text-sm">
              {similarCases?.suggested_resolution || alert.suggestedResolution || 'Delay 1 train'}
            </p>
            {similarCases && (
              <p className="text-xs text-muted-foreground mt-1">
                Average impact: {similarCases.typical_delay_min.toFixed(0)} min delay
              </p>
            )}
          </div>

          {/* Confidence */}
          <div className="pt-3 flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Prediction confidence</span>
            <span className={alert.confidence > 0.7 ? 'text-green-400' : 'text-yellow-400'}>
              {Math.round(alert.confidence * 100)}%
            </span>
          </div>

          {/* Actions */}
          <div className="pt-3 flex gap-2">
            {onViewDetails && (
              <button
                onClick={onViewDetails}
                className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 
                         rounded text-sm font-medium transition-colors"
              >
                View Details
              </button>
            )}
            {onPrepareResolution && (
              <button
                onClick={onPrepareResolution}
                className={`flex-1 px-4 py-2 rounded text-sm font-medium 
                          transition-colors ${colors.border.replace('border', 'bg')} 
                          hover:opacity-90 text-white`}
              >
                Prepare Resolution
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Sub-component for similar case display
function SimilarCaseCard({ case_ }: { case_: SimilarCase }) {
  return (
    <div className="p-2 bg-slate-800/50 rounded text-xs">
      <div className="flex items-center justify-between">
        <span className="font-medium">{case_.incident_type}</span>
        <span className="text-muted-foreground">
          {Math.round(case_.similarity_score * 100)}% match
        </span>
      </div>
      <p className="text-muted-foreground mt-1">
        {case_.location} • {case_.delay_duration_min}min delay • {case_.affected_trains} trains
      </p>
      {case_.resolution_types.length > 0 && (
        <p className="text-green-400 mt-1">→ {case_.resolution_types.join(', ')}</p>
      )}
    </div>
  );
}

export default ConflictAlertPanel;
