import { AlertTriangle, Clock, Train, MapPin } from 'lucide-react';

interface Alert {
  id: string;
  type: 'conflict' | 'delay' | 'warning';
  title: string;
  location: string;
  time: string;
  severity: 'high' | 'medium' | 'low';
}

const alerts: Alert[] = [
  {
    id: '1',
    type: 'conflict',
    title: 'Platform Conflict Detected',
    location: 'West Gateway (STN-E)',
    time: '2 min ago',
    severity: 'high',
  },
  {
    id: '2',
    type: 'delay',
    title: 'Headway Violation',
    location: 'East Junction (STN-C)',
    time: '8 min ago',
    severity: 'medium',
  },
  {
    id: '3',
    type: 'delay',
    title: 'Capacity Warning',
    location: 'Harbor Port (STN-G)',
    time: '15 min ago',
    severity: 'medium',
  },
  {
    id: '4',
    type: 'warning',
    title: 'Maintenance Window',
    location: 'North Terminal (STN-B)',
    time: '1 hour ago',
    severity: 'low',
  },
];

interface AlertFeedProps {
  onAlertClick?: (alert: Alert) => void;
}

export function AlertFeed({ onAlertClick }: AlertFeedProps) {
  const getAlertStyle = (alert: Alert) => {
    switch (alert.severity) {
      case 'high':
        return 'border-l-destructive bg-destructive/5 hover:bg-destructive/10';
      case 'medium':
        return 'border-l-warning bg-warning/5 hover:bg-warning/10';
      default:
        return 'border-l-muted-foreground bg-muted/50 hover:bg-muted';
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'conflict':
        return <AlertTriangle className="w-4 h-4 text-destructive" />;
      case 'delay':
        return <Clock className="w-4 h-4 text-warning" />;
      default:
        return <Train className="w-4 h-4 text-muted-foreground" />;
    }
  };

  return (
    <div className="glass-panel p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Live Alerts</h3>
        <span className="text-xs bg-destructive/20 text-destructive px-2 py-1 rounded-full">
          {alerts.filter(a => a.severity === 'high').length} Critical
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2">
        {alerts.map((alert) => (
          <div
            key={alert.id}
            onClick={() => onAlertClick?.(alert)}
            className={`p-3 rounded-lg border-l-4 cursor-pointer transition-all duration-200 ${getAlertStyle(alert)}`}
          >
            <div className="flex items-start gap-3">
              {getIcon(alert.type)}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{alert.title}</p>
                <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                  <MapPin className="w-3 h-3" />
                  <span className="truncate">{alert.location}</span>
                </div>
                <span className="text-xs text-muted-foreground">{alert.time}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
