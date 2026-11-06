import os, subprocess, glob
BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
pdfs = glob.glob(f"{BOOKS_DIR}/**/*.pdf", recursive=True)
print(f"🚀 Found {len(pdfs)} books. Starting sequential extraction...")
for i, pdf in enumerate(pdfs):
    print(f"\n[{i+1}/{len(pdfs)}] Processing: {os.path.basename(pdf)}")
    subprocess.run(["python3", "api_single_extractor.py", pdf])
