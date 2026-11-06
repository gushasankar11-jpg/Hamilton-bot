import re

def patch_script(path, save_func_code):
    content = open(path).read()
    # Find the save_db function and replace it
    pattern = re.compile(r'def save_db\(.*?\n(?=\ndef |\nclass |\nprint)', re.DOTALL)
    if pattern.search(content):
        content = pattern.sub(save_func_code + "\n\n", content, count=1)
    else:
        # If not found by regex, just replace the known old string
        content = content.replace('''def save_db(db):
    tmp = DB + ".tmp"
    json.dump(db, open(tmp, "w"), indent=2)
    os.replace(tmp, DB)''', save_func_code)
    
    # Update how save_db is called
    if "extract_all" in path:
        content = content.replace('save_db(db)', 'save_db(paper_name, db["papers"][paper_name])')
    elif "extract_adv" in path:
        content = content.replace('save_db(db)', 'save_db(subj, chapter_name, db["practice_adv"][subj][chapter_name])')
        
    open(path, "w").write(content)
    print(f"✅ Patched save logic in {path}")

# 1. Patch extract_all.py (Papers)
save_papers = '''def save_db(paper_name, paper_data):
    import time
    for attempt in range(10):
        try:
            db = load_db()
            db["papers"][paper_name] = paper_data
            tmp = DB + f".{os.getpid()}.tmp"
            json.dump(db, open(tmp, "w"), indent=2)
            os.replace(tmp, DB)
            return
        except Exception as e:
            time.sleep(0.5)
    print("⚠️ Could not save paper to DB after 10 retries")'''
patch_script("extract_all.py", save_papers)

# 2. Patch extract_adv_practice.py (Chapter-wise)
save_adv = '''def save_db(subj, chapter_name, chapter_data):
    import time
    for attempt in range(10):
        try:
            db = load_db()
            if "practice_adv" not in db: db["practice_adv"] = {}
            if subj not in db["practice_adv"]: db["practice_adv"][subj] = {}
            db["practice_adv"][subj][chapter_name] = chapter_data
            tmp = DB + f".{os.getpid()}.tmp"
            json.dump(db, open(tmp, "w"), indent=2)
            os.replace(tmp, DB)
            return
        except Exception as e:
            time.sleep(0.5)
    print("⚠️ Could not save chapter to DB after 10 retries")'''
patch_script("extract_adv_practice.py", save_adv)

