import { Lightbulb } from 'lucide-react';
import { ResolutionCard } from './ResolutionCard';

const resolutionOptions = [
  {
    rank: 1,
    title: 'Reroute via Platform 3',
    description: 'Redirect TR-2847 to available platform 3, allowing TR-1923 to proceed on original schedule.',
    delayReduction: 8,
    riskLevel: 'low' as const,
    supportingCases: 12,
    safetyChecks: [
      { name: 'Clearance', passed: true },
      { name: 'Capacity', passed: true },
      { name: 'Signal', passed: true },
    ],
    isRecommended: true,
  },
  {
    rank: 2,
    title: 'Hold & Sequence',
    description: 'Hold TR-2847 at approach signal, sequence arrivals with 3-minute buffer.',
    delayReduction: 5,
    riskLevel: 'low' as const,
    supportingCases: 8,
    safetyChecks: [
      { name: 'Clearance', passed: true },
      { name: 'Capacity', passed: true },
      { name: 'Signal', passed: true },
    ],
  },
  {
    rank: 3,
    title: 'Express Override',
    description: 'Grant priority to TR-1923 (express), cascade delay to local services.',
    delayReduction: 10,
    riskLevel: 'medium' as const,
    supportingCases: 5,
    safetyChecks: [
      { name: 'Clearance', passed: true },
      { name: 'Capacity', passed: false },
      { name: 'Signal', passed: true },
    ],
  },
];

interface ResolutionPanelProps {
  onViewExplanation?: () => void;
}

export function ResolutionPanel({ onViewExplanation }: ResolutionPanelProps) {
  return (
    <div className="h-full flex flex-col w-full">
      {/* Header */}
      <div className="glass-panel p-6 mb-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-lg bg-accent/20 flex items-center justify-center">
            <Lightbulb className="w-8 h-8 text-accent" />
          </div>
          <div>
            <h2 className="font-semibold text-xl">Resolution Options</h2>
            <p className="text-base text-muted-foreground">AI-ranked by effectiveness</p>
          </div>
        </div>

        <div className="mt-6 p-5 bg-primary/10 border border-primary/20 rounded-lg">
          <div className="flex flex-col gap-2 text-base text-primary">
            <span className="font-medium text-lg">3 viable options identified</span>
            <span className="text-sm text-muted-foreground">
              Based on 25 similar historical cases
            </span>
          </div>
        </div>
      </div>

      {/* Resolution Cards */}
      <div className="flex-1 overflow-y-auto space-y-6">
        {resolutionOptions.map((option) => (
          <ResolutionCard 
            key={option.rank} 
            {...option} 
            onClick={() => onViewExplanation?.()} 
          />
        ))}
      </div>
    </div>
  );
}
