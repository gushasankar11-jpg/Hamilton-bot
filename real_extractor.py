import os, subprocess, json, re
from PIL import Image

BASE_DIR = os.getcwd()
PDF_PRACTICE = os.path.join(BASE_DIR, "pyq_pdfs", "jee_main", "practice")
IMG_PRACTICE = os.path.join(BASE_DIR, "pyq_images", "jee_main", "practice")
DB_FILE = os.path.join(BASE_DIR, "data", "pyq_master.json")

master_db = {"practice": {}, "papers": {}}
CORE_LIMIT = 60  # First 60 go to 'eligible', rest go to 'skipped'

print(f"🚀 Starting FULL Extraction (Splitting at {CORE_LIMIT})...")

for subj in os.listdir(PDF_PRACTICE):
    subj_dir = os.path.join(PDF_PRACTICE, subj)
    if not os.path.isdir(subj_dir): continue
    master_db["practice"][subj] = {}

    for pdf in os.listdir(subj_dir):
        if not pdf.lower().endswith(".pdf"): continue
        chapter_name = pdf.replace("JEE Main ", "").replace(" Previous Year Questions with Answer Key.pdf", "").strip()
        pdf_path = os.path.join(subj_dir, pdf)
        
        try:
            info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout
            total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
        except:
            continue
            
        text = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
        ak_start = text.rfind("Answer Key")
        answers = {}
        if ak_start != -1:
            ak_text = text[ak_start:]
            mcq = re.findall(r'(\d+)\.\s*([A-D])\b', ak_text)
            num = re.findall(r'(\d+)\.\s*([\d]+(?:\.\d+)?)\b', ak_text)
            for q, a in mcq: answers[int(q)] = {"type": "mcq", "correct_index": ord(a) - 65}
            for q, a in num:
                if int(q) not in answers:
                    try: answers[int(q)] = {"type": "numerical", "correct_value": float(a)}
                    except: pass

        out_dir = os.path.join(IMG_PRACTICE, subj, chapter_name.replace(" ", "_"))
        os.makedirs(out_dir, exist_ok=True)
        
        all_qs = []
        
        for page in range(1, total_pages + 1):
            img_base = os.path.join(out_dir, f"tmp_page_{page}")
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], check=True)
            img_path = img_base + ".png"
            if not os.path.exists(img_path): continue
            img = Image.open(img_path)
            w, h = img.size
            
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
            q_matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q(\d+)\.</word>', xml)
            
            foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
            foot_y = float(foot.group(1)) if foot else h * (72/150)
            scale = 150.0 / 72.0
            
            for i, (y_str, q_num) in enumerate(q_matches):
                q_num = int(q_num)
                y_min = float(y_str) * scale
                y_max = float(q_matches[i+1][0]) * scale - 15 if i+1 < len(q_matches) else foot_y * scale - 15
                
                crop_top, crop_bottom = max(0, y_min - 20), min(h, y_max)
                q_img = img.crop((0, int(crop_top), w, int(crop_bottom)))
                q_filename = os.path.join(out_dir, f"q{q_num}.png")
                q_img.save(q_filename)
                
                header_text = text[max(0, text.find(f"Q{q_num}.")-100) : text.find(f"Q{q_num}.")+200]
                date_match = re.search(r'(JEE Main \d{4}.*?Shift)', header_text, re.IGNORECASE)
                source_date = date_match.group(1) if date_match else "JEE Main (Unknown Shift)"
                
                q_len = len(re.sub(r'[^\w\s]', '', header_text))
                diff = "Hard" if q_len > 400 else ("Easy" if q_len < 150 else "Medium")
                ideal = 120 if diff == "Hard" else (60 if diff == "Easy" else 90)
                
                ans_data = answers.get(q_num, {"type": "mcq", "correct_index": -1})
                
                all_qs.append({
                    "q_num": q_num,
                    "img": q_filename,
                    "type": ans_data["type"],
                    "correct_index": ans_data.get("correct_index", -1),
                    "correct_value": ans_data.get("correct_value", None),
                    "ideal_time": ideal,
                    "difficulty": diff,
                    "source": source_date,
                    "subtopic": chapter_name
                })
            os.remove(img_path)
            
        if all_qs:
            all_qs.sort(key=lambda x: x["q_num"])
            # Split into eligible (first 60) and skipped (rest)
            master_db["practice"][subj][chapter_name] = {
                "eligible": all_qs[:CORE_LIMIT],
                "skipped": all_qs[CORE_LIMIT:]
            }
            print(f"✅ {subj} / {chapter_name}: {len(all_qs[:CORE_LIMIT])} eligible, {len(all_qs[CORE_LIMIT:])} skipped")

with open(DB_FILE, "w") as f:
    json.dump(master_db, f, indent=2)
print(f"✅ Saved TWO-PHASE DB to {DB_FILE}")
