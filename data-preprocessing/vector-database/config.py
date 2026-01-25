"""
Qdrant Pipeline Configuration
=============================
Centralized configuration for all Qdrant pipeline scripts.
"""

from pathlib import Path

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
RAW_DIR = DATA_DIR / "raw_data"
PROCESSED_DIR = DATA_DIR / "Processed"
QDRANT_DIR = BASE_DIR / "Qdrant"
OUTPUT_DIR = QDRANT_DIR / "output"

# Input files
FAULT_DATA = PROCESSED_DIR / "fault_data_enriched.csv"
STATION_DATA = PROCESSED_DIR / "station_data_enriched.csv"
MILEAGE_DATA = PROCESSED_DIR / "mileage_data_enriched.csv"
OPERATION_DATA = PROCESSED_DIR / "operation_data_enriched.csv"

# Output files
ENRICHED_FAULT_DATA = OUTPUT_DIR / "fault_data_qdrant_ready.json"
TRAIN_DATA = OUTPUT_DIR / "train_split.json"
TEST_DATA = OUTPUT_DIR / "test_split.json"
EMBEDDINGS_FILE = OUTPUT_DIR / "embeddings.npy"
METADATA_FILE = OUTPUT_DIR / "metadata.json"

# ============================================================================
# QDRANT CONFIGURATION
# ============================================================================

# Choose deployment mode: "cloud" or "local"
QDRANT_MODE = "cloud"  # Change to "local" for Docker deployment

# --- CLOUD CONFIGURATION (Qdrant Cloud) ---
# Get your credentials from: https://cloud.qdrant.io/
QDRANT_CLOUD_URL = ""  # Replace with your cluster URL
QDRANT_API_KEY = ""  # Replace with your API key (or set env var QDRANT_API_KEY)

# --- LOCAL CONFIGURATION (Docker) ---
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

# Collection name (same for both modes)
QDRANT_COLLECTION_NAME = "rail_incidents"

# Vector dimensions (depends on embedding model)
# Chonkie SentenceTransformerEmbeddings with multilingual model: 384
# sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2: 384
# OpenAI text-embedding-3-small: 1536

# CHONKIE EMBEDDING CONFIG (SentenceTransformerEmbeddings)
# Why SentenceTransformerEmbeddings?
# - FREE: No API costs (Cohere charges per token)
# - LOCAL: Works offline, no rate limits
# - MULTILINGUAL: Supports Italian station names + English descriptions
# - QUALITY: Excellent semantic similarity for incident matching
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE = 384

# Alternative: Use OpenAI embeddings (not recommended - paid)
USE_OPENAI_EMBEDDINGS = False
OPENAI_API_KEY = None  # Set via environment variable OPENAI_API_KEY
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_VECTOR_SIZE = 1536

# ============================================================================
# TRAIN/TEST SPLIT (TIME-BASED)
# ============================================================================

# TIME-BASED split is CORRECT for simulation:
# - Train on PAST incidents (earlier dates)
# - Test on FUTURE incidents (later dates)
# - No data leakage, realistic prediction scenario
TRAIN_RATIO = 0.8
TEST_RATIO = 0.2
RANDOM_SEED = 42  # Not used in time-based split, kept for compatibility

# ============================================================================
# PROCESSING PARAMETERS
# ============================================================================

# Time window for correlating operations with faults (hours)
FAULT_OPERATION_TIME_WINDOW_HOURS = 4

# Distance threshold for linking stations to incidents (km)
STATION_MATCH_DISTANCE_KM = 50

# Minimum text length for embedding
MIN_TEXT_LENGTH = 10

# Batch size for embedding generation
EMBEDDING_BATCH_SIZE = 32
