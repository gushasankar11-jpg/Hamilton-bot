import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Remove any 'Coming Soon' buttons
content = re.sub(r'InlineKeyboardButton\(".*?Coming Soon.*?", callback_data="f_soon"\),?\n', '', content)
content = content.replace('elif data == "f_soon":\n            _b().answer_callback_query(call.id, "Coming Soon!", show_alert=True)', '')
print("✅ Removed 'Coming Soon' buttons.")

# 2. Replace the main PYQ Menu (inside f_mode:pyq)
old_menu_pattern = re.compile(r'if mode == "pyq":.*?parse_mode="HTML", reply_markup=kb\)', re.DOTALL)
new_menu = '''if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(InlineKeyboardButton("📖 JEE Main Chapter-wise", callback_data="f_pyq:practice"))
                kb.add(InlineKeyboardButton("🔥 JEE Adv Chapter-wise", callback_data="f_pyq_adv:practice"))
                kb.add(InlineKeyboardButton("📝 JEE Main Papers", callback_data="f_pyq_papers_cat:JEE MAIN"))
                kb.add(InlineKeyboardButton("🔥 JEE Adv Papers", callback_data="f_pyq_papers_cat:JEE ADV"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)'''
content = old_menu_pattern.sub(new_menu, content, count=1)
print("✅ Main PYQ Menu updated (Main/Adv Practice & Papers).")

# 3. Inject the f_pyq_papers_cat handler EXACTLY inside the `if data.startswith("f_mode:"):` block chain
if 'f_pyq_papers_cat:' not in content:
    marker = 'elif data.startswith("f_pyq_sub:")'
    if marker not in content:
        marker = 'elif data.startswith("f_sub:")'
        
    nav_handlers = '''elif data.startswith("f_pyq_papers_cat:"):
            cat = data.split(":", 1)[1]
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                papers = db.get("papers", {})
            except: papers = {}
            
            years = {}
            for p_name, p_data in papers.items():
                if p_data.get("exam_type", "JEE MAIN") == cat:
                    y = p_data.get("year", "Unknown")
                    years[y] = years.get(y, 0) + 1
                    
            if not years:
                _b().answer_callback_query(call.id, f"⏳ {cat} papers are still extracting. Please wait.", show_alert=True)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            for y in sorted(years.keys(), reverse=True):
                kb.add(InlineKeyboardButton(f"📅 {y} ({years[y]})", callback_data=f"f_pyq_paper_year:{cat}:{y}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
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
                    short = p_name.replace(f"{cat} ", "").replace(f"{year} ", "")
                    kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_pyq_paper:{p_name}"))
            
            kb.add(InlineKeyboardButton("🔙 Years", callback_data=f"f_pyq_papers_cat:{cat}"))
            _b().edit_message_text(f"📝 <b>{cat} {year} - Select Paper</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_paper:"):'''
    
    if marker in content:
        content = content.replace(marker, nav_handlers, 1)
        print("✅ Injected f_pyq_papers_cat handler into the correct chain.")
    else:
        print("❌ Could not find insertion point for handler.")

# 4. Ensure the Old 'f_pyq:papers' doesn't trigger the old logic anymore
old_papers_block = '''            elif ptype == "papers":'''
if old_papers_block in content:
    # Just redirect it to the main menu so it never hits the old code
    start_idx = content.find(old_papers_block)
    end_idx = content.find('elif data ==', start_idx + 20)
    if end_idx == -1: end_idx = content.find('elif data.startswith', start_idx + 20)
    
    redirect = '''            elif ptype == "papers":
                _b().answer_callback_query(call.id, "Please select from the main menu.")
                return
'''
    content = content[:start_idx] + redirect + content[end_idx:]

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved perfectly.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
