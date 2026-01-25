import { X, Train, Clock, AlertTriangle, MapPin, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ConflictDetailProps {
  onClose: () => void;
  onResolve: () => void;
}

const affectedTrains = [
  { id: 'TR-2847', destination: 'Central Hub', delay: '+12 min', status: 'waiting' },
  { id: 'TR-1923', destination: 'North Terminal', delay: '+8 min', status: 'approaching' },
  { id: 'TR-3156', destination: 'Harbor Port', delay: '+5 min', status: 'queued' },
];

const timelineEvents = [
  { time: '14:23', event: 'Conflict detected', status: 'past' },
  { time: '14:25', event: 'Memory search initiated', status: 'past' },
  { time: '14:26', event: 'Similar cases retrieved', status: 'current' },
  { time: '14:28', event: 'Resolution pending', status: 'future' },
  { time: '14:35', event: 'Estimated resolution', status: 'future' },
];

export function ConflictDetail({ onClose, onResolve }: ConflictDetailProps) {
  return (
    <div className="glass-panel h-full flex flex-col animate-slide-in-right">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-destructive/20 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-destructive" />
          </div>
          <div>
            <h2 className="font-semibold">Platform Conflict</h2>
            <p className="text-sm text-muted-foreground">West Gateway • STN-E</p>
          </div>
        </div>
        <button onClick={onClose} className="p-2 hover:bg-muted rounded-lg transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Classification */}
        <div>
          <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Classification</h3>
          <div className="flex flex-wrap gap-2">
            <span className="status-badge status-conflict">Platform Conflict</span>
            <span className="status-badge bg-primary/20 text-primary border border-primary/30">Priority: High</span>
            <span className="status-badge bg-muted text-muted-foreground">Auto-detected</span>
          </div>
        </div>

        {/* Affected Trains */}
        <div>
          <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Affected Trains</h3>
          <div className="space-y-2">
            {affectedTrains.map((train) => (
              <div key={train.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Train className="w-4 h-4 text-primary" />
                  <div>
                    <p className="text-sm font-mono font-medium">{train.id}</p>
                    <p className="text-xs text-muted-foreground">{train.destination}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-warning">{train.delay}</p>
                  <p className="text-xs text-muted-foreground capitalize">{train.status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Timeline */}
        <div>
          <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Delay Propagation</h3>
          <div className="relative pl-4">
            <div className="absolute left-1.5 top-2 bottom-2 w-px bg-border" />
            {timelineEvents.map((event, i) => (
              <div key={i} className="flex items-center gap-4 py-2">
                <div className={`timeline-marker ${
                  event.status === 'current' 
                    ? 'bg-primary animate-pulse' 
                    : event.status === 'past' 
                      ? 'bg-success' 
                      : 'bg-muted'
                }`} />
                <span className="text-xs font-mono text-muted-foreground w-12">{event.time}</span>
                <span className={`text-sm ${event.status === 'current' ? 'text-primary font-medium' : ''}`}>
                  {event.event}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="p-4 border-t border-border">
        <Button 
          onClick={onResolve} 
          className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
        >
          View Resolution Options
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
