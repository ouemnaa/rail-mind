"""
Example: Resolve conflicts from nour.json using the rail_brain system.
Demonstrates loading real conflicts and running solvers on them.
"""
import json
import sys
import pathlib
import numpy as np
from datetime import datetime

# Ensure imports work when running directly
CURRENT_DIR = pathlib.Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from mathematical_resolution import (
    Context,
    HistoricalConflict,
    SimilarCase,
    Resolution,
    ActionType,
    ResolutionOrchestrator,
    OrchestratorConfig,
    build_rail_graph,
)
from mathematical_resolution.conflict_adapter import (
    load_conflicts_from_json,
    enrich_conflicts_with_train_data,
    summarize_all_conflicts,
    summarize_conflict,
)


def load_lombardy_context():
    """Load the Lombardy simulation data for train context."""
    # Data is in creating-context folder
    PROJECT_ROOT = PARENT_DIR.parent.parent  # Go up to rail-mind root
    json_path = PROJECT_ROOT / 'creating-context' / 'lombardy_simulation_data.json'
    print(f"   DEBUG: Loading Lombardy data from {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read(100)
        print(f"   DEBUG: File starts with: {content!r}")
        f.seek(0)
        data = json.load(f)
        print(f"   DEBUG: Type of loaded data: {type(data)}")
        return data


def create_operational_context_from_conflict(conflict):
    """
    Create operational context based on conflict metadata.
    """
    # Try to determine weather from conflict if available
    weather = "clear"
    if conflict.affected_rails:
        # Check if any rail has weather info in metadata
        pass
    
    # Determine time from timestamp
    dt = datetime.fromtimestamp(conflict.timestamp)
    hour = dt.hour + dt.minute / 60.0
    
    # Peak hours: 7-9 AM, 5-7 PM
    is_peak = (7 <= dt.hour <= 9) or (17 <= dt.hour <= 19)
    
    return Context(
        time_of_day=hour,
        day_of_week=dt.weekday(),
        is_peak_hour=is_peak,
        weather_condition=weather,
        network_load=0.7 if is_peak else 0.5
    )


def create_historical_cases():
    """
    Create sample historical cases for case-based reasoning.
    These represent past successful resolutions.
    """
    from mathematical_resolution import Conflict
    
    # Case 1: Headway violation resolved by holding trailing train
    case1_conflict = Conflict(
        conflict_id="HIST-HEADWAY-001",
        station_ids=["MILANO ROGOREDO", "PAVIA"],
        train_ids=["REG_10001", "REG_10002"],
        delay_values={"REG_10001": 0.0, "REG_10002": 2.5},
        timestamp=datetime(2025, 12, 15, 9, 30).timestamp(),
        severity=0.8,
        conflict_type="headway",
    )
    case1 = HistoricalConflict(
        conflict=case1_conflict,
        resolution_applied=[
            Resolution(
                action_type=ActionType.HOLD,
                target_train_id="REG_10002",
                parameters={"hold_minutes": 3.0}
            )
        ],
        outcome_delay=3.0,
        outcome_passenger_impact=0.15,
        outcome_propagation=1,
        success_score=0.85,
    )
    
    # Case 2: Delay propagation resolved by speed adjustment
    case2_conflict = Conflict(
        conflict_id="HIST-DELAY-001",
        station_ids=["BRESCIA", "MILANO PORTA GARIBALDI"],
        train_ids=["FR_8001"],
        delay_values={"FR_8001": 5.0},
        timestamp=datetime(2025, 12, 20, 14, 0).timestamp(),
        severity=0.7,
        conflict_type="delay",
    )
    case2 = HistoricalConflict(
        conflict=case2_conflict,
        resolution_applied=[
            Resolution(
                action_type=ActionType.SPEED_ADJUST,
                target_train_id="FR_8001",
                parameters={"speed_factor": 1.08}  # 8% faster
            )
        ],
        outcome_delay=3.5,
        outcome_passenger_impact=0.1,
        outcome_propagation=0,
        success_score=0.88,
    )
    
    # Case 3: Weather stress resolved by speed reduction
    case3_conflict = Conflict(
        conflict_id="HIST-WEATHER-001",
        station_ids=["MILANO ROGOREDO", "PAVIA"],
        train_ids=["REG_5001"],
        delay_values={"REG_5001": 3.0},
        timestamp=datetime(2025, 11, 5, 16, 0).timestamp(),
        severity=0.65,
        conflict_type="capacity",
    )
    case3 = HistoricalConflict(
        conflict=case3_conflict,
        resolution_applied=[
            Resolution(
                action_type=ActionType.SPEED_ADJUST,
                target_train_id="REG_5001",
                parameters={"speed_factor": 0.85}  # 15% slower for safety
            )
        ],
        outcome_delay=4.5,  # Some extra delay but safe
        outcome_passenger_impact=0.2,
        outcome_propagation=0,
        success_score=0.82,
    )
    
    return [case1, case2, case3]


def find_similar_cases(conflict, historical_cases, top_k=2):
    """
    Find similar historical cases based on conflict type and severity.
    Simple matching - in production would use embedding similarity.
    """
    similar = []
    for case in historical_cases:
        # Match by conflict type
        if case.conflict.conflict_type == conflict.conflict_type:
            similarity = 0.8
        elif abs(case.conflict.severity - conflict.severity) < 0.2:
            similarity = 0.6
        else:
            similarity = 0.4
        
        similar.append(SimilarCase(
            historical=case,
            similarity=similarity
        ))
    
    # Sort by similarity descending
    similar.sort(key=lambda x: x.similarity, reverse=True)
    return similar[:top_k]


def resolve_single_conflict(conflict, context, similar_cases, lombardy_data, config):
    """
    Resolve a single conflict using the orchestrator.
    """
    print(f"\n{'='*60}")
    print(f"RESOLVING: {summarize_conflict(conflict)}")
    print(f"{'='*60}")
    
    # Build delays dict for stations (use conflict delays mapped to stations)
    # For simplicity, assign average delay to involved stations
    avg_delay = sum(conflict.delay_values.values()) / max(1, len(conflict.delay_values))
    station_delays = {sid: avg_delay for sid in conflict.station_ids}
    
    # Build rail graph from Lombardy data
    rail_graph = build_rail_graph(
        lombardy_data.get("stations", []),
        lombardy_data.get("rails", []),
        station_delays
    )
    
    # Build adjacency from conflict train relationships
    # For simplicity: all trains in a conflict are adjacent (connected)
    adjacency = {}
    for train_id in conflict.train_ids:
        adjacency[train_id] = [t for t in conflict.train_ids if t != train_id]
    
    # Create orchestrator
    orchestrator = ResolutionOrchestrator(config=config)
    
    # Resolve - returns list of plans
    plans = orchestrator.resolve(
        conflict=conflict,
        context=context,
        adjacency=adjacency,
        graph=rail_graph,
        similar_cases=similar_cases
    )
    
    # Return best plan (first in ranked list)
    return plans[0] if plans else None


def print_resolution_plan(plan, conflict):
    """Pretty-print a resolution plan with human-readable explanations."""
    # Import the validator for explanation formatting
    from mathematical_resolution.math import ActionValidator
    
    print(f"\n[PLAN] RESOLUTION PLAN (Solver: {plan.solver_used})")
    print(f"   Overall Fitness: {plan.overall_fitness:.4f}")
    
    original_delay = sum(conflict.delay_values.values())
    reduction_pct = (1 - plan.total_delay / original_delay) * 100 if original_delay > 0 else 0
    print(f"   Total Delay: {plan.total_delay:.2f} min (was {original_delay:.2f} min) → {reduction_pct:+.1f}%")
    print(f"   Passenger Impact: {plan.passenger_impact:.0f}")
    print(f"   Propagation Depth: {plan.propagation_depth}")
    print(f"   Recovery Smoothness: {plan.recovery_smoothness:.3f}")
    
    print(f"\n   Actions for {conflict.conflict_type.upper()} conflict:")
    for i, action in enumerate(plan.actions, 1):
        explanation = ActionValidator.format_action_explanation(action, conflict)
        print(f"   {i}. {explanation}")


def main():
    print("=" * 70)
    print("  RAIL BRAIN - Conflict Resolution from nour.json")
    print("=" * 70)
    
    # Load conflict data - use detected conflicts from backend or generate sample
    PROJECT_ROOT = PARENT_DIR.parent.parent
    #C:\rail-mind\agents\resolution-agent\nour.json
    conflicts_path = PROJECT_ROOT / 'agents' / 'resolution-agent' / 'nour.json' 
    if not conflicts_path.exists():
        # Fallback: try a nour.json if it exists
        alt_path = PARENT_DIR / 'nour.json'
        if alt_path.exists():
            conflicts_path = alt_path
        else:
            print(f"\n⚠️ No conflict file found. Please either:")
            print(f"   1. Run the simulation: python backend/integration/unified_api.py")
            print(f"   2. Call the /api/simulation/tick endpoint several times")
            print(f"   3. Create a sample nour.json file in: {PARENT_DIR}")
            return
    
    print(f"\n[DATA] Loading conflicts from: {conflicts_path}")
    
    conflicts = load_conflicts_from_json(str(conflicts_path))
    print(summarize_all_conflicts(conflicts))
    
    # Load Lombardy context for train enrichment
    print("\n[INFO] Loading Lombardy network data...")
    lombardy_data = load_lombardy_context()
    print(f"   DEBUG: lombardy_data type: {type(lombardy_data)}")
    if isinstance(lombardy_data, dict):
        print(f"   DEBUG: lombardy_data keys: {list(lombardy_data.keys())}")
    else:
        print(f"   DEBUG: lombardy_data is NOT a dict, it is: {lombardy_data[:1] if len(lombardy_data) > 0 else 'empty'}")
        
    train_data = lombardy_data.get("trains", []) if isinstance(lombardy_data, dict) else []
    print(f"   Loaded {len(train_data)} trains")
    
    # Enrich conflicts with train priority info
    conflicts = enrich_conflicts_with_train_data(conflicts, train_data)
    
    # Load historical cases for case-based reasoning
    historical_cases = create_historical_cases()
    print(f"\n[INFO] Loaded {len(historical_cases)} historical cases for CBR")
    
    # Configure orchestrator
    config = OrchestratorConfig(
        run_all_solvers=True,     # Run all solvers to find best
        enable_quantum=True,      # Enable quantum enhancement
        quantum_min_trains=2,     # Use quantum when >= 2 trains
    )
    
    print(f"\n⚙️  Config: run_all_solvers={config.run_all_solvers}, "
          f"quantum={'enabled' if config.enable_quantum else 'disabled'}")
    
    # Resolve each conflict
    all_plans = []
    for i, conflict in enumerate(conflicts, 1):
        print(f"\n{'#'*70}")
        print(f"# CONFLICT {i}/{len(conflicts)}")
        print(f"{'#'*70}")
        
        # Create context for this conflict
        context = create_operational_context_from_conflict(conflict)
        
        # Find similar historical cases
        similar = find_similar_cases(conflict, historical_cases)
        
        # Resolve
        plan = resolve_single_conflict(
            conflict, context, similar, lombardy_data, config
        )
        
        if plan is None:
            print(f"⚠️ No resolution found for conflict {conflict.conflict_id}")
            continue
        
        # Print result
        print_resolution_plan(plan, conflict)
        all_plans.append((conflict, plan))
    
    # Summary
    print("\n" + "=" * 70)
    print("  RESOLUTION SUMMARY")
    print("=" * 70)
    
    if not all_plans:
        print("\n⚠️ No conflicts were successfully resolved!")
        return
    
    total_original_delay = sum(
        sum(c.delay_values.values()) for c in conflicts
    )
    total_resolved_delay = sum(p.total_delay for _, p in all_plans)
    
    print(f"\n📈 Total original delay: {total_original_delay:.2f} min")
    print(f"📉 Total resolved delay: {total_resolved_delay:.2f} min")
    
    if total_original_delay > 0:
        reduction = (1 - total_resolved_delay/total_original_delay) * 100
        print(f"✅ Delay reduction: {reduction:.1f}%")
    
    print("\n📋 Per-conflict results:")
    for i, (conflict, plan) in enumerate(all_plans, 1):
        original = sum(conflict.delay_values.values())
        resolved = plan.total_delay
        reduction = (1 - resolved/original) * 100 if original > 0 else 0
        print(f"   {i}. {conflict.conflict_type}: {original:.1f}min → {resolved:.1f}min ({reduction:+.1f}%)")
    
    print("\n[SUCCESS] Resolution complete!")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
