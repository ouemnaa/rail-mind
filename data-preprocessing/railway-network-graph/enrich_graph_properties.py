"""
Enhanced Graph Property Enrichment
===================================
Estimates realistic station and track properties based on:
- Historical incident data
- Station degree and connectivity
- Geographic location
- Train operation patterns

Usage:
    python Rail_network/enrich_graph_properties.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data" / "Processed"
GRAPH_FILE = Path(__file__).parent / "output" / "rail_network_graph.json"

def load_historical_data():
    """Load historical data for estimation."""
    try:
        faults = pd.read_csv(DATA_DIR / "fault_data_enriched.csv")
        operations = pd.read_csv(DATA_DIR / "operation_data_enriched.csv", nrows=50000)
        stations = pd.read_csv(DATA_DIR / "station_data_enriched.csv")
        return faults, operations, stations
    except Exception as e:
        print(f"Warning: Could not load some data files: {e}")
        return None, None, None

def estimate_station_congestion(station_name, faults_df, operations_df):
    """Estimate congestion level based on historical data."""
    if faults_df is None or operations_df is None:
        return 'medium', 90  # Default
    
    # Count incidents at this station
    if 'location_station' in faults_df.columns:
        incidents = len(faults_df[faults_df['location_station'].str.contains(
            station_name, case=False, na=False)])
    else:
        incidents = 0
    
    # Estimate average delay
    avg_delay = 60 + (incidents * 15)  # Base 60s + 15s per incident
    
    # Classify congestion
    if incidents > 10:
        return 'high', min(avg_delay, 300)
    elif incidents > 3:
        return 'medium', min(avg_delay, 180)
    else:
        return 'low', min(avg_delay, 90)

def estimate_track_risk(edge_data, faults_df):
    """Estimate track risk profile based on historical incidents."""
    distance = edge_data.get('distance_km', 0)
    edge_type = edge_data.get('edge_type', 'regional')
    
    # Base risk on type and distance
    if edge_type == 'high_speed':
        base_risk = 0.3  # Higher speed = higher risk
    elif edge_type == 'conventional':
        base_risk = 0.2
    else:
        base_risk = 0.1
    
    # Longer distances = more risk
    distance_factor = min(distance / 100, 1.0)
    
    # Historical incidents
    hist_incidents = edge_data.get('historical_incidents', 0)
    incident_factor = min(hist_incidents / 10, 0.5)
    
    total_risk = base_risk + distance_factor * 0.3 + incident_factor
    
    if total_risk > 0.6:
        return 'high'
    elif total_risk > 0.3:
        return 'medium'
    else:
        return 'low'

def enrich_graph_properties():
    """Enrich graph with advanced property estimation."""
    print("=" * 70)
    print("ENRICHING GRAPH PROPERTIES")
    print("=" * 70)
    
    # Load graph
    if not GRAPH_FILE.exists():
        print(f"Error: Graph file not found at {GRAPH_FILE}")
        return
    
    with open(GRAPH_FILE, 'r') as f:
        graph_data = json.load(f)
    
    print(f"\n📊 Loaded graph: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges")
    
    # Load historical data
    print("\n📁 Loading historical data...")
    faults_df, operations_df, stations_df = load_historical_data()
    
    # Enrich nodes (stations)
    print("\n🚉 Enriching station properties...")
    enriched_nodes = 0
    
    for node in graph_data['nodes']:
        station_name = node.get('name', node.get('id', ''))
        degree = node.get('degree', 0)
        is_major = node.get('is_major_hub', False)
        
        # Update congestion based on historical data
        congestion, avg_delay = estimate_station_congestion(
            station_name, faults_df, operations_df)
        
        # Update if we have better estimates
        if faults_df is not None:
            node['historical_congestion_level'] = congestion
            node['avg_delay_sec'] = avg_delay
        
        # Adjust platform count based on degree (connectivity)
        if 'platforms' in node and degree > 0:
            # More connected stations likely have more platforms
            if degree > 30 and node['platforms'] < 10:
                node['platforms'] = np.random.randint(12, 20)
                node['max_trains_at_once'] = node['platforms'] - 2
            elif degree > 15 and node['platforms'] < 6:
                node['platforms'] = np.random.randint(6, 12)
                node['max_trains_at_once'] = node['platforms'] - 1
        
        enriched_nodes += 1
    
    print(f"  ✅ Enriched {enriched_nodes} stations")
    
    # Enrich edges (tracks)
    print("\n🛤️ Enriching track properties...")
    enriched_edges = 0
    
    for edge in graph_data['edges']:
        # Update risk profile
        risk = estimate_track_risk(edge, faults_df)
        edge['risk_profile'] = risk
        
        # Add freight access for longer routes
        if edge.get('distance_km', 0) > 50:
            edge['priority_access'] = ['passenger', 'freight']
        
        # Single-track detection for regional lines
        if edge.get('edge_type') == 'regional' and edge.get('distance_km', 0) > 30:
            edge['direction'] = 'single_track'
            edge['reroutable'] = False
        
        enriched_edges += 1
    
    print(f"  ✅ Enriched {enriched_edges} edges")
    
    # Save enriched graph
    print("\n💾 Saving enriched graph...")
    with open(GRAPH_FILE, 'w') as f:
        json.dump(graph_data, f, indent=2)
    
    print(f"  ✅ Saved to {GRAPH_FILE}")
    
    # Statistics
    print("\n📊 ENRICHMENT SUMMARY")
    print("-" * 70)
    
    # Station statistics
    congestion_counts = {}
    platform_dist = []
    for node in graph_data['nodes']:
        cong = node.get('historical_congestion_level', 'unknown')
        congestion_counts[cong] = congestion_counts.get(cong, 0) + 1
        if 'platforms' in node:
            platform_dist.append(node['platforms'])
    
    print("\n🚉 Station Properties:")
    print(f"  Congestion Levels:")
    for level, count in sorted(congestion_counts.items()):
        print(f"    {level}: {count} stations")
    
    if platform_dist:
        print(f"\n  Platform Distribution:")
        print(f"    Mean: {np.mean(platform_dist):.1f}")
        print(f"    Median: {np.median(platform_dist):.0f}")
        print(f"    Range: {min(platform_dist)} - {max(platform_dist)}")
    
    # Track statistics
    risk_counts = {}
    reroutable_count = 0
    for edge in graph_data['edges']:
        risk = edge.get('risk_profile', 'unknown')
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        if edge.get('reroutable', False):
            reroutable_count += 1
    
    print("\n🛤️ Track Properties:")
    print(f"  Risk Profiles:")
    for level, count in sorted(risk_counts.items()):
        print(f"    {level}: {count} tracks")
    print(f"\n  Reroutable tracks: {reroutable_count} ({reroutable_count/len(graph_data['edges'])*100:.1f}%)")
    
    print("\n" + "=" * 70)
    print("✅ ENRICHMENT COMPLETE")
    print("=" * 70)

if __name__ == '__main__':
    enrich_graph_properties()
