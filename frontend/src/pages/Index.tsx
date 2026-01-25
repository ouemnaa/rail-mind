import { useState } from 'react';
import { Clock, AlertTriangle, TrendingUp, Users } from 'lucide-react';
import { Header } from '@/components/layout/Header';
import { NetworkMap } from '@/components/dashboard/NetworkMap';
import { KPICard } from '@/components/dashboard/KPICard';
import { MemoryView } from '@/components/memory/MemoryView';
import { ResolutionPanel } from '@/components/resolution/ResolutionPanel';
import { ExplanationView } from '@/components/explanation/ExplanationView';

type View = 'dashboard' | 'memory' | 'resolution' | 'explanation';

const Index = () => {
  const [currentView, setCurrentView] = useState<View>('dashboard');
  const [showConflictDetail, setShowConflictDetail] = useState(false);

  const handleAlertClick = () => setShowConflictDetail(true);

  const handleViewResolution = () => {
    setCurrentView('memory');
    setShowConflictDetail(false);
  };

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
      default: // dashboard
        return (
          <div className="flex flex-col gap-6">
            {/* KPI Cards */}
            <div className="flex flex-wrap gap-4">
              <KPICard
                title="Avg Delay"
                value="4.2"
                unit="min"
                change={-12}
                icon={Clock}
                status="normal"
              />
              <KPICard
                title="Active Conflicts"
                value="2"
                icon={AlertTriangle}
                status="warning"
              />
              <KPICard
                title="Network Flow"
                value="94"
                unit="%"
                change={3}
                icon={TrendingUp}
                status="normal"
              />
              <KPICard
                title="Passengers"
                value="12.4K"
                change={8}
                icon={Users}
                status="normal"
              />
            </div>

            {/* Network Map */}
            <div className="flex-1">
              <NetworkMap onStationClick={() => setShowConflictDetail(true)} />
            </div>

            
          </div>
        );
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-background">
      <Header />

      <main className="flex-1 overflow-auto p-6">
        {renderMainContent()}
      </main>
    </div>
  );
};

export default Index;


{/*

  --- WITH RIGHT BARE THAT SHOWS CONFLICTS ---

import { useState } from 'react';
import { Clock, AlertTriangle, TrendingUp, Users } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { NetworkMap } from '@/components/dashboard/NetworkMap';
import { KPICard } from '@/components/dashboard/KPICard';
import { MemoryView } from '@/components/memory/MemoryView';
import { ResolutionPanel } from '@/components/resolution/ResolutionPanel';
import { ExplanationView } from '@/components/explanation/ExplanationView';

type View = 'dashboard' | 'memory' | 'resolution' | 'explanation';

const Index = () => {
  const [currentView, setCurrentView] = useState<View>('dashboard');
  const [showConflictDetail, setShowConflictDetail] = useState(false);

  const handleAlertClick = () => {
    setShowConflictDetail(true);
  };

  const handleViewResolution = () => {
    setCurrentView('memory');
    setShowConflictDetail(false);
  };

  const renderMainContent = () => {
    switch (currentView) {
      case 'memory':
        return (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
            <MemoryView />
            <ResolutionPanel onViewExplanation={() => setCurrentView('explanation')} />
          </div>
        );
      case 'resolution':
        return (
          <div className="max-w-2xl mx-auto h-full">
            <ResolutionPanel onViewExplanation={() => setCurrentView('explanation')} />
          </div>
        );
      case 'explanation':
        return (
          <div className="max-w-3xl mx-auto h-full">
            <ExplanationView onBack={() => setCurrentView('memory')} />
          </div>
        );
      default:
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
            <div className="lg:col-span-2 flex flex-col gap-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <KPICard
                  title="Avg Delay"
                  value="4.2"
                  unit="min"
                  change={-12}
                  icon={Clock}
                  status="normal"
                />
                <KPICard
                  title="Active Conflicts"
                  value="2"
                  icon={AlertTriangle}
                  status="warning"
                />
                <KPICard
                  title="Network Flow"
                  value="94"
                  unit="%"
                  change={3}
                  icon={TrendingUp}
                  status="normal"
                />
                <KPICard
                  title="Passengers"
                  value="12.4K"
                  change={8}
                  icon={Users}
                  status="normal"
                />
              </div>

              <div className="flex-1">
                <NetworkMap onStationClick={() => setShowConflictDetail(true)} />
              </div>
            </div>

             <div className="h-full">
              {showConflictDetail ? (
                <ConflictDetail 
                  onClose={() => setShowConflictDetail(false)} 
                  onResolve={handleViewResolution}
                />
              ) : (
                <AlertFeed onAlertClick={handleAlertClick} />
              )}
            </div>
            
           
          </div>
        );
    }
  };

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <Sidebar currentView={currentView} onViewChange={setCurrentView} />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        
        <main className="flex-1 overflow-auto p-6">
          {renderMainContent()}
        </main>
      </div>
    </div>
  );
};

export default Index;

*/}
