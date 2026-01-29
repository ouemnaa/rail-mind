/**
 * User (Passenger) View
 * =====================
 * 
 * A friendly, real-time passenger view for Rail Mind.
 * Features:
 * - Live train delays sorted by severity
 * - Top 3 delayed trains as highlighted cards
 * - Network risk summary
 * - Interactive region map
 * - Toast notifications for major delays
 * - Light/Dark mode toggle
 * 
 * Visual layout: Full-page dashboard that adapts from mobile stack to desktop grid.
 */

import { useState, useEffect, useMemo, lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Clock, 
  RefreshCw, 
  Train as TrainIcon, 
  Map as MapIcon, 
  AlertTriangle,
  Settings,
  Wifi,
  WifiOff,
  Sun,
  Moon,
  ChevronDown,
  ChevronUp,
  Search,
  Filter,
  Download
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useUnifiedSimulation } from '@/hooks/useUnifiedSimulation';
import { useInstallPrompt } from '@/hooks/use-install-prompt';
import { TrainCard, TrainCardCompact } from '@/components/user/TrainCard';
import { TrainDetailDrawer } from '@/components/user/TrainDetailDrawer';
import { toast } from 'sonner';
import type { TrainData } from '@/hooks/useUnifiedSimulation';

import { LombardyNetworkMap } from '@/components/dashboard/LombardyNetworkMap';

const POLL_INTERVAL = 5000;
const MAJOR_DELAY_THRESHOLD = 600; 

export default function User() {
  const navigate = useNavigate();
  const { isInstallable, installApp } = useInstallPrompt();
  const [showMapMobile, setShowMapMobile] = useState(false);
  const [selectedTrain, setSelectedTrain] = useState<TrainData | null>(null);
  const [lastNotifiedTrains, setLastNotifiedTrains] = useState<Set<string>>(new Set());
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [showAllTrains, setShowAllTrains] = useState(false);
  const [trafficFilter, setTrafficFilter] = useState<'all' | 'delayed' | 'ontime'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Toggle theme
  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDarkMode);
    document.documentElement.classList.toggle('light', !isDarkMode);
  }, [isDarkMode]);

  const {
    state,
    trains,
    predictions,
    detections,
    isLoading,
    error,
  } = useUnifiedSimulation({ autoStart: true, tickInterval: POLL_INTERVAL });

  const filteredTrains = useMemo(() => {
    let result = [...trains];
    
    // Status Filter
    if (trafficFilter === 'delayed') result = result.filter(t => t.delay_sec > 60);
    if (trafficFilter === 'ontime') result = result.filter(t => t.delay_sec <= 60);
    
    // Search Query
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(t => 
        t.train_id.toLowerCase().includes(q) || 
        (t.current_station || '').toLowerCase().includes(q) ||
        (t.next_station || '').toLowerCase().includes(q)
      );
    }
    
    return result.sort((a, b) => b.delay_sec - a.delay_sec);
  }, [trains, trafficFilter, searchQuery]);

  const topDelayedTrains = useMemo(() => {
    return trains.filter(t => t.delay_sec > 60).sort((a, b) => b.delay_sec - a.delay_sec).slice(0, 3);
  }, [trains]);

  const networkRisk = useMemo(() => {
    if (!state) return 0;
    const avgProbability = predictions.length > 0
      ? predictions.reduce((sum, p) => sum + p.probability, 0) / predictions.length
      : 0;
    const detectionBoost = detections.length > 0 ? 0.2 : 0;
    return Math.min(avgProbability + detectionBoost, 1);
  }, [state, predictions, detections]);

  const getRiskStyle = (risk: number) => {
    if (risk > 0.6) return { color: 'text-red-500', bg: 'bg-red-500/10', label: 'High Risk', emoji: '🔴' };
    if (risk > 0.3) return { color: 'text-orange-500', bg: 'bg-orange-500/10', label: 'Moderate', emoji: '🟠' };
    if (risk > 0.1) return { color: 'text-yellow-500', bg: 'bg-yellow-500/10', label: 'Low Risk', emoji: '🟡' };
    return { color: 'text-emerald-500', bg: 'bg-emerald-500/10', label: 'All Clear', emoji: '🟢' };
  };

  const riskStyle = getRiskStyle(networkRisk);

  useEffect(() => {
    trains.forEach(train => {
      if (train.delay_sec >= MAJOR_DELAY_THRESHOLD && !lastNotifiedTrains.has(train.train_id)) {
        toast.warning(`⚠️ Train ${train.train_id} is now ${Math.floor(train.delay_sec / 60)} minutes late`, {
          description: 'Significant delay alert.',
          duration: 8000,
        });
        setLastNotifiedTrains(prev => new Set(prev).add(train.train_id));
      }
    });
  }, [trains, lastNotifiedTrains]);

  const delayedCount = trains.filter(t => t.delay_sec > 60).length;
  const onTimeCount = trains.filter(t => t.delay_sec <= 60).length;

  return (
    <div className={`min-h-screen transition-all duration-500 ${
      isDarkMode ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'
    }`}>
      {/* Header - Full Bleed */}
      <header className={`sticky top-0 z-40 backdrop-blur-xl border-b transition-colors duration-300 ${
        isDarkMode ? 'bg-slate-950/80 border-slate-800/60' : 'bg-white/80 border-slate-200'
      }`}>
        <div className="w-full px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-xl ${
              isDarkMode ? 'bg-blue-600' : 'bg-blue-500'
            }`}>
              <TrainIcon className="w-6 h-6 text-white" />
            </div>
            <div className="hidden sm:block">
              <h1 className="font-black text-2xl tracking-tighter uppercase italic">Rail Mind</h1>
              <p className={`text-[10px] font-bold uppercase tracking-[0.2em] ${isDarkMode ? 'text-slate-500' : 'text-slate-400'}`}>
                Passenger Intelligence
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            {/* Connection Status */}
             <div className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-black uppercase tracking-widest ${
              error ? 'bg-red-500/10 text-red-500' : 'bg-emerald-500/10 text-emerald-500'
            }`}>
              <Wifi className="w-3 h-3" />
              <span className="hidden md:inline">{error ? 'Offline' : 'Real-time'}</span>
            </div>

            {/* Install App Button */}
            {isInstallable && (
              <button
                onClick={installApp}
                className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-black uppercase tracking-widest transition-all ${
                  isDarkMode 
                    ? 'bg-blue-600/10 text-blue-400 hover:bg-blue-600/20' 
                    : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
                }`}
              >
                <Download className="w-3 h-3" />
                <span className="hidden md:inline">Install App</span>
              </button>
            )}

            <button
              onClick={toggleTheme}
              className={`p-3 rounded-2xl transition-all ${
                isDarkMode ? 'bg-slate-900 text-yellow-400 hover:bg-slate-800' : 'bg-white text-slate-600 hover:bg-slate-100 shadow-sm border'
              }`}
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            
            {/* <Button 
              variant="outline" 
              size="sm" 
              onClick={() => navigate('/')}
              className="rounded-2xl font-bold uppercase text-[10px] tracking-widest px-6"
            >
              <Settings className="w-4 h-4 mr-2" />
              Operator View
            </Button> */}
          </div>
        </div>
      </header>

      {/* Hero Banner - Information density & Spacing */}
      <div className={`w-full px-6 py-10 transition-colors ${isDarkMode ? 'bg-blue-600/5' : 'bg-blue-500/5'}`}>
        <div className="flex flex-col lg:flex-row items-center lg:justify-between gap-8">
           <div className="flex flex-col items-center lg:items-start gap-4">
              <div className={`inline-flex items-center gap-2 px-5 py-2 rounded-full font-bold text-xs uppercase tracking-tighter ${
                isDarkMode ? 'bg-slate-900 text-slate-400' : 'bg-white text-slate-500 shadow-sm'
              }`}>
                <Clock className="w-4 h-4 text-blue-500" />
                Live Schedule • {state?.simulation_time || 'Syncing...'}
              </div>
              <h2 className="text-4xl lg:text-6xl font-black tracking-tighter text-center lg:text-left leading-none">
                Travel Smart with <br/> <span className="text-blue-500">Live AI Routing</span>
              </h2>
           </div>

            <div className={`p-8 rounded-[2.5rem] border-2 border-dashed ${isDarkMode ? 'border-slate-800 text-slate-500' : 'border-slate-200 text-slate-400'}`}>
               <p className="text-sm font-medium italic leading-relaxed text-center italic">
                 "Travel tip: Platform numbers are usually announced 10 minutes before arrival. Stay hydrated! 🥤"
               </p>
            </div>
        </div>
      </div>

      {/* Main Grid Layout - Responsively taking full page */}
      <main className="w-full px-6 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
          
          {/* LEFT: Stats & Alerts (4/12) */}
          <div className="lg:col-span-4 space-y-10">
            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className={`group p-8 rounded-[2.5rem] transition-all hover:scale-[1.03] ${
                isDarkMode ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-white border-2 border-emerald-100 shadow-xl shadow-emerald-500/5'
              }`}>
                <div className="text-5xl font-black text-emerald-500 mb-1 group-hover:scale-110 transition-transform">{onTimeCount}</div>
                <div className="text-xs font-black uppercase tracking-widest text-emerald-500/70">On Time</div>
              </div>
              <div className={`group p-8 rounded-[2.5rem] transition-all hover:scale-[1.03] ${
                isDarkMode ? 'bg-orange-500/10 border border-orange-500/20' : 'bg-white border-2 border-orange-100 shadow-xl shadow-orange-500/5'
              }`}>
                <div className="text-5xl font-black text-orange-500 mb-1 group-hover:scale-110 transition-transform">{delayedCount}</div>
                <div className="text-xs font-black uppercase tracking-widest text-orange-500/70">Delayed</div>
              </div>
            </div>

            {/* Today's Delays Section */}
            {topDelayedTrains.length > 0 && (
              <section className="space-y-6">
                <div className="flex items-center gap-4">
                   <h3 className="font-black text-xl uppercase italic tracking-tighter">Critical Alerts</h3>
                   <div className="h-0.5 flex-1 bg-orange-500/20" />
                </div>
                <div className="space-y-4">
                  {topDelayedTrains.map(train => (
                    <TrainCard
                      key={train.train_id}
                      trainId={train.train_id}
                      trainType={train.train_type}
                      origin={train.current_station}
                      destination={train.next_station}
                      delaySec={train.delay_sec}
                      status={train.status}
                      isHighlighted={true}
                      onClick={() => setSelectedTrain(train)}
                    />
                  ))}
                </div>
              </section>
            )}

            
          </div>

          {/* CENTER/RIGHT: List & Map (8/12) */}
          <div className="lg:col-span-8 space-y-10">
            
            {/* Map Section - Prominent on Desktop */}
            <section className="hidden lg:block">
              <div className={`rounded-[3rem] overflow-hidden border-8 shadow-2xl transition-all ${
                isDarkMode ? 'border-slate-900 bg-slate-900' : 'border-white bg-white'
              }`}>
                <div className="h-[550px]">
                  <Suspense fallback={<div className="h-full w-full flex items-center justify-center"><RefreshCw className="animate-spin" /></div>}>
                    <LombardyNetworkMap 
                      predictions={state ? { 
                        timestamp: state.simulation_time, 
                        predictions: predictions.map(p => ({
                          train_id: p.involved_trains[0] || 'Unknown',
                          probability: p.probability,
                          risk_level: p.severity as any,
                          color: p.severity === 'critical' ? '#dc2626' : p.severity === 'high' ? '#f97316' : '#f59e0b',
                          emoji: p.severity === 'critical' ? '🔴' : '🟠',
                          predicted_conflict_type: p.conflict_type as any,
                          predicted_time: p.timestamp,
                          predicted_location: p.location,
                          contributing_factors: [p.explanation],
                          confidence: 0.9
                        })), 
                        network_risk_score: networkRisk, 
                        high_risk_trains: [], 
                        critical_trains: [], 
                        recommended_actions: [], 
                        model_used: 'ensemble', 
                        strategy: 'default' 
                      } : null} 
                    />
                  </Suspense>
                </div>
              </div>
            </section>

            {/* Mobile Collapsible Map */}
            <section className="lg:hidden">
              <button
                onClick={() => setShowMapMobile(!showMapMobile)}
                className={`w-full flex items-center justify-between p-6 rounded-3xl transition-all ${
                  isDarkMode ? 'bg-slate-900 border border-slate-800' : 'bg-white shadow-lg border border-slate-100 font-bold'
                }`}
              >
                <div className="flex items-center gap-3">
                  <MapIcon className="w-5 h-5 text-blue-500" />
                  <span>Interactive Network Map</span>
                </div>
                {showMapMobile ? <ChevronUp /> : <ChevronDown />}
              </button>
              {showMapMobile && (
                <div className="mt-4 h-[400px] rounded-3xl overflow-hidden border-2 border-blue-500/20">
                   <Suspense fallback={<div className="h-full flex items-center justify-center"><RefreshCw /></div>}>
                     <LombardyNetworkMap 
                        predictions={state ? { 
                          timestamp: state.simulation_time, 
                          predictions: predictions.map(p => ({
                            train_id: p.involved_trains[0] || 'Unknown',
                            probability: p.probability,
                            risk_level: p.severity as any,
                            color: p.severity === 'critical' ? '#dc2626' : p.severity === 'high' ? '#f97316' : '#f59e0b',
                            emoji: p.severity === 'critical' ? '🔴' : '🟠',
                            predicted_conflict_type: p.conflict_type as any,
                            predicted_time: p.timestamp,
                            predicted_location: p.location,
                            contributing_factors: [p.explanation],
                            confidence: 0.9
                          })), 
                          network_risk_score: networkRisk, 
                          high_risk_trains: [], 
                          critical_trains: [], 
                          recommended_actions: [], 
                          model_used: 'ensemble', 
                          strategy: 'default' 
                        } : null}
                     />
                   </Suspense>
                </div>
              )}
            </section>

            {/* All Trains Feed - Streamlined */}
            <section className="space-y-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                 <h3 className="font-black text-xl uppercase italic tracking-tighter">Traffic Feed</h3>
                 
                 <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0 scrollbar-hide">
                    {[
                      { id: 'all', label: 'All', count: trains.length },
                      { id: 'delayed', label: 'Delayed', count: delayedCount, color: 'text-orange-500' },
                      { id: 'ontime', label: 'On Time', count: onTimeCount, color: 'text-emerald-500' }
                    ].map(f => (
                      <button
                        key={f.id}
                        onClick={() => setTrafficFilter(f.id as any)}
                        className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold transition-all whitespace-nowrap ${
                          trafficFilter === f.id
                            ? (isDarkMode ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20' : 'bg-blue-500 text-white shadow-lg shadow-blue-500/20')
                            : (isDarkMode ? 'bg-slate-900 text-slate-500 hover:bg-slate-800' : 'bg-white text-slate-400 hover:bg-slate-50 shadow-sm border')
                        }`}
                      >
                        {f.label} <span className="opacity-50 font-black">{f.count}</span>
                      </button>
                    ))}
                 </div>
              </div>

              {/* Search Bar */}
              <div className="relative group max-w-md">
                 <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                    <Search className={`w-4 h-4 transition-colors ${searchQuery ? 'text-blue-500' : 'text-slate-500'}`} />
                 </div>
                 <Input 
                    placeholder="Search train ID or station..."
                    className={`pl-10 h-12 rounded-2xl transition-all shadow-sm border-2 ${
                       isDarkMode 
                        ? 'bg-slate-900 border-slate-800 focus:border-blue-600 text-white' 
                        : 'bg-white border-slate-100 focus:border-blue-500 text-slate-900'
                    }`}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                 />
              </div>

              {/* Grid of Train Cards */}
              {filteredTrains.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filteredTrains.slice(0, showAllTrains ? filteredTrains.length : 6).map(train => (
                    <TrainCardCompact
                      key={train.train_id}
                      trainId={train.train_id}
                      trainType={train.train_type}
                      origin={train.current_station}
                      destination={train.next_station}
                      delaySec={train.delay_sec}
                      status={train.status}
                      onClick={() => setSelectedTrain(train)}
                    />
                  ))}
                </div>
              ) : (
                <div className={`p-12 text-center rounded-[2.5rem] border-2 border-dashed ${isDarkMode ? 'border-slate-800' : 'border-slate-100'}`}>
                   <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">No matching trains found</p>
                </div>
              )}

              {/* Show More / Show Less Button */}
              {filteredTrains.length > 6 && (
                <div className="text-center pt-2">
                   <button 
                      onClick={() => setShowAllTrains(!showAllTrains)}
                      className={`group flex items-center gap-2 mx-auto px-8 py-3 rounded-2xl font-black text-xs uppercase tracking-widest transition-all ${
                        isDarkMode 
                          ? 'bg-slate-900 hover:bg-slate-800 text-slate-300' 
                          : 'bg-white shadow-lg border border-slate-100 hover:bg-slate-50 text-slate-600'
                      }`}
                   >
                      {showAllTrains ? (
                         <>Show Fewer Results <ChevronUp className="w-3 h-3 transition-transform group-hover:-translate-y-0.5" /></>
                      ) : (
                         <>View All {filteredTrains.length} Results <ChevronDown className="w-3 h-3 transition-transform group-hover:translate-y-0.5" /></>
                      )}
                   </button>
                </div>
              )}
            </section>
          </div>
        </div>
      </main>

      <TrainDetailDrawer
        train={selectedTrain}
        isOpen={selectedTrain !== null}
        onClose={() => setSelectedTrain(null)}
      />

      <style>{`
        @keyframes pulse-subtle {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.9; transform: scale(0.99); }
        }
        .animate-pulse-subtle {
          animation: pulse-subtle 3s ease-in-out infinite;
        }
        @keyframes slide-up {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
        .animate-slide-up {
          animation: slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>
    </div>
  );
}
