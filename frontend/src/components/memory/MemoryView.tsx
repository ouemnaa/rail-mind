import { Brain, Search, Database } from 'lucide-react';
import { MemoryCard } from './MemoryCard';

const pastCases = [
  {
    id: 'MEM-7823',
    similarity: 94,
    date: '2024-12-15',
    location: 'West Gateway',
    incidentType: 'Platform Conflict',
    outcome: 'success' as const,
    summary: 'Similar platform conflict resolved by rerouting TR-1892 through alternate track. Minimal delay impact.',
    actionsTaken: [
      'Rerouted incoming train to platform 3',
      'Delayed departure by 4 minutes',
      'Notified passengers via PA system',
    ],
    contextDrift: 'Current situation has higher passenger volume (+23%)',
  },
  {
    id: 'MEM-6541',
    similarity: 87,
    date: '2024-11-28',
    location: 'Central Hub',
    incidentType: 'Platform Conflict',
    outcome: 'success' as const,
    summary: 'Platform conflict at peak hours. Successfully resolved using dynamic scheduling.',
    actionsTaken: [
      'Activated emergency scheduling protocol',
      'Coordinated with signal control',
      'Express train held for 6 minutes',
    ],
  },
  {
    id: 'MEM-5219',
    similarity: 72,
    date: '2024-10-03',
    location: 'East Junction',
    incidentType: 'Headway Violation',
    outcome: 'neutral' as const,
    summary: 'Headway violation caused cascading delays. Resolution took longer than optimal.',
    actionsTaken: [
      'Reduced line speed temporarily',
      'Inserted additional buffer time',
      'Manual override of automated signals',
    ],
    contextDrift: 'Different conflict type but similar network conditions',
  },
];

export function MemoryView() {
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="glass-panel p-4 mb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
              <Brain className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold">Memory Retrieval</h2>
              <p className="text-sm text-muted-foreground">Similar past situations</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Database className="w-4 h-4" />
            <span>1,247 cases indexed</span>
          </div>
        </div>

        {/* Search Stats */}
        <div className="mt-4 flex items-center gap-4 p-3 bg-muted/50 rounded-lg">
          <Search className="w-4 h-4 text-primary" />
          <div className="flex-1">
            <div className="text-sm">Vector similarity search completed</div>
            <div className="text-xs text-muted-foreground">3 relevant cases retrieved in 124ms</div>
          </div>
          <div className="text-xs font-mono text-primary">cosine_similarity ≥ 0.70</div>
        </div>
      </div>

      {/* Memory Cards */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {pastCases.map((case_) => (
          <MemoryCard key={case_.id} {...case_} />
        ))}
      </div>
    </div>
  );
}
