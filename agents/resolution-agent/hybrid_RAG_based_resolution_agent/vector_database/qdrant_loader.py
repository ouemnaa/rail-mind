"""
Qdrant Vector Database Loader
Loads conflicts from JSON file into Qdrant vector database (safe for cloud)
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer


class QdrantConflictLoader:
    """
    Loads conflict-resolution pairs from JSON into Qdrant
    """

    def __init__(
        self,
        collection_name: str,
        qdrant_url: str,
        qdrant_api_key: str,
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize Qdrant loader

        Args:
            collection_name: Name of the Qdrant collection
            qdrant_url: Qdrant cloud endpoint URL
            qdrant_api_key: API key for Qdrant cloud
            embedding_model: SentenceTransformer model to use for embeddings
        """
        self.collection_name = collection_name

        # Initialize Qdrant client (cloud)
        print(f"Connecting to Qdrant Cloud at {qdrant_url}...")
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

        # Initialize embedding model
        print(f"Loading embedding model: {embedding_model}...")
        self.embedding_model = SentenceTransformer(embedding_model)

        # Get embedding dimension
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        print(f"✓ Embedding dimension: {self.embedding_dim}")

    def create_collection(self):
        """
        Create Qdrant collection if it does not exist (SAFE: never delete existing collection)
        """
        collections = self.client.get_collections().collections
        if any(c.name == self.collection_name for c in collections):
            print(f"✓ Collection '{self.collection_name}' already exists. Using it.")
            return

        # Create collection
        print(f"Creating collection: {self.collection_name}")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.embedding_dim,
                distance=Distance.COSINE
            )
        )
        print(f"✓ Collection created successfully")

    def load_from_json(
        self,
        json_file: str,
        batch_size: int = 100
    ) -> int:
        """
        Load conflicts from JSON file into Qdrant
        """
        json_path = Path(json_file)

        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_file}")

        # Load JSON file
        print(f"\n📂 Loading conflicts from {json_file}...")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conflicts = data.get('conflicts', [])

        if not conflicts:
            print("⚠️  No conflicts found in JSON file")
            return 0

        print(f"   Found {len(conflicts)} conflicts")
        print(f"\n🔄 Processing and uploading to Qdrant...")

        total_uploaded = 0

        for i in range(0, len(conflicts), batch_size):
            batch = conflicts[i:i + batch_size]
            points = []

            for conflict in batch:
                embedding_text = self._create_embedding_text(conflict)
                embedding = self.embedding_model.encode(embedding_text).tolist()

                point = PointStruct(
                    id=conflict['id'],  # Ensure each conflict has unique ID
                    vector=embedding,
                    payload=conflict
                )
                points.append(point)

            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

            total_uploaded += len(points)
            print(f"   ✓ Uploaded {total_uploaded}/{len(conflicts)} conflicts")

        print(f"\n✓ Successfully loaded {total_uploaded} conflicts into Qdrant")
        return total_uploaded

    def _create_embedding_text(self, conflict: Dict[str, Any]) -> str:
        parts = [
            f"Problem: {conflict['conflict_description']}",
            f"Type: {conflict['conflict_type']}",
            f"Solution: {conflict['resolution_strategy']}",
            f"Reasoning: {conflict['reasoning']}"
        ]
        if conflict.get('context'):
            parts.append(f"Context: {conflict['context']}")
        return "\n".join(parts)

    def query_similar(
        self,
        query_text: str,
        limit: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_model.encode(query_text).tolist()
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold
        )

        results = []
        for hit in search_results:
            results.append({
                "score": hit.score,
                "id": hit.payload['id'],
                "conflict_description": hit.payload['conflict_description'],
                "conflict_type": hit.payload['conflict_type'],
                "resolution_strategy": hit.payload['resolution_strategy'],
                "reasoning": hit.payload['reasoning'],
                "context": hit.payload.get('context', ''),
                "confidence": hit.payload['confidence']
            })
        return results

    def get_statistics(self) -> Dict[str, Any]:
        collection_info = self.client.get_collection(self.collection_name)
        return {
            "total_points": collection_info.points_count,
            "vector_dimension": self.embedding_dim,
            "collection_name": self.collection_name
        }


# =========================
# Example Usage
# =========================

def main():
    """
    Complete workflow: Load JSON into Qdrant
    """
    import sys

    # =========================
    # ⚠️ CHANGE THESE BEFORE RUNNING
    # =========================
    JSON_FILE = "conflict_knowledge_base_uuid.json"   # your JSON file
    COLLECTION_NAME = "railway_algorithms"       # must be exactly your cloud collection
    QDRANT_URL = "https://cf323744-546a-492d-b614-8542cb3ce423.us-east-1-1.aws.cloud.qdrant.io"  # replace with your endpoint
    QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.fI89vclTejMkRnUs-MbAmV-O4PwoQcYE1DO_fN6l7LM"                 # replace with your API key

    # Check JSON exists
    if not Path(JSON_FILE).exists():
        print(f"❌ Error: JSON file not found: {JSON_FILE}")
        return 1

    try:
        # Initialize loader
        loader = QdrantConflictLoader(
            collection_name=COLLECTION_NAME,
            qdrant_url=QDRANT_URL,
            qdrant_api_key=QDRANT_API_KEY
        )

        # Create collection if not exists (SAFE)
        loader.create_collection()

        # Load conflicts
        loader.load_from_json(JSON_FILE)

        # Show stats
        stats = loader.get_statistics()
        print(f"\n✓ Collection: {stats['collection_name']}")
        print(f"✓ Total conflicts: {stats['total_points']}")
        print(f"✓ Vector dimension: {stats['vector_dimension']}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
