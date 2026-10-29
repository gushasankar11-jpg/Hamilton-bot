import json
# Read the corrupted file
with open("data/pyq_db.json", "r") as f:
    content = f.read()

# Try to decode only the first valid JSON object
try:
    decoder = json.JSONDecoder()
    obj, index = decoder.raw_decode(content)
    with open("data/pyq_db.json", "w") as f:
        json.dump(obj, f, indent=2)
    print("✅ Fixed corrupted JSON (removed extra data)")
except Exception as e:
    print(f"❌ Could not fix: {e}")
