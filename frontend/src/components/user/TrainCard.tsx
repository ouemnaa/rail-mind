/**
 * TrainCard Component
 * ===================
 * 
 * A friendly, passenger-focused card displaying train status and delay information.
 * Features emoji badges, humanized status messages, and accessible design.
 * Supports light/dark themes.
 */

import { Clock, MapPin, ChevronRight } from 'lucide-react';

export interface TrainCardProps {
  trainId: string;
  trainType: string;
  origin: string | null;
  destination: string | null;
  delaySec: number;
  status: string;
  isHighlighted?: boolean;
  onClick?: () => void;
}

// Get emoji badge based on delay severity
function getDelayBadge(delaySec: number): { emoji: string; color: string; bgColor: string; bgColorLight: string } {
  const delayMin = delaySec / 60;
  if (delayMin >= 15) return { emoji: '🔴', color: 'text-red-500', bgColor: 'bg-red-500/10', bgColorLight: 'bg-red-50' };
  if (delayMin >= 10) return { emoji: '🟠', color: 'text-orange-500', bgColor: 'bg-orange-500/10', bgColorLight: 'bg-orange-50' };
  if (delayMin >= 5) return { emoji: '🟡', color: 'text-yellow-500', bgColor: 'bg-yellow-500/10', bgColorLight: 'bg-yellow-50' };
  if (delayMin >= 1) return { emoji: '🟡', color: 'text-yellow-500', bgColor: 'bg-yellow-400/10', bgColorLight: 'bg-yellow-50' };
  return { emoji: '🟢', color: 'text-emerald-500', bgColor: 'bg-emerald-500/10', bgColorLight: 'bg-emerald-50' };
}

// Format delay in a human-friendly way
function formatDelay(delaySec: number): string {
  if (delaySec < 60) return 'On time';
  
  const minutes = Math.floor(delaySec / 60);
  const seconds = delaySec % 60;
  
  if (minutes < 10 && seconds > 0) {
    return `${minutes}m ${seconds}s late`;
  }
  return `${minutes} min late`;
}

// Get a friendly status message
function getStatusMessage(delaySec: number): string {
  const delayMin = delaySec / 60;
  
  if (delayMin < 1) return 'Running smoothly! 🎉';
  if (delayMin < 5) return 'Slight delay — almost there!';
  if (delayMin < 10) return 'Running a bit behind — hang tight!';
  if (delayMin < 15) return 'Significant delay — we appreciate your patience';
  return 'Major delay — please check alternative routes';
}

export function TrainCard({
  trainId,
  trainType,
  origin,
  destination,
  delaySec,
  isHighlighted = false,
  onClick,
}: TrainCardProps) {
  const { emoji, color, bgColor } = getDelayBadge(delaySec);
  const delayText = formatDelay(delaySec);
  const statusMessage = getStatusMessage(delaySec);
  
  // Format train type for display
  const displayType = trainType === 'REG' ? 'Regional' : 
                      trainType === 'FR' ? 'Frecciarossa' : 
                      trainType === 'IC' ? 'InterCity' : trainType;

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-6 rounded-3xl border transition-all duration-300
        hover:scale-[1.01] hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50
        dark:bg-slate-800/50 dark:border-slate-700/50 dark:hover:bg-slate-800
        bg-white border-slate-200 hover:bg-slate-50 shadow-sm
        ${isHighlighted ? `${bgColor} dark:${bgColor}` : ''}
        ${delaySec > 600 ? 'animate-pulse-subtle' : ''}
      `}
      aria-label={`Train ${trainId}, ${delayText}. ${statusMessage}`}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Left: Train info */}
        <div className="flex items-start gap-4 flex-1 min-w-0">
          {/* Emoji Badge */}
          <div className={`
            w-16 h-16 rounded-2xl flex items-center justify-center text-3xl shrink-0
            ${bgColor}
          `}>
            {emoji}
          </div>
          
          <div className="flex-1 min-w-0">
            {/* Train ID and Type */}
            <div className="flex items-center gap-3 mb-2">
              <span className="font-bold text-xl dark:text-white text-slate-900">{trainId}</span>
              <span className={`
                text-xs px-3 py-1 rounded-full font-semibold
                ${trainType === 'FR' ? 'bg-red-500/20 text-red-500' : 
                  trainType === 'IC' ? 'bg-blue-500/20 text-blue-500' : 
                  'bg-slate-500/20 dark:text-slate-400 text-slate-500'}
              `}>
                {displayType}
              </span>
            </div>
            
            {/* Route */}
            <div className="flex items-center gap-2 text-base dark:text-slate-400 text-slate-600 mb-3">
              <MapPin className="w-4 h-4 shrink-0" />
              <span className="truncate">
                {origin || 'Unknown'} → {destination || 'Unknown'}
              </span>
            </div>
            
            {/* Status Message */}
            {isHighlighted && (
              <p className={`text-base font-medium ${color}`}>
                {statusMessage}
              </p>
            )}
          </div>
        </div>
        
        {/* Right: Delay info */}
        <div className="flex flex-col items-end gap-2 shrink-0">
          <div className={`flex items-center gap-2 text-lg font-bold ${color}`}>
            <Clock className="w-5 h-5" />
            <span>{delayText}</span>
          </div>
          
          {!isHighlighted && (
            <ChevronRight className="w-5 h-5 dark:text-slate-500 text-slate-400 mt-2" />
          )}
        </div>
      </div>
    </button>
  );
}

// Compact version for the list
export function TrainCardCompact({
  trainId,
  trainType,
  origin,
  destination,
  delaySec,
  onClick,
}: TrainCardProps) {
  const { emoji, color } = getDelayBadge(delaySec);
  const delayText = formatDelay(delaySec);

  return (
    <button
      onClick={onClick}
      className="
        w-full flex items-center justify-between p-4 rounded-2xl border transition-all duration-200
        dark:bg-slate-800/30 dark:border-slate-700/30 dark:hover:bg-slate-800/60
        bg-white border-slate-200/80 hover:bg-slate-50 shadow-sm
        focus:outline-none focus:ring-2 focus:ring-blue-500/50
      "
      aria-label={`Train ${trainId}, ${delayText}`}
    >
      <div className="flex items-center gap-4">
        <span className="text-2xl">{emoji}</span>
        <div className="text-left">
          <div className="flex items-center gap-2">
            <span className="font-semibold dark:text-white text-slate-900">{trainId}</span>
            <span className="text-xs dark:text-slate-500 text-slate-400">{trainType}</span>
          </div>
          <div className="text-sm dark:text-slate-400 text-slate-500 truncate max-w-[180px]">
            {origin} → {destination}
          </div>
        </div>
      </div>
      
      <div className={`text-base font-semibold ${color}`}>
        {delayText}
      </div>
    </button>
  );
}

export default TrainCard;
