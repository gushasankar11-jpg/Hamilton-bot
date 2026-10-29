# ==========================================================
# pyq_manager.py — Simple Deduplication (No IDs needed)
# ==========================================================
import json
import os

DB_PATH = "data/pyq_database.json"

def load_db():
    if not os.path.exists(DB_PATH):
        return []
    try:
        with open(DB_PATH) as f:
            return json.load(f)
    except Exception:
        return []

def save_question_to_db(q_dict):
    """Saves a generated question to the local database so others can use it."""
    db = load_db()
    
    # Create a simple hash based on the first 50 chars of the question
    q_text = q_dict.get("question", "")
    q_hash = str(hash(q_text))
    q_dict["model_id"] = q_hash
    
    # Don't save if it already exists
    for existing in db:
        if existing.get("model_id") == q_hash:
            return
            
    db.append(q_dict)
    # Keep DB size reasonable (last 500 questions)
    db = db[-500:]
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)

def mark_as_seen(uid, model_id):
    """Remembers that this specific user has seen this question model."""
    profile_path = f"profiles/{uid}.json"
    if not os.path.exists(profile_path):
        return
    with open(profile_path) as f:
        p = json.load(f)
        
    p.setdefault("seen_models", []).append(model_id)
    p["seen_models"] = p["seen_models"][-200:] # keep last 200
    
    with open(profile_path, "w") as f:
        json.dump(p, f, indent=2)
