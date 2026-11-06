import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Find the Previous Papers menu block
old_menu = '''            elif ptype == "papers":'''
if old_menu in content:
    # Replace it to show Main vs Adv choice first
    new_block = '''            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton("📘 JEE Main Papers", callback_data="f_pyq_papers_cat:JEE MAIN"),
                    InlineKeyboardButton("🔥 JEE Adv Papers", callback_data="f_pyq_papers_cat:JEE ADV")
                )
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:main"))
                _b().edit_message_text("📝 <b>Previous Paper Tests</b>\\nSelect Exam Category:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)'''

    content = content.replace(old_menu, new_block, 1)
    print("✅ Updated Previous Papers main menu.")

# 2. Add the f_pyq_papers_cat handler
if 'f_pyq_papers_cat:' not in content:
    marker = 'elif data.startswith("f_pyq_paper:")'
    cat_handler = '''elif data.startswith("f_pyq_papers_cat:"):
            cat = data.split(":", 1)[1]
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                papers = db.get("papers", {})
            except: papers = {}
            
            kb = InlineKeyboardMarkup(row_width=1)
            count = 0
            for p_name, p_data in papers.items():
                if p_data.get("exam_type", "JEE MAIN") == cat:
                    kb.add(InlineKeyboardButton(f"📄 {p_name[:45]}", callback_data=f"f_pyq_paper:{p_name}"))
                    count += 1
            
            if count == 0:
                _b().answer_callback_query(call.id, f"⏳ {cat} papers are still processing. Please wait.", show_alert=True)
                return
                
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:papers"))
            _b().edit_message_text(f"📝 <b>{cat} - Available Papers ({count})</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_paper:")'''
    content = content.replace(marker, cat_handler, 1)
    print("✅ Added Paper Category handler.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
