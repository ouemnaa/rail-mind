# AI Rail Network Brain - Qdrant Vector Database Pipeline

Complete end-to-end pipeline for converting Italian railway incident data into searchable vectors using **Qdrant**. Enables semantic similarity search, incident prediction, and real-time conflict detection.

---

## 📁 Project Structure

```
vector-database/
├── config.py                    # ⚙️ Configuration (Qdrant connection, models, paths)
├── step1_enrich_data.py         # 🔧 Fill data gaps & enrich metadata
├── step2_train_test_split.py    # ⏱️ Time-based split for simulation
├── step3_generate_embeddings.py # 🧠 Generate vector embeddings with Chonkie
├── step4_ingest_qdrant.py       # 📤 Upload vectors to Qdrant database
├── step5_query_examples.py      # 🔍 Query utilities & demo scripts
├── run_pipeline.py              # ▶️ Execute full pipeline
├── README.md                    # 📖 This documentation
└── output/                      # 📊 Generated files
    ├── fault_data_enriched_full.csv
    ├── train_split.json / test_split.json
    ├── train_embeddings.npy / test_embeddings.npy
    └── qdrant_ingestion_report.json
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install pandas numpy chonkie[st] qdrant-client tqdm scikit-learn
```

### 2. Start Qdrant Database

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

### 3. Run Pipeline

```bash
cd Qdrant
python run_pipeline.py
```

**Or run steps individually:**

```bash
python step1_enrich_data.py       # 1️⃣ Enrich data
python step2_train_test_split.py  # 2️⃣ Time-based split
python step3_generate_embeddings.py  # 3️⃣ Generate vectors
python step4_ingest_qdrant.py     # 4️⃣ Upload to Qdrant
python step5_query_examples.py    # 5️⃣ Test queries
```

---

## 📊 Pipeline Stages

### Stage 1: Data Enrichment

**Purpose:** Fill missing data gaps and enrich incident metadata

| Gap Filled              | Strategy                                       | Output                                 |
| ----------------------- | ---------------------------------------------- | -------------------------------------- |
| **Missing Locations**   | Extract from segment/text → Fill station names | `location_station`, `location_segment` |
| **GPS Coordinates**     | Match station names → Database lookup          | `incident_lat`, `incident_lon`         |
| **Resolution Types**    | Infer from text patterns → Classify            | `resolution_types`, `has_resolution`   |
| **Operation Linkage**   | Join with daily train stats by date            | `ops_total_trains`, `ops_avg_delay`    |
| **Historical Patterns** | Detect recurring locations & trends            | `is_recurring`, `incidents_7days`      |
| **Precise Timestamps**  | Parse time from text → Datetime                | `incident_datetime`, `incident_hour`   |

### Stage 2: Time-Based Split

**Purpose:** Enable realistic simulation (no data leakage)

- ✅ **80% Train:** Earlier incidents → Learn patterns
- ✅ **20% Test:** Later incidents → Predict future
- ✅ **Chronological:** Train on past, test on future
- ❌ **NOT Random:** Prevents data leakage

### Stage 3: Vector Generation

**Purpose:** Convert text to semantic embeddings

**Model:** `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions)

| Why This Model?     | Advantage                                     |
| ------------------- | --------------------------------------------- |
| 🆓 **Free**         | No API costs (Cohere charges $0.10/1M tokens) |
| 🏠 **Local**        | Works offline, no rate limits                 |
| 🌍 **Multilingual** | Italian station names + English descriptions  |
| 🎯 **Quality**      | Excellent semantic similarity for RAG         |

**Alternatives Considered:**

- ❌ CohereEmbeddings → Paid API
- ❌ Model2VecEmbeddings → Less semantic depth
- ❌ AutoEmbeddings → Unpredictable model selection

### Stage 4: Qdrant Ingestion

**Purpose:** Upload vectors with metadata to Qdrant

- Creates collection: `rail_incidents`
- Vector size: 384 dimensions
- Distance metric: Cosine similarity
- Indexes: Keyword, numeric, boolean fields
- Both train & test data ingested (filterable by `split` field)

### Stage 5: Query Examples

**Purpose:** Demonstrate search capabilities

**Available Methods:**

- `search_similar_incidents(text)` - Semantic similarity
- `search_by_location(lat, lon)` - Geo-proximity
- `search_by_severity(min_score)` - Severity filtering
- `search_recurring_incidents()` - Problem hotspots
- `predict_resolution(description)` - ML prediction

---

## 🗂️ Qdrant Collection Schema

### Vector Format

- **Dimension:** 384
- **Distance:** Cosine similarity
- **Source:** Chonkie SentenceTransformerEmbeddings

### Payload Attributes (Stored in Qdrant)

| Attribute                    | Type               | Description                         | Example                                                   | Nullable |
| ---------------------------- | ------------------ | ----------------------------------- | --------------------------------------------------------- | -------- |
| **Core Identification**      |
| `id`                         | String             | Unique incident ID                  | `"train_42"`                                              | ❌       |
| `split`                      | String             | Train or test set                   | `"train"` / `"test"`                                      | ❌       |
| `date`                       | String             | Incident date                       | `"2024-09-20"`                                            | ❌       |
| `incident_datetime`          | String             | Full timestamp                      | `"2024-09-20 19:30:00"`                                   | ✅       |
| **Incident Details**         |
| `incident_type`              | String (Keyword)   | Type of incident                    | `"technical"`, `"trespasser"`, `"weather"`, `"strike"`    | ❌       |
| `line`                       | String             | Railway line                        | `"High Speed Rome - Naples"`                              | ❌       |
| `line_normalized`            | String (Keyword)   | Standardized line name              | `"High Speed Rome - Naples"`                              | ❌       |
| `delay_duration_min`         | Float              | Total delay in minutes              | `60.0`                                                    | ✅       |
| `severity_score`             | Float (Indexed)    | Computed severity (0-100)           | `52.93`                                                   | ✅       |
| `delay_reason`               | String             | Full incident description (Italian) | `"Circolazione rallentata tra..."`                        | ❌       |
| **Location Information**     |
| `location_station`           | String             | Affected station                    | `"Rome Prenestina"`                                       | ✅       |
| `location_segment`           | String             | Track segment                       | `"Tortona - Voghera after"`                               | ✅       |
| `matched_station`            | String             | Matched station from DB             | `"ROMA PRENESTINA"`                                       | ✅       |
| `matched_region`             | String (Keyword)   | Italian region                      | `"Lazio"`, `"Lombardy"`                                   | ✅       |
| `incident_lat`               | Float (Indexed)    | GPS latitude                        | `41.897`                                                  | ✅       |
| `incident_lon`               | Float (Indexed)    | GPS longitude                       | `12.532`                                                  | ✅       |
| **Temporal Features**        |
| `time_of_day`                | String (Keyword)   | Time period                         | `"morning_peak"`, `"evening_peak"`, `"night"`, `"midday"` | ✅       |
| `day_of_week`                | String (Keyword)   | Day name                            | `"Monday"` to `"Sunday"`                                  | ✅       |
| `incident_hour`              | Integer (Indexed)  | Hour (0-23)                         | `19`                                                      | ✅       |
| `is_weekend`                 | Boolean (Indexed)  | Weekend flag                        | `true` / `false`                                          | ❌       |
| `is_holiday`                 | Boolean (Indexed)  | Holiday flag                        | `true` / `false`                                          | ❌       |
| **Impact Metrics**           |
| `affected_trains_total`      | Integer            | Total affected trains               | `16`                                                      | ✅       |
| `affected_trains_high_speed` | Integer            | High-speed trains                   | `15`                                                      | ✅       |
| `affected_trains_intercity`  | Integer            | Intercity trains                    | `0`                                                       | ✅       |
| `affected_trains_regional`   | Integer            | Regional trains                     | `1`                                                       | ✅       |
| **Resolution Information**   |
| `resolution_types`           | String             | Resolution methods (pipe-separated) | `"SPEED_REGULATE\|GRADUAL_RECOVERY"`                      | ✅       |
| `has_resolution`             | Boolean (Indexed)  | Resolution status                   | `true` / `false`                                          | ❌       |
| **Historical Patterns**      |
| `is_recurring_location`      | Boolean (Indexed)  | Repeat incident at this location    | `true` / `false`                                          | ❌       |
| `recurrence_count`           | Integer            | Number of repeats                   | `2`                                                       | ✅       |
| `incidents_same_line_7days`  | Integer            | Similar incidents in last 7 days    | `2`                                                       | ✅       |
| `days_since_last_same_line`  | Float              | Days since last incident on line    | `5.3`                                                     | ✅       |
| **Operation Linkage**        |
| `ops_total_trains`           | Integer            | Daily trains on date                | `15000`                                                   | ✅       |
| `ops_avg_arrival_delay`      | Float              | Average delay (minutes)             | `3.5`                                                     | ✅       |
| `ops_delayed_trains`         | Integer            | Delayed trains on date              | `1200`                                                    | ✅       |
| `ops_on_time_pct`            | Float              | On-time percentage                  | `85.2`                                                    | ✅       |
| **Embeddings**               |
| `embedding_text`             | String (Full-text) | Enhanced text for search            | `"technical incident on..."`                              | ❌       |
| **Classification Flags**     |
| `is_high_speed_line`         | Boolean            | High-speed line flag                | `true` / `false`                                          | ❌       |

**Total Fields:** 40+ attributes per incident

---

**Total Fields:** 40+ attributes per incident

---

## 🔍 Query Examples by Category

### 1. Semantic Search (Vector Similarity)

```python
from step5_query_examples import RailIncidentSearch

searcher = RailIncidentSearch()

# Find similar incidents by text description
results = searcher.search_similar_incidents(
    text="technical problem on high-speed line near Rome",
    limit=5
)
```

### 2. Location-Based Search (Geo-Filtering)

```python
# Find incidents within 50km of Rome (41.9028° N, 12.4964° E)
results = searcher.search_by_location(
    lat=41.9028,
    lon=12.4964,
    radius_km=50,
    limit=10
)
```

### 3. Severity-Based Filtering

```python
# Find critical incidents (severity > 80)
results = searcher.search_by_severity(
    min_score=80,
    limit=20
)
```

### 4. Temporal Pattern Analysis

```python
# Filter by time period
client.query_points(
    collection_name="rail_incidents",
    query_filter={
        "must": [
            {"key": "time_of_day", "match": {"value": "morning_peak"}},
            {"key": "is_weekend", "match": {"value": False}}
        ]
    },
    limit=50
)
```

### 5. Recurring Incident Detection

```python
# Find hotspot locations
results = searcher.search_recurring_incidents(min_occurrences=3)
```

### 6. Resolution Prediction

```python
# Predict resolution strategies based on past similar incidents
resolution = searcher.predict_resolution(
    description="Train stuck due to signal failure near Milan"
)
```

---

## 🔧 Configuration (`config.py`)

### Qdrant Connection

```python
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_COLLECTION_NAME = "rail_incidents"
QDRANT_TIMEOUT = 60  # Increased for large batch uploads
```

### Embedding Model

```python
CHONKIE_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHONKIE_DIMENSION = 384
```

### Data Split (Time-Based)

```python
TRAIN_RATIO = 0.8  # 80% past → train, 20% future → test
```

---

## 📈 Simulation Workflow

### Why Time-Based Split?

Traditional ML uses **random split** → **Data leakage risk**

Our approach uses **chronological split** → **Realistic prediction**

```
[Past] ──────────────────────► [Future]
   ▲                             ▲
   │                             │
80% Train Data            20% Test Data
```

**Simulation Steps:**

1. Train model on past incidents (80%)
2. Predict on future incidents (20%)
3. Measure accuracy without data leakage
4. Deploy for real-time prediction

---

## 📊 Data Quality Summary

After enrichment:

- ✅ **113 Total Incidents** (90 train + 23 test)
- ✅ **All have embeddings** (384-dim vectors)
- ✅ **Gap-filling functions** for missing data:
  - `fill_missing_locations()` - Extract from text
  - `fill_missing_resolutions()` - Infer from patterns
- ⚠️ **Some NULL values remain** (preserved as `null` in JSON)
  - Important: NULL location = "location unknown" (keep for analysis)
  - Not removed: location_segment, location_station may be NULL

---

## 🛠️ Troubleshooting

### Qdrant Connection Timeout

```python
# Increase timeout in config.py
QDRANT_TIMEOUT = 60  # Default: 5s

# Reduce batch size in step4
batch_size = 50  # Default: 100
```

### Missing Embeddings

```bash
# Check if Chonkie is installed correctly
pip install chonkie[st] --upgrade

# Verify model download
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"
```

### NULL Values in Qdrant Payloads

- **Expected behavior:** Some fields may be NULL
- **Why:** Missing data preserved for transparency
- **Solution:** Gap-filling functions attempt to infer missing values
- **Rerun step1:** `python step1_enrich_data.py` to apply gap-filling

---

## 🎯 Next Steps

1. **Rerun pipeline with gap-filling:**

   ```bash
   python run_pipeline.py
   ```

2. **Test query performance:**

   ```bash
   python step5_query_examples.py
   ```

3. **Build ML model:**
   - Use embeddings for similarity-based prediction
   - Filter by indexed fields (location, severity, type)
   - Predict resolution strategies from historical data

4. **Deploy real-time prediction:**
   - Ingest new incidents as they occur
   - Query Qdrant for similar past incidents
   - Recommend resolution actions

---

## 📚 References

- **Qdrant Documentation:** https://qdrant.tech/documentation/
- **Chonkie Library:** https://github.com/bhavnicksm/chonkie
- **Sentence Transformers:** https://www.sbert.net/
- **Model Used:** `paraphrase-multilingual-MiniLM-L12-v2`

---

## 🏁 Success Criteria

✅ **Pipeline Complete When:**

- Qdrant contains 113 vectors (90 train + 23 test)
- All indexed fields are queryable
- Semantic search returns relevant results
- NULL values minimized by gap-filling
- Time-based split validated (no data leakage)

**Current Status:** ✅ All stages complete, ready for queries

---

RANDOM_SEED = 42

````

## 📈 Data Schema in Qdrant

Each point in the collection has:

**Vector:** 384-dimensional embedding (or 1536 for OpenAI)

**Payload fields:**
```json
{
  "id": "train_42",
  "date": "2024-09-20",
  "incident_datetime": "2024-09-20 19:30:00",
  "incident_type": "technical",
  "line": "High Speed Rome - Naples",
  "line_normalized": "High Speed Rome - Naples",
  "delay_duration_min": 60,
  "severity_score": 52.93,

  "location_station": "Rome Prenestina",
  "matched_station": "ROMA PRENESTINA",
  "matched_region": "Lazio",
  "incident_lat": 41.897,
  "incident_lon": 12.532,

  "time_of_day": "evening_peak",
  "day_of_week": "Friday",
  "is_weekend": false,
  "is_holiday": false,
  "incident_hour": 19,

  "affected_trains_total": 16,
  "affected_trains_high_speed": 15,

  "resolution_types": "SPEED_REGULATE|GRADUAL_RECOVERY",
  "has_resolution": true,

  "is_recurring_location": false,
  "recurrence_count": 0,
  "incidents_same_line_7days": 2,

  "ops_total_trains": 15000,
  "ops_avg_arrival_delay": 3.5,
  "ops_on_time_pct": 85.2,

  "embedding_text": "technical incident on High Speed Rome - Naples...",
  "split": "train"
}
````

## 🔍 Example Queries

### Python API

```python
from step5_query_examples import RailIncidentSearch

search = RailIncidentSearch()

# Find similar incidents
results = search.search_similar_incidents(
    "technical failure on high speed line during rush hour",
    limit=5
)

# Predict resolution for new incident
prediction = search.predict_resolution(
    "unauthorized person on tracks near Rome"
)
print(prediction['predicted_resolutions'])
# {'SPEED_REGULATE': 45.2, 'CANCEL': 23.1, ...}

# Search by location (Rome area)
nearby = search.search_by_location(lat=41.9, lon=12.5, radius_km=30)

# Get high severity incidents
severe = search.search_by_severity(min_severity=50)
```

### Direct Qdrant API

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

client = QdrantClient(host="localhost", port=6333)

# Filter by incident type
results = client.scroll(
    collection_name="rail_incidents",
    scroll_filter=Filter(must=[
        FieldCondition(key="incident_type", match=MatchValue(value="technical")),
        FieldCondition(key="severity_score", range=Range(gte=40))
    ]),
    limit=10
)
```

## 📊 Output Files

After running the pipeline:

| File                                | Description                             |
| ----------------------------------- | --------------------------------------- |
| `fault_data_enriched_full.csv/json` | All enriched data                       |
| `train_split.json`                  | Training set (80% - earlier dates)      |
| `test_split.json`                   | Test set (20% - later dates)            |
| `train_embeddings.npy`              | Training vectors                        |
| `test_embeddings.npy`               | Test vectors                            |
| `train_payloads.json`               | Training metadata                       |
| `test_payloads.json`                | Test metadata                           |
| `split_metadata.json`               | Split statistics (includes date ranges) |
| `embedding_metadata.json`           | Embedding info                          |
| `qdrant_ingestion_report.json`      | Ingestion summary                       |

## 🎬 Simulation Workflow

The **time-based split** enables realistic simulation:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SIMULATION WORKFLOW                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  TRAIN SET (80%)                    TEST SET (20%)                   │
│  Earlier dates ─────────────────────▶ Later dates                   │
│                                                                      │
│  1. Train: Learn patterns from      2. Simulate: Replay test        │
│     past incidents                     incidents chronologically     │
│                                                                      │
│  - What resolutions worked?         - New incident arrives          │
│  - Which locations recurring?       - Query similar past incidents  │
│  - What's the severity pattern?     - Predict resolution BEFORE     │
│                                       seeing actual outcome          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Example simulation code:**

```python
import json
from step5_query_examples import RailIncidentSearch

# Load test incidents (future)
with open("output/test_split.json") as f:
    test_incidents = json.load(f)

search = RailIncidentSearch()

# Simulate chronological replay
for incident in test_incidents:
    # Predict resolution BEFORE seeing actual outcome
    prediction = search.predict_resolution(incident['delay_reason'])

    # Compare with actual resolution
    actual = incident.get('resolution_types', '')
    print(f"Predicted: {prediction['predicted_resolutions']}")
    print(f"Actual: {actual}")
```

## 🐛 Troubleshooting

**Qdrant connection failed:**

```bash
# Make sure Qdrant is running
docker ps | grep qdrant

# Start if not running
docker run -p 6333:6333 qdrant/qdrant
```

**Missing Chonkie:**

```bash
pip install chonkie[st]
```

**Missing sentence-transformers (fallback):**

```bash
pip install sentence-transformers
```

**Out of memory with embeddings:**

- Reduce `EMBEDDING_BATCH_SIZE` in config.py
- Use smaller model

**No station coordinates matched:**

- Check station data has proper lat/lon
- Verify station names match incident locations

## 📝 Notes

- Uses **Chonkie SentenceTransformerEmbeddings** (free, local, multilingual)
- The pipeline uses **cosine similarity** for vector search (best for semantic similarity)
- **Time-based split** ensures no data leakage (train on past, test on future)
- **Recurring incidents** are detected by matching location names
- Embeddings are generated from the `embedding_text_enhanced` field which includes historical context

---

**Author:** AI Rail Network Brain Team  
**Date:** January 2026  
**Version:** 1.1 (Time-based split + Chonkie embeddings)
