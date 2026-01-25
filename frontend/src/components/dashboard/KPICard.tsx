import { LucideIcon } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  change?: number;
  icon: LucideIcon;
  status?: 'normal' | 'warning' | 'critical';
}

export function KPICard({ title, value, unit, change, icon: Icon, status = 'normal' }: KPICardProps) {
  const getStatusColor = () => {
    switch (status) {
      case 'warning': return 'text-warning';
      case 'critical': return 'text-destructive';
      default: return 'text-primary';
    }
  };

  const getGlowClass = () => {
    switch (status) {
      case 'warning': return 'glow-warning';
      case 'critical': return 'glow-danger';
      default: return '';
    }
  };

  return (
    <div className={`kpi-card ${getGlowClass()}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground uppercase tracking-wider">{title}</span>
        <Icon className={`w-4 h-4 ${getStatusColor()}`} />
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-bold ${getStatusColor()}`}>{value}</span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
      </div>
      {change !== undefined && (
        <div className={`text-xs ${change >= 0 ? 'text-success' : 'text-destructive'}`}>
          {change >= 0 ? '↑' : '↓'} {Math.abs(change)}% from last hour
        </div>
      )}
    </div>
  );
}
