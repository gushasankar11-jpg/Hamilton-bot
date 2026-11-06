import os, sys, json, re, base64, time, fcntl
import pdfplumber
import requests
from PIL import Image, ImageDraw
import ai_client

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
STATUS_FILE = os.path.join(BASE, "data", "worker_status.json")
PROGRESS_FILE = os.path.join(BASE, "data", "extraction_progress.json")
ERROR_LOG = os.path.join(BASE, "api_errors.log")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)

def update_status(status, book="", page=0, items=0):
    with open(STATUS_FILE + ".lock", "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        data = {"status": status, "book": book, "page": page, "items": items}
        tmp = STATUS_FILE + ".tmp"
        json.dump(data, open(tmp, "w"), indent=2)
        os.replace(tmp, STATUS_FILE)
        fcntl.flock(lockfile, fcntl.LOCK_UN)

def log_error(source, msg):
    with open(ERROR_LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {source}: {msg}\n")

def ask_ai_vision(img_b64, book_name, page_num):
    prompt = """
    You are an expert JEE textbook layout analyzer. Analyze this page (1 or 2 columns).
    Group into EXACTLY these categories:
    1. "theory": Explanations, definitions, formulas. (Group all together)
    2. "illustration": Worked examples. Include header, question, and solution.
    3. "exercise": Questions under an "Exercise" header. Include question AND options (A,B,C,D).
    4. "solution": Step-by-step math.
    5. "ignore": Cover, Preface, Index.
    Return ONLY JSON. Boxes 0-1000. {"items": [{"type": "theory", "box": [ymin, xmin, ymax, xmax]}]}
    """
    
    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    groq_keys = getattr(ai_client, "GROQ_KEYS", [])
    keys = gemini_keys + groq_keys
    
    # INFINITE RETRY UNTIL SUCCESS
    while True:
        for k_idx, key in enumerate(keys):
            update_status(f"📡 K{k_idx+1}", book_name, page_num)
            
            # Determine provider based on key index
            if k_idx < len(gemini_keys):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
                headers = {"Content-Type": "application/json"}
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {
                    "model": "qwen/qwen3.8-27b",
                    "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=15)
                data = res.json()
                if "error" not in data:
                    if k_idx < len(gemini_keys):
                        raw = data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        raw = data["choices"][0]["message"]["content"]
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    if match: return json.loads(match.group(0))
            except Exception as e:
                log_error(f"Key {k_idx+1}", str(e))
                
        update_status(f"⏳ Keys Exhausted. Waiting 5s", book_name, page_num)
        time.sleep(5)

def process_pdf(pdf_path):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")[:30]
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    os.makedirs(out_book_dir, exist_ok=True)
    
    # --- EXACT PAGE RESUME LOGIC ---
    prog = {}
    if os.path.exists(PROGRESS_FILE):
        try: prog = json.load(open(PROGRESS_FILE))
        except: pass
        
    start_page = prog.get(book_id, 1)
    
    if start_page == -1:
        print(f"⏭️ Skipping: {book_id} (Already fully extracted)")
        return
        
    print(f"\n📖 STARTING BOOK: {book_id} from Page {start_page}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf_obj:
            total_pages = len(pdf_obj.pages)
            for page_num in range(start_page, total_pages + 1):
                page = pdf_obj.pages[page_num - 1]
                
                im = page.to_image(resolution=100).original
                im.thumbnail((1024, 1024))
                w, h = im.size
                
                temp_img = "temp_api.jpg"
                im.save(temp_img, "JPEG", quality=85)
                
                with open(temp_img, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')
                    
                print(f"  👁️ Scanning Page {page_num}/{total_pages}...")
                
                result = ask_ai_vision(img_b64, book_id, page_num)
                
                if not result or "items" not in result:
                    continue
                    
                all_boxes = []
                for item in result["items"]:
                    sec = item.get("type", "theory").lower()
                    if sec == "ignore": continue
                    if sec not in ["theory", "illustration", "exercise", "solution"]: sec = "theory"
                    box = item.get("box", [])
                    if len(box) == 4: all_boxes.append((sec, box))
                        
                item_count = 0
                
                # 1. Crop Illustrations and Exercises
                for sec, box in all_boxes:
                    if sec == "theory": continue
                    ymin, xmin, ymax, xmax = box
                    x0, y0 = max(0, int((xmin/1000)*w)-5), max(0, int((ymin/1000)*h)-5)
                    x1, y1 = min(w, int((xmax/1000)*w)+5), min(h, int((ymax/1000)*h)+5)
                    if (x1-x0) < 100 or (y1-y0) < 50: continue
                    
                    crop = im.crop((x0, y0, x1, y1))
                    filename = f"{sec}_{item_count+1}_p{page_num}.png"
                    filepath = os.path.join(out_book_dir, sec, filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    crop.save(filepath)
                    item_count += 1
                    
                # 2. Handle Theory
                theory_boxes = [b for s, b in all_boxes if s == "theory"]
                other_boxes = [b for s, b in all_boxes if s != "theory"]
                
                if theory_boxes:
                    theory_area = sum([ (b[2]-b[0])*(b[3]-b[1]) for b in theory_boxes ])
                    if (theory_area / (1000*1000)) > 0.40:
                        theory_img = im.copy()
                        draw = ImageDraw.Draw(theory_img)
                        for obox in other_boxes:
                            oymin, oxmin, oymax, oxmax = obox
                            ox0, oy0 = max(0, int((oxmin/1000)*w)-10), max(0, int((oymin/1000)*h)-10)
                            ox1, oy1 = min(w, int((oxmax/1000)*w)+10), min(h, int((oymax/1000)*h)+10)
                            draw.rectangle([ox0, oy0, ox1, oy1], fill="white")
                        
                        filename = f"theory_{item_count+1}_p{page_num}.png"
                        filepath = os.path.join(out_book_dir, "theory", filename)
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        theory_img.save(filepath)
                        item_count += 1
                    else:
                        for idx, tbox in enumerate(theory_boxes):
                            tymin, txmin, tymax, txmax = tbox
                            tx0, ty0 = max(0, int((txmin/1000)*w)-5), max(0, int((tymin/1000)*h)-5)
                            tx1, ty1 = min(w, int((txmax/1000)*w)+5), min(h, int((tymax/1000)*h)+5)
                            if (tx1-tx0) < 100 or (ty1-ty0) < 50: continue
                            
                            theory_crop = im.crop((tx0, ty0, tx1, ty1))
                            filename = f"theory_{item_count+1}_p{page_num}.png"
                            filepath = os.path.join(out_book_dir, "theory", filename)
                            os.makedirs(os.path.dirname(filepath), exist_ok=True)
                            theory_crop.save(filepath)
                            item_count += 1
                    
                update_status("✅ Page Done", book_id, page_num, item_count)
                
                # SAVE PROGRESS AFTER EVERY PAGE
                prog[book_id] = page_num + 1
                json.dump(prog, open(PROGRESS_FILE, "w"), indent=2)
                
                time.sleep(1) 
                
        # Mark as completely done
        prog[book_id] = -1
        json.dump(prog, open(PROGRESS_FILE, "w"), indent=2)
        print(f"✅ Book finished: {book_id}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_pdf(sys.argv[1])
