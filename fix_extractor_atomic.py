import ast

path = "perfect_extractor.py"
content = open(path).read()

old = '''            with open(DB_FILE, "w") as f:
                json.dump(master_db, f, indent=2)'''

new = '''            tmp = DB_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(master_db, f, indent=2)
            import os as _os
            _os.replace(tmp, DB_FILE)'''

if old in content:
    content = content.replace(old, new)
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ Extractor now uses atomic writes (no more mid-read corruption)")
    except SyntaxError as e:
        print(f"❌ Syntax: {e}")
else:
    print("⚠️ Pattern not found — extractor may already be atomic")
