import json, os, time, re
import ai_client

DB = "data/pyq_master.json"

def extract_json(text):
    # Safely extract JSON even if AI wraps it in markdown
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try: return json.loads(match.group(0))
        except: return None
    return None

def update_db():
    db = json.load(open(DB))
    # Process Papers
    for p_name, p_data in db.get("papers", {}).items():
        qs = p_data.get("questions", [])
        if len(qs) == 0: continue
        
        # Skip if already updated by AI (diff will be 8 or less, default is usually 6)
        if all(q.get("difficulty") != 6 for q in qs): 
            print(f"⏩ Skip (Already done): {p_name[:30]}")
            continue

        print(f"🧠 Analyzing paper: {p_name[:30]}")
        for i in range(0, len(qs), 10):
            batch = qs[i:i+10]
            batch_text = "\n".join([f"ID:{q['q_num']} | {q.get('q_text','')[:300]}" for q in batch])
            prompt = f"""Analyze these JEE questions. Give exact difficulty (1-10) and ideal time in seconds (60-180).
Return ONLY JSON: {{"results": [{{"id": "1", "diff": 8, "time": 120}}, ...]}}
Questions:
{batch_text}"""
            
            try:
                # Uses the built-in 8-key rotation in ai_client!
                res = ai_client._route_call("You are a JSON API. Output ONLY valid JSON.", prompt)
                data = extract_json(res)
                if data and "results" in data:
                    for r in data["results"]:
                        qn = int(r["id"])
                        for q in qs:
                            if q["q_num"] == qn:
                                q["difficulty"] = r["diff"]
                                q["ideal_time"] = r["time"]
            except Exception as e:
                print(f"⚠️ AI Error (Rotating key...): {e}")
                time.sleep(2)
                
            time.sleep(0.5) 
        
        # Save after every paper
        tmp = DB + ".tmp"
        json.dump(db, open(tmp, "w"), indent=2)
        os.replace(tmp, DB)
        print(f"✅ AI Updated & Saved: {p_name[:30]}")

if __name__ == "__main__":
    update_db()
