"""
Step 1: Data Enrichment - Fill Gaps
===================================
This script enriches fault data by:
1. Filling missing location fields (location_station, location_segment)
2. Linking station coordinates to incident locations
3. Correlating train operations with fault events
4. Detecting historical sequence patterns
5. Adding precise timestamps

Author: AI Rail Network Brain Team
Date: January 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import re
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

from config import (
    PROCESSED_DIR, OUTPUT_DIR, 
    FAULT_OPERATION_TIME_WINDOW_HOURS,
    STATION_MATCH_DISTANCE_KM
)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km using Haversine formula."""
    R = 6371  # Earth's radius in km
    
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    return R * c


def fill_missing_locations(df_faults):
    """
    Fill missing location_station and location_segment fields.
    Strategy:
    1. If location_station is NaN but location_segment exists → extract station from segment
    2. If location_segment is NaN but location_station exists → use station as segment
    3. Extract location from delay_reason text if both are NaN
    """
    print("\n[STEP 0] Filling missing location fields...")
    
    filled_station = 0
    filled_segment = 0
    
    for idx, row in df_faults.iterrows():
        # Fill location_station from location_segment
        if pd.isna(row.get('location_station')) and pd.notna(row.get('location_segment')):
            segment = str(row['location_segment'])
            # Extract first station name (e.g., "Tortona - Voghera after" → "Tortona")
            first_station = segment.split('-')[0].strip()
            # Remove common suffixes
            first_station = re.sub(r'\s+(after|before|near|between).*$', '', first_station, flags=re.IGNORECASE)
            if first_station:
                df_faults.at[idx, 'location_station'] = first_station
                filled_station += 1
        
        # Fill location_segment from location_station
        if pd.isna(row.get('location_segment')) and pd.notna(row.get('location_station')):
            station = str(row['location_station'])
            df_faults.at[idx, 'location_segment'] = f"near {station}"
            filled_segment += 1
        
        # Try to extract from delay_reason if both are NaN
        if pd.isna(row.get('location_station')) and pd.isna(row.get('location_segment')):
            delay_reason = str(row.get('delay_reason', ''))
            
            # Pattern: "near <Station>" or "between <Station1> and <Station2>"
            near_match = re.search(r'near\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', delay_reason)
            between_match = re.search(r'between\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+and\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', delay_reason)
            
            if between_match:
                station1, station2 = between_match.groups()
                df_faults.at[idx, 'location_station'] = station1
                df_faults.at[idx, 'location_segment'] = f"{station1} - {station2}"
                filled_station += 1
                filled_segment += 1
            elif near_match:
                station = near_match.group(1)
                df_faults.at[idx, 'location_station'] = station
                df_faults.at[idx, 'location_segment'] = f"near {station}"
                filled_station += 1
                filled_segment += 1
            else:
                # Last resort: use line name
                line = str(row.get('line', ''))
                if line and '-' in line:
                    first_city = line.split('-')[0].strip()
                    # Remove "High Speed" prefix
                    first_city = re.sub(r'^High\s+Speed\s*', '', first_city, flags=re.IGNORECASE).strip()
                    if first_city:
                        df_faults.at[idx, 'location_station'] = first_city
                        df_faults.at[idx, 'location_segment'] = f"on {line}"
                        filled_station += 1
                        filled_segment += 1
    
    print(f"  ✅ Filled {filled_station} location_station fields")
    print(f"  ✅ Filled {filled_segment} location_segment fields")
    
    return df_faults


def fill_missing_resolutions(df_faults):
    """
    Fill missing resolution_types based on incident characteristics.
    Strategy:
    1. If resolution is NaN but incident is resolved → infer from delay duration
    2. If still NaN → mark as "UNKNOWN" or "ONGOING"
    """
    print("\n[STEP 0b] Filling missing resolution types...")
    
    filled = 0
    
    for idx, row in df_faults.iterrows():
        if pd.isna(row.get('resolution_types')) or row.get('resolution_types') == '':
            delay_reason = str(row.get('delay_reason', '')).lower()
            
            # Check if resolved
            if 'return' in delay_reason or 'regular' in delay_reason or 'restored' in delay_reason:
                # Infer resolution type based on incident type
                incident_type = row.get('incident_type', '')
                
                if incident_type == 'technical':
                    df_faults.at[idx, 'resolution_types'] = 'TECHNICAL_FIX'
                elif incident_type == 'trespasser':
                    df_faults.at[idx, 'resolution_types'] = 'POLICE_INTERVENTION'
                elif incident_type == 'weather':
                    df_faults.at[idx, 'resolution_types'] = 'WEATHER_CLEARED'
                elif incident_type == 'strike':
                    df_faults.at[idx, 'resolution_types'] = 'STRIKE_ENDED'
                else:
                    df_faults.at[idx, 'resolution_types'] = 'RESOLVED'
                
                df_faults.at[idx, 'has_resolution'] = True
                filled += 1
            else:
                # Mark as ongoing/unknown
                df_faults.at[idx, 'resolution_types'] = 'ONGOING'
                df_faults.at[idx, 'has_resolution'] = False
    
    print(f"  ✅ Filled {filled} resolution_types fields")
    
    return df_faults


def load_data():
    """Load all processed data files."""
    print("Loading processed data...")
    
    # Load fault data
    df_faults = pd.read_csv(PROCESSED_DIR / "fault_data_enriched.csv")
    df_faults['date'] = pd.to_datetime(df_faults['date'])
    print(f"  Faults: {len(df_faults)} records")
    
    # Load station data
    df_stations = pd.read_csv(PROCESSED_DIR / "station_data_enriched.csv")
    print(f"  Stations: {len(df_stations)} records")
    
    # Load mileage data
    df_mileage = pd.read_csv(PROCESSED_DIR / "mileage_data_enriched.csv")
    print(f"  Mileage/Routes: {len(df_mileage)} records")
    
    # Load operation data (sample if too large)
    df_operations = pd.read_csv(PROCESSED_DIR / "operation_data_enriched.csv")
    df_operations['date'] = pd.to_datetime(df_operations['date'])
    print(f"  Operations: {len(df_operations)} records")
    
    return df_faults, df_stations, df_mileage, df_operations


def link_station_coordinates(df_faults, df_stations):
    """
    Link station coordinates to incident locations.
    Fills gap: Station coordinates linked to incidents
    """
    print("\n[STEP 1] Linking station coordinates to incidents...")
    
    # Create station lookup dictionary (normalized name -> coordinates)
    station_coords = {}
    for _, row in df_stations.iterrows():
        name = str(row['name']).upper().strip()
        station_coords[name] = {
            'lat': row['lat'],
            'lon': row['lon'],
            'region': row.get('region_name', 'Unknown')
        }
        # Also add normalized version
        name_normalized = row.get('name_normalized', name)
        if name_normalized:
            station_coords[name_normalized] = station_coords[name]
    
    # Function to find best matching station
    def find_station_coords(location_text):
        if pd.isna(location_text) or not location_text:
            return None, None, None, None
        
        location_text = str(location_text).upper().strip()
        
        # Direct match
        if location_text in station_coords:
            coords = station_coords[location_text]
            return coords['lat'], coords['lon'], location_text, coords['region']
        
        # Partial match - find best match
        best_match = None
        best_score = 0
        
        for station_name, coords in station_coords.items():
            # Check if station name is contained in location text
            if station_name in location_text:
                if len(station_name) > best_score:
                    best_score = len(station_name)
                    best_match = (coords['lat'], coords['lon'], station_name, coords['region'])
            # Check if location text is contained in station name
            elif location_text in station_name:
                if len(location_text) > best_score:
                    best_score = len(location_text)
                    best_match = (coords['lat'], coords['lon'], station_name, coords['region'])
        
        if best_match:
            return best_match
        
        return None, None, None, None
    
    # Apply to each fault record
    incident_lats = []
    incident_lons = []
    matched_stations = []
    matched_regions = []
    
    for idx, row in df_faults.iterrows():
        lat, lon, station, region = None, None, None, None
        
        # Try location_station first
        if pd.notna(row.get('location_station')):
            lat, lon, station, region = find_station_coords(row['location_station'])
        
        # Try location_segment if no match
        if lat is None and pd.notna(row.get('location_segment')):
            # Extract first station from segment (e.g., "Roma - Milano" -> "Roma")
            segment = str(row['location_segment'])
            first_station = segment.split('-')[0].strip()
            lat, lon, station, region = find_station_coords(first_station)
        
        # Try extracting from line name if still no match
        if lat is None and pd.notna(row.get('line')):
            line = str(row['line'])
            # Try first city in line name
            first_city = line.split('-')[0].strip()
            lat, lon, station, region = find_station_coords(first_city)
        
        incident_lats.append(lat)
        incident_lons.append(lon)
        matched_stations.append(station)
        matched_regions.append(region)
    
    df_faults['incident_lat'] = incident_lats
    df_faults['incident_lon'] = incident_lons
    df_faults['matched_station'] = matched_stations
    df_faults['matched_region'] = matched_regions
    
    matched_count = sum(1 for lat in incident_lats if lat is not None)
    print(f"  ✅ Matched {matched_count}/{len(df_faults)} incidents to coordinates ({100*matched_count/len(df_faults):.1f}%)")
    
    return df_faults


def correlate_operations_with_faults(df_faults, df_operations):
    """
    Correlate train operations with fault events.
    Fills gap: Train operation linkage
    """
    print("\n[STEP 2] Correlating operations with fault events...")
    
    # Aggregate operation statistics by date and line
    operation_stats = {}
    
    for date in df_faults['date'].unique():
        date_ops = df_operations[df_operations['date'] == date]
        
        if len(date_ops) == 0:
            continue
        
        # Calculate delay statistics
        for col in ['arrival_delay_min', 'departure_delay_min']:
            if col in date_ops.columns:
                date_ops[col] = pd.to_numeric(date_ops[col], errors='coerce')
        
        stats = {
            'total_operations': len(date_ops),
            'avg_arrival_delay': date_ops['arrival_delay_min'].mean() if 'arrival_delay_min' in date_ops.columns else None,
            'avg_departure_delay': date_ops['departure_delay_min'].mean() if 'departure_delay_min' in date_ops.columns else None,
            'max_arrival_delay': date_ops['arrival_delay_min'].max() if 'arrival_delay_min' in date_ops.columns else None,
            'delayed_trains_count': len(date_ops[date_ops.get('arrival_delay_min', 0) > 5]) if 'arrival_delay_min' in date_ops.columns else 0,
            'on_time_percentage': (len(date_ops[date_ops.get('arrival_delay_min', 0).abs() <= 5]) / len(date_ops) * 100) if len(date_ops) > 0 else 0
        }
        
        operation_stats[pd.Timestamp(date)] = stats
    
    # Link operations to faults
    ops_total = []
    ops_avg_arrival_delay = []
    ops_avg_departure_delay = []
    ops_max_delay = []
    ops_delayed_count = []
    ops_on_time_pct = []
    
    for idx, row in df_faults.iterrows():
        fault_date = row['date']
        
        if fault_date in operation_stats:
            stats = operation_stats[fault_date]
            ops_total.append(stats['total_operations'])
            ops_avg_arrival_delay.append(stats['avg_arrival_delay'])
            ops_avg_departure_delay.append(stats['avg_departure_delay'])
            ops_max_delay.append(stats['max_arrival_delay'])
            ops_delayed_count.append(stats['delayed_trains_count'])
            ops_on_time_pct.append(stats['on_time_percentage'])
        else:
            ops_total.append(None)
            ops_avg_arrival_delay.append(None)
            ops_avg_departure_delay.append(None)
            ops_max_delay.append(None)
            ops_delayed_count.append(None)
            ops_on_time_pct.append(None)
    
    df_faults['ops_total_trains'] = ops_total
    df_faults['ops_avg_arrival_delay'] = ops_avg_arrival_delay
    df_faults['ops_avg_departure_delay'] = ops_avg_departure_delay
    df_faults['ops_max_delay'] = ops_max_delay
    df_faults['ops_delayed_trains'] = ops_delayed_count
    df_faults['ops_on_time_pct'] = ops_on_time_pct
    
    linked_count = sum(1 for x in ops_total if x is not None)
    print(f"  ✅ Linked {linked_count}/{len(df_faults)} faults to operation data ({100*linked_count/len(df_faults):.1f}%)")
    
    return df_faults


def detect_historical_patterns(df_faults):
    """
    Detect historical sequence patterns and recurring issues.
    Fills gap: Historical sequence patterns
    """
    print("\n[STEP 3] Detecting historical sequence patterns...")
    
    # Sort by date
    df_faults = df_faults.sort_values('date').reset_index(drop=True)
    
    # Track patterns by line and incident type
    line_history = defaultdict(list)
    type_history = defaultdict(list)
    location_history = defaultdict(list)
    
    # Calculate pattern features
    days_since_last_same_line = []
    days_since_last_same_type = []
    days_since_last_same_location = []
    incidents_same_line_7days = []
    incidents_same_type_7days = []
    is_recurring_location = []
    recurrence_count = []
    
    for idx, row in df_faults.iterrows():
        current_date = row['date']
        line = row.get('line_normalized', row.get('line', 'Unknown'))
        incident_type = row.get('incident_type', 'unknown')
        location = row.get('location_station') or row.get('location_segment') or 'Unknown'
        
        # Days since last incident on same line
        if line in line_history and line_history[line]:
            last_date = line_history[line][-1]
            days_diff = (current_date - last_date).days
            days_since_last_same_line.append(days_diff)
        else:
            days_since_last_same_line.append(None)
        
        # Days since last incident of same type
        if incident_type in type_history and type_history[incident_type]:
            last_date = type_history[incident_type][-1]
            days_diff = (current_date - last_date).days
            days_since_last_same_type.append(days_diff)
        else:
            days_since_last_same_type.append(None)
        
        # Days since last incident at same location
        if location in location_history and location_history[location]:
            last_date = location_history[location][-1]
            days_diff = (current_date - last_date).days
            days_since_last_same_location.append(days_diff)
        else:
            days_since_last_same_location.append(None)
        
        # Count incidents in last 7 days
        seven_days_ago = current_date - timedelta(days=7)
        
        line_count = sum(1 for d in line_history[line] if d >= seven_days_ago)
        incidents_same_line_7days.append(line_count)
        
        type_count = sum(1 for d in type_history[incident_type] if d >= seven_days_ago)
        incidents_same_type_7days.append(type_count)
        
        # Check if recurring location (>= 2 incidents at same location)
        location_count = len(location_history[location])
        is_recurring_location.append(location_count >= 1)
        recurrence_count.append(location_count)
        
        # Update history
        line_history[line].append(current_date)
        type_history[incident_type].append(current_date)
        location_history[location].append(current_date)
    
    df_faults['days_since_last_same_line'] = days_since_last_same_line
    df_faults['days_since_last_same_type'] = days_since_last_same_type
    df_faults['days_since_last_same_location'] = days_since_last_same_location
    df_faults['incidents_same_line_7days'] = incidents_same_line_7days
    df_faults['incidents_same_type_7days'] = incidents_same_type_7days
    df_faults['is_recurring_location'] = is_recurring_location
    df_faults['recurrence_count'] = recurrence_count
    
    recurring = sum(is_recurring_location)
    print(f"  ✅ Identified {recurring} recurring incidents ({100*recurring/len(df_faults):.1f}%)")
    
    return df_faults


def add_precise_timestamps(df_faults):
    """
    Add precise datetime timestamps by combining date and extracted time.
    Fills gap: Real-time timestamps
    """
    print("\n[STEP 4] Adding precise timestamps...")
    
    precise_timestamps = []
    
    for idx, row in df_faults.iterrows():
        base_date = row['date']
        incident_time = row.get('incident_time')
        
        if pd.notna(incident_time) and incident_time:
            try:
                # Parse time string (e.g., "19:30", "9:30 am", "17:43")
                time_str = str(incident_time).strip()
                
                # Handle various formats
                if ':' in time_str:
                    parts = time_str.replace('am', '').replace('pm', '').strip().split(':')
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                    
                    # Adjust for PM
                    if 'pm' in str(incident_time).lower() and hour < 12:
                        hour += 12
                    
                    # Create precise timestamp
                    if isinstance(base_date, pd.Timestamp):
                        precise_dt = base_date.replace(hour=hour, minute=minute, second=0)
                    else:
                        precise_dt = datetime.combine(base_date, datetime.min.time()).replace(hour=hour, minute=minute)
                    
                    precise_timestamps.append(precise_dt)
                else:
                    precise_timestamps.append(base_date)
            except (ValueError, AttributeError):
                precise_timestamps.append(base_date)
        else:
            # No time available, use date with estimated time based on time_of_day
            time_of_day = row.get('time_of_day', 'unknown')
            estimated_hour = {
                'morning_peak': 8,
                'midday': 13,
                'evening_peak': 18,
                'night': 22
            }.get(time_of_day, 12)
            
            if isinstance(base_date, pd.Timestamp):
                precise_dt = base_date.replace(hour=estimated_hour, minute=0, second=0)
            else:
                precise_dt = datetime.combine(base_date, datetime.min.time()).replace(hour=estimated_hour)
            
            precise_timestamps.append(precise_dt)
    
    df_faults['incident_datetime'] = precise_timestamps
    df_faults['incident_hour'] = [dt.hour if pd.notna(dt) else None for dt in precise_timestamps]
    df_faults['incident_minute'] = [dt.minute if pd.notna(dt) else None for dt in precise_timestamps]
    
    print(f"  ✅ Added precise timestamps to all {len(df_faults)} records")
    
    return df_faults


def create_enhanced_embedding_text(row):
    """Create enriched embedding text with all available context."""
    parts = []
    
    # Incident type and line
    incident_type = row.get('incident_type', 'unknown')
    line = row.get('line_normalized', row.get('line', 'unknown'))
    parts.append(f"{incident_type.replace('_', ' ')} incident on {line}")
    
    # Location with coordinates context
    if pd.notna(row.get('matched_station')):
        parts.append(f"near {row['matched_station']}")
    elif pd.notna(row.get('location_station')):
        parts.append(f"near {row['location_station']}")
    
    if pd.notna(row.get('location_segment')):
        parts.append(f"between {row['location_segment']}")
    
    if pd.notna(row.get('matched_region')):
        parts.append(f"in {row['matched_region']} region")
    
    # Temporal context
    if pd.notna(row.get('incident_datetime')):
        dt = row['incident_datetime']
        if isinstance(dt, (datetime, pd.Timestamp)):
            parts.append(f"on {dt.strftime('%A')} at {dt.strftime('%H:%M')}")
    
    time_of_day = row.get('time_of_day', 'unknown')
    if time_of_day != 'unknown':
        parts.append(f"during {time_of_day.replace('_', ' ')}")
    
    # Impact
    if pd.notna(row.get('delay_duration_min')) and row['delay_duration_min'] > 0:
        parts.append(f"causing {int(row['delay_duration_min'])} minutes delay")
    
    total_affected = row.get('affected_trains_total', 0)
    if total_affected > 0:
        parts.append(f"affecting {total_affected} trains")
    
    # Resolutions
    resolution_types = row.get('resolution_types', '')
    if resolution_types and resolution_types != '' and pd.notna(resolution_types):
        if isinstance(resolution_types, str):
            resolutions = resolution_types.split('|')
            res_text = ', '.join([r.lower().replace('_', ' ') for r in resolutions])
            parts.append(f"resolved by {res_text}")
        elif isinstance(resolution_types, (list, tuple)):
            res_text = ', '.join([str(r).lower().replace('_', ' ') for r in resolution_types])
            parts.append(f"resolved by {res_text}")
    
    # Historical context
    if row.get('is_recurring_location', False):
        parts.append(f"recurring incident at this location (count: {row.get('recurrence_count', 0) + 1})")
    
    if pd.notna(row.get('incidents_same_line_7days')) and row['incidents_same_line_7days'] > 0:
        parts.append(f"{row['incidents_same_line_7days']} similar incidents on this line in past week")
    
    # Severity
    if pd.notna(row.get('severity_score')):
        severity = row['severity_score']
        if severity >= 50:
            parts.append("high severity incident")
        elif severity >= 25:
            parts.append("moderate severity incident")
        else:
            parts.append("low severity incident")
    
    return ". ".join(parts) + "."


def main():
    """Main enrichment pipeline."""
    print("=" * 60)
    print("DATA ENRICHMENT PIPELINE - FILLING GAPS")
    print("=" * 60)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load data
    df_faults, df_stations, df_mileage, df_operations = load_data()
    
    # Step 0: Fill missing location fields FIRST
    df_faults = fill_missing_locations(df_faults)
    
    # Step 0b: Fill missing resolution types
    df_faults = fill_missing_resolutions(df_faults)
    
    # Step 1: Link station coordinates (now with better filled data)
    df_faults = link_station_coordinates(df_faults, df_stations)
    
    # Step 2: Correlate operations with faults
    df_faults = correlate_operations_with_faults(df_faults, df_operations)
    
    # Step 3: Detect historical patterns
    df_faults = detect_historical_patterns(df_faults)
    
    # Step 4: Add precise timestamps
    df_faults = add_precise_timestamps(df_faults)
    
    # Step 5: Create enhanced embedding text
    print("\n[STEP 5] Creating enhanced embedding text...")
    df_faults['embedding_text_enhanced'] = df_faults.apply(create_enhanced_embedding_text, axis=1)
    print(f"  ✅ Generated enhanced embedding text for all {len(df_faults)} records")
    
    # Save enriched data
    print("\n[SAVING] Exporting enriched data...")
    
    # Save as CSV
    df_faults.to_csv(OUTPUT_DIR / "fault_data_enriched_full.csv", index=False)
    
    # Save as JSON (for Qdrant)
    # Convert datetime objects to strings for JSON serialization
    df_json = df_faults.copy()
    for col in df_json.columns:
        if df_json[col].dtype == 'datetime64[ns]' or 'datetime' in str(df_json[col].dtype):
            df_json[col] = df_json[col].astype(str)
    
    df_json.to_json(OUTPUT_DIR / "fault_data_enriched_full.json", orient='records', indent=2)
    
    print(f"\n✅ Enriched data saved to {OUTPUT_DIR}")
    print(f"   - fault_data_enriched_full.csv")
    print(f"   - fault_data_enriched_full.json")
    
    # Print summary
    print("\n" + "=" * 60)
    print("ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"Total incidents: {len(df_faults)}")
    print(f"With location_station: {df_faults['location_station'].notna().sum()}")
    print(f"With location_segment: {df_faults['location_segment'].notna().sum()}")
    print(f"With coordinates: {df_faults['incident_lat'].notna().sum()}")
    print(f"With resolution_types: {(df_faults['resolution_types'].notna() & (df_faults['resolution_types'] != '')).sum()}")
    print(f"With operation linkage: {df_faults['ops_total_trains'].notna().sum()}")
    print(f"Recurring incidents: {df_faults['is_recurring_location'].sum()}")
    print(f"With precise timestamps: {df_faults['incident_datetime'].notna().sum()}")
    
    return df_faults


if __name__ == "__main__":
    main()
