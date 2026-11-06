import os, subprocess, json, re
from PIL import Image

BASE = os.getcwd()
DB = os.path.join(BASE, "data", "pyq_master.json")
LOG = os.path.join(BASE, "extract_all.log")

def log(msg):
    print(msg, flush=True)
    try:
        with open(LOG, "a") as f: f.write(msg + "\n")
    except: pass

def detect_type(q_text):
    t = q_text.lower()
    if "match the column" in t or "match the following" in t: return "match"
    if "one or more" in t or "more than one correct" in t: return "multiple"
    if "numerical" in t or "integer type" in t or "decimal value" in t: return "numerical"
    return "single"

def load_db():
    if os.path.exists(DB):
        try: return json.load(open(DB))
        except: pass
    return {"practice": {}, "practice_adv": {}, "papers": {}}

def save_db(paper_name, paper_data):
    import time
    for attempt in range(10):
        try:
            db = load_db()
            db["papers"][paper_name] = paper_data
            tmp = DB + f".{os.getpid()}.tmp"
            json.dump(db, open(tmp, "w"), indent=2)
            os.replace(tmp, DB)
            return
        except Exception as e:
            time.sleep(0.5)
    print("⚠️ Could not save paper to DB after 10 retries")


def extract_paper(pdf_path, paper_name, exam_type, db):
    log(f"\n📄 [{exam_type}] {paper_name[:60]}")
    try:
        info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15).stdout
        total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
    except: return False
    
    if total_pages < 2 or total_pages > 60:
        log(f"  ⚠️ Skipped (Suspicious pages: {total_pages})")
        return False
    
    full_text = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
    
    # 1. Extract Answer Key
    ak_pos = max(full_text.rfind("Answer Key"), full_text.rfind("ANSWER KEY"))
    answers = {}
    if ak_pos != -1:
        for q, a in re.findall(r'(\d+)[\.\s]*([A-D])\b', full_text[ak_pos:]):
            answers[int(q)] = ord(a) - 65
    
    # 2. Map Coordinates (Flexible Regex)
        page_texts = {}
    for p_idx in range(1, total_pages + 1):
        try:
            page_texts[p_idx] = subprocess.run(["pdftotext", "-f", str(p_idx), "-l", str(p_idx), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        except: page_texts[p_idx] = ""

    q_coords = {}
    for page in range(1, total_pages + 1):
        if "Answer Key" in page_texts[page] or "ANSWER KEY" in page_texts[page]:
            continue # Skip cropping the answer key itself
        try:
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        except: continue
        
        # Match "1.", "Q1.", "1)", "(1)" -> Capture X and Y
        matches = re.findall(r'<word xMin="([\d\.]+)" yMin="([\d\.]+)"[^>]*>(?:Q\s*\.?\s*)?(\d+)[\.\)\s]*</word>', xml)
        foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
        foot_y = float(foot.group(1)) if foot else 1000
        
        for i, (x_str, y_str, q_num) in enumerate(matches):
            x_min = float(x_str)
            if x_min > 120: continue # Ignore numbers in the middle of the page
            
            qn = int(q_num)
            if qn < 1 or qn > 100: continue
            
            y_min = float(y_str)
            # The end of this question is the start of the NEXT valid question
            y_max = foot_y - 10
            for j in range(i+1, len(matches)):
                if float(matches[j][0]) < 120 and 1 <= int(matches[j][2]) <= 100:
                    y_max = float(matches[j][1])
                    break
                    
            if qn not in q_coords:
                q_coords[qn] = {"page": page, "y_min": y_min, "y_max": y_max}
    
    # 3. Extract Question Texts
    q_texts = {}
    for block in re.split(r'(?=(?:^|\n)(?:Q\s*\.?\s*)?\d+[\.\)])', full_text):
        m = re.match(r'(?:^|\n)(?:Q\s*\.?\s*)?(\d+)[\.\)]', block)
        if m:
            qn = int(m.group(1))
            if qn not in q_texts and 1 <= qn <= 100:
                q_texts[qn] = re.sub(r'\s+', ' ', block[:1500]).strip()
    
    # 4. Crop
    safe_name = re.sub(r'[^A-Za-z0-9_\-]', '_', paper_name)[:60]
    out_dir = os.path.join(BASE, "pyq_images", "papers", safe_name)
    os.makedirs(out_dir, exist_ok=True)
    
    paper_qs = []
    for page in range(1, total_pages + 1):
        to_crop = [qn for qn, c in q_coords.items() if c["page"] == page]
        if not to_crop: continue
        
        img_base = os.path.join(out_dir, f"tmp_{page}")
        try:
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        except: continue
        
        img_path = img_base + ".png"
        if not os.path.exists(img_path): continue
        
        img = Image.open(img_path)
        w, h = img.size
        scale = 150.0 / 72.0
        
        for idx_in_page, qn in enumerate(to_crop):
            c = q_coords[qn]
            top = max(0, (c["y_min"] * scale) - 20)
            bot = min(h, (c["y_max"] * scale))
            if bot <= top + 20: continue
            
            q_file = os.path.join(out_dir, f"q{qn}.png")
            main_img = img.crop((0, int(top), w, int(bot)))
            
            # --- CROSS PAGE STITCHING ---
            is_last_on_page = (idx_in_page == len(to_crop) - 1)
            q_text = q_texts.get(qn, "")
            lacks_options = not re.search(r'\(A\)|A\)|a\)', q_text)
            
            if is_last_on_page and lacks_options and page < total_pages:
                next_img_base = os.path.join(out_dir, f"tmp_{page+1}")
                subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page+1), "-l", str(page+1), "-singlefile", pdf_path, next_img_base], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                next_img_path = next_img_base + ".png"
                
                if os.path.exists(next_img_path):
                    next_img = Image.open(next_img_path)
                    next_xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page+1), "-l", str(page+1), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
                    next_q_matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q?(\d+)[\.\)\s]*</word>', next_xml)
                    
                    next_y_max = float(next_q_matches[0][0]) if next_q_matches else 200
                    next_crop_bottom = min(next_img.size[1], next_y_max * scale)
                    
                    top_part = next_img.crop((0, 0, next_img.size[0], int(next_crop_bottom)))
                    
                    combined = Image.new('RGB', (w, main_img.size[1] + top_part.size[1]), 'white')
                    combined.paste(main_img, (0, 0))
                    combined.paste(top_part, (0, main_img.size[1]))
                    combined.save(q_file)
                    
                    next_img.close()
                    try: os.remove(next_img_path)
                    except: pass
                else:
                    main_img.save(q_file)
            else:
                main_img.save(q_file)
            
            q_text = q_texts.get(qn, "")
            paper_qs.append({
                "q_num": qn,
                "subject": "Mixed", # We'll split sections later
                "section": 1,
                "type": detect_type(q_text),
                "correct_index": answers.get(qn, -1),
                "ideal_time": 120 if len(q_text) > 400 else 90,
                "difficulty": 8 if len(q_text) > 400 else 6,
                "source": paper_name,
                "q_text": q_text,
                "img": q_file
            })
        img.close()
        try: os.remove(img_path)
        except: pass
        
    if paper_qs:
        paper_qs.sort(key=lambda x: x["q_num"])
        year_m = re.search(r'20\d\d', paper_name)
        db["papers"][paper_name] = {
            "questions": paper_qs,
            "exam_type": exam_type,
            "year": year_m.group(0) if year_m else "?"
        }
        save_db(paper_name, db["papers"][paper_name])
        log(f"  ✅ Saved {len(paper_qs)} Qs")
        return True
    else:
        log(f"  ⚠️ Found 0 Qs (Formatting is too complex for regex)")
        return False

def main():
    db = load_db()
    for k in ["practice", "practice_adv", "papers"]:
        if k not in db: db[k] = {}
    
    jobs = []
    # Adv Papers
    adv_dir = os.path.join(BASE, "pyq_pdfs", "jee_adv", "papers")
    if os.path.isdir(adv_dir):
        for f in sorted(os.listdir(adv_dir)):
            if f.lower().endswith(".pdf"):
                name = f.replace(".pdf", "").strip()
                if name not in db["papers"]:
                    jobs.append((os.path.join(adv_dir, f), name, "JEE ADV"))
    
    # Main Papers
    main_dir = os.path.join(BASE, "pyq_pdfs", "jee_main", "papers")
    if os.path.isdir(main_dir):
        for f in sorted(os.listdir(main_dir)):
            if f.lower().endswith(".pdf"):
                name = f.replace(".pdf", "").replace("JEE Main ", "").strip()
                if name not in db["papers"]:
                    jobs.append((os.path.join(main_dir, f), name, "JEE MAIN"))
    
    log(f"🚀 Extractor started: {len(jobs)} papers queued")
    
    for i, (path, name, typ) in enumerate(jobs, 1):
        log(f"[{i}/{len(jobs)}] {typ}: {name[:60]}")
        try:
            extract_paper(path, name, typ, db)
        except Exception as e:
            log(f"  ❌ Crash: {e}")
    
    log(f"\n🎉 DONE — {len(db['papers'])} total papers in DB")

if __name__ == "__main__":
    main()
