import json
import re

DB_FILE = "data/pyq_master.json"
db = json.load(open(DB_FILE))

def get_year(q):
    src = q.get("source", "")
    m = re.search(r'(20\d\d)', src)
    return int(m.group(1)) if m else 0

# Sort priorities for Main and Adv Chapter-wise
for subj, chapters in db.get("practice", {}).items():
    for ch, data in chapters.items():
        priority = data.get("priority", [])
        # Sort by Year descending (2026 first), then by Difficulty descending (Hard first)
        priority.sort(key=lambda x: (get_year(x), x.get("difficulty", 5)), reverse=True)
        data["priority"] = priority

for subj, chapters in db.get("practice_adv", {}).items():
    for ch, data in chapters.items():
        priority = data.get("priority", [])
        priority.sort(key=lambda x: (get_year(x), x.get("difficulty", 5)), reverse=True)
        data["priority"] = priority

json.dump(db, open(DB_FILE, "w"), indent=2)
print("✅ DB Sorted: Newest Years (2026+) and Hardest questions are now Priority 1.")
