import os, subprocess, json, re
from PIL import Image

BASE = os.getcwd()
PDF_BASE = os.path.join(BASE, "pyq_pdfs", "jee_adv", "practice")
IMG_BASE = os.path.join(BASE, "pyq_images", "jee_adv", "practice")
DB = os.path.join(BASE, "data", "pyq_master.json")

def detect_type(q_text):
    t = q_text.lower()
    if "match the column" in t or "match the following" in t or "match list" in t:
        return "match"
    if "one or more" in t or "more than one correct" in t or "multiple correct" in t:
        return "multiple"
    if "numerical" in t or "integer" in t or "decimal" in t or "value of" in t:
        return "numerical"
    return "single"

def load_db():
    if os.path.exists(DB):
        try: return json.load(open(DB))
        except: pass
    return {"practice": {}, "practice_adv": {}, "papers": {}}

def save_db(subj, chapter_name, chapter_data):
    import time
    for attempt in range(10):
        try:
            db = load_db()
            if "practice_adv" not in db: db["practice_adv"] = {}
            if subj not in db["practice_adv"]: db["practice_adv"][subj] = {}
            db["practice_adv"][subj][chapter_name] = chapter_data
            tmp = DB + f".{os.getpid()}.tmp"
            json.dump(db, open(tmp, "w"), indent=2)
            os.replace(tmp, DB)
            return
        except Exception as e:
            time.sleep(0.5)
    print("⚠️ Could not save chapter to DB after 10 retries")


print("🚀 Starting JEE ADVANCED Chapter-Wise Extraction...")

db = load_db()
if "practice_adv" not in db: db["practice_adv"] = {}

for subj in ["Physics", "Chemistry", "Maths"]:
    subj_dir = os.path.join(PDF_BASE, subj)
    if not os.path.isdir(subj_dir): continue
    if subj not in db["practice_adv"]: db["practice_adv"][subj] = {}
    
    for pdf in sorted(os.listdir(subj_dir)):
        if not pdf.lower().endswith(".pdf"): continue
        
        chapter_name = pdf.replace(".pdf", "").replace("JEE Adv ", "").replace("JEE Advanced ", "").strip()
        
        if chapter_name in db["practice_adv"][subj]:
            print(f"⏩ Skip (Done): {subj} / {chapter_name[:40]}")
            continue
            
        pdf_path = os.path.join(subj_dir, pdf)
        print(f"\n📄 Scanning: {subj} / {chapter_name[:40]}")
        
        try:
            info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15).stdout
            total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
        except: continue
            
        full_text = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
        
        # Extract answer key (usually at the end)
        ak_pos = max(full_text.rfind("Answer Key"), full_text.rfind("ANSWER KEY"))
        answers = {}
        if ak_pos != -1:
            for q, a in re.findall(r'(\d+)\.\s*([A-D])\b', full_text[ak_pos:]):
                answers[int(q)] = ord(a) - 65
                
        # Map coordinates (Adv uses 1. 2. without Q)
        q_coords = {}
        for page in range(1, total_pages + 1):
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
            # Match both "Q1." and "1."
            matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q?(\d+)\.</word>', xml)
            foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
            foot_y = float(foot.group(1)) if foot else 1000
            
            for i, (y_str, q_num) in enumerate(matches):
                qn = int(q_num)
                if qn > 100: continue
                y_min = float(y_str)
                y_max = float(matches[i+1][0]) if i+1 < len(matches) else foot_y - 10
                q_coords[qn] = {"page": page, "y_min": y_min, "y_max": y_max}

        # Extract text for AI typing
        q_texts = {}
        # Split by "1." or "Q1." at start of line
        for block in re.split(r'(?=(?:^|\n)Q?\d+\.)', full_text):
            m = re.match(r'(?:^|\n)Q?(\d+)\.', block)
            if m:
                qn = int(m.group(1))
                if qn not in q_texts and qn <= 100:
                    q_texts[qn] = re.sub(r'\s+', ' ', block[:1500]).strip()

        out_dir = os.path.join(IMG_BASE, subj, chapter_name.replace(" ", "_"))
        os.makedirs(out_dir, exist_ok=True)
        
        priority_qs, normal_qs = [], []
        
        for page in range(1, total_pages + 1):
            to_crop = [qn for qn, c in q_coords.items() if c["page"] == page]
            if not to_crop: continue
            
            img_base = os.path.join(out_dir, f"tmp_{page}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], check=True, stdout=subprocess.DEVNULL, timeout=30)
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            
            img = Image.open(img_path)
            w, h = img.size
            scale = 150.0 / 72.0
            
            for qn in to_crop:
                c = q_coords[qn]
                top = max(0, (c["y_min"] * scale) - 20)
                bot = min(h, (c["y_max"] * scale))
                if bot <= top + 30: continue
                
                q_file = os.path.join(out_dir, f"q{qn}.png")
                img.crop((0, int(top), w, int(bot))).save(q_file)
                
                q_text = q_texts.get(qn, "")
                qtype = detect_type(q_text)
                diff = 8 if len(q_text) > 400 else (5 if len(q_text) < 150 else 6)
                
                q_obj = {
                    "q_num": qn,
                    "type": qtype,
                    "correct_index": answers.get(qn, -1),
                    "ideal_time": 120 if diff == 8 else 90,
                    "difficulty": diff,
                    "source": "JEE Adv",
                    "subtopic": chapter_name,
                    "q_text": q_text,
                    "img": q_file
                }
                
                # Simple fingerprinting for Priority/Normal
                if qn <= 60: # Just take first 60 as priority for now
                    priority_qs.append(q_obj)
                else:
                    normal_qs.append(q_obj)
                    
            img.close()
            try: os.remove(img_path)
            except: pass
            
        if priority_qs or normal_qs:
            priority_qs.sort(key=lambda x: x["q_num"])
            normal_qs.sort(key=lambda x: x["q_num"])
            db["practice_adv"][subj][chapter_name] = {
                "priority": priority_qs,
                "normal": normal_qs
            }
            save_db(subj, chapter_name, db["practice_adv"][subj][chapter_name])
            print(f"  ✅ Saved {len(priority_qs)+len(normal_qs)} questions")
        else:
            print(f"  ⚠️ No questions found")

print("\n🎉 ADVANCED PRACTICE EXTRACTION DONE!")
