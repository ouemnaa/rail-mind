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
      className={`relative group bg-card/40 backdrop-blur-md border border-border/50 rounded-2xl p-6 transition-all duration-500 hover:bg-card/60 hover:border-primary/50 hover:shadow-2xl hover:shadow-primary/10 cursor-pointer overflow-hidden ${
        isRecommended ? 'ring-2 ring-primary/40' : ''
      }`}
      onClick={onClick}
    >
      {/* Glow Effect on Hover */}
      <div className="absolute -inset-px bg-gradient-to-br from-primary/20 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl pointer-events-none" />

      {/* Header */}
      <div className="relative flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-black text-lg transition-transform duration-500 group-hover:scale-110 ${
            isRecommended 
              ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/20' 
              : 'bg-muted/80 text-muted-foreground'
          }`}>
            {rank}
          </div>
          <div>
            <h3 className="text-xl font-bold tracking-tight group-hover:text-primary transition-colors">{title}</h3>
            {isRecommended && (
              <div className="flex items-center gap-1 mt-1">
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                <span className="text-[10px] uppercase font-black tracking-widest text-primary">Highest Confidence</span>
              </div>
            )}
          </div>
        </div>
        <div className="w-10 h-10 rounded-full bg-muted/30 flex items-center justify-center group-hover:bg-primary/20 group-hover:text-primary transition-all">
          <ChevronRight className="w-6 h-6" />
        </div>
      </div>

      <p className="relative text-sm text-muted-foreground leading-relaxed mb-6 h-12 line-clamp-2 italic">
        "{description}"
      </p>

      {/* Metrics Dashboard */}
      <div className="relative grid grid-cols-3 gap-2 mb-6">
        <div className="bg-background/40 border border-border/50 rounded-xl p-3 flex flex-col items-center text-center group-hover:border-primary/20 transition-colors">
          <TrendingDown className="w-4 h-4 text-success mb-1" />
          <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-tighter">Savings</span>
          <div className="text-lg font-black text-success">-{delayReduction}m</div>
        </div>
        <div className="bg-background/40 border border-border/50 rounded-xl p-3 flex flex-col items-center text-center group-hover:border-primary/20 transition-colors">
          <AlertTriangle className={`w-4 h-4 mb-1 ${riskLevel === 'low' ? 'text-success' : 'text-warning'}`} />
          <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-tighter">Risk</span>
          <div className={`text-lg font-black capitalize ${riskLevel === 'low' ? 'text-success' : 'text-warning'}`}>
            {riskLevel}
          </div>
        </div>
        <div className="bg-background/40 border border-border/50 rounded-xl p-3 flex flex-col items-center text-center group-hover:border-primary/20 transition-colors">
          <Database className="w-4 h-4 text-primary mb-1" />
          <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-tighter">Evidence</span>
          <div className="text-lg font-black text-primary">{supportingCases}</div>
        </div>
      </div>

      {/* Safety Matrix */}
      <div className="relative flex flex-wrap gap-2 pt-4 border-t border-border/50">
        {safetyChecks.map((check, i) => (
          <div 
            key={i} 
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-colors ${
              check.passed 
                ? 'bg-success/10 text-success border border-success/20' 
                : 'bg-destructive/10 text-destructive border border-destructive/20'
            }`}
          >
            {check.passed ? (
              <CheckCircle className="w-3 h-3" />
            ) : (
              <AlertTriangle className="w-3 h-3" />
            )}
            {check.name}
          </div>
        ))}
      </div>
    </div>
  );
}
