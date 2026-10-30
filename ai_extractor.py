import os, subprocess, json, re, urllib.request, time
from PIL import Image

# PUT YOUR GROQ API KEY HERE
GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE"

BASE_DIR = os.getcwd()
PDF_PRACTICE = os.path.join(BASE_DIR, "pyq_pdfs", "jee_main", "practice")
IMG_PRACTICE = os.path.join(BASE_DIR, "pyq_images", "jee_main", "practice")
DB_FILE = os.path.join(BASE_DIR, "data", "pyq_master.json")

master_db = {"practice": {}, "papers": {}}

def ask_ai(question_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    Analyze this JEE Main question:
    "{question_text}"
    
    Return ONLY a valid JSON object with these exact keys:
    {{
      "model": "Short name of concept (e.g., 'Capacitor Energy')",
      "is_priority": (boolean, true if it's a unique model, high-yield, or advanced),
      "difficulty": (integer 1-10),
      "ideal_time": (integer in seconds),
      "solution_process": "General step-by-step",
      "solution_angle": "Different way to visualize",
      "solution_shortcut": "Fast trick or elimination",
      "solution_formula": "Core formula used"
    }}
    """
    
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
    try:
        res = urllib.request.urlopen(req, timeout=15)
        result = json.loads(res.read().decode())
        return json.loads(result["choices"][0]["message"]["content"])
    except Exception as e:
        return None

print("🚀 Starting PRIORITY-FIRST Extraction...")

for subj in os.listdir(PDF_PRACTICE):
    subj_dir = os.path.join(PDF_PRACTICE, subj)
    if not os.path.isdir(subj_dir): continue
    master_db["practice"][subj] = {}

    for pdf in os.listdir(subj_dir):
        if not pdf.lower().endswith(".pdf"): continue
        chapter_name = pdf.replace("JEE Main ", "").replace(" Previous Year Questions with Answer Key.pdf", "").strip()
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

        q_blocks = re.split(r'(?=Q\d+\.)', full_text)
        out_dir = os.path.join(IMG_PRACTICE, subj, chapter_name.replace(" ", "_"))
        os.makedirs(out_dir, exist_ok=True)
        
        priority_qs, normal_qs = [], []
        seen_models = set()
        
        for block in q_blocks:
            match = re.match(r'Q(\d+)\.', block)
            if not match: continue
            q_num = int(match.group(1))
            q_text = re.sub(r'\s+', ' ', block[:800]).strip()
            
            ai_data = ask_ai(q_text)
            if not ai_data: continue
                
            model_name = ai_data.get("model", "Unknown")
            if model_name in seen_models: 
                continue # Skip repeated models entirely
            seen_models.add(model_name)
            
            sol_str = f"1. Process: {ai_data.get('solution_process')}\n2. Angle: {ai_data.get('solution_angle')}\n3. Shortcut: {ai_data.get('solution_shortcut')}\n4. Formula: {ai_data.get('solution_formula')}"
            ans_data = answers.get(q_num, {"type": "mcq", "correct_index": -1})
            
            q_obj = {
                "q_num": q_num,
                "type": ans_data["type"],
                "correct_index": ans_data.get("correct_index", -1),
                "ideal_time": ai_data.get("ideal_time", 90),
                "difficulty": ai_data.get("difficulty", 5),
                "source": "JEE Main (AI Filtered)",
                "subtopic": chapter_name,
                "explanation": sol_str
            }
            
            if ai_data.get("is_priority"):
                priority_qs.append(q_obj)
            else:
                normal_qs.append(q_obj)
            time.sleep(0.3)

        # Crop images for both lists
        for q in priority_qs + normal_qs:
            q_num = q["q_num"]
            for page in range(1, total_pages + 1):
                xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
                if f">Q{q_num}.<" not in xml: continue
                
                img_base = os.path.join(out_dir, f"tmp_page_{page}")
                subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], check=True)
                img = Image.open(img_base + ".png")
                w, h = img.size
                q_matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q(\d+)\.</word>', xml)
                foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
                foot_y = float(foot.group(1)) if foot else h * (72/150)
                scale = 150.0 / 72.0
                
                for i, (y_str, qn) in enumerate(q_matches):
                    if int(qn) != q_num: continue
                    y_min = float(y_str) * scale
                    y_max = float(q_matches[i+1][0]) * scale - 15 if i+1 < len(q_matches) else foot_y * scale - 15
                    crop_top = max(0, y_min - 20)
                    crop_bottom = max(crop_top + 50, min(h, y_max))
                    q_filename = os.path.join(out_dir, f"q{q_num}.png")
                    img.crop((0, int(crop_top), w, int(crop_bottom))).save(q_filename)
                    q["img"] = q_filename
                    break
                os.remove(img_base + ".png")
                break
                
        priority_qs = [q for q in priority_qs if "img" in q]
        normal_qs = [q for q in normal_qs if "img" in q]
        
        if priority_qs or normal_qs:
            master_db["practice"][subj][chapter_name] = {
                "priority": priority_qs,
                "normal": normal_qs
            }
            print(f"✅ {subj} / {chapter_name}: {len(priority_qs)} Priority, {len(normal_qs)} Normal")

with open(DB_FILE, "w") as f:
    json.dump(master_db, f, indent=2)
print(f"✅ Saved AI-FILTERED DB to {DB_FILE}")
