import os, sys, json, re
import pdfplumber
import ai_client

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
os.makedirs(OUT_DIR, exist_ok=True)

def ask_ai_group(blocks_text):
    prompt = f"""
    You are an expert educational content analyzer for JEE textbooks.
    Group the blocks into distinct items using these STRICT rules:
    
    1. "theory": ONLY pure conceptual text, definitions, and formulas. DO NOT include any worked examples, mathematical steps, or solutions here.
    2. "illustration": The header (e.g., "Example 1.1") AND the complete question AND its full solution. Group all three together.
    3. "exercise": The exercise header AND individual questions (Q1, Q2, Q3) separately.
    4. "solution": If an exercise question has its solution right below it, group the solution separately and label it "solution".
    
    Return ONLY JSON:
    {{
      "items": [
        {{"type": "theory", "block_ids": [1, 2, 3]}},
        {{"type": "illustration", "block_ids": [4, 5, 6, 7]}},
        {{"type": "exercise", "block_ids": [8, 9]}},
        {{"type": "solution", "block_ids": [10, 11]}}
      ]
    }}
    Do not add any markdown or explanation outside the JSON.

    Here are the blocks:
    {blocks_text}
    """
    try:
        res = ai_client._route_call("You are a JSON API. Output ONLY valid JSON.", prompt)
        if not res:
            return None
        match = re.search(r'\{.*\}', res, re.DOTALL)
        if match: return json.loads(match.group(0))
        return None
    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        return None

def process_pdf(pdf_path, test_limit=10):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    os.makedirs(out_book_dir, exist_ok=True)
    
    print(f"🤖 Extracting 10 Pages: {book_id}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            end_page = min(15 + test_limit, total_pages)
            
            # PROCESS IN CHUNKS OF 2 PAGES TO AVOID 413 TOKEN ERROR
            for batch_start in range(15, end_page, 2):
                batch_end = min(batch_start + 2, end_page)
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
                
                if not blocks_data: continue

                dump = "\n".join([f"[{b['id']}] {re.sub(r'\s+', ' ', b['text']).strip()}" for b in blocks_data])
                ai_result = ask_ai_group(dump)
                
                if not ai_result or "items" not in ai_result:
                    print(" ❌ AI failed.")
                    continue
                    
                print(f" ✅ Grouped {len(ai_result['items'])} items.")
                
                for item in ai_result["items"]:
                    sec = item.get("type", "theory")
                    ids = item.get("block_ids", [])
                    if not ids: continue
                    
                    group_blocks = [b for b in blocks_data if b["id"] in ids]
                    if not group_blocks: continue
                    
                    pages_in_group = {}
                    for b in group_blocks:
                        if b["page"] not in pages_in_group: pages_in_group[b["page"]] = []
                        pages_in_group[b["page"]].append(b)
                        
                    for p_num, p_blocks in pages_in_group.items():
                        page = pdf.pages[p_num]
                        
                        # --- EXACT DIMENSION BORDER (No hardcoded mid-points) ---
                        x0 = max(0, min([b["x0"] for b in p_blocks]) - 10)
                        y0 = max(0, min([b["y0"] for b in p_blocks]) - 10)
                        x1 = min(page.width, max([b["x1"] for b in p_blocks]) + 10)
                        y1 = min(page.height, max([b["y1"] for b in p_blocks]) + 10)
                        
                        im = page.crop((x0, y0, x1, y1)).to_image(resolution=150).original
                        if im.height > 4000:
                            ratio = 4000 / im.height
                            im = im.resize((int(im.width * ratio), 4000))
                            
                        filename = f"{sec}_q{ids[0]}_p{p_num+1}.png"
                        filepath = os.path.join(out_book_dir, sec, filename)
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        im.save(filepath)

    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_pdf(sys.argv[1], test_limit=10)
