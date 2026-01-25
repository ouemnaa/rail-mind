import { Clock, MapPin, Zap, ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Minus } from 'lucide-react';
import { useState } from 'react';

interface MemoryCardProps {
  id: string;
  similarity: number;
  date: string;
  location: string;
  incidentType: string;
  outcome: 'success' | 'neutral' | 'warning';
  summary: string;
  actionsTaken: string[];
  contextDrift?: string;
}

export function MemoryCard({
  id,
  similarity,
  date,
  location,
  incidentType,
  outcome,
  summary,
  actionsTaken,
  contextDrift,
}: MemoryCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getOutcomeBadge = () => {
    switch (outcome) {
      case 'success':
        return (
          <span className="status-badge outcome-badge-success">
            <CheckCircle2 className="w-3 h-3" />
            Successful
          </span>
        );
      case 'warning':
        return (
          <span className="status-badge outcome-badge-warning">
            <AlertCircle className="w-3 h-3" />
            Issues
          </span>
        );
      default:
        return (
          <span className="status-badge outcome-badge-neutral">
            <Minus className="w-3 h-3" />
            Neutral
          </span>
        );
    }
  };

  return (
    <div className="memory-card group">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <span className="text-xs font-mono text-muted-foreground">Case #{id}</span>
          {getOutcomeBadge()}
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gradient-primary">{similarity}%</div>
          <div className="text-xs text-muted-foreground">similarity</div>
        </div>
      </div>

      {/* Similarity Bar */}
      <div className="mb-4">
        <div className="similarity-bar">
          <div className="similarity-fill" style={{ width: `${similarity}%` }} />
        </div>
      </div>

      {/* Matching Factors */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Clock className="w-3.5 h-3.5 text-primary" />
          <span>{date}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <MapPin className="w-3.5 h-3.5 text-primary" />
          <span>{location}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Zap className="w-3.5 h-3.5 text-primary" />
          <span>{incidentType}</span>
        </div>
      </div>

      {/* Summary */}
      <p className="text-sm text-muted-foreground mb-4">{summary}</p>

      {/* Expandable Details */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-xs text-primary hover:text-primary/80 transition-colors"
      >
        {isExpanded ? (
          <>
            <ChevronUp className="w-4 h-4" />
            Hide details
          </>
        ) : (
          <>
            <ChevronDown className="w-4 h-4" />
            View actions & context
          </>
        )}
      </button>

      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-border space-y-4 animate-fade-in">
          {/* Actions Taken */}
          <div>
            <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Actions Taken</h4>
            <ul className="space-y-1">
              {actionsTaken.map((action, i) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <span className="text-primary mt-1">•</span>
                  {action}
                </li>
              ))}
            </ul>
          </div>

          {/* Context Drift */}
          {contextDrift && (
            <div className="evidence-highlight">
              <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
                Context Differences
              </h4>
              <p className="text-sm">{contextDrift}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
