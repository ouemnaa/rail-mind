"""
Detection Engine Runner
=======================
Main entry point for running the conflict detection system.

Usage:
    python -m detection.run_detection
    python -m detection.run_detection --scenario rush_hour --ticks 200
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

from models import TrainStatus
from state_tracker import StateTracker
from engine import DetectionEngine
from simulator import MockSimulator, SimulationConfig, ScenarioType


def load_lombardy_data(data_path: Path) -> dict:
    """Load the Lombardy simulation data."""
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def setup_state_tracker(data: dict) -> StateTracker:
    """Initialize state tracker with Lombardy data."""
    tracker = StateTracker()
    
    # Load network structure (stations and rails)
    tracker.load_from_json(data)
    
    # Note: StateTracker.load_from_json already loads trains
    # Just ensure they are properly initialized for simulation
    for train_id, train in tracker.state.trains.items():
        train.status = TrainStatus.STOPPED
        train.current_position_type = "unknown"
        train.delay_seconds = 0
        train.current_speed_kmh = 0.0
    
    print(f"[Setup] Loaded {len(tracker.state.stations)} stations")
    print(f"[Setup] Loaded {len(tracker.state.edges)} edges")
    print(f"[Setup] Loaded {len(tracker.state.trains)} trains")
    
    return tracker


def run_simulation(
    data_path: Path,
    scenario: str = "normal",
    ticks: int = 100,
    output_path: Path = None,
    seed: int = None,
    verbose: bool = True,
    realtime: bool = False
) -> dict:
    """
    Run the full detection simulation.
    
    Args:
        data_path: Path to lombardy_simulation_data.json
        scenario: Simulation scenario (normal, rush_hour, disruption, stress_test)
        ticks: Number of simulation ticks
        output_path: Optional path for conflict output JSON
        seed: Random seed for reproducibility
        verbose: Print progress updates
    
    Returns:
        Summary dict with statistics and detected conflicts
    """
    # Load data
    if verbose:
        print(f"\n{'='*60}")
        print("RailMind Conflict Detection Engine")
        print(f"{'='*60}\n")
        print(f"[Init] Loading data from {data_path}")
    
    data = load_lombardy_data(data_path)
    
    # Setup components
    tracker = setup_state_tracker(data)
    
    # Configure output
    output_file = output_path or Path("output/conflicts.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create emitter with file output
    from engine import ConflictEmitter
    emitter = ConflictEmitter(enable_console=verbose, json_file=str(output_file))
    
    engine = DetectionEngine(
        state_tracker=tracker,
        emitter=emitter
    )
    
    # Configure simulator
    scenario_type = ScenarioType(scenario) if scenario in [s.value for s in ScenarioType] else ScenarioType.NORMAL
    
    config = SimulationConfig(
        tick_interval_seconds=10,
        max_ticks=ticks,
        scenario=scenario_type,
        random_seed=seed
    )
    
    simulator = MockSimulator(tracker, config)
    
    # Initialize some trains
    initial_train_count = {
        ScenarioType.NORMAL: 15,
        ScenarioType.RUSH_HOUR: 30,
        ScenarioType.DISRUPTION: 20,
        ScenarioType.STRESS_TEST: 40
    }.get(scenario_type, 15)
    
    simulator.initialize_trains(initial_train_count)
    
    if verbose:
        print(f"\n[Sim] Starting {scenario} scenario")
        print(f"[Sim] Running for {ticks} ticks (tick interval: {config.tick_interval_seconds}s)")
        print(f"[Sim] Initial trains: {initial_train_count}")
        print(f"\n{'-'*60}")
    
    if ticks < 10:
        print(f"[Warning] Simulation duration ({ticks} ticks) may be too short to detect operational conflicts.")

    # Run simulation
    all_changes = []

    if realtime:
        # Real-time mode: run simulator and sleep between ticks. The simulator
        # provides `run_realtime` which sleeps for a real interval between ticks.
        def _realtime_callback(changes):
            conflicts = engine.tick(simulator.current_time)
            all_changes.append({
                **changes, 
                "conflicts_detected": len(conflicts),
                "state_snapshot": engine.get_state_snapshot()
            })
            if verbose:
                stats = engine.get_statistics()
                conflict_stats = stats.get('conflict_stats', {})
                print(f"[Tick {changes['tick']:3d}] Active: {len(simulator.active_trains):2d} | "
                      f"Arrivals: {len(changes['arrivals']):2d} | "
                      f"Conflicts: {conflict_stats.get('total', 0):3d}")

        simulator.run_realtime(tick_real_seconds=30, callback=_realtime_callback)
    else:
        for changes in simulator.run():
            # Run detection using simulator's current time
            conflicts = engine.tick(simulator.current_time)

            all_changes.append({
                **changes,
                "conflicts_detected": len(conflicts),
                "state_snapshot": engine.get_state_snapshot()
            })

            if verbose:
                stats = engine.get_statistics()
                conflict_stats = stats.get('conflict_stats', {})
                print(f"[Tick {changes['tick']:3d}] Active: {len(simulator.active_trains):2d} | "
                      f"Arrivals: {len(changes['arrivals']):2d} | "
                      f"Conflicts: {conflict_stats.get('total', 0):3d}")
    
    # Final summary
    stats = engine.get_statistics()
    sim_summary = simulator.get_summary()
    
    summary = {
        "simulation": {
            "scenario": scenario,
            "ticks": ticks,
            "seed": seed,
            "data_source": str(data_path),
            "run_time": datetime.now().isoformat()
        },
        "network": {
            "stations": len(tracker.state.stations),
            "edges": len(tracker.state.edges),
            "trains_loaded": len(tracker.state.trains)
        },
        "simulation_results": sim_summary,
        "detection_results": stats,
        "conflict_output_file": str(output_file)
    }
    
    if verbose:
        print(f"\n{'-'*60}")
        print("\n[Complete] Simulation finished")
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Ticks completed: {sim_summary['ticks_completed']}")
        print(f"Active trains: {sim_summary['active_trains']}")
        print(f"Completed trains: {sim_summary['completed_trains']}")
        
        conflict_stats = stats.get('conflict_stats', {})
        print(f"\nConflicts detected: {conflict_stats.get('total', 0)}")
        print(f"\nConflicts by type:")
        by_type = conflict_stats.get('by_type', {})
        if not by_type:
            print("  - None")
        for ctype, count in by_type.items():
            print(f"  - {ctype}: {count}")
            
        print(f"\nConflicts by severity:")
        by_severity = conflict_stats.get('by_severity', {})
        if not by_severity:
            print("  - None")
        for sev, count in by_severity.items():
            print(f"  - {sev}: {count}")
        print(f"\nConflict log written to: {output_file}")
        print(f"{'='*60}\n")
    
    # Write summary
    summary_path = output_file.parent / "simulation_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    # Write full simulation log
    log_path = output_file.parent / "simulation_log.json"
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(all_changes, f, indent=2)
    
    return summary


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="RailMind Conflict Detection Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
  normal      Regular train operations
  rush_hour   High traffic density
  disruption  Frequent delays and incidents
  stress_test Maximum network load

Examples:
  python -m detection.run_detection
  python -m detection.run_detection --scenario rush_hour --ticks 200
  python -m detection.run_detection --scenario stress_test --seed 42
        """
    )
    
    # Compute default data path relative to this script's location
    import os
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _repo_root = os.path.abspath(os.path.join(_script_dir, '..', '..', '..'))
    _default_data = os.path.join(_repo_root, 'creating-context', 'lombardy_simulation_data.json')
    
    parser.add_argument(
        '--data', '-d',
        type=str,
        default=_default_data,
        help='Path to simulation data JSON'
    )
    
    parser.add_argument(
        '--scenario', '-s',
        type=str,
        default='normal',
        choices=['normal', 'rush_hour', 'disruption', 'stress_test'],
        help='Simulation scenario'
    )
    
    parser.add_argument(
        '--ticks', '-t',
        type=int,
        default=100,
        help='Number of simulation ticks'
    )
    parser.add_argument(
        '--realtime', '-r',
        action='store_true',
        help='Run simulation in realtime mode (sleep between ticks, 30s)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='detection/output/conflicts.json',
        help='Output path for conflict log'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducibility'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress output'
    )
    
    args = parser.parse_args()
    
    run_simulation(
        data_path=Path(args.data),
        scenario=args.scenario,
        ticks=args.ticks,
        output_path=Path(args.output),
        seed=args.seed,
        verbose=not args.quiet,
        realtime=args.realtime
    )


if __name__ == "__main__":
    main()
