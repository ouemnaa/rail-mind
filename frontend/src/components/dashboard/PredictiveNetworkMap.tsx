/**
 * Enhanced Network Map with Conflict Prediction
 * ==============================================
 *
 * Displays the rail network with trains colored by risk level:
 * 🟢 GREEN:   Safe, no predicted conflicts (prob < 0.3)
 * 🟡 YELLOW:  Minor delay, low risk (prob 0.3-0.5)
 * 🟠 ORANGE:  High risk predicted (prob 0.6-0.8)
 * 🔴 RED:     Conflict detected NOW (prob > 0.8 or actual conflict)
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { ConflictPrediction, BatchPrediction, RiskLevel } from '../../types/prediction';

interface Station {
  id: string;
  name: string;
  x: number;
  y: number;
  status: 'normal' | 'low_risk' | 'high_risk' | 'critical';
  riskLevel?: RiskLevel;
  trainsAtStation: number;
}

interface Track {
  from: string;
  to: string;
  active?: boolean;
  length?: number;
  congestion?: number;
}

interface Train {
  id: string;
  currentEdgeIndex: number;
  position: number;
  speed: number;
  route: Track[];
  status: 'moving' | 'stopped';
  // Prediction data
  riskLevel: RiskLevel;
  probability: number;
  predictedConflictType?: string;
  color: string;
}

interface PredictiveNetworkMapProps {
  predictions?: BatchPrediction | null;
  onStationClick?: (station: Station) => void;
  onTrainClick?: (train: Train) => void;
  highlightedTrains?: string[];
}

// Risk level colors
const RISK_COLORS: Record<RiskLevel, string> = {
  safe: '#22c55e',      // Green
  low_risk: '#eab308',  // Yellow
  high_risk: '#f97316', // Orange
  critical: '#ef4444',  // Red
};

const RISK_GLOW: Record<RiskLevel, string> = {
  safe: 'drop-shadow(0 0 3px #22c55e)',
  low_risk: 'drop-shadow(0 0 5px #eab308)',
  high_risk: 'drop-shadow(0 0 8px #f97316)',
  critical: 'drop-shadow(0 0 12px #ef4444)',
};

export function PredictiveNetworkMap({
  predictions,
  onStationClick,
  onTrainClick,
  highlightedTrains = [],
}: PredictiveNetworkMapProps) {
  const [stations, setStations] = useState<Station[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [trains, setTrains] = useState<Train[]>([]);
  const [hoveredStation, setHoveredStation] = useState<string | null>(null);
  const [hoveredTrain, setHoveredTrain] = useState<string | null>(null);
  const [selectedTrain, setSelectedTrain] = useState<Train | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  // Load network data
  useEffect(() => {
    fetch('/network.json')
      .then((res) => res.json())
      .then((data) => {
        const minLat = Math.min(...data.nodes.map((n: any) => n.lat));
        const maxLat = Math.max(...data.nodes.map((n: any) => n.lat));
        const minLon = Math.min(...data.nodes.map((n: any) => n.lon));
        const maxLon = Math.max(...data.nodes.map((n: any) => n.lon));

        const svgWidth = 2400;
        const svgHeight = 1600;
        const padding = 100;

        const nodes: Station[] = data.nodes.map((node: any) => ({
          id: node.id,
          name: node.name,
          x:
            padding +
            ((node.lon - minLon) / (maxLon - minLon)) * (svgWidth - 2 * padding),
          y:
            svgHeight -
            padding -
            ((node.lat - minLat) / (maxLat - minLat)) * (svgHeight - 2 * padding),
          status: 'normal',
          trainsAtStation: 0,
        }));

        const edges: Track[] = data.edges.map((edge: any) => {
          const fromNode = nodes.find((n) => n.id === edge.source)!;
          const toNode = nodes.find((n) => n.id === edge.target)!;
          const length = Math.hypot(toNode.x - fromNode.x, toNode.y - fromNode.y);
          return {
            from: edge.source,
            to: edge.target,
            active: edge.current_load > 0,
            length,
            congestion: 0,
          };
        });

        setStations(nodes);
        setTracks(edges);

        // Initialize trains with default safe status
        const sampleTrains: Train[] = Array.from({ length: 15 }).map((_, i) => {
          const edge = edges[Math.floor(Math.random() * edges.length)];
          return {
            id: `TR-${1000 + i}`,
            currentEdgeIndex: edges.indexOf(edge),
            position: Math.random(),
            speed: 20 + Math.random() * 40,
            route: edges,
            status: 'moving',
            riskLevel: 'safe',
            probability: Math.random() * 0.3,
            color: RISK_COLORS.safe,
          };
        });

        setTrains(sampleTrains);
      });
  }, []);

  // Update train colors based on predictions
  useEffect(() => {
    if (!predictions) return;

    setTrains((prevTrains) =>
      prevTrains.map((train) => {
        const prediction = predictions.predictions.find(
          (p) => p.train_id === train.id
        );

        if (prediction) {
          return {
            ...train,
            riskLevel: prediction.risk_level as RiskLevel,
            probability: prediction.probability,
            predictedConflictType: prediction.predicted_conflict_type || undefined,
            color: RISK_COLORS[prediction.risk_level as RiskLevel],
          };
        }
        return train;
      })
    );

    // Update station colors based on trains heading there
    setStations((prevStations) =>
      prevStations.map((station) => {
        const trainsAtStation = predictions.predictions.filter(
          (p) => p.predicted_location === station.id
        );
        
        const maxRisk = trainsAtStation.reduce((max, p) => {
          const riskOrder = { safe: 0, low_risk: 1, high_risk: 2, critical: 3 };
          return riskOrder[p.risk_level as RiskLevel] > riskOrder[max]
            ? (p.risk_level as RiskLevel)
            : max;
        }, 'normal' as Station['status']);

        return {
          ...station,
          status: maxRisk as Station['status'],
          riskLevel: maxRisk === 'normal' ? 'safe' : (maxRisk as RiskLevel),
          trainsAtStation: trainsAtStation.length,
        };
      })
    );
  }, [predictions]);

  const getStationById = useCallback(
    (id: string) => stations.find((s) => s.id === id),
    [stations]
  );

  // Train animation
  useEffect(() => {
    const interval = setInterval(() => {
      setTrains((prevTrains) =>
        prevTrains.map((train) => {
          if (train.status === 'stopped') return train;

          const edge = train.route[train.currentEdgeIndex];
          if (!edge) return train;

          const distancePerTick = train.speed / 60 / (edge.length || 100);
          let newPos = train.position + distancePerTick;
          let nextEdgeIndex = train.currentEdgeIndex;

          if (newPos >= 1) {
            nextEdgeIndex = (nextEdgeIndex + 1) % train.route.length;
            newPos = 0;
          }

          return {
            ...train,
            position: newPos,
            currentEdgeIndex: nextEdgeIndex,
          };
        })
      );
    }, 1000 / 30);

    return () => clearInterval(interval);
  }, []);

  // Pan & zoom handlers
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

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleTrainClick = (train: Train) => {
    setSelectedTrain(train);
    onTrainClick?.(train);
  };

  // Get station color based on risk
  const getStationColor = (station: Station) => {
    if (station.riskLevel) {
      return RISK_COLORS[station.riskLevel];
    }
    return '#10b981'; // Default green
  };

  // Get node size based on risk
  const getNodeSize = (station: Station) => {
    if (station.status === 'critical') return 8;
    if (station.status === 'high_risk') return 7;
    return 5;
  };

  return (
    <div className="relative w-full h-full bg-slate-900 overflow-hidden rounded-lg border border-slate-700">
      {/* Legend */}
      <div className="absolute top-4 left-4 z-20 bg-slate-800/90 p-3 rounded-lg border border-slate-600">
        <h4 className="text-xs font-semibold text-slate-300 mb-2">Risk Level</h4>
        <div className="space-y-1">
          {Object.entries(RISK_COLORS).map(([level, color]) => (
            <div key={level} className="flex items-center gap-2 text-xs">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-slate-300 capitalize">
                {level.replace('_', ' ')}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Network Stats */}
      {predictions && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-20 flex gap-4">
          <div className="bg-slate-800/90 px-3 py-2 rounded-lg border border-slate-600">
            <span className="text-xs text-slate-400">Network Risk</span>
            <p className="text-lg font-bold" style={{
              color: predictions.network_risk_score > 0.5 
                ? RISK_COLORS.critical 
                : predictions.network_risk_score > 0.3 
                  ? RISK_COLORS.high_risk 
                  : RISK_COLORS.safe
            }}>
              {(predictions.network_risk_score * 100).toFixed(0)}%
            </p>
          </div>
          <div className="bg-slate-800/90 px-3 py-2 rounded-lg border border-slate-600">
            <span className="text-xs text-slate-400">Critical</span>
            <p className="text-lg font-bold text-red-500">
              {predictions.critical_trains.length}
            </p>
          </div>
          <div className="bg-slate-800/90 px-3 py-2 rounded-lg border border-slate-600">
            <span className="text-xs text-slate-400">High Risk</span>
            <p className="text-lg font-bold text-orange-500">
              {predictions.high_risk_trains.length}
            </p>
          </div>
        </div>
      )}

      {/* Zoom Controls */}
      <div className="absolute top-4 right-4 z-20 flex flex-col gap-2">
        <button
          onClick={() => setZoom(Math.min(zoom * 1.2, 5))}
          className="px-3 py-2 bg-slate-800/90 hover:bg-slate-700 border border-slate-600 rounded text-sm font-medium text-white"
        >
          +
        </button>
        <button
          onClick={() => setZoom(Math.max(zoom / 1.2, 0.1))}
          className="px-3 py-2 bg-slate-800/90 hover:bg-slate-700 border border-slate-600 rounded text-sm font-medium text-white"
        >
          −
        </button>
        <button
          onClick={resetView}
          className="px-3 py-2 bg-slate-800/90 hover:bg-slate-700 border border-slate-600 rounded text-xs font-medium text-white"
        >
          Reset
        </button>
      </div>

      {/* SVG Network */}
      <div
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <svg
          ref={svgRef}
          viewBox="0 0 2400 1600"
          className="w-full h-full"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.1s ease-out',
          }}
        >
          {/* Tracks */}
          <g>
            {tracks.map((track, i) => {
              const from = getStationById(track.from);
              const to = getStationById(track.to);
              if (!from || !to) return null;

              return (
                <line
                  key={i}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={track.active ? '#60a5fa' : '#475569'}
                  strokeWidth={track.active ? 3 : 2}
                  opacity={track.active ? 0.8 : 0.3}
                />
              );
            })}
          </g>

          {/* Stations */}
          {stations.map((station) => {
            const isHovered = hoveredStation === station.id;
            const color = getStationColor(station);
            const size = getNodeSize(station);

            return (
              <g
                key={station.id}
                className="cursor-pointer"
                onClick={() => onStationClick?.(station)}
                onMouseEnter={() => setHoveredStation(station.id)}
                onMouseLeave={() => setHoveredStation(null)}
              >
                {/* Glow effect for high-risk stations */}
                {station.status !== 'normal' && (
                  <circle
                    cx={station.x}
                    cy={station.y}
                    r={size + 4}
                    fill="none"
                    stroke={color}
                    strokeWidth={2}
                    opacity={0.3}
                    className="animate-pulse"
                  />
                )}

                <circle
                  cx={station.x}
                  cy={station.y}
                  r={isHovered ? size + 2 : size}
                  fill={color}
                  className="transition-all duration-200"
                />

                {/* Station label on hover */}
                {isHovered && (
                  <g>
                    <rect
                      x={station.x + 10}
                      y={station.y - 25}
                      width={station.name.length * 7 + 20}
                      height={30}
                      fill="#1e293b"
                      stroke="#475569"
                      rx={4}
                    />
                    <text
                      x={station.x + 20}
                      y={station.y - 5}
                      fill="white"
                      fontSize={12}
                    >
                      {station.name}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Trains */}
          {trains.map((train) => {
            const edge = train.route[train.currentEdgeIndex];
            if (!edge) return null;

            const from = getStationById(edge.from);
            const to = getStationById(edge.to);
            if (!from || !to) return null;

            const x = from.x + (to.x - from.x) * train.position;
            const y = from.y + (to.y - from.y) * train.position;
            const isHighlighted = highlightedTrains.includes(train.id);
            const isHovered = hoveredTrain === train.id;
            const isSelected = selectedTrain?.id === train.id;

            return (
              <g
                key={train.id}
                className="cursor-pointer"
                onClick={() => handleTrainClick(train)}
                onMouseEnter={() => setHoveredTrain(train.id)}
                onMouseLeave={() => setHoveredTrain(null)}
              >
                {/* Glow effect for non-safe trains */}
                {train.riskLevel !== 'safe' && (
                  <circle
                    cx={x}
                    cy={y}
                    r={12}
                    fill="none"
                    stroke={train.color}
                    strokeWidth={2}
                    opacity={0.4}
                    className="animate-pulse"
                  />
                )}

                {/* Selection ring */}
                {(isSelected || isHighlighted) && (
                  <circle
                    cx={x}
                    cy={y}
                    r={14}
                    fill="none"
                    stroke="white"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                  />
                )}

                {/* Train dot */}
                <circle
                  cx={x}
                  cy={y}
                  r={isHovered ? 9 : 7}
                  fill={train.color}
                  stroke="#fff"
                  strokeWidth={2}
                  style={{
                    filter: train.riskLevel !== 'safe' ? RISK_GLOW[train.riskLevel] : 'none',
                  }}
                  className="transition-all duration-200"
                />

                {/* Train info tooltip */}
                {(isHovered || isSelected) && (
                  <g>
                    <rect
                      x={x + 15}
                      y={y - 40}
                      width={160}
                      height={50}
                      fill="#1e293b"
                      stroke={train.color}
                      strokeWidth={2}
                      rx={6}
                    />
                    <text x={x + 25} y={y - 20} fill="white" fontSize={12} fontWeight="bold">
                      {train.id}
                    </text>
                    <text x={x + 25} y={y - 4} fill="#94a3b8" fontSize={10}>
                      Risk: {Math.round(train.probability * 100)}% ({train.riskLevel.replace('_', ' ')})
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Info Bar */}
      <div className="absolute bottom-4 left-4 z-20 text-xs text-slate-300 bg-slate-800/90 px-3 py-2 rounded border border-slate-600">
        Zoom: {zoom.toFixed(1)}x | Stations: {stations.length} | Tracks:{' '}
        {tracks.length} | Trains: {trains.length}
      </div>
    </div>
  );
}

export default PredictiveNetworkMap;
