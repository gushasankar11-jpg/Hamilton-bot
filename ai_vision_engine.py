import os, sys, json, re, base64, time, fcntl
import pdfplumber
import requests
from PIL import Image
import ai_client

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
STATUS_FILE = os.path.join(BASE, "data", "worker_status.json")
ERROR_LOG = os.path.join(BASE, "api_errors.log")
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

def log_error(source, msg):
    with open(ERROR_LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {source}: {msg}\n")

def ask_ai_vision(img_b64, worker_id, book_name, page_num):
    prompt = """
    Analyze this textbook page image.
    If this page is a Cover, Preface, Index, or Advertisement, return: {"items": [{"type": "ignore", "box": [0, 0, 1000, 1000]}]}
    Otherwise, group content into: "theory", "illustration", "exercise", or "solution".
    Return ONLY JSON. Box coordinates MUST be 0-1000.
    Format: {"items": [{"type": "theory", "box": [ymin, xmin, ymax, xmax]}]}
    """
    
    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    
    # STRICT 1-TO-1 KEY BINDING
    w_idx = int(worker_id) - 1
    key = gemini_keys[w_idx] if len(gemini_keys) > w_idx else gemini_keys[0]
    
    # ONLY GEMINI 1.5 FLASH
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    
    fails = 0
    while fails < 5: # Try 5 times, then skip page so it doesn't get stuck forever
        update_status(worker_id, f"📡 {model[:8]} K{w_idx+1}", book_name, page_num)
        
        payload = {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
        
        try:
            res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=20)
            data = res.json()
            if "error" in data:
                err_msg = data['error']['message']
                log_error(f"Gem {model} K{w_idx+1}", err_msg)
                
                # SLEEP FOR EXACTLY 4 SECONDS IF RATE LIMITED
                update_status(worker_id, f"💤 Sleep 4s (K{w_idx+1})", book_name, page_num)
                time.sleep(4)
                fails += 1
                continue
                
            raw = data["candidates"][0]["content"]["parts"][0]["text"]
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match: return json.loads(match.group(0))
        except Exception as e:
            log_error(f"Gem {model} K{w_idx+1}", str(e))
            update_status(worker_id, f"💤 Sleep 4s (K{w_idx+1})", book_name, page_num)
            time.sleep(4)
            fails += 1

    return None

def process_page(pdf_path, page_num, out_book_dir, worker_id, book_name):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]
        im = page.to_image(resolution=72).original
        im.thumbnail((800, 1000))
        temp_img = f"temp_{worker_id}.jpg"
        im.save(temp_img, "JPEG", quality=60)
        
        with open(temp_img, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
        result = ask_ai_vision(img_b64, worker_id, book_name, page_num)
        
        if not result or "items" not in result:
            update_status(worker_id, "❌ Page Skipped (API Dead)", book_name, page_num)
            return
            
        item_count = 0
        w, h = im.size
        
        for i, item in enumerate(result["items"]):
            sec = item.get("type", "theory").lower()
            if sec == "ignore": continue
            if sec not in ["theory", "illustration", "exercise", "solution"]: sec = "theory"
            
            box = item.get("box", [])
            if len(box) != 4: continue
            
            ymin, xmin, ymax, xmax = box
            x0 = max(0, int((xmin / 1000) * w) - 5)
            y0 = max(0, int((ymin / 1000) * h) - 5)
            x1 = min(w, int((xmax / 1000) * w) + 5)
            y1 = min(h, int((ymax / 1000) * h) + 5)
            
            crop = im.crop((x0, y0, x1, y1))
            filename = f"{sec}_{i+1}_p{page_num}.png"
            filepath = os.path.join(out_book_dir, sec, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            crop.save(filepath)
            item_count += 1
            
        update_status(worker_id, "✅ Page Done", book_name, page_num, item_count)

def process_pdf(pdf_path, worker_id):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace("_", " ")[:20]
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id.replace(" ", "_"))
    os.makedirs(out_book_dir, exist_ok=True)
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            for page_num in range(1, total_pages + 1):
                process_page(pdf_path, page_num, out_book_dir, worker_id, book_id)
    except Exception as e:
        update_status(worker_id, f"❌ Error", book_id)
    update_status(worker_id, "✅ Book Done", book_id)

if __name__ == "__main__":
    if len(sys.argv) > 2:
        process_pdf(sys.argv[1], sys.argv[2])
