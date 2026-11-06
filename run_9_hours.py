import os, subprocess, glob

BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
pdfs = glob.glob(f"{BOOKS_DIR}/**/*.pdf", recursive=True)

print(f"🚀 Found {len(pdfs)} books. Starting the 9-hour single-worker extraction...")
print(f"⚠️ This will run completely locally using OpenCV + Tesseract. No APIs, no limits.")

for i, pdf in enumerate(pdfs):
    print(f"\n[{i+1}/{len(pdfs)}] Processing: {os.path.basename(pdf)}")
    subprocess.run(["python3", "master_single_extractor.py", pdf])

print("\n🎉 ALL BOOKS EXTRACTED SUCCESSFULLY!")
