import os, json

IMG_PRACTICE = os.path.join("pyq_images", "jee_main", "practice")
DB_FILE = os.path.join("data", "pyq_db.json")

db = {"practice": {}, "papers": {}}

if os.path.isdir(IMG_PRACTICE):
    for subj in sorted(os.listdir(IMG_PRACTICE)):
        subj_dir = os.path.join(IMG_PRACTICE, subj)
        if not os.path.isdir(subj_dir):
            continue
        db["practice"][subj] = {}
        for folder in sorted(os.listdir(subj_dir)):
            folder_path = os.path.join(subj_dir, folder)
            if not os.path.isdir(folder_path):
                continue
            pages = [f for f in os.listdir(folder_path)
                     if f.startswith("page") and f.lower().endswith(".png")]
            if not pages:
                continue
            chapter_key = folder.replace("_", " ")
            db["practice"][subj][chapter_key] = {
                "pages": len(pages),
                "path": folder_path
            }

# Preserve any existing 'papers' entries
if os.path.exists(DB_FILE):
    try:
        old = json.load(open(DB_FILE))
        if old.get("papers"):
            db["papers"] = old["papers"]
    except Exception:
        pass

os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
with open(DB_FILE, "w") as f:
    json.dump(db, f, indent=2)

print("Rebuilt", DB_FILE)
print("Subjects:", list(db["practice"].keys()))
total_pages = 0
for s, chaps in db["practice"].items():
    n = sum(c["pages"] for c in chaps.values())
    print(f"  {s}: {len(chaps)} chapters, {n} pages")
    total_pages += n
print(f"  TOTAL: {total_pages} pages")
