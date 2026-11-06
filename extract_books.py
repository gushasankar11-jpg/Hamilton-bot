import os, subprocess, json, re, time
from PIL import Image
import difflib

BASE = os.getcwd()
BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
DB_FILE = os.path.join(BASE, "data", "books_master.json")

os.makedirs(OUT_DIR, exist_ok=True)

def log(msg):
    print(msg, flush=True)

def get_similarity(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

def process_book_folder(subj, book_name, folder_path):
    pdfs = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    if not pdfs: return
    
    log(f"\n📚 Processing Book: {subj} / {book_name} ({len(pdfs)} PDFs)")
    
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
        
        # 1. Identify Question pages vs Solution pages
        page_texts = {}
        sol_start_page = None
        
        for page in range(1, total_pages + 1):
            try:
                txt = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
                page_texts[page] = txt
                # Check for solution section header
                if not sol_start_page and re.search(r'\b(Solutions?|Answers?|Hints)\b', txt, re.IGNORECASE):
                    if page > (total_pages * 0.3): # Solutions usually in the later half
                        sol_start_page = page
                        log(f"    📍 Detected Solutions starting at page {page}")
            except: page_texts[page] = ""
        
        if not sol_start_page:
            sol_start_page = total_pages + 1 # No solutions found (e.g. MS Chauhan 16th)

        # 2. Extract Questions
        q_coords = {}
        q_texts = {}
        for page in range(1, sol_start_page):
            if "Answer Key" in page_texts[page] or "ANSWER KEY" in page_texts[page]: continue
            
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
            matches = re.findall(r'<word xMin="([\d\.]+)" yMin="([\d\.]+)"[^>]*>Q?\.?\s*(\d+)[\.\)\s]*</word>', xml)
            foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
            foot_y = float(foot.group(1)) if foot else 1000
            
            for i, (x_str, y_str, q_num) in enumerate(matches):
                if float(x_str) > 150: continue # Ignore numbers in text
                qn = int(q_num)
                y_min = float(y_str)
                y_max = float(matches[i+1][1]) if i+1 < len(matches) else foot_y - 10
                if qn not in q_coords:
                    q_coords[qn] = {"page": page, "y_min": y_min, "y_max": y_max}
        
        for block in re.split(r'(?=(?:^|\n)Q?\.?\s*\d+[\.\)])', "\n".join(page_texts.values())):
            m = re.match(r'(?:^|\n)Q?\.?\s*(\d+)[\.\)]', block)
            if m:
                qn = int(m.group(1))
                if qn not in q_texts:
                    q_texts[qn] = re.sub(r'\s+', ' ', block[:1500]).strip()

        # Save Question Images
        for qn, coord in q_coords.items():
            # Crop logic (simplified for this script, assumes single page for speed)
            img_base = os.path.join(out_book_dir, f"tmp_{coord['page']}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(coord['page']), "-l", str(coord['page']), "-singlefile", pdf_path, img_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            
            img = Image.open(img_path)
            w, h = img.size
            scale = 150.0 / 72.0
            top = max(0, (coord['y_min'] * scale) - 20)
            bot = min(h, (coord['y_max'] * scale))
            
            q_file = os.path.join(out_book_dir, f"q{qn}.png")
            img.crop((0, int(top), w, int(bot))).save(q_file)
            img.close()
            os.remove(img_path)

        # 3. Extract Solutions (if they exist in this PDF)
        sol_imgs = {}
        if sol_start_page <= total_pages:
            sol_coords = {}
            for page in range(sol_start_page, total_pages + 1):
                xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
                matches = re.findall(r'<word xMin="([\d\.]+)" yMin="([\d\.]+)"[^>]*>Q?\.?\s*(\d+)[\.\)\s]*</word>', xml)
                foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
                foot_y = float(foot.group(1)) if foot else 1000
                
                for i, (x_str, y_str, q_num) in enumerate(matches):
                    if float(x_str) > 150: continue
                    qn = int(q_num)
                    y_min = float(y_str)
                    y_max = float(matches[i+1][1]) if i+1 < len(matches) else foot_y - 10
                    if qn not in sol_coords:
                        sol_coords[qn] = {"page": page, "y_min": y_min, "y_max": y_max}
                        
            for qn, coord in sol_coords.items():
                img_base = os.path.join(out_book_dir, f"tmp_sol_{coord['page']}")
                subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(coord['page']), "-l", str(coord['page']), "-singlefile", pdf_path, img_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                img_path = img_base + ".png"
                if not os.path.exists(img_path): continue
                
                img = Image.open(img_path)
                w, h = img.size
                scale = 150.0 / 72.0
                top = max(0, (coord['y_min'] * scale) - 20)
                bot = min(h, (coord['y_max'] * scale))
                
                s_file = os.path.join(out_book_dir, f"sol_{qn}.png")
                img.crop((0, int(top), w, int(bot))).save(s_file)
                sol_imgs[qn] = s_file
                img.close()
                os.remove(img_path)

        # 4. Save to DB
        if q_coords:
            db = {}
            if os.path.exists(DB_FILE):
                try: db = json.load(open(DB_FILE))
                except: pass
            
            if subj not in db: db[subj] = {}
            if book_name not in db[subj]: db[subj][book_name] = {}
            
            q_list = []
            for qn in sorted(q_coords.keys()):
                q_file = os.path.join(out_book_dir, f"q{qn}.png")
                if not os.path.exists(q_file): continue
                
                q_obj = {
                    "q_num": qn,
                    "img": q_file,
                    "q_text": q_texts.get(qn, ""),
                    "solution_img": sol_imgs.get(qn) # Might be None for MS Chauhan 16th
                }
                q_list.append(q_obj)
                
            db[subj][book_name][book_id] = q_list
            
            tmp = DB_FILE + ".tmp"
            json.dump(db, open(tmp, "w"), indent=2)
            os.replace(tmp, DB_FILE)
            log(f"    ✅ Saved {len(q_list)} questions for {book_id}")

print("🚀 Starting Mass Book Extraction...")
for subj in os.listdir(BOOKS_DIR):
    subj_path = os.path.join(BOOKS_DIR, subj)
    if not os.path.isdir(subj_path): continue
    for book_name in os.listdir(subj_path):
        book_path = os.path.join(subj_path, book_name)
        if os.path.isdir(book_path):
            process_book_folder(subj, book_name, book_path)

print("\n🎉 ALL BOOKS EXTRACTED!")
