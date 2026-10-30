path = "ai_extractor.py"
content = open(path).read()

old_init = """master_db = {"practice": {}, "papers": {}}
if os.path.exists(DB_FILE):
    try: master_db = json.load(open(DB_FILE))
    except: pass"""

new_init = """master_db = {"practice": {}, "papers": {}}
if os.path.exists(DB_FILE):
    try:
        loaded_db = json.load(open(DB_FILE))
        if "practice" in loaded_db: master_db["practice"] = loaded_db["practice"]
        if "papers" in loaded_db: master_db["papers"] = loaded_db["papers"]
    except: pass"""

if old_init in content:
    content = content.replace(old_init, new_init)
    open(path, "w").write(content)
    print("✅ Fixed master_db initialization.")
else:
    print("⏭️ Pattern not found, adding safe init manually...")
    # Fallback if exact string doesn't match
    content = content.replace('master_db = {"practice": {}, "papers": {}}\nif os.path.exists(DB_FILE):', 
                              'master_db = {"practice": {}, "papers": {}}\nif os.path.exists(DB_FILE):\n    loaded_db = {}')
    open(path, "w").write(content)

