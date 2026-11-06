import os, sys, json, re
import pdfplumber
import ai_client

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
os.makedirs(OUT_DIR, exist_ok=True)

def ask_ai_group(blocks_text):
    prompt = f"""
    You are an expert educational content analyzer.
    Group the blocks into distinct items using these STRICT rules:
    1. "theory": Complete paragraphs and formulas.
    2. "illustration_question": The header (e.g. "Example 1.1") AND the question statement ONLY.
    3. "illustration_solution": The solution for that illustration.
    4. "exercise_question": The exercise header AND individual questions (Q1, Q2).
    
    Return ONLY JSON:
    {{
      "items": [
        {{"type": "theory", "start_id": 1, "end_id": 15}},
        {{"type": "illustration_question", "start_id": 16, "end_id": 18}},
        {{"type": "illustration_solution", "start_id": 19, "end_id": 25}}
      ]
    }}
    Blocks:
    {blocks_text}
    """
    try:
        res = ai_client._route_call("You are a JSON API.", prompt)
        res = res.replace("```json", "").replace("```", "").strip()
        return json.loads(res)
    except: return None

def generate_options(q_text):
    prompt = f"""
    Generate 4 multiple choice options (A, B, C, D) for this JEE question:
    "{q_text}"
    Return ONLY JSON: {{"A": "option 1", "B": "option 2", "C": "option 3", "D": "option 4", "correct": "A"}}
    """
    try:
        res = ai_client._route_call("You are a JSON API.", prompt)
        res = res.replace("```json", "").replace("```", "").strip()
        return json.loads(res)
    except: return None

def process_pdf(pdf_path, test_limit=2):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    os.makedirs(out_book_dir, exist_ok=True)
    
    print(f"🤖 Extracting: {book_id} (Pages 15 to {15+test_limit})")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            end_page = min(15 + test_limit, total_pages)
            
            for batch_start in range(15, end_page, 10):
                batch_end = min(batch_start + 10, end_page)
                print(f"  🧠 AI grouping pages {batch_start+1} to {batch_end}...", end="", flush=True)
                
                blocks_data = []
                block_id = 0
                
                for page_num in range(batch_start, batch_end):
                    page = pdf.pages[page_num]
                    words = page.extract_words()
                    if not words: continue
                    lines = {}
                    for w in words:
                        y_round = round(w['top'] / 5) * 5
                        if y_round not in lines: lines[y_round] = []
                        lines[y_round].append(w)
                    for y in sorted(lines.keys()):
                        lw = sorted(lines[y], key=lambda w: w['x0'])
                        text = " ".join([w['text'] for w in lw])
                        blocks_data.append({
                            "id": block_id, "text": text, "page": page_num,
                            "x0": lw[0]['x0'], "y0": lw[0]['top'], "x1": lw[-1]['x1'], "y1": lw[-1]['bottom']
                        })
                        block_id += 1
                
                if not blocks_data:
                    print(" ❌ Empty.")
                    continue

                # Clean text for AI
                dump = "\n".join([f"[{b['id']}] {re.sub(r'\s+', ' ', b['text']).strip()}" for b in blocks_data])
                ai_result = ask_ai_group(dump)
                
                if not ai_result or "items" not in ai_result:
                    print(" ❌ AI failed.")
                    continue
                    
                print(f" ✅ Grouped {len(ai_result['items'])} items.")
                
                for item in ai_result["items"]:
                    sec = item.get("type", "theory")
                    start_id = item.get("start_id")
                    end_id = item.get("end_id")
                    
                    if start_id is None or end_id is None: continue
                    
                    group_blocks = [b for b in blocks_data if start_id <= b["id"] <= end_id]
                    if not group_blocks: continue
                    
                    # If it's an illustration question, generate options!
                    if sec == "illustration_question":
                        q_text = " ".join([b["text"] for b in group_blocks])
                        print(f"    ✨ Generating MCQ options for Illustration...", end="", flush=True)
                        opts = generate_options(q_text)
                        if opts:
                            # Save options as a JSON text file so the bot can read it later
                            opt_file = os.path.join(out_book_dir, "illustration", f"opts_q{start_id}.json")
                            os.makedirs(os.path.dirname(opt_file), exist_ok=True)
                            json.dump(opts, open(opt_file, "w"), indent=2)
                            print(" Done.")
                        else:
                            print(" Failed.")
                    
                    # Group by page for cropping
                    pages_in_group = {}
                    for b in group_blocks:
                        if b["page"] not in pages_in_group: pages_in_group[b["page"]] = []
                        pages_in_group[b["page"]].append(b)
                        
                    for p_num, p_blocks in pages_in_group.items():
                        page = pdf.pages[p_num]
                        
                        # Exact bounding box of ONLY these blocks
                        x0 = max(0, min([b["x0"] for b in p_blocks]) - 5)
                        y0 = max(0, min([b["y0"] for b in p_blocks]) - 5)
                        x1 = min(page.width, max([b["x1"] for b in p_blocks]) + 5)
                        y1 = min(page.height, max([b["y1"] for b in p_blocks]) + 5)
                        
                        im = page.crop((x0, y0, x1, y1)).to_image(resolution=150).original
                        if im.height > 4000:
                            ratio = 4000 / im.height
                            im = im.resize((int(im.width * ratio), 4000))
                            
                        filename = f"{sec}_q{start_id}_p{p_num+1}.png"
                        filepath = os.path.join(out_book_dir, sec, filename)
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        im.save(filepath)

    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_pdf(sys.argv[1], test_limit=2)
