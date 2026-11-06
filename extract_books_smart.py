import os, subprocess, json, re, time, gc
from PIL import Image
import pytesseract
from pytesseract import Output

BASE = os.getcwd()
BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
DB_FILE = os.path.join(BASE, "data", "books_master.json")
os.makedirs(OUT_DIR, exist_ok=True)

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
    
    print(f"\n📚 Processing: {subj} / {book_name}")
    
    for pdf in pdfs:
        pdf_path = os.path.join(folder_path, pdf)
        book_id = pdf.replace(".pdf", "").replace(" ", "_")
        out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
        os.makedirs(out_book_dir, exist_ok=True)
        
        scanned = is_scanned(pdf_path)
        print(f"  📄 Scanning: {pdf[:50]} [{'OCR' if scanned else 'TEXT'}]")
        
        try:
            info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15).stdout
            total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
        except: continue
        
        db_entries = {"illustration": [], "exercise": []}
        active_section = "exercise"
        
        # Start from page 16 to skip Preface/Index
        for page in range(16, total_pages + 1):
            img_base = os.path.join(out_book_dir, f"tmp_{page}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            
            img = Image.open(img_path)
            w, h = img.size
            
            if scanned:
                data = pytesseract.image_to_data(img, output_type=Output.DICT)
                boxes = [{"text": data['text'][i].strip(), "top": data['top'][i], "left": data['left'][i], "width": data['width'][i]} 
                         for i in range(len(data['level'])) if data['text'][i].strip()]
            else:
                xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
                scale = 150.0 / 72.0
                boxes = [{"text": m.group(3), "top": float(m.group(2))*scale, "left": float(m.group(1))*scale, "width": 50} 
                         for m in re.finditer(r'<word xMin="([\d\.]+)" yMin="([\d\.]+)"[^>]*>(.*?)</word>', xml)]

            # Junk Filter: If less than 40 words, skip page (blank/index)
            if len(boxes) < 40:
                img.close(); os.remove(img_path); gc.collect(); continue

            # Detect Sections
            page_text_all = " ".join([b['text'].upper() for b in boxes])
            if "ILLUSTRATION" in page_text_all or "SOLVED EXAMPLE" in page_text_all: active_section = "illustration"
            elif "EXERCISE" in page_text_all or "LEVEL" in page_text_all: active_section = "exercise"

            # Find Questions (must be near the left margin)
            qs = []
            for b in boxes:
                if re.match(r'^(Q\.?\s*)?\d+[\.\)]?$', b['text']) and b['left'] < (w * 0.35):
                    qn_match = re.search(r'\d+', b['text'])
                    if qn_match: 
                        qs.append({"qn": int(qn_match.group()), "top": b['top'], "left": b['left']})
            
            qs = sorted(qs, key=lambda x: x['top'])
            unique_qs = []
            last_qn = -1
            for q in qs:
                if q['qn'] != last_qn:
                    unique_qs.append(q)
                    last_qn = q['qn']

            # Crop Questions
            for idx, q in enumerate(unique_qs):
                top = int(q['top']) - 20
                bot = int(unique_qs[idx+1]['top']) - 20 if idx+1 < len(unique_qs) else h - 50
                
                if bot > top + 50:
                    filename = f"{active_section}_{q['qn']}_p{page}.png"
                    filepath = os.path.join(out_book_dir, active_section, filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    # Crop the whole width (safer than guessing columns for now)
                    img.crop((0, top, w, bot)).save(filepath)
                    
                    snippet = " ".join([b['text'] for b in boxes if top <= b['top'] <= bot])[:500]
                    db_entries[active_section].append({"q_num": q['qn'], "img": filepath, "q_text": snippet})

            img.close()
            os.remove(img_path)
            gc.collect()
            print(f"    Page {page}/{total_pages} done...", end="\r", flush=True)

        if subj not in db: db[subj] = {}
        if book_name not in db[subj]: db[subj][book_name] = {}
        db[subj][book_name][book_id] = {"content": db_entries, "scanned": scanned}
        
        tmp = DB_FILE + ".tmp"
        json.dump(db, open(tmp, "w"), indent=2)
        os.replace(tmp, DB_FILE)
        print(f"\n    ✅ {book_id}: {len(db_entries['exercise'])} Ex | {len(db_entries['illustration'])} Illus")

print("🚀 Starting SMART Book Extraction...")
for subj in os.listdir(BOOKS_DIR):
    subj_path = os.path.join(BOOKS_DIR, subj)
    if not os.path.isdir(subj_path): continue
    for book_name in os.listdir(subj_path):
        book_path = os.path.join(subj_path, book_name)
        if os.path.isdir(book_path):
            process_book_folder(subj, book_name, book_path)
print("\n🎉 DONE!")
