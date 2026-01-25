"""
Step 5: Query Examples and Utilities
====================================
Example queries and utility functions for searching the Qdrant database.
Demonstrates conflict detection and prediction capabilities.

Author: AI Rail Network Brain Team
Date: January 2026
"""

import numpy as np
import json
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

import os
from config import (
    OUTPUT_DIR, QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION_NAME,
    EMBEDDING_MODEL, USE_OPENAI_EMBEDDINGS, OPENAI_EMBEDDING_MODEL,
    QDRANT_MODE, QDRANT_CLOUD_URL, QDRANT_API_KEY
)


class RailIncidentSearch:
    """Search interface for rail incident database."""
    
    def __init__(self):
        self.client = None
        self.model = None
        self._connect()
    
    def _connect(self):
        """Connect to Qdrant (Cloud or Local) and load embedding model."""
        try:
            from qdrant_client import QdrantClient
            
            if QDRANT_MODE == "cloud":
                # Qdrant Cloud connection
                api_key = os.environ.get("QDRANT_API_KEY", QDRANT_API_KEY)
                self.client = QdrantClient(
                    url=QDRANT_CLOUD_URL,
                    api_key=api_key,
                    timeout=120
                )
                print(f"✅ Connected to Qdrant Cloud")
            else:
                # Local Docker connection
                self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=60)
                print(f"✅ Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
        except Exception as e:
            print(f"❌ Failed to connect to Qdrant: {e}")
            return
        
        # Load embedding model
        if not USE_OPENAI_EMBEDDINGS:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(EMBEDDING_MODEL)
                print(f"✅ Loaded embedding model: {EMBEDDING_MODEL}")
            except ImportError:
                print("⚠️ sentence-transformers not available, text queries disabled")
    
    def embed_text(self, text):
        """Generate embedding for a query text."""
        if self.model is None:
            raise ValueError("Embedding model not loaded")
        return self.model.encode(text).tolist()
    
    def search_similar_incidents(self, query_text, limit=5, filters=None):
        """
        Search for incidents similar to a text description.
        
        Args:
            query_text: Natural language description of incident
            limit: Number of results to return
            filters: Optional Qdrant filter conditions
        
        Returns:
            List of similar incidents with scores
        """
        if self.client is None:
            print("❌ Not connected to Qdrant")
            return []
        
        # Generate query embedding
        query_vector = self.embed_text(query_text)
        
        # Build filter if provided
        query_filter = None
        if filters:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
            conditions = []
            
            for field, value in filters.items():
                if isinstance(value, dict) and ('gte' in value or 'lte' in value):
                    # Range filter
                    conditions.append(FieldCondition(
                        key=field,
                        range=Range(**value)
                    ))
                else:
                    # Match filter
                    conditions.append(FieldCondition(
                        key=field,
                        match=MatchValue(value=value)
                    ))
            
            query_filter = Filter(must=conditions)
        
        # Search using query_points (newer Qdrant API)
        response = self.client.query_points(
            collection_name=QDRANT_COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True
        )
        
        return response.points
    
    def search_by_location(self, lat, lon, radius_km=50, limit=10):
        """
        Search for incidents near a geographic location.
        
        Args:
            lat: Latitude
            lon: Longitude
            radius_km: Search radius in kilometers
            limit: Number of results
        
        Returns:
            List of nearby incidents
        """
        from qdrant_client.models import Filter, FieldCondition, Range
        
        # Approximate degree to km conversion at Italian latitudes
        lat_delta = radius_km / 111
        lon_delta = radius_km / (111 * np.cos(np.radians(lat)))
        
        # Create geo filter
        geo_filter = Filter(must=[
            FieldCondition(
                key="incident_lat",
                range=Range(gte=lat - lat_delta, lte=lat + lat_delta)
            ),
            FieldCondition(
                key="incident_lon",
                range=Range(gte=lon - lon_delta, lte=lon + lon_delta)
            )
        ])
        
        # Scroll through results
        results, _ = self.client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            scroll_filter=geo_filter,
            limit=limit,
            with_payload=True
        )
        
        return results
    
    def search_by_severity(self, min_severity=50, limit=10):
        """
        Search for high-severity incidents.
        
        Args:
            min_severity: Minimum severity score (0-100)
            limit: Number of results
        
        Returns:
            List of high-severity incidents
        """
        from qdrant_client.models import Filter, FieldCondition, Range
        
        severity_filter = Filter(must=[
            FieldCondition(
                key="severity_score",
                range=Range(gte=min_severity)
            )
        ])
        
        results, _ = self.client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            scroll_filter=severity_filter,
            limit=limit,
            with_payload=True
        )
        
        return results
    
    def search_recurring_incidents(self, limit=10):
        """
        Find recurring incidents (same location, multiple occurrences).
        
        Returns:
            List of recurring incidents
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        recurring_filter = Filter(must=[
            FieldCondition(
                key="is_recurring_location",
                match=MatchValue(value=True)
            )
        ])
        
        results, _ = self.client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            scroll_filter=recurring_filter,
            limit=limit,
            with_payload=True
        )
        
        return results
    
    def predict_resolution(self, incident_description):
        """
        Predict likely resolution strategies based on similar past incidents.
        
        Args:
            incident_description: Description of current incident
        
        Returns:
            Dictionary with resolution predictions and confidence
        """
        # Find similar incidents
        similar = self.search_similar_incidents(incident_description, limit=10)
        
        if not similar:
            return {"error": "No similar incidents found"}
        
        # Aggregate resolution types
        resolution_counts = {}
        total_weight = 0
        
        for result in similar:
            resolution_types = result.payload.get('resolution_types', '')
            score = result.score
            
            if resolution_types:
                # Handle both string and list formats
                if isinstance(resolution_types, str):
                    resolutions = resolution_types.split('|')
                else:
                    resolutions = resolution_types
                
                for res in resolutions:
                    if res:
                        resolution_counts[res] = resolution_counts.get(res, 0) + score
                        total_weight += score
        
        # Calculate confidence scores
        predictions = {}
        for res, weight in sorted(resolution_counts.items(), key=lambda x: -x[1]):
            predictions[res] = round(weight / total_weight * 100, 1) if total_weight > 0 else 0
        
        # Get average metrics from similar incidents
        avg_delay = np.mean([r.payload.get('delay_duration_min', 0) for r in similar if r.payload.get('delay_duration_min')])
        avg_affected = np.mean([r.payload.get('affected_trains_total', 0) for r in similar if r.payload.get('affected_trains_total')])
        
        return {
            'predicted_resolutions': predictions,
            'confidence': round(similar[0].score * 100, 1) if similar else 0,
            'based_on_incidents': len(similar),
            'estimated_delay_minutes': round(avg_delay, 0) if not np.isnan(avg_delay) else None,
            'estimated_affected_trains': round(avg_affected, 0) if not np.isnan(avg_affected) else None,
            'similar_incidents': [
                {
                    'type': r.payload.get('incident_type'),
                    'line': r.payload.get('line_normalized'),
                    'resolution': r.payload.get('resolution_types'),
                    'similarity': round(r.score, 3)
                }
                for r in similar[:3]
            ]
        }
    
    def get_statistics(self):
        """Get collection statistics."""
        if self.client is None:
            return None
        
        info = self.client.get_collection(QDRANT_COLLECTION_NAME)
        return {
            'total_points': info.points_count,
            'status': str(info.status)
        }


def demo_queries():
    """Demonstrate various query capabilities."""
    print("=" * 60)
    print("QDRANT QUERY DEMONSTRATIONS")
    print("=" * 60)
    
    search = RailIncidentSearch()
    
    if search.client is None:
        return
    
    # Demo 1: Similar incident search
    print("\n📌 DEMO 1: Search Similar Incidents")
    print("-" * 40)
    
    query = "technical failure on high speed line causing delays during morning rush hour"
    print(f"Query: {query}")
    
    results = search.search_similar_incidents(query, limit=3)
    
    for i, result in enumerate(results):
        print(f"\n  {i+1}. Score: {result.score:.3f}")
        print(f"     Type: {result.payload.get('incident_type')}")
        print(f"     Line: {result.payload.get('line_normalized')}")
        print(f"     Delay: {result.payload.get('delay_duration_min')} min")
        print(f"     Resolution: {result.payload.get('resolution_types')}")
    
    # Demo 2: Predict resolution
    print("\n📌 DEMO 2: Predict Resolution for New Incident")
    print("-" * 40)
    
    new_incident = "unauthorized person near tracks on Bologna-Venice line during afternoon"
    print(f"Incident: {new_incident}")
    
    prediction = search.predict_resolution(new_incident)
    
    print(f"\n  Predicted Resolutions:")
    for res, conf in prediction.get('predicted_resolutions', {}).items():
        print(f"    - {res}: {conf}%")
    
    print(f"\n  Estimated delay: {prediction.get('estimated_delay_minutes')} minutes")
    print(f"  Estimated affected trains: {prediction.get('estimated_affected_trains')}")
    print(f"  Confidence: {prediction.get('confidence')}%")
    
    # Demo 3: High severity incidents
    print("\n📌 DEMO 3: High Severity Incidents (>50)")
    print("-" * 40)
    
    high_severity = search.search_by_severity(min_severity=50, limit=3)
    
    for i, result in enumerate(high_severity):
        print(f"\n  {i+1}. Severity: {result.payload.get('severity_score')}")
        print(f"     Type: {result.payload.get('incident_type')}")
        print(f"     Line: {result.payload.get('line_normalized')}")
        print(f"     Affected trains: {result.payload.get('affected_trains_total')}")
    
    # Demo 4: Recurring incidents
    print("\n📌 DEMO 4: Recurring Incidents")
    print("-" * 40)
    
    recurring = search.search_recurring_incidents(limit=3)
    
    for i, result in enumerate(recurring):
        print(f"\n  {i+1}. Location: {result.payload.get('matched_station') or result.payload.get('location_station')}")
        print(f"     Recurrence count: {result.payload.get('recurrence_count')}")
        print(f"     Type: {result.payload.get('incident_type')}")
        print(f"     Line: {result.payload.get('line_normalized')}")
    
    # Demo 5: Statistics
    print("\n📌 DEMO 5: Collection Statistics")
    print("-" * 40)
    
    stats = search.get_statistics()
    print(f"  Total incidents in database: {stats['total_points']}")
    print(f"  Status: {stats['status']}")
    
    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    demo_queries()
