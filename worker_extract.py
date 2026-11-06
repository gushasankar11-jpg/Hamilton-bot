import os, subprocess, json, re, gc, sys
from PIL import Image
import pytesseract
from pytesseract import Output

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
DB_FILE = os.path.join(BASE, "data", "books_master.json")

# The Universal Semantic Boundaries
BOUNDARY_REGEX = re.compile(
    r'\b(Example|Illustration|EXERCISE|Exercise|LEVEL|Level|SOLVED EXAMPLE|SOLUTION|Solution|ANSWER KEY|Q\.?\s*\d+|^\d+[\.\)])\b',
    re.IGNORECASE
)

def is_scanned(pdf_path):
    try:
        text = subprocess.run(["pdftotext", "-f", "15", "-l", "15", pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        if len(text.strip()) < 50 or "downloaded from" in text.lower(): return True
    except: return True
    return False

def get_boxes(img, pdf_path, page, scanned):
    """Returns a list of words with (text, x, y, w, h)."""
    if scanned:
        data = pytesseract.image_to_data(img, output_type=Output.DICT)
        return [{"text": data['text'][i].strip(), "left": data['left'][i], "top": data['top'][i], "width": data['width'][i], "height": data['height'][i]} 
                for i in range(len(data['level'])) if data['text'][i].strip() and int(data['conf'][i]) > 30]
    else:
        xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
        scale = 150.0 / 72.0
        return [{"text": m.group(3), "left": float(m.group(1))*scale, "top": float(m.group(2))*scale, "width": 50, "height": 20} 
                for m in re.finditer(r'<word xMin="([\d\.]+)" yMin="([\d\.]+)"[^>]*>(.*?)</word>', xml)]

def detect_columns(boxes, w):
    """Returns True if the page has two columns based on a central vertical gap."""
    mid_left, mid_right = int(w * 0.35), int(w * 0.65)
    x_counts = [0] * (mid_right - mid_left)
    for b in boxes:
        if mid_left <= b['left'] <= mid_right:
            for i in range(int(b['left']) - mid_left, int(b['left'] + b['width']) - mid_left):
                if 0 <= i < len(x_counts): x_counts[i] += 1
                
    max_gap, gap_start, current_gap = 0, -1, 0
    for i, count in enumerate(x_counts):
        if count == 0:
            current_gap += 1
            if current_gap > max_gap: max_gap, gap_start = current_gap, i - current_gap + 1 + mid_left
        else:
            current_gap = 0
            
    return (max_gap > 40, gap_start + (max_gap // 2) if max_gap > 40 else -1)

def find_boundaries(boxes, x_start, x_end):
    """Finds the Y-coordinates where a new semantic block starts."""
    boundaries = []
    for b in boxes:
        # Only check words inside this column's X range
        if x_start <= b['left'] <= x_end:
            text = b['text']
            if BOUNDARY_REGEX.search(text):
                # Check if it's a question number (only valid if it's at the start of a line)
                if re.match(r'^(Q\.?\s*)?\d+[\.\)]?$', text) and b['left'] > (x_start + 100):
                    continue # Ignore random numbers mid-line
                boundaries.append(b['top'])
    return sorted(list(set(boundaries)))

def process_pdf(pdf_path):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    os.makedirs(out_book_dir, exist_ok=True)
    
    scanned = is_scanned(pdf_path)
    print(f"[{'OCR' if scanned else 'TEXT'}] Engine Started: {book_name} / {pdf[:30]}", flush=True)
    
    try:
        total_pages = int(re.search(r'Pages:\s+(\d+)', subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout).group(1))
    except: return
        
    db_entries = {"theory": [], "illustration": [], "exercise": [], "solution": []}
    global_counter = 1
    
    for page in range(16, total_pages + 1):
        img_base = os.path.join(out_book_dir, f"tmp_{page}")
        subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        img_path = img_base + ".png"
        if not os.path.exists(img_path): continue
        
        img = Image.open(img_path)
        w, h = img.size
        boxes = get_boxes(img, pdf_path, page, scanned)

        if len(boxes) < 20:
            img.close(); os.remove(img_path); gc.collect(); continue

        is_two_col, split_x = detect_columns(boxes, w)
        
        if is_two_col:
            columns = [
                {"boxes": [b for b in boxes if b['left'] < split_x], "x_start": 0, "x_end": split_x + 10},
                {"boxes": [b for b in boxes if b['left'] >= split_x], "x_start": split_x - 10, "x_end": w}
            ]
        else:
            columns = [{"boxes": boxes, "x_start": 0, "x_end": w}]

        for col in columns:
            if not col['boxes']: continue
            
            # Find all Y boundaries in this column
            bounds = find_boundaries(col['boxes'], col['x_start'], col['x_end'])
            
            # Add the start and end of the page to the boundaries
            if not bounds or bounds[0] > 100: bounds.insert(0, 0)
            if bounds[-1] < h - 50: bounds.append(h)

            # Iterate through segments
            for i in range(len(bounds) - 1):
                top_y, bot_y = bounds[i], bounds[i+1]
                if bot_y - top_y < 40: continue # Skip tiny slivers

                # Determine section based on the text inside this segment
                segment_boxes = [b for b in col['boxes'] if top_y <= b['top'] < bot_y]
                if not segment_boxes: continue
                
                seg_text = " ".join([b['text'].upper() for b in segment_boxes])
                sec = "theory"
                if "EXERCISE" in seg_text or "LEVEL 1" in seg_text or "LEVEL 2" in seg_text: sec = "exercise"
                elif "ILLUSTRATION" in seg_text or "EXAMPLE" in seg_text: sec = "illustration"
                elif "SOLUTION" in seg_text or "ANSWER" in seg_text: sec = "solution"

                crop_img = img.crop((col["x_start"], int(top_y), col["x_end"], int(bot_y)))
                
                # --- TELEGRAM SAFE RESIZE ---
                if crop_img.height > 4000:
                    ratio = 4000 / crop_img.height
                    crop_img = crop_img.resize((int(crop_img.width * ratio), 4000), Image.LANCZOS)

                filename = f"{sec}_q{global_counter}_p{page}.png"
                filepath = os.path.join(out_book_dir, sec, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                crop_img.save(filepath)
                
                snippet = " ".join([b['text'] for b in segment_boxes])[:300]
                db_entries[sec].append({"q_num": global_counter, "img": filepath, "q_text": snippet})
                global_counter += 1

        img.close()
        os.remove(img_path)
        gc.collect()
        print(f"  {book_id[:20]} p{page} done (2-Col: {is_two_col})", flush=True)

    # Save DB
    import fcntl
    with open(DB_FILE + ".lock", "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        db = {}
        if os.path.exists(DB_FILE):
            try: db = json.load(open(DB_FILE))
            except: pass
        if subj not in db: db[subj] = {}
        if book_name not in db[subj]: db[subj][book_name] = {}
        db[subj][book_name][book_id] = {"content": db_entries, "scanned": scanned}
        tmp = DB_FILE + ".tmp"
        json.dump(db, open(tmp, "w"), indent=2)
        os.replace(tmp, DB_FILE)
        fcntl.flock(lockfile, fcntl.LOCK_UN)

    print(f"✅ FINISHED: {pdf[:20]} -> {len(db_entries['theory'])} Th, {len(db_entries['illustration'])} Ill, {len(db_entries['exercise'])} Ex", flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_pdf(sys.argv[1])
