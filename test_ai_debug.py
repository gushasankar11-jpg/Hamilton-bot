import ai_client
import json

print("🧪 Testing AI Connection...")
prompt = 'Return ONLY JSON: {"items": [{"type": "theory", "start_id": 1, "end_id": 5}]}'
try:
    res = ai_client._route_call("You are a JSON API.", prompt)
    print("\n✅ RAW AI RESPONSE:")
    print("-------------------")
    print(res)
    print("-------------------")
    
    # Try parsing
    clean = res.replace("```json", "").replace("```", "").strip()
    data = json.loads(clean)
    print("✅ JSON Parsed Successfully:", data)
except Exception as e:
    print(f"\n❌ AI FAILED: {e}")
