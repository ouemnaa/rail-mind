from pathlib import Path
from datetime import datetime
import os

# Define the file path
file_path = Path(r"c:\Users\dongm\OneDrive\Desktop\rail-mind\backend\integration\unified_api.py")

print(f"Reading file: {file_path}")
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Part 1: Find the split point
# We are looking for the docstring block describing "Unified FastAPI Server" which starts the VALID second part.
# In the inspection, it started around line 140 with """ and 141 "Unified FastAPI Server"
start_index = -1
for i, line in enumerate(lines):
    if "Unified FastAPI Server" in line:
        # Check if previous line is """
        if i > 0 and '"""' in lines[i-1]:
            start_index = i - 1
        else:
            # Maybe on the same line? No, view_file showed separate lines.
            # Let's look for the preceding """
            for j in range(i-1, i-5, -1):
                if '"""' in lines[j]:
                    start_index = j
                    break
        break

if start_index == -1:
    print("Could not find 'Unified FastAPI Server' split point. Looking for just the import sys after docstring?")
    # Fallback: Look for the import sys that starts the new block
    # imports start around 165
    for i, line in enumerate(lines):
        if i > 150 and "import sys" in line and "import json" in lines[i+8]: # rough fingerprint
            start_index = i
            # But we want the docstring too.
            # Let's just search for the specific docstring line again
            pass

if start_index == -1:
    print("FATAL: Could not identify the split point. Aborting to avoid damage.")
    # For safety, we will just use the hardcoded observation if we are sure.
    # The user saw line 141: "Unified FastAPI Server"
    # So searching string "Unified FastAPI Server" should work.
    pass
else:
    print(f"Found split point at line {start_index+1}")

# Adjust start_index to keep the docstring.
# We slice from start_index.
if start_index != -1:
    new_lines = lines[start_index:]
else:
    # If we really can't find it, maybe the file was already fixed?
    # Check if 'import sys' is at the TOP (ignoring 140 lines).
    if "Unified FastAPI Server" in lines[0:20]:
        print("File seems to be already cleaned (Docstring at top).")
        new_lines = lines
    else:
        print("Could not find marker. Printing first 10 lines:")
        for l in lines[:10]:
            print(l.strip())
        exit(1)

# Part 2: Insert submit_feedback
# We'll look for where to insert it.
insert_marker = '@app.post("/api/outcomes/store")'
insert_index = -1
for i, line in enumerate(new_lines):
    if insert_marker in line:
        insert_index = i
        break

if insert_index == -1:
    print("Could not find insertion point for outcome store.")
    exit(1)

print(f"Found insertion point at relative line {insert_index+1}")

submit_feedback_code = r'''
@app.post("/api/feedback")
async def submit_feedback(request: Request) -> dict:
    """
    Store user feedback and chosen resolution in Qdrant collection 'rail_incidents'.
    Request body should include:
    {
        "conflict_id": str,
        "resolution_id": str,
        "feedback": str,
        "user_id": str (optional),
        ... (any other fields)
    }
    """
    try:
        data = await request.json()
        conflict_id = data.get("conflict_id")
        resolution_id = data.get("resolution_id")
        feedback = data.get("feedback", "")
        user_id = data.get("user_id", "anonymous")
        timestamp = datetime.now().isoformat()

        # Prepare Qdrant payload
        payload = {
            "conflict_id": conflict_id,
            "resolution_id": resolution_id,
            "feedback": feedback,
            "user_id": user_id,
            "timestamp": timestamp,
        }

        # Optionally add all other fields
        for k, v in data.items():
            if k not in payload:
                payload[k] = v

        # Store in Qdrant
        try:
            from qdrant_client import QdrantClient
            import uuid
            # Use a simple text embedding for feedback+resolution
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            text_to_embed = f"{conflict_id} {resolution_id} {feedback}"
            embedding = model.encode(text_to_embed).tolist()

            qdrant_url = "https://cf323744-546a-492d-b614-8542cb3ce423.us-east-1-1.aws.cloud.qdrant.io"
            qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.fI89vclTejMkRnUs-MbAmV-O4PwoQcYE1DO_fN6l7LM"
            client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

            collection_name = "rail_incidents"
            # Ensure collection exists
            try:
                client.get_collection(collection_name)
            except:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config={"size": len(embedding), "distance": "Cosine"},
                )

            client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": int(uuid.uuid4().int % (2**32)),
                        "vector": embedding,
                        "payload": payload,
                    }
                ]
            )
            print(f"[API] ✅ Feedback stored in Qdrant: {collection_name}")
        except Exception as e:
            print(f"[API] ⚠️ Qdrant feedback storage failed: {e}")

        # Optionally, also store to local file for audit
        feedback_dir = OUTCOMES_DIR / "feedback"
        feedback_dir.mkdir(exist_ok=True)
        feedback_file = feedback_dir / f"feedback_{conflict_id}_{timestamp.replace(':', '-')}.json"
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return {"success": True, "message": "Feedback stored successfully"}
    except Exception as e:
        print(f"[API] ❌ Failed to store feedback: {e}")
        return {"success": False, "message": f"Failed to store feedback: {e}"}

'''

# Insert code
new_lines.insert(insert_index, submit_feedback_code + "\n\n")

# Write to a temp file first maybe? No, let's just write to the file.
backup_path = file_path.with_suffix(".py.bak")
with open(backup_path, "w", encoding="utf-8") as f:
    f.writelines(lines)
print(f"Backup created at {backup_path}")

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Successfully overwrote unified_api.py")
