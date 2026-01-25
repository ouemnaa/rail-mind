"""
Rail Network Graph Configuration
================================
Configuration settings for the graph network module.
"""

from pathlib import Path

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
PROCESSED_DIR = DATA_DIR / "Processed"
OUTPUT_DIR = Path(__file__).parent / "output"

# Input files
STATION_DATA = PROCESSED_DIR / "station_data_enriched.csv"
MILEAGE_DATA = PROCESSED_DIR / "mileage_data_enriched.csv"
FAULT_DATA = PROCESSED_DIR / "fault_data_enriched.csv"
OPERATION_DATA = PROCESSED_DIR / "operation_data_enriched.csv"

# ============================================================================
# GRAPH CONFIGURATION
# ============================================================================

GRAPH_CONFIG = {
    # Node types
    'node_types': ['station', 'junction', 'depot'],
    
    # Edge types (track types)
    'edge_types': {
        'high_speed': {'max_speed': 300, 'capacity': 12},  # trains per hour
        'conventional': {'max_speed': 160, 'capacity': 8},
        'regional': {'max_speed': 120, 'capacity': 6},
        'metro': {'max_speed': 80, 'capacity': 20},
    },
    
    # Conflict detection thresholds
    'conflict_thresholds': {
        'capacity_warning': 0.7,   # 70% capacity = warning
        'capacity_critical': 0.9,  # 90% capacity = critical
        'delay_cascade_min': 15,   # min delay (minutes) to consider cascade
        'proximity_km': 50,        # km radius for nearby incident check
    },
    
    # Simulation parameters
    'simulation': {
        'time_step_minutes': 5,
        'max_propagation_hops': 5,
        'delay_decay_factor': 0.8,  # delay reduces by 20% per hop
    },
    
    # Resolution strategies
    'resolution_strategies': [
        'SPEED_REGULATE',
        'REROUTE',
        'CANCEL',
        'SHORT_TURN',
        'BUS_BRIDGE',
        'SINGLE_TRACK',
        'HOLD',
        'GRADUAL_RECOVERY',
    ],
}

# ============================================================================
# ITALIAN REGIONS FOR GEOGRAPHIC GROUPING
# ============================================================================

ITALIAN_REGIONS = {
    'North': ['Piedmont', 'Lombardy', 'Veneto', 'Liguria', 'Emilia-Romagna', 
              'Friuli-Venezia Giulia', 'Trentino-Alto Adige', "Valle d'Aosta"],
    'Central': ['Tuscany', 'Lazio', 'Umbria', 'Marche', 'Abruzzo'],
    'South': ['Campania', 'Apulia', 'Calabria', 'Basilicata', 'Molise'],
    'Islands': ['Sicily', 'Sardinia'],
}

# ============================================================================
# MAJOR ITALIAN RAILWAY HUBS
# ============================================================================

MAJOR_HUBS = [
    'ROMA TERMINI',
    'MILANO CENTRALE',
    'NAPOLI CENTRALE',
    'TORINO PORTA NUOVA',
    'FIRENZE SANTA MARIA NOVELLA',
    'BOLOGNA CENTRALE',
    'VENEZIA SANTA LUCIA',
    'GENOVA PIAZZA PRINCIPE',
    'VERONA PORTA NUOVA',
    'PALERMO CENTRALE',
]
