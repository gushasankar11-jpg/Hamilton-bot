import os, sys, json, re, base64, time, fcntl, traceback
import pdfplumber
import requests
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import ai_client

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "practice_bits")
STATE_FILE = os.path.join(BASE, "data", "company_state.json")
BOOKS_DIR = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

# --- COMPANY STATE MANAGEMENT ---
def update_state(role, worker_id, status, book="-", page=0, pages_done=0, error_msg=""):
    with open(STATE_FILE + ".lock", "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        data = {}
        if os.path.exists(STATE_FILE):
            try: data = json.load(open(STATE_FILE))
            except: pass
        
        if role not in data: data[role] = {}
        data[role][str(worker_id)] = {
            "status": status, "book": book, "page": page, 
            "pages_done": pages_done, "error": error_msg,
            "updated": time.strftime("%H:%M:%S")
        }
        tmp = STATE_FILE + ".tmp"
        json.dump(data, open(tmp, "w"), indent=2)
        os.replace(tmp, STATE_FILE)
        fcntl.flock(lockfile, fcntl.LOCK_UN)

def log_worker(worker_id, msg):
    with open(f"data/worker_logs/W{worker_id}.log", "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

# --- MANAGER (Error Handling & API Routing) ---
def manager_api_call(img_b64, worker_id):
    prompt = """
    You are a team of 5 expert AI agents analyzing this JEE textbook image (2 pages merged).
    AGENT 1: Ignore all Theory/Examples. Only find Exercises, Level 1/2/3, Bits.
    AGENT 2: Filter out theoretical questions. Only MCQ (A,B,C,D) or Numerical.
    AGENT 3: Draw tight bounding boxes. If question spans page break, draw ONE tall box.
    AGENT 4: Review boxes for cut-offs or overlaps.
    AGENT 5: Finalize and assign Chapter Name.
    Return ONLY JSON: {"extract": true, "chapter_name": "Name", "questions": [{"q_num": 1, "box": [ymin, xmin, ymax, xmax]}], "solutions": [{"q_num": 1, "box": [...]}]}
    """
    
    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    groq_keys = getattr(ai_client, "GROQ_KEYS", [])
    keys = gemini_keys + groq_keys
    
    # Latest Deep Thinking Models
    gemini_models = ["gemini-2.5-pro", "gemini-3.5-pro"]
    groq_model = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    while True:
        for k_idx, key in enumerate(keys):
            update_state("Manager", 1, f"Routing K{k_idx+1}", error_msg="")
            
            if k_idx < len(gemini_keys):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_models[0]}:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
                headers = {"Content-Type": "application/json"}
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {"model": groq_model, "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}], "temperature": 0.1, "response_format": {"type": "json_object"}}
                
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=45)
                data = res.json()
                
                if "error" not in data:
                    if k_idx < len(gemini_keys):
                        raw = data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        raw = data["choices"][0]["message"]["content"]
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    if match: return json.loads(match.group(0))
                else:
                    err = data["error"]["message"]
                    log_worker(worker_id, f"Manager diagnosed: {err}")
                    update_state("Manager", 1, "Diagnosing Error", error_msg=err[:50])
                    
                    if "429" in err or "quota" in err.lower():
                        time.sleep(15)
                    elif "not found" in err.lower() or "404" in err:
                        if k_idx < len(gemini_keys) and len(gemini_models) > 1:
                            gemini_models.pop(0) # Switch model
            except Exception as e:
                log_worker(worker_id, f"Network error: {e}")
                time.sleep(5)
                
        update_state("Manager", 1, "All Keys Exhausted. Boss notified.", error_msg="Waiting for keys to reset")
        time.sleep(30) # Boss ensures we wait and try again

# --- WORKER (Extraction) ---
def worker_process(worker_id, pdf_path):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")[:25]
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    
    q_dir = os.path.join(out_book_dir, "questions")
    s_dir = os.path.join(out_book_dir, "solutions")
    os.makedirs(q_dir, exist_ok=True)
    os.makedirs(s_dir, exist_ok=True)
    
    prog_file = os.path.join(out_book_dir, "progress.json")
    prog = {"page": 1}
    if os.path.exists(prog_file):
        try: prog = json.load(open(prog_file))
        except: pass
        
    start_page = prog.get("page", 1)
    if start_page == -1:
        update_state("Worker", worker_id, "✅ Done", book_id)
        return
        
    log_worker(worker_id, f"Assigned to {book_id} starting at Page {start_page}")
    update_state("Worker", worker_id, "Starting", book_id, start_page, start_page)
    
    try:
        with pdfplumber.open(pdf_path) as pdf_obj:
            total_pages = len(pdf_obj.pages)
            
            # Process 2 pages at a time
            for page_num in range(start_page, total_pages + 1, 2):
                page1 = page_num
                page2 = min(page_num + 1, total_pages)
                
                update_state("Worker", worker_id, f"Cropping Pg {page1}-{page2}", book_id, page_num, page_num)
                log_worker(worker_id, f"Processing {page1}-{page2}...")
                
                # Merge 2 pages
                img1 = pdf_obj.pages[page1 - 1].to_image(resolution=120).original
                if page2 <= total_pages:
                    img2 = pdf_obj.pages[page2 - 1].to_image(resolution=120).original
                    w = max(img1.width, img2.width)
                    h = img1.height + img2.height
                    merged = Image.new('RGB', (w, h), 'white')
                    merged.paste(img1, (0, 0))
                    merged.paste(img2, (0, img1.height))
                else:
                    merged = img1
                    
                merged.thumbnail((1200, 2000))
                w, h = merged.size
                
                temp_img = f"temp_{worker_id}.jpg"
                merged.save(temp_img, "JPEG", quality=85)
                with open(temp_img, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')
                    
                result = manager_api_call(img_b64, worker_id)
                
                if result and result.get("extract", False):
                    chapter = result.get("chapter_name", "Chapter").replace(" ", "_")
                    for q in result.get("questions", []):
                        qnum = q.get("q_num", 0)
                        box = q.get("box", [])
                        if len(box) != 4: continue
                        ymin, xmin, ymax, xmax = box
                        x0, y0 = max(0, int((xmin/1000)*w)-10), max(0, int((ymin/1000)*h)-10)
                        x1, y1 = min(w, int((xmax/1000)*w)+10), min(h, int((ymax/1000)*h)+10)
                        if (x1-x0) > 50 and (y1-y0) > 30:
                            merged.crop((x0, y0, x1, y1)).save(os.path.join(q_dir, f"{chapter}_Q{qnum}.png"))
                            
                    for s in result.get("solutions", []):
                        snum = s.get("q_num", 0)
                        box = s.get("box", [])
                        if len(box) != 4: continue
                        ymin, xmin, ymax, xmax = box
                        x0, y0 = max(0, int((xmin/1000)*w)-10), max(0, int((ymin/1000)*h)-10)
                        x1, y1 = min(w, int((xmax/1000)*w)+10), min(h, int((ymax/1000)*h)+10)
                        if (x1-x0) > 50 and (y1-y0) > 30:
                            merged.crop((x0, y0, x1, y1)).save(os.path.join(s_dir, f"{chapter}_Sol_{snum}.png"))
                
                prog["page"] = page2 + 1
                json.dump(prog, open(prog_file, "w"), indent=2)
                time.sleep(2)
                
        prog["page"] = -1
        json.dump(prog, open(prog_file, "w"), indent=2)
        update_state("Worker", worker_id, "✅ Book Done", book_id, total_pages, total_pages)
        
    except Exception as e:
        log_worker(worker_id, f"CRASH: {e}\n{traceback.format_exc()}")
        update_state("Worker", worker_id, "❌ Crashed", book_id, 0, 0, str(e))

# --- BOSS (Orchestrator) ---
def boss_run():
    import glob
    from concurrent.futures import ThreadPoolExecutor
    
    pdfs = glob.glob(f"{BOOKS_DIR}/**/*.pdf", recursive=True)
    # Sort by size (smallest first for quick wins)
    pdfs.sort(key=lambda x: os.path.getsize(x))
    
    update_state("Boss", 1, f"Found {len(pdfs)} books. Delegating...")
    
    def run_task(args):
        worker_id, pdf = args
        while True:
            try:
                worker_process(worker_id, pdf)
                break # Success
            except Exception as e:
                update_state("Boss", 1, f"Restarting W{worker_id} due to crash")
                time.sleep(5) # Boss forces restart at any cost
                
    # Company has 8 Workers
    tasks = [(i + 1, pdf) for i, pdf in enumerate(pdfs)]
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(run_task, tasks)
        
    update_state("Boss", 1, "🎉 ALL WORK COMPLETED. Company shutting down.")

if __name__ == "__main__":
    boss_run()
