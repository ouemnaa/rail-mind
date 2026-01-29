import { useState } from "react";
import {
  Lightbulb,
  Play,
  Loader2,
  AlertCircle,
  RefreshCw,
  Clock,
  Zap,
  Brain,
  Scale,
} from "lucide-react";
import { ResolutionCard } from "./ResolutionCard";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

// API base URL - adjust based on environment
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8002";

interface OrchestratorOutput {
  status: string;
  conflict_id: string;
  started_at: string;
  finished_at: string;
  total_execution_ms: number;
  agents: {
    hybrid_rag: {
      status: string;
      execution_ms: number;
      raw_result: any;
      normalized_count: number;
    };
    mathematical: {
      status: string;
      execution_ms: number;
      raw_result: any;
      normalized_count: number;
    };
  };
  llm_judge: {
    status: string;
    execution_ms: number;
    ranked_resolutions: RankedResolution[] | null;
    error: string | null;
  };
}

interface RankedResolution {
  rank: number;
  resolution_id: string;
  resolution_number: number;
  overall_score: number;
  safety_rating: number;
  efficiency_rating: number;
  feasibility_rating: number;
  robustness_rating: number;
  justification: string;
  bullet_resolution_actions?: { actions: string[] };
  full_resolution?: {
    source_agent: string;
    strategy_name: string;
    actions: string[];
    expected_outcome: string;
    reasoning: string;
    safety_score: number;
    efficiency_score: number;
    feasibility_score: number;
    overall_fitness: number;
    estimated_delay_min: number;
    affected_trains: string[];
    side_effects: string[];
    algorithm_type: string;
  };
}

interface ApiResponse {
  success: boolean;
  filepath: string;
  filename: string;
  conflict_id: string;
  output: OrchestratorOutput;
}

// Sample conflict for demo/testing
const SAMPLE_CONFLICT = {
  conflict_id: "CONF-2026-0129-DEMO",
  conflict_type: "headway",
  station_ids: ["MILANO CENTRALE", "MILANO ROGOREDO"],
  train_ids: ["REG_2816", "FR_9703"],
  delay_values: { REG_2816: 2.5, FR_9703: 1.8 },
  timestamp: Date.now() / 1000,
  severity: 0.75,
  blocking_behavior: "soft",
};

// Fallback static options when API not available
const staticResolutionOptions = [
  {
    rank: 1,
    title: "Reroute via Platform 3",
    description:
      "Redirect TR-2847 to available platform 3, allowing TR-1923 to proceed on original schedule.",
    delayReduction: 8,
    riskLevel: "low" as const,
    supportingCases: 12,
    safetyChecks: [
      { name: "Clearance", passed: true },
      { name: "Capacity", passed: true },
      { name: "Signal", passed: true },
    ],
    isRecommended: true,
  },
  {
    rank: 2,
    title: "Hold & Sequence",
    description:
      "Hold TR-2847 at approach signal, sequence arrivals with 3-minute buffer.",
    delayReduction: 5,
    riskLevel: "low" as const,
    supportingCases: 8,
    safetyChecks: [
      { name: "Clearance", passed: true },
      { name: "Capacity", passed: true },
      { name: "Signal", passed: true },
    ],
  },
  {
    rank: 3,
    title: "Express Override",
    description:
      "Grant priority to TR-1923 (express), cascade delay to local services.",
    delayReduction: 10,
    riskLevel: "medium" as const,
    supportingCases: 5,
    safetyChecks: [
      { name: "Clearance", passed: true },
      { name: "Capacity", passed: false },
      { name: "Signal", passed: true },
    ],
  },
];

interface ResolutionPanelProps {
  onViewExplanation?: () => void;
  conflictId?: string;
  detection?: any;
}

export function ResolutionPanel({
  onViewExplanation,
  detection,
}: ResolutionPanelProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ApiResponse | null>(null);
  const [selectedConflict] = useState<any>(detection || SAMPLE_CONFLICT);

  // Convert orchestrator result to display format
  const getResolutionOptions = () => {
    if (!result?.output?.llm_judge?.ranked_resolutions) {
      return null; // Return null to show static fallback
    }

    return result.output.llm_judge.ranked_resolutions.map((r) => {
      const fullRes = r.full_resolution;
      const actions =
        r.bullet_resolution_actions?.actions || fullRes?.actions || [];

      // Determine risk level from scores
      const avgScore = (r.safety_rating + r.feasibility_rating) / 2;
      let riskLevel: "low" | "medium" | "high" = "low";
      if (avgScore < 5) riskLevel = "high";
      else if (avgScore < 7) riskLevel = "medium";

      return {
        rank: r.rank,
        title: fullRes?.strategy_name || r.resolution_id,
        description:
          r.justification || fullRes?.expected_outcome || "Resolution option",
        delayReduction: fullRes?.estimated_delay_min
          ? Math.round(fullRes.estimated_delay_min)
          : 5,
        riskLevel,
        supportingCases: Math.round(r.overall_score / 10),
        safetyChecks: [
          { name: "Safety", passed: r.safety_rating >= 6 },
          { name: "Feasibility", passed: r.feasibility_rating >= 6 },
          { name: "Efficiency", passed: r.efficiency_rating >= 6 },
        ],
        isRecommended: r.rank === 1,
        sourceAgent: fullRes?.source_agent || "Unknown",
        actions,
      };
    });
  };

  const handleResolve = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/conflicts/resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conflict: selectedConflict,
          timeout: 90,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
        );
      }

      const data: ApiResponse = await response.json();
      setResult(data);

      if (!data.success) {
        setError(
          `Resolution failed: ${data.output?.status || "Unknown error"}`,
        );
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unknown error occurred";
      setError(message);
      console.error("Resolution error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const dynamicOptions = getResolutionOptions();
  const resolutionOptions = dynamicOptions || staticResolutionOptions;
  const hasApiResults = dynamicOptions !== null;

  return (
    <div className="h-full flex flex-col w-full">
      {/* Header */}
      <div className="glass-panel p-6 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-lg bg-accent/20 flex items-center justify-center">
              <Lightbulb className="w-8 h-8 text-accent" />
            </div>
            <div>
              <h2 className="font-semibold text-xl">Resolution Options</h2>
              <p className="text-base text-muted-foreground">
                {hasApiResults
                  ? "AI-ranked by effectiveness"
                  : "Click Resolve to generate options"}
              </p>
            </div>
          </div>

          {/* Resolve Button */}
          <Button
            onClick={handleResolve}
            disabled={isLoading}
            size="lg"
            className="gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Resolving...
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                Resolve Conflict
              </>
            )}
          </Button>
        </div>

        {/* Conflict Info */}
        <div className="mt-4 p-4 bg-muted/30 rounded-lg">
          <div className="text-sm text-muted-foreground mb-1">
            Active Conflict
          </div>
          <div className="font-medium">{selectedConflict.conflict_id}</div>
          <div className="text-sm text-muted-foreground">
            {selectedConflict.conflict_type} at{" "}
            {selectedConflict.station_ids?.join(" → ")}
          </div>
          <div className="text-sm text-muted-foreground">
            Trains: {selectedConflict.train_ids?.join(", ")}
          </div>
        </div>

        {/* Results Summary (when API results available) */}
        {result && (
          <div className="mt-4 p-4 bg-primary/10 border border-primary/20 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-lg text-primary">
                {resolutionOptions.length} options identified
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResolve}
                disabled={isLoading}
              >
                <RefreshCw
                  className={`w-4 h-4 mr-1 ${isLoading ? "animate-spin" : ""}`}
                />
                Re-run
              </Button>
            </div>

            {/* Timing Stats */}
            <div className="grid grid-cols-4 gap-2 text-xs">
              <div className="flex items-center gap-1">
                <Clock className="w-3 h-3 text-muted-foreground" />
                <span>Total: {result.output.total_execution_ms}ms</span>
              </div>
              <div className="flex items-center gap-1">
                <Brain className="w-3 h-3 text-blue-500" />
                <span>
                  RAG: {result.output.agents.hybrid_rag.execution_ms}ms
                </span>
              </div>
              <div className="flex items-center gap-1">
                <Zap className="w-3 h-3 text-yellow-500" />
                <span>
                  Math: {result.output.agents.mathematical.execution_ms}ms
                </span>
              </div>
              <div className="flex items-center gap-1">
                <Scale className="w-3 h-3 text-purple-500" />
                <span>Judge: {result.output.llm_judge.execution_ms}ms</span>
              </div>
            </div>

            {/* Agent Status */}
            <div className="mt-2 flex gap-4 text-xs">
              <span
                className={
                  result.output.agents.hybrid_rag.status === "ok"
                    ? "text-green-500"
                    : "text-red-500"
                }
              >
                Hybrid RAG: {result.output.agents.hybrid_rag.status} (
                {result.output.agents.hybrid_rag.normalized_count} resolutions)
              </span>
              <span
                className={
                  result.output.agents.mathematical.status === "ok"
                    ? "text-green-500"
                    : "text-red-500"
                }
              >
                Mathematical: {result.output.agents.mathematical.status} (
                {result.output.agents.mathematical.normalized_count}{" "}
                resolutions)
              </span>
            </div>
          </div>
        )}

        {/* Fallback info when no API results */}
        {!result && (
          <div className="mt-6 p-5 bg-primary/10 border border-primary/20 rounded-lg">
            <div className="flex flex-col gap-2 text-base text-primary">
              <span className="font-medium text-lg">
                {resolutionOptions.length} sample options shown
              </span>
              <span className="text-sm text-muted-foreground">
                Click "Resolve Conflict" to get AI-generated resolutions
              </span>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <Alert variant="destructive" className="mt-4">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Resolution Error</AlertTitle>
            <AlertDescription className="text-sm">
              {error}
              {result?.output?.llm_judge?.error && (
                <div className="mt-1 text-xs opacity-75">
                  Judge error: {result.output.llm_judge.error}
                </div>
              )}
            </AlertDescription>
          </Alert>
        )}
      </div>

      {/* Resolution Cards */}
      <div className="flex-1 overflow-y-auto space-y-6">
        {resolutionOptions.map((option) => (
          <div key={option.rank}>
            <ResolutionCard
              rank={option.rank}
              title={option.title}
              description={option.description}
              delayReduction={option.delayReduction}
              riskLevel={option.riskLevel}
              supportingCases={option.supportingCases}
              safetyChecks={option.safetyChecks}
              isRecommended={option.isRecommended}
              onClick={() => onViewExplanation?.()}
            />
            {/* Source Agent Badge (only for API results) */}
            {hasApiResults && "sourceAgent" in option && (
              <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                <span
                  className={`px-2 py-0.5 rounded-full ${
                    (option as any).sourceAgent?.includes("Hybrid")
                      ? "bg-blue-500/20 text-blue-400"
                      : "bg-yellow-500/20 text-yellow-400"
                  }`}
                >
                  {(option as any).sourceAgent}
                </span>
                {(option as any).actions?.length > 0 && (
                  <span>• {(option as any).actions.length} action steps</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
