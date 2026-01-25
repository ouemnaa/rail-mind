from datetime import datetime
from state_tracker import StateTracker
from engine import DetectionEngine, ConflictEmitter
from models import TrainType, TrainStatus, BlockingBehavior

def run_smoke_test():
    tracker = StateTracker()
    
    # Add a station with low capacity
    # Using real names from Lombardy data for realism
    tracker.load_from_json({
        "stations": [
            {"id": "MILANO CENTRALE", "max_trains_at_once": 1, "blocking_behavior": "hard"}
        ],
        "rails": [
            {"source": "MILANO CENTRALE", "target": "MILANO LAMBRATE", "capacity": 1}
        ],
        "trains": [
            {
                "train_id": "TEST_1",
                "train_type": "intercity",
                "route": [{"station_name": "MILANO CENTRALE"}]
            },
            {
                "train_id": "TEST_2",
                "train_type": "regional",
                "route": [{"station_name": "MILANO CENTRALE"}]
            }
        ]
    })
    
    # Initialize engine
    emitter = ConflictEmitter(enable_console=True)
    engine = DetectionEngine(tracker, emitter=emitter)
    
    # Manually place two trains at the same station (Capacity 1)
    tracker.train_arrives_at_station("TEST_1", "MILANO CENTRALE")
    tracker.train_arrives_at_station("TEST_2", "MILANO CENTRALE")
    
    print("\n--- Running Detection on Conflicting State ---")
    conflicts = engine.evaluate_all_rules()
    
    print(f"\nDetected {len(conflicts)} conflicts.")
    for c in conflicts:
        print(f"Rule: {c.rule_triggered} | Explanation: {c.explanation}")

if __name__ == "__main__":
    run_smoke_test()
