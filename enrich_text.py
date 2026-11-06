"""Adds q_text to already-extracted chapters WITHOUT re-cropping images."""
import os, subprocess, json, re

BASE_DIR = os.getcwd()
PDF_PRACTICE = os.path.join(BASE_DIR, "pyq_pdfs", "jee_main", "practice")
DB_FILE = os.path.join(BASE_DIR, "data", "pyq_master.json")

db = json.load(open(DB_FILE))

for subj, chapters in db.get("practice", {}).items():
    subj_dir = os.path.join(PDF_PRACTICE, subj)
    if not os.path.isdir(subj_dir): continue
    
    for ch, data in chapters.items():
        # Skip if all questions already have text
        all_qs = data.get("priority", []) + data.get("normal", [])
        if not all_qs: continue
        if all(q.get("q_text") for q in all_qs):
            print(f"⏩ Skipping (has text): {subj} / {ch}")
            continue
        
        pdf_name = f"JEE Main {ch.replace(' ', ' ')} Previous Year Questions with Answer Key.pdf"
        pdf_path = os.path.join(subj_dir, pdf_name)
        if not os.path.exists(pdf_path):
            # Try alternate name
            for f in os.listdir(subj_dir):
                if ch.replace(" ", "") in f.replace(" ", "").replace(".pdf", ""):
                    pdf_path = os.path.join(subj_dir, f)
                    break
        
        if not os.path.exists(pdf_path):
            print(f"❌ PDF not found for: {ch}")
            continue
        
        print(f"📄 Enriching text: {subj} / {ch}")
        full_text = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
        
        q_texts = {}
        for block in re.split(r'(?=Q\d+\.)', full_text):
            m = re.match(r'Q(\d+)\.', block)
            if m:
                q_texts[int(m.group(1))] = re.sub(r'\s+', ' ', block[:1500]).strip()
        
        for q in all_qs:
            q["q_text"] = q_texts.get(q["q_num"], "")
        
        db["practice"][subj][ch] = data

with open(DB_FILE, "w") as f:
    json.dump(db, f, indent=2)

print(f"✅ Text enrichment complete!")
