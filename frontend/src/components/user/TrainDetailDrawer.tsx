/**
 * TrainDetailDrawer Component
 * ===========================
 * 
 * A lightweight detail drawer showing train information for passengers.
 * Includes ETA, platform info, and friendly guidance.
 * Supports light/dark themes.
 */

import { X, Clock, MapPin, Train, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { TrainData } from '@/hooks/useUnifiedSimulation';

interface TrainDetailDrawerProps {
  train: TrainData | null;
  isOpen: boolean;
  onClose: () => void;
}

function formatDelay(delaySec: number): string {
  if (delaySec < 60) return 'On time';
  const minutes = Math.floor(delaySec / 60);
  return `${minutes} min late`;
}

function getDelayBadge(delaySec: number): { emoji: string; color: string; label: string } {
  const delayMin = delaySec / 60;
  if (delayMin >= 15) return { emoji: '🔴', color: 'text-red-500', label: 'Major Delay' };
  if (delayMin >= 10) return { emoji: '🟠', color: 'text-orange-500', label: 'Significant Delay' };
  if (delayMin >= 5) return { emoji: '🟡', color: 'text-yellow-500', label: 'Minor Delay' };
  if (delayMin >= 1) return { emoji: '🟡', color: 'text-yellow-500', label: 'Slight Delay' };
  return { emoji: '🟢', color: 'text-emerald-500', label: 'On Time' };
}

function getPassengerGuidance(train: TrainData): string {
  const delayMin = train.delay_sec / 60;
  
  if (delayMin < 1) {
    return `Your train is running on schedule. Please proceed to the platform when ready.`;
  }
  if (delayMin < 5) {
    return `Expect a short wait of about ${Math.ceil(delayMin)} minutes. The train will arrive shortly.`;
  }
  if (delayMin < 10) {
    return `Please allow extra time — approximately ${Math.ceil(delayMin)} minute wait expected. Check the departure boards for platform updates.`;
  }
  if (delayMin < 15) {
    return `We apologize for the delay. Estimated wait: ${Math.ceil(delayMin)} minutes. Please check for announcements and consider refreshments nearby.`;
  }
  return `Significant delay of ${Math.ceil(delayMin)}+ minutes. Please check alternative connections or speak with station staff for assistance.`;
}

export function TrainDetailDrawer({ train, isOpen, onClose }: TrainDetailDrawerProps) {
  if (!isOpen || !train) return null;

  const { emoji, color, label } = getDelayBadge(train.delay_sec);
  const guidance = getPassengerGuidance(train);
  const displayType = train.train_type === 'REG' ? 'Regional' : 
                      train.train_type === 'FR' ? 'Frecciarossa' : 
                      train.train_type === 'IC' ? 'InterCity' : train.train_type;

  // Calculate estimated arrival
  const now = new Date();
  const estimatedArrival = new Date(now.getTime() + train.delay_sec * 1000);

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />
      
      {/* Drawer */}
      <div 
        className="fixed bottom-0 left-0 right-0 z-50 rounded-t-[2rem] shadow-2xl 
                   animate-slide-up max-h-[90vh] overflow-y-auto
                   dark:bg-slate-900 bg-white"
        role="dialog"
        aria-modal="true"
        aria-labelledby="train-detail-title"
      >
        {/* Handle */}
        <div className="flex justify-center pt-4 pb-3">
          <div className="w-14 h-1.5 rounded-full dark:bg-slate-700 bg-slate-300" />
        </div>
        
        {/* Header */}
        <div className="px-8 pb-6 border-b dark:border-slate-800 border-slate-200">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-5">
              <div className={`
                w-20 h-20 rounded-2xl flex items-center justify-center text-4xl
                ${train.delay_sec > 300 ? 'bg-orange-500/10' : 'bg-emerald-500/10'}
              `}>
                {emoji}
              </div>
              <div>
                <h2 id="train-detail-title" className="text-3xl font-bold flex items-center gap-3 dark:text-white text-slate-900">
                  <Train className="w-7 h-7" />
                  {train.train_id}
                </h2>
                <p className="text-lg dark:text-slate-400 text-slate-500 mt-1">{displayType}</p>
                <span className={`inline-flex items-center gap-2 text-base font-semibold mt-2 ${color}`}>
                  {label}
                </span>
              </div>
            </div>
            
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={onClose} 
              className="rounded-full w-12 h-12 dark:hover:bg-slate-800 hover:bg-slate-100"
            >
              <X className="w-6 h-6" />
              <span className="sr-only">Close</span>
            </Button>
          </div>
        </div>
        
        {/* Content */}
        <div className="p-8 space-y-8">
          {/* Route Info */}
          <div className="flex items-center gap-6 p-6 rounded-2xl dark:bg-slate-800/50 bg-slate-100">
            <div className="flex-1">
              <div className="text-sm dark:text-slate-500 text-slate-400 uppercase tracking-wider mb-2">From</div>
              <div className="font-bold text-xl dark:text-white text-slate-900">{train.current_station || 'En Route'}</div>
            </div>
            <div className="text-4xl dark:text-slate-600 text-slate-300">→</div>
            <div className="flex-1 text-right">
              <div className="text-sm dark:text-slate-500 text-slate-400 uppercase tracking-wider mb-2">To</div>
              <div className="font-bold text-xl dark:text-white text-slate-900">{train.next_station || 'Destination'}</div>
            </div>
          </div>
          
          {/* Time Info */}
          <div className="grid grid-cols-2 gap-6">
            <div className="p-6 rounded-2xl dark:bg-slate-800 bg-white border dark:border-slate-700 border-slate-200">
              <div className="flex items-center gap-2 dark:text-slate-400 text-slate-500 mb-3">
                <Clock className="w-5 h-5" />
                <span className="text-sm uppercase tracking-wider font-medium">Delay</span>
              </div>
              <div className={`text-3xl font-bold ${color}`}>
                {formatDelay(train.delay_sec)}
              </div>
            </div>
            
            <div className="p-6 rounded-2xl dark:bg-slate-800 bg-white border dark:border-slate-700 border-slate-200">
              <div className="flex items-center gap-2 dark:text-slate-400 text-slate-500 mb-3">
                <MapPin className="w-5 h-5" />
                <span className="text-sm uppercase tracking-wider font-medium">Status</span>
              </div>
              <div className="text-2xl font-bold capitalize dark:text-white text-slate-900">
                {train.status.replace(/_/g, ' ')}
              </div>
            </div>
          </div>
          
          {/* ETA */}
          <div className="p-6 rounded-2xl bg-blue-500/10 border border-blue-500/20">
            <div className="flex items-center gap-2 text-blue-500 mb-3">
              <Clock className="w-5 h-5" />
              <span className="text-sm font-semibold uppercase tracking-wider">Estimated Arrival</span>
            </div>
            <div className="text-4xl font-bold text-blue-500">
              {estimatedArrival.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
          
          {/* Passenger Guidance */}
          <div className="p-6 rounded-2xl dark:bg-slate-800/50 bg-slate-50 border dark:border-slate-700 border-slate-200">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center shrink-0">
                <Info className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <h3 className="font-bold text-lg mb-2 text-blue-500">Passenger Guidance</h3>
                <p className="text-base leading-relaxed dark:text-slate-300 text-slate-600">
                  {guidance}
                </p>
              </div>
            </div>
          </div>
          
          {/* Speed Info */}
          <div className="flex items-center justify-between text-base dark:text-slate-400 text-slate-500">
            <span>Current Speed</span>
            <span className="font-mono font-semibold dark:text-white text-slate-900">{Math.round(train.speed_kmh)} km/h</span>
          </div>
        </div>
        
        {/* Footer spacer for safe area */}
        <div className="h-12" />
      </div>
    </>
  );
}

export default TrainDetailDrawer;
