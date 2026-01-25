"""
Lombardy Railway Data Extraction Pipeline
=========================================
Transforms and extracts train, station, and rail data for Lombardy region
to produce simulation-ready JSON for:
- Conflict Detection Engine
- Predictive Memory (Qdrant)
- Conflict Resolution Agent
- Simulation Engine
"""

import json
import csv
from collections import defaultdict
from typing import Dict, List, Set, Any


def parse_float(value: str) -> float:
    """Parse float value, handling comma as decimal separator and malformed data."""
    if not value or value.strip() == '':
        return 0.0
    cleaned = value.replace(',', '.')
    # Handle multiple decimal points by keeping only the first
    parts = cleaned.split('.')
    if len(parts) > 2:
        cleaned = parts[0] + '.' + ''.join(parts[1:])
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def load_csv_data(filepath: str) -> List[Dict[str, Any]]:
    """Load and parse the train CSV data."""
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                'train_id': row['train_id'],
                'route_id': int(row['route_id']),
                'station_name': row['station_name'],
                'station_order': int(row['station_order']),
                'lat': parse_float(row['lat']),
                'lon': parse_float(row['lon']),
                'distance': parse_float(row['distance']),
                'train_type': row['train_type'],
                'station_name_normalized': row['station_name_normalized']
            })
    return rows


def load_network_graph(filepath: str) -> Dict[str, Any]:
    """Load and parse the network graph JSON."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_lombardy_stations(nodes: List[Dict]) -> Dict[str, Dict]:
    """Extract only Lombardy stations from the network graph nodes."""
    lombardy_stations = {}
    for node in nodes:
        if node.get('region') == 'Lombardy':
            lombardy_stations[node['id']] = node
    return lombardy_stations


def extract_lombardy_rails(edges: List[Dict], lombardy_station_ids: Set[str]) -> List[Dict]:
    """Extract rails where both source AND target are Lombardy stations."""
    lombardy_rails = []
    for edge in edges:
        source = edge.get('source')
        target = edge.get('target')
        if source in lombardy_station_ids and target in lombardy_station_ids:
            lombardy_rails.append(edge)
    return lombardy_rails


def group_trains_by_id(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """Group CSV rows by train_id, preserving station order."""
    trains = defaultdict(list)
    for row in rows:
        trains[row['train_id']].append(row)
    
    # Sort each train's stops by station_order
    for train_id in trains:
        trains[train_id].sort(key=lambda x: x['station_order'])
    
    return trains


def build_train_object(train_id: str, stops: List[Dict]) -> Dict[str, Any]:
    """Build a single train JSON object from its stops."""
    if not stops:
        return None
    
    route = []
    for stop in stops:
        route.append({
            'station_name': stop['station_name'],
            'station_order': stop['station_order'],
            'lat': stop['lat'],
            'lon': stop['lon'],
            'distance_from_previous_km': stop['distance']
        })
    
    return {
        'train_id': train_id,
        'train_type': stops[0]['train_type'],
        'route_id': stops[0]['route_id'],
        'route': route
    }


def filter_lombardy_train_segment(train: Dict, lombardy_station_names: Set[str]) -> Dict:
    """
    Filter train to keep only Lombardy segment.
    A train is relevant if at least one station is in Lombardy.
    Returns the train with only Lombardy stations in its route.
    """
    if not train or not train.get('route'):
        return None
    
    # Check if any station is in Lombardy
    has_lombardy_station = any(
        stop['station_name'] in lombardy_station_names 
        for stop in train['route']
    )
    
    if not has_lombardy_station:
        return None
    
    # Filter route to keep only Lombardy stations
    lombardy_route = [
        stop for stop in train['route']
        if stop['station_name'] in lombardy_station_names
    ]
    
    if not lombardy_route:
        return None
    
    # Preserve original order (already sorted by station_order)
    return {
        'train_id': train['train_id'],
        'train_type': train['train_type'],
        'route_id': train['route_id'],
        'route': lombardy_route
    }


def integrity_check(trains: List[Dict], lombardy_station_names: Set[str]) -> List[Dict]:
    """
    Ensure every station in train routes exists in the Lombardy node list.
    Drop train segments referencing missing stations.
    """
    valid_trains = []
    for train in trains:
        if not train or not train.get('route'):
            continue
        
        # Filter out stops with stations not in Lombardy station list
        valid_route = [
            stop for stop in train['route']
            if stop['station_name'] in lombardy_station_names
        ]
        
        if valid_route:
            train['route'] = valid_route
            valid_trains.append(train)
    
    return valid_trains


def main():
    """Main processing pipeline."""
    
    # File paths
    csv_path = 'mileage_data_enriched.csv'
    graph_path = 'network_graph.json'
    output_path = 'lombardy_simulation_data.json'
    
    print("Loading input data...")
    
    # Load data
    csv_rows = load_csv_data(csv_path)
    print(f"  Loaded {len(csv_rows)} CSV rows")
    
    network_graph = load_network_graph(graph_path)
    print(f"  Loaded network graph with {len(network_graph['nodes'])} nodes and {len(network_graph['edges'])} edges")
    
    # PART B: Network Graph Extraction
    print("\nProcessing network graph...")
    
    # B1: Station (Node) Filtering
    lombardy_stations = extract_lombardy_stations(network_graph['nodes'])
    lombardy_station_ids = set(lombardy_stations.keys())
    print(f"  Extracted {len(lombardy_stations)} Lombardy stations")
    
    # B2: Rail (Edge) Filtering
    lombardy_rails = extract_lombardy_rails(network_graph['edges'], lombardy_station_ids)
    print(f"  Extracted {len(lombardy_rails)} Lombardy-to-Lombardy rails")
    
    # PART A: Train Data Transformation
    print("\nProcessing train data...")
    
    # A1: Group Trains
    trains_grouped = group_trains_by_id(csv_rows)
    print(f"  Grouped into {len(trains_grouped)} unique trains")
    
    # A2: Build Train JSON objects
    all_trains = []
    for train_id, stops in trains_grouped.items():
        train_obj = build_train_object(train_id, stops)
        if train_obj:
            all_trains.append(train_obj)
    print(f"  Built {len(all_trains)} train objects")
    
    # A3: Lombardy Train Filtering
    lombardy_trains = []
    for train in all_trains:
        filtered_train = filter_lombardy_train_segment(train, lombardy_station_ids)
        if filtered_train:
            lombardy_trains.append(filtered_train)
    print(f"  Filtered to {len(lombardy_trains)} trains with Lombardy segments")
    
    # B3: Integrity Check
    print("\nPerforming integrity check...")
    valid_trains = integrity_check(lombardy_trains, lombardy_station_ids)
    print(f"  Validated {len(valid_trains)} trains after integrity check")
    
    # Count total stations in train routes
    stations_in_routes = set()
    for train in valid_trains:
        for stop in train['route']:
            stations_in_routes.add(stop['station_name'])
    print(f"  Trains reference {len(stations_in_routes)} unique Lombardy stations")
    
    # PART C: Final Output Format
    print("\nBuilding final output...")
    
    output = {
        'trains': valid_trains,
        'stations': list(lombardy_stations.values()),
        'rails': lombardy_rails
    }
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nOutput written to: {output_path}")
    print(f"  - Trains: {len(output['trains'])}")
    print(f"  - Stations: {len(output['stations'])}")
    print(f"  - Rails: {len(output['rails'])}")
    
    return output


if __name__ == '__main__':
    main()
