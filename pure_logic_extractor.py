import os, subprocess, json, re
from PIL import Image
from collections import defaultdict

BASE_DIR = os.getcwd()
PDF_PRACTICE = os.path.join(BASE_DIR, "pyq_pdfs", "jee_main", "practice")
IMG_PRACTICE = os.path.join(BASE_DIR, "pyq_images", "jee_main", "practice")
DB_FILE = os.path.join(BASE_DIR, "data", "pyq_master.json")

# Only extract questions from the last 10 years
MIN_YEAR = 2016 

master_db = {"practice": {}, "papers": {}}
if os.path.exists(DB_FILE):
    try:
        loaded = json.load(open(DB_FILE))
        if "practice" in loaded: master_db["practice"] = loaded["practice"]
        if "papers" in loaded: master_db["papers"] = loaded["papers"]
    except: pass

def get_fingerprint(text):
    """Extracts the 'Model' of the question using pure Python logic."""
    # Remove JEE Main dates so they don't affect the model detection
    text = re.sub(r'JEE Main \d{4}.*?Shift', '', text, flags=re.IGNORECASE)
    # Keep only letters
    clean = re.sub(r'[^a-z\s]', ' ', text.lower())
    words = [w for w in clean.split() if len(w) > 3]
    
    # Common words that don't define the physics/math model
    stop = {'find', 'calculate', 'value', 'given', 'figure', 'shown', 'system', 
            'which', 'following', 'correct', 'mass', 'block', 'particle', 'body', 
            'what', 'will', 'with', 'from', 'that', 'this', 'then', 'ratio', 'minimum', 
            'maximum', 'total', 'equal', 'point', 'surface', 'respect'}
            
    core = [w for w in words if w not in stop]
    # Return a sorted string of the first 5 unique core words
    return "_".join(sorted(list(set(core[:5]))))

print("🚀 Starting PURE LOGIC Extraction (No API, Last 10 Years)...")

for subj in os.listdir(PDF_PRACTICE):
    subj_dir = os.path.join(PDF_PRACTICE, subj)
    if not os.path.isdir(subj_dir): continue
    if subj not in master_db["practice"]: master_db["practice"][subj] = {}

    for pdf in os.listdir(subj_dir):
        if not pdf.lower().endswith(".pdf"): continue
        chapter_name = pdf.replace("JEE Main ", "").replace(" Previous Year Questions with Answer Key.pdf", "").replace(".pdf", "").strip()
        
        if chapter_name in master_db["practice"][subj]:
            print(f"⏩ Skipping (Already done): {chapter_name}")
            continue
            
        pdf_path = os.path.join(subj_dir, pdf)
        print(f"\n📄 Scanning: {subj} / {chapter_name}")
        
        try:
            info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout
            total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
        except: continue
            
        full_text = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
        ak_start = full_text.rfind("Answer Key")
        answers = {}
        if ak_start != -1:
            ak_text = full_text[ak_start:]
            mcq = re.findall(r'(\d+)\.\s*([A-D])\b', ak_text)
            for q, a in mcq: answers[int(q)] = {"type": "mcq", "correct_index": ord(a) - 65}

        # Map coordinates
        q_coords = {}
        for page in range(1, total_pages + 1):
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
            q_matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q(\d+)\.</word>', xml)
            foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
            foot_y = float(foot.group(1)) if foot else 1000 
            
            for i, (y_str, q_num) in enumerate(q_matches):
                q_num = int(q_num)
                y_min = float(y_str)
                y_max = float(q_matches[i+1][0]) if i+1 < len(q_matches) else foot_y - 10
                q_coords[q_num] = {"page": page, "y_min": y_min, "y_max": y_max}

        q_blocks = re.split(r'(?=Q\d+\.)', full_text)
        out_dir = os.path.join(IMG_PRACTICE, subj, chapter_name.replace(" ", "_"))
        os.makedirs(out_dir, exist_ok=True)
        
        model_groups = defaultdict(list)
        
        for block in q_blocks:
            match = re.match(r'Q(\d+)\.', block)
            if not match: continue
            q_num = int(match.group(1))
            if q_num not in q_coords: continue 
            
            q_text = re.sub(r'\s+', ' ', block[:800]).strip()
            
            # 1. Filter by Last 10 Years
            year_match = re.search(r'(20[2-9]\d)', q_text[:200])
            year = int(year_match.group(1)) if year_match else 0
            if year != 0 and year < MIN_YEAR:
                continue # Skip old questions
                
            # 2. Heuristic Difficulty & Time
            q_len = len(q_text)
            diff_num = 8 if q_len > 350 else (5 if q_len < 150 else 6) # 8=Hard, 6=Medium, 5=Easy
            ideal = 120 if diff_num == 8 else (60 if diff_num == 5 else 90)
            
            ans_data = answers.get(q_num, {"type": "mcq", "correct_index": -1})
            
            # 3. Fingerprint for model detection
            fingerprint = get_fingerprint(q_text)
            
            model_groups[fingerprint].append({
                "q_num": q_num,
                "year": year,
                "type": ans_data["type"],
                "correct_index": ans_data.get("correct_index", -1),
                "ideal_time": ideal,
                "difficulty": diff_num,
                "source": f"JEE Main {year}" if year > 0 else "JEE Main",
                "subtopic": chapter_name,
                "explanation": "💡 (Click 'Doubt in Explanation' to generate 5-part AI solution)",
                "q_coord": q_coords[q_num] # Store for cropping
            })

        # --- CURATION (Publisher Logic) ---
        curated_qs = []
        for fp, qs in model_groups.items():
            # Sort by Year (Newest first)
            qs.sort(key=lambda x: x["year"], reverse=True)
            
            # Keep the latest question from this model (Priority)
            curated_qs.append(qs[0])
            
            # Keep one more (the second latest) as Normal
            if len(qs) > 1:
                curated_qs.append(qs[1])

        # Now crop the curated ones
        for q in curated_qs:
            coord = q["q_coord"]
            img_base = os.path.join(out_dir, f"tmp_page_{coord['page']}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(coord['page']), "-l", str(coord['page']), "-singlefile", pdf_path, img_base], check=True, stdout=subprocess.DEVNULL)
            
            q_filename = os.path.join(out_dir, f"q{q['q_num']}.png")
            if os.path.exists(img_base + ".png"):
                img = Image.open(img_base + ".png")
                w, h = img.size
                scale = 150.0 / 72.0
                crop_top = max(0, (coord['y_min'] * scale) - 20)
                crop_bottom = min(h, (coord['y_max'] * scale))
                if crop_bottom > crop_top:
                    img.crop((0, int(crop_top), w, int(crop_bottom))).save(q_filename)
                os.remove(img_base + ".png")
            
            # Clean up metadata before saving
            del q["q_coord"]
            q["img"] = q_filename

        # Sort the curated list by Year descending (Newest first)
        curated_qs.sort(key=lambda x: x["year"], reverse=True)

        if curated_qs:
            # Split 50/50 into Priority and Normal for the UI
            master_db["practice"][subj][chapter_name] = {
                "priority": curated_qs[::2], # Every 2nd item (Newest)
                "normal": curated_qs[1::2]   # The rest
            }
            with open(DB_FILE, "w") as f:
                json.dump(master_db, f, indent=2)
            print(f"✅ {subj} / {chapter_name}: Curated {len(curated_qs)} unique models (Saved)")
        else:
            print(f"⚠️ {subj} / {chapter_name}: No questions found from {MIN_YEAR}+.")

print(f"\n🎉 ALL DONE! Saved curated DB to {DB_FILE}")
