import os, sys, json, re, base64, time, fcntl
import pdfplumber
import requests
from PIL import Image
import ai_client

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "practice_bits")
STATUS_FILE = os.path.join(BASE, "data", "agent_status.json")
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

def ask_ai_multi_agent(img_b64, book_name, page_num):
    prompt = """
    You are a team of 5 expert AI agents analyzing this JEE textbook image (2 pages merged vertically).
    
    AGENT 1 (The Boss): Ignore all Theory, Examples, and Illustrations. Only identify pages containing "Exercises", "Level 1", "Level 2", "Bits", or "Problems". If none exist, return {"extract": false}.
    
    AGENT 2 (The Classifier): For every Exercise question, filter out questions that cannot be answered via Options (A,B,C,D) or Numerical input. Ignore purely theoretical questions.
    
    AGENT 3 (The Bounder): Draw a tight bounding box around the question, its options, and any diagrams. Draw a separate box for its solution if visible. If a question starts at the bottom of page 1 and continues to page 2, draw ONE tall box that covers both halves (do not split it).
    
    AGENT 4 (The Reviewer): Review all boxes. Ensure options are not cut off. Ensure no overlapping boxes (Q1 box shouldn't include Q2). Ensure no questions were skipped. Adjust coordinates if necessary.
    
    AGENT 5 (The Finalizer): Assign the exact Chapter Name and Question Number to each box. Output the final JSON.
    
    Return ONLY valid JSON:
    {
      "extract": true,
      "chapter_name": "Straight Lines",
      "questions": [
        {"q_num": 1, "box": [ymin, xmin, ymax, xmax]}
      ],
      "solutions": [
        {"q_num": 1, "box": [ymin, xmin, ymax, xmax]}
      ]
    }
    Boxes must be normalized 0-1000 relative to the ENTIRE merged image.
    """
    
    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    groq_keys = getattr(ai_client, "GROQ_KEYS", [])
    keys = gemini_keys + groq_keys
    
    # Deep Thinking Models Only (No Flash)
    gemini_model = "gemini-1.5-pro" 
    groq_model = "llama-3.2-90b-vision-preview"
    
    while True:
        for k_idx, key in enumerate(keys):
            update_status(f"🧠 Agent Pipeline K{k_idx+1}", book_name, page_num)
            
            if k_idx < len(gemini_keys):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
                headers = {"Content-Type": "application/json"}
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {
                    "model": groq_model,
                    "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
                    "temperature": 0.1, "response_format": {"type": "json_object"}
                }
                
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=30)
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
                
        update_status(f"⏳ Keys Exhausted. Wait 5s", book_name, page_num)
        time.sleep(5)

def process_pdf(pdf_path):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")[:30]
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    
    q_dir = os.path.join(out_book_dir, "questions")
    s_dir = os.path.join(out_book_dir, "solutions")
    os.makedirs(q_dir, exist_ok=True)
    os.makedirs(s_dir, exist_ok=True)
    
    # Resume logic (Page based)
    prog_file = os.path.join(out_book_dir, "progress.json")
    prog = {}
    if os.path.exists(prog_file):
        try: prog = json.load(open(prog_file))
        except: pass
        
    start_page = prog.get("page", 1)
    if start_page == -1:
        print(f"⏭️ Skipping: {book_id} (Already fully extracted)")
        return
        
    print(f"\n📖 Extracting: {book_id} from Page {start_page}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf_obj:
            total_pages = len(pdf_obj.pages)
            
            # Process 2 pages at a time
            for page_num in range(start_page, total_pages + 1, 2):
                page1_num = page_num
                page2_num = min(page_num + 1, total_pages)
                
                print(f"  👁️ Merging Pages {page1_num} & {page2_num}...")
                
                # Render Page 1
                p1 = pdf_obj.pages[page1_num - 1]
                img1 = p1.to_image(resolution=120).original
                
                # Render Page 2
                if page2_num <= total_pages:
                    p2 = pdf_obj.pages[page2_num - 1]
                    img2 = p2.to_image(resolution=120).original
                else:
                    img2 = None
                    
                # Merge Vertically
                if img2:
                    w = max(img1.width, img2.width)
                    h = img1.height + img2.height
                    merged_img = Image.new('RGB', (w, h), 'white')
                    merged_img.paste(img1, (0, 0))
                    merged_img.paste(img2, (0, img1.height))
                else:
                    merged_img = img1
                    
                merged_img.thumbnail((1200, 2000)) # Keep it safe for API
                w, h = merged_img.size
                
                temp_img = "temp_merged.jpg"
                merged_img.save(temp_img, "JPEG", quality=85)
                
                with open(temp_img, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')
                    
                result = ask_ai_multi_agent(img_b64, book_id, f"{page1_num}-{page2_num}")
                
                if not result or not result.get("extract", False):
                    print("    ⏭️ Skipped (No Exercises/Answers found by Boss Agent).")
                    prog["page"] = page2_num + 1
                    json.dump(prog, open(prog_file, "w"), indent=2)
                    continue
                    
                chapter_name = result.get("chapter_name", "Chapter").replace(" ", "_")
                print(f"    🎯 Found Content for Chapter: {chapter_name}")
                
                # Crop Questions
                for q in result.get("questions", []):
                    qnum = q.get("q_num", 0)
                    box = q.get("box", [])
                    if len(box) != 4: continue
                    
                    ymin, xmin, ymax, xmax = box
                    x0 = max(0, int((xmin/1000)*w) - 10)
                    y0 = max(0, int((ymin/1000)*h) - 10)
                    x1 = min(w, int((xmax/1000)*w) + 10)
                    y1 = min(h, int((ymax/1000)*h) + 10)
                    
                    if (x1-x0) < 50 or (y1-y0) < 30: continue
                    
                    crop = merged_img.crop((x0, y0, x1, y1))
                    filename = f"{chapter_name}_Q{qnum}.png"
                    crop.save(os.path.join(q_dir, filename))
                    print(f"    ✂️ Saved {filename}")

                # Crop Solutions
                for s in result.get("solutions", []):
                    snum = s.get("q_num", 0)
                    box = s.get("box", [])
                    if len(box) != 4: continue
                    
                    ymin, xmin, ymax, xmax = box
                    x0 = max(0, int((xmin/1000)*w) - 10)
                    y0 = max(0, int((ymin/1000)*h) - 10)
                    x1 = min(w, int((xmax/1000)*w) + 10)
                    y1 = min(h, int((ymax/1000)*h) + 10)
                    
                    if (x1-x0) < 50 or (y1-y0) < 30: continue
                    
                    crop = merged_img.crop((x0, y0, x1, y1))
                    filename = f"{chapter_name}_Sol_{snum}.png"
                    crop.save(os.path.join(s_dir, filename))
                    print(f"    ✂️ Saved {filename}")

                # Save progress (skip 2 pages ahead)
                prog["page"] = page2_num + 1
                json.dump(prog, open(prog_file, "w"), indent=2)
                time.sleep(2) # Brief pause between pairs
                
        prog["page"] = -1
        json.dump(prog, open(prog_file, "w"), indent=2)
        print(f"✅ Book finished: {book_id}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_pdf(sys.argv[1])
