"""
Rail Network Graph Builder
==========================
Builds a NetworkX graph of the Italian railway network from data.
Supports conflict detection, resolution generation, and what-if simulation.

Author: AI Rail Network Brain Team
Date: January 2026
"""

import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import json
import warnings
warnings.filterwarnings('ignore')

from .config import (
    STATION_DATA, MILEAGE_DATA, FAULT_DATA, OPERATION_DATA, OUTPUT_DIR,
    GRAPH_CONFIG, MAJOR_HUBS, ITALIAN_REGIONS
)


class RailNetworkGraph:
    """
    Graph-based representation of Italian railway network.
    
    Features:
    ---------
    - Nodes: Railway stations with attributes (lat, lon, region, capacity)
    - Edges: Track segments with attributes (distance, type, capacity, travel_time)
    - Incident overlay: Active incidents affect node/edge properties
    
    Use Cases:
    ----------
    1. Conflict Detection: Find capacity conflicts, cascade risks
    2. Resolution Generation: Suggest alternative routes, rescheduling
    3. What-If Simulation: Predict impact of incidents/changes
    """
    
    def __init__(self):
        """Initialize empty graph."""
        self.G = nx.DiGraph()  # Directed graph (trains have direction)
        self.stations_df = None
        self.routes_df = None
        self.incidents_df = None
        self.operations_df = None
        
        # Index structures for fast lookup
        self.station_index = {}  # name -> node_id
        self.region_stations = defaultdict(list)  # region -> [stations]
        self.line_edges = defaultdict(list)  # line_name -> [edges]
        
        # Active state (for simulation)
        self.active_incidents = []
        self.current_time = None
        
    # =========================================================================
    # GRAPH CONSTRUCTION
    # =========================================================================
    
    def build_from_data(self, verbose=True):
        """
        Build complete graph from data files.
        
        Steps:
        1. Load station data → Create nodes
        2. Load mileage data → Create edges (routes)
        3. Load incident data → Add incident attributes
        4. Load operation data → Add flow statistics
        """
        if verbose:
            print("=" * 60)
            print("BUILDING RAIL NETWORK GRAPH")
            print("=" * 60)
        
        # Step 1: Load and create nodes
        self._load_stations(verbose)
        
        # Step 2: Load and create edges
        self._load_routes(verbose)
        
        # Step 3: Load incidents
        self._load_incidents(verbose)
        
        # Step 4: Load operations
        self._load_operations(verbose)
        
        # Step 5: Compute additional graph properties
        self._compute_graph_properties(verbose)
        
        if verbose:
            self._print_summary()
        
        return self
    
    def _load_stations(self, verbose=True):
        """Load station data and create graph nodes."""
        if verbose:
            print("\n📍 Loading stations...")
        
        if not STATION_DATA.exists():
            print(f"  ⚠️ Station data not found: {STATION_DATA}")
            return
        
        self.stations_df = pd.read_csv(STATION_DATA)
        
        for _, row in self.stations_df.iterrows():
            station_name = row['name_normalized'] if pd.notna(row.get('name_normalized')) else row['name']
            
            # Create node with attributes
            self.G.add_node(
                station_name,
                node_type='station',
                name=row['name'],
                name_short=row.get('name_short', station_name),
                station_id=row.get('station_id'),
                lat=row['lat'] if pd.notna(row.get('lat')) else None,
                lon=row['lon'] if pd.notna(row.get('lon')) else None,
                region=row.get('region_name', 'Unknown'),
                region_id=row.get('id_region'),
                # Capacity and status (defaults)
                capacity=GRAPH_CONFIG['edge_types']['conventional']['capacity'],
                current_load=0,
                status='operational',
                # Incident tracking
                active_incidents=[],
                incident_history=[],
            )
            
            # Build indexes
            self.station_index[station_name] = station_name
            if row.get('name'):
                self.station_index[row['name']] = station_name
            
            region = row.get('region_name', 'Unknown')
            self.region_stations[region].append(station_name)
        
        if verbose:
            print(f"  ✅ Loaded {len(self.G.nodes)} stations")
            print(f"  📊 Regions: {len(self.region_stations)}")
    
    def _load_routes(self, verbose=True):
        """Load mileage data and create graph edges."""
        if verbose:
            print("\n🛤️ Loading routes...")
        
        if not MILEAGE_DATA.exists():
            print(f"  ⚠️ Mileage data not found: {MILEAGE_DATA}")
            return
        
        self.routes_df = pd.read_csv(MILEAGE_DATA)
        
        # Group by route to create edges
        edges_created = 0
        
        for route_id, route_group in self.routes_df.groupby('route_id'):
            # Sort by station order
            route_sorted = route_group.sort_values('station_order')
            stations = route_sorted['station_name_normalized'].tolist()
            distances = route_sorted['distance'].tolist()
            train_type = route_sorted['train_type'].iloc[0] if 'train_type' in route_sorted else 'regional'
            
            # Determine edge type from train type
            if 'high' in str(train_type).lower() or 'speed' in str(train_type).lower():
                edge_type = 'high_speed'
            elif 'inter' in str(train_type).lower() or 'euro' in str(train_type).lower():
                edge_type = 'conventional'
            else:
                edge_type = 'regional'
            
            edge_config = GRAPH_CONFIG['edge_types'].get(edge_type, GRAPH_CONFIG['edge_types']['regional'])
            
            # Create edges between consecutive stations
            for i in range(len(stations) - 1):
                from_station = stations[i]
                to_station = stations[i + 1]
                distance = distances[i + 1] if i + 1 < len(distances) else 0
                
                # Skip if stations not in graph
                if from_station not in self.G.nodes or to_station not in self.G.nodes:
                    continue
                
                # Calculate travel time (distance / max_speed * 60 + buffer)
                travel_time = (distance / edge_config['max_speed']) * 60 + 2 if distance > 0 else 5
                
                # Create or update edge
                if self.G.has_edge(from_station, to_station):
                    # Edge exists, update if better
                    existing = self.G[from_station][to_station]
                    if edge_type == 'high_speed' and existing.get('edge_type') != 'high_speed':
                        self.G[from_station][to_station].update({
                            'edge_type': edge_type,
                            'max_speed': edge_config['max_speed'],
                            'capacity': max(existing.get('capacity', 0), edge_config['capacity']),
                        })
                else:
                    # Create new edge
                    self.G.add_edge(
                        from_station,
                        to_station,
                        edge_type=edge_type,
                        distance_km=distance,
                        travel_time_min=travel_time,
                        max_speed=edge_config['max_speed'],
                        capacity=edge_config['capacity'],
                        current_load=0,
                        status='operational',
                        routes=[route_id],
                        active_incidents=[],
                    )
                    edges_created += 1
                    
                    # Also create reverse edge (bidirectional tracks)
                    if not self.G.has_edge(to_station, from_station):
                        self.G.add_edge(
                            to_station,
                            from_station,
                            edge_type=edge_type,
                            distance_km=distance,
                            travel_time_min=travel_time,
                            max_speed=edge_config['max_speed'],
                            capacity=edge_config['capacity'],
                            current_load=0,
                            status='operational',
                            routes=[route_id],
                            active_incidents=[],
                        )
        
        if verbose:
            print(f"  ✅ Created {self.G.number_of_edges()} edges")
            print(f"  🚄 Routes processed: {len(self.routes_df['route_id'].unique())}")
    
    def _load_incidents(self, verbose=True):
        """Load incident data and associate with nodes/edges."""
        if verbose:
            print("\n⚠️ Loading incidents...")
        
        if not FAULT_DATA.exists():
            print(f"  ⚠️ Incident data not found: {FAULT_DATA}")
            return
        
        self.incidents_df = pd.read_csv(FAULT_DATA)
        
        incidents_linked = 0
        
        for idx, row in self.incidents_df.iterrows():
            incident = {
                'id': idx,
                'date': row['date'],
                'type': row.get('incident_type', 'unknown'),
                'line': row.get('line_normalized', row.get('line', 'Unknown')),
                'station': row.get('location_station'),
                'segment': row.get('location_segment'),
                'delay_min': row.get('delay_duration_min', 0),
                'severity': row.get('severity_score', 0),
                'affected_trains': row.get('affected_trains_total', 0),
                'resolution': row.get('resolution_types', ''),
                'time_of_day': row.get('time_of_day', 'unknown'),
            }
            
            # Try to link to station node
            station_name = row.get('location_station')
            if pd.notna(station_name):
                # Find matching node
                matched = self._find_station(station_name)
                if matched and matched in self.G.nodes:
                    self.G.nodes[matched]['incident_history'].append(incident)
                    incidents_linked += 1
            
            self.active_incidents.append(incident)
        
        if verbose:
            print(f"  ✅ Loaded {len(self.incidents_df)} incidents")
            print(f"  🔗 Linked to stations: {incidents_linked}")
    
    def _load_operations(self, verbose=True):
        """Load operation data for traffic statistics."""
        if verbose:
            print("\n📊 Loading operations...")
        
        if not OPERATION_DATA.exists():
            print(f"  ⚠️ Operation data not found: {OPERATION_DATA}")
            return
        
        self.operations_df = pd.read_csv(OPERATION_DATA)
        
        if verbose:
            print(f"  ✅ Loaded {len(self.operations_df)} operation records")
    
    def _compute_graph_properties(self, verbose=True):
        """Compute additional graph properties and metrics."""
        if verbose:
            print("\n🔧 Computing graph properties...")
        
        # Identify hub stations (high degree)
        degrees = dict(self.G.degree())
        avg_degree = np.mean(list(degrees.values())) if degrees else 0
        
        for node in self.G.nodes:
            node_degree = degrees.get(node, 0)
            self.G.nodes[node]['degree'] = node_degree
            self.G.nodes[node]['is_hub'] = node_degree > avg_degree * 2
            self.G.nodes[node]['is_major_hub'] = node in MAJOR_HUBS
        
        # Compute connected components
        if self.G.number_of_nodes() > 0:
            # Use undirected version for connectivity
            undirected = self.G.to_undirected()
            components = list(nx.connected_components(undirected))
            largest_component = max(components, key=len) if components else set()
            
            for node in self.G.nodes:
                self.G.nodes[node]['in_main_network'] = node in largest_component
        
        if verbose:
            hubs = [n for n in self.G.nodes if self.G.nodes[n].get('is_hub')]
            print(f"  ✅ Identified {len(hubs)} hub stations")
            print(f"  📈 Average degree: {avg_degree:.2f}")
    
    def _find_station(self, name):
        """Find station node by name (fuzzy matching)."""
        if not name:
            return None
        
        name_upper = str(name).upper().strip()
        
        # Direct match
        if name_upper in self.station_index:
            return self.station_index[name_upper]
        
        # Partial match
        for station in self.G.nodes:
            if name_upper in station or station in name_upper:
                return station
        
        return None
    
    def _print_summary(self):
        """Print graph summary."""
        print("\n" + "=" * 60)
        print("GRAPH SUMMARY")
        print("=" * 60)
        print(f"📍 Nodes (Stations): {self.G.number_of_nodes()}")
        print(f"🛤️ Edges (Segments):  {self.G.number_of_edges()}")
        print(f"📊 Regions: {len(self.region_stations)}")
        print(f"⚠️ Incidents loaded: {len(self.active_incidents)}")
        
        # Top regions by stations
        print("\n🏆 Top Regions by Stations:")
        sorted_regions = sorted(self.region_stations.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        for region, stations in sorted_regions:
            print(f"   {region}: {len(stations)} stations")
        
        # Hub stations
        hubs = [n for n in self.G.nodes if self.G.nodes[n].get('is_major_hub')]
        print(f"\n🚉 Major Hubs in Network: {len(hubs)}")
        for hub in hubs[:5]:
            print(f"   - {hub}")
    
    # =========================================================================
    # GRAPH QUERIES
    # =========================================================================
    
    def get_station(self, name):
        """Get station node attributes."""
        matched = self._find_station(name)
        if matched:
            return dict(self.G.nodes[matched])
        return None
    
    def get_neighbors(self, station_name, direction='both'):
        """Get neighboring stations."""
        matched = self._find_station(station_name)
        if not matched:
            return []
        
        if direction == 'outgoing':
            return list(self.G.successors(matched))
        elif direction == 'incoming':
            return list(self.G.predecessors(matched))
        else:
            return list(set(self.G.successors(matched)) | set(self.G.predecessors(matched)))
    
    def get_path(self, from_station, to_station, weight='travel_time_min'):
        """Find shortest path between stations."""
        from_matched = self._find_station(from_station)
        to_matched = self._find_station(to_station)
        
        if not from_matched or not to_matched:
            return None
        
        try:
            path = nx.shortest_path(self.G, from_matched, to_matched, weight=weight)
            total_weight = nx.shortest_path_length(self.G, from_matched, to_matched, weight=weight)
            return {
                'path': path,
                'stations': len(path),
                f'total_{weight}': total_weight,
            }
        except nx.NetworkXNoPath:
            return None
    
    def get_stations_in_radius(self, lat, lon, radius_km=50):
        """Find stations within radius of coordinates."""
        stations = []
        
        for node in self.G.nodes:
            node_lat = self.G.nodes[node].get('lat')
            node_lon = self.G.nodes[node].get('lon')
            
            if node_lat and node_lon:
                dist = self._haversine_distance(lat, lon, node_lat, node_lon)
                if dist <= radius_km:
                    stations.append({
                        'station': node,
                        'distance_km': round(dist, 2),
                        **self.G.nodes[node]
                    })
        
        return sorted(stations, key=lambda x: x['distance_km'])
    
    def get_region_subgraph(self, region):
        """Get subgraph for a specific region."""
        if region not in self.region_stations:
            return None
        
        stations = self.region_stations[region]
        return self.G.subgraph(stations).copy()
    
    # =========================================================================
    # CONFLICT DETECTION
    # =========================================================================
    
    def detect_conflicts(self, incident=None):
        """
        Detect potential conflicts in the network.
        
        Types of conflicts:
        1. Capacity conflicts (overloaded segments)
        2. Cascade risks (incidents near hubs)
        3. Geographic clusters (multiple incidents in area)
        4. Temporal patterns (recurring issues)
        
        Returns:
            List of detected conflicts with severity and recommendations.
        """
        conflicts = []
        thresholds = GRAPH_CONFIG['conflict_thresholds']
        
        # 1. Check capacity on all edges
        for u, v, data in self.G.edges(data=True):
            capacity = data.get('capacity', 10)
            load = data.get('current_load', 0)
            utilization = load / capacity if capacity > 0 else 0
            
            if utilization >= thresholds['capacity_critical']:
                conflicts.append({
                    'type': 'capacity_critical',
                    'severity': 'high',
                    'location': f"{u} → {v}",
                    'utilization': round(utilization * 100, 1),
                    'description': f"Segment at {utilization*100:.0f}% capacity",
                    'recommendation': 'Consider rerouting or adding services',
                })
            elif utilization >= thresholds['capacity_warning']:
                conflicts.append({
                    'type': 'capacity_warning',
                    'severity': 'medium',
                    'location': f"{u} → {v}",
                    'utilization': round(utilization * 100, 1),
                    'description': f"Segment at {utilization*100:.0f}% capacity",
                    'recommendation': 'Monitor for potential issues',
                })
        
        # 2. Check for cascade risks (incidents near hubs)
        for node in self.G.nodes:
            if self.G.nodes[node].get('is_hub') or self.G.nodes[node].get('is_major_hub'):
                incident_history = self.G.nodes[node].get('incident_history', [])
                if len(incident_history) >= 2:
                    conflicts.append({
                        'type': 'cascade_risk',
                        'severity': 'high',
                        'location': node,
                        'incidents': len(incident_history),
                        'description': f"Hub station with {len(incident_history)} past incidents",
                        'recommendation': 'Pre-position recovery resources',
                    })
        
        # 3. Check geographic clusters
        incident_locations = []
        for incident in self.active_incidents:
            station = incident.get('station')
            if station:
                matched = self._find_station(station)
                if matched and matched in self.G.nodes:
                    node_data = self.G.nodes[matched]
                    if node_data.get('lat') and node_data.get('lon'):
                        incident_locations.append({
                            'station': matched,
                            'lat': node_data['lat'],
                            'lon': node_data['lon'],
                            'incident': incident,
                        })
        
        # Find clusters (simple: check for multiple incidents within proximity)
        for i, loc1 in enumerate(incident_locations):
            nearby = []
            for j, loc2 in enumerate(incident_locations):
                if i != j:
                    dist = self._haversine_distance(
                        loc1['lat'], loc1['lon'],
                        loc2['lat'], loc2['lon']
                    )
                    if dist <= thresholds['proximity_km']:
                        nearby.append(loc2)
            
            if len(nearby) >= 2:
                conflicts.append({
                    'type': 'geographic_cluster',
                    'severity': 'medium',
                    'location': loc1['station'],
                    'nearby_incidents': len(nearby),
                    'description': f"Cluster of {len(nearby)+1} incidents within {thresholds['proximity_km']}km",
                    'recommendation': 'Investigate root cause, may be systemic issue',
                })
        
        return conflicts
    
    def analyze_incident_impact(self, station_name, delay_min=30, affected_trains=10):
        """
        Analyze potential impact of an incident at a station.
        
        Args:
            station_name: Station where incident occurs
            delay_min: Expected delay in minutes
            affected_trains: Number of trains affected
            
        Returns:
            Impact analysis with affected routes, cascade risk, etc.
        """
        matched = self._find_station(station_name)
        if not matched:
            return {'error': f"Station not found: {station_name}"}
        
        node_data = self.G.nodes[matched]
        
        # Find affected routes (edges)
        incoming = list(self.G.predecessors(matched))
        outgoing = list(self.G.successors(matched))
        
        # Calculate cascade potential
        is_hub = node_data.get('is_hub', False)
        is_major = node_data.get('is_major_hub', False)
        degree = node_data.get('degree', 0)
        
        cascade_factor = 1.0
        if is_major:
            cascade_factor = 3.0
        elif is_hub:
            cascade_factor = 2.0
        else:
            cascade_factor = 1.0 + (degree / 10)
        
        estimated_total_delay = delay_min * cascade_factor
        estimated_affected_total = int(affected_trains * cascade_factor)
        
        # Find alternate routes
        alternates = []
        for out_station in outgoing[:3]:
            # Try to find alternative paths avoiding this station
            for other_in in incoming[:3]:
                if other_in != out_station:
                    try:
                        # Create subgraph without incident station
                        temp_G = self.G.copy()
                        temp_G.remove_node(matched)
                        if nx.has_path(temp_G, other_in, out_station):
                            path = nx.shortest_path(temp_G, other_in, out_station)
                            alternates.append({
                                'from': other_in,
                                'to': out_station,
                                'via': path,
                            })
                    except:
                        pass
        
        return {
            'station': matched,
            'region': node_data.get('region'),
            'is_hub': is_hub,
            'is_major_hub': is_major,
            'degree': degree,
            'incoming_routes': len(incoming),
            'outgoing_routes': len(outgoing),
            'initial_delay_min': delay_min,
            'initial_affected': affected_trains,
            'cascade_factor': round(cascade_factor, 2),
            'estimated_total_delay_min': round(estimated_total_delay, 0),
            'estimated_total_affected': estimated_affected_total,
            'alternate_routes': alternates[:5],
            'severity': 'critical' if is_major else ('high' if is_hub else 'medium'),
        }
    
    # =========================================================================
    # RESOLUTION GENERATION
    # =========================================================================
    
    def suggest_resolutions(self, incident_station, incident_type='technical'):
        """
        Suggest resolution strategies for an incident.
        
        Args:
            incident_station: Station where incident occurred
            incident_type: Type of incident (technical, trespasser, weather, etc.)
            
        Returns:
            Ranked list of resolution strategies with rationale.
        """
        matched = self._find_station(incident_station)
        if not matched:
            return {'error': f"Station not found: {incident_station}"}
        
        node_data = self.G.nodes[matched]
        suggestions = []
        
        # Get historical resolutions for similar incidents
        historical = node_data.get('incident_history', [])
        historical_resolutions = defaultdict(int)
        
        for inc in historical:
            if inc.get('type') == incident_type:
                res = inc.get('resolution', '')
                if res:
                    for r in res.split('|'):
                        if r:
                            historical_resolutions[r] += 1
        
        # Strategy 1: Speed regulation (almost always applicable)
        suggestions.append({
            'strategy': 'SPEED_REGULATE',
            'priority': 1,
            'confidence': 0.9,
            'rationale': 'Safe default, minimizes disruption while allowing continued operation',
            'historical_success': historical_resolutions.get('SPEED_REGULATE', 0),
        })
        
        # Strategy 2: Reroute (if alternatives exist)
        alternates = self._find_alternate_routes(matched)
        if alternates:
            suggestions.append({
                'strategy': 'REROUTE',
                'priority': 2,
                'confidence': 0.8,
                'rationale': f'{len(alternates)} alternate routes available',
                'alternate_routes': alternates[:3],
                'historical_success': historical_resolutions.get('REROUTE', 0),
            })
        
        # Strategy 3: Gradual recovery (for major incidents)
        if incident_type in ['trespasser', 'technical']:
            suggestions.append({
                'strategy': 'GRADUAL_RECOVERY',
                'priority': 3,
                'confidence': 0.7,
                'rationale': 'Phased restoration reduces system shock',
                'historical_success': historical_resolutions.get('GRADUAL_RECOVERY', 0),
            })
        
        # Strategy 4: Cancellation (last resort for severe cases)
        suggestions.append({
            'strategy': 'CANCEL',
            'priority': 4,
            'confidence': 0.5,
            'rationale': 'Last resort if other strategies insufficient',
            'historical_success': historical_resolutions.get('CANCEL', 0),
        })
        
        # Strategy 5: Bus bridge (for prolonged outages)
        if incident_type in ['maintenance', 'technical', 'trespasser']:
            suggestions.append({
                'strategy': 'BUS_BRIDGE',
                'priority': 5,
                'confidence': 0.6,
                'rationale': 'Maintains connectivity during prolonged outage',
                'historical_success': historical_resolutions.get('BUS_BRIDGE', 0),
            })
        
        # Sort by historical success + base confidence
        for s in suggestions:
            s['score'] = s['confidence'] + (s['historical_success'] * 0.1)
        
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'station': matched,
            'incident_type': incident_type,
            'suggestions': suggestions,
            'historical_incidents': len(historical),
        }
    
    def _find_alternate_routes(self, station):
        """Find alternate routes avoiding a station."""
        alternates = []
        
        incoming = list(self.G.predecessors(station))
        outgoing = list(self.G.successors(station))
        
        # Create graph without the station
        temp_G = self.G.copy()
        temp_G.remove_node(station)
        
        for in_st in incoming[:5]:
            for out_st in outgoing[:5]:
                if in_st != out_st:
                    try:
                        if nx.has_path(temp_G, in_st, out_st):
                            path = nx.shortest_path(temp_G, in_st, out_st)
                            length = nx.shortest_path_length(temp_G, in_st, out_st, weight='travel_time_min')
                            alternates.append({
                                'from': in_st,
                                'to': out_st,
                                'via': path,
                                'travel_time_min': round(length, 1),
                            })
                    except:
                        pass
        
        return alternates
    
    # =========================================================================
    # WHAT-IF SIMULATION
    # =========================================================================
    
    def simulate_incident(self, station_name, duration_min=60, severity='medium'):
        """
        Simulate an incident and predict network impact.
        
        Args:
            station_name: Station where incident occurs
            duration_min: Expected duration of incident
            severity: 'low', 'medium', 'high', 'critical'
            
        Returns:
            Simulation results with cascade effects.
        """
        matched = self._find_station(station_name)
        if not matched:
            return {'error': f"Station not found: {station_name}"}
        
        sim_params = GRAPH_CONFIG['simulation']
        
        # Initial impact
        severity_multipliers = {
            'low': 0.5,
            'medium': 1.0,
            'high': 1.5,
            'critical': 2.5,
        }
        multiplier = severity_multipliers.get(severity, 1.0)
        
        # Propagate delays through network
        affected_stations = {matched: duration_min * multiplier}
        cascade_queue = [(matched, duration_min * multiplier, 0)]
        
        while cascade_queue:
            current, delay, hops = cascade_queue.pop(0)
            
            if hops >= sim_params['max_propagation_hops']:
                continue
            
            # Propagate to neighbors
            neighbors = self.get_neighbors(current)
            decayed_delay = delay * sim_params['delay_decay_factor']
            
            if decayed_delay < sim_params['time_step_minutes']:
                continue
            
            for neighbor in neighbors:
                if neighbor not in affected_stations:
                    affected_stations[neighbor] = decayed_delay
                    cascade_queue.append((neighbor, decayed_delay, hops + 1))
        
        # Calculate summary statistics
        total_delay = sum(affected_stations.values())
        max_delay = max(affected_stations.values())
        
        # Identify critical stations affected
        critical_affected = [
            s for s in affected_stations
            if self.G.nodes[s].get('is_major_hub') or self.G.nodes[s].get('is_hub')
        ]
        
        return {
            'incident_station': matched,
            'incident_duration_min': duration_min,
            'severity': severity,
            'total_affected_stations': len(affected_stations),
            'total_cascade_delay_min': round(total_delay, 0),
            'max_station_delay_min': round(max_delay, 0),
            'critical_stations_affected': critical_affected,
            'affected_stations': {k: round(v, 1) for k, v in sorted(affected_stations.items(), key=lambda x: -x[1])[:20]},
            'simulation_params': sim_params,
        }
    
    def compare_scenarios(self, scenarios):
        """
        Compare multiple what-if scenarios.
        
        Args:
            scenarios: List of dicts with 'station', 'duration_min', 'severity'
            
        Returns:
            Comparison of all scenarios with ranking.
        """
        results = []
        
        for i, scenario in enumerate(scenarios):
            sim = self.simulate_incident(
                station_name=scenario.get('station'),
                duration_min=scenario.get('duration_min', 60),
                severity=scenario.get('severity', 'medium'),
            )
            sim['scenario_id'] = i + 1
            sim['scenario_name'] = scenario.get('name', f"Scenario {i+1}")
            results.append(sim)
        
        # Rank by total impact
        results.sort(key=lambda x: x.get('total_cascade_delay_min', 0), reverse=True)
        
        for rank, r in enumerate(results):
            r['impact_rank'] = rank + 1
        
        return {
            'scenarios_count': len(scenarios),
            'worst_case': results[0] if results else None,
            'best_case': results[-1] if results else None,
            'all_scenarios': results,
        }
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates in km."""
        R = 6371  # Earth's radius in km
        
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    def export_graph(self, filepath=None):
        """Export graph to JSON format."""
        if filepath is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            filepath = OUTPUT_DIR / "rail_network_graph.json"
        
        data = {
            'nodes': [
                {
                    'id': node,
                    **{k: v for k, v in self.G.nodes[node].items() 
                       if not isinstance(v, list) or k != 'incident_history'}
                }
                for node in self.G.nodes
            ],
            'edges': [
                {
                    'source': u,
                    'target': v,
                    **{k: v for k, v in data.items() if not isinstance(v, list)}
                }
                for u, v, data in self.G.edges(data=True)
            ],
            'metadata': {
                'total_nodes': self.G.number_of_nodes(),
                'total_edges': self.G.number_of_edges(),
                'regions': len(self.region_stations),
                'incidents_loaded': len(self.active_incidents),
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"✅ Graph exported to: {filepath}")
        return filepath
    
    def get_stats(self):
        """Get graph statistics."""
        return {
            'nodes': self.G.number_of_nodes(),
            'edges': self.G.number_of_edges(),
            'regions': len(self.region_stations),
            'incidents': len(self.active_incidents),
            'hubs': len([n for n in self.G.nodes if self.G.nodes[n].get('is_hub')]),
            'major_hubs': len([n for n in self.G.nodes if self.G.nodes[n].get('is_major_hub')]),
            'density': nx.density(self.G) if self.G.number_of_nodes() > 0 else 0,
        }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Build and test the rail network graph."""
    print("=" * 60)
    print("RAIL NETWORK GRAPH BUILDER")
    print("=" * 60)
    
    # Build graph
    graph = RailNetworkGraph()
    graph.build_from_data(verbose=True)
    
    # Test queries
    print("\n" + "=" * 60)
    print("TEST QUERIES")
    print("=" * 60)
    
    # Test station lookup
    print("\n🔍 Station Lookup: ROMA TERMINI")
    station = graph.get_station("ROMA TERMINI")
    if station:
        print(f"   Region: {station.get('region')}")
        print(f"   Degree: {station.get('degree')}")
        print(f"   Is Hub: {station.get('is_hub')}")
    
    # Test path finding
    print("\n🛤️ Path: Milano Centrale → Roma Termini")
    path = graph.get_path("MILANO CENTRALE", "ROMA TERMINI")
    if path:
        print(f"   Stations: {path['stations']}")
        print(f"   Travel time: {path.get('total_travel_time_min', 'N/A')} min")
    
    # Test conflict detection
    print("\n⚠️ Conflict Detection")
    conflicts = graph.detect_conflicts()
    print(f"   Detected: {len(conflicts)} potential conflicts")
    for c in conflicts[:3]:
        print(f"   - {c['type']}: {c['location']} ({c['severity']})")
    
    # Test incident simulation
    print("\n🔮 Simulating incident at Bologna Centrale (60 min, high severity)")
    sim = graph.simulate_incident("BOLOGNA CENTRALE", duration_min=60, severity='high')
    if 'error' not in sim:
        print(f"   Affected stations: {sim['total_affected_stations']}")
        print(f"   Total cascade delay: {sim['total_cascade_delay_min']} min")
        print(f"   Critical hubs affected: {len(sim['critical_stations_affected'])}")
    
    # Test resolution suggestions
    print("\n💡 Resolution suggestions for technical incident at Firenze SMN")
    resolutions = graph.suggest_resolutions("FIRENZE SANTA MARIA NOVELLA", "technical")
    if 'error' not in resolutions:
        print(f"   Top suggestions:")
        for s in resolutions['suggestions'][:3]:
            print(f"   - {s['strategy']}: {s['rationale'][:50]}...")
    
    # Export graph
    print("\n💾 Exporting graph...")
    graph.export_graph()
    
    print("\n" + "=" * 60)
    print("✅ GRAPH BUILD COMPLETE")
    print("=" * 60)
    
    return graph


if __name__ == "__main__":
    main()
