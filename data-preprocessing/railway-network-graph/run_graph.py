"""
Run Rail Network Graph Builder
==============================
Standalone script to build and test the rail network graph.

Usage:
    python rail_network/run_graph.py
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import networkx as nx
from datetime import datetime, timedelta
from collections import defaultdict
import json
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
PROCESSED_DIR = DATA_DIR / "Processed"
OUTPUT_DIR = Path(__file__).parent / "output"

STATION_DATA = PROCESSED_DIR / "station_data_enriched.csv"
MILEAGE_DATA = PROCESSED_DIR / "mileage_data_enriched.csv"
FAULT_DATA = PROCESSED_DIR / "fault_data_enriched.csv"

GRAPH_CONFIG = {
    'edge_types': {
        'high_speed': {'max_speed': 300, 'capacity': 12},
        'conventional': {'max_speed': 160, 'capacity': 8},
        'regional': {'max_speed': 120, 'capacity': 6},
    },
    'conflict_thresholds': {
        'capacity_warning': 0.7,
        'capacity_critical': 0.9,
        'proximity_km': 50,
    },
    'simulation': {
        'time_step_minutes': 5,
        'max_propagation_hops': 5,
        'delay_decay_factor': 0.8,
    },
}

MAJOR_HUBS = [
    'ROMA TERMINI', 'MILANO CENTRALE', 'NAPOLI CENTRALE',
    'TORINO PORTA NUOVA', 'FIRENZE SANTA MARIA NOVELLA',
    'BOLOGNA CENTRALE', 'VENEZIA SANTA LUCIA',
    'GENOVA PIAZZA PRINCIPE', 'VERONA PORTA NUOVA', 'PALERMO CENTRALE',
]


# ============================================================================
# RAIL NETWORK GRAPH
# ============================================================================

class RailNetworkGraph:
    """Graph representation of Italian railway network."""
    
    def __init__(self):
        self.G = nx.DiGraph()
        self.stations_df = None
        self.routes_df = None
        self.incidents_df = None
        self.station_index = {}
        self.region_stations = defaultdict(list)
        self.active_incidents = []
        
    def build_from_data(self, verbose=True):
        """Build graph from data."""
        if verbose:
            print("=" * 60)
            print("BUILDING RAIL NETWORK GRAPH")
            print("=" * 60)
        
        self._load_stations(verbose)
        self._load_routes(verbose)
        self._load_incidents(verbose)
        self._compute_properties(verbose)
        
        if verbose:
            self._print_summary()
        return self
    
    def _load_stations(self, verbose):
        if verbose:
            print("\n📍 Loading stations...")
        if not STATION_DATA.exists():
            print(f"  ⚠️ Not found: {STATION_DATA}")
            return
        
        self.stations_df = pd.read_csv(STATION_DATA)
        for _, row in self.stations_df.iterrows():
            name = row.get('name_normalized', row['name'])
            if pd.isna(name):
                name = row['name']
            
            # Handle region name with proper NaN check
            region_name = row.get('region_name')
            if pd.isna(region_name):
                region_name = 'Unknown'
            
            # Estimate station capacity properties based on characteristics
            is_major = name in MAJOR_HUBS
            
            # Platform estimation: major hubs have more platforms
            if is_major:
                platforms = np.random.randint(15, 25)  # Major hubs: 15-24 platforms
                max_trains = platforms - 2  # Reserve 2 for emergencies
                max_arrivals = int(platforms * 0.4)  # 40% simultaneous arrivals
                min_dwell = 120  # 2 minutes minimum
                blocking = 'soft'
                signal = 'centralized'
                has_yard = True
                priority = True
                congestion = 'high'
                avg_delay = 180  # 3 minutes average
            else:
                # Regional/small stations
                platforms = np.random.randint(2, 8)  # 2-7 platforms
                max_trains = max(1, platforms - 1)
                max_arrivals = max(1, int(platforms * 0.5))
                min_dwell = 60  # 1 minute minimum
                blocking = 'soft' if platforms > 3 else 'hard'
                signal = 'regional' if platforms > 4 else 'local'
                has_yard = platforms > 5
                priority = False
                congestion = 'low' if platforms > 5 else 'medium'
                avg_delay = 60  # 1 minute average
            
            self.G.add_node(name, 
                node_type='station', 
                name=row['name'],
                lat=row['lat'] if pd.notna(row.get('lat')) else None,
                lon=row['lon'] if pd.notna(row.get('lon')) else None,
                region=region_name,
                incident_history=[],
                # New operational properties
                platforms=platforms,
                max_trains_at_once=max_trains,
                max_simultaneous_arrivals=max_arrivals,
                min_dwell_time_sec=min_dwell,
                blocking_behavior=blocking,
                signal_control=signal,
                has_switchyard=has_yard,
                hold_allowed=True,
                max_hold_time_sec=600,  # 10 minutes max hold
                priority_station=priority,
                priority_override_allowed=is_major,
                historical_congestion_level=congestion,
                avg_delay_sec=avg_delay
            )
            
            self.station_index[name] = name
            self.station_index[row['name']] = name
            self.region_stations[region_name].append(name)
        
        if verbose:
            print(f"  ✅ {len(self.G.nodes)} stations")
    
    def _load_routes(self, verbose):
        if verbose:
            print("\n🛤️ Loading routes...")
        if not MILEAGE_DATA.exists():
            print(f"  ⚠️ Not found: {MILEAGE_DATA}")
            return
        
        self.routes_df = pd.read_csv(MILEAGE_DATA)
        for route_id, group in self.routes_df.groupby('route_id'):
            sorted_g = group.sort_values('station_order')
            stations = sorted_g['station_name_normalized'].tolist()
            distances = sorted_g['distance'].tolist()
            train_type = sorted_g['train_type'].iloc[0] if 'train_type' in sorted_g else 'regional'
            
            edge_type = 'high_speed' if 'high' in str(train_type).lower() else (
                'conventional' if 'inter' in str(train_type).lower() else 'regional')
            cfg = GRAPH_CONFIG['edge_types'].get(edge_type, GRAPH_CONFIG['edge_types']['regional'])
            
            for i in range(len(stations) - 1):
                f, t = stations[i], stations[i + 1]
                if f not in self.G.nodes or t not in self.G.nodes:
                    continue
                d = distances[i + 1] if i + 1 < len(distances) else 0
                try:
                    d = float(d) if pd.notna(d) else 0
                except:
                    d = 0
                tt = (d / cfg['max_speed']) * 60 + 2 if d > 0 else 5
                
                if not self.G.has_edge(f, t):
                    # Estimate edge properties based on train type and distance
                    # Min headway: time between consecutive trains (safety constraint)
                    if edge_type == 'high_speed':
                        min_headway = 180  # 3 minutes for high-speed
                        max_speed = 300
                        reroutable = True
                        risk = 'medium'  # High speed = higher risk
                    elif edge_type == 'conventional':
                        min_headway = 240  # 4 minutes for intercity
                        max_speed = 160
                        reroutable = True
                        risk = 'low'
                    else:  # regional
                        min_headway = 300  # 5 minutes for regional
                        max_speed = 120
                        reroutable = False  # Regional lines often single-track
                        risk = 'low'
                    
                    # Estimate historical incidents based on distance and type
                    hist_incidents = max(0, int(d / 50) + np.random.randint(0, 3))
                    
                    self.G.add_edge(f, t, 
                        edge_type=edge_type, 
                        distance_km=d, 
                        travel_time_min=tt,
                        capacity=cfg['capacity'], 
                        current_load=0,
                        # New operational properties
                        direction='bidirectional',
                        min_headway_sec=min_headway,
                        max_speed_kmh=max_speed,
                        reroutable=reroutable,
                        priority_access=['passenger'],  # Default passenger priority
                        risk_profile=risk,
                        historical_incidents=hist_incidents
                    )
                    self.G.add_edge(t, f, 
                        edge_type=edge_type, 
                        distance_km=d, 
                        travel_time_min=tt,
                        capacity=cfg['capacity'], 
                        current_load=0,
                        # New operational properties
                        direction='bidirectional',
                        min_headway_sec=min_headway,
                        max_speed_kmh=max_speed,
                        reroutable=reroutable,
                        priority_access=['passenger'],
                        risk_profile=risk,
                        historical_incidents=hist_incidents
                    )
        
        if verbose:
            print(f"  ✅ {self.G.number_of_edges()} edges")
    
    def _load_incidents(self, verbose):
        if verbose:
            print("\n⚠️ Loading incidents...")
        if not FAULT_DATA.exists():
            print(f"  ⚠️ Not found: {FAULT_DATA}")
            return
        
        self.incidents_df = pd.read_csv(FAULT_DATA)
        linked = 0
        for idx, row in self.incidents_df.iterrows():
            inc = {'id': idx, 'date': row['date'], 'type': row.get('incident_type', 'unknown'),
                'line': row.get('line_normalized', 'Unknown'), 'station': row.get('location_station'),
                'delay_min': row.get('delay_duration_min', 0), 'severity': row.get('severity_score', 0),
                'resolution': row.get('resolution_types', '')}
            
            if pd.notna(row.get('location_station')):
                m = self._find_station(row['location_station'])
                if m:
                    self.G.nodes[m]['incident_history'].append(inc)
                    linked += 1
            self.active_incidents.append(inc)
        
        if verbose:
            print(f"  ✅ {len(self.incidents_df)} incidents ({linked} linked)")
    
    def _compute_properties(self, verbose):
        if verbose:
            print("\n🔧 Computing properties...")
        degrees = dict(self.G.degree())
        avg = np.mean(list(degrees.values())) if degrees else 0
        
        for n in self.G.nodes:
            d = degrees.get(n, 0)
            self.G.nodes[n]['degree'] = d
            self.G.nodes[n]['is_hub'] = d > avg * 2
            self.G.nodes[n]['is_major_hub'] = n in MAJOR_HUBS
        
        if verbose:
            print(f"  ✅ Avg degree: {avg:.1f}")
    
    def _find_station(self, name):
        if not name:
            return None
        u = str(name).upper().strip()
        if u in self.station_index:
            return self.station_index[u]
        for s in self.G.nodes:
            if u in s or s in u:
                return s
        return None
    
    def _print_summary(self):
        print("\n" + "=" * 60)
        print("GRAPH SUMMARY")
        print("=" * 60)
        print(f"📍 Nodes: {self.G.number_of_nodes()}")
        print(f"🛤️ Edges: {self.G.number_of_edges()}")
        print(f"📊 Regions: {len(self.region_stations)}")
        print(f"⚠️ Incidents: {len(self.active_incidents)}")
        majors = [n for n in self.G.nodes if self.G.nodes[n].get('is_major_hub')]
        print(f"🚉 Major Hubs: {len(majors)}")
    
    # === QUERIES ===
    def get_station(self, name):
        m = self._find_station(name)
        return dict(self.G.nodes[m]) if m else None
    
    def get_neighbors(self, name):
        m = self._find_station(name)
        return list(set(self.G.successors(m)) | set(self.G.predecessors(m))) if m else []
    
    def get_path(self, fr, to):
        f, t = self._find_station(fr), self._find_station(to)
        if not f or not t:
            return None
        try:
            path = nx.shortest_path(self.G, f, t, weight='travel_time_min')
            length = nx.shortest_path_length(self.G, f, t, weight='travel_time_min')
            return {'path': path, 'stations': len(path), 'travel_time_min': round(length, 1)}
        except:
            return None
    
    # === CONFLICT DETECTION ===
    def detect_conflicts(self):
        conflicts = []
        for u, v, d in self.G.edges(data=True):
            util = d.get('current_load', 0) / d.get('capacity', 10)
            if util >= 0.9:
                conflicts.append({'type': 'capacity_critical', 'severity': 'high', 'location': f"{u}→{v}"})
        for n in self.G.nodes:
            if self.G.nodes[n].get('is_major_hub') and len(self.G.nodes[n].get('incident_history', [])) >= 2:
                conflicts.append({'type': 'cascade_risk', 'severity': 'high', 'location': n})
        return conflicts
    
    def analyze_incident_impact(self, name, delay=30):
        m = self._find_station(name)
        if not m:
            return {'error': 'Not found'}
        node = self.G.nodes[m]
        cf = 1 + (3 if node.get('is_major_hub') else (2 if node.get('is_hub') else node.get('degree', 0) / 10))
        return {'station': m, 'is_hub': node.get('is_hub'), 'is_major': node.get('is_major_hub'),
            'degree': node.get('degree'), 'cascade_factor': round(cf, 2), 'estimated_delay': round(delay * cf)}
    
    # === RESOLUTION ===
    def suggest_resolutions(self, name, inc_type='technical'):
        m = self._find_station(name)
        if not m:
            return {'error': 'Not found'}
        hist = defaultdict(int)
        for i in self.G.nodes[m].get('incident_history', []):
            if i.get('type') == inc_type:
                for r in str(i.get('resolution', '')).split('|'):
                    if r:
                        hist[r] += 1
        return {'station': m, 'suggestions': [
            {'strategy': 'SPEED_REGULATE', 'rationale': 'Safe default', 'hist': hist.get('SPEED_REGULATE', 0)},
            {'strategy': 'REROUTE', 'rationale': 'Use alternates', 'hist': hist.get('REROUTE', 0)},
            {'strategy': 'GRADUAL_RECOVERY', 'rationale': 'Phased restore', 'hist': hist.get('GRADUAL_RECOVERY', 0)},
            {'strategy': 'CANCEL', 'rationale': 'Last resort', 'hist': hist.get('CANCEL', 0)},
        ]}
    
    # === SIMULATION ===
    def simulate_incident(self, name, duration=60, severity='medium'):
        m = self._find_station(name)
        if not m:
            return {'error': 'Not found'}
        sim = GRAPH_CONFIG['simulation']
        mult = {'low': 0.5, 'medium': 1.0, 'high': 1.5, 'critical': 2.5}.get(severity, 1.0)
        affected = {m: duration * mult}
        queue = [(m, duration * mult, 0)]
        while queue:
            cur, delay, hops = queue.pop(0)
            if hops >= sim['max_propagation_hops']:
                continue
            for nb in self.get_neighbors(cur):
                dec = delay * sim['delay_decay_factor']
                if dec >= sim['time_step_minutes'] and nb not in affected:
                    affected[nb] = dec
                    queue.append((nb, dec, hops + 1))
        crit = [s for s in affected if self.G.nodes[s].get('is_major_hub') or self.G.nodes[s].get('is_hub')]
        return {'station': m, 'affected': len(affected), 'total_delay': round(sum(affected.values())),
            'critical_hubs': crit, 'top_10': dict(sorted(affected.items(), key=lambda x: -x[1])[:10])}
    
    # === EXPORT ===
    def export_graph(self, fp=None):
        if fp is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            fp = OUTPUT_DIR / "rail_network_graph.json"
        data = {
            'nodes': [{'id': n, **{k: v for k, v in self.G.nodes[n].items() if not isinstance(v, list)}} for n in self.G.nodes],
            'edges': [{'source': u, 'target': v, **d} for u, v, d in self.G.edges(data=True)],
            'stats': {'nodes': self.G.number_of_nodes(), 'edges': self.G.number_of_edges()},
        }
        with open(fp, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\n💾 Exported: {fp}")
        return fp


# ============================================================================
# MAIN
# ============================================================================

def main():
    g = RailNetworkGraph()
    g.build_from_data()
    
    print("\n" + "=" * 60)
    print("TESTING FEATURES")
    print("=" * 60)
    
    print("\n🔍 Roma Termini:")
    info = g.get_station("ROMA TERMINI")
    if info:
        print(f"   Region: {info.get('region')}, Degree: {info.get('degree')}, Major: {info.get('is_major_hub')}")
    
    print("\n🛤️ Path Milano→Roma:")
    p = g.get_path("MILANO CENTRALE", "ROMA TERMINI")
    if p:
        print(f"   {p['stations']} stations, ~{p['travel_time_min']} min")
    
    print("\n⚠️ Conflicts:")
    c = g.detect_conflicts()
    print(f"   {len(c)} detected")
    
    print("\n🔮 Simulate Bologna C.LE 60min high:")
    s = g.simulate_incident("BOLOGNA C.LE", 60, 'high')
    if 'error' not in s:
        print(f"   Affected: {s.get('affected', 0)}, Delay: {s.get('total_delay', 0)}min, Critical: {len(s.get('critical_hubs', []))}")
    else:
        print(f"   {s['error']}")
    
    print("\n💡 Resolutions Firenze:")
    r = g.suggest_resolutions("FIRENZE SANTA MARIA NOVELLA")
    for x in r.get('suggestions', [])[:3]:
        print(f"   - {x['strategy']}: {x['rationale']}")
    
    g.export_graph()
    
    print("\n" + "=" * 60)
    print("✅ GRAPH READY: Conflict Detection | Resolution | Simulation")
    print("=" * 60)
    return g


if __name__ == "__main__":
    main()
