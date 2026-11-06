import os, sys, re, json, fcntl
import pdfplumber

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
STATUS_FILE = os.path.join(BASE, "data", "worker_status.json")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)

def update_status(worker_id, status, book="", page=0, items=0):
    with open(STATUS_FILE + ".lock", "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        data = {}
        if os.path.exists(STATUS_FILE):
            try: data = json.load(open(STATUS_FILE))
            except: pass
        data[str(worker_id)] = {"status": status, "book": book, "page": page, "items": items}
        tmp = STATUS_FILE + ".tmp"
        json.dump(data, open(tmp, "w"), indent=2)
        os.replace(tmp, STATUS_FILE)
        fcntl.flock(lockfile, fcntl.LOCK_UN)

HEADING_REGEX = re.compile(r'\b(Example|Illustration|EXERCISE|Exercise|SOLVED EXAMPLE|SOLUTION|Solution|LEVEL|Level)\b', re.IGNORECASE)

def process_pdf(pdf_path, worker_id):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")[:25]
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    os.makedirs(out_book_dir, exist_ok=True)
    
    update_status(worker_id, "📖 Reading", book_id)
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            for page_num in range(1, total_pages + 1):
                update_status(worker_id, "✂️ Cropping", book_id, page_num)
                
                page = pdf.pages[page_num - 1]
                words = page.extract_words()
                if not words: continue
                
                lines = {}
                for w in words:
                    y_round = round(w['top'] / 10) * 10
                    if y_round not in lines: lines[y_round] = []
                    lines[y_round].append(w)
                
                items = []
                current_item = None
                
                for y in sorted(lines.keys()):
                    lw = sorted(lines[y], key=lambda w: w['x0'])
                    text = " ".join([w['text'] for w in lw])
                    
                    is_heading = HEADING_REGEX.search(text)
                    is_q_num = re.match(r'^(Q\.?\s*)?\d+[\.\)]', text.strip()) and lw[0]['x0'] < (page.width * 0.4)
                    
                    if is_heading or is_q_num:
                        if current_item: items.append(current_item)
                        
                        sec = "theory"
                        t_upper = text.upper()
                        if "EXERCISE" in t_upper or "LEVEL" in t_upper: sec = "exercise"
                        elif "ILLUSTRATION" in t_upper or "EXAMPLE" in t_upper or "SOL" in t_upper: sec = "illustration"
                        
                        current_item = {
                            "type": sec, "text": text, 
                            "x0": lw[0]['x0'], "y0": lw[0]['top'], 
                            "x1": lw[-1]['x1'], "y1": lw[-1]['bottom']
                        }
                    else:
                        if current_item:
                            current_item["text"] += "\n" + text
                            current_item["x0"] = min(current_item["x0"], lw[0]['x0'])
                            current_item["y0"] = min(current_item["y0"], lw[0]['top'])
                            current_item["x1"] = max(current_item["x1"], lw[-1]['x1'])
                            current_item["y1"] = max(current_item["y1"], lw[-1]['bottom'])
                        else:
                            current_item = {
                                "type": "theory", "text": text, 
                                "x0": lw[0]['x0'], "y0": lw[0]['top'], 
                                "x1": lw[-1]['x1'], "y1": lw[-1]['bottom']
                            }
                            
                if current_item: items.append(current_item)
                
                for i, item in enumerate(items):
                    if (item["y1"] - item["y0"]) < 30: continue 
                    
                    x0 = max(0, item["x0"] - 5)
                    y0 = max(0, item["y0"] - 5)
                    x1 = min(page.width, item["x1"] + 5)
                    y1 = min(page.height, item["y1"] + 5)
                    
                    im = page.crop((x0, y0, x1, y1)).to_image(resolution=120).original
                    if im.height > 4000:
                        ratio = 4000 / im.height
                        im = im.resize((int(im.width * ratio), 4000))
                        
                    filename = f"{item['type']}_{i+1}_p{page_num}.png"
                    filepath = os.path.join(out_book_dir, item['type'], filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    im.save(filepath)
                    
                update_status(worker_id, "✅ Page Done", book_id, page_num, len(items))
                
    except Exception as e:
        update_status(worker_id, "❌ Error", book_id)
        return

    update_status(worker_id, "✅ Book Done", book_id)

if __name__ == "__main__":
    if len(sys.argv) > 2:
        process_pdf(sys.argv[1], sys.argv[2])
