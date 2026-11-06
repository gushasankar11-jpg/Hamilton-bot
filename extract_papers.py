import os, subprocess, json, re
from PIL import Image

BASE_DIR = os.getcwd()
PDF_PAPERS = os.path.join(BASE_DIR, "pyq_pdfs", "jee_main", "papers")
IMG_PAPERS = os.path.join(BASE_DIR, "pyq_images", "jee_main", "papers")
DB_FILE = os.path.join(BASE_DIR, "data", "pyq_master.json")

if not os.path.exists(PDF_PAPERS):
    print("❌ Papers folder not found")
    exit(1)

db = json.load(open(DB_FILE))
if "papers" not in db: db["papers"] = {}

pdfs = [f for f in os.listdir(PDF_PAPERS) if f.lower().endswith(".pdf")]
print(f"Found {len(pdfs)} paper PDFs")
print("")

for pdf in sorted(pdfs):
    paper_name = pdf.replace(".pdf", "").replace("JEE Main ", "").replace(" Question Paper with Answer Key", "").strip()
    
    if paper_name in db["papers"]:
        print(f"⏩ Skip (done): {paper_name[:60]}")
        continue
    
    pdf_path = os.path.join(PDF_PAPERS, pdf)
    print(f"📄 Extracting: {paper_name[:60]}")
    
    # Get year + shift
    year_match = re.search(r'(20\d\d)', paper_name)
    year = year_match.group(1) if year_match else "?"
    
    try:
        info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout
        total_pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
    except: continue
    
    # Answer key extraction
    full_text = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
    ak_start = full_text.rfind("Answer Key")
    if ak_start == -1: ak_start = full_text.rfind("ANSWER KEY")
    answers = {}
    if ak_start != -1:
        ak_text = full_text[ak_start:]
        mcq = re.findall(r'(\d+)\.\s*([A-D])\b', ak_text)
        for q, a in mcq: answers[int(q)] = ord(a) - 65
    
    # Map question coordinates
    q_coords = {}
    for page in range(1, total_pages + 1):
        xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True).stdout
        q_matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q(\d+)\.</word>', xml)
        if not q_matches:
            q_matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>(\d+)\.</word>', xml)
        foot = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml)
        foot_y = float(foot.group(1)) if foot else 1000
        
        for i, (y_str, q_num) in enumerate(q_matches):
            qn = int(q_num)
            y_min = float(y_str)
            y_max = float(q_matches[i+1][0]) if i+1 < len(q_matches) else foot_y - 10
            q_coords[qn] = {"page": page, "y_min": y_min, "y_max": y_max}
    
    # Extract question texts
    q_texts = {}
    for block in re.split(r'(?=Q\d+\.)', full_text):
        m = re.match(r'Q(\d+)\.', block)
        if m:
            q_texts[int(m.group(1))] = re.sub(r'\s+', ' ', block[:1500]).strip()
    
    # Create paper entry
    out_dir = os.path.join(IMG_PAPERS, paper_name.replace(" ", "_").replace("/", "_"))
    os.makedirs(out_dir, exist_ok=True)
    
    paper_qs = []
    
    for page in range(1, total_pages + 1):
        img_base = os.path.join(out_dir, f"tmp_{page}")
        subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page), "-l", str(page), "-singlefile", pdf_path, img_base], check=True, stdout=subprocess.DEVNULL)
        img_path = img_base + ".png"
        if not os.path.exists(img_path): continue
        img = Image.open(img_path)
        w, h = img.size
        scale = 150.0 / 72.0
        
        for qn, coord in q_coords.items():
            if coord["page"] != page: continue
            
            crop_top = max(0, (coord["y_min"] * scale) - 20)
            crop_bottom = min(h, (coord["y_max"] * scale))
            if crop_bottom <= crop_top: continue
            
            q_filename = os.path.join(out_dir, f"q{qn}.png")
            img.crop((0, int(crop_top), w, int(crop_bottom))).save(q_filename)
            
            q_text = q_texts.get(qn, "")
            diff = 8 if len(q_text) > 400 else (5 if len(q_text) < 150 else 6)
            
            paper_qs.append({
                "q_num": qn,
                "type": "mcq",
                "correct_index": answers.get(qn, -1),
                "ideal_time": 120 if diff == 8 else 90,
                "difficulty": diff,
                "source": paper_name,
                "subtopic": "Full Paper",
                "q_text": q_text,
                "img": q_filename
            })
        os.remove(img_path)
        print(f"   Page {page}/{total_pages}...", end="\r")
    
    if paper_qs:
        paper_qs.sort(key=lambda x: x["q_num"])
        db["papers"][paper_name] = {"questions": paper_qs, "year": year}
        json.dump(db, open(DB_FILE, "w"), indent=2)
        print(f"\n✅ {paper_name[:50]}: {len(paper_qs)} questions")
    else:
        print(f"\n⚠️ No questions found in {paper_name}")

print("\n🎉 Paper extraction complete!")
print(f"Total papers in DB: {len(db['papers'])}")
