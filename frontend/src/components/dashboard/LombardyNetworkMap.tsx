/**
 * Lombardy Rail Network Map
 * =========================
 *
 * Interactive map showing Lombardy region rail network with:
 * - Real stations from simulation data
 * - Live train positions with risk-based coloring
 * - Geographic coordinates mapped to SVG
 *
 * Risk Level Colors:
 * 🟢 GREEN:   Safe, no predicted conflicts (prob < 0.3)
 * 🟡 YELLOW:  Minor delay, low risk (prob 0.3-0.5)
 * 🟠 ORANGE:  High risk predicted (prob 0.6-0.8)
 * 🔴 RED:     Conflict detected NOW (prob > 0.8 or actual conflict)
 */

import { useState, useEffect, useRef, useMemo } from 'react';
import { ZoomIn, ZoomOut, Maximize2, Train as TrainIcon, AlertTriangle } from 'lucide-react';
import type { BatchPrediction, RiskLevel, IncidentType } from '../../types/prediction';

// ============================================================================
// Types
// ============================================================================

interface LombardyStation {
  name: string;
  lat: number;
  lon: number;
  x: number;  // SVG x coordinate
  y: number;  // SVG y coordinate
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
  position: { x: number; y: number };
  progress: number;  // 0-1 between stations
  riskLevel: RiskLevel;
  probability: number;
  conflictType: string | null;
  incidentType: IncidentType | null;
  location: string | null;
  factors: string[];
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

interface LombardyNetworkMapProps {
  predictions?: BatchPrediction | null;
  onStationClick?: (station: LombardyStation) => void;
  onTrainClick?: (train: LombardyTrain) => void;
  selectedTrainId?: string | null;
}

// ============================================================================
// Constants
// ============================================================================

// Lombardy bounding box - tighter focus on Milan metro area
const LOMBARDY_BOUNDS = {
  minLat: 45.15,   // South of Pavia
  maxLat: 45.95,   // North of Como
  minLon: 8.85,    // West
  maxLon: 10.15,   // East of Brescia
};

const SVG_WIDTH = 1400;   // Wider for better horizontal spread
const SVG_HEIGHT = 1000;  // Taller for better aspect ratio
const PADDING = 100;      // More padding for labels

// Risk level colors - more vibrant
const RISK_COLORS: Record<RiskLevel, string> = {
  safe: '#10b981',      // Emerald green
  low_risk: '#f59e0b',  // Amber
  high_risk: '#f97316', // Orange
  critical: '#dc2626',  // Red
};

const RISK_GLOW: Record<RiskLevel, string> = {
  safe: 'none',
  low_risk: 'drop-shadow(0 0 6px rgba(245, 158, 11, 0.6))',
  high_risk: 'drop-shadow(0 0 8px rgba(249, 115, 22, 0.7))',
  critical: 'drop-shadow(0 0 12px rgba(220, 38, 38, 0.8))',
};

// Major Lombardy hubs for larger display
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

// ============================================================================
// Coordinate Conversion
// ============================================================================

function geoToSvg(lat: number, lon: number): { x: number; y: number } {
  const x = PADDING + ((lon - LOMBARDY_BOUNDS.minLon) / (LOMBARDY_BOUNDS.maxLon - LOMBARDY_BOUNDS.minLon)) * (SVG_WIDTH - 2 * PADDING);
  const y = SVG_HEIGHT - PADDING - ((lat - LOMBARDY_BOUNDS.minLat) / (LOMBARDY_BOUNDS.maxLat - LOMBARDY_BOUNDS.minLat)) * (SVG_HEIGHT - 2 * PADDING);
  return { x, y };
}

// ============================================================================
// Component
// ============================================================================

export function LombardyNetworkMap({
  predictions,
  onStationClick,
  onTrainClick,
  selectedTrainId,
}: LombardyNetworkMapProps) {
  const [stations, setStations] = useState<Map<string, LombardyStation>>(new Map());
  const [trains, setTrains] = useState<LombardyTrain[]>([]);
  const [connections, setConnections] = useState<Array<{ from: string; to: string }>>([]);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredStation, setHoveredStation] = useState<string | null>(null);
  const [hoveredTrain, setHoveredTrain] = useState<string | null>(null);
  const [simulationTime, setSimulationTime] = useState(0);
  const svgRef = useRef<SVGSVGElement>(null);

  // Load Lombardy simulation data
  useEffect(() => {
    fetch('/lombardy_simulation_data.json')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load simulation data');
        return res.json();
      })
      .then((data: { trains: SimulationTrain[] }) => {
        const stationMap = new Map<string, LombardyStation>();
        const connectionSet = new Set<string>();

        // Extract stations and connections from routes
        data.trains.forEach((train) => {
          train.route.forEach((stop, index) => {
            // Add station if not exists
            if (!stationMap.has(stop.station_name)) {
              const coords = geoToSvg(stop.lat, stop.lon);
              stationMap.set(stop.station_name, {
                name: stop.station_name,
                lat: stop.lat,
                lon: stop.lon,
                x: coords.x,
                y: coords.y,
                isHub: MAJOR_HUBS.has(stop.station_name),
                trainsCount: 0,
                riskLevel: 'safe',
                maxRiskProbability: 0,
              });
            }

            // Add connection to next station
            if (index < train.route.length - 1) {
              const nextStop = train.route[index + 1];
              const connKey = [stop.station_name, nextStop.station_name].sort().join('|');
              connectionSet.add(connKey);
            }
          });
        });

        setStations(stationMap);
        setConnections(
          Array.from(connectionSet).map((key) => {
            const [from, to] = key.split('|');
            return { from, to };
          })
        );

        // Initialize trains with positions
        const initialTrains: LombardyTrain[] = data.trains.slice(0, 30).map((t, idx) => {
          const progress = Math.random();
          const stopIdx = Math.floor(progress * (t.route.length - 1));
          const currentStop = t.route[stopIdx];
          const nextStop = t.route[Math.min(stopIdx + 1, t.route.length - 1)];

          const fromCoords = geoToSvg(currentStop.lat, currentStop.lon);
          const toCoords = geoToSvg(nextStop.lat, nextStop.lon);
          const localProgress = (progress * (t.route.length - 1)) % 1;

          return {
            id: t.train_id,
            type: t.train_type,
            currentStation: currentStop.station_name,
            nextStation: nextStop.station_name,
            position: {
              x: fromCoords.x + (toCoords.x - fromCoords.x) * localProgress,
              y: fromCoords.y + (toCoords.y - fromCoords.y) * localProgress,
            },
            progress: localProgress,
            riskLevel: 'safe',
            probability: Math.random() * 0.3,
            conflictType: null,
            incidentType: null,
            location: currentStop.station_name,
            factors: [],
          };
        });

        setTrains(initialTrains);
      })
      .catch((err) => {
        console.error('Error loading simulation data:', err);
      });
  }, []);

  // Update trains from predictions
  useEffect(() => {
    if (!predictions || trains.length === 0) return;

    setTrains((prev) =>
      prev.map((train) => {
        const prediction = predictions.predictions.find((p) => p.train_id === train.id);
        if (prediction) {
          return {
            ...train,
            riskLevel: prediction.risk_level as RiskLevel,
            probability: prediction.probability,
            conflictType: prediction.predicted_conflict_type,
            location: prediction.predicted_location,
            factors: prediction.contributing_factors,
          };
        }
        return train;
      })
    );

    // Update station risk levels based on predictions
    setStations((prev) => {
      const newMap = new Map(prev);
      
      // Reset all stations
      newMap.forEach((station) => {
        station.riskLevel = 'safe';
        station.maxRiskProbability = 0;
        station.trainsCount = 0;
      });

      // Update based on predictions
      predictions.predictions.forEach((p) => {
        if (p.predicted_location) {
          const station = newMap.get(p.predicted_location);
          if (station) {
            station.trainsCount++;
            if (p.probability > station.maxRiskProbability) {
              station.maxRiskProbability = p.probability;
              station.riskLevel = p.risk_level as RiskLevel;
            }
          }
        }
      });

      return newMap;
    });
  }, [predictions, trains.length]);

  // Animate trains - improved smooth movement along routes
  useEffect(() => {
    const interval = setInterval(() => {
      setSimulationTime((t) => t + 1);
      setTrains((prev) =>
        prev.map((train) => {
          // Calculate new progress
          const newProgress = train.progress + 0.005; // Slower, smoother movement
          
          if (newProgress >= 1) {
            // Train arrived at next station - move to next segment
            const currentStationIdx = Array.from(stations.keys()).indexOf(train.currentStation);
            const nextStationIdx = Array.from(stations.keys()).indexOf(train.nextStation || '');
            
            // For now, loop back
            return {
              ...train,
              progress: 0,
            };
          }
          
          // Interpolate position between current and next station
          const currentStation = stations.get(train.currentStation);
          const nextStation = stations.get(train.nextStation || '');
          
          if (currentStation && nextStation) {
            return {
              ...train,
              progress: newProgress,
              position: {
                x: currentStation.x + (nextStation.x - currentStation.x) * newProgress,
                y: currentStation.y + (nextStation.y - currentStation.y) * newProgress,
              },
            };
          }
          
          return {
            ...train,
            progress: newProgress,
          };
        })
      );
    }, 100); // Update every 100ms for smoother animation

    return () => clearInterval(interval);
  }, [stations]);

  // Pan/zoom handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.max(0.5, Math.min(4, z * delta)));
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Stats
  const stats = useMemo(() => {
    const critical = trains.filter((t) => t.riskLevel === 'critical').length;
    const highRisk = trains.filter((t) => t.riskLevel === 'high_risk').length;
    const lowRisk = trains.filter((t) => t.riskLevel === 'low_risk').length;
    const safe = trains.filter((t) => t.riskLevel === 'safe').length;
    return { critical, highRisk, lowRisk, safe, total: trains.length };
  }, [trains]);

  return (
    <div className="relative w-full h-full bg-slate-900 overflow-hidden rounded-lg border border-slate-700">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-20 bg-gradient-to-b from-slate-900 to-transparent p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Lombardy Rail Network</h2>
            
          </div>
          <div className="flex gap-2">
            {/* Stats badges */}
            {stats.critical > 0 && (
              <span className="flex items-center gap-1 bg-red-500/20 text-red-500 px-2 py-1 rounded-full text-xs font-semibold">
                <AlertTriangle className="w-3 h-3" />
                {stats.critical} Critical
              </span>
            )}
            {stats.highRisk > 0 && (
              <span className="bg-orange-500/20 text-orange-500 px-2 py-1 rounded-full text-xs font-semibold">
                {stats.highRisk} High Risk
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="absolute top-20 left-4 z-20 bg-slate-800/95 p-3 rounded-lg border border-slate-600 backdrop-blur">
        <h4 className="text-xs font-semibold text-slate-300 mb-2 uppercase tracking-wide">Risk Levels</h4>
        <div className="space-y-1.5">
          {(Object.entries(RISK_COLORS) as [RiskLevel, string][]).map(([level, color]) => (
            <div key={level} className="flex items-center gap-2 text-xs">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-slate-300 capitalize">{level.replace('_', ' ')}</span>
              <span className="text-slate-500 ml-auto">
                {level === 'safe' && `${stats.safe}`}
                {level === 'low_risk' && `${stats.lowRisk}`}
                {level === 'high_risk' && `${stats.highRisk}`}
                {level === 'critical' && `${stats.critical}`}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-3 pt-2 border-t border-slate-600">
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded-full border-2 border-white bg-transparent" />
            <span className="text-slate-300">Hub Station</span>
          </div>
        </div>
      </div>

      {/* Network Risk Score */}
      {predictions && (
        <div className="absolute top-20 right-4 z-20 bg-slate-800/95 p-3 rounded-lg border border-slate-600 backdrop-blur">
          <h4 className="text-xs font-semibold text-slate-400 mb-1">Network Risk</h4>
          <div className="flex items-end gap-2">
            <span
              className="text-3xl font-bold"
              style={{
                color:
                  predictions.network_risk_score > 0.6
                    ? RISK_COLORS.critical
                    : predictions.network_risk_score > 0.4
                    ? RISK_COLORS.high_risk
                    : predictions.network_risk_score > 0.2
                    ? RISK_COLORS.low_risk
                    : RISK_COLORS.safe,
              }}
            >
              {(predictions.network_risk_score * 100).toFixed(0)}%
            </span>
          </div>
          <div className="mt-2 h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full transition-all duration-500"
              style={{
                width: `${predictions.network_risk_score * 100}%`,
                backgroundColor:
                  predictions.network_risk_score > 0.6
                    ? RISK_COLORS.critical
                    : predictions.network_risk_score > 0.4
                    ? RISK_COLORS.high_risk
                    : predictions.network_risk_score > 0.2
                    ? RISK_COLORS.low_risk
                    : RISK_COLORS.safe,
              }}
            />
          </div>
        </div>
      )}

      {/* Zoom Controls */}
      <div className="absolute bottom-20 right-4 z-20 flex flex-col gap-1">
        <button
          onClick={() => setZoom((z) => Math.min(z * 1.3, 4))}
          className="p-2 bg-slate-800/90 hover:bg-slate-700 border border-slate-600 rounded text-white transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(z / 1.3, 0.5))}
          className="p-2 bg-slate-800/90 hover:bg-slate-700 border border-slate-600 rounded text-white transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={resetView}
          className="p-2 bg-slate-800/90 hover:bg-slate-700 border border-slate-600 rounded text-white transition-colors"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* SVG Map */}
      <div
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          className="w-full h-full"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.15s ease-out',
          }}
        >
          {/* Background grid */}
          <defs>
            <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
              <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#334155" strokeWidth="0.5" opacity="0.3" />
            </pattern>
          </defs>
          <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="url(#grid)" />

          {/* Region label */}
          <text x={SVG_WIDTH / 2} y={40} textAnchor="middle" fill="#64748b" fontSize="14" fontWeight="500">
            LOMBARDIA
          </text>

          {/* Track connections */}
          <g>
            {connections.map((conn, i) => {
              const from = stations.get(conn.from);
              const to = stations.get(conn.to);
              if (!from || !to) return null;

              // Determine track color based on stations
              const maxRisk = Math.max(from.maxRiskProbability, to.maxRiskProbability);
              const trackColor =
                maxRisk > 0.8 ? '#ef444480' : maxRisk > 0.5 ? '#f9731680' : '#47556980';
              // Track width scales inversely (thinner when zoomed in for clarity)
              const trackInvScale = 1 / Math.max(0.5, zoom);

              return (
                <line
                  key={i}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={trackColor}
                  strokeWidth={2 * trackInvScale}
                />
              );
            })}
          </g>

          {/* Stations */}
          {Array.from(stations.values()).map((station) => {
            const isHovered = hoveredStation === station.name;
            // Inverse scale: elements shrink as zoom increases for better clarity
            const invScale = 1 / Math.max(0.5, zoom);
            const baseSize = station.isHub ? 8 : 5;
            const size = baseSize * invScale;
            const color = RISK_COLORS[station.riskLevel];

            return (
              <g
                key={station.name}
                className="cursor-pointer"
                onClick={() => onStationClick?.(station)}
                onMouseEnter={() => setHoveredStation(station.name)}
                onMouseLeave={() => setHoveredStation(null)}
              >
                {/* Risk glow for non-safe stations */}
                {station.riskLevel !== 'safe' && (
                  <circle
                    cx={station.x}
                    cy={station.y}
                    r={size + 6 * invScale}
                    fill="none"
                    stroke={color}
                    strokeWidth={2 * invScale}
                    opacity={0.4}
                    className="animate-pulse"
                  />
                )}

                {/* Hub indicator ring */}
                {station.isHub && (
                  <circle
                    cx={station.x}
                    cy={station.y}
                    r={size + 3 * invScale}
                    fill="none"
                    stroke="white"
                    strokeWidth={1.5 * invScale}
                    opacity={0.6}
                  />
                )}

                {/* Station dot */}
                <circle
                  cx={station.x}
                  cy={station.y}
                  r={isHovered ? size + 2 * invScale : size}
                  fill={color}
                  stroke="#1e293b"
                  strokeWidth={1 * invScale}
                  className="transition-all duration-150"
                />

                {/* Station label for hubs or hovered - with better positioning */}
                {(station.isHub || isHovered) && (
                  <g>
                    {/* Label background for readability */}
                    <rect
                      x={station.x - 50 * invScale}
                      y={station.y - size - 22 * invScale}
                      width={100 * invScale}
                      height={14 * invScale}
                      fill="#1e293b"
                      fillOpacity={0.8}
                      rx={2 * invScale}
                    />
                    <text
                      x={station.x}
                      y={station.y - size - 10 * invScale}
                      textAnchor="middle"
                      fill="white"
                      fontSize={(isHovered ? 10 : 8) * invScale}
                      fontWeight={station.isHub ? 600 : 400}
                      className="pointer-events-none"
                    >
                      {station.name.length > 20 ? station.name.substring(0, 18) + '...' : station.name}
                    </text>
                  </g>
                )}

                {/* Tooltip on hover */}
                {isHovered && (
                  <g>
                    <rect
                      x={station.x + 15}
                      y={station.y - 10}
                      width={180}
                      height={60}
                      fill="#1e293b"
                      stroke={color}
                      strokeWidth={1}
                      rx={4}
                    />
                    <text x={station.x + 25} y={station.y + 8} fill="white" fontSize={10}>
                      {station.name}
                    </text>
                    <text x={station.x + 25} y={station.y + 22} fill="#94a3b8" fontSize={9}>
                      Risk: {station.riskLevel.replace('_', ' ')} ({(station.maxRiskProbability * 100).toFixed(0)}%)
                    </text>
                    <text x={station.x + 25} y={station.y + 36} fill="#94a3b8" fontSize={9}>
                      Trains: {station.trainsCount} | {station.isHub ? 'Hub' : 'Station'}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Trains */}
          {trains.map((train) => {
            const isHovered = hoveredTrain === train.id;
            const isSelected = selectedTrainId === train.id;
            const color = RISK_COLORS[train.riskLevel];
            // Inverse scale for trains
            const trainInvScale = 1 / Math.max(0.5, zoom);

            return (
              <g
                key={train.id}
                className="cursor-pointer"
                onClick={() => onTrainClick?.(train)}
                onMouseEnter={() => setHoveredTrain(train.id)}
                onMouseLeave={() => setHoveredTrain(null)}
              >
                {/* Risk glow */}
                {train.riskLevel !== 'safe' && (
                  <circle
                    cx={train.position.x}
                    cy={train.position.y}
                    r={14 * trainInvScale}
                    fill="none"
                    stroke={color}
                    strokeWidth={2 * trainInvScale}
                    opacity={0.5}
                    className="animate-pulse"
                  />
                )}

                {/* Selection ring */}
                {isSelected && (
                  <circle
                    cx={train.position.x}
                    cy={train.position.y}
                    r={16 * trainInvScale}
                    fill="none"
                    stroke="white"
                    strokeWidth={2 * trainInvScale}
                    strokeDasharray={`${4 * trainInvScale} ${2 * trainInvScale}`}
                  />
                )}

                {/* Train icon */}
                <circle
                  cx={train.position.x}
                  cy={train.position.y}
                  r={(isHovered ? 10 : 8) * trainInvScale}
                  fill={color}
                  stroke="white"
                  strokeWidth={2}
                  style={{ filter: RISK_GLOW[train.riskLevel] }}
                  className="transition-all duration-150"
                />

                {/* Train ID label */}
                {(isHovered || isSelected || train.riskLevel === 'critical') && (
                  <text
                    x={train.position.x}
                    y={train.position.y - 14 * trainInvScale}
                    textAnchor="middle"
                    fill="white"
                    fontSize={9 * trainInvScale}
                    fontWeight={600}
                    className="pointer-events-none"
                  >
                    {train.id}
                  </text>
                )}

                {/* Detailed tooltip */}
                {isHovered && (
                  <g>
                    <rect
                      x={train.position.x + 15}
                      y={train.position.y - 25}
                      width={200}
                      height={80}
                      fill="#1e293b"
                      stroke={color}
                      strokeWidth={2}
                      rx={6}
                    />
                    <text
                      x={train.position.x + 25}
                      y={train.position.y - 7}
                      fill="white"
                      fontSize={11}
                      fontWeight={600}
                    >
                      {train.id} ({train.type})
                    </text>
                    <text x={train.position.x + 25} y={train.position.y + 10} fill="#94a3b8" fontSize={9}>
                      Risk: {(train.probability * 100).toFixed(0)}% - {train.riskLevel.replace('_', ' ')}
                    </text>
                    <text x={train.position.x + 25} y={train.position.y + 24} fill="#94a3b8" fontSize={9}>
                      Location: {train.location || train.currentStation}
                    </text>
                    {train.conflictType && (
                      <text x={train.position.x + 25} y={train.position.y + 38} fill="#fbbf24" fontSize={9}>
                        ⚠️ {train.conflictType.replace('_', ' ')}
                      </text>
                    )}
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Info Bar */}
      <div className="absolute bottom-4 left-4 right-20 z-20 flex items-center justify-between text-xs text-slate-400 bg-slate-800/90 px-3 py-2 rounded border border-slate-600">
        <span>
          <TrainIcon className="w-3 h-3 inline mr-1" />
          {trains.length} trains • {stations.size} stations • Zoom: {zoom.toFixed(1)}x
        </span>
        {predictions && (
          <span>
            Last update: {new Date(predictions.timestamp).toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}

export default LombardyNetworkMap;
