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

def process_book_folder(subj, book_name, folder_path):
    pdfs = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    if not pdfs: return
    
    log(f"\n📚 Processing (OCR): {subj} / {book_name}")
    
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
        
        # We process page by page (limit to first 50 pages for testing, remove limit later)
        # For now, process all pages
        db_entries = {"theory": [], "illustration": [], "exercise": [], "solution": []}
        
        active_section = "exercise" # Default
        active_paragraph_y = None
        active_paragraph_page = None
        
        for page in range(1, total_pages + 1):
            img_base = os.path.join(out_book_dir, f"tmp_{page}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            
            img = Image.open(img_path)
            w, h = img.size
            
            # OCR the page
            data = pytesseract.image_to_data(img, output_type=Output.DICT)
            n_boxes = len(data['level'])
            
            current_q_y = None
            current_q_text = ""
            current_q_num = 1
            
            for i in range(n_boxes):
                text = data['text'][i].strip()
                if not text: continue
                
                top = data['top'][i]
                left = data['left'][i]
                text_upper = text.upper()
                
                # 1. Detect Section Headers
                if "EXERCISE" in text_upper: active_section = "exercise"
                elif "ILLUSTRATION" in text_upper or "EXAMPLE" in text_upper: active_section = "illustration"
                elif "THEORY" in text_upper: active_section = "theory"
                elif "SOLUTION" in text_upper: active_section = "solution"
                
                # 2. Detect Paragraph Start
                if "PARAGRAPH" in text_upper or "PASSAGE" in text_upper:
                    active_paragraph_y = top
                    active_paragraph_page = page
                
                # 3. Detect Question Number (e.g., "1.", "Q.1", "12)")
                if re.match(r'^(Q\.?\s*)?\d+[\.\)]?$', text) and left < (w * 0.3):
                    q_num_match = re.search(r'\d+', text)
                    if q_num_match:
                        q_num = int(q_num_match.group())
                        # If we found a question, we need to crop it
                        # But we need to know where it ENDS. So we look ahead.
                        # For simplicity, we crop up to the next question or bottom of page.
                        # Save the (top) coordinate.
                        if current_q_y is not None:
                            # We found the next question, so crop the PREVIOUS one
                            crop_top = current_q_y
                            # If paragraph is above, include it
                            if active_paragraph_y is not None and active_paragraph_page == page and active_paragraph_y < crop_top:
                                crop_top = active_paragraph_y
                                
                            crop_bot = top - 20
                            if crop_bot > crop_top + 50:
                                filename = f"{active_section}_{current_q_num}_p{page}.png"
                                filepath = os.path.join(out_book_dir, active_section, filename)
                                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                                img.crop((0, int(crop_top), w, int(crop_bot))).save(filepath)
                                
                                db_entries[active_section].append({
                                    "q_num": current_q_num,
                                    "img": filepath,
                                    "q_text": current_q_text
                                })
                        
                        current_q_y = top
                        current_q_num = q_num
                        current_q_text = "" # Reset text buffer
                        
                # Buffer text for the question
                if current_q_y is not None:
                    current_q_text += text + " "
            
            # Crop the last question on the page
            if current_q_y is not None:
                crop_top = current_q_y
                if active_paragraph_y is not None and active_paragraph_page == page and active_paragraph_y < crop_top:
                    crop_top = active_paragraph_y
                crop_bot = h - 50
                if crop_bot > crop_top + 50:
                    filename = f"{active_section}_{current_q_num}_p{page}.png"
                    filepath = os.path.join(out_book_dir, active_section, filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    img.crop((0, int(crop_top), w, int(crop_bot))).save(filepath)
                    db_entries[active_section].append({
                        "q_num": current_q_num,
                        "img": filepath,
                        "q_text": current_q_text
                    })
            
            # Reset paragraph if we move to a new page
            active_paragraph_y = None
            img.close()
            os.remove(img_path)
            log(f"    Page {page}/{total_pages} OCR'd...", end="\r")

        # Save to DB
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
        
        log(f"\n    ✅ {book_id}: {len(db_entries['exercise'])} Exercises, {len(db_entries['illustration'])} Illustrations.")

print("🚀 Starting OCR Book Extraction...")
for subj in os.listdir(BOOKS_DIR):
    subj_path = os.path.join(BOOKS_DIR, subj)
    if not os.path.isdir(subj_path): continue
    for book_name in os.listdir(subj_path):
        book_path = os.path.join(subj_path, book_name)
        if os.path.isdir(book_path):
            process_book_folder(subj, book_name, book_path)

print("\n🎉 ALL BOOKS EXTRACTED!")
