import json
from pathlib import Path

data_path = Path(r"C:\vectors-in-orbit\creating-context\lombardy_simulation_data.json")
with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Loaded {len(data.get('trains', []))} trains")
print(f"Loaded {len(data.get('stations', []))} stations")
print(f"Loaded {len(data.get('rails', []))} rails")

conflicts = []

# Check edge capacity
for edge in data.get("rails", []):
    load = edge.get("current_load", 0)
    cap = edge.get("capacity", 2)
    if load > cap:
        conflicts.append(f"Edge {edge['source']}--{edge['target']} has load {load} > capacity {cap}")

# Check station capacity
for station in data.get("stations", []):
    # Data doesn't seem to have current_occupancy, it's a runtime state
    pass

print(f"Found {len(conflicts)} initial edge capacity conflicts in data")
for c in conflicts[:10]:
    print(c)
