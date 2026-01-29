"""
Test Script: Context Updater

Tests the action-to-parameter translation system
"""

import json
from context_updater import ResolutionContextUpdater


def test_context_updater():
    """Test the context updater with sample data"""
    
    print("\n" + "="*70)
    print(" "*20 + "CONTEXT UPDATER TEST")
    print("="*70 + "\n")
    
    # Configuration
    OPENROUTER_API_KEY = "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"  # Replace with your key
    
    # Check if API key is set
    if "YOUR-API-KEY" in OPENROUTER_API_KEY:
        print("⚠️  No API key configured!")
        print("   Please set OPENROUTER_API_KEY in this script")
        print("   The system will use fallback rule-based interpretation\n")
    
    # Initialize updater
    print("⚙️  Initializing Context Updater...")
    updater = ResolutionContextUpdater(
        llm_api_key=OPENROUTER_API_KEY,
        llm_model="tngtech/deepseek-r1t2-chimera:free"
    )
    print("✓ System initialized\n")
    
    # Test 1: Load and display resolution
    print("="*70)
    print("TEST 1: Resolution Loading")
    print("="*70 + "\n")
    
    with open("sample_resolution.json", "r") as f:
        resolution = json.load(f)
    
    print(f"✓ Resolution: {resolution['resolution_id']}")
    print(f"  Rank: {resolution['rank']}")
    print(f"  Overall Score: {resolution['overall_score']}")
    print(f"\n  Actions:")
    for i, action in enumerate(resolution['bullet_resolution_actions']['actions'], 1):
        print(f"    {i}. {action}")
    
    # Test 2: Load context
    print("\n" + "="*70)
    print("TEST 2: Context Loading")
    print("="*70 + "\n")
    
    with open("lombardy_simulation_data.json", "r") as f:
        context = json.load(f)
    
    print(f"✓ Context loaded:")
    print(f"  - Trains: {len(context['trains'])}")
    print(f"  - Rails: {len(context['rails'])}")
    print(f"  - Stations: {len(context['stations'])}")
    
    # Show sample train
    sample_train = context['trains'][0]
    print(f"\n  Sample Train: {sample_train['train_id']}")
    print(f"    Type: {sample_train['train_type']}")
    print(f"    Route stops: {len(sample_train['route'])}")
    
    # Show sample rail
    sample_rail = context['rails'][0]
    print(f"\n  Sample Rail: {sample_rail['source']} → {sample_rail['target']}")
    print(f"    Distance: {sample_rail['distance_km']} km")
    print(f"    Max Speed: {sample_rail['max_speed_kmh']} km/h")
    print(f"    Min Headway: {sample_rail['min_headway_sec']}s")
    
    # Test 3: Apply resolution
    print("\n" + "="*70)
    print("TEST 3: Applying Resolution to Context")
    print("="*70 + "\n")
    
    try:
        updated_context = updater.apply_resolution(
            resolution_file="sample_resolution.json",
            context_file="lombardy_simulation_data.json",
            output_file="test_updated_context.json"
        )
        
        print("\n✅ SUCCESS!")
        
        # Test 4: Verify structure unchanged
        print("\n" + "="*70)
        print("TEST 4: Structure Verification")
        print("="*70 + "\n")
        
        # Check keys
        original_keys = set(context.keys())
        updated_keys = set(updated_context.keys())
        print(f"✓ Top-level keys preserved: {original_keys == updated_keys}")
        
        # Check counts
        print(f"✓ Train count: {len(context['trains'])} → {len(updated_context['trains'])} (unchanged: {len(context['trains']) == len(updated_context['trains'])})")
        print(f"✓ Rail count: {len(context['rails'])} → {len(updated_context['rails'])} (unchanged: {len(context['rails']) == len(updated_context['rails'])})")
        
        # Show what changed
        print("\n" + "="*70)
        print("TEST 5: Changes Summary")
        print("="*70 + "\n")
        
        changes_found = False
        
        # Check for rail changes
        for orig_rail, upd_rail in zip(context['rails'][:100], updated_context['rails'][:100]):  # Check first 100
            changes = []
            for key in orig_rail.keys():
                if orig_rail[key] != upd_rail[key]:
                    changes.append(f"{key}: {orig_rail[key]} → {upd_rail[key]}")
            
            if changes:
                changes_found = True
                print(f"  Rail {orig_rail['source']} → {orig_rail['target']}:")
                for change in changes:
                    print(f"    • {change}")
        
        if not changes_found:
            print("  No parameter changes detected in first 100 rails")
            print("  (This may mean LLM API key is needed, or changes are in specific rails)")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70 + "\n")


def test_structure_preservation():
    """Verify structure is strictly preserved"""
    
    print("\n" + "="*70)
    print("STRUCTURE PRESERVATION TEST")
    print("="*70 + "\n")
    
    with open("lombardy_simulation_data.json", "r") as f:
        original = json.load(f)
    
    try:
        with open("test_updated_context.json", "r") as f:
            updated = json.load(f)
        
        # Deep structure check
        def check_structure(orig, upd, path=""):
            if type(orig) != type(upd):
                print(f"❌ Type mismatch at {path}: {type(orig).__name__} vs {type(upd).__name__}")
                return False
            
            if isinstance(orig, dict):
                if set(orig.keys()) != set(upd.keys()):
                    print(f"❌ Keys differ at {path}")
                    print(f"   Missing: {set(orig.keys()) - set(upd.keys())}")
                    print(f"   Extra: {set(upd.keys()) - set(orig.keys())}")
                    return False
                
                for key in orig.keys():
                    if not check_structure(orig[key], upd[key], f"{path}.{key}"):
                        return False
            
            elif isinstance(orig, list):
                if len(orig) != len(upd):
                    print(f"❌ List length differs at {path}: {len(orig)} vs {len(upd)}")
                    return False
                
                for i, (o, u) in enumerate(zip(orig, upd)):
                    if not check_structure(o, u, f"{path}[{i}]"):
                        return False
            
            return True
        
        if check_structure(original, updated):
            print("✅ STRUCTURE PERFECTLY PRESERVED!")
            print("   All fields, keys, and list lengths match exactly")
        else:
            print("❌ Structure was modified!")
    
    except FileNotFoundError:
        print("⚠️  Updated context file not found - run test_context_updater() first")


if __name__ == "__main__":
    # Run tests
    test_context_updater()
    test_structure_preservation()
