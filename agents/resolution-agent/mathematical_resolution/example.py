"""
Example usage of Rail Brain.
"""
import numpy as np

from rail_brain import (
    Conflict,
    Context,
    ResolutionOrchestrator,
    OrchestratorConfig,
    build_rail_graph,
)


def main():
    # 1. Define a conflict (pre-given)
    conflict = Conflict(
        conflict_id="CONF-2026-001",
        station_ids=["STN_A", "STN_B", "STN_C"],
        train_ids=["TR101", "TR102", "TR103", "TR104"],
        delay_values={
            "TR101": 15.0,  # 15 min delay
            "TR102": 8.0,
            "TR103": 3.0,
            "TR104": 0.0,
        },
        timestamp=1706025600.0,
        severity=0.7,
        conflict_type="platform",
        embedding=None  # Will compute from GNN
    )
    
    # 2. Define operational context
    context = Context(
        time_of_day=8.5,  # 8:30 AM
        day_of_week=1,    # Tuesday
        is_peak_hour=True,
        weather_condition="rain",
        network_load=0.85
    )
    
    # 3. Define train adjacency (which trains affect each other)
    adjacency = {
        "TR101": ["TR102", "TR103"],
        "TR102": ["TR101", "TR104"],
        "TR103": ["TR101"],
        "TR104": ["TR102"],
    }
    
    # 4. Optional: Define rail network for GNN embedding
    stations = [
        {"id": "STN_A", "capacity": 4, "type": "terminal"},
        {"id": "STN_B", "capacity": 6, "type": "junction"},
        {"id": "STN_C", "capacity": 3, "type": "through"},
        {"id": "STN_D", "capacity": 5, "type": "junction"},
    ]
    
    connections = [
        {"from": "STN_A", "to": "STN_B", "distance": 10},
        {"from": "STN_B", "to": "STN_C", "distance": 15},
        {"from": "STN_B", "to": "STN_D", "distance": 8},
        {"from": "STN_C", "to": "STN_D", "distance": 12},
    ]
    
    # Build graph
    graph = build_rail_graph(stations, connections, conflict.delay_values)
    
    # 5. Create orchestrator and resolve
    config = OrchestratorConfig(
        use_learned_selector=True,
        run_all_solvers=False,
        fitness_threshold=0.6
    )
    
    orchestrator = ResolutionOrchestrator(config)
    
    # Resolve conflict
    plans = orchestrator.resolve(conflict, context, adjacency, graph)
    
    print("=" * 60)
    print("RAIL BRAIN - Conflict Resolution")
    print("=" * 60)
    
    for i, plan in enumerate(plans, 1):
        print(f"\n--- Plan {i} (Solver: {plan.solver_used}) ---")
        print(f"Overall Fitness: {plan.overall_fitness:.3f}")
        print(f"Total Delay: {plan.total_delay:.1f} min")
        print(f"Passenger Impact: {plan.passenger_impact:.0f}")
        print(f"Propagation Depth: {plan.propagation_depth}")
        print(f"Recovery Smoothness: {plan.recovery_smoothness:.3f}")
        print("\nActions:")
        for action in plan.actions:
            print(f"  - {action.action_type.value}: Train {action.target_train_id}")
            print(f"    Params: {action.parameters}")
    
    # Get explanation
    best_plan, explanation = orchestrator.resolve_with_explanation(
        conflict, context, adjacency, graph
    )
    
    print("\n")
    print(explanation)


if __name__ == "__main__":
    main()
