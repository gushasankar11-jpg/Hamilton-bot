import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Deduplicate handle_buttons (keep only the first)
starts = [m.start() for m in re.finditer(r'^def handle_buttons\(call\):', content, re.MULTILINE)]
if len(starts) > 1:
    print(f"[1] Found {len(starts)} handlers, cutting duplicates...")
    # Find the end of the first handler (next top-level function)
    first_end = content.find('\ndef ', starts[0] + 10)
    if first_end == -1: first_end = content.find('\n@bot', starts[0] + 10)
    
    # Delete everything after the first handler ends
    content = content[:first_end] + '\n\n'
    print("✅ Duplicates removed. File truncated to first handler.")

# 2. Replace the 'f_pyq:papers' block
old_papers_block = '''            elif ptype == "papers":'''
if old_papers_block in content:
    # Find the entire old block
    start_idx = content.find(old_papers_block)
    end_idx = content.find('elif data ==', start_idx + 20)
    if end_idx == -1: end_idx = content.find('elif data.startswith', start_idx + 20)
    
    new_papers_block = '''            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton("📘 JEE Main Papers", callback_data="f_pyq_papers_cat:JEE MAIN"),
                    InlineKeyboardButton("🔥 JEE Adv Papers", callback_data="f_pyq_papers_cat:JEE ADV")
                )
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Tests</b>\\nSelect Exam Category:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                
'''
    content = content[:start_idx] + new_papers_block + content[end_idx:]
    print("✅ Papers menu replaced.")

# 3. Add the Hierarchical Navigation Handlers
if 'f_pyq_papers_cat:' not in content:
    # Insert before f_pyq_paper
    marker = 'elif data.startswith("f_pyq_paper:")'
    
    nav_handlers = '''elif data.startswith("f_pyq_papers_cat:"):
            cat = data.split(":", 1)[1]
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                papers = db.get("papers", {})
            except: papers = {}
            
            # Group by Year
            years = {}
            for p_name, p_data in papers.items():
                if p_data.get("exam_type", "JEE MAIN") == cat:
                    y = p_data.get("year", "Unknown")
                    if y not in years: years[y] = 0
                    years[y] += 1
                    
            if not years:
                _b().answer_callback_query(call.id, f"⏳ {cat} papers are still processing.", show_alert=True)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            for y in sorted(years.keys(), reverse=True):
                kb.add(InlineKeyboardButton(f"📅 {y} ({years[y]})", callback_data=f"f_pyq_paper_year:{cat}:{y}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:papers"))
            _b().edit_message_text(f"📝 <b>{cat} - Select Year</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_paper_year:"):
            _, cat, year = data.split(":", 2)
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                papers = db.get("papers", {})
            except: papers = {}
            
            kb = InlineKeyboardMarkup(row_width=1)
            for p_name, p_data in papers.items():
                if p_data.get("exam_type", "JEE MAIN") == cat and p_data.get("year", "Unknown") == year:
                    short_name = p_name.replace(f"{cat} ", "").replace(f"{year} ", "")
                    kb.add(InlineKeyboardButton(f"📄 {short_name[:40]}", callback_data=f"f_pyq_paper:{p_name}"))
            
            kb.add(InlineKeyboardButton("🔙 Years", callback_data=f"f_pyq_papers_cat:{cat}"))
            _b().edit_message_text(f"📝 <b>{cat} {year} - Select Paper</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_paper:")'''
    
    content = content.replace(marker, nav_handlers, 1)
    print("✅ Hierarchical navigation added (Category -> Year -> Paper).")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved perfectly.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
