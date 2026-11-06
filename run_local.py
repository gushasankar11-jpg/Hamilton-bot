import os, subprocess, glob
BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
pdfs = glob.glob(f"{BOOKS_DIR}/**/*.pdf", recursive=True)
print(f"Found {len(pdfs)} books. Starting LOCAL extraction (No API, No Limits)...")
for pdf in pdfs:
    subprocess.run(["python3", "local_extractor.py", pdf])
print("🎉 ALL BOOKS EXTRACTED LOCALLY!")
