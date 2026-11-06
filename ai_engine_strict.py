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
    
    1. "theory": ONLY conceptual text, definitions, and formulas. DO NOT include any worked examples or illustrations here. If there is no pure theory, do not output a theory item.
    2. "illustration": The header (e.g., "Example 1.1") AND the complete question AND its full solution. Group all three together.
    3. "exercise": The exercise header AND individual questions (Q1, Q2, Q3) separately.
    
    Return ONLY a JSON object like this:
    {{
      "items": [
        {{"type": "theory", "block_ids": [1, 2, 3]}},
        {{"type": "illustration", "block_ids": [4, 5, 6, 7]}},
        {{"type": "exercise", "block_ids": [8, 9]}},
        {{"type": "exercise", "block_ids": [10, 11]}}
      ]
    }}
    Do not add any markdown or explanation outside the JSON.

    Here are the blocks:
    {blocks_text}
    """
    try:
        res = ai_client._route_call("You are a JSON API. Output ONLY valid JSON.", prompt)
        match = re.search(r'\{.*\}', res, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return None
    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        return None

def process_pdf(pdf_path):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    os.makedirs(out_book_dir, exist_ok=True)
    
    # 6 pages from different parts of the book
    test_pages = [15, 16, 45, 46, 100, 101]
    print(f"🤖 Strict Extraction: {book_id} on pages {[p+1 for p in test_pages]}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            blocks_data = []
            block_id = 0
            
            # 1. Extract blocks for the 6 pages
            for page_num in test_pages:
                if page_num >= len(pdf.pages): continue
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
                print(" ❌ No blocks found.")
                return

            # 2. Send to AI
            dump = "\n".join([f"[{b['id']}] {re.sub(r'\s+', ' ', b['text']).strip()}" for b in blocks_data])
            print(f"  🧠 AI grouping {len(blocks_data)} blocks...", end="", flush=True)
            ai_result = ask_ai_group(dump)
            
            if not ai_result or "items" not in ai_result:
                print(" ❌ AI failed.")
                return
                
            print(f" ✅ Grouped {len(ai_result['items'])} items.")
            
            # 3. Crop with Column Protection
            counter = 1
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
                    
                    # COLUMN DETECTION FIX: Prevent bleeding into adjacent column
                    avg_x0 = sum([b["x0"] for b in p_blocks]) / len(p_blocks)
                    page_mid = page.width / 2
                    
                    x0 = min([b["x0"] for b in p_blocks])
                    x1 = max([b["x1"] for b in p_blocks])
                    
                    if avg_x0 < page_mid: # Left column
                        x0 = max(0, x0 - 5)
                        x1 = min(page_mid - 5, x1 + 5) # Stop before right column
                    else: # Right column
                        x0 = max(page_mid + 5, x0 - 5) # Start after left column
                        x1 = min(page.width, x1 + 5)
                        
                    y0 = max(0, min([b["y0"] for b in p_blocks]) - 5)
                    y1 = min(page.height, max([b["y1"] for b in p_blocks]) + 5)
                    
                    im = page.crop((x0, y0, x1, y1)).to_image(resolution=150).original
                    if im.height > 4000:
                        ratio = 4000 / im.height
                        im = im.resize((int(im.width * ratio), 4000))
                        
                    filename = f"{sec}_q{counter}_p{p_num+1}.png"
                    filepath = os.path.join(out_book_dir, sec, filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    im.save(filepath)
                    counter += 1

    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_pdf(sys.argv[1])
