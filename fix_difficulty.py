import json

DB_FILE = "data/pyq_master.json"
db = json.load(open(DB_FILE))

def calc_diff(q_text):
    if not q_text: return 5
    q_len = len(q_text)
    # Smarter Heuristic
    if "Assertion" in q_text or "Match the" in q_text or "Statement" in q_text:
        return 8 # Conceptually tricky
    if q_len > 400:
        return 7 # Long calculation
    if q_len > 200:
        return 6
    if q_len < 100:
        return 4 # Very short, likely direct formula
    return 5 # Average

for subj, chapters in db.get("practice", {}).items():
    for ch, data in chapters.items():
        for q in data.get("priority", []) + data.get("normal", []):
            q["difficulty"] = calc_diff(q.get("q_text", ""))

json.dump(db, open(DB_FILE, "w"), indent=2)
print("✅ Fixed difficulty for all questions in DB.")
