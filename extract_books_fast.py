import os, subprocess, json, re, time, gc
from PIL import Image
import pytesseract
from pytesseract import Output

BASE = os.getcwd()
BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
DB_FILE = os.path.join(BASE, "data", "books_master.json")

os.makedirs(OUT_DIR, exist_ok=True)

KEYWORDS = {
    "theory": ["THEORY", "CONCEPT", "FORMULA", "POINTS TO REMEMBER", "MATHEMATICAL TOOL"],
    "illustration": ["ILLUSTRATION", "SOLVED EXAMPLE", "EXAMPLE", "TRY IT YOURSELF"],
    "exercise": ["EXERCISE", "LEVEL 1", "LEVEL 2", "PROBLEMS", "MISCELLANEOUS", "OBJECTIVE", "SUBJECTIVE", "MATRIX MATCH", "ASSERTION", "PASSAGE", "PARAGRAPH"]
}

def is_scanned(pdf_path):
    try:
        text = subprocess.run(["pdftotext", "-f", "10", "-l", "10", pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        if len(text.strip()) < 50 or "downloaded from" in text.lower():
            return True
    except: return True
    return False

def process_book_folder(subj, book_name, folder_path):
    pdfs = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    if not pdfs: return
    
    print(f"\n📚 Processing: {subj} / {book_name}", flush=True)
    
    for pdf in pdfs:
        pdf_path = os.path.join(folder_path, pdf)
        book_id = pdf.replace(".pdf", "").replace(" ", "_")
        out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
        os.makedirs(out_book_dir, exist_ok=True)
        
        scanned = is_scanned(pdf_path)
        print(f"  📄 Scanning: {pdf[:50]} [{'OCR' if scanned else 'TEXT'}]", flush=True)
        
        try:
            info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15).stdout
            total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
        except: continue
        
        # Resume logic
        db = {}
        if os.path.exists(DB_FILE):
            try: db = json.load(open(DB_FILE))
            except: pass
        if subj in db and book_name in db[subj] and book_id in db[subj][book_name]:
            if len(db[subj][book_name][book_id].get("content", {}).get("exercise", [])) > 50:
                print(f"    ⏩ Skip (Already done)", flush=True)
                continue

        db_entries = {"theory": [], "illustration": [], "exercise": [], "solution": []}
        active_section = "theory"
        
        for page in range(1, total_pages + 1):
            img_base = os.path.join(out_book_dir, f"tmp_{page}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            
            img = Image.open(img_path)
            w, h = img.size
            
            # Fast OCR by resizing in memory
            img_small = img.resize((w // 2, h // 2))
            
            if scanned:
                data = pytesseract.image_to_data(img_small, output_type=Output.DICT)
                boxes = [{"text": data['text'][i].strip(), "top": data['top'][i]*2, "left": data['left'][i]*2} 
                         for i in range(len(data['level'])) if data['text'][i].strip()]
            else:
                xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
                scale = 150.0 / 72.0
                boxes = [{"text": m.group(3), "top": float(m.group(2))*scale, "left": float(m.group(1))*scale} 
                         for m in re.finditer(r'<word xMin="([\d\.]+)" yMin="([\d\.]+)"[^>]*>(.*?)</word>', xml)]

            # Detect Section
            page_text_all = " ".join([b['text'].upper() for b in boxes])
            for sec, kws in KEYWORDS.items():
                if any(kw in page_text_all for kw in kws):
                    active_section = sec
                    break

            # Find Questions
            qs = []
            for b in boxes:
                if re.match(r'^(Q\.?\s*)?\d+[\.\)]?$', b['text']) and b['left'] < (w * 0.35):
                    qn_match = re.search(r'\d+', b['text'])
                    if qn_match: qs.append({"qn": int(qn_match.group()), "top": b['top']})
            
            qs = sorted(qs, key=lambda x: x['top'])
            unique_qs = []
            last_qn = -1
            for q in qs:
                if q['qn'] != last_qn:
                    unique_qs.append(q)
                    last_qn = q['qn']

            if not unique_qs and len(boxes) > 20:
                filename = f"theory_p{page}.png"
                filepath = os.path.join(out_book_dir, "theory", filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                img.save(filepath)
                db_entries["theory"].append({"q_num": page, "img": filepath, "q_text": page_text_all[:200]})
            elif unique_qs:
                for idx, q in enumerate(unique_qs):
                    top = int(q['top']) - 20
                    bot = int(unique_qs[idx+1]['top']) - 20 if idx+1 < len(unique_qs) else h - 50
                    if bot > top + 40:
                        filename = f"{active_section}_{q['qn']}_p{page}.png"
                        filepath = os.path.join(out_book_dir, active_section, filename)
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        img.crop((0, top, w, bot)).save(filepath)
                        snippet = " ".join([b['text'] for b in boxes if top <= b['top'] <= bot])[:500]
                        db_entries[active_section].append({"q_num": q['qn'], "img": filepath, "q_text": snippet})

            img.close()
            img_small.close()
            os.remove(img_path)
            gc.collect() # MEMORY SAFE
            print(f"    Page {page}/{total_pages} done...", end="\r", flush=True)

        if subj not in db: db[subj] = {}
        if book_name not in db[subj]: db[subj][book_name] = {}
        db[subj][book_name][book_id] = {"content": db_entries, "scanned": scanned}
        
        tmp = DB_FILE + ".tmp"
        json.dump(db, open(tmp, "w"), indent=2)
        os.replace(tmp, DB_FILE)
        print(f"\n    ✅ {book_id}: {len(db_entries['exercise'])} Ex | {len(db_entries['illustration'])} Illus | {len(db_entries['theory'])} Theory", flush=True)

print("🚀 Starting FAST Universal Book Extraction...")
for subj in os.listdir(BOOKS_DIR):
    subj_path = os.path.join(BOOKS_DIR, subj)
    if not os.path.isdir(subj_path): continue
    for book_name in os.listdir(subj_path):
        book_path = os.path.join(subj_path, book_name)
        if os.path.isdir(book_path):
            process_book_folder(subj, book_name, book_path)
print("\n🎉 ALL BOOKS EXTRACTED!")
