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
    <div className="h-full flex flex-col animate-fade-in">
      {/* Header */}
      <div className="glass-panel p-4 mb-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={onBack} className="shrink-0">
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h2 className="font-semibold">Decision Explanation</h2>
            <p className="text-sm text-muted-foreground">Understanding the AI reasoning</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Similarity Breakdown */}
        <div className="glass-panel p-4">
          <div className="flex items-center gap-2 mb-4">
            <Brain className="w-5 h-5 text-primary" />
            <h3 className="font-medium">Similarity Breakdown</h3>
          </div>

          <div className="space-y-4">
            {similarityBreakdown.map((item, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{item.label}</span>
                  <span className="text-sm font-mono text-primary">{item.value}%</span>
                </div>
                <Progress value={item.value} className="h-2 mb-1" />
                <p className="text-xs text-muted-foreground">{item.description}</p>
              </div>
            ))}
          </div>

          {/* Composite Score */}
          <div className="mt-6 p-4 bg-primary/10 rounded-lg border border-primary/20">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Composite Similarity Score</span>
              <span className="text-2xl font-bold text-gradient-primary">91%</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Weighted average based on factor relevance to current conflict type
            </p>
          </div>
        </div>

        {/* What Influenced Decision */}
        <div className="glass-panel p-4">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-success" />
            <h3 className="font-medium">Factors Considered</h3>
          </div>

          <ul className="space-y-2">
            {includedFactors.map((factor, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-success" />
                {factor}
              </li>
            ))}
          </ul>
        </div>

        {/* What Was Excluded */}
        <div className="glass-panel p-4">
          <div className="flex items-center gap-2 mb-4">
            <XCircle className="w-5 h-5 text-muted-foreground" />
            <h3 className="font-medium">Excluded Factors</h3>
          </div>

          <div className="space-y-3">
            {excludedFactors.map((item, i) => (
              <div key={i} className="p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <AlertTriangle className="w-4 h-4" />
                  {item.factor}
                </div>
                <p className="text-xs text-muted-foreground mt-1 ml-6">{item.reason}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Confidence Statement */}
        <div className="glass-panel p-4">
          <div className="flex items-center gap-2 mb-4">
            <Info className="w-5 h-5 text-accent" />
            <h3 className="font-medium">Confidence Statement</h3>
          </div>

          <div className="evidence-highlight">
            <p className="text-sm">
              The recommended resolution has been successfully applied in <strong className="text-primary">12 out of 14</strong> similar 
              historical cases (86% success rate). The two unsuccessful cases involved factors not present in the current situation 
              (emergency maintenance and signal failure).
            </p>
          </div>

          <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
            <span>Model confidence: <span className="text-primary font-medium">High</span></span>
            <span>•</span>
            <span>Data recency: <span className="text-success font-medium">Current</span></span>
            <span>•</span>
            <span>Safety verified: <span className="text-success font-medium">Yes</span></span>
          </div>
        </div>
      </div>
    </div>
  );
}
