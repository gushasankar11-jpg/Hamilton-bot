import os, subprocess, json, re, time, sys
from PIL import Image

# ==========================================
# YOUR KEYS
# ==========================================
GROQ_KEYS = [
    "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",
    "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",
    "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",
    "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"
]

groq_idx = 0

def ask_ai(question_text):
    global groq_idx
    
    prompt = f"""
    Analyze this JEE Main question:
    "{question_text}"
    
    Return ONLY a valid JSON object with these exact keys:
    {{
      "model": "Short name of the tested concept",
      "is_priority": (boolean, true if it's a unique model, high-yield, or advanced),
      "difficulty": (integer 1-10),
      "ideal_time": (integer in seconds),
      "solution_process": "General step-by-step",
      "solution_angle": "Different way to visualize",
      "solution_shortcut": "Fast trick or elimination",
      "solution_formula": "Core formula used"
    }}
    """
    
    while True:
        if groq_idx >= len(GROQ_KEYS):
            print("\n⏳ ALL KEYS EXHAUSTED. Waiting 60s...")
            time.sleep(60)
            groq_idx = 0

        key = GROQ_KEYS[groq_idx]
        
        # We use CURL for 100% reliable connection on Termux
        cmd = [
            "curl", "-s", "-X", "POST", "https://api.groq.com/openai/v1/chat/completions",
            "-H", f"Authorization: Bearer {key}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "model": "openai/gpt-oss-120b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            })
        ]
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            result = json.loads(res.stdout)
            
            if "error" in result:
                print(f"\n⚠️ Groq Key {groq_idx+1} error: {result['error']['message']}. Switching...", end="")
                groq_idx += 1
                continue
                
            return json.loads(result["choices"][0]["message"]["content"])
        except Exception as e:
            print(f"\n⚠️ Key {groq_idx+1} timeout/error. Switching...", end="")
            groq_idx += 1

# ==========================================
# EXTRACTION LOGIC
# ==========================================
print("🧪 Testing API with CURL...")
try:
    test_res = ask_ai("Return a json: {\"status\": \"ok\"}")
    print("\n✅ API is working perfectly!")
except Exception as e:
    print(f"\n❌ API Test Failed: {e}")
    sys.exit(1)

time.sleep(1)

BASE_DIR = os.getcwd()
PDF_PRACTICE = os.path.join(BASE_DIR, "pyq_pdfs", "jee_main", "practice")
IMG_PRACTICE = os.path.join(BASE_DIR, "pyq_images", "jee_main", "practice")
DB_FILE = os.path.join(BASE_DIR, "data", "pyq_master.json")

master_db = {"practice": {}, "papers": {}}
if os.path.exists(DB_FILE):
    try:
        loaded_db = json.load(open(DB_FILE))
        if "practice" in loaded_db: master_db["practice"] = loaded_db["practice"]
        if "papers" in loaded_db: master_db["papers"] = loaded_db["papers"]
    except: pass

print("\n🚀 Starting PRIORITY Extraction...")

for subj in os.listdir(PDF_PRACTICE):
    subj_dir = os.path.join(PDF_PRACTICE, subj)
    if not os.path.isdir(subj_dir): continue
    if subj not in master_db["practice"]: master_db["practice"][subj] = {}

    for pdf in os.listdir(subj_dir):
        if not pdf.lower().endswith(".pdf"): continue
        chapter_name = pdf.replace(".pdf", "").strip()
        
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

        # OPTIMIZATION: Map coordinates ONCE
        print("  🗺️ Mapping question coordinates (Optimized)...")
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
        
        priority_qs, normal_qs = [], []
        seen_models = set()
        
        for block in q_blocks:
            match = re.match(r'Q(\d+)\.', block)
            if not match: continue
            q_num = int(match.group(1))
            if q_num not in q_coords: continue 
            
            q_text = re.sub(r'\s+', ' ', block[:800]).strip()
            
            print(f"  🧠 Analyzing Q{q_num}...", end="", flush=True)
            try:
                ai_data = ask_ai(q_text)
            except Exception:
                continue
            print(" Done!")
                
            model_name = ai_data.get("model", "Unknown")
            if model_name in seen_models: 
                print(f"    ⏭️ Skipped (Repeated Model: {model_name})")
                continue
            seen_models.add(model_name)
            
            sol_str = f"1. Process: {ai_data.get('solution_process')}\n2. Angle: {ai_data.get('solution_angle')}\n3. Shortcut: {ai_data.get('solution_shortcut')}\n4. Formula: {ai_data.get('solution_formula')}"
            ans_data = answers.get(q_num, {"type": "mcq", "correct_index": -1})
            
            # CROP IMMEDIATELY
            coord = q_coords[q_num]
            img_base = os.path.join(out_dir, f"tmp_page_{coord['page']}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(coord['page']), "-l", str(coord['page']), "-singlefile", pdf_path, img_base], check=True, stdout=subprocess.DEVNULL)
            
            q_filename = os.path.join(out_dir, f"q{q_num}.png")
            if os.path.exists(img_base + ".png"):
                img = Image.open(img_base + ".png")
                w, h = img.size
                scale = 150.0 / 72.0
                
                crop_top = max(0, (coord['y_min'] * scale) - 20)
                crop_bottom = min(h, (coord['y_max'] * scale))
                if crop_bottom > crop_top:
                    img.crop((0, int(crop_top), w, int(crop_bottom))).save(q_filename)
                os.remove(img_base + ".png")

            q_obj = {
                "q_num": q_num,
                "type": ans_data["type"],
                "correct_index": ans_data.get("correct_index", -1),
                "ideal_time": ai_data.get("ideal_time", 90),
                "difficulty": ai_data.get("difficulty", 5),
                "source": "JEE Main",
                "subtopic": chapter_name,
                "explanation": sol_str,
                "img": q_filename
            }
            
            if ai_data.get("is_priority"):
                priority_qs.append(q_obj)
            else:
                normal_qs.append(q_obj)
            time.sleep(1.0)

        if priority_qs or normal_qs:
            master_db["practice"][subj][chapter_name] = {
                "priority": priority_qs,
                "normal": normal_qs
            }
            with open(DB_FILE, "w") as f:
                json.dump(master_db, f, indent=2)
            print(f"✅ {subj} / {chapter_name}: {len(priority_qs)} Priority, {len(normal_qs)} Normal (Saved)")
        else:
            print(f"⚠️ {subj} / {chapter_name}: No questions passed.")

print(f"\n🎉 ALL DONE! Saved final DB to {DB_FILE}")
