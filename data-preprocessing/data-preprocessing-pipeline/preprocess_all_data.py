"""
AI Rail Network Brain - Comprehensive Data Preprocessing Pipeline
==================================================================
This script performs all data preprocessing tasks:
1. Load and clean raw data (encoding, dates, missing values)
2. Extract features from incident text (Italian → English)
3. Extract implicit resolutions from narratives
4. Calculate severity scores
5. Process operation data (delays, running times, stop times)
6. Add contextual features (holidays, day of week)
7. Export enriched data for Qdrant ingestion

Integrates functionality from:
- Add_actual_running_time.py
- Add_actual_stop_time.py
- Add_scheduled_running_time.py
- Add_scheduled_stop_time.py
- Add_holiday.py
- Add_week.py
- Calculate_arrival_delay_time.py
- Calculate_departure_delay_time.py

Author: AI Rail Network Brain Team
Date: January 2026
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime
from pathlib import Path
from collections import Counter
import json
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = Path(__file__).parent.parent / "Data"
OUTPUT_DIR = Path(__file__).parent.parent / "Data" / "Processed"

# Italian holidays in 2024
ITALIAN_HOLIDAYS_2024 = [
    '2024-01-01',  # New Year's Day
    '2024-01-06',  # Epiphany
    '2024-03-31',  # Easter Sunday
    '2024-04-01',  # Easter Monday
    '2024-04-25',  # Liberation Day
    '2024-05-01',  # Labour Day
    '2024-06-02',  # Republic Day
    '2024-08-15',  # Assumption of Mary
    '2024-11-01',  # All Saints' Day
    '2024-12-08',  # Immaculate Conception
    '2024-12-25',  # Christmas Day
    '2024-12-26',  # St. Stephen's Day
]

# Italian to English mappings for incident types
INCIDENT_TYPE_PATTERNS = {
    'technical': [
        r'inconveniente tecnico',
        r'technical inconvenience',
        r'guasto',
        r'technical failure',
        r'technical checks',
        r'controlli tecnici'
    ],
    'weather': [
        r'maltempo',
        r'pioggia',
        r'neve',
        r'adverse weather',
        r'weather conditions',
        r'condizioni meteo'
    ],
    'trespasser': [
        r'investimento.*persona',
        r'investment of a person',
        r'persone.*binari',
        r'unauthorized people',
        r'presenza di persone',
        r'people near the tracks'
    ],
    'equipment_failure': [
        r'guasto',
        r'failure',
        r'malfunzionamento',
        r'breakdown'
    ],
    'maintenance': [
        r'manutenzione',
        r'maintenance',
        r'lavori',
        r'works',
        r'infrastructure strengthening'
    ],
    'police_intervention': [
        r'intervento.*polizia',
        r'police',
        r'forze dell\'ordine',
        r'authorities'
    ],
    'fire': [
        r'incendio',
        r'fire',
        r'fuoco'
    ],
    'accident': [
        r'incidente',
        r'accident',
        r'collision',
        r'impatto'
    ]
}

# Resolution action patterns (Italian and English)
RESOLUTION_PATTERNS = {
    'REROUTE': [
        r'deviat[io].*alternativ',
        r'deflected on alternative',
        r'treni.*deviati',
        r'trains.*deflected',
        r'instradati via',
        r'sent.*via.*line',
        r'unrelated.*conventional',
        r'conventional line'
    ],
    'BUS_BRIDGE': [
        r'servizio sostitutivo.*bus',
        r'bus.*sostitutiv',
        r'replacement.*bus',
        r'bus service',
        r'autobus.*sostitu'
    ],
    'CANCEL': [
        r'treno cancellato',
        r'train.*canceled',
        r'soppresso',
        r'deleted',
        r'regional.*canceled',
        r'cancellations'
    ],
    'SPEED_REGULATE': [
        r'rallentamenti.*(\d+).*min',
        r'slowdowns.*(\d+)',
        r'velocità ridotta',
        r'reduced speed',
        r'marcia a vista',
        r'slowdowns up to'
    ],
    'SHORT_TURN': [
        r'limitato a',
        r'limited to',
        r'ends the race to',
        r'termine.*modificat'
    ],
    'HOLD': [
        r'in attesa',
        r'fermo in stazione',
        r'sosta prolungata',
        r'stopped in line',
        r'stationary train'
    ],
    'SINGLE_TRACK': [
        r'binario unico',
        r'single track',
        r'only track',
        r'managed on.*track'
    ],
    'GRADUAL_RECOVERY': [
        r'graduale ripresa',
        r'gradually resumed',
        r'gradual recovery',
        r'progressivamente'
    ]
}

# Location extraction patterns
LOCATION_PATTERNS = {
    'between_stations': [
        r'tra\s+(\w+(?:\s+\w+)?)\s+e\s+(\w+(?:\s+\w+)?)',
        r'between\s+(\w+(?:\s+\w+)?)\s+and\s+(\w+(?:\s+\w+)?)'
    ],
    'near_station': [
        r'presso\s+(\w+(?:\s+\w+)?)',
        r'near\s+(\w+(?:\s+\w+)?)',
        r'vicino\s+(\w+(?:\s+\w+)?)'
    ],
    'direction': [
        r'direzione\s+(\w+)',
        r'towards\s+(\w+)',
        r'direction\s+(\w+)'
    ]
}

# Region mapping
REGION_MAPPING = {
    1: 'Piedmont',
    2: 'Aosta Valley',
    3: 'Lombardy',
    4: 'Trentino-Alto Adige/South Tyrol',
    5: 'Veneto',
    6: 'Friuli Venezia Giulia',
    7: 'Liguria',
    8: 'Emilia-Romagna',
    9: 'Tuscany',
    10: 'Umbria',
    11: 'Marche',
    12: 'Lazio',
    13: 'Abruzzo',
    14: 'Molise',
    15: 'Campania',
    16: 'Apulia',
    17: 'Basilicata',
    18: 'Calabria',
    19: 'Sicily',
    20: 'Sardinia'
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def time_to_minutes(time_str):
    """Convert time string (HH:MM) to minutes since midnight"""
    try:
        if pd.isna(time_str) or time_str == '0' or time_str == 0:
            return None
        if not isinstance(time_str, str):
            time_str = str(time_str)
        
        # Handle various formats
        time_str = time_str.strip()
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) >= 2:
                hours = int(parts[0])
                minutes = int(parts[1])
                return hours * 60 + minutes
        return None
    except (ValueError, AttributeError):
        return None


def safe_convert_time(time_str):
    """Safely convert time string to datetime for calculations"""
    try:
        if pd.isna(time_str) or time_str == '0' or time_str == 0:
            return None
        return pd.to_datetime(time_str, format='%H:%M', errors='coerce')
    except (ValueError, TypeError):
        return None


def classify_time_of_day(time_str):
    """Classify time into periods: morning_peak, midday, evening_peak, night"""
    try:
        if isinstance(time_str, str):
            time_match = re.search(r'(\d{1,2})[:\.](\d{2})', time_str)
            if time_match:
                hour = int(time_match.group(1))
            else:
                return 'unknown'
        elif isinstance(time_str, (int, float)) and not pd.isna(time_str):
            hour = int(time_str) // 60  # If already in minutes
        else:
            return 'unknown'
        
        if 6 <= hour < 10:
            return 'morning_peak'
        elif 10 <= hour < 16:
            return 'midday'
        elif 16 <= hour < 20:
            return 'evening_peak'
        else:
            return 'night'
    except:
        return 'unknown'


# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def load_fault_data(filepath):
    """Load and clean Train_fault_information.csv"""
    print("Loading Train_fault_information.csv...")
    
    try:
        df = pd.read_csv(filepath, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, encoding='latin-1')
    
    # Clean column names
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # Parse dates - handle multiple formats
    df['date'] = pd.to_datetime(df['date'], format='%Y/%m/%d', errors='coerce')
    
    # Parse delay duration
    df['delay_duration_min'] = df['delay_duration'].apply(parse_delay_duration)
    
    # Handle missing values
    df['delay_reason'] = df['delay_reason'].fillna('')
    df['line'] = df['line'].fillna('Unknown')
    
    # Normalize line names
    df['line_normalized'] = df['line'].apply(normalize_line_name)
    
    print(f"  Loaded {len(df)} fault records")
    return df


def load_station_data(filepath):
    """Load and clean Train_station_locations_data.csv"""
    print("Loading Train_station_locations_data.csv...")
    
    try:
        df = pd.read_csv(filepath, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, encoding='latin-1')
    
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # Normalize station names
    df['name_normalized'] = df['name'].str.upper().str.strip()
    
    # Validate coordinates (Italy bounds)
    df = df[(df['lat'].between(35, 48)) & (df['lon'].between(6, 19))]
    
    # Add region names
    if 'id_region' in df.columns:
        df['region_name'] = df['id_region'].map(REGION_MAPPING)
    
    print(f"  Loaded {len(df)} station records")
    return df


def load_mileage_data(filepath):
    """Load and clean Adjacent_railway_stations_mileage_data.csv"""
    print("Loading Adjacent_railway_stations_mileage_data.csv...")
    
    try:
        df = pd.read_csv(filepath, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, encoding='latin-1')
    
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # Extract train type from train_id
    df['train_type'] = df['train_id'].apply(extract_train_type_from_id)
    
    # Normalize station names
    df['station_name_normalized'] = df['station_name'].str.upper().str.strip()
    
    print(f"  Loaded {len(df)} route-station records")
    return df


def load_operation_data(filepath):
    """Load and clean Train_operation_data.csv"""
    print("Loading Train_operation_data.csv...")
    
    try:
        df = pd.read_csv(filepath, encoding='utf-8', low_memory=False)
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        print(f"  Loaded {len(df)} operation records")
        return df
    except FileNotFoundError:
        print(f"  Warning: File not found: {filepath}")
        return None
    except Exception as e:
        print(f"  Warning: Could not load operation data: {e}")
        return None


# ============================================================================
# PARSING FUNCTIONS
# ============================================================================

def parse_delay_duration(duration_str):
    """Parse delay duration string to minutes (integer)"""
    if pd.isna(duration_str) or duration_str == '':
        return None
    
    duration_str = str(duration_str).lower().strip()
    
    # Handle "UTI" or unknown values
    if 'uti' in duration_str or duration_str in ['', 'nan', 'unknown']:
        return None
    
    # Extract number from string like "40 min", "40min", "40"
    match = re.search(r'(\d+)', duration_str)
    if match:
        return int(match.group(1))
    
    return None


def normalize_line_name(line_name):
    """Normalize line names for consistency"""
    if pd.isna(line_name):
        return 'Unknown'
    
    line_name = str(line_name).strip()
    
    # Remove common prefixes
    line_name = re.sub(r'^(Via:\s*RFI\s*(Line)?:?\s*)', '', line_name, flags=re.IGNORECASE)
    line_name = re.sub(r'^(Notices of \d+/\d+/\d+ Trenitalia RFI\s*(Line)?:?\s*)', '', line_name, flags=re.IGNORECASE)
    
    # Standardize separators
    line_name = re.sub(r'\s*[-–—]\s*', ' - ', line_name)
    
    # Remove "High Speed ??" artifacts
    line_name = re.sub(r'\?\?', '', line_name)
    line_name = re.sub(r'High Speed\s+', 'High Speed ', line_name)
    
    # Clean up whitespace
    line_name = ' '.join(line_name.split())
    
    return line_name.strip()


def extract_train_type_from_id(train_id):
    """Extract train type from train_id prefix"""
    if pd.isna(train_id):
        return 'unknown'
    
    train_id = str(train_id).upper()
    
    if train_id.startswith('IC_'):
        return 'intercity'
    elif train_id.startswith('REG_') or train_id.startswith('R_'):
        return 'regional'
    elif train_id.startswith('EC_'):
        return 'eurocity'
    elif train_id.startswith('AV_') or train_id.startswith('FR_'):
        return 'high_speed'
    elif train_id.startswith('RV_'):
        return 'fast_regional'
    else:
        return 'other'


# ============================================================================
# FEATURE EXTRACTION FUNCTIONS
# ============================================================================

def extract_incident_type(text):
    """Extract incident type from text using pattern matching"""
    if pd.isna(text) or text == '':
        return 'unknown'
    
    text_lower = str(text).lower()
    
    for incident_type, patterns in INCIDENT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return incident_type
    
    return 'other'


def extract_resolutions(text):
    """Extract resolution actions from incident text"""
    if pd.isna(text) or text == '':
        return []
    
    text_lower = str(text).lower()
    resolutions = []
    
    for resolution_type, patterns in RESOLUTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                resolution = {'type': resolution_type}
                
                # Extract duration for speed regulation
                if resolution_type == 'SPEED_REGULATE':
                    duration_match = re.search(r'(\d+)\s*min', text_lower)
                    if duration_match:
                        resolution['duration_min'] = int(duration_match.group(1))
                
                resolutions.append(resolution)
                break  # Only add each type once
    
    return resolutions


def extract_location_info(text):
    """Extract location information from text"""
    if pd.isna(text) or text == '':
        return {'segment': None, 'station': None, 'direction': None}
    
    text_str = str(text)
    location = {'segment': None, 'station': None, 'direction': None}
    
    # Try to find "between X and Y" pattern
    for pattern in LOCATION_PATTERNS['between_stations']:
        match = re.search(pattern, text_str, re.IGNORECASE)
        if match:
            location['segment'] = f"{match.group(1)} - {match.group(2)}"
            break
    
    # Try to find "near X" pattern
    for pattern in LOCATION_PATTERNS['near_station']:
        match = re.search(pattern, text_str, re.IGNORECASE)
        if match:
            location['station'] = match.group(1)
            break
    
    # Try to find direction
    for pattern in LOCATION_PATTERNS['direction']:
        match = re.search(pattern, text_str, re.IGNORECASE)
        if match:
            location['direction'] = match.group(1)
            break
    
    return location


def extract_affected_trains(text):
    """Extract information about affected trains from text"""
    if pd.isna(text) or text == '':
        return {'high_speed': 0, 'intercity': 0, 'regional': 0, 'total': 0}
    
    text_lower = str(text).lower()
    affected = {'high_speed': 0, 'intercity': 0, 'regional': 0, 'total': 0}
    
    # Extract counts for each train type
    hs_match = re.search(r'(\d+)\s*(?:high.?speed|alta velocit)', text_lower)
    if hs_match:
        affected['high_speed'] = int(hs_match.group(1))
    
    ic_match = re.search(r'(\d+)\s*(?:intercity|IC)', text_lower, re.IGNORECASE)
    if ic_match:
        affected['intercity'] = int(ic_match.group(1))
    
    reg_match = re.search(r'(\d+)\s*regional', text_lower)
    if reg_match:
        affected['regional'] = int(reg_match.group(1))
    
    affected['total'] = affected['high_speed'] + affected['intercity'] + affected['regional']
    
    return affected


def extract_time_from_text(text):
    """Extract incident start time from text"""
    if pd.isna(text) or text == '':
        return None
    
    patterns = [
        r'from\s+(\d{1,2}[:\.]?\d{2})\s*(?:am|pm)?',
        r'dalle\s+(?:ore\s+)?(\d{1,2}[:\.]?\d{2})',
        r'(\d{1,2}[:\.]?\d{2})\s*(?:am|pm)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, str(text), re.IGNORECASE)
        if match:
            return match.group(1).replace('.', ':')
    
    return None


def calculate_severity_score(row):
    """Calculate severity score (0-100)"""
    score = 0
    
    # Delay duration component (40%)
    if pd.notna(row.get('delay_duration_min')):
        delay_score = min(row['delay_duration_min'] / 180 * 100, 100)
        score += delay_score * 0.4
    
    # Affected trains component (30%)
    affected_count = row.get('affected_trains_total', 0)
    if affected_count > 0:
        trains_score = min(affected_count / 50 * 100, 100)
        score += trains_score * 0.3
    
    # Peak hour component (20%)
    time_of_day = row.get('time_of_day', 'unknown')
    if time_of_day in ['morning_peak', 'evening_peak']:
        score += 100 * 0.2
    elif time_of_day == 'midday':
        score += 50 * 0.2
    
    # High speed line component (10%)
    line = str(row.get('line', '')).lower()
    if 'high speed' in line or 'alta velocit' in line:
        score += 100 * 0.1
    elif 'intercity' in line:
        score += 50 * 0.1
    
    return round(score, 2)


def is_high_speed_line(line_name):
    """Check if line is a high-speed line"""
    if pd.isna(line_name):
        return False
    line_lower = str(line_name).lower()
    return 'high speed' in line_lower or 'alta velocit' in line_lower


def create_embedding_text(row):
    """Create a clean English text for embedding"""
    parts = []
    
    # Incident type
    incident_type = row.get('incident_type', 'unknown')
    parts.append(f"{incident_type.replace('_', ' ')} incident")
    
    # Line
    line = row.get('line_normalized', 'unknown line')
    parts.append(f"on {line}")
    
    # Location
    if pd.notna(row.get('location_segment')):
        parts.append(f"between {row['location_segment']}")
    elif pd.notna(row.get('location_station')):
        parts.append(f"near {row['location_station']}")
    
    # Duration
    if pd.notna(row.get('delay_duration_min')):
        parts.append(f"causing {int(row['delay_duration_min'])} minutes delay")
    
    # Affected trains
    total_affected = row.get('affected_trains_total', 0)
    if total_affected > 0:
        parts.append(f"affecting {total_affected} trains")
    
    # Resolutions
    resolution_types = row.get('resolution_types', [])
    if resolution_types:
        res_str = ', '.join([r.replace('_', ' ').lower() for r in resolution_types])
        parts.append(f"resolved by {res_str}")
    
    # Time context
    time_of_day = row.get('time_of_day', 'unknown')
    if time_of_day != 'unknown':
        parts.append(f"during {time_of_day.replace('_', ' ')}")
    
    return '. '.join(parts) + '.'


# ============================================================================
# OPERATION DATA PROCESSING (From existing scripts)
# ============================================================================

def add_holiday_flag(df):
    """Add holiday flag to dataframe (from Add_holiday.py)"""
    if 'date' not in df.columns:
        return df
    
    print("  Adding holiday flags...")
    
    # Convert holidays to datetime
    holidays = pd.to_datetime(ITALIAN_HOLIDAYS_2024)
    
    # Ensure date column is datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Add holiday flag
    df['is_holiday'] = df['date'].isin(holidays)
    
    return df


def add_day_of_week(df):
    """Add day of week to dataframe (from Add_week.py)"""
    if 'date' not in df.columns:
        return df
    
    print("  Adding day of week...")
    
    # Ensure date column is datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Add day of week (1=Monday, 7=Sunday)
    df['day_of_week_num'] = df['date'].dt.dayofweek + 1
    df['day_of_week'] = df['date'].dt.day_name()
    df['is_weekend'] = df['date'].dt.dayofweek >= 5
    
    return df


def calculate_arrival_delay(df):
    """Calculate arrival delay in minutes (from Calculate_arrival_delay_time.py)"""
    if 'actual_arrival_time' not in df.columns or 'scheduled_arrival_time' not in df.columns:
        return df
    
    print("  Calculating arrival delays...")
    
    try:
        actual_arrival = pd.to_datetime(df['actual_arrival_time'], format='%H:%M', errors='coerce')
        scheduled_arrival = pd.to_datetime(df['scheduled_arrival_time'], format='%H:%M', errors='coerce')
        
        # Calculate delay in minutes
        arrival_delay = (actual_arrival - scheduled_arrival).dt.total_seconds() / 60
        df['arrival_delay_min'] = arrival_delay.round(1)
    except Exception as e:
        print(f"    Warning: Could not calculate arrival delay: {e}")
    
    return df


def calculate_departure_delay(df):
    """Calculate departure delay in minutes (from Calculate_departure_delay_time.py)"""
    if 'actual_departure_time' not in df.columns or 'scheduled_departure_time' not in df.columns:
        return df
    
    print("  Calculating departure delays...")
    
    try:
        actual_departure = pd.to_datetime(df['actual_departure_time'], format='%H:%M', errors='coerce')
        scheduled_departure = pd.to_datetime(df['scheduled_departure_time'], format='%H:%M', errors='coerce')
        
        # Calculate delay in minutes
        departure_delay = (actual_departure - scheduled_departure).dt.total_seconds() / 60
        df['departure_delay_min'] = departure_delay.round(1)
    except Exception as e:
        print(f"    Warning: Could not calculate departure delay: {e}")
    
    return df


def calculate_scheduled_stop_time(df):
    """Calculate scheduled stop time at each station (from Add_scheduled_stop_time.py)"""
    if 'scheduled_arrival_time' not in df.columns or 'scheduled_departure_time' not in df.columns:
        return df
    
    print("  Calculating scheduled stop times...")
    
    def calc_stop_time(row):
        arrival_min = time_to_minutes(row.get('scheduled_arrival_time'))
        departure_min = time_to_minutes(row.get('scheduled_departure_time'))
        
        if arrival_min is None or departure_min is None:
            return None
        
        return departure_min - arrival_min
    
    df['scheduled_stop_time_min'] = df.apply(calc_stop_time, axis=1)
    
    return df


def calculate_actual_stop_time(df):
    """Calculate actual stop time at each station (from Add_actual_stop_time.py)"""
    if 'actual_arrival_time' not in df.columns or 'actual_departure_time' not in df.columns:
        return df
    
    print("  Calculating actual stop times...")
    
    def calc_stop_time(row):
        arrival_min = time_to_minutes(row.get('actual_arrival_time'))
        departure_min = time_to_minutes(row.get('actual_departure_time'))
        
        if arrival_min is None or departure_min is None:
            return None
        
        return departure_min - arrival_min
    
    df['actual_stop_time_min'] = df.apply(calc_stop_time, axis=1)
    
    return df


def calculate_scheduled_running_time(df):
    """Calculate scheduled running time between stations (from Add_scheduled_running_time.py)"""
    if 'scheduled_arrival_time' not in df.columns or 'scheduled_departure_time' not in df.columns:
        return df
    
    if 'station_order' not in df.columns:
        return df
    
    print("  Calculating scheduled running times...")
    
    # Reset index for safe iteration
    df = df.reset_index(drop=True)
    
    # Convert times to minutes
    df['_sched_arr_min'] = df['scheduled_arrival_time'].apply(time_to_minutes)
    df['_sched_dep_min'] = df['scheduled_departure_time'].apply(time_to_minutes)
    
    # Initialize running time column
    df['scheduled_running_time_min'] = 0.0
    
    # Calculate running time (arrival at current - departure from previous)
    for i in range(1, len(df)):
        if df.loc[i, 'station_order'] != 1:
            curr_arrival = df.loc[i, '_sched_arr_min']
            prev_departure = df.loc[i-1, '_sched_dep_min']
            
            if curr_arrival is not None and prev_departure is not None:
                df.loc[i, 'scheduled_running_time_min'] = curr_arrival - prev_departure
    
    # Remove temporary columns
    df.drop(columns=['_sched_arr_min', '_sched_dep_min'], inplace=True, errors='ignore')
    
    return df


def calculate_actual_running_time(df):
    """Calculate actual running time between stations (from Add_actual_running_time.py)"""
    if 'actual_arrival_time' not in df.columns or 'actual_departure_time' not in df.columns:
        return df
    
    if 'station_order' not in df.columns:
        return df
    
    print("  Calculating actual running times...")
    
    # Reset index for safe iteration
    df = df.reset_index(drop=True)
    
    df['actual_running_time_min'] = None
    
    for i in range(len(df)):
        if df.loc[i, 'station_order'] == 1:
            df.loc[i, 'actual_running_time_min'] = 0
        elif i > 0:
            current_arrival = safe_convert_time(df.loc[i, 'actual_arrival_time'])
            
            if pd.notna(current_arrival):
                # Find previous departure
                j = i - 1
                while j >= 0:
                    prev_departure = safe_convert_time(df.loc[j, 'actual_departure_time'])
                    if pd.notna(prev_departure):
                        running_time = (current_arrival - prev_departure).total_seconds() / 60
                        df.loc[i, 'actual_running_time_min'] = round(running_time, 1)
                        break
                    j -= 1
    
    return df


# ============================================================================
# ENRICHMENT PIPELINE
# ============================================================================

def enrich_fault_data(df):
    """Apply all feature extraction to fault data"""
    print("\nEnriching fault data with extracted features...")
    
    # Extract incident type
    print("  Extracting incident types...")
    df['incident_type'] = df['delay_reason'].apply(extract_incident_type)
    
    # Extract resolutions
    print("  Extracting implicit resolutions...")
    df['resolutions_extracted'] = df['delay_reason'].apply(extract_resolutions)
    df['resolution_types'] = df['resolutions_extracted'].apply(
        lambda x: [r['type'] for r in x] if x else []
    )
    df['has_resolution'] = df['resolutions_extracted'].apply(lambda x: len(x) > 0)
    
    # Extract location info
    print("  Extracting location information...")
    location_info = df['delay_reason'].apply(extract_location_info)
    df['location_segment'] = location_info.apply(lambda x: x['segment'])
    df['location_station'] = location_info.apply(lambda x: x['station'])
    df['location_direction'] = location_info.apply(lambda x: x['direction'])
    
    # Extract affected trains
    print("  Extracting affected train counts...")
    affected_info = df['delay_reason'].apply(extract_affected_trains)
    df['affected_trains_high_speed'] = affected_info.apply(lambda x: x['high_speed'])
    df['affected_trains_intercity'] = affected_info.apply(lambda x: x['intercity'])
    df['affected_trains_regional'] = affected_info.apply(lambda x: x['regional'])
    df['affected_trains_total'] = affected_info.apply(lambda x: x['total'])
    
    # Extract time and classify
    print("  Extracting incident times...")
    df['incident_time'] = df['delay_reason'].apply(extract_time_from_text)
    df['time_of_day'] = df['incident_time'].apply(classify_time_of_day)
    
    # Add temporal features
    df = add_day_of_week(df)
    df = add_holiday_flag(df)
    
    # Check if high-speed line
    df['is_high_speed_line'] = df['line'].apply(is_high_speed_line)
    
    # Calculate severity score
    print("  Calculating severity scores...")
    df['severity_score'] = df.apply(calculate_severity_score, axis=1)
    
    # Create text for embedding
    print("  Creating embedding text...")
    df['embedding_text'] = df.apply(create_embedding_text, axis=1)
    
    return df


def enrich_operation_data(df):
    """Apply all processing to operation data"""
    if df is None or df.empty:
        return df
    
    print("\nEnriching operation data...")
    
    # Add temporal features
    df = add_day_of_week(df)
    df = add_holiday_flag(df)
    
    # Calculate delays
    df = calculate_arrival_delay(df)
    df = calculate_departure_delay(df)
    
    # Calculate stop times
    df = calculate_scheduled_stop_time(df)
    df = calculate_actual_stop_time(df)
    
    # Calculate running times (only if station_order exists)
    if 'station_order' in df.columns:
        df = calculate_scheduled_running_time(df)
        df = calculate_actual_running_time(df)
    
    return df


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def export_processed_data(df_faults, df_stations, df_mileage, df_operations, output_dir):
    """Export all processed data to CSV and JSON formats"""
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nExporting processed data to {output_dir}...")
    
    # Export enriched fault data
    print("  Exporting fault data...")
    df_faults_csv = df_faults.copy()
    df_faults_csv['resolution_types'] = df_faults_csv['resolution_types'].apply(
        lambda x: '|'.join(x) if x else ''
    )
    df_faults_csv['resolutions_extracted'] = df_faults_csv['resolutions_extracted'].apply(str)
    df_faults_csv.to_csv(output_dir / 'fault_data_enriched.csv', index=False, encoding='utf-8')
    
    # JSON version
    df_faults.to_json(output_dir / 'fault_data_enriched.json', orient='records', 
                      date_format='iso', indent=2)
    
    # Export station data
    if df_stations is not None and not df_stations.empty:
        print("  Exporting station data...")
        df_stations.to_csv(output_dir / 'station_data_enriched.csv', index=False, encoding='utf-8')
    
    # Export mileage data
    if df_mileage is not None and not df_mileage.empty:
        print("  Exporting mileage data...")
        df_mileage.to_csv(output_dir / 'mileage_data_enriched.csv', index=False, encoding='utf-8')
    
    # Export operation data
    if df_operations is not None and not df_operations.empty:
        print("  Exporting operation data...")
        df_operations.to_csv(output_dir / 'operation_data_enriched.csv', index=False, encoding='utf-8')
    
    # Export summary statistics
    print("  Generating summary statistics...")
    export_summary_stats(df_faults, output_dir)
    
    print("  Export complete!")


def export_summary_stats(df, output_dir):
    """Export summary statistics about the processed data"""
    
    stats = {
        'total_incidents': len(df),
        'date_range': {
            'start': str(df['date'].min()) if pd.notna(df['date'].min()) else None,
            'end': str(df['date'].max()) if pd.notna(df['date'].max()) else None
        },
        'incident_types': df['incident_type'].value_counts().to_dict(),
        'resolution_coverage': {
            'with_resolution': int(df['has_resolution'].sum()),
            'without_resolution': int((~df['has_resolution']).sum()),
            'coverage_percentage': round(df['has_resolution'].mean() * 100, 2)
        },
        'resolution_types': {},
        'severity_stats': {
            'mean': round(df['severity_score'].mean(), 2) if pd.notna(df['severity_score'].mean()) else None,
            'median': round(df['severity_score'].median(), 2) if pd.notna(df['severity_score'].median()) else None,
            'max': round(df['severity_score'].max(), 2) if pd.notna(df['severity_score'].max()) else None
        },
        'delay_stats': {
            'mean_minutes': round(df['delay_duration_min'].mean(), 2) if pd.notna(df['delay_duration_min'].mean()) else None,
            'median_minutes': round(df['delay_duration_min'].median(), 2) if pd.notna(df['delay_duration_min'].median()) else None,
            'max_minutes': int(df['delay_duration_min'].max()) if pd.notna(df['delay_duration_min'].max()) else None
        },
        'time_of_day_distribution': df['time_of_day'].value_counts().to_dict(),
        'lines_affected': int(df['line_normalized'].nunique())
    }
    
    # Count resolution types
    all_resolutions = []
    for res_list in df['resolution_types']:
        if res_list:
            all_resolutions.extend(res_list)
    stats['resolution_types'] = dict(Counter(all_resolutions))
    
    # Save as JSON
    with open(output_dir / 'preprocessing_summary.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*60)
    print("PREPROCESSING SUMMARY")
    print("="*60)
    print(f"Total incidents processed: {stats['total_incidents']}")
    print(f"Date range: {stats['date_range']['start']} to {stats['date_range']['end']}")
    print(f"\nIncident types found:")
    for itype, count in sorted(stats['incident_types'].items(), key=lambda x: -x[1]):
        print(f"  - {itype}: {count}")
    print(f"\nResolution extraction coverage: {stats['resolution_coverage']['coverage_percentage']}%")
    print(f"\nResolution types extracted:")
    for rtype, count in sorted(stats['resolution_types'].items(), key=lambda x: -x[1]):
        print(f"  - {rtype}: {count}")
    if stats['severity_stats']['mean']:
        print(f"\nSeverity score: mean={stats['severity_stats']['mean']}, max={stats['severity_stats']['max']}")
    if stats['delay_stats']['mean_minutes']:
        print(f"Delay duration: mean={stats['delay_stats']['mean_minutes']} min, max={stats['delay_stats']['max_minutes']} min")
    print("="*60)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main preprocessing pipeline"""
    print("="*60)
    print("AI RAIL NETWORK BRAIN - DATA PREPROCESSING PIPELINE")
    print("="*60)
    
    # Load data
    print("\n[STEP 1] Loading raw data...")
    
    df_faults = load_fault_data(DATA_DIR / 'Train_fault_information.csv')
    df_stations = load_station_data(DATA_DIR / 'Train_station_locations_data.csv')
    df_mileage = load_mileage_data(DATA_DIR / 'Adjacent_railway_stations_mileage_data.csv')
    df_operations = load_operation_data(DATA_DIR / 'Train_operation_data.csv')
    
    # Enrich fault data
    print("\n[STEP 2] Enriching fault data...")
    df_faults = enrich_fault_data(df_faults)
    
    # Enrich operation data
    print("\n[STEP 3] Enriching operation data...")
    df_operations = enrich_operation_data(df_operations)
    
    # Export processed data
    print("\n[STEP 4] Exporting processed data...")
    export_processed_data(df_faults, df_stations, df_mileage, df_operations, OUTPUT_DIR)
    
    print("\n[COMPLETE] Preprocessing pipeline finished successfully!")
    print(f"Output files saved to: {OUTPUT_DIR}")
    
    return df_faults, df_stations, df_mileage, df_operations


if __name__ == '__main__':
    df_faults, df_stations, df_mileage, df_operations = main()
