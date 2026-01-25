"""
Qdrant Operational Memory
=========================

Similarity search for finding similar historical incidents.
When a conflict is predicted, this module finds past cases with
similar characteristics to suggest likely resolutions.
"""

import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import warnings

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
    from sentence_transformers import SentenceTransformer
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    warnings.warn("qdrant-client or sentence-transformers not installed")

try:
    from .config import qdrant_config, FAULT_DATA
    from .predictor import ConflictPrediction
except ImportError:
    from config import qdrant_config, FAULT_DATA
    from predictor import ConflictPrediction


@dataclass
class SimilarCase:
    """A similar historical case found via Qdrant."""
    case_id: str
    similarity_score: float
    date: str
    line: str
    location: str
    incident_type: str
    delay_duration_min: float
    affected_trains: int
    resolution_types: List[str]
    resolution_description: str
    time_of_day: str
    severity_score: float


@dataclass
class MemorySearchResult:
    """Result of searching operational memory."""
    query_train_id: str
    query_conflict_type: str
    query_location: str
    similar_cases: List[SimilarCase]
    suggested_resolution: Optional[str]
    typical_delay_min: float
    confidence: float


class OperationalMemory:
    """
    Qdrant-based operational memory for finding similar historical incidents.
    
    Uses semantic search to find past incidents that are similar to the
    current predicted conflict, enabling experience-based resolution suggestions.
    
    Features:
    - Multilingual embeddings (Italian station names + English descriptions)
    - Semantic similarity search
    - Resolution pattern learning
    - Confidence scoring
    """
    
    def __init__(
        self,
        initialize: bool = True,
        data_path: Optional[Path] = None
    ):
        """
        Initialize operational memory.
        
        Args:
            initialize: Whether to initialize Qdrant connection
            data_path: Path to historical incident data
        """
        self.config = qdrant_config
        self.data_path = data_path or FAULT_DATA
        self.client = None
        self.encoder = None
        self.collection_ready = False
        
        if initialize and QDRANT_AVAILABLE:
            self._initialize()
    
    def _initialize(self):
        """Initialize Qdrant client and embedding model."""
        try:
            # Initialize Qdrant client
            if self.config.mode == "cloud" and self.config.cloud_url:
                self.client = QdrantClient(
                    url=self.config.cloud_url,
                    api_key=self.config.api_key
                )
            else:
                self.client = QdrantClient(
                    host=self.config.host,
                    port=self.config.port
                )
            
            # Initialize embedding model
            self.encoder = SentenceTransformer(self.config.embedding_model)
            
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.config.collection_name in collection_names:
                self.collection_ready = True
            else:
                print(f"Collection '{self.config.collection_name}' not found. "
                      f"Run setup_collection() to create it.")
                
        except Exception as e:
            warnings.warn(f"Failed to initialize Qdrant: {e}")
            self.client = None
    
    def setup_collection(self, recreate: bool = False):
        """
        Create and populate the Qdrant collection.
        
        Args:
            recreate: If True, delete existing collection and recreate
        """
        if not QDRANT_AVAILABLE or self.client is None:
            raise RuntimeError("Qdrant not available")
        
        # Create collection
        if recreate:
            try:
                self.client.delete_collection(self.config.collection_name)
            except:
                pass
        
        self.client.create_collection(
            collection_name=self.config.collection_name,
            vectors_config=rest.VectorParams(
                size=self.config.vector_size,
                distance=rest.Distance.COSINE
            )
        )
        
        # Load and index historical data
        incidents = self._load_historical_data()
        if incidents:
            self._index_incidents(incidents)
        
        self.collection_ready = True
    
    def _load_historical_data(self) -> List[Dict]:
        """Load historical incident data."""
        if not self.data_path.exists():
            print(f"Warning: Historical data not found at {self.data_path}")
            return []
        
        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data if isinstance(data, list) else []
    
    def _index_incidents(self, incidents: List[Dict]):
        """Index incidents into Qdrant collection."""
        if not incidents:
            return
        
        # Prepare points for indexing
        points = []
        
        for i, incident in enumerate(incidents):
            # Create embedding text
            embedding_text = incident.get("embedding_text_enhanced", "")
            if not embedding_text:
                embedding_text = self._create_embedding_text(incident)
            
            # Generate embedding
            embedding = self.encoder.encode(embedding_text).tolist()
            
            # Create payload with all relevant metadata
            payload = {
                "date": incident.get("date", ""),
                "line": incident.get("line_normalized", incident.get("line", "")),
                "location_station": incident.get("location_station", ""),
                "location_segment": incident.get("location_segment", ""),
                "incident_type": incident.get("incident_type", ""),
                "delay_duration_min": incident.get("delay_duration_min", 0),
                "affected_trains_total": incident.get("affected_trains_total", 0),
                "resolution_types": incident.get("resolution_types", ""),
                "has_resolution": incident.get("has_resolution", False),
                "time_of_day": incident.get("time_of_day", ""),
                "severity_score": incident.get("severity_score", 0),
                "matched_region": incident.get("matched_region", ""),
                "embedding_text": embedding_text
            }
            
            points.append(rest.PointStruct(
                id=i,
                vector=embedding,
                payload=payload
            ))
        
        # Batch upload
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.config.collection_name,
                points=batch
            )
        
        print(f"Indexed {len(points)} incidents into Qdrant")
    
    def _create_embedding_text(self, incident: Dict) -> str:
        """Create embedding text from incident data."""
        parts = []
        
        if incident.get("incident_type"):
            parts.append(f"{incident['incident_type']} incident")
        
        if incident.get("line"):
            parts.append(f"on {incident['line']}")
        
        if incident.get("location_station"):
            parts.append(f"near {incident['location_station']}")
        
        if incident.get("delay_duration_min"):
            parts.append(f"causing {incident['delay_duration_min']} minutes delay")
        
        if incident.get("affected_trains_total"):
            parts.append(f"affecting {incident['affected_trains_total']} trains")
        
        if incident.get("resolution_types"):
            parts.append(f"resolved by {incident['resolution_types']}")
        
        if incident.get("time_of_day"):
            parts.append(f"during {incident['time_of_day']}")
        
        return ". ".join(parts) + "."
    
    def search_similar(
        self,
        prediction: ConflictPrediction,
        additional_context: Optional[Dict] = None,
        top_k: Optional[int] = None
    ) -> MemorySearchResult:
        """
        Search for similar historical incidents.
        
        Args:
            prediction: Current conflict prediction
            additional_context: Additional context for the search
            top_k: Number of results to return
            
        Returns:
            MemorySearchResult with similar cases and suggestions
        """
        top_k = top_k or self.config.top_k
        
        if not QDRANT_AVAILABLE or not self.collection_ready:
            return self._fallback_search(prediction)
        
        # Create query embedding
        query_text = self._create_query_text(prediction, additional_context)
        query_embedding = self.encoder.encode(query_text).tolist()
        
        # Search Qdrant
        results = self.client.search(
            collection_name=self.config.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            score_threshold=self.config.score_threshold
        )
        
        # Convert to SimilarCase objects
        similar_cases = []
        for result in results:
            payload = result.payload
            similar_cases.append(SimilarCase(
                case_id=str(result.id),
                similarity_score=result.score,
                date=payload.get("date", ""),
                line=payload.get("line", ""),
                location=payload.get("location_station", ""),
                incident_type=payload.get("incident_type", ""),
                delay_duration_min=payload.get("delay_duration_min", 0),
                affected_trains=payload.get("affected_trains_total", 0),
                resolution_types=payload.get("resolution_types", "").split("|"),
                resolution_description=payload.get("embedding_text", ""),
                time_of_day=payload.get("time_of_day", ""),
                severity_score=payload.get("severity_score", 0)
            ))
        
        # Analyze results for suggestions
        suggested_resolution = self._suggest_resolution(similar_cases)
        typical_delay = self._calculate_typical_delay(similar_cases)
        confidence = self._calculate_search_confidence(similar_cases)
        
        return MemorySearchResult(
            query_train_id=prediction.train_id,
            query_conflict_type=prediction.predicted_conflict_type or "unknown",
            query_location=prediction.predicted_location or "unknown",
            similar_cases=similar_cases,
            suggested_resolution=suggested_resolution,
            typical_delay_min=typical_delay,
            confidence=confidence
        )
    
    def _create_query_text(
        self,
        prediction: ConflictPrediction,
        additional_context: Optional[Dict]
    ) -> str:
        """Create query text for embedding search."""
        parts = []
        
        if prediction.predicted_conflict_type:
            # Map conflict type to incident type
            type_mapping = {
                "platform_conflict": "operational",
                "track_conflict": "infrastructure",
                "headway_violation": "operational",
                "capacity_exceeded": "congestion",
                "schedule_deviation": "delay",
                "cascading_delay": "delay propagation"
            }
            incident_type = type_mapping.get(
                prediction.predicted_conflict_type, 
                prediction.predicted_conflict_type
            )
            parts.append(f"{incident_type} incident")
        
        if prediction.predicted_location:
            parts.append(f"near {prediction.predicted_location}")
        
        for factor in prediction.contributing_factors[:3]:
            parts.append(factor)
        
        if additional_context:
            if additional_context.get("line"):
                parts.append(f"on {additional_context['line']}")
            if additional_context.get("time_of_day"):
                parts.append(f"during {additional_context['time_of_day']}")
        
        return ". ".join(parts) + "."
    
    def _suggest_resolution(self, similar_cases: List[SimilarCase]) -> Optional[str]:
        """Suggest resolution based on similar cases."""
        if not similar_cases:
            return None
        
        # Count resolution types
        resolution_counts = {}
        for case in similar_cases:
            for res_type in case.resolution_types:
                res_type = res_type.strip()
                if res_type:
                    resolution_counts[res_type] = resolution_counts.get(res_type, 0) + 1
        
        if not resolution_counts:
            return "Monitor situation and prepare contingency"
        
        # Get most common resolution
        most_common = max(resolution_counts, key=resolution_counts.get)
        
        # Map to actionable suggestion
        resolution_suggestions = {
            "SPEED_REGULATE": "Reduce speed on affected segment",
            "GRADUAL_RECOVERY": "Implement gradual recovery plan",
            "REROUTE": "Consider alternative routing",
            "DELAY": "Apply controlled delay to resolve conflict",
            "HOLD": "Hold train at current station",
            "PRIORITY_CHANGE": "Adjust train priorities",
            "PLATFORM_CHANGE": "Reassign platform allocation"
        }
        
        return resolution_suggestions.get(most_common, f"Apply {most_common}")
    
    def _calculate_typical_delay(self, similar_cases: List[SimilarCase]) -> float:
        """Calculate typical delay from similar cases."""
        if not similar_cases:
            return 0.0
        
        delays = [c.delay_duration_min for c in similar_cases if c.delay_duration_min > 0]
        
        if not delays:
            return 0.0
        
        # Use weighted average (higher similarity = higher weight)
        weights = [c.similarity_score for c in similar_cases if c.delay_duration_min > 0]
        weighted_sum = sum(d * w for d, w in zip(delays, weights))
        weight_total = sum(weights)
        
        return weighted_sum / weight_total if weight_total > 0 else np.mean(delays)
    
    def _calculate_search_confidence(self, similar_cases: List[SimilarCase]) -> float:
        """Calculate confidence in search results."""
        if not similar_cases:
            return 0.0
        
        # Factors affecting confidence:
        # 1. Number of results found
        count_factor = min(len(similar_cases) / self.config.top_k, 1.0)
        
        # 2. Average similarity score
        avg_similarity = np.mean([c.similarity_score for c in similar_cases])
        
        # 3. Consistency of resolutions
        resolution_types = set()
        for case in similar_cases:
            resolution_types.update(case.resolution_types)
        consistency_factor = 1.0 / max(len(resolution_types), 1)
        
        # Weighted combination
        confidence = (
            count_factor * 0.3 +
            avg_similarity * 0.5 +
            consistency_factor * 0.2
        )
        
        return min(confidence, 0.95)
    
    def _fallback_search(self, prediction: ConflictPrediction) -> MemorySearchResult:
        """Provide fallback results when Qdrant is not available."""
        # Create generic suggestions based on conflict type
        type_suggestions = {
            "platform_conflict": "Reassign platform or delay one train",
            "track_conflict": "Hold one train at previous station",
            "headway_violation": "Increase headway through speed adjustment",
            "capacity_exceeded": "Divert some trains to alternative routes",
            "schedule_deviation": "Implement recovery timetable",
            "cascading_delay": "Apply selective delays to break cascade"
        }
        
        return MemorySearchResult(
            query_train_id=prediction.train_id,
            query_conflict_type=prediction.predicted_conflict_type or "unknown",
            query_location=prediction.predicted_location or "unknown",
            similar_cases=[],
            suggested_resolution=type_suggestions.get(
                prediction.predicted_conflict_type, 
                "Monitor situation and apply standard procedures"
            ),
            typical_delay_min=5.0,  # Default estimate
            confidence=0.3  # Low confidence for fallback
        )
    
    def get_resolution_statistics(self) -> Dict[str, Any]:
        """Get statistics about resolutions in the database."""
        if not self.collection_ready:
            return {"error": "Collection not ready"}
        
        # This would require scrolling through all points
        # For now, return placeholder
        return {
            "total_incidents": "unknown",
            "resolution_types": ["SPEED_REGULATE", "GRADUAL_RECOVERY", "REROUTE", "DELAY", "HOLD"],
            "average_delay_min": 30,
            "most_common_resolution": "SPEED_REGULATE"
        }


# Factory function
def create_operational_memory(
    mode: str = "local",
    initialize: bool = True
) -> OperationalMemory:
    """
    Factory function to create operational memory.
    
    Args:
        mode: "local" for Docker Qdrant, "cloud" for Qdrant Cloud
        initialize: Whether to initialize immediately
        
    Returns:
        Configured OperationalMemory instance
    """
    from .config import QdrantConfig
    
    config = QdrantConfig(mode=mode)
    # Update global config
    from . import config as cfg
    cfg.qdrant_config = config
    
    return OperationalMemory(initialize=initialize)
