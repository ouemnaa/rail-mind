import { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Polyline, Popup, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { BatchPrediction, RiskLevel } from '../../types/prediction';
import { AlertTriangle, Train as TrainIcon, Layers } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface LombardyStation {
  name: string;
  lat: number;
  lon: number;
  isHub: boolean;
  trainsCount: number;
  riskLevel: RiskLevel;
  maxRiskProbability: number;
}

interface LombardyTrain {
  id: string;
  type: string;
  currentStation: string;
  nextStation: string | null;
  lat: number;
  lon: number;
  riskLevel: RiskLevel;
  probability: number;
  conflictType: string | null;
  location: string | null;
}

interface RouteStop {
  station_name: string;
  lat: number;
  lon: number;
}

interface SimulationTrain {
  train_id: string;
  train_type: string;
  route: RouteStop[];
}

interface LombardyLeafletMapProps {
  predictions?: BatchPrediction | null;
  realTimeTrains?: any[];
  onStationClick?: (station: LombardyStation) => void;
  onTrainClick?: (train: LombardyTrain) => void;
  selectedTrainId?: string | null;
  isDarkMode?: boolean;
}

// ============================================================================
// Constants
// ============================================================================

const RISK_COLORS: Record<RiskLevel, string> = {
  safe: '#10b981',      // Emerald green
  low_risk: '#f59e0b',  // Amber
  high_risk: '#f97316', // Orange
  critical: '#dc2626',  // Red
};

const MAJOR_HUBS = new Set([
  'MILANO CENTRALE',
  'MILANO PORTA GARIBALDI',
  'MILANO CADORNA',
  'MILANO BOVISA',
  'MILANO LAMBRATE',
  'BRESCIA',
  'BERGAMO',
  'PAVIA',
  'MONZA',
  'VARESE',
  'COMO SAN GIOVANNI',
  'LECCO',
  'CREMONA',
  'MANTOVA',
]);

export function LombardyLeafletMap({
  predictions,
  realTimeTrains,
  onStationClick,
  onTrainClick,
  selectedTrainId,
  isDarkMode = true,
}: LombardyLeafletMapProps) {
  const [stations, setStations] = useState<Map<string, LombardyStation>>(new Map());
  const [fallbackTrains, setFallbackTrains] = useState<LombardyTrain[]>([]);
  const [connections, setConnections] = useState<Array<{ from: [number, number]; to: [number, number] }>>([]);
  const [isSatellite, setIsSatellite] = useState(false);

  // Load simulation data
  useEffect(() => {
    fetch('/lombardy_simulation_data.json')
      .then((res) => res.json())
      .then((data: { trains: SimulationTrain[] }) => {
        const stationMap = new Map<string, LombardyStation>();
        const connectionSet = new Set<string>();

        data.trains.forEach((train) => {
          train.route.forEach((stop, index) => {
            if (!stationMap.has(stop.station_name)) {
              stationMap.set(stop.station_name, {
                name: stop.station_name,
                lat: stop.lat,
                lon: stop.lon,
                isHub: MAJOR_HUBS.has(stop.station_name),
                trainsCount: 0,
                riskLevel: 'safe',
                maxRiskProbability: 0,
              });
            }

            if (index < train.route.length - 1) {
              const nextStop = train.route[index + 1];
              const connKey = [stop.station_name, nextStop.station_name].sort().join('|');
              connectionSet.add(connKey);
            }
          });
        });

        setStations(stationMap);
        
        const newConnections: Array<{ from: [number, number]; to: [number, number] }> = [];
        connectionSet.forEach((key) => {
          const [fromName, toName] = key.split('|');
          const from = stationMap.get(fromName);
          const to = stationMap.get(toName);
          if (from && to) {
            newConnections.push({ from: [from.lat, from.lon], to: [to.lat, to.lon] });
          }
        });
        setConnections(newConnections);

        // Initialize mock trains if real-time not available
        const initialTrains: LombardyTrain[] = data.trains.slice(0, 40).map((t) => {
          const stopIdx = Math.floor(Math.random() * (t.route.length - 1));
          const stop = t.route[stopIdx];
          return {
            id: t.train_id,
            type: t.train_type,
            currentStation: stop.station_name,
            nextStation: t.route[stopIdx + 1]?.station_name || null,
            lat: stop.lat,
            lon: stop.lon,
            riskLevel: 'safe',
            probability: 0,
            conflictType: null,
            location: stop.station_name,
          };
        });
        setFallbackTrains(initialTrains);
      })
      .catch(err => console.error("Map data load error:", err));
  }, []);

  // Process trains for display
  const displayTrains = useMemo(() => {
    const rawTrains = realTimeTrains || fallbackTrains;
    return rawTrains.map((t: any) => {
      const isLombardyTrain = 'riskLevel' in t;
      if (isLombardyTrain) return t as LombardyTrain;
      
      const pred = predictions?.predictions.find(p => p.train_id === t.train_id);
      return {
        id: t.train_id,
        type: t.train_type,
        currentStation: t.current_station,
        nextStation: t.next_station,
        lat: t.lat,
        lon: t.lon,
        riskLevel: (pred?.risk_level || 'safe') as RiskLevel,
        probability: pred?.probability || 0,
        conflictType: pred?.predicted_conflict_type || null,
        location: t.current_station,
      } as LombardyTrain;
    });
  }, [realTimeTrains, fallbackTrains, predictions]);

  return (
    <div className="w-full h-full rounded-[2.5rem] overflow-hidden relative group border-4 border-white/10 shadow-2xl">
      <MapContainer 
        center={[45.4642, 9.1900]} 
        zoom={10} 
        style={{ height: '100%', width: '100%', background: '#0f172a' }}
        scrollWheelZoom={true}
        className="z-10"
      >
        <TileLayer
          attribution='&copy; CARTO'
          url={isSatellite 
            ? "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            : isDarkMode 
                ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                : "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          }
        />

        {connections.map((conn, i) => (
          <Polyline 
            key={`conn-${i}`} 
            positions={[conn.from, conn.to]} 
            pathOptions={{ color: isDarkMode ? '#334155' : '#cbd5e1', weight: 1.5, opacity: 0.5 }} 
          />
        ))}

        {Array.from(stations.values()).map((s) => (
          <CircleMarker
            key={`station-${s.name}`}
            center={[s.lat, s.lon]}
            radius={s.isHub ? 6 : 3}
            pathOptions={{ 
                fillColor: '#fff', 
                color: isDarkMode ? '#1e293b' : '#64748b', 
                weight: 2, 
                fillOpacity: 1 
            }}
            eventHandlers={{
                click: () => onStationClick?.(s)
            }}
          >
            <Popup>
              <div className="p-1">
                <div className="font-bold text-base">{s.name}</div>
                <div className="text-[10px] text-muted-foreground uppercase font-black mt-1">Station Network Node</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {displayTrains.map((t) => (
          <CircleMarker
            key={`train-${t.id}`}
            center={[t.lat, t.lon]}
            radius={7}
            pathOptions={{
                fillColor: RISK_COLORS[t.riskLevel],
                color: '#fff',
                weight: 2,
                fillOpacity: 1,
            }}
            eventHandlers={{
                click: () => onTrainClick?.(t)
            }}
          >
            <Popup className="premium-popup">
              <div className="w-52 p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="font-black text-xl tracking-tighter italic">{t.id}</div>
                  <div className={`px-2 py-0.5 rounded text-[10px] font-bold text-white uppercase`} style={{ backgroundColor: RISK_COLORS[t.riskLevel] }}>
                    {t.riskLevel.replace('_', ' ')}
                  </div>
                </div>
                
                <div className="space-y-1">
                  <div className="text-[9px] uppercase font-black text-slate-400">Current Vector</div>
                  <div className="text-xs font-bold">{t.currentStation} → {t.nextStation || 'Final Destination'}</div>
                </div>

                {t.conflictType && (
                   <div className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/20 rounded-xl">
                      <AlertTriangle className="w-4 h-4 text-red-500" />
                      <div className="text-[10px] font-black text-red-500 uppercase">AI: {t.conflictType}</div>
                   </div>
                )}
                
                <div className="pt-2 border-t border-slate-100 flex justify-between items-center text-[10px]">
                   <span className="text-slate-400 font-bold uppercase">AI Confidence</span>
                   <span className="font-black">{(t.probability * 100).toFixed(0)}%</span>
                </div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Floating HUD Container */}
      <div className="absolute top-6 left-6 z-[400] flex flex-col gap-3 pointer-events-none">
         <div className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl p-4 shadow-2xl rounded-2xl pointer-events-auto border border-white/20">
            <div className="flex items-center gap-3">
               <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-600/30">
                  <TrainIcon className="w-6 h-6 text-white" />
               </div>
               <div>
                  <div className="text-sm font-black uppercase tracking-tighter dark:text-white">Lombardy Traffic</div>
                  <div className="text-[10px] font-bold text-blue-500 uppercase tracking-widest">{displayTrains.length} Active Vectors</div>
               </div>
            </div>
         </div>
         
         <button 
            onClick={() => setIsSatellite(!isSatellite)}
            className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl p-3 shadow-xl rounded-xl pointer-events-auto flex items-center gap-2 transition-all hover:scale-105 active:scale-95 border border-white/20"
         >
            <Layers className="w-4 h-4 text-blue-600" />
            <span className="text-[10px] font-black uppercase tracking-widest dark:text-white">
                {isSatellite ? 'Street View' : 'Satellite View'}
            </span>
         </button>
      </div>
      
      {/* Legend Overlay */}
      <div className="absolute bottom-6 right-6 z-[400] bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl p-4 shadow-2xl rounded-2xl pointer-events-auto border border-white/20">
         <div className="space-y-2">
            {Object.entries(RISK_COLORS).map(([level, color]) => (
               <div key={level} className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full shadow-[0_0_8px_rgba(0,0,0,0.2)]" style={{ backgroundColor: color }}></div>
                  <span className="text-[9px] font-black uppercase tracking-widest text-slate-500 dark:text-slate-400">{level.replace('_', ' ')}</span>
               </div>
            ))}
         </div>
      </div>

      <style>{`
        .leaflet-container {
            background: #0f172a !important;
        }
        .premium-popup .leaflet-popup-content-wrapper {
            border-radius: 1.25rem !important;
            padding: 0 !important;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.98);
            backdrop-filter: blur(10px);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25) !important;
        }
        .premium-popup .leaflet-popup-content {
            margin: 0 !important;
        }
        .leaflet-popup-tip {
            background: rgba(255, 255, 255, 0.98);
        }
      `}</style>
    </div>
  );
}

export default LombardyLeafletMap;
