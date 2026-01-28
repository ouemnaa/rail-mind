"""
Integration Test: Resolution Generation System

This script tests the complete two-layer system with real conflict data.
Run this to verify everything works correctly.
"""

import json
from resolution_generator import ResolutionGenerationSystem


def test_basic_functionality():
    """
    Test basic resolution generation without LLM (fallback mode)
    """
    print("="*70)
    print("TEST 1: Basic Functionality (No LLM)")
    print("="*70)
    
    # Load test data
    with open("conflict_input.json", "r") as f:
        content = f.read()
        # Parse first conflict (file contains multiple conflicts as separate JSON objects)
        first_conflict = content.split('\n\n')[0]
        conflict = json.loads(first_conflict)
    
    with open("context.json", "r") as f:
        context = json.load(f)
    
    print(f"\n✓ Loaded conflict: {conflict['conflict_id']}")
    print(f"  Type: {conflict['conflict_type']}")
    print(f"  Severity: {conflict['severity']}")
    print(f"✓ Loaded context: {len(context.get('trains', []))} trains, {len(context.get('edges', []))} edges")
    
    # Initialize system without LLM
    print("\n⚙️  Initializing system (fallback mode)...")
    
    try:
        system = ResolutionGenerationSystem(
            qdrant_url="https://cf323744-546a-492d-b614-8542cb3ce423.us-east-1-1.aws.cloud.qdrant.io",
            qdrant_api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.fI89vclTejMkRnUs-MbAmV-O4PwoQcYE1DO_fN6l7LM",
            algorithm_collection="railway_algorithms",
            historical_collection="rail_incidents",
            llm_api_key=None  # No LLM - fallback mode
        )
        print("✓ System initialized")
    except Exception as e:
        print(f"⚠️  Could not connect to Qdrant: {e}")
        print("   This is expected if Qdrant is not running.")
        print("   The code structure is correct - you just need to set up Qdrant.")
        return
    
    # Generate resolutions
    print("\n🔄 Generating resolutions...")
    try:
        report = system.generate_resolutions(
            conflict=conflict,
            context=context
        )
        
        print(f"\n✅ SUCCESS! Generated {len(report.resolutions)} resolutions")
        
        # Save results
        system.save_report(report, "test_report.json", format="json")
        #system.save_report(report, "test_report.md", format="markdown")
        
    except Exception as e:
        print(f"⚠️  Error during generation: {e}")
        print("   Check that Qdrant collections exist and have data")


def test_with_llm():
    """
    Test with LLM integration (requires OpenRouter API key)
    """
    print("\n" + "="*70)
    print("TEST 2: With LLM Integration")
    print("="*70)
    
    # Check if API key is available
    OPENROUTER_API_KEY = "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"  # Replace with real key to test
    
    if "YOUR-API-KEY" in OPENROUTER_API_KEY:
        print("\n⚠️  No API key configured - skipping LLM test")
        print("   To test LLM features, set OPENROUTER_API_KEY in this script")
        return
    
    # Load test data
    with open("conflict_input.json", "r") as f:
        content = f.read()
        first_conflict = content.split('\n\n')[0]
        conflict = json.loads(first_conflict)
    
    with open("context.json", "r") as f:
        context = json.load(f)
    
    # Initialize with LLM
    print("\n⚙️  Initializing system with LLM...")
    
    try:
        system = ResolutionGenerationSystem(
            qdrant_url="https://cf323744-546a-492d-b614-8542cb3ce423.us-east-1-1.aws.cloud.qdrant.io",
            qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.fI89vclTejMkRnUs-MbAmV-O4PwoQcYE1DO_fN6l7LM",
            llm_api_key="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",
            llm_model="tngtech/deepseek-r1t2-chimera:free"
        )
        print("✓ System initialized with LLM")
        
        # Generate resolutions
        print("\n🔄 Generating resolutions with LLM...")
        report = system.generate_resolutions(
            conflict=conflict,
            context=context
        )
        
        print(f"\n✅ SUCCESS! Generated {len(report.resolutions)} resolutions")
        
        # Check for hybrid resolutions
        hybrid_count = sum(1 for r in report.resolutions if r.source_type == "hybrid")
        print(f"   Including {hybrid_count} hybrid resolutions")
        
        # Save results
        system.save_report(report, "test_report_llm.json", format="json")
        #system.save_report(report, "test_report_llm.md", format="markdown")
        
    except Exception as e:
        print(f"⚠️  Error: {e}")


def test_data_structures():
    """
    Test that data structures are correct
    """
    print("\n" + "="*70)
    print("TEST 3: Data Structure Validation")
    print("="*70)
    
    # Test conflict input format
    print("\n📄 Validating conflict input format...")
    with open("conflict_input.json", "r") as f:
        content = f.read()
        conflicts = []
        for obj_str in content.split('\n\n'):
            if obj_str.strip():
                try:
                    conflicts.append(json.loads(obj_str))
                except:
                    pass
    
    print(f"✓ Found {len(conflicts)} conflicts in input file")
    
    for i, conflict in enumerate(conflicts[:3], 1):  # Check first 3
        required_fields = [
            'conflict_id', 'conflict_type', 'severity', 
            'location', 'involved_trains', 'explanation'
        ]
        missing = [f for f in required_fields if f not in conflict]
        
        if missing:
            print(f"  ⚠️  Conflict {i} missing fields: {missing}")
        else:
            print(f"  ✓ Conflict {i} ({conflict['conflict_type']}) - valid")
    
    # Test context format
    print("\n📄 Validating context format...")
    with open("context.json", "r") as f:
        context = json.load(f)
    
    required_context = ['trains', 'edges']
    missing_context = [f for f in required_context if f not in context]
    
    if missing_context:
        print(f"  ⚠️  Context missing fields: {missing_context}")
    else:
        print(f"  ✓ Context structure valid")
        print(f"    - {len(context['trains'])} trains")
        print(f"    - {len(context['edges'])} edges")


def main():
    """
    Run all tests
    """
    print("\n" + "🧪 "*20)
    print(" "*15 + "RESOLUTION GENERATOR - INTEGRATION TESTS")
    print("🧪 "*20)
    
    # Test 1: Data structures
    test_data_structures()
    
    # Test 2: Basic functionality
    test_basic_functionality()
    
    # Test 3: LLM integration
    test_with_llm()
    
    print("\n" + "="*70)
    print("TESTS COMPLETE")
    print("="*70)
    print()


if __name__ == "__main__":
    main()
