"""Quantum LNS smoke test to ensure non-empty repairs when quantum is enabled."""

import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__":
    rail_brain_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(rail_brain_root))

import pytest

from rail_brain.data_structures import Conflict, Context
from rail_brain.math import (
    DelayParams,
    DelayPropagation,
    FitnessEvaluator,
    LargeNeighborhoodSearch,
)


@pytest.mark.skip(reason="Requires Qiskit stack; skip if not installed")
def test_quantum_lns_produces_actions():
    try:
        import rail_brain.quantum_solver  # noqa: F401  (verifies import works)
    except ImportError:
        pytest.skip("Quantum dependencies not installed")

    conflict = Conflict(
        conflict_id="TEST-QUANTUM",
        station_ids=["S1"],
        train_ids=["T1", "T2", "T3", "T4"],
        delay_values={"T1": 8.0, "T2": 6.0, "T3": 4.0, "T4": 3.0},
        timestamp=0.0,
        severity=0.5,
        conflict_type="platform",
        blocking_behavior="hard",
    )

    context = Context(
        time_of_day=8.0,
        is_peak_hour=True,
        weather_condition="clear",
        network_load=0.7,
        day_of_week="Monday",
    )

    adjacency = {
        "T1": ["T2", "T3"],
        "T2": ["T1", "T4"],
        "T3": ["T1", "T4"],
        "T4": ["T2", "T3"],
    }

    evaluator = FitnessEvaluator(DelayPropagation(DelayParams()))
    lns = LargeNeighborhoodSearch(
        evaluator,
        max_iterations=5,
        destroy_fraction=0.5,
        enable_quantum=True,
        quantum_min_trains=2,
    )

    plan = lns.solve(conflict, context, adjacency)

    assert plan.actions, "Quantum repair produced no actions"
    assert plan.overall_fitness >= 0.0
    assert plan.solver_used == "lns"


if __name__ == "__main__":
    try:
        import rail_brain.quantum_solver  # noqa: F401
    except ImportError:
        print("Quantum dependencies not installed; skipping run")
        raise SystemExit(0)

    conflict = Conflict(
        conflict_id="TEST-QUANTUM",
        station_ids=["S1"],
        train_ids=["T1", "T2", "T3", "T4"],
        delay_values={"T1": 8.0, "T2": 6.0, "T3": 4.0, "T4": 3.0},
        timestamp=0.0,
        severity=0.5,
        conflict_type="platform",
        blocking_behavior="hard",
    )

    context = Context(
        time_of_day=8.0,
        is_peak_hour=True,
        weather_condition="clear",
        network_load=0.7,
        day_of_week="Monday",
    )

    adjacency = {
        "T1": ["T2", "T3"],
        "T2": ["T1", "T4"],
        "T3": ["T1", "T4"],
        "T4": ["T2", "T3"],
    }

    evaluator = FitnessEvaluator(DelayPropagation(DelayParams()))
    lns = LargeNeighborhoodSearch(
        evaluator,
        max_iterations=5,
        destroy_fraction=0.5,
        enable_quantum=True,
        quantum_min_trains=2,
    )

    plan = lns.solve(conflict, context, adjacency)

    print("Solver:", plan.solver_used)
    print("Actions:")
    for a in plan.actions:
        print(" -", a.action_type.value, a.target_train_id, a.parameters)
    print("Fitness:", f"{plan.overall_fitness:.3f}")
    print("Total delay:", f"{plan.total_delay:.1f} min")
