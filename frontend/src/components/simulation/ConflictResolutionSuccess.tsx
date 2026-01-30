/**
 * Conflict Resolution Success Toast
 * ==================================
 * 
 * Displays a beautiful success notification when a conflict
 * is detected, resolved, and archived with KPI improvements.
 */

import { useEffect, useState } from 'react';
import { CheckCircle, TrendingDown, Zap, Archive, X } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export interface ResolutionSuccessData {
  conflict_id: string;
  conflict_type: string;
  location: string;
  resolution_strategy: string;
  delay_reduction_percent: number;
  efficiency_gain_percent: number;
  confidence_score: number;
  time_to_resolve_sec: number;
}

interface ConflictResolutionSuccessProps {
  data: ResolutionSuccessData;
  onClose: () => void;
  autoDismiss?: number; // milliseconds, 0 = no auto-dismiss
}

/**
 * Toast notification for successful conflict resolution
 */
export const ConflictResolutionSuccess = ({
  data,
  onClose,
  autoDismiss = 8000,
}: ConflictResolutionSuccessProps) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (autoDismiss > 0) {
      const timer = setTimeout(() => {
        setIsVisible(false);
        setTimeout(onClose, 300); // Wait for animation
      }, autoDismiss);

      return () => clearTimeout(timer);
    }
  }, [autoDismiss, onClose]);

  if (!isVisible) return null;

  const delayColor = data.delay_reduction_percent >= 30 ? 'text-emerald-400' : 'text-yellow-400';
  const efficiencyColor = data.efficiency_gain_percent >= 20 ? 'text-emerald-400' : 'text-yellow-400';
  const confidenceColor = data.confidence_score >= 80 ? 'text-emerald-400' : 'text-orange-400';

  return (
    <div className="fixed bottom-4 right-4 z-50 animate-in slide-in-from-right-4 fade-in-0 duration-300">
      <Card className="w-96 border-emerald-500/30 bg-emerald-500/5 shadow-2xl">
        {/* Header with success icon */}
        <div className="flex items-start justify-between p-4 border-b border-emerald-500/20">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center animate-pulse">
              <CheckCircle className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h3 className="font-bold text-emerald-400">Conflict Resolved!</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                {data.conflict_type.toUpperCase()} at {data.location}
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setIsVisible(false);
              setTimeout(onClose, 300);
            }}
            className="p-1 hover:bg-emerald-500/10 rounded transition-colors"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* Resolution strategy */}
        <div className="px-4 py-3 border-b border-emerald-500/20">
          <p className="text-xs text-muted-foreground mb-1">Applied Strategy</p>
          <p className="font-semibold text-sm text-emerald-300">
            {data.resolution_strategy}
          </p>
        </div>

        {/* KPI Improvements */}
        <div className="p-4 space-y-3">
          <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
            📊 Improvements
          </h4>

          {/* Delay Reduction */}
          <div className="flex items-center justify-between p-3 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-emerald-400" />
              <span className="text-sm">Delay Reduction</span>
            </div>
            <span className={`font-bold text-sm ${delayColor}`}>
              {data.delay_reduction_percent.toFixed(1)}%
            </span>
          </div>

          {/* Efficiency Gain */}
          <div className="flex items-center justify-between p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-blue-400" />
              <span className="text-sm">Efficiency Gain</span>
            </div>
            <span className={`font-bold text-sm ${efficiencyColor}`}>
              {data.efficiency_gain_percent.toFixed(1)}%
            </span>
          </div>

          {/* Confidence Score */}
          <div className="flex items-center justify-between p-3 bg-purple-500/10 rounded-lg border border-purple-500/20">
            <div className="flex items-center gap-2">
              <Archive className="w-4 h-4 text-purple-400" />
              <span className="text-sm">Confidence</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-500"
                  style={{ width: `${Math.min(data.confidence_score, 100)}%` }}
                />
              </div>
              <span className={`font-bold text-sm w-12 text-right ${confidenceColor}`}>
                {data.confidence_score.toFixed(0)}%
              </span>
            </div>
          </div>
        </div>

        {/* Footer with metadata */}
        <div className="px-4 py-3 border-t border-emerald-500/20 flex items-center justify-between bg-emerald-500/5">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              ID: {data.conflict_id.substring(0, 8)}
            </Badge>
            <span className="text-xs text-muted-foreground">
              ⏱️ {data.time_to_resolve_sec.toFixed(1)}s
            </span>
          </div>
          <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
            ✓ Archived
          </Badge>
        </div>
      </Card>
    </div>
  );
};

/**
 * Hook for managing resolution success notifications
 */
export function useResolutionSuccess() {
  const [notification, setNotification] = useState<ResolutionSuccessData | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  const showSuccess = (data: ResolutionSuccessData) => {
    setNotification(data);
    setIsVisible(true);
  };

  const dismissSuccess = () => {
    setIsVisible(false);
    setTimeout(() => setNotification(null), 300);
  };

  return {
    notification,
    isVisible,
    showSuccess,
    dismissSuccess,
  };
}
