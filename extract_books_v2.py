import os, subprocess, json, re, time
from PIL import Image

BASE = os.getcwd()
BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
DB_FILE = os.path.join(BASE, "data", "books_master.json")

os.makedirs(OUT_DIR, exist_ok=True)

def log(msg):
    print(msg, flush=True)

def detect_section(text):
    t = text.upper()
    if re.search(r'\b(THEORY|CONCEPT|FORMULA)\b', t): return "theory"
    if re.search(r'\b(ILLUSTRATION|SOLVED EXAMPLE|EXAMPLE)\b', t): return "illustration"
    if re.search(r'\b(EXERCISE|LEVEL|PROBLEM|QUESTION)\b', t): return "exercise"
    if re.search(r'\b(SOLUTION|ANSWER KEY|HINTS)\b', t): return "solution"
    return None

def process_book_folder(subj, book_name, folder_path):
    pdfs = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    if not pdfs: return
    
    log(f"\n📚 Processing: {subj} / {book_name}")
    
    for pdf in pdfs:
        pdf_path = os.path.join(folder_path, pdf)
        book_id = pdf.replace(".pdf", "").replace(" ", "_")
        out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
        os.makedirs(out_book_dir, exist_ok=True)
        
        log(f"  📄 Scanning: {pdf[:50]}")
        
        try:
            info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15).stdout
            total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
        except: continue
        
        page_texts = {}
        page_sections = {}
        current_section = "unknown"
        
        # 1. Map Sections
        for page in range(1, total_pages + 1):
            try:
                txt = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
                page_texts[page] = txt
                detected = detect_section(txt[:500]) # Check top of page
                if detected:
                    current_section = detected
                page_sections[page] = current_section
            except: 
                page_texts[page] = ""
                page_sections[page] = current_section

        # 2. Extract Crops
        crop_data = [] # List of dicts {qn, section, page, y_min, y_max, text}
        
        for page in range(1, total_pages + 1):
            sec = page_sections[page]
            if sec == "unknown": continue
            
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
            # Find any numbered item (Q1, 1., Illustration 1)
            matches = re.findall(r'<word xMin="([\d\.]+)" yMin="([\d\.]+)"[^>]*>(?:Q\.?\s*|Illustration\s*)?(\d+)[\.\)\s]*</word>', xml)
            foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
            foot_y = float(foot.group(1)) if foot else 1000
            
            for i, (x_str, y_str, q_num) in enumerate(matches):
                if float(x_str) > 200: continue # Skip numbers in the middle of text
                qn = int(q_num)
                y_min = float(y_str)
                y_max = float(matches[i+1][1]) if i+1 < len(matches) else foot_y - 10
                
                # Get text block for this question
                # (Simplified for speed, getting surrounding text)
                q_text = f"Q{qn} from {sec}" 
                
                crop_data.append({
                    "qn": qn, "section": sec, "page": page, 
                    "y_min": y_min, "y_max": y_max, "text": q_text
                })

        # 3. Crop Images
        sec_dirs = {}
        for sec in ["theory", "illustration", "exercise", "solution"]:
            sec_dirs[sec] = os.path.join(out_book_dir, sec)
            os.makedirs(sec_dirs[sec], exist_ok=True)

        db_entries = {"theory": [], "illustration": [], "exercise": [], "solution": []}

        for item in crop_data:
            sec = item["section"]
            page = item["page"]
            
            img_base = os.path.join(out_book_dir, f"tmp_{page}")
            if not os.path.exists(img_base + ".png"):
                subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            
            img = Image.open(img_path)
            w, h = img.size
            scale = 150.0 / 72.0
            top = max(0, (item['y_min'] * scale) - 20)
            bot = min(h, (item['y_max'] * scale))
            
            if bot > top:
                # We name them systematically
                filename = f"{sec}_{item['qn']}_p{page}.png"
                filepath = os.path.join(sec_dirs[sec], filename)
                img.crop((0, int(top), w, int(bot))).save(filepath)
                
                db_entries[sec].append({
                    "q_num": item["qn"],
                    "img": filepath,
                    "q_text": item["text"]
                })
            img.close()

        # Cleanup temp images
        for f in os.listdir(out_book_dir):
            if f.startswith("tmp_") and f.endswith(".png"):
                os.remove(os.path.join(out_book_dir, f))

        # 4. Save to DB
        db = {}
        if os.path.exists(DB_FILE):
            try: db = json.load(open(DB_FILE))
            except: pass
        
        if subj not in db: db[subj] = {}
        if book_name not in db[subj]: db[subj][book_name] = {}
        
        db[subj][book_name][book_id] = db_entries
        
        tmp = DB_FILE + ".tmp"
        json.dump(db, open(tmp, "w"), indent=2)
        os.replace(tmp, DB_FILE)
        
        log(f"    ✅ {book_id}: {len(db_entries['exercise'])} Exercises, {len(db_entries['illustration'])} Illustrations, {len(db_entries['theory'])} Theory.")

print("🚀 Starting SMART Book Extraction (Theory/Illustrations/Exercises)...")
for subj in os.listdir(BOOKS_DIR):
    subj_path = os.path.join(BOOKS_DIR, subj)
    if not os.path.isdir(subj_path): continue
    for book_name in os.listdir(subj_path):
        book_path = os.path.join(subj_path, book_name)
        if os.path.isdir(book_path):
            process_book_folder(subj, book_name, book_path)

print("\n🎉 ALL BOOKS EXTRACTED!")
