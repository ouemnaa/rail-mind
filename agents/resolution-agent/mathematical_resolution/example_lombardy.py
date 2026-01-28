"""
Realistic example using Lombardy rail network data.
Simulates a conflict scenario with similar historical cases.
"""
import json
import sys
import pathlib
import numpy as np
from datetime import datetime

# Ensure the parent directory is on sys.path so "rail_brain" can be imported when running directly
CURRENT_DIR = pathlib.Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from rail_brain import (
    Conflict,
    Context,
    HistoricalConflict,
    SimilarCase,
    Resolution,
    ActionType,
    ResolutionOrchestrator,
    OrchestratorConfig,
    build_rail_graph,
)


def load_lombardy_data():
    """Load the Lombardy simulation data."""
    with open('lombardy_simulation_data.json', 'r') as f:
        return json.load(f)


def create_current_conflict():
    """
    Realistic conflict scenario based on actual train network.
    Platform/capacity conflict at MILANO CENTRALE - high demand period.
    Three real trains competing for limited platform slots:
    - IC_1539 (intercity): 10 min late, high priority (many passengers)
    - REG_2014 (regional): 6 min late, medium priority  
    - REG_25821 (regional): 4 min late, lower priority
    """
    return Conflict(
        conflict_id="CONF-2026-0125-MILANO-PLATFORM",
        station_ids=["MILANO CENTRALE"],
        train_ids=["IC_1539", "REG_2014", "REG_25821"],
        delay_values={
            "IC_1539": 10.0,      # intercity - most delay/priority
            "REG_2014": 6.0,      # regional - medium
            "REG_25821": 4.0,     # regional - least
        },
        timestamp=datetime(2026, 1, 25, 8, 30).timestamp(),
        severity=0.65,
        conflict_type="platform",  # Platform capacity conflict
        blocking_behavior="hard"
    )


def create_operational_context():
    """
    Context: Saturday morning, peak hour, rain.
    """
    return Context(
        time_of_day=8.5,           # 8:30 AM
        day_of_week=5,             # Saturday
        is_peak_hour=True,         # Morning rush
        weather_condition="rain",  # Reduced visibility, slower trains
        network_load=0.82          # High network utilization
    )


def create_similar_case_1():
    """
    Historical Case 1: Similar platform conflict 2 weeks ago at MILANO CENTRALE
    Resolution: Light hold + modest speed adjustment
    Result: ~8 min delay (vs original 20), success score 0.81
    """
    historical_conflict = Conflict(
        conflict_id="CONF-2026-0111-MILANO",
        station_ids=["MILANO CENTRALE"],
        train_ids=["IC_1234", "REG_9999", "REG_8888"],
        delay_values={
            "IC_1234": 9.0,
            "REG_9999": 5.0,
            "REG_8888": 4.5,
        },
        timestamp=datetime(2026, 1, 11, 8, 15).timestamp(),
        severity=0.60,
        conflict_type="platform",
        blocking_behavior="hard"
    )
    
    resolution = [
        Resolution(
            action_type=ActionType.HOLD,
            target_train_id="REG_8888",
            parameters={"hold_minutes": 2.0}
        ),
        Resolution(
            action_type=ActionType.SPEED_ADJUST,
            target_train_id="IC_1234",
            parameters={"speed_factor": 1.08}
        ),
    ]
    
    historical = HistoricalConflict(
        conflict=historical_conflict,
        resolution_applied=resolution,
        outcome_delay=8.2,                      # Good reduction
        outcome_passenger_impact=2100,          # Reasonable impact
        outcome_propagation=2,                  # Affected 2 trains with actions
        success_score=0.81                      # 81% success
    )
    
    return SimilarCase(
        historical=historical,
        similarity=0.88                         # Very similar
    )


def create_similar_case_2():
    """
    Historical Case 2: Platform conflict at BERGAMO (4 days ago)
    Multiple actions with reroute avoided delays
    Result: ~6 min delay (vs original 12), success 0.77
    """
    historical_conflict = Conflict(
        conflict_id="CONF-2026-0117-BERGAMO",
        station_ids=["BERGAMO"],
        train_ids=["IC_3333", "REG_4444"],
        delay_values={
            "IC_3333": 8.5,
            "REG_4444": 3.5,
        },
        timestamp=datetime(2026, 1, 17, 10, 45).timestamp(),
        severity=0.48,
        conflict_type="platform",
        blocking_behavior="hard"
    )
    
    resolution = [
        Resolution(
            action_type=ActionType.SPEED_ADJUST,
            target_train_id="IC_3333",
            parameters={"speed_factor": 1.10}
        ),
        Resolution(
            action_type=ActionType.REROUTE,
            target_train_id="REG_4444",
            parameters={"time_delta": 1.5}
        )
    ]
    
    historical = HistoricalConflict(
        conflict=historical_conflict,
        resolution_applied=resolution,
        outcome_delay=6.0,                      # Good reduction
        outcome_passenger_impact=980,
        outcome_propagation=2,                  # Both trains got actions
        success_score=0.77
    )
    
    return SimilarCase(
        historical=historical,
        similarity=0.71                         # Moderately similar
    )


def create_train_adjacency():
    """
    Define which trains affect each other based on shared tracks/platforms.
    All three compete for MILANO CENTRALE platform capacity.
    """
    return {
        "IC_1539": ["REG_2014", "REG_25821"],      # Intercity blocks/is blocked by regionals
        "REG_2014": ["IC_1539", "REG_25821"],      # Regionals share platform
        "REG_25821": ["IC_1539", "REG_2014"],      # Mutual blocking
    }


def build_example_graph():
    """
    Build simplified RailGraph from key Lombardy stations/connections.
    """
    stations = [
        {
            "id": "MILANO CENTRALE",
            "name": "MILANO CENTRALE",
            "lat": 45.486347,
            "lon": 9.204528,
            "capacity": 16,
            "type": "terminal"
        },
        {
            "id": "MILANO BOVISA",
            "name": "MILANO BOVISA",
            "lat": 45.502546,
            "lon": 9.15928,
            "capacity": 9,
            "type": "hub"
        },
        {
            "id": "MONZA",
            "name": "MONZA",
            "lat": 45.577789,
            "lon": 9.273253,
            "capacity": 6,
            "type": "through"
        },
    ]
    
    connections = [
        {
            "from": "MILANO CENTRALE",
            "to": "MILANO BOVISA",
            "distance": 3.98,
            "travel_time": 4.0
        },
        {
            "from": "MILANO CENTRALE",
            "to": "MONZA",
            "distance": 15.0,
            "travel_time": 12.0
        },
        {
            "from": "MILANO BOVISA",
            "to": "MONZA",
            "distance": 12.0,
            "travel_time": 10.0
        },
    ]
    
    # Current delays for visualization
    delays = {
        "MILANO CENTRALE": 12.0,    # Platform bottleneck
        "MILANO BOVISA": 5.0,
        "MONZA": 0.0,
    }
    
    graph = build_rail_graph(stations, connections, delays)
    return graph


def run_example():
    """Run the full example and display results."""
    print("=" * 80)
    print("LOMBARDY RAIL NETWORK - CONFLICT RESOLUTION EXAMPLE")
    print("=" * 80)
    print()
    
    # Create scenario
    print("[1] Creating conflict scenario...")
    current_conflict = create_current_conflict()
    context = create_operational_context()
    adjacency = create_train_adjacency()
    graph = build_example_graph()
    
    print(f"  Conflict ID: {current_conflict.conflict_id}")
    print(f"  Type: {current_conflict.conflict_type}")
    print(f"  Severity: {current_conflict.severity:.0%}")
    print(f"  Affected trains: {', '.join(current_conflict.train_ids)}")
    print(f"  Delays: {current_conflict.delay_values}")
    print()
    
    # Retrieve similar cases
    print("[2] Retrieving similar historical cases...")
    similar_cases = [
        create_similar_case_1(),
        create_similar_case_2(),
    ]
    
    for i, case in enumerate(similar_cases, 1):
        print(f"  Case {i}: {case.historical.conflict.conflict_id}")
        print(f"    Similarity: {case.similarity:.0%}")
        print(f"    Success score: {case.historical.success_score:.0%}")
        print(f"    Approach: {[a.action_type.value for a in case.historical.resolution_applied]}")
    print()
    
    # Configure orchestrator
    print("[3] Configuring orchestrator...")
    config = OrchestratorConfig(
        use_learned_selector=True,
        run_all_solvers=True,         # Test ALL solvers and pick best
        fitness_threshold=0.65,
        max_retries=2,
        use_similar_cases=False,      # Disable case-based to test pure solving
        similar_case_weight=0.5,
        # Quantum-enhanced LNS (requires Qiskit: pip install qiskit qiskit-aer qiskit-algorithms qiskit-optimization)
        enable_quantum=True,          # Enable quantum repair in LNS
        quantum_min_trains=3,         # Use quantum when >= 3 trains need repair
    )
    
    orchestrator = ResolutionOrchestrator(config)
    print(f"  Learned solver selection: {config.use_learned_selector}")
    print(f"  Case-based reasoning: {config.use_similar_cases}")
    print(f"  Quantum-enhanced LNS: {config.enable_quantum}")
    print()
    
    # Resolve conflict
    print("[4] Running resolution algorithm...")
    print()
    
    best_plan, explanation = orchestrator.resolve_with_explanation(
        current_conflict,
        context,
        adjacency,
        graph,
        similar_cases
    )
    
    # Display results
    print(explanation)
    print()
    print("=" * 80)
    print("DETAILED PLAN BREAKDOWN")
    print("=" * 80)
    print()
    
    if best_plan:
        print(f"Solver Used: {best_plan.solver_used}")
        print(f"Overall Fitness Score: {best_plan.overall_fitness:.3f} / 1.0")
        print()
        
        print("Actions to Execute:")
        for i, action in enumerate(best_plan.actions, 1):
            print(f"  {i}. {action.action_type.value.upper()}")
            print(f"     Train: {action.target_train_id}")
            print(f"     Parameters: {action.parameters}")
        print()
        
        print("Predicted Impact:")
        print(f"  Total Delay: {best_plan.total_delay:.1f} minutes")
        print(f"  Passenger Impact: {best_plan.passenger_impact:.0f} passenger-minutes")
        print(f"  Propagation Depth: {best_plan.propagation_depth} trains affected")
        print(f"  Recovery Smoothness: {best_plan.recovery_smoothness:.2f} / 1.0")
        print()
        
        print("Fitness Component Breakdown:")
        print(f"  - Delay Minimization: {(1 - best_plan.total_delay / max(1, best_plan.total_delay + 100)):.2%}")
        print(f"  - Passenger Protection: {(1 - best_plan.passenger_impact / max(1, best_plan.passenger_impact + 10000)):.2%}")
        print(f"  - Limited Propagation: {(1 - best_plan.propagation_depth / max(1, len(current_conflict.train_ids))):.2%}")
        print(f"  - Recovery Smoothness: {best_plan.recovery_smoothness:.2%}")
        print()


if __name__ == "__main__":
    try:
        run_example()
    except Exception as e:
        print(f"Error running example: {e}")
        import traceback
        traceback.print_exc()
