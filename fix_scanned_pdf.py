import ast

path = "corporate_pipeline.py"
content = open(path).read()

# 1. Fix W1 Scanner (Pass scanned pages instead of skipping)
old_w1 = '''        t0 = time.time()
        page_text = item.get("page_text", "").upper()
        keywords = ["EXERCISE", "OBJECTIVE", "INTEGER", "MULTIPLE CORRECT", "MATCH THE COLUMN", "COMPREHENSION", "PRACTICE", "EXERCISES"]
        
        if any(k in page_text for k in keywords):
            update_state("W1_Scanner", "✅ Pass", book=item["book"], chapter=item["chapter"], page=item["p1"])
            q_scanned.put(item)
        else:
            update_state("W1_Scanner", "⏭️ Skipped", book=item["book"], chapter=item["chapter"], page=item["p1"])
            if os.path.exists(item["img_path"]): os.remove(item["img_path"])'''

new_w1 = '''        t0 = time.time()
        page_text = item.get("page_text", "").upper()
        
        # If text is less than 50 chars, it's a scanned image (No text layer)
        # We MUST pass it to W2 to avoid losing everything.
        if len(page_text) < 50:
            update_state("W1_Scanner", "✅ Pass (Scanned)", book=item["book"], chapter=item["chapter"], page=item["p1"])
            q_scanned.put(item)
        else:
            keywords = ["EXERCISE", "OBJECTIVE", "INTEGER", "MULTIPLE CORRECT", "MATCH THE COLUMN", "COMPREHENSION", "PRACTICE", "EXERCISES", "LEVEL"]
            if any(k in page_text for k in keywords):
                update_state("W1_Scanner", "✅ Pass", book=item["book"], chapter=item["chapter"], page=item["p1"])
                q_scanned.put(item)
            else:
                update_state("W1_Scanner", "⏭️ Skipped", book=item["book"], chapter=item["chapter"], page=item["p1"])
                if os.path.exists(item["img_path"]): os.remove(item["img_path"])'''

if old_w1 in content: content = content.replace(old_w1, new_w1)

# 2. Fix W2 Extractor (If no words found, crop whole page as fallback)
old_w2 = '''        if q_boxes:
            item["boxes"] = [{"q_num": q["q_num"], "type": "mcq", "box": q["box"]} for q in q_boxes]
            q_extracted.put(item)
        else:
            if os.path.exists(item["img_path"]): os.remove(item["img_path"])'''

new_w2 = '''        if q_boxes:
            item["boxes"] = [{"q_num": q["q_num"], "type": "mcq", "box": q["box"]} for q in q_boxes]
            q_extracted.put(item)
        else:
            # FALLBACK: If no numbers found (Scanned PDF), crop the whole page
            # This ensures we don't lose the questions.
            update_state(f"W2_Extractor_{worker_id}", "✅ Whole Page Fallback", book=item["book"], chapter=item["chapter"], page=item["p1"])
            item["boxes"] = [{"q_num": f"Pg{item['p1']}", "type": "mcq", "box": [0, 0, 1000, 1000]}]
            q_extracted.put(item)'''

if old_w2 in content: content = content.replace(old_w2, new_w2)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Patched: Scanned PDF handling added.")
except SyntaxError as e:
    print(f"❌ Syntax Error: {e}")
