import os, json, subprocess, re

print("=== Building Master PYQ Database ===")
master_db = {}
base_dir = "pyq_images/jee_main/practice"
pdf_dir = "pyq_pdfs/jee_main/practice"

for subj in os.listdir(base_dir):
    subj_path = os.path.join(base_dir, subj)
    if not os.path.isdir(subj_path): continue
    master_db[subj] = {}
    
    for chap in os.listdir(subj_path):
        chap_path = os.path.join(subj_path, chap)
        if not os.path.isdir(chap_path): continue
        
        pdf_name = f"JEE Main {chap.replace('_', ' ')} Previous Year Questions with Answer Key.pdf"
        pdf_path = os.path.join(pdf_dir, subj, pdf_name)
        
        answers = {}
        if os.path.exists(pdf_path):
            text = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
            ak_start = text.find("Answer Key")
            if ak_start == -1: ak_start = text.find("ANSWER KEY")
            
            if ak_start != -1:
                ak_text = text[ak_start:]
                # Stricter MCQ match
                mcq_matches = re.findall(r'(\d+)\.\s*([A-D])\b', ak_text)
                # Stricter Numerical match (prevents stray dots)
                num_matches = re.findall(r'(\d+)\.\s*([\d]+(?:\.\d+)?)\b', ak_text)
                
                for q, a in mcq_matches:
                    answers[int(q)] = {"type": "mcq", "correct_index": ord(a) - 65}
                for q, a in num_matches:
                    if int(q) not in answers: 
                        try:
                            answers[int(q)] = {"type": "numerical", "correct_value": float(a)}
                        except ValueError:
                            pass # Skip if invalid float
        
        q_files = [f for f in os.listdir(chap_path) if f.startswith("q") and f.endswith(".png")]
        q_files.sort(key=lambda x: int(re.sub(r'\D', '', x)))
        
        master_db[subj][chap] = []
        for f in q_files:
            q_num = int(re.sub(r'\D', '', f))
            ans_data = answers.get(q_num, {"type": "mcq", "correct_index": -1})
            
            master_db[subj][chap].append({
                "q_num": q_num,
                "img": os.path.join(chap_path, f),
                "type": ans_data["type"],
                "correct_index": ans_data.get("correct_index", -1),
                "correct_value": ans_data.get("correct_value", None),
                "ideal_time": 90, 
                "difficulty": "Medium (5/10)"
            })

with open("data/pyq_master.json", "w") as f:
    json.dump(master_db, f, indent=2)

print(f"✅ Saved to data/pyq_master.json")
for s, chaps in master_db.items():
    total_qs = sum(len(q_list) for q_list in chaps.values())
    print(f"  {s}: {len(chaps)} chapters, {total_qs} questions")
