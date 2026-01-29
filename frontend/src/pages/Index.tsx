import { useState, useMemo } from 'react';
import { Clock, AlertTriangle, TrendingUp, Users, WifiOff, Play, Pause, RotateCcw, FastForward, Map } from 'lucide-react';
import { Header } from '@/components/layout/Header';
import { LombardyNetworkMap } from '@/components/dashboard/LombardyNetworkMap';
import { NetworkMap } from '@/components/dashboard/NetworkMap';
import { UnifiedAlertPanel } from '@/components/dashboard/UnifiedAlertPanel';
import { KPICard } from '@/components/dashboard/KPICard';
import { MemoryView } from '@/components/memory/MemoryView';
import { ResolutionPanel } from '@/components/resolution/ResolutionPanel';
import { ExplanationView } from '@/components/explanation/ExplanationView';
import { MaintenanceView } from '@/components/maintanace/MaintenanceView';
import { DocumentationView } from '@/components/documentation/DocumentationView';
import { useUnifiedSimulation } from '@/hooks/useUnifiedSimulation';
import type { BatchPrediction, ConflictPrediction } from '@/types/prediction';
import { Sidebar } from '@/components/layout/Sidebar';

type View = 'dashboard' | 'memory' | 'resolution' | 'explanation' | 'maintenance' | 'documentation';
type MapMode = 'lombardy' | 'full-network';

const Index = () => {
  const [currentView, setCurrentView] = useState<View>('dashboard');
  const [showConflictDetail, setShowConflictDetail] = useState(false);
  const [mapMode, setMapMode] = useState<MapMode>('lombardy');

  const {
    state,
    trains,
    predictions,
    detections,
    isRunning,
    isLoading,
    error,
    start,
    stop,
    tick,
    multiTick,
    reset,
  } = useUnifiedSimulation({ autoStart: true, tickInterval: 2000 });

  const batchPrediction: BatchPrediction | null = useMemo(() => {
    if (!state) return null;

    const allConflicts = [...predictions, ...detections];

    const avgProbability = predictions.length > 0
      ? predictions.reduce((sum, p) => sum + p.probability, 0) / predictions.length
      : 0;

    const detectionBoost = detections.length > 0 ? 0.2 : 0;
    const networkRisk = Math.min(avgProbability + detectionBoost, 1);

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
      network_risk_score: networkRisk,
      high_risk_trains: predictions.filter(p => p.probability >= 0.6).flatMap(p => p.involved_trains),
      critical_trains: detections.flatMap(d => d.involved_trains),
      recommended_actions: [],
      model_used: 'xgboost_ensemble',
      strategy: 'continuous',
    };
  }, [state, predictions, detections]);

  const criticalCount = detections.length;
  const highRiskCount = predictions.filter(p => p.probability >= 0.5).length;
  const networkRisk = batchPrediction?.network_risk_score || 0;
  const totalTrains = trains.length;
  const delayedTrains = trains.filter(t => t.delay_sec > 60).length;

  const renderMainContent = () => {
    switch (currentView) {
      case 'memory':
        return (
          <div className="flex flex-col gap-6">
            <MemoryView />
            <ResolutionPanel onViewExplanation={() => setCurrentView('explanation')} />
          </div>
        );
      case 'resolution':
        return (
          <div className="max-w-2xl mx-auto">
            <ResolutionPanel onViewExplanation={() => setCurrentView('explanation')} />
          </div>
        );
      case 'explanation':
        return (
          <div className="max-w-3xl mx-auto">
            <ExplanationView onBack={() => setCurrentView('memory')} />
          </div>
        );
      case 'maintenance':
        return <MaintenanceView onBack={() => setCurrentView('dashboard')} />;
      case 'documentation':
        return <DocumentationView onBack={() => setCurrentView('dashboard')} />;
      default: // dashboard
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
            <div className="lg:col-span-2 flex flex-col gap-6">
              {/* KPI Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <KPICard title="Network Risk" value={(networkRisk*100).toFixed(0)} unit="%" icon={TrendingUp} status={networkRisk>0.5?'critical':networkRisk>0.3?'warning':'normal'} />
                <KPICard title="Active Conflicts" value={criticalCount.toString()} icon={AlertTriangle} status={criticalCount>0?'critical':'normal'} />
                <KPICard title="High Risk" value={highRiskCount.toString()} icon={Clock} status={highRiskCount>3?'warning':'normal'} />
                <KPICard title="Trains" value={`${totalTrains}`} icon={Users} status={delayedTrains>5?'warning':'normal'} />
              </div>

              {/* Map Toggle */}
              <div className="flex-1 min-h-[500px] flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold">Rail Network</h2>
                  <button
                    onClick={() => setMapMode(mapMode === 'lombardy' ? 'full-network' : 'lombardy')}
                    className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm transition-colors"
                    title={mapMode==='lombardy'?'Show full network':'Show Lombardy only'}
                  >
                    <Map className="w-4 h-4" />
                    {mapMode==='lombardy'?'Full Network':'Lombardy Only'}
                  </button>
                </div>
                {mapMode==='lombardy' ? (
                  <LombardyNetworkMap 
                    predictions={batchPrediction} 
                    onStationClick={()=>setShowConflictDetail(true)} 
                  />
                ) : (
                  <NetworkMap  onStationClick={()=>setShowConflictDetail(true)} />
                )}
              </div>
            </div>

            <div className="h-full min-h-[600px]">
              <UnifiedAlertPanel 
                predictions={predictions} 
                detections={detections} 
                tickNumber={state?.tick_number} 
                simulationTime={state?.simulation_time}
                onPause={stop}
                onResume={start}
              />
            </div>
          </div>
        );
    }
  };

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <Sidebar  />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        {error && (
          <div className="bg-red-500/20 border-b border-red-500/50 px-4 py-2 flex items-center justify-between">
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <WifiOff className="w-4 h-4" />
              <span>API connection error: {error}</span>
            </div>
            <button onClick={()=>tick()} className="text-xs bg-red-500/30 hover:bg-red-500/50 px-3 py-1 rounded">Retry</button>
          </div>
        )}
        {isLoading && !state && (
          <div className="bg-blue-500/20 border-b border-blue-500/50 px-4 py-2">
            <div className="flex items-center gap-2 text-blue-400 text-sm">
              <div className="animate-spin w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full" />
              <span>Connecting to simulation...</span>
            </div>
          </div>
        )}
        <main className="flex-1 overflow-auto p-6">{renderMainContent()}</main>
























    {/* Status bar with simulation controls */}
    <div className="border-t border-slate-700 bg-slate-900/50 px-4 py-2 text-xs text-slate-400 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 border-r border-slate-700 pr-4">
          <button
            onClick={isRunning ? stop : start}
            className={`p-1.5 rounded transition-colors ${
              isRunning
                ? 'bg-orange-500/20 text-orange-400 hover:bg-orange-500/30'
                : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
            }`}
            title={isRunning ? 'Pause simulation' : 'Start simulation'}
          >
            {isRunning ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
          </button>

          <button
            onClick={() => tick()}
            className="p-1.5 bg-slate-700/50 hover:bg-slate-600/50 rounded"
            title="Single tick"
          >
            <FastForward className="w-3 h-3" />
          </button>

          <button
            onClick={() => multiTick(5)}
            className="px-2 py-1 bg-slate-700/50 hover:bg-slate-600/50 rounded text-xs"
            title="5 ticks"
          >
            +5
          </button>

          <button
            onClick={reset}
            className="p-1.5 bg-slate-700/50 hover:bg-slate-600/50 rounded"
            title="Reset simulation"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </div>

        <span>
          Tick:{' '}
          <span className="text-slate-300 font-mono">
            {state?.tick_number || 0}
          </span>
        </span>
      </div>



      <div className="flex items-center gap-4">
        <span>
          Predictions:{' '}
          <span className={predictions.length ? 'text-orange-400' : 'text-slate-300'}>
            {predictions.length}
          </span>
        </span>

        <span>
          Detections:{' '}
          <span className={detections.length ? 'text-red-400 font-semibold' : 'text-slate-300'}>
            {detections.length}
          </span>
        </span>

        {state && (
          <span className="text-slate-500">
            {state.simulation_time}
          </span>
        )}
      </div>
    </div>
  </div>
</div>

  );
};

export default Index;
