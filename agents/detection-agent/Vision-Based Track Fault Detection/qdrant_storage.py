"""
Qdrant Storage for Track Faults
================================
Stores detected track faults in Qdrant vector database for:
- Historical analysis and pattern recognition
- Similar fault case retrieval for resolution suggestions
- Maintenance scheduling optimization

Author: RailMind Team
"""

import os
import json
import base64
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import uuid


@dataclass
class TrackFaultRecord:
    """Record of a detected track fault for Qdrant storage."""
    fault_id: str
    fault_type: str  # rail_crack, wear, fastener_loose, sleeper_damage, corrosion
    confidence: float
    edge_location: str  # e.g., "VOGHERA--PAVIA"
    image_path: str
    timestamp: str
    status: str  # "detected", "confirmed", "maintenance_scheduled", "resolved"
    maintenance_eta_minutes: Optional[int] = None
    resolution_notes: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TrackFaultQdrantStorage:
    """
    Stores and retrieves track fault records from Qdrant.
    Uses text embeddings to find similar historical faults.
    """
    
    COLLECTION_NAME = "rail_track_faults"
    VECTOR_SIZE = 384  # Using sentence-transformers mini model
    
    def __init__(self):
        self.client = None
        self.embedding_model = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Qdrant client and embedding model."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct
            
            # Try cloud first, then local
            qdrant_url = os.environ.get("QDRANT_CLOUD_URL", "")
            qdrant_key = os.environ.get("QDRANT_API_KEY", "")
            
            if qdrant_url and qdrant_key:
                print(f"[TrackFault-Qdrant] Connecting to Qdrant Cloud...")
                self.client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=60)
            else:
                print(f"[TrackFault-Qdrant] Connecting to local Qdrant at localhost:6333...")
                self.client = QdrantClient(host="localhost", port=6333, timeout=30)
            
            # Create collection if not exists
            self._ensure_collection()
            print(f"[TrackFault-Qdrant] ✅ Connected successfully!")
            
        except ImportError:
            print("[TrackFault-Qdrant] ⚠️ qdrant-client not installed, running in demo mode")
            self.client = None
        except Exception as e:
            print(f"[TrackFault-Qdrant] ⚠️ Could not connect to Qdrant: {e}")
            self.client = None
        
        # Initialize embedding model
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("[TrackFault-Qdrant] ✅ Embedding model loaded")
        except ImportError:
            print("[TrackFault-Qdrant] ⚠️ sentence-transformers not installed, using random embeddings")
            self.embedding_model = None
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        if not self.client:
            return
        
        from qdrant_client.models import Distance, VectorParams
        
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.COLLECTION_NAME not in collection_names:
            print(f"[TrackFault-Qdrant] Creating collection: {self.COLLECTION_NAME}")
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE
                )
            )
    
    def _generate_embedding(self, fault_record: TrackFaultRecord) -> List[float]:
        """Generate embedding from fault description."""
        # Create text description for embedding
        text = f"""
        Track fault detected: {fault_record.fault_type}
        Location: {fault_record.edge_location}
        Confidence: {fault_record.confidence:.1%}
        Status: {fault_record.status}
        Time: {fault_record.timestamp}
        """
        
        if self.embedding_model:
            embedding = self.embedding_model.encode(text).tolist()
        else:
            # Fallback: random embedding for demo
            np.random.seed(hash(text) % 2**32)
            embedding = np.random.rand(self.VECTOR_SIZE).tolist()
        
        return embedding
    
    def store_fault(self, fault_record: TrackFaultRecord) -> bool:
        """
        Store a track fault record in Qdrant.
        
        Args:
            fault_record: The fault record to store
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            print(f"[TrackFault-Qdrant] Demo mode: Would store fault {fault_record.fault_id}")
            return True
        
        try:
            from qdrant_client.models import PointStruct
            
            embedding = self._generate_embedding(fault_record)
            
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=fault_record.to_dict()
            )
            
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[point]
            )
            
            print(f"[TrackFault-Qdrant] ✅ Stored fault: {fault_record.fault_type} at {fault_record.edge_location}")
            return True
            
        except Exception as e:
            print(f"[TrackFault-Qdrant] ❌ Failed to store fault: {e}")
            return False
    
    def search_similar_faults(
        self, 
        fault_type: str, 
        edge_location: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search for similar historical faults to get resolution suggestions.
        
        Args:
            fault_type: Type of fault (rail_crack, wear, etc.)
            edge_location: Edge where fault was detected
            limit: Maximum number of results
            
        Returns:
            List of similar fault records with resolution info
        """
        if not self.client:
            # Demo mode: return mock similar faults
            return self._get_demo_similar_faults(fault_type)
        
        try:
            # Create query text
            query_text = f"Track fault: {fault_type} at location {edge_location}"
            
            if self.embedding_model:
                query_vector = self.embedding_model.encode(query_text).tolist()
            else:
                np.random.seed(hash(query_text) % 2**32)
                query_vector = np.random.rand(self.VECTOR_SIZE).tolist()
            
            results = self.client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_vector,
                limit=limit
            )
            
            return [
                {
                    "score": hit.score,
                    **hit.payload
                }
                for hit in results.points
            ]
            
        except Exception as e:
            print(f"[TrackFault-Qdrant] Search error: {e}")
            return self._get_demo_similar_faults(fault_type)
    
    def _get_demo_similar_faults(self, fault_type: str) -> List[Dict]:
        """Return demo similar faults for testing."""
        demo_resolutions = {
            "rail_crack": [
                {"fault_type": "rail_crack", "resolution_notes": "Emergency rail replacement, 45 min downtime", "maintenance_eta_minutes": 45},
                {"fault_type": "rail_crack", "resolution_notes": "Temporary speed restriction to 40km/h, repair scheduled overnight", "maintenance_eta_minutes": 120},
            ],
            "wear": [
                {"fault_type": "wear", "resolution_notes": "Rail grinding scheduled during low-traffic hours", "maintenance_eta_minutes": 90},
                {"fault_type": "wear", "resolution_notes": "Wear within tolerance, monitoring increased", "maintenance_eta_minutes": 0},
            ],
            "fastener_loose": [
                {"fault_type": "fastener_loose", "resolution_notes": "Tightening crew dispatched, 20 min fix", "maintenance_eta_minutes": 20},
            ],
            "sleeper_damage": [
                {"fault_type": "sleeper_damage", "resolution_notes": "Sleeper replacement, track closed for 2 hours", "maintenance_eta_minutes": 120},
            ],
            "corrosion": [
                {"fault_type": "corrosion", "resolution_notes": "Anti-corrosion treatment applied, monitoring", "maintenance_eta_minutes": 30},
            ],
        }
        return demo_resolutions.get(fault_type, [{"resolution_notes": "Standard inspection required", "maintenance_eta_minutes": 60}])
    
    def update_fault_status(
        self, 
        fault_id: str, 
        new_status: str,
        resolution_notes: Optional[str] = None
    ) -> bool:
        """Update the status of a fault record."""
        if not self.client:
            print(f"[TrackFault-Qdrant] Demo mode: Would update fault {fault_id} to {new_status}")
            return True
        
        try:
            # Search for the fault by ID
            results = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter={
                    "must": [
                        {"key": "fault_id", "match": {"value": fault_id}}
                    ]
                },
                limit=1
            )
            
            if results[0]:
                point_id = results[0][0].id
                payload_update = {"status": new_status}
                if resolution_notes:
                    payload_update["resolution_notes"] = resolution_notes
                
                self.client.set_payload(
                    collection_name=self.COLLECTION_NAME,
                    payload=payload_update,
                    points=[point_id]
                )
                return True
            return False
            
        except Exception as e:
            print(f"[TrackFault-Qdrant] Update error: {e}")
            return False
    
    def get_active_faults(self) -> List[Dict]:
        """Get all faults that are not yet resolved."""
        if not self.client:
            return []
        
        try:
            results = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter={
                    "must_not": [
                        {"key": "status", "match": {"value": "resolved"}}
                    ]
                },
                limit=100
            )
            
            return [point.payload for point in results[0]]
            
        except Exception as e:
            print(f"[TrackFault-Qdrant] Get active faults error: {e}")
            return []


# Singleton instance
_storage_instance: Optional[TrackFaultQdrantStorage] = None

def get_qdrant_storage() -> TrackFaultQdrantStorage:
    """Get singleton Qdrant storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = TrackFaultQdrantStorage()
    return _storage_instance


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("TRACK FAULT QDRANT STORAGE - TEST")
    print("=" * 60)
    
    storage = get_qdrant_storage()
    
    # Create a test fault record
    test_fault = TrackFaultRecord(
        fault_id=f"TF-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        fault_type="wear",
        confidence=0.748,
        edge_location="VOGHERA--PAVIA",
        image_path="images/7.MOV_20201228114152_10038.JPEG",
        timestamp=datetime.now().isoformat(),
        status="detected",
        lat=45.0,
        lon=9.1
    )
    
    # Store the fault
    print("\n1. Storing fault record...")
    storage.store_fault(test_fault)
    
    # Search for similar faults
    print("\n2. Searching for similar historical faults...")
    similar = storage.search_similar_faults("wear", "VOGHERA--PAVIA")
    for i, s in enumerate(similar, 1):
        print(f"   {i}. {s.get('resolution_notes', 'N/A')} (ETA: {s.get('maintenance_eta_minutes', 'N/A')} min)")
    
    print("\n✅ Test complete!")
