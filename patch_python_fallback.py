import ast

path = "corporate_pipeline.py"
content = open(path).read()

# 1. Fix Chapter Name (Ignore Watermarks)
old_ch = '''                page_text = pdf.pages[p1 - 1].extract_text() or ""
                lines = page_text.split('\\n')
                chapter = "Unknown"
                if lines:
                    chapter = max(lines[:5], key=len).strip()[:20] if len(lines[0]) < 10 else lines[0][:20]'''
new_ch = '''                page_text = pdf.pages[p1 - 1].extract_text() or ""
                lines = [l.strip() for l in page_text.split('\\n') if l.strip()]
                chapter = "Unknown"
                for line in lines[:10]:
                    # Ignore watermarks and page numbers
                    if "downloaded from" in line.lower() or "jeemain" in line.lower(): continue
                    if len(line) > 4 and not line.isdigit(): 
                        chapter = line[:25] # Take the first valid heading
                        break'''
if old_ch in content: content = content.replace(old_ch, new_ch)

# 2. Python Fallback for W1 (Scanner)
old_w1 = '''        res = manager_api_call(prompt, img_b64, "W1_Scanner")
        
        if res and res.get("extract", False):
            item["has_paragraphs"] = res.get("has_paragraphs", False)
            q_scanned.put(item)
        else:
            update_state("W1_Scanner", "Skipped", book=item["book"], chapter=item["chapter"], page=item["p1"])
            if os.path.exists(item["img_path"]): os.remove(item["img_path"])'''
            
new_w1 = '''        res = None
        # Check if we have ANY API keys available
        available = [(p, k) for p, k in [("Gemini", k) for k in getattr(ai_client, "GEMINI_KEYS", [])[:2]] + [("Groq", k) for k in getattr(ai_client, "GROQ_KEYS", [])[:1]] if k not in BANNED_KEYS or time.time() > BANNED_KEYS[k]["unban_time"]]
        
        if available:
            res = manager_api_call(prompt, img_b64, "W1_Scanner")
            
        if not res:
            # PYTHON FALLBACK: Read text and look for keywords
            page_text = item.get("page_text", "").upper()
            keywords = ["EXERCISE", "OBJECTIVE", "INTEGER", "MULTIPLE CORRECT", "MATCH THE COLUMN", "COMPREHENSION"]
            if any(k in page_text for k in keywords):
                item["has_paragraphs"] = "COMPREHENSION" in page_text
                q_scanned.put(item)
                update_state("W1_Scanner", "✅ Python FALLBACK", book=item["book"], chapter=item["chapter"], page=item["p1"])
            else:
                update_state("W1_Scanner", "⏭️ Skipped (Python)", book=item["book"], chapter=item["chapter"], page=item["p1"])
                if os.path.exists(item["img_path"]): os.remove(item["img_path"])
        else:
            if res.get("extract", False):
                item["has_paragraphs"] = res.get("has_paragraphs", False)
                q_scanned.put(item)
            else:
                update_state("W1_Scanner", "⏭️ Skipped (AI)", book=item["book"], chapter=item["chapter"], page=item["p1"])
                if os.path.exists(item["img_path"]): os.remove(item["img_path"])'''
if old_w1 in content: content = content.replace(old_w1, new_w1)

# 3. Python Fallback for W2 (Extractor)
old_w2 = '''        res = manager_api_call(prompt, img_b64, "W2_Extractor")
        
        if res:
            item["boxes"] = res.get("questions", [])
            if item["boxes"]: q_extracted.put(item)
            else: 
                if os.path.exists(item["img_path"]): os.remove(item["img_path"])
        else:
            if os.path.exists(item["img_path"]): os.remove(item["img_path"])'''
            
new_w2 = '''        res = None
        available = [(p, k) for p, k in [("Gemini", k) for k in getattr(ai_client, "GEMINI_KEYS", [])[:2]] + [("Groq", k) for k in getattr(ai_client, "GROQ_KEYS", [])[:1]] if k not in BANNED_KEYS or time.time() > BANNED_KEYS[k]["unban_time"]]
        
        if available:
            res = manager_api_call(prompt, img_b64, "W2_Extractor")
            
        if res:
            item["boxes"] = res.get("questions", [])
            if item["boxes"]: q_extracted.put(item)
            else: 
                if os.path.exists(item["img_path"]): os.remove(item["img_path"])
        else:
            # PYTHON FALLBACK: Crop the whole page as one giant block
            update_state("W2_Extractor", "✅ Python FALLBACK", book=item["book"], chapter=item["chapter"], page=item["p1"])
            item["boxes"] = [{"q_num": f"Pg{item['p1']}", "type": "mcq", "box": [0, 0, 1000, 1000]}]
            q_extracted.put(item)'''
if old_w2 in content: content = content.replace(old_w2, new_w2)

# 4. Save page_text in W0 so W1 can use it for Python fallback
old_w0_put = '''                q_pages.put({"p1": p1, "p2": p2, "book": book_name, "chapter": chapter, "out_dir": out_book_dir, "img_path": temp_img, "w": w, "h": h, "total": total_pages})'''
new_w0_put = '''                q_pages.put({"p1": p1, "p2": p2, "book": book_name, "chapter": chapter, "out_dir": out_book_dir, "img_path": temp_img, "w": w, "h": h, "total": total_pages, "page_text": page_text})'''
if old_w0_put in content: content = content.replace(old_w0_put, new_w0_put)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Pipeline Patched: Python Fallback added. Chapter names fixed.")
except SyntaxError as e:
    print(f"❌ Syntax Error: {e}")
