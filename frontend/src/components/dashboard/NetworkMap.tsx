import { useState, useEffect, useRef } from 'react';

interface Station {
  id: string;
  name: string;
  x: number;
  y: number;
  status: 'normal' | 'delayed' | 'conflict';
}

interface Track {
  from: string;
  to: string;
  active?: boolean;
  length?: number;
}

interface Train {
  id: string;
  currentEdgeIndex: number;
  position: number; // 0-1 along edge
  speed: number; // km/h
  route: Track[]; // precomputed path along tracks
  color: string;
  status: 'moving' | 'stopped';
  crowd: number; // sensor data 0-100
}

interface NetworkMapProps {
  onStationClick?: (station: Station) => void;
}

export function NetworkMap({ onStationClick }: NetworkMapProps) {
  const [stations, setStations] = useState<Station[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [trains, setTrains] = useState<Train[]>([]);
  const [hoveredStation, setHoveredStation] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  // Load network
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
          };
        });

        setStations(nodes);
        setTracks(edges);

        // Initialize trains on random edges
        const sampleTrains: Train[] = Array.from({ length: 5 }).map((_, i) => {
          const edge = edges[Math.floor(Math.random() * edges.length)];
          return {
            id: `TR-${1000 + i}`,
            currentEdgeIndex: edges.indexOf(edge),
            position: 0,
            speed: 20 + Math.random() * 40, // 20-60 km/h
            route: edges, // simple: can improve with pathfinding
            color: `hsl(${Math.random() * 360}, 70%, 50%)`,
            status: 'moving',
            crowd: Math.floor(Math.random() * 100),
          };
        });

        setTrains(sampleTrains);
      });
  }, []);

  const getStationById = (id: string) => stations.find((s) => s.id === id);

  // Train simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setTrains((prevTrains) =>
        prevTrains.map((train) => {
          const edge = train.route[train.currentEdgeIndex];
          if (!edge) return train;

          const from = getStationById(edge.from)!;
          const to = getStationById(edge.to)!;

          // Simple speed-to-position conversion
          const distancePerTick = (train.speed / 60) / edge.length!;
          let newPos = train.position + distancePerTick;
          let nextEdgeIndex = train.currentEdgeIndex;

          if (newPos >= 1) {
            nextEdgeIndex += 1;
            newPos = 0;
            if (nextEdgeIndex >= train.route.length) {
              return { ...train, position: 1, status: 'stopped' };
            }
          }

          // Sensors simulation
          const newCrowd = Math.min(100, train.crowd + (Math.random() * 2 - 1));
          if (newCrowd > 80) {
            console.log(`Sensor Alert! Train ${train.id} crowded: ${newCrowd.toFixed(0)}%`);
          }

          return {
            ...train,
            position: newPos,
            currentEdgeIndex: nextEdgeIndex,
            crowd: newCrowd,
          };
        })
      );
    }, 1000 / 30); // 30 FPS
    return () => clearInterval(interval);
  }, [tracks]);

  // Pan & zoom handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };
  const handleMouseUp = () => setIsDragging(false);
  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const nodeSize = 5;

  return (
    <div className="relative w-full h-full bg-slate-900 overflow-hidden rounded-lg border border-slate-700">
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

      {/* SVG */}
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
          <g opacity={1}>
            {tracks.map((track, i) => {
              const from = getStationById(track.from)!;
              const to = getStationById(track.to)!;
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
          {stations.map((station) => (
            <g
              key={station.id}
              className="cursor-pointer"
              onClick={() => onStationClick?.(station)}
              onMouseEnter={() => setHoveredStation(station.id)}
              onMouseLeave={() => setHoveredStation(null)}
            >
              <circle
                cx={station.x}
                cy={station.y}
                r={nodeSize}
                fill={
                  station.status === 'delayed'
                    ? '#fbbf24'
                    : station.status === 'conflict'
                    ? '#ef4444'
                    : '#10b981'
                }
                className="transition-all duration-200"
              />
            </g>
          ))}

          {/* Trains */}
          {trains.map((train) => {
            const edge = train.route[train.currentEdgeIndex];
            if (!edge) return null;
            const from = getStationById(edge.from)!;
            const to = getStationById(edge.to)!;
            const x = from.x + (to.x - from.x) * train.position;
            const y = from.y + (to.y - from.y) * train.position;

            return (
              <circle
                key={train.id}
                cx={x}
                cy={y}
                r={6}
                fill={train.color}
                stroke="#fff"
                strokeWidth={1}
              />
            );
          })}
        </svg>
      </div>

      {/* Info */}
      <div className="absolute bottom-4 left-4 z-20 text-xs text-slate-300 bg-slate-800/90 px-3 py-2 rounded border border-slate-600">
        Zoom: {zoom.toFixed(1)}x | Stations: {stations.length} | Tracks: {tracks.length} | Trains: {trains.length}
      </div>
    </div>
  );
}

export default NetworkMap;
