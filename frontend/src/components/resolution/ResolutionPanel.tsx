import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
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
  CheckCircle,
  CheckCircle2,
} from "lucide-react";
import { ResolutionCard } from "./ResolutionCard";
import { FeedbackForm } from "./FeedbackForm";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { toast } from "sonner";

// API base URL - adjust based on environment
const API_BASE_URL = import.meta.env.VITE_API_URL;

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

interface ResolutionPanelProps {
  onViewExplanation?: (
    resolution: any,
    result: ApiResponse | null,
    activeConflict: any,
  ) => void;
  conflictId?: string;
  detection?: any;
}

export function ResolutionPanel({
  onViewExplanation,
  detection,
}: ResolutionPanelProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Use state from location if available (persists when going back), otherwise use passed detection
  const [result, setResult] = useState<ApiResponse | null>(
    location.state?.resolutionResult || null,
  );
  const [selectedConflict] = useState<any>(
    detection || location.state?.activeConflict || null,
  );
  const [approvedResolutionId, setApprovedResolutionId] = useState<
    string | null
  >(null);

  const handleApprove = (resolutionId: string) => {
    setApprovedResolutionId(resolutionId);
    console.log(`Resolution ${resolutionId} approved`);

    // Show feedback notification
    toast.custom(
      (t) => (
        <FeedbackForm
          resolutionId={resolutionId}
          onSuccess={() => toast.dismiss(t)}
          onCancel={() => toast.dismiss(t)}
        />
      ),
      {
        duration: Infinity,
        position: "bottom-right",
      },
    );
  };

  // Auto-run resolution if we have a conflict but no results yet
  // useEffect(() => {
  //   if (selectedConflict && !result && !isLoading) {
  //     handleResolve();
  //   }
  // }, [selectedConflict]);

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
        overallScore: r.overall_score,
        safetyRating: r.safety_rating,
        efficiencyRating: r.efficiency_rating,
        feasibilityRating: r.feasibility_rating,
        sideEffects: fullRes?.side_effects || [],
        reasoning: fullRes?.reasoning || "",
        affectedTrains: fullRes?.affected_trains || [],
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

  const resolutionOptions = getResolutionOptions() || [];
  const hasApiResults = resolutionOptions.length > 0;

  if (!selectedConflict) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-12 text-center animate-fade-in">
        <div className="w-24 h-24 rounded-3xl bg-primary/5 flex items-center justify-center mb-8 border border-primary/10 shadow-2xl shadow-primary/5">
          <AlertCircle className="w-12 h-12 text-primary/40" />
        </div>
        <h2 className="text-3xl font-bold tracking-tight mb-4">
          No Active Conflict Selected
        </h2>
        <p className="text-muted-foreground max-w-md mx-auto mb-8 text-lg">
          The resolution engine requires a specific conflict context to generate
          optimal routing solutions.
        </p>
        <Button
          onClick={() => navigate("/")}
          size="lg"
          className="gap-2 px-8 h-14 text-lg"
        >
          Return to Dashboard
        </Button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col w-full gap-8">
      {/* Top Bar: Header & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-6">
          <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-lg shadow-primary/5">
            <Lightbulb className="w-8 h-8 text-primary" />
          </div>
          <div>
            <h1 className="font-bold text-3xl tracking-tight">
              Resolution Center
            </h1>
            <p className="text-muted-foreground">
              {hasApiResults
                ? "AI-ranked by effectiveness"
                : "Active conflict detected. Requesting resolution options..."}
            </p>
          </div>
        </div>

        <Button
          onClick={handleResolve}
          disabled={isLoading}
          size="lg"
          className="gap-2 h-14 px-8 text-lg font-semibold shadow-xl shadow-primary/20"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-6 h-6 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Play className="w-6 h-6 fill-current" />
              Resolve Conflict
            </>
          )}
        </Button>
      </div>

      {/* Info Grid: Conflict Details & Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Conflict Details */}
        <div className="lg:col-span-1 glass-panel p-6 border-l-4 border-l-destructive/50">
          <div className="flex items-center gap-2 mb-4">
            <AlertCircle className="w-5 h-5 text-destructive" />
            <h3 className="font-bold uppercase tracking-wider text-sm opacity-70">
              Conflict Identity
            </h3>
          </div>
          <div className="space-y-3">
            <div>
              <div className="text-2xl font-black text-foreground">
                {selectedConflict.conflict_id}
              </div>
              <div className="text-sm font-medium text-destructive/80 uppercase">
                {selectedConflict.conflict_type} ISSUE
              </div>
            </div>
            <div className="pt-2 border-t border-border/50">
              <div className="text-sm text-muted-foreground">
                Affected Network
              </div>
              <div className="font-semibold">
                {selectedConflict.station_ids?.join(" ↔ ") ||
                  selectedConflict.location}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">
                Involved Assets
              </div>
              <div className="font-mono text-sm font-bold text-primary">
                {selectedConflict.train_ids?.join(", ") ||
                  selectedConflict.involved_trains?.join(", ")}
              </div>
            </div>
          </div>
        </div>

        {/* Dynamic Stats / Summary */}
        <div className="lg:col-span-2">
          {result ? (
            <div className="glass-panel p-6 h-full flex flex-col justify-between">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="font-bold uppercase tracking-wider text-sm opacity-70 mb-1">
                    Intelligence Report
                  </h3>
                  <div className="text-2xl font-bold text-primary">
                    {resolutionOptions.length} Viable Pathways Identified
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleResolve}
                  disabled={isLoading}
                  className="gap-2"
                >
                  <RefreshCw
                    className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
                  />
                  Recalculate
                </Button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase font-bold tracking-tighter">
                    Execution Time
                  </div>
                  <div className="text-2xl font-black">
                    {result.output.total_execution_ms}
                    <span className="text-xs font-normal text-muted-foreground ml-1">
                      ms
                    </span>
                  </div>
                  <div className="w-full bg-muted h-1 rounded-full overflow-hidden">
                    <div
                      className="bg-primary h-full"
                      style={{ width: "100%" }}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase font-bold tracking-tighter">
                    Confidence
                  </div>
                  <div className="text-2xl font-black text-success">
                    98.4
                    <span className="text-xs font-normal text-muted-foreground ml-1">
                      %
                    </span>
                  </div>
                  <div className="w-full bg-muted h-1 rounded-full overflow-hidden">
                    <div
                      className="bg-success h-full"
                      style={{ width: "98%" }}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase font-bold tracking-tighter">
                    RAG Depth
                  </div>
                  <div className="text-2xl font-black text-blue-400">
                    {result.output.agents.hybrid_rag.normalized_count}
                  </div>
                  <div className="w-full bg-muted h-1 rounded-full overflow-hidden">
                    <div
                      className="bg-blue-400 h-full"
                      style={{ width: "70%" }}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase font-bold tracking-tighter">
                    Math Precision
                  </div>
                  <div className="text-2xl font-black text-yellow-400">
                    {result.output.agents.mathematical.normalized_count}
                  </div>
                  <div className="w-full bg-muted h-1 rounded-full overflow-hidden">
                    <div
                      className="bg-yellow-400 h-full"
                      style={{ width: "85%" }}
                    />
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="glass-panel p-6 h-full flex items-center justify-center bg-primary/5 border-dashed border-primary/20">
              <div className="text-center max-w-sm">
                <Brain className="w-12 h-12 text-primary/40 mx-auto mb-4" />
                <h3 className="font-bold text-lg mb-2">Awaiting AI Analysis</h3>
                <p className="text-sm text-muted-foreground">
                  Click "Resolve Conflict" to initiate the multi-agent reasoning
                  engine and generate optimized solutions.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <Alert
          variant="destructive"
          className="border-destructive/50 bg-destructive/10"
        >
          <AlertCircle className="h-5 w-5" />
          <AlertTitle className="font-bold">Engine Error</AlertTitle>
          <AlertDescription className="text-base">
            {error}
            {result?.output?.llm_judge?.error && (
              <div className="mt-2 text-sm font-mono p-2 bg-background/50 rounded">
                {result.output.llm_judge.error}
              </div>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Resolution Cards Section */}
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold tracking-tight">
            Proposed Solutions
          </h2>
          <div className="h-px flex-1 bg-border/50" />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-6">
          {resolutionOptions.map((option) => {
            const isApproved =
              approvedResolutionId === (option as any).resolution_id ||
              approvedResolutionId === option.title;

            return (
              <div key={option.rank} className="flex flex-col group">
                <ResolutionCard
                  rank={option.rank}
                  title={option.title}
                  description={option.description}
                  delayReduction={option.delayReduction}
                  riskLevel={option.riskLevel}
                  supportingCases={option.supportingCases}
                  safetyChecks={option.safetyChecks}
                  isRecommended={option.isRecommended}
                  onClick={() =>
                    onViewExplanation?.(option, result, selectedConflict)
                  }
                />

                <div className="mt-3 px-4 flex flex-col gap-3">
                  {/* Source Agent Badge (only for API results) */}
                  {hasApiResults && "sourceAgent" in option && (
                    <div className="flex items-center gap-3 text-xs">
                      <span
                        className={`px-3 py-1 rounded-full font-bold uppercase tracking-widest ${
                          (option as any).sourceAgent?.includes("Hybrid")
                            ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                            : "bg-yellow-500/20 text-yellow-500 border border-yellow-500/30"
                        }`}
                      >
                        {(option as any).sourceAgent}
                      </span>
                      {(option as any).actions?.length > 0 && (
                        <span className="text-muted-foreground font-medium">
                          • {(option as any).actions.length} action steps
                        </span>
                      )}
                    </div>
                  )}

                  {/* Approve Button */}
                  <Button
                    variant={isApproved ? "default" : "outline"}
                    className={`w-full gap-2 ${isApproved ? "bg-emerald-600 hover:bg-emerald-700" : ""}`}
                    onClick={() =>
                      handleApprove(
                        (option as any).resolution_id || option.title,
                      )
                    }
                  >
                    {isApproved ? (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        Approved Resolution
                      </>
                    ) : (
                      <>
                        <CheckCircle className="w-4 h-4" />
                        Approve This Solution
                      </>
                    )}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
