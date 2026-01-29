import { ArrowLeft, Brain, FileText, Network, AlertTriangle, CheckCircle, XCircle, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';

interface ExplanationViewProps {
  onBack: () => void;
}

const similarityBreakdown = [
  { label: 'Numeric Similarity', value: 94, description: 'Time of day, passenger count, track occupancy' },
  { label: 'Text Similarity', value: 87, description: 'Incident descriptions and operator notes' },
  { label: 'Topology Similarity', value: 91, description: 'Network state and station connections' },
];

const includedFactors = [
  'Platform availability status',
  'Real-time passenger density',
  'Historical resolution success rate',
  'Current signal configuration',
  'Adjacent track occupancy',
];

const excludedFactors = [
  { factor: 'Weather conditions', reason: 'Not relevant to indoor platform conflict' },
  { factor: 'Maintenance schedule', reason: 'No scheduled maintenance within resolution window' },
  { factor: 'Historical data > 2 years', reason: 'Outdated after signal system upgrade' },
];

export function ExplanationView({ onBack }: ExplanationViewProps) {
  return (
    <div className="h-full flex flex-col gap-8 animate-fade-in">
      {/* Premium Header */}
      <div className="flex items-center justify-between gap-6">
        <div className="flex items-center gap-6">
          <Button 
            variant="outline" 
            size="icon" 
            onClick={onBack} 
            className="w-14 h-14 rounded-2xl border-primary/20 bg-primary/5 hover:bg-primary/10 transition-all shrink-0"
          >
            <ArrowLeft className="w-6 h-6 text-primary" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="font-bold text-3xl tracking-tight">Decision Engineering</h1>
              <span className="px-3 py-1 bg-accent/20 text-accent text-[10px] font-bold rounded-full border border-accent/30 uppercase tracking-widest">
                Reasoning Artifact
              </span>
            </div>
            <p className="text-muted-foreground italic flex items-center gap-2">
              <Info className="w-4 h-4 text-primary" />
              Detailed breakdown of the AI's neural path and historical context mapping.
            </p>
          </div>
        </div>

        <div className="hidden xl:flex glass-panel px-6 py-4 items-center gap-8 border-primary/20">
          <div className="flex flex-col">
            <span className="text-xs text-muted-foreground uppercase font-bold tracking-tighter">Model Version</span>
            <span className="text-lg font-black text-primary">v4.2-NEURAL</span>
          </div>
          <div className="w-px h-8 bg-border/50" />
          <div className="flex flex-col">
            <span className="text-xs text-muted-foreground uppercase font-bold tracking-tighter">Latency</span>
            <span className="text-lg font-black text-success">148ms</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Metrics & Evidence */}
        <div className="lg:col-span-4 space-y-6">
          {/* Similarity Core */}
          <div className="glass-panel p-6 border-t-4 border-t-primary">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <Brain className="w-5 h-5 text-primary" />
              </div>
              <h3 className="font-bold uppercase tracking-wider text-sm opacity-70">Similarity Engine</h3>
            </div>

            <div className="space-y-6">
              {similarityBreakdown.map((item, i) => (
                <div key={i} className="group">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold group-hover:text-primary transition-colors">{item.label}</span>
                    <span className="text-sm font-mono font-black text-primary bg-primary/10 px-2 py-0.5 rounded">{item.value}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden mb-2">
                    <div 
                      className="h-full bg-primary transition-all duration-1000 ease-out" 
                      style={{ width: `${item.value}%` }} 
                    />
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-tight px-1">{item.description}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 pt-6 border-t border-border/50">
              <div className="flex items-center justify-between items-end">
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase font-black tracking-tighter mb-1">Composite Score</div>
                  <div className="text-4xl font-black text-gradient-primary leading-none">91.4%</div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] items-center justify-center text-success flex gap-1 font-bold mb-1 uppercase tracking-widest">
                    <CheckCircle className="w-3 h-3" /> Optimal
                  </div>
                  <div className="text-[10px] text-muted-foreground">Threshold: 85%</div>
                </div>
              </div>
            </div>
          </div>

          {/* Verification Status */}
          <div className="glass-panel p-6">
            <h3 className="font-bold uppercase tracking-wider text-xs opacity-70 mb-4">Neural Gate Verification</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-success/5 border border-success/20 rounded-xl transition-all hover:bg-success/10">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-success/20 flex items-center justify-center">
                    <CheckCircle className="w-4 h-4 text-success" />
                  </div>
                  <span className="text-xs font-bold">Safety Compliance</span>
                </div>
                <span className="text-[10px] font-black text-success uppercase">Verified</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-blue-500/5 border border-blue-500/20 rounded-xl transition-all hover:bg-blue-500/10">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                    <Network className="w-4 h-4 text-blue-400" />
                  </div>
                  <span className="text-xs font-bold">Network Topology</span>
                </div>
                <span className="text-[10px] font-black text-blue-400 uppercase">Synchronized</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Reasoning & Factors */}
        <div className="lg:col-span-8 space-y-6">
          {/* Main Confidence Statement */}
          <div className="glass-panel p-8 bg-gradient-to-br from-card/80 to-primary/5 transition-all hover:shadow-2xl hover:shadow-primary/5">
             <div className="flex items-center gap-3 mb-6">
               <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center border border-accent/20">
                 <FileText className="w-6 h-6 text-accent" />
               </div>
               <h3 className="font-bold tracking-tight text-xl">Engine Confidence Statement</h3>
             </div>

             <div className="p-6 bg-background/60 backdrop-blur-md rounded-2xl border border-border/50 relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <Brain className="w-24 h-24" />
                </div>
                <p className="text-lg leading-relaxed text-foreground/90 relative z-10">
                  The recommended resolution has been successfully applied in <strong className="text-primary text-xl px-1">12 out of 14</strong> similar 
                  historical cases, representing an <strong className="text-success text-xl px-1">86%</strong> success rate. 
                  Analytical validation confirms that the current conflict matches the <strong className="text-accent underline decoration-accent/30 decoration-2 underline-offset-4">Topological Signature</strong> 
                  of these successful precedents while excluding noisy variables from 2024 signal upgrades.
                </p>
             </div>

             <div className="mt-8 flex flex-wrap gap-6 pt-6 border-t border-border/50">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground uppercase font-black tracking-tighter">Confidence</span>
                  <span className="text-sm font-bold text-success">HIGH STABILITY</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground uppercase font-black tracking-tighter">Reliability</span>
                  <span className="text-sm font-bold text-primary">RELIABLE PATHWAY</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground uppercase font-black tracking-tighter">Traceability</span>
                  <span className="text-sm font-bold text-accent font-mono uppercase">100% LOGGED</span>
                </div>
             </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Factors Considered */}
            <div className="glass-panel p-6 border-l-4 border-l-success">
              <div className="flex items-center gap-3 mb-5">
                <CheckCircle className="w-5 h-5 text-success" />
                <h3 className="font-bold uppercase tracking-wider text-sm opacity-70">Inclusion Logic</h3>
              </div>
              <div className="space-y-4">
                {includedFactors.map((factor, i) => (
                  <div key={i} className="flex items-center gap-3 group">
                    <div className="w-1.5 h-1.5 rounded-full bg-success group-hover:scale-150 transition-transform" />
                    <span className="text-sm font-medium opacity-90">{factor}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Factors Excluded */}
            <div className="glass-panel p-6 border-l-4 border-l-muted-foreground/30">
              <div className="flex items-center gap-3 mb-5">
                <XCircle className="w-5 h-5 text-muted-foreground" />
                <h3 className="font-bold uppercase tracking-wider text-sm opacity-70">Pruning Logic</h3>
              </div>
              <div className="space-y-3">
                {excludedFactors.map((item, i) => (
                  <div key={i} className="p-3 bg-muted/20 rounded-xl border border-border/30 hover:bg-muted/30 transition-colors">
                    <div className="flex items-center gap-2 text-xs font-black text-muted-foreground uppercase mb-1">
                      <AlertTriangle className="w-3 h-3" />
                      {item.factor}
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-relaxed italic">{item.reason}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
