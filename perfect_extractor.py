import os, subprocess, json, re
from PIL import Image

BASE_DIR = os.getcwd()
PDF_PRACTICE = os.path.join(BASE_DIR, "pyq_pdfs", "jee_main", "practice")
IMG_PRACTICE = os.path.join(BASE_DIR, "pyq_images", "jee_main", "practice")
DB_FILE = os.path.join(BASE_DIR, "data", "pyq_master.json")

MIN_YEAR = 2016 

master_db = {"practice": {}, "papers": {}}
if os.path.exists(DB_FILE):
    try:
        loaded = json.load(open(DB_FILE))
        if "practice" in loaded: master_db["practice"] = loaded["practice"]
        if "papers" in loaded: master_db["papers"] = loaded["papers"]
    except: pass

def get_fingerprint(text):
    text = re.sub(r'JEE Main \d{4}.*?Shift', '', text, flags=re.IGNORECASE)
    clean = re.sub(r'[^a-z\s]', ' ', text.lower())
    words = [w for w in clean.split() if len(w) > 3]
    stop = {'find', 'calculate', 'value', 'given', 'figure', 'shown', 'system', 
            'which', 'following', 'correct', 'mass', 'block', 'particle', 'body', 
            'what', 'will', 'with', 'from', 'that', 'this', 'then', 'ratio', 'minimum', 
            'maximum', 'total', 'equal', 'point', 'surface', 'respect'}
    core = [w for w in words if w not in stop]
    return "_".join(sorted(list(set(core[:5]))))

print("🚀 Starting FAST PERFECT Extraction (Page by Page)...")

for subj in os.listdir(PDF_PRACTICE):
    subj_dir = os.path.join(PDF_PRACTICE, subj)
    if not os.path.isdir(subj_dir): continue
    if subj not in master_db["practice"]: master_db["practice"][subj] = {}

    for pdf in os.listdir(subj_dir):
        if not pdf.lower().endswith(".pdf"): continue
        chapter_name = pdf.replace("JEE Main ", "").replace(" Previous Year Questions with Answer Key.pdf", "").replace(".pdf", "").strip()
        
        if chapter_name in master_db["practice"][subj] and len(master_db["practice"][subj][chapter_name].get("priority", [])) > 0:
            print(f"⏩ Skipping (Already done): {chapter_name}")
            continue
            
        pdf_path = os.path.join(subj_dir, pdf)
        print(f"\n📄 Scanning: {subj} / {chapter_name}")
        
        try:
            info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout
            total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
            print(f"   (Total Pages: {total_pages})")
        except: continue
            
        # 1. Get all text and answers first
        full_text = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
        ak_start = full_text.rfind("Answer Key")
        answers = {}
        if ak_start != -1:
            ak_text = full_text[ak_start:]
            mcq = re.findall(r'(\d+)\.\s*([A-D])\b', ak_text)
            for q, a in mcq: answers[int(q)] = {"type": "mcq", "correct_index": ord(a) - 65}

        # Map question text to numbers
        q_texts = {}
        for block in re.split(r'(?=Q\d+\.)', full_text):
            match = re.match(r'Q(\d+)\.', block)
            if match:
                q_texts[int(match.group(1))] = re.sub(r'\s+', ' ', block[:800]).strip()

        out_dir = os.path.join(IMG_PRACTICE, subj, chapter_name.replace(" ", "_"))
        os.makedirs(out_dir, exist_ok=True)
        
        priority_qs = []
        normal_qs = []
        seen_models = set()
        
        # 2. Loop PAGE BY PAGE (Renders each page only ONCE)
        for page in range(1, total_pages + 1):
            img_base = os.path.join(out_dir, f"tmp_page_{page}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], check=True, stdout=subprocess.DEVNULL)
            
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            img = Image.open(img_path)
            w, h = img.size
            
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
            q_matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q(\d+)\.</word>', xml)
            foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
            foot_y = float(foot.group(1)) if foot else 1000 
            scale = 150.0 / 72.0
            
            for i, (y_str, q_num) in enumerate(q_matches):
                q_num = int(q_num)
                if q_num not in q_texts: continue
                q_text = q_texts[q_num]
                
                year_match = re.search(r'(20[2-9]\d)', q_text[:200])
                year = int(year_match.group(1)) if year_match else 0
                if year != 0 and year < MIN_YEAR: continue # Skip old
                
                y_min = float(y_str)
                y_max = float(q_matches[i+1][0]) if i+1 < len(q_matches) else foot_y - 10
                
                crop_top = max(0, (y_min * scale) - 20)
                crop_bottom = min(h, (y_max * scale))
                
                if crop_bottom <= crop_top: continue
                
                q_filename = os.path.join(out_dir, f"q{q_num}.png")
                img.crop((0, int(crop_top), w, int(crop_bottom))).save(q_filename)
                
                q_len = len(q_text)
                diff_num = 8 if q_len > 350 else (5 if q_len < 150 else 6) 
                ideal = 120 if diff_num == 8 else (60 if diff_num == 5 else 90)
                ans_data = answers.get(q_num, {"type": "mcq", "correct_index": -1})
                
                q_obj = {
                    "q_num": q_num,
                    "type": ans_data["type"],
                    "correct_index": ans_data.get("correct_index", -1),
                    "ideal_time": ideal,
                    "difficulty": diff_num,
                    "source": f"JEE Main {year}" if year > 0 else "JEE Main",
                    "subtopic": chapter_name,
                    "explanation": "💡 (Click 'Doubt in Explanation' to generate 5-part AI solution)",
                    "img": q_filename
                }
                
                fingerprint = get_fingerprint(q_text)
                if fingerprint not in seen_models:
                    seen_models.add(fingerprint)
                    priority_qs.append(q_obj)
                else:
                    normal_qs.append(q_obj)
                    
            os.remove(img_path) # Delete temp page
            print(f"   Scanned page {page}/{total_pages}...", end="\r")

        if priority_qs or normal_qs:
            master_db["practice"][subj][chapter_name] = {
                "priority": priority_qs,
                "normal": normal_qs
            }
            tmp = DB_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(master_db, f, indent=2)
            import os as _os
            _os.replace(tmp, DB_FILE)
            print(f"\n✅ {subj} / {chapter_name}: {len(priority_qs)} Priority, {len(normal_qs)} Normal (Saved)")
        else:
            print(f"\n⚠️ {subj} / {chapter_name}: No questions found.")

print(f"\n🎉 ALL DONE! Saved perfect DB to {DB_FILE}")
