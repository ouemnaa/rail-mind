import { Clock, TrendingDown, Shield, AlertTriangle, CheckCircle, Database, ChevronRight } from 'lucide-react';

interface ResolutionCardProps {
  rank: number;
  title: string;
  description: string;
  delayReduction: number;
  riskLevel: 'low' | 'medium' | 'high';
  supportingCases: number;
  safetyChecks: { name: string; passed: boolean }[];
  isRecommended?: boolean;
  onClick?: () => void;
}

export function ResolutionCard({
  rank,
  title,
  description,
  delayReduction,
  riskLevel,
  supportingCases,
  safetyChecks,
  isRecommended,
  onClick,
}: ResolutionCardProps) {
  const getRiskColor = () => {
    switch (riskLevel) {
      case 'low': return 'text-success border-l-success';
      case 'medium': return 'text-warning border-l-warning';
      case 'high': return 'text-destructive border-l-destructive';
    }
  };

  return (
    <div 
      className={`resolution-card ${getRiskColor()} ${isRecommended ? 'ring-1 ring-primary/50' : ''} cursor-pointer`}
      onClick={onClick}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm ${
            isRecommended ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
          }`}>
            #{rank}
          </div>
          <div>
            <h3 className="font-medium">{title}</h3>
            {isRecommended && (
              <span className="text-xs text-primary">✦ Recommended</span>
            )}
          </div>
        </div>
        <ChevronRight className="w-5 h-5 text-muted-foreground" />
      </div>

      <p className="text-sm text-muted-foreground mb-4">{description}</p>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-muted/50 rounded-lg p-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
            <TrendingDown className="w-3 h-3" />
            <span>Delay Impact</span>
          </div>
          <div className="text-lg font-bold text-success">-{delayReduction} min</div>
        </div>
        <div className="bg-muted/50 rounded-lg p-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
            <AlertTriangle className="w-3 h-3" />
            <span>Risk Level</span>
          </div>
          <div className={`text-lg font-bold capitalize ${getRiskColor().split(' ')[0]}`}>
            {riskLevel}
          </div>
        </div>
        <div className="bg-muted/50 rounded-lg p-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
            <Database className="w-3 h-3" />
            <span>Past Cases</span>
          </div>
          <div className="text-lg font-bold text-primary">{supportingCases}</div>
        </div>
      </div>

      {/* Safety Checks */}
      <div className="flex items-center gap-4 text-xs">
        <span className="text-muted-foreground">Safety:</span>
        {safetyChecks.map((check, i) => (
          <div key={i} className="flex items-center gap-1">
            {check.passed ? (
              <CheckCircle className="w-3.5 h-3.5 text-success" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 text-warning" />
            )}
            <span className={check.passed ? 'text-success' : 'text-warning'}>{check.name}</span>
          </div>
        ))}
      </div>

      {/* Source Tag */}
      <div className="mt-3 pt-3 border-t border-border">
        <span className="text-xs text-muted-foreground italic">
          ✦ Inspired by {supportingCases} similar past resolutions
        </span>
      </div>
    </div>
  );
}
