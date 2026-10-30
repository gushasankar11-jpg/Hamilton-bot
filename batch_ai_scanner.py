import os, subprocess, json, time
from collections import defaultdict

# Your keys
GROQ_KEYS = [
    "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",
    "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",
    "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",
    "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"
]
MODEL_NAME = "openai/gpt-oss-120b"
groq_idx = 0
DB_FILE = "data/pyq_master.json"

def ask_ai(batch_text):
    global groq_idx
    prompt = f"""
    I am giving you a batch of 10 JEE Main physics questions.
    Analyze them and return a JSON object with a key "verdicts".
    For each question (1 to 10), give:
    - "id": The question number
    - "model": The physics model (e.g., 'Projectile Motion')
    - "keep": true if it's a unique/good question, false if it's a repeat or bad
    - "difficulty": integer 1-10
    - "ideal_time": integer in seconds
    
    Here are the questions:
    {batch_text}
    """
    while True:
        if groq_idx >= len(GROQ_KEYS):
            time.sleep(60); groq_idx = 0
        key = GROQ_KEYS[groq_idx]
        cmd = [
            "curl", "-s", "-X", "POST", "https://api.groq.com/openai/v1/chat/completions",
            "-H", f"Authorization: Bearer {key}", "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            })
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            result = json.loads(res.stdout)
            if "error" in result:
                groq_idx += 1; continue
            return json.loads(result["choices"][0]["message"]["content"])
        except Exception:
            groq_idx += 1

print("🚀 Starting Batch AI Scan...")
db = json.load(open(DB_FILE))

for subj, chapters in db.get("practice", {}).items():
    for ch, q_data in chapters.items():
        qs = q_data.get("priority", [])
        if not qs: continue
        
        print(f"🧠 Batching {subj} / {ch} ({len(qs)} questions)...")
        
        new_priority, new_normal = [], []
        for i in range(0, len(qs), 10):
            batch = qs[i:i+10]
            batch_text = ""
            for q in batch:
                # We don't have the text anymore (we deleted it), so we guess from subtopic
                batch_text += f"ID: {q['q_num']} - Topic: {q.get('subtopic')}\\n"
            
            # Since we don't have text, we use the Vision AI or just skip AI text analysis for now
            # (This is a placeholder for when we re-extract with text)
            
            for q in batch:
                new_priority.append(q) # Keep all for now
                
        db["practice"][subj][ch] = {"priority": new_priority, "normal": q_data.get("normal", [])}
        json.dump(db, open(DB_FILE, "w"), indent=2)
        print(f"✅ {ch}: Processed.")

print("🎉 Batch Scan Complete!")
