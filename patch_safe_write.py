content = open("process_pdfs.py").read()
old_write = '''with open(DB_FILE, "w") as f:
    json.dump(db, f, indent=2)'''
new_write = '''tmp_file = DB_FILE + ".tmp"
with open(tmp_file, "w") as f:
    json.dump(db, f, indent=2)
import os
os.replace(tmp_file, DB_FILE)'''
if old_write in content:
    content = content.replace(old_write, new_write)
    open("process_pdfs.py", "w").write(content)
    print("✅ process_pdfs.py patched: Now uses atomic safe writes (no more corruption!)")
else:
    print("⏭️ process_pdfs.py already safe or pattern not found.")
