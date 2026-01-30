/**
 * Simulation Page
 * ===============
 * 
 * Full simulation workflow:
 * 1. Detect conflict and save to backend
 * 2. Show conflict and resolution options
 * 3. User selects resolution
 * 4. Run A/B comparison simulation
 * 5. Apply resolution, remove from active state
 * 6. Show success notification
 * 7. Archive to Qdrant
 * 8. Continue simulation
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    Play,
    Pause,
    RotateCcw,
    AlertTriangle,
    CheckCircle,
    Zap,
    Split,
    ArrowRight,
} from 'lucide-react';
import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ABComparisonView } from '@/components/simulation/ABComparisonView';
import { ResolutionCard } from '@/components/resolution/ResolutionCard';
import { LombardyNetworkMap } from '@/components/dashboard/LombardyNetworkMap';
import { ConflictResolutionSuccess } from '@/components/simulation/ConflictResolutionSuccess';
import { useUnifiedSimulation } from '@/hooks/useUnifiedSimulation';
import { useConflictWorkflow } from '@/hooks/useConflictWorkflow';
import type { AppliedResolution, SimulationTrain, ResolutionAction } from '@/types/simulation';
import type { BatchPrediction, ConflictPrediction } from '@/types/prediction';
import type { ResolutionSuccessData } from '@/components/simulation/ConflictResolutionSuccess';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002';

type SimulationPhase =
    | 'running'           // Normal simulation running
    | 'conflict-detected' // Conflict detected, showing resolutions
    | 'selecting'         // User selecting resolution
    | 'comparing'         // Running A/B comparison
    | 'applying'          // Applying chosen resolution
    | 'resolved';         // Resolution applied, continuing

interface DetectedConflict {
    conflict_id: string;
    conflict_type: string;
    severity: string;
    location: string;
    involved_trains: string[];
    timestamp: string;
    probability: number;
    resolutions: any[];
}

const Simulation = () => {
    const navigate = useNavigate();
    const location = useLocation();

    // Simulation state
    const [phase, setPhase] = useState<SimulationPhase>('running');
    const [activeConflict, setActiveConflict] = useState<DetectedConflict | null>(null);
    const [resolutionOptions, setResolutionOptions] = useState<any[]>([]);
    const [selectedResolution, setSelectedResolution] = useState<AppliedResolution | null>(null);
    const [isLoadingResolutions, setIsLoadingResolutions] = useState(false);
    const [resolvedConflicts, setResolvedConflicts] = useState<string[]>([]);
    
    // Success notification state
    const [successNotification, setSuccessNotification] = useState<ResolutionSuccessData | null>(null);
    const [resolutionStartTime, setResolutionStartTime] = useState<number>(0);

    // Use the unified simulation hook
    const {
        state,
        trains,
        predictions,
        detections,
        isRunning,
        start,
        stop,
        tick,
        reset,
    } = useUnifiedSimulation({ autoStart: true, tickInterval: 2000 });

    // Use conflict workflow hook
    const {
        workflow,
        saveDetectedConflict,
        removeFromActive,
        markResolved,
        archiveResolvedConflict,
        getConflictStats,
    } = useConflictWorkflow();

    // Convert trains to simulation format
    const simulationTrains: SimulationTrain[] = useMemo(() => {
        return trains.map(train => ({
            train_id: train.train_id,
            train_type: train.train_type,
            current_station: train.current_station,
            next_station: train.next_station,
            position_km: train.position_km,
            speed_kmh: train.speed_kmh,
            delay_sec: train.delay_sec,
            status: train.status as any,
            lat: train.lat,
            lon: train.lon,
            resolution_status: 'original',
        }));
    }, [trains]);

    // Convert to batch prediction for map
    const batchPrediction: BatchPrediction | null = useMemo(() => {
        if (!state) return null;

        const allConflicts = [...predictions, ...detections];
        const avgProbability = predictions.length > 0
            ? predictions.reduce((sum, p) => sum + p.probability, 0) / predictions.length
            : 0;

        const convertedPredictions: ConflictPrediction[] = allConflicts.map(conflict => ({
            train_id: conflict.involved_trains[0] || 'unknown',
            probability: conflict.probability,
            risk_level: conflict.source === 'detection' ? 'critical' :
                conflict.probability >= 0.6 ? 'high_risk' :
                    conflict.probability >= 0.3 ? 'low_risk' : 'safe',
            color: conflict.source === 'detection' ? '#dc2626' :
                conflict.probability >= 0.6 ? '#f97316' : '#f59e0b',
            emoji: conflict.source === 'detection' ? '🔴' : '🟠',
            predicted_conflict_type: conflict.conflict_type as any,
            predicted_time: conflict.timestamp,
            predicted_location: conflict.location,
            contributing_factors: [conflict.explanation],
            confidence: conflict.probability,
            model_used: 'xgboost_ensemble',
        }));

        return {
            timestamp: state.simulation_time,
            predictions: convertedPredictions,
            network_risk_score: avgProbability,
            high_risk_trains: predictions.filter(p => p.probability >= 0.6).flatMap(p => p.involved_trains),
            critical_trains: detections.flatMap(d => d.involved_trains),
            recommended_actions: [],
            model_used: 'xgboost_ensemble',
            strategy: 'continuous',
        };
    }, [state, predictions, detections]);

    // Watch for new detections (real conflicts) - STEP 1: Save detected conflict
    useEffect(() => {
        if (phase === 'running' && detections.length > 0) {
            // Find a detection we haven't resolved yet
            const newConflict = detections.find(d => !resolvedConflicts.includes(d.conflict_id));

            if (newConflict) {
                stop(); // Pause simulation
                
                // STEP 1: Save the detected conflict to backend
                saveDetectedConflict({
                    conflict_id: newConflict.conflict_id,
                    conflict_type: newConflict.conflict_type,
                    location: newConflict.location,
                    involved_trains: newConflict.involved_trains,
                }).then(result => {
                    if (result.success) {
                        console.log(`✅ Conflict ${newConflict.conflict_id} saved to backend`);
                    }
                });

                setResolutionStartTime(Date.now());
                
                setActiveConflict({
                    conflict_id: newConflict.conflict_id,
                    conflict_type: newConflict.conflict_type,
                    severity: newConflict.severity,
                    location: newConflict.location,
                    involved_trains: newConflict.involved_trains,
                    timestamp: newConflict.timestamp,
                    probability: newConflict.probability,
                    resolutions: [],
                });
                setPhase('conflict-detected');
            }
        }
    }, [detections, phase, resolvedConflicts, stop, saveDetectedConflict]);

    // Fetch resolution options when conflict is detected
    const fetchResolutions = useCallback(async () => {
        if (!activeConflict) return;

        setIsLoadingResolutions(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/conflicts/resolve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conflict: {
                        conflict_id: activeConflict.conflict_id,
                        conflict_type: activeConflict.conflict_type,
                        station_ids: activeConflict.location.split(' - '),
                        train_ids: activeConflict.involved_trains,
                        severity: activeConflict.severity === 'critical' ? 1 : 0.7,
                    },
                    timeout: 90,
                }),
            });


            if (response.ok) {
                const data = await response.json();
                if (data.output?.llm_judge?.ranked_resolutions) {
                    setResolutionOptions(data.output.llm_judge.ranked_resolutions);
                }
            }
        } catch (error) {
            console.error('Failed to fetch resolutions:', error);
            // Use fallback resolutions
            setResolutionOptions(getFallbackResolutions(activeConflict));
        } finally {
            setIsLoadingResolutions(false);
            setPhase('selecting');
        }
    }, [activeConflict]);

    // Generate fallback resolutions if API fails
    const getFallbackResolutions = (conflict: DetectedConflict) => [
        {
            rank: 1,
            resolution_id: 'res_speed_reduction',
            overall_score: 85,
            safety_rating: 9,
            efficiency_rating: 7,
            feasibility_rating: 8,
            justification: 'Reduce speed of trailing train to increase headway',
            full_resolution: {
                strategy_name: 'Speed Reduction Protocol',
                source_agent: 'Hybrid RAG',
                actions: ['Reduce trailing train speed by 20%', 'Monitor headway distance'],
                affected_trains: conflict.involved_trains,
                estimated_delay_min: 3,
            },
        },
        {
            rank: 2,
            resolution_id: 'res_hold_train',
            overall_score: 78,
            safety_rating: 10,
            efficiency_rating: 6,
            feasibility_rating: 7,
            justification: 'Hold trailing train at station until path is clear',
            full_resolution: {
                strategy_name: 'Station Hold Strategy',
                source_agent: 'Mathematical Solver',
                actions: ['Hold train at current station', 'Resume after 2 minutes'],
                affected_trains: conflict.involved_trains,
                estimated_delay_min: 5,
            },
        },
        {
            rank: 3,
            resolution_id: 'res_priority_pass',
            overall_score: 72,
            safety_rating: 8,
            efficiency_rating: 8,
            feasibility_rating: 6,
            justification: 'Give priority to delayed train, hold others',
            full_resolution: {
                strategy_name: 'Priority Routing',
                source_agent: 'Hybrid RAG',
                actions: ['Prioritize most delayed train', 'Clear path ahead'],
                affected_trains: conflict.involved_trains,
                estimated_delay_min: 4,
            },
        },
    ];

    // Handle resolution selection
    const handleSelectResolution = (resolution: any) => {
        // Convert to AppliedResolution format
        const applied: AppliedResolution = {
            resolution_id: resolution.resolution_id,
            strategy_name: resolution.full_resolution?.strategy_name || 'Unknown Strategy',
            applied_at: new Date().toISOString(),
            affected_trains: resolution.full_resolution?.affected_trains || activeConflict?.involved_trains || [],
            actions: (resolution.full_resolution?.actions || []).map((action: string, i: number): ResolutionAction => ({
                type: i === 0 ? 'speed_reduction' : 'hold_train',
                train_id: activeConflict?.involved_trains[i] || 'unknown',
                description: action,
                parameters: {},
            })),
        };

        setSelectedResolution(applied);
        setPhase('comparing');
    };

    // Handle back from comparison
    const handleBackFromComparison = () => {
        setSelectedResolution(null);
        setPhase('selecting');
    };

    // Handle apply resolution

    // Complete workflow: remove from active, mark resolved, archive, show notification, resume
    const handleApplyResolution = async (resolutionId: string, comparisonResults?: any, finalKpis?: any) => {
        if (!activeConflict || !selectedResolution) return;

        // Remove from active and mark as resolved
        removeFromActive(activeConflict.conflict_id);
        markResolved(activeConflict.conflict_id, resolutionId, selectedResolution.strategy_name);

        setResolvedConflicts(prev => [...prev, activeConflict.conflict_id]);
        setPhase('resolved');

        // Archive to Qdrant (with comparison results and KPIs)
        const archiveResult = await archiveResolvedConflict(
            activeConflict.conflict_id,
            resolutionId,
            selectedResolution.strategy_name,
            comparisonResults || {},
            finalKpis || {}
        );

        // Show success notification
        const timeToResolve = (Date.now() - resolutionStartTime) / 1000;
        setSuccessNotification({
            conflict_id: activeConflict.conflict_id,
            conflict_type: activeConflict.conflict_type,
            location: activeConflict.location,
            resolution_strategy: selectedResolution.strategy_name,
            delay_reduction_percent: comparisonResults?.delay_reduction_percent || 0,
            efficiency_gain_percent: comparisonResults?.efficiency_gain_percent || 0,
            confidence_score: comparisonResults?.confidence_score || 0,
            time_to_resolve_sec: timeToResolve,
        });

        // Resume simulation after a brief pause
        setTimeout(() => {
            setActiveConflict(null);
            setSelectedResolution(null);
            setResolutionOptions([]);
            setPhase('running');
            start();
        }, 2000);
    };

    // Store outcome for learning
    const handleStoreOutcome = async (outcome: any) => {
        try {
            // Store to Qdrant for future learning
            const response = await fetch(`${API_BASE_URL}/api/outcomes/store`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(outcome),
            });

            if (response.ok) {
                console.log('✅ Outcome stored for learning:', outcome);
            } else {
                console.warn('⚠️ Outcome storage failed:', response.status);
            }
        } catch (error) {
            console.warn('⚠️ Outcome storage unavailable (backend may not be running):', error);
            // Continue anyway - this is non-critical
        }
    };

    // Render based on phase
    const renderContent = () => {
        // A/B Comparison View
        if (phase === 'comparing' && selectedResolution && activeConflict) {
            return (
                <ABComparisonView
                    conflictId={activeConflict.conflict_id}
                    conflictType={activeConflict.conflict_type}
                    location={activeConflict.location}
                    involvedTrains={activeConflict.involved_trains}
                    resolution={selectedResolution}
                    initialTrains={simulationTrains}
                    onBack={handleBackFromComparison}
                    // Pass comparisonResults and finalKpis to handler
                    onApplyResolution={(resolutionId, comparisonResults, finalKpis) =>
                        handleApplyResolution(resolutionId, comparisonResults, finalKpis)
                    }
                    onStoreOutcome={handleStoreOutcome}
                />
            );
        }

        // Resolution Selection View
        if ((phase === 'conflict-detected' || phase === 'selecting') && activeConflict) {
            return (
                <div className="space-y-6">
                    {/* Conflict Alert */}
                    <Card className="border-red-500/30 bg-red-500/5">
                        <CardContent className="p-6">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center animate-pulse">
                                    <AlertTriangle className="w-6 h-6 text-red-400" />
                                </div>
                                <div className="flex-1">
                                    <h2 className="text-xl font-bold text-red-400">
                                        Conflict Detected!
                                    </h2>
                                    <p className="text-muted-foreground">
                                        {activeConflict.conflict_type.toUpperCase()} at {activeConflict.location}
                                    </p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Badge variant="destructive">{activeConflict.severity}</Badge>
                                    <Badge variant="outline">
                                        {activeConflict.involved_trains.length} trains
                                    </Badge>
                                </div>
                            </div>

                            <div className="mt-4 flex items-center gap-4">
                                <span className="text-sm text-muted-foreground">Involved Trains:</span>
                                {activeConflict.involved_trains.map(trainId => (
                                    <Badge key={trainId} variant="secondary" className="font-mono">
                                        🚂 {trainId}
                                    </Badge>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Resolution Options */}
                    {isLoadingResolutions ? (
                        <Card className="glass-panel">
                            <CardContent className="p-12 text-center">
                                <div className="animate-spin w-12 h-12 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4" />
                                <h3 className="text-lg font-bold">Generating Resolutions...</h3>
                                <p className="text-muted-foreground">
                                    AI agents are analyzing the conflict and generating optimal solutions
                                </p>
                            </CardContent>
                        </Card>
                    ) : resolutionOptions.length === 0 ? (
                        <div className="text-center py-8">
                            <Button onClick={fetchResolutions} size="lg" className="gap-2">
                                <Zap className="w-5 h-5" />
                                Generate Resolution Options
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <CheckCircle className="w-5 h-5 text-primary" />
                                Select a Resolution to Compare
                            </h3>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {resolutionOptions.map((option) => (
                                    <div key={option.rank} className="flex flex-col">
                                        <ResolutionCard
                                            rank={option.rank}
                                            title={option.full_resolution?.strategy_name || `Resolution ${option.rank}`}
                                            description={option.justification}
                                            delayReduction={option.full_resolution?.estimated_delay_min || 5}
                                            riskLevel={option.safety_rating >= 8 ? 'low' : option.safety_rating >= 6 ? 'medium' : 'high'}
                                            supportingCases={Math.round(option.overall_score / 10)}
                                            safetyChecks={[
                                                { name: 'Safety', passed: option.safety_rating >= 7 },
                                                { name: 'Feasibility', passed: option.feasibility_rating >= 6 },
                                            ]}
                                            isRecommended={option.rank === 1}
                                            onClick={() => handleSelectResolution(option)}
                                        />

                                        <Button
                                            onClick={() => handleSelectResolution(option)}
                                            className="mt-3 gap-2"
                                            variant={option.rank === 1 ? 'default' : 'outline'}
                                        >
                                            <Split className="w-4 h-4" />
                                            Compare A/B
                                            <ArrowRight className="w-4 h-4" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        // Normal Running View
        return (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
                {/* Network Map */}
                <div className="lg:col-span-2 flex flex-col">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold">Live Network Simulation</h2>
                        <div className="flex items-center gap-2">
                            <Badge variant={isRunning ? 'default' : 'secondary'}>
                                {isRunning ? '● Running' : '○ Paused'}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                                Tick: {state?.tick_number || 0}
                            </span>
                        </div>
                    </div>

                    <div className="flex-1 min-h-[500px]">
                        <LombardyNetworkMap predictions={batchPrediction} />
                    </div>
                </div>

                {/* Status Panel */}
                <div className="space-y-4">
                    <Card className="glass-panel">
                        <CardHeader>
                            <CardTitle className="text-sm">Simulation Status</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground">Trains</span>
                                <span className="font-bold">{trains.length}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground">Predictions</span>
                                <Badge variant="outline" className="text-orange-400">
                                    {predictions.length}
                                </Badge>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground">Detections</span>
                                <Badge variant={detections.length > 0 ? 'destructive' : 'outline'}>
                                    {detections.length}
                                </Badge>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground">Resolved</span>
                                <Badge className="bg-emerald-500/20 text-emerald-400">
                                    {resolvedConflicts.length}
                                </Badge>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Recent Alerts */}
                    <Card className="glass-panel">
                        <CardHeader>
                            <CardTitle className="text-sm">Recent Alerts</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {[...predictions, ...detections].slice(0, 5).map((alert, i) => (
                                <div
                                    key={alert.conflict_id}
                                    className={`p-2 rounded mb-2 ${alert.source === 'detection'
                                            ? 'bg-red-500/10 border border-red-500/20'
                                            : 'bg-orange-500/10 border border-orange-500/20'
                                        }`}
                                >
                                    <div className="flex items-center justify-between">
                                        <span className={`text-sm font-medium ${alert.source === 'detection' ? 'text-red-400' : 'text-orange-400'
                                            }`}>
                                            {alert.conflict_type}
                                        </span>
                                        <Badge variant="outline" className="text-xs">
                                            {alert.source}
                                        </Badge>
                                    </div>
                                    <div className="text-xs text-muted-foreground mt-1">
                                        {alert.location}
                                    </div>
                                </div>
                            ))}

                            {predictions.length === 0 && detections.length === 0 && (
                                <div className="text-center text-muted-foreground py-4">
                                    No active alerts
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
            </div>
        );
    };

    return (
        <div className="h-screen flex overflow-hidden bg-background">
            <Sidebar />

            <div className="flex-1 flex flex-col overflow-hidden">
                <Header />

                <main className="flex-1 overflow-auto p-6">
                    {renderContent()}
                    {/* Success notification */}
                    {successNotification && (
                        <ConflictResolutionSuccess
                            data={successNotification}
                            onClose={() => setSuccessNotification(null)}
                        />
                    )}
                </main>

                {/* Simulation Controls - only show when not comparing */}
                {phase !== 'comparing' && (
                    <div className="border-t border-slate-700 bg-slate-900/50 px-4 py-2 text-xs text-slate-400 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2 border-r border-slate-700 pr-4">
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={isRunning ? stop : start}
                                    disabled={phase !== 'running'}
                                    className={isRunning ? 'text-orange-400' : 'text-emerald-400'}
                                >
                                    {isRunning ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => tick()}>
                                    +1
                                </Button>
                                <Button size="sm" variant="ghost" onClick={reset}>
                                    <RotateCcw className="w-3 h-3" />
                                </Button>
                            </div>

                            <span>
                                Phase: <span className="text-slate-300 capitalize">{phase.replace('-', ' ')}</span>
                            </span>
                        </div>

                        <div className="flex items-center gap-4">
                            <span>
                                Predictions:{' '}
                                <span className={predictions.length ? 'text-orange-400' : ''}>
                                    {predictions.length}
                                </span>
                            </span>
                            <span>
                                Detections:{' '}
                                <span className={detections.length ? 'text-red-400 font-semibold' : ''}>
                                    {detections.length}
                                </span>
                            </span>
                            {state && <span className="text-slate-500">{state.simulation_time}</span>}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Simulation;
