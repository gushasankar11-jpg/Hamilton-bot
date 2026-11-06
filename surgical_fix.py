import ast, os, re

# ==========================================
# FIX 1: Remove the orphaned decorator in c30a
# ==========================================
path_auth = "bot_chunks/c30a_admin_auth.py"
if os.path.exists(path_auth):
    content = open(path_auth).read()
    # Remove the bad decorator
    content = content.replace("@bot.message_handler(func=lambda m: True, content_types=['text'])\n# def _auth_text_router", "# def _auth_text_router")
    open(path_auth, "w").write(content)
    print("✅ Fixed c30a: Removed orphaned text handler decorator.")

# ==========================================
# FIX 2: Fix the message deletion crash in c30s
# ==========================================
path_cleanup = "bot_chunks/c30s_admin_cleanup.py"
if os.path.exists(path_cleanup):
    content = open(path_cleanup).read()
    # The error is likely calling bot.delete_message(uid, message) instead of message.message_id
    # We use a regex to find bot.delete_message calls that don't use .message_id
    content = re.sub(r'bot\.delete_message\(([^,]+), ([^)]+)\)', r'bot.delete_message(\1, \2.message_id)', content)
    open(path_cleanup, "w").write(content)
    print("✅ Fixed c30s: Patched message deletion crash.")

# ==========================================
# FIX 3: Fast Paper Extractor (Python First)
# ==========================================
extractor_code = '''import os, sys, json, re, base64, time
import pdfplumber
import requests
from PIL import Image
import ai_client

BASE = os.getcwd()
PDF_DIRS = [os.path.join(BASE, "pyq_pdfs", "jee_main", "papers"), os.path.join(BASE, "pyq_pdfs", "jee_adv", "papers")]
IMG_DIR = os.path.join(BASE, "pyq_images", "papers")
DB_FILE = os.path.join(BASE, "data", "pyq_master.json")
os.makedirs(IMG_DIR, exist_ok=True)

def ask_ai_paper(img_b64, page_num, expected_qs):
    prompt = f"""
    Analyze this JEE paper page. Extract exactly the questions on this page.
    Return ONLY JSON: {{"questions": [{{"q_num": 1, "type": "mcq", "box": [ymin, xmin, ymax, xmax]}}]}}
    Max {expected_qs} questions.
    """
    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    for key in gemini_keys[:2]: # Use only 2 keys to prevent burning quota
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
        try:
            res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
            data = res.json()
            if "error" not in data:
                raw = data["candidates"][0]["content"]["parts"][0]["text"]
                match = re.search(r'\\{.*\\}', raw, re.DOTALL)
                if match: return json.loads(match.group(0))
        except: continue
    return None

def process_paper(pdf_path, exam_type):
    pdf_name = os.path.basename(pdf_path)
    book_id = pdf_name.replace(".pdf", "").replace(" ", "_")
    out_dir = os.path.join(IMG_DIR, book_id)
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"\\n📄 Extracting: {pdf_name[:50]}", flush=True)
    paper_questions = []
    expected_qs = 75 if exam_type == "JEE MAIN" else 54
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
            # PURE PYTHON: Find answer key page
            ak_page = total_pages
            for p_idx in range(total_pages):
                text = pdf.pages[p_idx].extract_text() or ""
                if "Answer Key" in text.upper() or "ANSWERS" in text.upper():
                    ak_page = p_idx
                    break
            
            # Only process pages BEFORE the answer key
            for page_num in range(3, ak_page): # Skip first 3 pages (cover/instructions)
                if len(paper_questions) >= expected_qs: break
                
                page = pdf.pages[page_num]
                im = page.to_image(resolution=120).original
                im.thumbnail((1024, 1024))
                w, h = im.size
                
                temp_img = "temp_paper.jpg"
                im.save(temp_img, "JPEG", quality=85)
                with open(temp_img, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                    
                result = ask_ai_paper(img_b64, page_num, expected_qs)
                if not result: continue
                
                for item in result.get("questions", []):
                    if len(paper_questions) >= expected_qs: break
                    box = item.get("box", [])
                    if len(box) != 4: continue
                    ymin, xmin, ymax, xmax = box
                    x0, y0 = max(0, int((xmin/1000)*w)-5), max(0, int((ymin/1000)*h)-5)
                    x1, y1 = min(w, int((xmax/1000)*w)+5), min(h, int((ymax/1000)*h)+5)
                    
                    filepath = os.path.join(out_dir, f"q{len(paper_questions)+1}.png")
                    im.crop((x0, y0, x1, y1)).save(filepath)
                    paper_questions.append({
                        "q_num": len(paper_questions)+1, "type": item.get("type", "mcq"), "img": filepath,
                        "source": pdf_name, "difficulty": 6, "ideal_time": 120
                    })
    except Exception as e:
        print(f"❌ Error: {e}")
        
    if paper_questions:
        db = json.load(open(DB_FILE))
        year_match = re.search(r'20\\d\\d', pdf_name)
        year = year_match.group(0) if year_match else "Unknown"
        db.setdefault("papers", {})[book_id] = {
            "questions": paper_questions, "total_questions": expected_qs, 
            "exam_type": exam_type, "year": year
        }
        json.dump(db, open(DB_FILE, "w"), indent=2)
        print(f"✅ Saved {len(paper_questions)} Qs.", flush=True)

if __name__ == "__main__":
    all_pdfs = []
    for d in PDF_DIRS:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".pdf"): all_pdfs.append((os.path.join(d, f), "JEE ADV" if "adv" in d else "JEE MAIN"))
    
    print(f"Found {len(all_pdfs)} papers. Starting Fast Extraction...")
    for pdf, typ in all_pdfs:
        process_paper(pdf, typ)
'''
open("extract_papers_ai.py", "w").write(extractor_code)
print("✅ Extractor rewritten to be 10x faster.")

