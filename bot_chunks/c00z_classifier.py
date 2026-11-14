import json, os, time, threading, glob

def scan_and_classify():
    """Scans extracted books and papers, classifies, and updates DB."""
    db_path = "data/pyq_master.json"
    stats_path = "data/chapter_stats.json"
    
    try:
        db = json.load(open(db_path))
    except:
        db = {"practice": {}, "practice_adv": {}, "papers": {}}
        
    if "practice" not in db: db["practice"] = {}
    
    stats = {}
    updated = False
    
    # 1. Scan Extracted Books (Maths, Physics, etc.)
    for file_path in glob.glob("data/extracted_books_v3/*.json"):
        try:
            book = json.load(open(file_path))
            filename = os.path.basename(file_path)
            
            # Infer Subject & Chapter from filename
            subj = "Maths" if "math" in filename.lower() or "calculus" in filename.lower() or "geometry" in filename.lower() else "Physics"
            
            # Format chapter name (e.g. Cengage_Calculus_G_Tewani -> Calculus)
            ch_name = filename.replace("Cengage_", "").replace("_G_Tewani", "").replace(".json", "").replace("_", " ").title()
            
            if subj not in db["practice"]: db["practice"][subj] = {}
            if ch_name not in db["practice"][subj]: db["practice"][subj][ch_name] = {"priority": [], "normal": []}
            
            # Classify
            mcq = num = match = 0
            for ex in book.get("exercises", []):
                q = {
                    "q_num": ex.get("page", "1"),
                    "type": "MCQ", # Default
                    "img": ex.get("img"),
                    "source": filename,
                    "chapter": ch_name
                }
                
                # Simple heuristic to detect numerics/matches based on block text if available
                if "match" in str(ex).lower(): 
                    q["type"] = "Match"; match += 1
                elif "numerical" in str(ex).lower():
                    q["type"] = "Num"; num += 1
                else:
                    mcq += 1
                    
                db["practice"][subj][ch_name]["normal"].append(q)
                
            if subj not in stats: stats[subj] = {}
            stats[subj][ch_name] = {"MCQ": mcq, "Num": num, "Match": match}
            updated = True
        except Exception as e:
            pass

    if updated:
        # Clean up duplicates
        for subj in db["practice"]:
            for ch in db["practice"][subj]:
                seen = set()
                unique_qs = []
                for q in db["practice"][subj][ch]["normal"]:
                    if q["img"] not in seen:
                        seen.add(q["img"])
                        unique_qs.append(q)
                db["practice"][subj][ch]["normal"] = unique_qs
                
        json.dump(db, open(db_path, "w"), indent=2)
        json.dump(stats, open(stats_path, "w"), indent=2)
        print(f"✅ [Classifier] Auto-classified {len(stats)} chapters.")

def classifier_worker():
    time.sleep(5) # Wait for bot to start
    while True:
        scan_and_classify()
        time.sleep(300) # Run every 5 minutes

try:
    threading.Thread(target=classifier_worker, daemon=True).start()
    print("✅ c00z_classifier: Background Worker Started", flush=True)
except Exception as e:
    print(f"❌ Classifier Error: {e}")
