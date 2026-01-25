"""
Step 3: Generate Embeddings
===========================
Generates vector embeddings for fault data using:
- Sentence Transformers (default, free, local)
- OpenAI Embeddings (optional, requires API key)

Author: AI Rail Network Brain Team
Date: January 2026
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

from config import (
    OUTPUT_DIR, EMBEDDING_MODEL, VECTOR_SIZE,
    EMBEDDING_BATCH_SIZE, MIN_TEXT_LENGTH,
    TRAIN_DATA, TEST_DATA
)

# ============================================================
# Chonkie Configuration
# ============================================================

# Chonkie embedding model (multilingual for Italian+English rail data)
CHONKIE_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHONKIE_DIMENSION = 384

# Try importing Chonkie
CHONKIE_AVAILABLE = False
try:
    from chonkie.embeddings import SentenceTransformerEmbeddings
    CHONKIE_AVAILABLE = True
except ImportError:
    print("⚠️ Chonkie not installed. Will fall back to sentence-transformers.")
    print("   Install Chonkie with: pip install chonkie[st]")


class ChonkieEmbeddingGenerator:
    """
    Generate embeddings using Chonkie's SentenceTransformerEmbeddings.
    
    ╔═══════════════════════════════════════════════════════════════════╗
    ║ Why SentenceTransformerEmbeddings for Rail Data?                  ║
    ╠═══════════════════════════════════════════════════════════════════╣
    ║ ✓ Free: No API costs (vs Cohere which charges per token)         ║
    ║ ✓ Local: Works offline, no rate limits                           ║
    ║ ✓ Multilingual: Italian station names + English descriptions     ║
    ║ ✓ Quality: Excellent semantic similarity for incident matching   ║
    ║ ✓ Proven: Industry standard for RAG systems                      ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self, model_name: str = None):
        """Initialize Chonkie embeddings."""
        self.model_name = model_name or CHONKIE_MODEL
        self.embeddings = None
        self.dimension = CHONKIE_DIMENSION
        self.use_fallback = False
        
    def initialize(self):
        """Initialize the Chonkie embedding model."""
        print(f"\n🚀 Initializing Chonkie SentenceTransformerEmbeddings...")
        print(f"   Model: {self.model_name}")
        
        if CHONKIE_AVAILABLE:
            try:
                self.embeddings = SentenceTransformerEmbeddings(
                    model=self.model_name
                )
                
                # Test and get dimension
                test_emb = self.embeddings.embed("test")
                if hasattr(test_emb, '__len__'):
                    self.dimension = len(test_emb)
                
                print(f"   ✅ Chonkie model loaded successfully")
                print(f"   Dimension: {self.dimension}")
                return True
                
            except Exception as e:
                print(f"   ⚠️ Chonkie error: {e}")
                print(f"   Falling back to sentence-transformers...")
        
        # Fallback to sentence-transformers directly
        try:
            from sentence_transformers import SentenceTransformer
            self.embeddings = SentenceTransformer(self.model_name)
            self.use_fallback = True
            self.dimension = self.embeddings.get_sentence_embedding_dimension()
            print(f"   ✅ Fallback model loaded (sentence-transformers)")
            print(f"   Dimension: {self.dimension}")
            return True
        except ImportError:
            print("   ❌ Neither Chonkie nor sentence-transformers available")
            print("   Install with: pip install chonkie[st] or pip install sentence-transformers")
            return False
    
    def embed_text(self, text: str) -> list:
        """Generate embedding for a single text."""
        if self.embeddings is None:
            raise ValueError("Model not initialized. Call initialize() first.")
        
        if self.use_fallback:
            embedding = self.embeddings.encode(text)
        else:
            embedding = self.embeddings.embed(text)
        
        if isinstance(embedding, np.ndarray):
            return embedding.tolist()
        return list(embedding)
    
    def embed_batch(self, texts: list, batch_size: int = 32) -> list:
        """Generate embeddings for multiple texts."""
        if self.embeddings is None:
            raise ValueError("Model not initialized. Call initialize() first.")
        
        if self.use_fallback:
            # sentence-transformers direct batch
            embeddings = self.embeddings.encode(
                texts, 
                batch_size=batch_size,
                show_progress_bar=True
            )
            return embeddings.tolist()
        else:
            # Chonkie batch embedding
            all_embeddings = []
            
            for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
                batch = texts[i:i + batch_size]
                batch_embeddings = self.embeddings.embed_batch(batch)
                
                for emb in batch_embeddings:
                    if isinstance(emb, np.ndarray):
                        all_embeddings.append(emb.tolist())
                    else:
                        all_embeddings.append(list(emb))
            
            return all_embeddings


def prepare_texts(data):
    """Prepare texts for embedding."""
    texts = []
    
    for record in data:
        # Use enhanced embedding text if available, otherwise fall back to original
        text = record.get('embedding_text_enhanced') or record.get('embedding_text', '')
        
        # Clean and validate text
        if text and len(str(text)) >= MIN_TEXT_LENGTH:
            texts.append(str(text))
        else:
            # Create fallback text from available fields
            fallback = f"{record.get('incident_type', 'incident')} on {record.get('line', 'unknown line')}"
            texts.append(fallback)
    
    return texts


def create_qdrant_payloads(data):
    """Create payload metadata for Qdrant."""
    payloads = []
    
    for record in data:
        # Select relevant fields for Qdrant payload
        payload = {
            # Core identification
            'id': record.get('id', None),
            'date': str(record.get('date', '')),
            'incident_datetime': str(record.get('incident_datetime', '')),
            
            # Incident details
            'incident_type': record.get('incident_type', 'unknown'),
            'line': record.get('line', ''),
            'line_normalized': record.get('line_normalized', ''),
            'delay_duration_min': record.get('delay_duration_min'),
            'severity_score': record.get('severity_score'),
            
            # Location (with coordinates)
            'location_station': record.get('location_station'),
            'location_segment': record.get('location_segment'),
            'matched_station': record.get('matched_station'),
            'matched_region': record.get('matched_region'),
            'incident_lat': record.get('incident_lat'),
            'incident_lon': record.get('incident_lon'),
            
            # Temporal features
            'time_of_day': record.get('time_of_day'),
            'day_of_week': record.get('day_of_week'),
            'is_weekend': record.get('is_weekend'),
            'is_holiday': record.get('is_holiday'),
            'incident_hour': record.get('incident_hour'),
            
            # Impact
            'affected_trains_total': record.get('affected_trains_total', 0),
            'affected_trains_high_speed': record.get('affected_trains_high_speed', 0),
            'affected_trains_intercity': record.get('affected_trains_intercity', 0),
            'affected_trains_regional': record.get('affected_trains_regional', 0),
            
            # Resolutions
            'resolution_types': record.get('resolution_types', ''),
            'has_resolution': record.get('has_resolution', False),
            
            # Historical patterns
            'is_recurring_location': record.get('is_recurring_location', False),
            'recurrence_count': record.get('recurrence_count', 0),
            'incidents_same_line_7days': record.get('incidents_same_line_7days', 0),
            'days_since_last_same_line': record.get('days_since_last_same_line'),
            
            # Operation linkage
            'ops_total_trains': record.get('ops_total_trains'),
            'ops_avg_arrival_delay': record.get('ops_avg_arrival_delay'),
            'ops_delayed_trains': record.get('ops_delayed_trains'),
            'ops_on_time_pct': record.get('ops_on_time_pct'),
            
            # Full text for display
            'delay_reason': record.get('delay_reason', ''),
            'embedding_text': record.get('embedding_text_enhanced') or record.get('embedding_text', ''),
            
            # High-speed indicator
            'is_high_speed_line': record.get('is_high_speed_line', False)
        }
        
        # Convert NaN to None (null in JSON) but KEEP the fields
        # Fields like location_segment are important even if NaN
        import math
        def clean_value(v):
            if v is None:
                return None
            if isinstance(v, float) and math.isnan(v):
                return None  # Convert NaN to None, but keep the field
            return v
        
        payload = {k: clean_value(v) for k, v in payload.items()}
        
        payloads.append(payload)
    
    return payloads


def main():
    """Main embedding generation pipeline using Chonkie."""
    print("=" * 70)
    print("EMBEDDING GENERATION WITH CHONKIE")
    print("Using: SentenceTransformerEmbeddings (Multilingual)")
    print("=" * 70)
    
    # Show why SentenceTransformerEmbeddings
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║ Why SentenceTransformerEmbeddings?                                ║
    ╠═══════════════════════════════════════════════════════════════════╣
    ║ • CohereEmbeddings    → Paid API ($0.10/1M tokens), external dep ║
    ║ • Model2VecEmbeddings → Fast but less semantic understanding     ║
    ║ • AutoEmbeddings      → Unpredictable model selection            ║
    ║ • SentenceTransformer → ✅ FREE, LOCAL, MULTILINGUAL, QUALITY    ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize Chonkie embeddings
    generator = ChonkieEmbeddingGenerator()
    
    if not generator.initialize():
        print("\n❌ Failed to initialize embedding model")
        return
    
    # Load train data
    print("\n📂 Loading train data...")
    if not TRAIN_DATA.exists():
        print(f"   ❌ Train data not found: {TRAIN_DATA}")
        print("   Run step2_train_test_split.py first")
        return
    
    with open(TRAIN_DATA, 'r', encoding='utf-8') as f:
        train_data = json.load(f)
    print(f"   Loaded {len(train_data)} training records")
    
    # Load test data
    print("\n📂 Loading test data...")
    with open(TEST_DATA, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    print(f"   Loaded {len(test_data)} test records")
    
    # Prepare texts
    print("\n📝 Preparing texts for embedding...")
    train_texts = prepare_texts(train_data)
    test_texts = prepare_texts(test_data)
    print(f"   Train texts: {len(train_texts)}")
    print(f"   Test texts: {len(test_texts)}")
    if train_texts:
        print(f"   Sample: {train_texts[0][:100]}...")
    
    # Generate embeddings using Chonkie
    print("\n🔮 Generating TRAIN embeddings...")
    train_embeddings = generator.embed_batch(train_texts, EMBEDDING_BATCH_SIZE)
    train_embeddings = np.array(train_embeddings)
    
    print("\n🔮 Generating TEST embeddings...")
    test_embeddings = generator.embed_batch(test_texts, EMBEDDING_BATCH_SIZE)
    test_embeddings = np.array(test_embeddings)
    
    print(f"\n✅ Train embeddings shape: {train_embeddings.shape}")
    print(f"✅ Test embeddings shape: {test_embeddings.shape}")
    
    # Create Qdrant payloads
    print("\n📦 Creating Qdrant payloads...")
    train_payloads = create_qdrant_payloads(train_data)
    test_payloads = create_qdrant_payloads(test_data)
    
    # Add split identifiers
    for i, payload in enumerate(train_payloads):
        payload['id'] = payload.get('id') or f"train_{i}"
        payload['split'] = 'train'
    
    for i, payload in enumerate(test_payloads):
        payload['id'] = payload.get('id') or f"test_{i}"
        payload['split'] = 'test'
    
    # Save embeddings
    print("\n💾 Saving embeddings...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    np.save(OUTPUT_DIR / "train_embeddings.npy", train_embeddings)
    np.save(OUTPUT_DIR / "test_embeddings.npy", test_embeddings)
    print(f"   ✅ Train embeddings: {OUTPUT_DIR / 'train_embeddings.npy'}")
    print(f"   ✅ Test embeddings: {OUTPUT_DIR / 'test_embeddings.npy'}")
    
    # Save payloads
    with open(OUTPUT_DIR / "train_payloads.json", 'w', encoding='utf-8') as f:
        json.dump(train_payloads, f, indent=2, default=str)
    
    with open(OUTPUT_DIR / "test_payloads.json", 'w', encoding='utf-8') as f:
        json.dump(test_payloads, f, indent=2, default=str)
    
    print(f"   ✅ Train payloads: {OUTPUT_DIR / 'train_payloads.json'}")
    print(f"   ✅ Test payloads: {OUTPUT_DIR / 'test_payloads.json'}")
    
    # Save metadata
    metadata = {
        'embedding_library': 'chonkie' if not generator.use_fallback else 'sentence-transformers',
        'embedding_class': 'SentenceTransformerEmbeddings',
        'model': generator.model_name,
        'vector_dimension': generator.dimension,
        'train_count': len(train_data),
        'test_count': len(test_data),
        'total_count': len(train_data) + len(test_data),
        'why_this_model': {
            'free': 'No API costs (Cohere charges per token)',
            'local': 'Works offline, no rate limits',
            'multilingual': 'Supports Italian station names + English',
            'quality': 'Excellent semantic similarity for incident matching'
        }
    }
    
    with open(OUTPUT_DIR / "embedding_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"   ✅ Metadata: {OUTPUT_DIR / 'embedding_metadata.json'}")
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ EMBEDDING GENERATION COMPLETE")
    print("=" * 70)
    print(f"""
    📊 Summary:
       Library: Chonkie (SentenceTransformerEmbeddings)
       Model: {generator.model_name}
       Dimension: {generator.dimension}
       Train: {train_embeddings.shape}
       Test: {test_embeddings.shape}
    
    💡 Why this choice?
       ✓ FREE - No API costs (unlike Cohere)
       ✓ LOCAL - Works offline, no external dependency
       ✓ MULTILINGUAL - Handles Italian stations + English descriptions
       ✓ QUALITY - Best semantic understanding for similarity search
    """)


if __name__ == "__main__":
    main()
