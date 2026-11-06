import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# --- 1. Restore the Test button in the Main Menu ---
# Find the main menu block
old_menu = '''kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
                    InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq")
                )'''
new_menu = '''kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
                    InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq")
                )
                kb.add(
                    InlineKeyboardButton("📝 Test", callback_data="f_mode:test"),
                    InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual")
                )'''
if old_menu in content:
    content = content.replace(old_menu, new_menu)
    print("✅ Test button restored to Main Menu.")
else:
    # If exact string not found, look for the f_back:main block and patch it
    old_back = '''kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"), InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))'''
    new_back = '''kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"), InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
                kb.add(InlineKeyboardButton("📝 Test", callback_data="f_mode:test"), InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"))'''
    if old_back in content:
        content = content.replace(old_back, new_back)
        print("✅ Test button restored via fallback.")


# --- 2. Inject Missing Handlers at the TOP of handle_buttons ---
marker = 'def handle_buttons(call):'
if marker in content:
    # Find where the variables are initialized
    init_marker = 'data = call.data'
    if init_marker in content:
        injection = '''data = call.data
        state = _state.get(uid, {})
        
        # ==========================================
        # SAFE OVERRIDE HANDLERS (Caught before old code)
        # ==========================================
        if data == "f_pyq_adv:practice":
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("Physics", callback_data="f_pyq_adv_sub:Physics"),
                InlineKeyboardButton("Chemistry", callback_data="f_pyq_adv_sub:Chemistry"),
                InlineKeyboardButton("Maths", callback_data="f_pyq_adv_sub:Maths")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
            _b().edit_message_text("🔥 <b>JEE Advanced - Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        elif data.startswith("f_pyq_adv_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                chapters = list(db.get("practice_adv", {}).get(subj, {}).keys())
            except: chapters = []
            
            kb = InlineKeyboardMarkup(row_width=1)
            if not chapters:
                _b().send_message(uid, f"⏳ <b>{subj} - Still Processing</b>\\nNo chapters extracted yet for Advanced.")
                return
            
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_adv_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq_adv:practice"))
            _b().edit_message_text(f"🔥 <b>{subj} - Advanced Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        elif data.startswith("f_pyq_adv_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                q_data = db["practice_adv"][subj][ch]
            except Exception as e:
                _b().answer_callback_query(call.id, "Error loading DB.", show_alert=True)
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            send_pyq_q(uid)
            return

        elif data.startswith("f_pyq_papers_cat:"):
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
            return

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
            return
        # =========================================='''
        
        content = content.replace(init_marker, injection, 1)
        print("✅ Missing handlers injected at the top of handle_buttons.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved perfectly.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
