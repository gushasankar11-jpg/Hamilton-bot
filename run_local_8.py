import os, subprocess, glob
from concurrent.futures import ThreadPoolExecutor

BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
pdfs = glob.glob(f"{BOOKS_DIR}/**/*.pdf", recursive=True)

print(f"🚀 Found {len(pdfs)} books. Starting 8 LOCAL workers (No API)...")

def process(pdf, worker_id):
    subprocess.run(["python3", "local_extractor.py", pdf, str(worker_id)])

with ThreadPoolExecutor(max_workers=8) as executor:
    for i, pdf in enumerate(pdfs):
        worker_id = (i % 8) + 1
        executor.submit(process, pdf, worker_id)

print("🎉 ALL BOOKS EXTRACTED!")
