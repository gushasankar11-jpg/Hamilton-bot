#!/usr/bin/env python3
import os, sys, json, re, base64, time, argparse, traceback
from datetime import datetime

# ---------- 1. DEPENDENCY CHECK ----------
try:
    import pdfplumber, requests
    from PIL import Image
except ImportError as e:
    print(f"❌ Missing package: {e}")
    sys.exit(1)

# Load your existing 8-key rotator!
try:
    import ai_client
    KEYS = getattr(ai_client, "GEMINI_KEYS", [])
except ImportError:
    KEYS = []

if not KEYS:
    print("❌ Could not load GEMINI_KEYS from ai_client.py")
    sys.exit(1)

# ---------- 2. PATHS ----------
BASE       = os.getcwd()
# EXACT FOLDER WHERE YOUR BOOKS ARE:
BOOKS_DIR  = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books")

# Output folders (New folders, won't overwrite old stuff)
OUT_ROOT   = os.path.join(BASE, "data", "extracted_books_v3")
IMG_ROOT   = os.path.join(BASE, "pyq_images", "extracted_books_v3")
RUN_LOG    = os.path.join(OUT_ROOT, "_run.log")

os.makedirs(OUT_ROOT, exist_ok=True)
os.makedirs(IMG_ROOT, exist_ok=True)

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with open(RUN_LOG, "a") as f: f.write(line + "\n")
    print(line, flush=True)

# ---------- 3. AI CALL ----------
PROMPT = """Analyze this textbook page. Detect every distinct content block.
Classify each block as exactly one of:
  "theory"       - definitions, formulas, conceptual explanations
  "illustration" - a worked example WITH its solution shown inline
  "exercise"     - an MCQ, numerical, or subjective question with NO solution
  "solution"     - answer key or step-by-step solution block
Skip headers, footers, page numbers. DO NOT skip any question.
Return ONLY JSON: {"blocks":[{"category":"exercise","box":[ymin,xmin,ymax,xmax]}]}
Box is 0-1000, top-left origin."""

def call_gemini(img_b64):
    if not KEYS: return None
    tpl = ("https://generativelanguage.googleapis.com/v1beta/"
           "models/gemini-3.1-flash-lite:generateContent?key={k}")
    payload = {"contents": [{"parts": [
        {"text": PROMPT},
        {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}
    ]}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
    
    for key in KEYS:
        for attempt in range(2):
            try:
                r = requests.post(tpl.format(k=key), headers={"Content-Type": "application/json"}, json=payload, timeout=30)
                d = r.json()
                if "error" in d:
                    log(f"    Key err: {d['error'].get('message','?')[:50]}")
                    break
                raw = d["candidates"][0]["content"]["parts"][0]["text"]
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m: return json.loads(m.group(0))
            except Exception as e:
                time.sleep(1)
    return None

# ---------- 4. CROPPING ----------
CATS = ("theory", "illustration", "exercise", "solution")

def crop(im, blocks, out_dir, prefix):
    w, h = im.size
    saved = []
    for i, b in enumerate(blocks):
        cat = b.get("category"); box = b.get("box", [])
        if cat not in CATS or len(box) != 4: continue
        try:
            ymin, xmin, ymax, xmax = [int(x) for x in box]
        except: continue
        
        # Add 5px padding to avoid cutting text
        x0 = max(0, int((xmin/1000)*w) - 5); y0 = max(0, int((ymin/1000)*h) - 5)
        x1 = min(w, int((xmax/1000)*w) + 5); y1 = min(h, int((ymax/1000)*h) + 5)
        
        if x1-x0 < 20 or y1-y0 < 20: continue
        
        p = os.path.join(out_dir, f"{prefix}_{cat}_{i:02d}.png")
        im.crop((x0, y0, x1, y1)).save(p)
        saved.append({"category": cat, "img": p})
    return saved

# ---------- 5. PROCESS BOOK ----------
def process_book(pdf_path, subj, publisher):
    name = os.path.basename(pdf_path)
    pid  = re.sub(r"[^\w.-]", "_", name.replace(".pdf", ""))
    out_json = os.path.join(OUT_ROOT, pid + ".json")
    
    if os.path.exists(out_json):
        log(f"  ⏭️  Skip (done): {name}")
        return True
        
    img_dir = os.path.join(IMG_ROOT, pid)
    os.makedirs(img_dir, exist_ok=True)
    log(f"📚 Processing: {name}")
    buckets = {c: [] for c in CATS}
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
            # NO SKIPPING. Scan every single page.
            for pn in range(total_pages):
                page = pdf.pages[pn]
                try:
                    im = page.to_image(resolution=120).original
                    im.thumbnail((1024, 1024))
                    tmp = os.path.join(OUT_ROOT, "_tmp.jpg")
                    im.save(tmp, "JPEG", quality=85)
                    with open(tmp, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                        
                    res = call_gemini(b64)
                    if not res:
                        log(f"    pg {pn+1}/{total_pages}: No result")
                        continue
                        
                    blocks = res.get("blocks", [])
                    for s in crop(im, blocks, img_dir, f"p{pn+1:02d}"):
                        s["page"] = pn+1; s["source"] = name
                        buckets[s["category"]].append(s)
                        
                    log(f"    pg {pn+1}/{total_pages}: {len(blocks)} blocks found")
                    
                except Exception as e:
                    log(f"    pg {pn+1} error: {e}")
                    
    except Exception as e:
        log(f"  ❌ PDF Fail: {e}")
        return False

    total = sum(len(v) for v in buckets.values())
    if total == 0:
        log(f"  ⚠️  0 blocks found.")
        return False

    year = re.search(r"20\d\d", name)
    data = {
        "source": name, "subject": subj, "publisher": publisher,
        "extracted_at": datetime.now().isoformat(),
        "theory": buckets["theory"], "illustrations": buckets["illustration"],
        "exercises": buckets["exercise"], "solutions": buckets["solution"],
        "counts": {c: len(buckets[c]) for c in CATS},
    }
    with open(out_json, "w") as f: json.dump(data, f, indent=2)
    log(f"  ✅ Saved {pid}.json — Ex={len(buckets['exercise'])}, Sol={len(buckets['solution'])}")
    return True

# ---------- 6. MAIN ----------
def main():
    print(f"🔍 Searching for books in: {BOOKS_DIR}")
    
    # Find all PDFs recursively
    all_books = []
    for root, dirs, files in os.walk(BOOKS_DIR):
        for f in files:
            if f.lower().endswith(".pdf"):
                # Extract subject and publisher from the folder path
                parts = root.split("/")
                subj = parts[-2] if len(parts) > 1 else "Unknown"
                pub = parts[-1] if len(parts) > 0 else "Unknown"
                all_books.append((os.path.join(root, f), subj, pub))
                
    if not all_books:
        print("❌ No PDFs found in the books folder!")
        return
        
    print(f"✅ Found {len(all_books)} books.")
    
    ok = fail = 0
    for pdf, subj, pub in all_books:
        try:
            if process_book(pdf, subj, pub): ok += 1
            else: fail += 1
        except Exception:
            fail += 1
            log(f"  ❌ Crash: {traceback.format_exc()}")

    print(f"\n=== SUMMARY ===\n  OK: {ok} | FAIL: {fail}")
    print(f"  JSON output : {OUT_ROOT}")
    print(f"  Images      : {IMG_ROOT}")

if __name__ == "__main__":
    main()
