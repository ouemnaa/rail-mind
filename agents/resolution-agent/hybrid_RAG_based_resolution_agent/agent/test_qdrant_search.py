"""
INTERACTIVE QDRANT SEARCH TESTER
Tests the Resolution Agent's search capabilities and evaluates Qdrant content quality

Usage:
    python test_qdrant_search.py

This will:
1. Show all collections and their content
2. Test searches with various conflict types
3. Evaluate if the knowledge base needs enrichment
"""

import json
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
import numpy as np


# =========================
# Configuration
# =========================

QDRANT_URL = "https://cf323744-546a-492d-b614-8542cb3ce423.us-east-1-1.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.fI89vclTejMkRnUs-MbAmV-O4PwoQcYE1DO_fN6l7LM"
ALGORITHM_COLLECTION = "railway_algorithms"
HISTORICAL_COLLECTION = "rail_incidents"


class QdrantSearchTester:
    def __init__(self):
        print("🔄 Connecting to Qdrant Cloud...")
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        print("✅ Connected!")
        
        print("🔄 Loading embedding model...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Model loaded!")
    
    def show_all_algorithm_content(self):
        """Display all content in the railway_algorithms collection"""
        print("\n" + "="*70)
        print("  ALL ALGORITHM KNOWLEDGE BASE ENTRIES")
        print("="*70)
        
        results, _ = self.client.scroll(
            collection_name=ALGORITHM_COLLECTION,
            limit=100,
            with_payload=True
        )
        
        # Group by conflict type
        by_type = {}
        for point in results:
            ctype = point.payload.get('conflict_type', 'Unknown')
            if ctype not in by_type:
                by_type[ctype] = []
            by_type[ctype].append(point.payload)
        
        print(f"\n📊 Total entries: {len(results)}")
        print(f"📊 Unique conflict types: {len(by_type)}")
        print("\n" + "-"*70)
        
        for ctype, entries in sorted(by_type.items()):
            print(f"\n🏷️  CONFLICT TYPE: {ctype} ({len(entries)} entries)")
            print("-"*50)
            for i, entry in enumerate(entries, 1):
                print(f"\n  [{i}] Source: {entry.get('source', 'N/A')}")
                print(f"      Description: {entry.get('conflict_description', 'N/A')[:100]}...")
                print(f"      Resolution: {entry.get('resolution_strategy', 'N/A')[:100]}...")
    
    def show_historical_sample(self, limit=10):
        """Display sample historical incidents"""
        print("\n" + "="*70)
        print("  HISTORICAL INCIDENTS SAMPLE")
        print("="*70)
        
        results, _ = self.client.scroll(
            collection_name=HISTORICAL_COLLECTION,
            limit=limit,
            with_payload=True
        )
        
        # Group by incident type
        by_type = {}
        for point in results:
            itype = point.payload.get('incident_type', 'Unknown')
            if itype not in by_type:
                by_type[itype] = 0
            by_type[itype] += 1
        
        print(f"\n📊 Showing first {len(results)} of 122 incidents")
        print(f"📊 Incident types in sample: {dict(by_type)}")
        
        for i, point in enumerate(results[:5], 1):
            p = point.payload
            print(f"\n--- Incident {i} ---")
            print(f"  Type: {p.get('incident_type', 'N/A')}")
            print(f"  Line: {p.get('line', 'N/A')}")
            print(f"  Location: {p.get('location_station', 'N/A')} / {p.get('location_segment', 'N/A')}")
            print(f"  Delay: {p.get('delay_duration_min', 'N/A')} min")
            print(f"  Resolution: {p.get('resolution_types', 'N/A')}")
            print(f"  Affected: {p.get('affected_trains_total', 'N/A')} trains")
    
    def test_search(self, query: str, collection: str, top_k: int = 5):
        """Perform search and display results"""
        print(f"\n🔍 QUERY: \"{query[:80]}...\"" if len(query) > 80 else f"\n🔍 QUERY: \"{query}\"")
        print(f"   Collection: {collection}")
        print("-"*50)
        
        # Generate embedding
        query_vector = self.embedder.encode(query).tolist()
        
        # Search
        results = self.client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=top_k,
            with_payload=True
        )
        
        if not results.points:
            print("❌ No results found!")
            return []
        
        scores = [p.score for p in results.points]
        
        print(f"\n📈 Results: {len(results.points)} | Best: {max(scores):.3f} | Avg: {np.mean(scores):.3f}")
        print()
        
        for i, point in enumerate(results.points, 1):
            score_bar = "█" * int(point.score * 20) + "░" * (20 - int(point.score * 20))
            print(f"  {i}. [{score_bar}] {point.score:.3f}")
            
            if collection == ALGORITHM_COLLECTION:
                print(f"     Type: {point.payload.get('conflict_type', 'N/A')}")
                print(f"     Resolution: {point.payload.get('resolution_strategy', 'N/A')[:80]}...")
            else:
                print(f"     Type: {point.payload.get('incident_type', 'N/A')}")
                print(f"     Line: {point.payload.get('line', 'N/A')}")
                print(f"     Resolution: {point.payload.get('resolution_types', 'N/A')}")
            print()
        
        return results.points
    
    def analyze_coverage(self):
        """Analyze what types of conflicts are covered in the knowledge base"""
        print("\n" + "="*70)
        print("  KNOWLEDGE BASE COVERAGE ANALYSIS")
        print("="*70)
        
        # Get all algorithms
        algos, _ = self.client.scroll(
            collection_name=ALGORITHM_COLLECTION,
            limit=100,
            with_payload=True
        )
        
        algo_types = set()
        for a in algos:
            algo_types.add(a.payload.get('conflict_type', ''))
        
        # Get incident types
        incidents, _ = self.client.scroll(
            collection_name=HISTORICAL_COLLECTION,
            limit=200,
            with_payload=True
        )
        
        incident_types = {}
        for inc in incidents:
            itype = inc.payload.get('incident_type', 'Unknown')
            incident_types[itype] = incident_types.get(itype, 0) + 1
        
        print(f"\n📚 ALGORITHM COLLECTION ({len(algos)} entries)")
        print(f"   Conflict types covered:")
        for t in sorted(algo_types):
            print(f"     • {t}")
        
        print(f"\n📜 HISTORICAL COLLECTION ({len(incidents)} entries)")
        print(f"   Incident types (top 10):")
        for t, count in sorted(incident_types.items(), key=lambda x: -x[1])[:10]:
            print(f"     • {t}: {count} cases")
        
        # Identify gaps
        print("\n⚠️  POTENTIAL GAPS:")
        
        # Common conflict types we might expect
        expected_types = [
            "track_fault", "signal_failure", "power_outage",
            "platform_congestion", "edge_overflow", "headway_violation",
            "weather_disruption", "maintenance_delay", "crew_shortage"
        ]
        
        missing_algos = []
        for t in expected_types:
            found = any(t.lower() in at.lower() for at in algo_types)
            if not found:
                missing_algos.append(t)
        
        if missing_algos:
            print(f"   Algorithm KB missing: {', '.join(missing_algos)}")
        else:
            print("   ✅ Algorithm KB covers expected types")
        
        return algo_types, incident_types


def main():
    tester = QdrantSearchTester()
    
    while True:
        print("\n" + "="*70)
        print("  QDRANT SEARCH TESTER - MAIN MENU")
        print("="*70)
        print("""
  1. Show all algorithm entries (knowledge base content)
  2. Show historical incidents sample
  3. Analyze coverage (what's in the KB)
  4. Test search with custom query
  5. Test search with predefined conflicts
  6. Run full diagnostic
  0. Exit
""")
        choice = input("Select option: ").strip()
        
        if choice == "0":
            print("Goodbye!")
            break
        
        elif choice == "1":
            tester.show_all_algorithm_content()
        
        elif choice == "2":
            tester.show_historical_sample()
        
        elif choice == "3":
            tester.analyze_coverage()
        
        elif choice == "4":
            print("\nEnter your search query:")
            query = input("> ").strip()
            if query:
                print("\nSearch in: 1) Algorithms  2) Historical")
                col_choice = input("> ").strip()
                collection = ALGORITHM_COLLECTION if col_choice == "1" else HISTORICAL_COLLECTION
                tester.test_search(query, collection, top_k=5)
        
        elif choice == "5":
            print("\n📋 Testing predefined conflicts...")
            
            conflicts = [
                ("Headway violation", "headway_violation Train entered segment 50 seconds after previous train, minimum is 180 seconds"),
                ("Platform congestion", "platform_congestion 5 trains simultaneously requesting same platform at Milano Centrale"),
                ("Track fault", "track_fault Vision system detected potential defect on track with 86% confidence"),
                ("Edge overflow", "edge_overflow 4 trains on single track segment, capacity is 2"),
                ("Signal failure", "signal_failure Red signal malfunction blocking traffic at junction"),
                ("Delay cascade", "delay_cascade Initial 15 min delay at Roma propagating through network affecting 20 trains")
            ]
            
            for name, query in conflicts:
                print(f"\n{'='*50}")
                print(f"  TEST: {name}")
                print(f"{'='*50}")
                tester.test_search(query, ALGORITHM_COLLECTION, top_k=3)
                input("\nPress Enter for next test...")
        
        elif choice == "6":
            print("\n🔬 Running full diagnostic...")
            tester.analyze_coverage()
            tester.show_all_algorithm_content()
            tester.show_historical_sample()


if __name__ == "__main__":
    main()
