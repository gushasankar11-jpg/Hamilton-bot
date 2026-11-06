import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Fix the f_pyq:papers block
# We use regex to find the exact block and replace it.
pattern = re.compile(r'(\s*)elif ptype == "papers":(.*?)(?=\s*except|\s*elif|\s*@bot)', re.DOTALL)
match = pattern.search(content)

if match:
    indent = match.group(1)
    new_block = f'''{indent}elif ptype == "papers":
{indent}    kb = InlineKeyboardMarkup(row_width=2)
{indent}    kb.add(
{indent}        InlineKeyboardButton("📘 JEE Main Papers", callback_data="f_pyq_papers_cat:JEE MAIN"),
{indent}        InlineKeyboardButton("🔥 JEE Adv Papers", callback_data="f_pyq_papers_cat:JEE ADV")
{indent}    )
{indent}    kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
{indent}    _b().edit_message_text("📝 <b>Previous Paper Tests</b>\\nSelect Exam Category:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
'''
    content = content[:match.start()] + new_block + content[match.end():]
    print("✅ Replaced 'papers' block safely.")
else:
    print("⚠️ 'papers' block not found, might already be replaced.")

# 2. Add the Category -> Year -> Paper handlers
# We inject them right before `elif data.startswith("f_pyq_paper:")` or `elif data.startswith("f_pyq_ch:")`
if 'f_pyq_papers_cat:' not in content:
    marker = 'elif data.startswith("f_pyq_paper:")'
    if marker not in content:
        marker = 'elif data.startswith("f_pyq_ch:")'
        
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
                    short = p_name.replace(f"{cat} ", "").replace(f"{year} ", "")
                    kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_pyq_paper:{p_name}"))
            
            kb.add(InlineKeyboardButton("🔙 Years", callback_data=f"f_pyq_papers_cat:{cat}"))
            _b().edit_message_text(f"📝 <b>{cat} {year} - Select Paper</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        '''
    content = content.replace(marker, nav_handlers + marker, 1)
    print("✅ Added Category/Year navigation handlers.")
else:
    print("✅ Navigation handlers already exist.")

# 3. Ensure the main PYQ menu has the Advanced button
if 'f_pyq_adv:practice' not in content:
    old_menu = '''            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )'''
    new_menu = '''            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(InlineKeyboardButton("📖 JEE Main Chapter-wise", callback_data="f_pyq:practice"))
                kb.add(InlineKeyboardButton("🔥 JEE Advanced Chapter-wise", callback_data="f_pyq_adv:practice"))
                kb.add(InlineKeyboardButton("📝 Previous Papers", callback_data="f_pyq:papers"))'''
    
    if old_menu in content:
        content = content.replace(old_menu, new_menu)
        print("✅ Added Advanced Chapter-wise button to main menu.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved perfectly (No syntax errors).")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
