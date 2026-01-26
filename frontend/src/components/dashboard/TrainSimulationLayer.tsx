import { useEffect, useMemo, useState } from "react";

interface RouteStop {
  station_name: string;
  station_order: number;
  distance_from_previous_km: number;
  lat: number;
  lon: number;
}

interface Station {
  id: string;
  name: string;
  x: number;
  y: number;
  region?: string;
  status?: "normal" | "delayed" | "conflict";
}

export interface Train {
  id: string;
  route: RouteStop[];
  segmentIndex: number; // current segment
  progress: number; // 0 → 1 on segment
  speedKmh: number;
  color: string;
}

interface Props {
  stations: Station[];
  zoom: number;
  onTrainClick?: (train: Train) => void; // <- pass handler from parent
}

export function TrainSimulationLayer({ stations, zoom, onTrainClick }: Props) {
  const [trains, setTrains] = useState<Train[]>([]);

  const stationByName = useMemo(() => {
    return new Map(
      stations.map((s) => [s.name.trim().toUpperCase(), s])
    );
  }, [stations]);

  useEffect(() => {
    fetch("/trains.json")
      .then((res) => res.json())
      .then((data) => {
        const mapped: Train[] = data.trains.map((t: any, i: number) => ({
          id: t.train_id,
          route: t.route.sort(
            (a: RouteStop, b: RouteStop) => a.station_order - b.station_order
          ),
          segmentIndex: 1,
          progress: 0,
          speedKmh: 120,
          color: ["#22c55e", "#60a5fa", "#f59e0b"][i % 3],
        }));
        setTrains(mapped);
      });
  }, []);

  useEffect(() => {
    let frame: number;
    const lastTime = { t: performance.now() };

    const animate = (now: number) => {
      const deltaSec = (now - lastTime.t) / 1000;
      lastTime.t = now;

      setTrains((prev) =>
        prev.map((train) => {
          const segment = train.route[train.segmentIndex];
          if (!segment) return train;

          const segmentDistance = segment.distance_from_previous_km || 0.001;
          const distancePerSec = train.speedKmh / 3600;

          let progress =
            train.progress + (distancePerSec * deltaSec) / segmentDistance;

          let segmentIndex = train.segmentIndex;

          if (progress >= 1) {
            progress = 0;
            segmentIndex++;
            if (segmentIndex >= train.route.length) segmentIndex = 1;
          }

          return { ...train, progress, segmentIndex };
        })
      );

      frame = requestAnimationFrame(animate);
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <>
      {trains.map((train) => {
        const prev = train.route[train.segmentIndex - 1];
        const next = train.route[train.segmentIndex];
        if (!prev || !next) return null;

        const a = stationByName.get(prev.station_name.trim().toUpperCase());
        const b = stationByName.get(next.station_name.trim().toUpperCase());
        if (!a || !b) return null;

        const x = a.x + (b.x - a.x) * train.progress;
        const y = a.y + (b.y - a.y) * train.progress;

        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const angle = (Math.atan2(dy, dx) * 180) / Math.PI;

        return (
          <g
            key={train.id}
            transform={`translate(${x},${y}) rotate(${angle})`}
            onClick={() => onTrainClick?.(train)} // <- trigger parent handler
            style={{ cursor: "pointer" }}
          >
            <svg
              width={30 / zoom}
              height={12 / zoom}
              viewBox="0 0 100 40"
              fill={train.color}
              stroke="#333"
              strokeWidth={1.5}
            >
              <rect x="0" y="5" width="100" height="30" rx="8" ry="8" />
              <rect x="10" y="10" width="15" height="10" fill="#fff" rx="2" />
              <rect x="30" y="10" width="15" height="10" fill="#fff" rx="2" />
              <rect x="50" y="10" width="15" height="10" fill="#fff" rx="2" />
              <rect x="70" y="10" width="15" height="10" fill="#fff" rx="2" />
              <circle cx="20" cy="35" r="5" fill="#333" />
              <circle cx="80" cy="35" r="5" fill="#333" />
            </svg>
          </g>
        );
      })}
    </>
  );
}
