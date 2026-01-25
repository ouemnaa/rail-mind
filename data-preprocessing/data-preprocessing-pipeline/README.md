# Data Preprocessing Pipeline - README

## AI Rail Network Brain - Data Preprocessing Module

This module performs comprehensive data preprocessing for the AI Rail Network Brain project, transforming raw Italian railway data into enriched, analysis-ready datasets for Qdrant vector database ingestion.

---

## 🎯 Quick Start

```bash
# 1. Run preprocessing pipeline
cd DATA_Code_Preprocessing
python preprocess_all_data.py

# 2. Open data_exploration.ipynb for visualizations
```

---

## Overview

The preprocessing pipeline:
1. **Loads** raw CSV files with proper encoding
2. **Cleans** data (dates, missing values, normalization)
3. **Extracts** features from Italian/English text
4. **Identifies** incident types and implicit resolutions
5. **Calculates** severity scores
6. **Processes** operation data (delays, running times, stop times)
7. **Adds** temporal features (holidays, day of week)
8. **Exports** enriched data in CSV and JSON formats

---

## Input Files

| File | Description | Records |
|------|-------------|---------|
| `Train_fault_information.csv` | Incident reports with delay reasons | 113 |
| `Train_station_locations_data.csv` | Station coordinates | 2,975 |
| `Adjacent_railway_stations_mileage_data.csv` | Route segments | 12,173 |
| `Train_operation_data.csv` | Train operations | 2,678,291 |

---

## Output Files

All processed files are saved to `Data/Processed/`:

| File | Format | Description |
|------|--------|-------------|
| `fault_data_enriched.csv` | CSV | Enriched fault data (flattened) |
| `fault_data_enriched.json` | JSON | Enriched fault data (structured) |
| `station_data_enriched.csv` | CSV | Stations with region names |
| `mileage_data_enriched.csv` | CSV | Routes with train types |
| `operation_data_enriched.csv` | CSV | Operations with delays & times |
| `preprocessing_summary.json` | JSON | Statistics and summary |

---

## 📊 Data Exploration Notebook

The `data_exploration.ipynb` notebook provides comprehensive visualizations:

### Visualizations Included:
- **Incident Type Distribution** - Bar charts and pie charts
- **Severity Analysis** - By incident type comparison
- **Delay Duration** - Histograms and box plots
- **Temporal Patterns** - Day of week, time of day analysis
- **Daily Trends** - Incident count over time with trend line
- **Resolution Analysis** - Types and coverage
- **Heatmaps** - Incident type vs time, incident type vs day
- **Correlation Matrix** - Numeric feature relationships
- **Station Distribution** - Geographic map of Italy
- **Train Types** - Distribution in route data
- **Operation Metrics** - Delay and running time distributions

### Generated Visualization Files:
```
Data/Processed/
├── viz_incident_types.png
├── viz_severity_by_type.png
├── viz_delay_distribution.png
├── viz_temporal_patterns.png
├── viz_daily_trend.png
├── viz_resolution_types.png
├── viz_resolution_coverage.png
├── viz_heatmap_type_time.png
├── viz_heatmap_type_day.png
├── viz_correlation_matrix.png
├── viz_stations_by_region.png
├── viz_station_map.png
├── viz_train_types.png
├── viz_operation_delays.png
└── viz_operation_times.png
```

---

## Extracted Features

### Incident Types
Automatically classified from text patterns:

| Type | Italian Keywords | English Keywords |
|------|------------------|------------------|
| `technical` | inconveniente tecnico, guasto | technical failure, technical checks |
| `weather` | maltempo, pioggia, neve | adverse weather |
| `trespasser` | investimento persona, persone binari | unauthorized people, people near tracks |
| `equipment_failure` | guasto, malfunzionamento | failure, breakdown |
| `maintenance` | manutenzione, lavori | maintenance, works |
| `police_intervention` | intervento polizia | police, authorities |
| `fire` | incendio, fuoco | fire |
| `accident` | incidente, impatto | accident, collision |

### Resolution Types (Extracted from Narratives)

| Resolution | Patterns Detected |
|------------|-------------------|
| `REROUTE` | "trains deflected on alternative", "deviati" |
| `BUS_BRIDGE` | "bus replacement service", "servizio sostitutivo bus" |
| `CANCEL` | "train canceled", "treno cancellato", "deleted" |
| `SPEED_REGULATE` | "slowdowns up to X min", "rallentamenti" |
| `SHORT_TURN` | "limited to", "limitato a", "ends the race to" |
| `HOLD` | "stopped in line", "in attesa" |
| `SINGLE_TRACK` | "managed on single track", "binario unico" |
| `GRADUAL_RECOVERY` | "gradually resumed", "graduale ripresa" |

### Additional Features

| Feature | Description |
|---------|-------------|
| `location_segment` | Extracted "between X and Y" |
| `location_station` | Extracted "near X" |
| `location_direction` | Extracted direction (towards Rome, etc.) |
| `affected_trains_high_speed` | Count of affected high-speed trains |
| `affected_trains_intercity` | Count of affected intercity trains |
| `affected_trains_regional` | Count of affected regional trains |
| `incident_time` | Extracted start time |
| `time_of_day` | Classified: morning_peak, midday, evening_peak, night |
| `severity_score` | Calculated 0-100 severity score |
| `embedding_text` | Clean English text for vector embedding |

---

## 📈 Operation Data Features

The pipeline also enriches operation data with:

| Feature | Description | Source Script |
|---------|-------------|---------------|
| `day_of_week` | Day name (Monday-Sunday) | Add_week.py |
| `day_of_week_num` | Day number (1-7) | Add_week.py |
| `is_weekend` | Weekend flag (True/False) | Add_week.py |
| `is_holiday` | Italian holiday flag | Add_holiday.py |
| `arrival_delay_min` | Arrival delay in minutes | Calculate_arrival_delay_time.py |
| `departure_delay_min` | Departure delay in minutes | Calculate_departure_delay_time.py |
| `scheduled_stop_time_min` | Scheduled stop duration | Add_scheduled_stop_time.py |
| `actual_stop_time_min` | Actual stop duration | Add_actual_stop_time.py |
| `scheduled_running_time_min` | Scheduled running time | Add_scheduled_running_time.py |
| `actual_running_time_min` | Actual running time | Add_actual_running_time.py |

---

## 🇮🇹 Italian Holidays (2024)

The pipeline recognizes these Italian public holidays:

| Date | Holiday |
|------|---------|
| Jan 1 | New Year's Day |
| Jan 6 | Epiphany |
| Mar 31 | Easter Sunday |
| Apr 1 | Easter Monday |
| Apr 25 | Liberation Day |
| May 1 | Labour Day |
| Jun 2 | Republic Day |
| Aug 15 | Assumption of Mary |
| Nov 1 | All Saints' Day |
| Dec 8 | Immaculate Conception |
| Dec 25 | Christmas Day |
| Dec 26 | St. Stephen's Day |

---

## Severity Score Formula

```
severity = (
    delay_duration_min / 180 * 100 * 0.4 +      # 40% weight
    affected_trains / 50 * 100 * 0.3 +           # 30% weight
    is_peak_hour * 100 * 0.2 +                   # 20% weight
    is_high_speed_line * 100 * 0.1               # 10% weight
)
```

Score range: 0-100 (higher = more severe)

---

## Usage

### Run from Command Line

```bash
cd DATA_Code_Preprocessing
python preprocess_all_data.py
```

### Run from Python

```python
from preprocess_all_data import main

# Run full pipeline
df_faults, df_stations, df_mileage = main()

# Or use individual functions
from preprocess_all_data import (
    load_fault_data,
    extract_incident_type,
    extract_resolutions,
    calculate_severity_score
)

# Load and process specific file
df = load_fault_data('path/to/Train_fault_information.csv')
```

---

## Enriched Data Schema

### fault_data_enriched.json

```json
{
  "date": "2024-09-20",
  "line": "Milan - Genoa",
  "line_normalized": "Milan - Genoa",
  "delay_reason": "...(original text)...",
  "delay_duration": "40 min",
  "delay_duration_min": 40,
  
  "incident_type": "technical",
  "resolutions_extracted": [
    {"type": "REROUTE"},
    {"type": "SPEED_REGULATE", "duration_min": 30}
  ],
  "resolution_types": ["REROUTE", "SPEED_REGULATE"],
  "has_resolution": true,
  
  "location_segment": "Tortona - Voghera",
  "location_station": null,
  "location_direction": "Rome",
  
  "affected_trains_high_speed": 2,
  "affected_trains_intercity": 4,
  "affected_trains_regional": 9,
  "affected_trains_total": 15,
  
  "incident_time": "17:00",
  "time_of_day": "evening_peak",
  "day_of_week": "Friday",
  "is_weekend": false,
  "is_high_speed_line": false,
  
  "severity_score": 45.67,
  
  "embedding_text": "technical incident on Milan - Genoa between Tortona - Voghera causing 40 minutes delay affecting 15 trains resolved by reroute, speed regulate during evening peak."
}
```

---

## Region Mapping

Stations are mapped to Italian regions:

| ID | Region |
|----|--------|
| 1 | Piedmont |
| 2 | Aosta Valley |
| 3 | Lombardy |
| 4 | Trentino-Alto Adige/South Tyrol |
| 5 | Veneto |
| 6 | Friuli Venezia Giulia |
| 7 | Liguria |
| 8 | Emilia-Romagna |
| 9 | Tuscany |
| 10 | Umbria |
| 11 | Marche |
| 12 | Lazio |
| 13 | Abruzzo |
| 14 | Molise |
| 15 | Campania |
| 16 | Apulia |
| 17 | Basilicata |
| 18 | Calabria |
| 19 | Sicily |
| 20 | Sardinia |

---

## Train Type Classification

Extracted from `train_id` prefixes:

| Prefix | Train Type |
|--------|------------|
| `IC_` | Intercity |
| `REG_`, `R_` | Regional |
| `EC_` | EuroCity |
| `AV_`, `FR_` | High-Speed |
| `RV_` | Fast Regional |

---

## Dependencies

```
pandas>=1.5.0
numpy>=1.21.0
matplotlib>=3.5.0
seaborn>=0.12.0
```

Install with:
```bash
pip install pandas numpy matplotlib seaborn
```

---

## Next Steps (Qdrant Ingestion)

After preprocessing, the enriched data is ready for:

1. **Embedding Generation** - Use `embedding_text` with sentence-transformers
2. **Qdrant Upload** - Store vectors with full payload
3. **Similarity Search** - Query by incident type, location, severity

Example Qdrant payload structure:
```python
{
    "id": "INC_2024_0920_001",
    "vector": [...],  # From embedding_text
    "payload": {
        "incident_type": "technical",
        "line": "Milan - Genoa",
        "severity_score": 45.67,
        "resolution_types": ["REROUTE", "SPEED_REGULATE"],
        # ... all other fields
    }
}
```

---

## File Structure

```
DATA_Code_Preprocessing/
├── preprocess_all_data.py      # Main preprocessing script
├── data_exploration.ipynb      # 📊 Data visualization notebook
├── README_preprocessing.md     # This documentation
├── Add_actual_running_time.py  # (legacy - integrated)
├── Add_holiday.py              # (legacy - integrated)
├── Add_week.py                 # (legacy - integrated)
├── ...                         # (other legacy scripts)

Data/
├── Train_fault_information.csv
├── Train_station_locations_data.csv
├── Adjacent_railway_stations_mileage_data.csv
├── Train_operation_data.csv
└── Processed/                  # OUTPUT DIRECTORY
    ├── fault_data_enriched.csv
    ├── fault_data_enriched.json
    ├── station_data_enriched.csv
    ├── mileage_data_enriched.csv
    ├── operation_data_enriched.csv
    ├── preprocessing_summary.json
    └── viz_*.png               # 📊 Generated visualizations
```

---

## 📊 Sample Statistics (from preprocessing run)

```
Total incidents processed: 113
Date range: 2024-09-20 to 2024-09-30

Incident types found:
  - technical: 44 (38.9%)
  - other: 22 (19.5%)
  - maintenance: 20 (17.7%)
  - trespasser: 14 (12.4%)
  - weather: 9 (8.0%)
  - fire: 3 (2.7%)
  - police_intervention: 1 (0.9%)

Resolution extraction coverage: 87.61%

Resolution types extracted:
  - SPEED_REGULATE: 78
  - CANCEL: 46
  - REROUTE: 11
  - BUS_BRIDGE: 11
  - GRADUAL_RECOVERY: 7
  - HOLD: 6
  - SINGLE_TRACK: 4
  - SHORT_TURN: 1

Severity score: mean=22.21, max=73.2
Delay duration: mean=43.1 min, max=225 min
```

---

## Authors

AI Rail Network Brain Team - AI Hackathon 2026
