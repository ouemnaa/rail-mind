import json
import uuid
from pathlib import Path

INPUT_JSON = "conflict_knowledge_base.json"
OUTPUT_JSON = "conflict_knowledge_base_uuid.json"

# Load JSON
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

# Update IDs to UUIDs
for conflict in data.get("conflicts", []):
    # Replace 'id' with a UUID generated from the original id
    conflict["id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, conflict["id"]))

# Save new JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(f"✓ Updated {len(data.get('conflicts', []))} conflict IDs and saved to {OUTPUT_JSON}")
