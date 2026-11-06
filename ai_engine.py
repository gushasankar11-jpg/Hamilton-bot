import os, sys, json, re
import pdfplumber
import ai_client

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
DB_FILE = os.path.join(BASE, "data", "books_master.json")
os.makedirs(OUT_DIR, exist_ok=True)

def ask_ai_to_group(blocks_text):
    """Uses ai_client (8 keys) to group text blocks into educational items."""
    prompt = f"""
    I have extracted these text blocks from a textbook page. 
    Analyze them and group them into individual items:
    1. "theory": Explanations, definitions, formulas, or headers.
    2. "illustration": Solved examples, illustrations (include the header and solution).
    3. "exercise": Individual questions (group the question and its options/subparts, but keep Q1 and Q2 separate).

    Return ONLY a valid JSON object like this:
    {{
      "items": [
        {{"type": "theory", "block_ids": [0, 1]}},
        {{"type": "illustration", "block_ids": [2, 3, 4]}},
        {{"type": "exercise", "block_ids": [5]}},
        {{"type": "exercise", "block_ids": [6]}}
      ]
    }}

    Here are the blocks:
    {blocks_text}
    """
    
    system_prompt = "You are a JSON API. Output ONLY valid JSON."
    
    try:
        # Uses the built-in 8-key rotation!
        res = ai_client._route_call(system_prompt, prompt)
        # Clean markdown if AI adds it
        res = res.replace("```json", "").replace("```", "").strip()
        return json.loads(res)
    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        return None

def process_pdf(pdf_path):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    os.makedirs(out_book_dir, exist_ok=True)
    
    print(f"🤖 AI Mapping & Extracting: {book_id}", flush=True)
    
    db_entries = {"theory": [], "illustration": [], "exercise": [], "solution": []}
    global_counter = 1
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
            for page_num in range(15, total_pages): # Test on first 10 pages
                page = pdf.pages[page_num]
                words = page.extract_words()
                if not words: continue
                
                # Group words into lines
                lines = {}
                for w in words:
                    y_round = round(w['top'] / 5) * 5
                    if y_round not in lines: lines[y_round] = []
                    lines[y_round].append(w)
                    
                sorted_y = sorted(lines.keys())
                if not sorted_y: continue
                
                # Create text blocks (lines with coordinates)
                blocks = []
                for y in sorted_y:
                    line_words = sorted(lines[y], key=lambda w: w['x0'])
                    text = " ".join([w['text'] for w in line_words])
                    blocks.append({
                        "id": len(blocks),
                        "text": text,
                        "x0": line_words[0]['x0'],
                        "y0": line_words[0]['top'],
                        "x1": line_words[-1]['x1'],
                        "y1": line_words[-1]['bottom'],
                    })
                
                # Format blocks for AI
                blocks_text = "\n".join([f"ID {b['id']}: {b['text']}" for b in blocks])
                
                # Ask AI to group them
                print(f"  🧠 AI analyzing page {page_num+1} ({len(blocks)} blocks)...", end="", flush=True)
                ai_result = ask_ai_to_group(blocks_text)
                
                if not ai_result or "items" not in ai_result:
                    print(" ❌ AI failed to group.")
                    continue
                    
                print(" ✅ Grouped.")
                
                # Crop based on AI's groups
                for item in ai_result["items"]:
                    sec = item.get("type", "theory")
                    if sec not in db_entries: sec = "theory"
                    
                    ids = item.get("block_ids", [])
                    if not ids: continue
                    
                    # Get the bounding box for all blocks in this group
                    group_blocks = [b for b in blocks if b["id"] in ids]
                    if not group_blocks: continue
                    
                    x0 = max(0, min([b["x0"] for b in group_blocks]) - 10)
                    y0 = max(0, min([b["y0"] for b in group_blocks]) - 10)
                    x1 = min(page.width, max([b["x1"] for b in group_blocks]) + 10)
                    y1 = min(page.height, max([b["y1"] for b in group_blocks]) + 10)
                    
                    bbox = (x0, y0, x1, y1)
                    
                    # Render crop
                    im = page.crop(bbox).to_image(resolution=150).original
                    
                    # Telegram Size Fix
                    if im.height > 4000:
                        ratio = 4000 / im.height
                        im = im.resize((int(im.width * ratio), 4000))
                        
                    filename = f"{sec}_q{global_counter}_p{page_num+1}.png"
                    filepath = os.path.join(out_book_dir, sec, filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    im.save(filepath)
                    
                    combined_text = " ".join([b["text"] for b in group_blocks])
                    db_entries[sec].append({
                        "q_num": global_counter,
                        "img": filepath,
                        "text": combined_text[:500]
                    })
                    global_counter += 1

    except Exception as e:
        print(f"\n❌ Error processing {book_id}: {e}")
        return

    # Save DB
    import fcntl
    with open(DB_FILE + ".lock", "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        db = {}
        if os.path.exists(DB_FILE):
            try: db = json.load(open(DB_FILE))
            except: pass
        if subj not in db: db[subj] = {}
        if book_name not in db[subj]: db[subj][book_name] = {}
        db[subj][book_name][book_id] = {"content": db_entries}
        tmp = DB_FILE + ".tmp"
        json.dump(db, open(tmp, "w"), indent=2)
        os.replace(tmp, DB_FILE)
        fcntl.flock(lockfile, fcntl.LOCK_UN)

    print(f"\n✅ Finished {book_id} -> {len(db_entries['theory'])} Theory, {len(db_entries['illustration'])} Illus, {len(db_entries['exercise'])} Ex", flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_pdf(sys.argv[1])
