"""
Step 4: Ingest into Qdrant
==========================
Loads embeddings and payloads into Qdrant vector database.
Creates collection with proper schema and indexes.

Author: AI Rail Network Brain Team
Date: January 2026
"""

import numpy as np
import json
from pathlib import Path
from tqdm import tqdm
import uuid
import warnings
warnings.filterwarnings('ignore')

import os
from config import (
    OUTPUT_DIR, QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION_NAME,
    VECTOR_SIZE, USE_OPENAI_EMBEDDINGS, OPENAI_VECTOR_SIZE,
    QDRANT_MODE, QDRANT_CLOUD_URL, QDRANT_API_KEY
)


def load_qdrant_client():
    """Load Qdrant client - supports both Cloud and Local deployment."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        from qdrant_client.models import PayloadSchemaType, TextIndexParams, TokenizerType
        
        if QDRANT_MODE == "cloud":
            # --- QDRANT CLOUD CONNECTION ---
            api_key = os.environ.get("QDRANT_API_KEY", QDRANT_API_KEY)
            
            if not api_key or api_key == "YOUR_API_KEY":
                print("❌ Qdrant Cloud API key not configured!")
                print("   Set QDRANT_API_KEY in config.py or as environment variable")
                return None
            
            if QDRANT_CLOUD_URL == "https://YOUR-CLUSTER-URL.cloud.qdrant.io":
                print("❌ Qdrant Cloud URL not configured!")
                print("   Set QDRANT_CLOUD_URL in config.py")
                return None
            
            print(f"Connecting to Qdrant Cloud...")
            print(f"  URL: {QDRANT_CLOUD_URL}")
            
            client = QdrantClient(
                url=QDRANT_CLOUD_URL,
                api_key=api_key,
                timeout=120  # Longer timeout for cloud
            )
            
            # Test connection
            collections = client.get_collections()
            print(f"  ✅ Connected to Qdrant Cloud! Collections: {len(collections.collections)}")
        
        else:
            # --- LOCAL DOCKER CONNECTION ---
            print(f"Connecting to local Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
            
            client = QdrantClient(
                host=QDRANT_HOST, 
                port=QDRANT_PORT,
                timeout=60
            )
            
            # Test connection
            collections = client.get_collections()
            print(f"  ✅ Connected to local Qdrant! Collections: {len(collections.collections)}")
        
        return client
    
    except ImportError:
        print("❌ qdrant-client not installed")
        print("   Install with: pip install qdrant-client")
        return None
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        if QDRANT_MODE == "cloud":
            print("   Check your QDRANT_CLOUD_URL and QDRANT_API_KEY in config.py")
        else:
            print("   Make sure Qdrant is running:")
            print("   docker run -p 6333:6333 qdrant/qdrant")
        return None


def create_collection(client, vector_size):
    """Create Qdrant collection with proper schema."""
    from qdrant_client.models import Distance, VectorParams
    from qdrant_client.models import PayloadSchemaType, TextIndexParams, TokenizerType
    
    print(f"\nCreating collection: {QDRANT_COLLECTION_NAME}")
    
    # Check if collection exists
    collections = client.get_collections()
    existing_names = [c.name for c in collections.collections]
    
    if QDRANT_COLLECTION_NAME in existing_names:
        print(f"  ⚠️ Collection exists, recreating...")
        client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)
    
    # Create collection
    client.create_collection(
        collection_name=QDRANT_COLLECTION_NAME,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE  # Good for semantic similarity
        )
    )
    
    print(f"  ✅ Collection created with vector size: {vector_size}")
    
    # Create payload indexes for filtering
    print("  Creating payload indexes...")
    
    # Text index for full-text search on embedding_text
    try:
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION_NAME,
            field_name="embedding_text",
            field_schema=TextIndexParams(
                type="text",
                tokenizer=TokenizerType.WORD,
                min_token_len=2,
                max_token_len=15,
                lowercase=True
            )
        )
    except Exception as e:
        print(f"    Note: Text index may not be supported: {e}")
    
    # Keyword indexes for filtering
    keyword_fields = [
        "incident_type",
        "line_normalized", 
        "matched_region",
        "time_of_day",
        "day_of_week",
        "split"
    ]
    
    for field in keyword_fields:
        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD
            )
        except Exception:
            pass
    
    # Numeric indexes for range queries
    numeric_fields = [
        "severity_score",
        "delay_duration_min",
        "affected_trains_total",
        "incident_lat",
        "incident_lon",
        "incident_hour"
    ]
    
    for field in numeric_fields:
        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.FLOAT
            )
        except Exception:
            pass
    
    # Boolean indexes
    bool_fields = [
        "is_weekend",
        "is_holiday",
        "is_recurring_location",
        "is_high_speed_line",
        "has_resolution"
    ]
    
    for field in bool_fields:
        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.BOOL
            )
        except Exception:
            pass
    
    print("  ✅ Indexes created")


def ingest_data(client, embeddings, payloads, batch_name="data"):
    """Ingest data into Qdrant with retry logic."""
    from qdrant_client.models import PointStruct
    import time
    
    print(f"\nIngesting {len(embeddings)} {batch_name} points...")
    
    # Create points
    points = []
    for i, (embedding, payload) in enumerate(zip(embeddings, payloads)):
        # Generate UUID for point
        point_id = str(uuid.uuid4())
        
        # Add point_id to payload for reference
        payload['point_id'] = point_id
        
        points.append(PointStruct(
            id=point_id,
            vector=embedding.tolist() if isinstance(embedding, np.ndarray) else embedding,
            payload=payload
        ))
    
    # Upsert in smaller batches with retry
    batch_size = 50  # Reduced from 100 to avoid timeout
    max_retries = 3
    
    for i in tqdm(range(0, len(points), batch_size), desc=f"Uploading {batch_name}"):
        batch = points[i:i + batch_size]
        
        # Retry logic
        for attempt in range(max_retries):
            try:
                client.upsert(
                    collection_name=QDRANT_COLLECTION_NAME,
                    points=batch,
                    wait=True  # Wait for operation to complete
                )
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"\n  ⚠️ Upload attempt {attempt + 1} failed, retrying in 2s...")
                    time.sleep(2)
                else:
                    print(f"\n  ❌ Upload failed after {max_retries} attempts: {e}")
                    raise
    
    print(f"  ✅ Ingested {len(points)} points")
    return len(points)


def verify_collection(client):
    """Verify collection and print statistics."""
    print("\n" + "=" * 60)
    print("COLLECTION VERIFICATION")
    print("=" * 60)
    
    # Get collection info
    info = client.get_collection(collection_name=QDRANT_COLLECTION_NAME)
    
    print(f"Collection: {QDRANT_COLLECTION_NAME}")
    print(f"  Points count: {info.points_count}")
    print(f"  Status: {info.status}")
    
    # Sample search to verify
    print("\nTest search (finding similar incidents)...")
    
    # Get a sample point
    sample_points = client.scroll(
        collection_name=QDRANT_COLLECTION_NAME,
        limit=1,
        with_vectors=True
    )
    
    if sample_points[0]:
        sample_vector = sample_points[0][0].vector
        sample_payload = sample_points[0][0].payload
        
        print(f"  Sample incident: {sample_payload.get('incident_type')} on {sample_payload.get('line_normalized')}")
        
        # Search for similar (using query_points for newer Qdrant versions)
        try:
            results = client.query_points(
                collection_name=QDRANT_COLLECTION_NAME,
                query=sample_vector,
                limit=3
            ).points
        except AttributeError:
            # Fallback for older versions
            results = client.search(
                collection_name=QDRANT_COLLECTION_NAME,
                query_vector=sample_vector,
                limit=3
            )
        
        print(f"  Top 3 similar incidents:")
        for i, result in enumerate(results):
            payload = result.payload if hasattr(result, 'payload') else result
            print(f"    {i+1}. {payload.get('incident_type')} on {payload.get('line_normalized')} "
                  f"(score: {result.score if hasattr(result, 'score') else 'N/A'})")
    
    return info


def main():
    """Main Qdrant ingestion pipeline."""
    print("=" * 60)
    print("QDRANT INGESTION PIPELINE")
    print("=" * 60)
    
    # Load Qdrant client
    client = load_qdrant_client()
    if client is None:
        return
    
    # Load embeddings
    print("\nLoading embeddings...")
    
    train_embeddings_file = OUTPUT_DIR / "train_embeddings.npy"
    test_embeddings_file = OUTPUT_DIR / "test_embeddings.npy"
    
    if not train_embeddings_file.exists():
        print(f"❌ Embeddings not found: {train_embeddings_file}")
        print("   Run step3_generate_embeddings.py first")
        return
    
    train_embeddings = np.load(train_embeddings_file)
    test_embeddings = np.load(test_embeddings_file)
    
    print(f"  Train embeddings: {train_embeddings.shape}")
    print(f"  Test embeddings: {test_embeddings.shape}")
    
    # Load payloads
    print("\nLoading payloads...")
    
    with open(OUTPUT_DIR / "train_payloads.json", 'r', encoding='utf-8') as f:
        train_payloads = json.load(f)
    
    with open(OUTPUT_DIR / "test_payloads.json", 'r', encoding='utf-8') as f:
        test_payloads = json.load(f)
    
    print(f"  Train payloads: {len(train_payloads)}")
    print(f"  Test payloads: {len(test_payloads)}")
    
    # Get vector size
    vector_size = train_embeddings.shape[1]
    
    # Create collection
    create_collection(client, vector_size)
    
    # Ingest train data
    train_count = ingest_data(client, train_embeddings, train_payloads, "train")
    
    # Ingest test data
    test_count = ingest_data(client, test_embeddings, test_payloads, "test")
    
    # Verify collection
    info = verify_collection(client)
    
    # Save ingestion report
    report = {
        'collection_name': QDRANT_COLLECTION_NAME,
        'host': QDRANT_HOST,
        'port': QDRANT_PORT,
        'vector_size': vector_size,
        'train_points': train_count,
        'test_points': test_count,
        'total_points': info.points_count,
        'status': str(info.status)
    }
    
    with open(OUTPUT_DIR / "qdrant_ingestion_report.json", 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\n" + "=" * 60)
    print("✅ QDRANT INGESTION COMPLETE")
    print("=" * 60)
    print(f"Collection: {QDRANT_COLLECTION_NAME}")
    print(f"Total points: {info.points_count}")
    print(f"Train/Test: {train_count}/{test_count}")


if __name__ == "__main__":
    main()
