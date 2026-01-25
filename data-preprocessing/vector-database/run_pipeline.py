"""
Run Full Qdrant Pipeline
========================
Executes all steps in sequence:
1. Enrich data (fill gaps)
2. Train/test split
3. Generate embeddings
4. Ingest into Qdrant
5. Run demo queries

Author: AI Rail Network Brain Team
Date: January 2026
"""

import sys
from pathlib import Path

def main():
    print("=" * 70)
    print("AI RAIL NETWORK BRAIN - FULL QDRANT PIPELINE")
    print("=" * 70)
    
    # Step 1: Enrich data
    print("\n" + "🔷" * 25)
    print("STEP 1: DATA ENRICHMENT")
    print("🔷" * 25)
    
    from step1_enrich_data import main as enrich_main
    enrich_main()
    
    # Step 2: Train/test split
    print("\n" + "🔷" * 25)
    print("STEP 2: TRAIN/TEST SPLIT")
    print("🔷" * 25)
    
    from step2_train_test_split import main as split_main
    split_main()
    
    # Step 3: Generate embeddings
    print("\n" + "🔷" * 25)
    print("STEP 3: GENERATE EMBEDDINGS")
    print("🔷" * 25)
    
    from step3_generate_embeddings import main as embed_main
    embed_main()
    
    # Step 4: Ingest into Qdrant
    print("\n" + "🔷" * 25)
    print("STEP 4: INGEST INTO QDRANT")
    print("🔷" * 25)
    
    from step4_ingest_qdrant import main as ingest_main
    ingest_main()
    
    # Step 5: Demo queries (optional)
    if "--demo" in sys.argv:
        print("\n" + "🔷" * 25)
        print("STEP 5: DEMO QUERIES")
        print("🔷" * 25)
        
        from step5_query_examples import demo_queries
        demo_queries()
    
    print("\n" + "=" * 70)
    print("🎉 FULL PIPELINE COMPLETE!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Use RailIncidentSearch class for queries")
    print("  2. Run step5_query_examples.py for demo")
    print("  3. Integrate with your application")


if __name__ == "__main__":
    main()
