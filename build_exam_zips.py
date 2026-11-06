#!/usr/bin/env python3
import os, json, zipfile, datetime, glob, re

BASE = os.getcwd()
DB_FILE = "data/pyq_master.json"
IMG_DIR = "pyq_images/papers"
OUT_DIR = "exam_packages"
os.makedirs(OUT_DIR, exist_ok=True)

def classify(paper_name, paper_data):
    exam_type = str(paper_data.get("exam_type", "")).upper()
    year = paper_data.get("year")
    exam = "JEE_Adv" if ("ADV" in exam_type or "ADV" in paper_name.upper()) else "JEE_Main"
    m = re.search(r'(Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec)[a-z]*[\s_]*(?:Day[\s_]*(\d))?[\s_]*(Shift[\s_]*\d|S\d|Morning|Evening)', paper_name, re.IGNORECASE)
    if m:
        month = m.group(1).capitalize()
        day = m.group(2) or ""
        shift = m.group(3) or ("Morning" if "morning" in paper_name.lower() else "Evening" if "evening" in paper_name.lower() else "")
        session = month + (f"_Day{day}" if day else "") + (f"_{shift}" if shift else "")
    else:
        session = "Paper"
    return exam, year or "Unknown", session

def build_zip(paper_name, paper_data, zip_path):
    questions = paper_data.get("questions", [])
    safe_name = paper_name.replace("/", "_").replace(" ", "_")
    img_folder = os.path.join(IMG_DIR, safe_name)
    images = []
    if os.path.isdir(img_folder):
        for ext in ("png", "jpg"):
            images += sorted(glob.glob(os.path.join(img_folder, f"*.{ext}")))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {"paper_name": paper_name, "exam_type": paper_data.get("exam_type"),
            "year": paper_data.get("year"), "question_count": len(questions),
            "image_count": len(images), "has_answer_key": any(q.get("correct_ans") for q in questions if isinstance(q, dict)),
            "extracted_at": datetime.datetime.now().isoformat()}
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("questions.json", json.dumps(questions, indent=2))
        readme = f"# {paper_name}\n\n- Exam: {manifest['exam_type']}\n- Year: {manifest['year']}\n- Questions: {len(questions)}\n- Images: {len(images)}\n\n## Files\n- manifest.json — metadata\n- questions.json — Qs + answers\n- images/ — page crops\n"
        zf.writestr("README.md", readme)
        for img in images:
            zf.write(img, f"images/{os.path.basename(img)}")
    return os.path.getsize(zip_path)

def main():
    db = json.load(open(DB_FILE))
    papers = db.get("papers", {})
    print(f"Papers in DB: {len(papers)}")
    master = {"generated_at": datetime.datetime.now().isoformat(), "packages": [], "by_exam": {}}
    for paper_name, paper_data in papers.items():
        exam, year, session = classify(paper_name, paper_data)
        exam_dir = os.path.join(OUT_DIR, exam, str(year))
        os.makedirs(exam_dir, exist_ok=True)
        zip_name = f"{exam}_{year}_{session}.zip".replace(" ", "_")
        zip_path = os.path.join(exam_dir, zip_name)
        print(f"  → {exam}/{year}/{zip_name}")
        size = build_zip(paper_name, paper_data, zip_path)
        master["packages"].append({"exam": exam, "year": str(year), "session": session,
            "paper_name": paper_name, "zip_path": os.path.relpath(zip_path, OUT_DIR),
            "zip_size_kb": size // 1024, "question_count": len(paper_data.get("questions", []))})
        master["by_exam"].setdefault(exam, {}).setdefault(str(year), 0)
        master["by_exam"][exam][str(year)] += 1
    master["total_packages"] = len(master["packages"])
    with open(os.path.join(OUT_DIR, "manifest_master.json"), "w") as f:
        json.dump(master, f, indent=2)
    print(f"\n✅ Built {master['total_packages']} zips")
    print(f"📁 {OUT_DIR}/")
    print(f"📋 {OUT_DIR}/manifest_master.json")

if __name__ == "__main__":
    main()
