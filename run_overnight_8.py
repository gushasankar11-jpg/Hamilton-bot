import os, subprocess, glob
from concurrent.futures import ThreadPoolExecutor
import time

BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
pdfs = glob.glob(f"{BOOKS_DIR}/**/*.pdf", recursive=True)

def process(pdf, worker_id):
    subprocess.run(["python3", "ai_vision_engine.py", pdf, str(worker_id)])

print(f"🚀 Found {len(pdfs)} PDFs. Starting 8 workers...")

# Assign worker IDs 1 through 8
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = []
    for i, pdf in enumerate(pdfs):
        worker_id = (i % 8) + 1
        futures.append(executor.submit(process, pdf, worker_id))
    
    for f in futures:
        f.result()

print("🎉 ALL BOOKS EXTRACTED!")
