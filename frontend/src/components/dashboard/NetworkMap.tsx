import { useState, useEffect, useRef } from "react";
import { Plus, Minus, Maximize2 } from "lucide-react";
import { TrainSimulationLayer } from "./TrainSimulationLayer";

interface Station {
  id: string;
  name: string;
  x: number;
  y: number;
  region: string;
  status: "normal" | "delayed" | "conflict";
}

interface Track {
  from: string;
  to: string;
  active?: boolean;
}

interface NetworkMapProps {
  onStationClick?: (station: Station) => void;
}

export function NetworkMap({ onStationClick }: NetworkMapProps) {
  const [stations, setStations] = useState<Station[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [regions, setRegions] = useState<
    Record<string, { minX: number; minY: number; maxX: number; maxY: number }>
  >({});

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const SVG_WIDTH = 2400;
  const SVG_HEIGHT = 1600;

  /* ============================ LOAD DATA ============================ */
  useEffect(() => {
    fetch("/network.json")
      .then((res) => res.json())
      .then((data) => {
        const minLat = Math.min(...data.nodes.map((n: any) => n.lat));
        const maxLat = Math.max(...data.nodes.map((n: any) => n.lat));
        const minLon = Math.min(...data.nodes.map((n: any) => n.lon));
        const maxLon = Math.max(...data.nodes.map((n: any) => n.lon));

        const P = 100;

        const nodes: Station[] = data.nodes.map((n: any) => ({
          id: n.id,
          name: n.name,
          region: n.region,
          x: P + ((n.lon - minLon) / (maxLon - minLon)) * (SVG_WIDTH - P * 2),
          y:
            SVG_HEIGHT -
            P -
            ((n.lat - minLat) / (maxLat - minLat)) *
              (SVG_HEIGHT - P * 2),
          status: "normal",
        }));

        const edges: Track[] = data.edges.map((e: any) => ({
          from: e.source,
          to: e.target,
          active: e.current_load > 0,
        }));

        const regionMap: any = {};
        nodes.forEach((n) => {
          regionMap[n.region] ??= {
            minX: n.x,
            minY: n.y,
            maxX: n.x,
            maxY: n.y,
          };
          regionMap[n.region].minX = Math.min(regionMap[n.region].minX, n.x);
          regionMap[n.region].minY = Math.min(regionMap[n.region].minY, n.y);
          regionMap[n.region].maxX = Math.max(regionMap[n.region].maxX, n.x);
          regionMap[n.region].maxY = Math.max(regionMap[n.region].maxY, n.y);
        });

        setStations(nodes);
        setTracks(edges);
        setRegions(regionMap);
      });
  }, []);

  /* ============================ CAMERA ============================ */
  const zoomToRegion = (regionName: string, padding = 80) => {
    const region = regions[regionName];
    const container = containerRef.current;
    if (!region || !container) return;

    setSelectedRegion(regionName);

    const rect = container.getBoundingClientRect();
    const scale = Math.min(
      rect.width / (region.maxX - region.minX + padding * 2),
      rect.height / (region.maxY - region.minY + padding * 2)
    );

    const cx = (region.minX + region.maxX) / 2;
    const cy = (region.minY + region.maxY) / 2;

    setZoom(scale);
    setPan({
      x: rect.width / 2 - cx * scale,
      y: rect.height / 2 - cy * scale,
    });
  };

  const resetView = () => {
    setSelectedRegion(null);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleZoomIn = () => setZoom((z) => Math.min(z * 1.3, 8));
  const handleZoomOut = () => setZoom((z) => Math.max(z / 1.3, 0.3));

  /* ============================ DRAG ============================ */
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };

  const handleMouseUp = () => setIsDragging(false);

  /* ============================ FILTER BY REGION ============================ */
  const visibleStations = selectedRegion
    ? stations.filter((s) => s.region === selectedRegion)
    : stations;

  const visibleTracks = tracks.filter((t) => {
    const a = stations.find((s) => s.id === t.from);
    const b = stations.find((s) => s.id === t.to);
    if (!a || !b) return false;
    if (!selectedRegion) return true;
    return a.region === selectedRegion && b.region === selectedRegion;
  });

  /* ============================ RENDER ============================ */
  return (
    <div className="relative w-full h-full bg-slate-900 overflow-hidden rounded-lg border border-slate-700">

      {/* REGION SELECTOR */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap gap-2 max-w-md">
        {Object.keys(regions).map((r) => (
          <button
            key={r}
            onClick={() => zoomToRegion(r)}
            className={`px-3 py-1 rounded text-xs border ${
              selectedRegion === r
                ? "bg-blue-600 border-blue-500 text-white"
                : "bg-slate-800 border-slate-600 text-white"
            }`}
          >
            {r}
          </button>
        ))}
        {selectedRegion && (
          <button
            onClick={resetView}
            className="px-3 py-1 rounded text-xs bg-red-600 text-white"
          >
            Reset
          </button>
        )}
      </div>

      {/* CONTROLS */}
      <div className="absolute top-4 right-4 z-20 flex flex-col gap-2">
        <button onClick={handleZoomIn} className="p-2 bg-slate-800 border border-slate-600 rounded text-white">
          <Plus size={20} />
        </button>
        <button onClick={handleZoomOut} className="p-2 bg-slate-800 border border-slate-600 rounded text-white">
          <Minus size={20} />
        </button>
        <button onClick={resetView} className="p-2 bg-slate-800 border border-slate-600 rounded text-white">
          <Maximize2 size={20} />
        </button>
      </div>

      {/* SVG */}
      <div
        ref={containerRef}
        className="w-full h-full cursor-grab"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <svg ref={svgRef} viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`} className="w-full h-full">
          <g
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: "0 0",
            }}
          >
            {/* TRACKS */}
            {visibleTracks.map((t, i) => {
              const a = visibleStations.find((s) => s.id === t.from)!;
              const b = visibleStations.find((s) => s.id === t.to)!;
              return (
                <line
                  key={i}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={t.active ? "#60a5fa" : "#475569"}
                  strokeWidth={3}
                />
              );
            })}

            {/* STATIONS */}
            {visibleStations.map((s) => (
              <circle
                key={s.id}
                cx={s.x}
                cy={s.y}
                r={6 / zoom}
                fill="#10b981"
                stroke="#fff"
                strokeWidth={1.5 / zoom}
                onClick={() => onStationClick?.(s)}
              />
            ))}

            {/* 🚆 TRAINS (AUTO FILTERED BY REGION) */}
            <TrainSimulationLayer stations={visibleStations} zoom={zoom} />
          </g>
        </svg>
      </div>
    </div>
  );
}

export default NetworkMap;
