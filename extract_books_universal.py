import os, subprocess, json, re, time
from PIL import Image
import pytesseract
from pytesseract import Output

BASE = os.getcwd()
BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
DB_FILE = os.path.join(BASE, "data", "books_master.json")

os.makedirs(OUT_DIR, exist_ok=True)

def log(msg):
    print(msg, flush=True)

def is_scanned(pdf_path):
    """Checks if the PDF is a scanned image by looking at page 10."""
    try:
        text = subprocess.run(["pdftotext", "-f", "10", "-l", "10", pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        # If text is less than 50 chars or contains typical scan watermarks
        if len(text.strip()) < 50 or "downloaded from" in text.lower():
            return True
    except:
        return True
    return False

def process_book_folder(subj, book_name, folder_path):
    pdfs = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    if not pdfs: return
    
    log(f"\n📚 Processing: {subj} / {book_name}")
    
    for pdf in pdfs:
        pdf_path = os.path.join(folder_path, pdf)
        book_id = pdf.replace(".pdf", "").replace(" ", "_")
        out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
        os.makedirs(out_book_dir, exist_ok=True)
        
        scanned = is_scanned(pdf_path)
        mode = "OCR" if scanned else "TEXT"
        log(f"  📄 Scanning: {pdf[:50]} [{mode}]")
        
        try:
            info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15).stdout
            total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
        except: continue
        
        # --- STEP 1: INDEX THE PAGE HEADERS (Map 4.15 to PDF Page 150) ---
        # We scan the top and bottom of each page to find the printed page numbers.
        page_map = {} # "4.15" -> 150
        
        # (For speed, we only index every page using a cheap bbox check)
        for page in range(1, total_pages + 1):
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
            # Look for point system like 4.15 at the top or bottom
            matches = re.findall(r'<word xMin="[\d\.]+" yMin="[\d\.]+"[^>]*>(\d+\.\d+)</word>', xml)
            for m in matches:
                if m not in page_map:
                    page_map[m] = page

        # --- STEP 2: EXTRACT CONTENT ---
        db_entries = {"theory": [], "illustration": [], "exercise": [], "solution": []}
        active_section = "exercise"
        
        for page in range(1, total_pages + 1):
            img_base = os.path.join(out_book_dir, f"tmp_{page}")
            # Render only if we need to crop
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            
            img = Image.open(img_path)
            w, h = img.size
            scale = 150.0 / 72.0
            
            # Get Text / Boxes
            if scanned:
                data = pytesseract.image_to_data(img, output_type=Output.DICT)
                boxes = []
                for i in range(len(data['level'])):
                    if data['text'][i].strip():
                        boxes.append({"text": data['text'][i].strip(), "top": data['top'][i], "left": data['left'][i]})
            else:
                xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
                boxes = []
                for m in re.finditer(r'<word xMin="([\d\.]+)" yMin="([\d\.]+)"[^>]*>(.*?)</word>', xml):
                    boxes.append({"text": m.group(3), "top": float(m.group(2)) * scale, "left": float(m.group(1)) * scale})

            current_q_y = None
            current_q_num = None
            current_q_text = ""

            for i, box in enumerate(boxes):
                text_upper = box['text'].upper()
                
                # Detect Sections
                if "EXERCISE" in text_upper: active_section = "exercise"
                elif "ILLUSTRATION" in text_upper or "EXAMPLE" in text_upper: active_section = "illustration"
                elif "THEORY" in text_upper: active_section = "theory"
                elif "SOLUTION" in text_upper: active_section = "solution"

                # Detect Question Start
                if re.match(r'^(Q\.?\s*)?\d+[\.\)]?$', text_upper) and box['left'] < (w * 0.3):
                    q_num_match = re.search(r'\d+', text_upper)
                    if q_num_match:
                        q_num = int(q_num_match.group())
                        
                        if current_q_y is not None and current_q_num is not None:
                            # Save previous question
                            crop_bot = box['top'] - 20
                            if crop_bot > current_q_y + 40:
                                filename = f"{active_section}_{current_q_num}_p{page}.png"
                                filepath = os.path.join(out_book_dir, active_section, filename)
                                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                                img.crop((0, int(current_q_y), w, int(crop_bot))).save(filepath)
                                db_entries[active_section].append({"q_num": current_q_num, "img": filepath, "q_text": current_q_text})
                        
                        current_q_y = box['top']
                        current_q_num = q_num
                        current_q_text = ""
                
                if current_q_y is not None:
                    current_q_text += box['text'] + " "

            # Save last question on page
            if current_q_y is not None and current_q_num is not None:
                crop_bot = h - 50
                if crop_bot > current_q_y + 40:
                    filename = f"{active_section}_{current_q_num}_p{page}.png"
                    filepath = os.path.join(out_book_dir, active_section, filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    img.crop((0, int(current_q_y), w, int(crop_bot))).save(filepath)
                    db_entries[active_section].append({"q_num": current_q_num, "img": filepath, "q_text": current_q_text})

            img.close()
            os.remove(img_path)
            print(f"    Page {page}/{total_pages} extracted...", end="\r", flush=True)

        # Save to DB
        db = {}
        if os.path.exists(DB_FILE):
            try: db = json.load(open(DB_FILE))
            except: pass
        
        if subj not in db: db[subj] = {}
        if book_name not in db[subj]: db[subj][book_name] = {}
        
        db[subj][book_name][book_id] = {
            "content": db_entries,
            "page_map": page_map
        }
        
        tmp = DB_FILE + ".tmp"
        json.dump(db, open(tmp, "w"), indent=2)
        os.replace(tmp, DB_FILE)
        
        log(f"\n    ✅ {book_id}: {len(db_entries['exercise'])} Exercises, {len(db_entries['illustration'])} Illustrations.")

print("🚀 Starting UNIVERSAL Book Extraction...")
for subj in os.listdir(BOOKS_DIR):
    subj_path = os.path.join(BOOKS_DIR, subj)
    if not os.path.isdir(subj_path): continue
    for book_name in os.listdir(subj_path):
        book_path = os.path.join(subj_path, book_name)
        if os.path.isdir(book_path):
            process_book_folder(subj, book_name, book_path)

print("\n🎉 ALL BOOKS EXTRACTED!")
