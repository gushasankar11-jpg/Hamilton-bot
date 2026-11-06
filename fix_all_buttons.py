import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Clean out any old/broken handle_buttons
pattern = re.compile(r'@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("f_"\)\)\s*\ndef handle_buttons\(call\):.*?(?=\n@bot\.|\ndef |\nclass |\Z)', re.DOTALL)
content = pattern.sub('', content)

# 2. Insert the flawless Master Handler
master_handler = '''
@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]

    if data.startswith("f_ans:") and state.get("processing"): return

    # --- MAIN MENU ---
    if data.startswith("f_mode:"):
        mode = data.split(":")[1]
        _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
        
        if mode == "pyq":
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(InlineKeyboardButton("📖 JEE Main Chapter-wise", callback_data="f_pyq:practice"))
            kb.add(InlineKeyboardButton("🔥 JEE Adv Chapter-wise", callback_data="f_pyq_adv:practice"))
            kb.add(InlineKeyboardButton("📝 JEE Main Papers", callback_data="f_pyq_papers_cat:JEE MAIN"))
            kb.add(InlineKeyboardButton("🔥 JEE Adv Papers", callback_data="f_pyq_papers_cat:JEE ADV"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text("🔍 <b>PYQ Explorer</b>\\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return
            
        if mode == "test":
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(InlineKeyboardButton("Mock Test 1", callback_data="f_soon"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text("📝 <b>Test Mode</b>\\nComing soon...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        kb = InlineKeyboardMarkup(row_width=3)
        kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
        _b().edit_message_text(f"📚 <b>{mode.capitalize()} Mode</b>\\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    # --- BACK BUTTON ---
    if data.startswith("f_back:"):
        target = data.split(":")[1]
        if target == "main":
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"), InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
            kb.add(InlineKeyboardButton("📝 Test", callback_data="f_mode:test"), InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"))
            kb.add(InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional"))
            _b().edit_message_text("📚 <b>Exam Engine</b>\\nSelect Mode:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    # --- ADVANCED CHAPTER-WISE ---
    if data == "f_pyq_adv:practice":
        kb = InlineKeyboardMarkup(row_width=3)
        kb.add(InlineKeyboardButton("Physics", callback_data="f_pyq_adv_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_pyq_adv_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_pyq_adv_sub:Maths"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
        _b().edit_message_text("🔥 <b>JEE Advanced - Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_adv_sub:"):
        subj = data.split(":")[1]
        state["pyq_subj"] = subj
        state["is_adv"] = True
        import json
        try:
            with open("data/pyq_master.json") as f: db = json.load(f)
            chapters = list(db.get("practice_adv", {}).get(subj, {}).keys())
        except: chapters = []
        kb = InlineKeyboardMarkup(row_width=1)
        if not chapters:
            _b().send_message(uid, f"⏳ <b>{subj} - Still Processing</b>")
            return
        for ch in chapters: kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_adv_ch:{ch}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq_adv:practice"))
        _b().edit_message_text(f"🔥 <b>{subj} - Advanced Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_adv_ch:"):
        ch = data.split(":", 1)[1]
        subj = state.get("pyq_subj")
        import json
        with open("data/pyq_master.json") as f: db = json.load(f)
        q_data = db.get("practice_adv", {}).get(subj, {}).get(ch)
        if not q_data: return
        state["mode"] = "pyq"; state["subj"] = subj; state["chapter"] = ch
        state["pyq_questions"] = q_data.get("priority", []); state["pyq_normal"] = q_data.get("normal", [])
        state["pyq_index"] = 0
        try: _b().delete_message(uid, call.message.message_id)
        except: pass
        send_pyq_q(uid)
        return

    # --- PAPERS NAVIGATION ---
    if data.startswith("f_pyq_papers_cat:"):
        cat = data.split(":", 1)[1]
        import json
        with open("data/pyq_master.json") as f: db = json.load(f)
        papers = db.get("papers", {})
        years = {}
        for p_name, p_data in papers.items():
            if p_data.get("exam_type", "JEE MAIN") == cat:
                y = p_data.get("year", "Unknown")
                years[y] = years.get(y, 0) + 1
        if not years:
            _b().answer_callback_query(call.id, f"⏳ {cat} papers are still extracting.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(row_width=3)
        for y in sorted(years.keys(), reverse=True):
            kb.add(InlineKeyboardButton(f"📅 {y} ({years[y]})", callback_data=f"f_pyq_paper_year:{cat}:{y}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
        _b().edit_message_text(f"📝 <b>{cat} - Select Year</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_paper_year:"):
        _, cat, year = data.split(":", 2)
        import json
        with open("data/pyq_master.json") as f: db = json.load(f)
        papers = db.get("papers", {})
        kb = InlineKeyboardMarkup(row_width=1)
        for p_name, p_data in papers.items():
            if p_data.get("exam_type") == cat and p_data.get("year") == year:
                kb.add(InlineKeyboardButton(f"📄 {p_name[:40]}", callback_data=f"f_pyq_paper:{p_name}"))
        kb.add(InlineKeyboardButton("🔙 Years", callback_data=f"f_pyq_papers_cat:{cat}"))
        _b().edit_message_text(f"📝 <b>{cat} {year} - Select Paper</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_paper:"):
        paper_name = data.split(":", 1)[1]
        import json, time as _t
        with open("data/pyq_master.json") as f: db = json.load(f)
        paper_data = db.get("papers", {}).get(paper_name)
        if not paper_data: return
        state["mode"] = "pyq"; state["subj"] = "Full Paper"; state["chapter"] = paper_name
        state["pyq_questions"] = paper_data.get("questions", []); state["pyq_normal"] = []
        state["pyq_index"] = 0; state["pyq_is_paper"] = True
        try: _b().delete_message(uid, call.message.message_id)
        except: pass
        cdown = _b().send_message(uid, "📄 <b>Starting Paper Test...</b>\\n\\n5...")
        for n in [4, 3, 2, 1]:
            _t.sleep(1)
            _b().edit_message_text(f"📄 <b>Starting Paper Test...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
        _t.sleep(1)
        _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
        _t.sleep(0.5)
        send_pyq_q(uid)
        return

    # --- MAIN CHAPTER-WISE ---
    if data.startswith("f_pyq:"):
        ptype = data.split(":")[1]
        import json
        with open("data/pyq_master.json") as f: db = json.load(f)
        if ptype == "practice":
            kb = InlineKeyboardMarkup(row_width=3)
            for subj in db.get("practice", {}).keys(): kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
            _b().edit_message_text("📖 <b>JEE Main PYQ Practice</b>\\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_sub:"):
        subj = data.split(":")[1]
        state["pyq_subj"] = subj; state["is_adv"] = False
        import json
        with open("data/pyq_master.json") as f: db = json.load(f)
        kb = InlineKeyboardMarkup(row_width=1)
        for ch in db.get("practice", {}).get(subj, {}).keys(): kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
        _b().edit_message_text(f"📖 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_ch:"):
        ch = data.split(":", 1)[1]
        subj = state.get("pyq_subj")
        import json
        with open("data/pyq_master.json") as f: db = json.load(f)
        q_data = db.get("practice", {}).get(subj, {}).get(ch)
        if not q_data: return
        state["mode"] = "pyq"; state["subj"] = subj; state["chapter"] = ch
        state["pyq_questions"] = q_data.get("priority", []); state["pyq_normal"] = q_data.get("normal", [])
        state["pyq_index"] = 0
        try: _b().delete_message(uid, call.message.message_id)
        except: pass
        send_pyq_q(uid)
        return

    # --- NAVIGATION BAR & SOLUTIONS ---
    if data == "nav_topics":
        state["nav_view"] = "topics"; state["nav_topic"] = None; state["nav_year"] = None
        _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=_build_pyq_nav(uid))
        return
    if data == "nav_back_year":
        state["nav_view"] = "years"; state["nav_year"] = None
        _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=_build_pyq_nav(uid))
        return
    if data.startswith("nav_topic:"):
        state["nav_topic"] = state.get("_nav_topics", [])[int(data.split(":")[1])]
        state["nav_view"] = "years"; state["nav_year"] = None
        _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=_build_pyq_nav(uid))
        return
    if data.startswith("nav_year:"):
        state["nav_year"] = data.split(":", 1)[1]; state["nav_view"] = "questions"
        _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=_build_pyq_nav(uid))
        return
    if data.startswith("nav_jump:"):
        state["pyq_timer_active"] = False
        try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
        except: pass
        try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
        except: pass
        state["pyq_index"] = int(data.split(":")[1])
        send_pyq_q(uid)
        return

    # --- PRACTICE MODE (f_sub, f_ch, f_ans, etc) ---
    if data.startswith("f_sub:"):
        subj = data.split(":")[1]; state["subj"] = subj
        import json
        try:
            with open(f"data/jee_main_{subj.lower()}.json") as f: chapters = _extract_chapters(json.load(f))
        except: chapters = []
        state["chapters"] = chapters; state["page"] = 0
        _show_chapters(uid, call.message.message_id)
        return

    if data.startswith("f_page:"):
        state["page"] += int(data.split(":")[1])
        _show_chapters(uid, call.message.message_id)
        return

    if data.startswith("f_ch:"):
        state["chapter"] = data.split(":", 1)[1]; state["q_count"] = 0
        _b().edit_message_text(f"⏳ Generating Q1...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
        import threading
        threading.Thread(target=_generate_next, args=(uid, call.message.message_id), daemon=True).start()
        return

    if data.startswith("f_ans:"):
        state["selected"] = int(data.split(":")[1])
        kb = InlineKeyboardMarkup(row_width=4)
        kb.row(*[InlineKeyboardButton(f"{'✅' if i == state['selected'] else ''}{chr(65+i)}", callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
        return

    if data in ("f_save", "f_skip"):
        state["pyq_timer_active"] = False
        try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
        except: pass
        if data == "f_save" and state.get("selected") is not None:
            is_correct = state["selected"] == state["q"].get("correct_index", 0)
            time_taken = int(time.time() - state.get("q_start_time", time.time()))
            ideal = state["q"].get("ideal_time", 60)
            correct_letter = chr(65 + state["q"].get("correct_index", 0))
            msg = f"✅ <b>Correct!</b> ⏱ {time_taken}s / {ideal}s" if is_correct else f"❌ <b>Wrong.</b> Answer: <b>{correct_letter}</b> ⏱ {time_taken}s"
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("💡 AI Solution", callback_data="f_solution"), InlineKeyboardButton("▶️ Next", callback_data="f_next_q"))
            kb.add(InlineKeyboardButton("💬 Doubt", callback_data="f_doubt"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
        else:
            state["pyq_index"] = state.get("pyq_index", 0) + 1
            send_pyq_q(uid)
        state["selected"] = None
        return

    if data == "f_next_q":
        state["selected"] = None
        if state.get("mode") == "pyq":
            state["pyq_index"] = state.get("pyq_index", 0) + 1
            send_pyq_q(uid)
        else:
            import threading
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()
        return
        
    if data == "f_solution":
        load = _b().send_message(uid, "🧠 <i>Generating beautifully formatted solution...</i>")
        try:
            q_text = state.get("q", {}).get("q_text", "")
            sol = get_ai_solution(q_text, uid)
            clean_sol = clean_math(sol)
            if len(clean_sol) > 4000: clean_sol = clean_sol[:4000] + "..."
            _b().edit_message_text(clean_sol, chat_id=uid, message_id=load.message_id, parse_mode="HTML")
        except Exception as e:
            _b().edit_message_text(f"❌ Error: {e}", chat_id=uid, message_id=load.message_id)
        return

    if data == "f_doubt":
        state["waiting_for_doubt"] = True
        _b().send_message(uid, "💬 <b>Please type your doubt about this question.</b>", parse_mode="HTML")
        return
'''
content += "\n\n" + master_handler + "\n"
open(path, "w").write(content)
print("✅ Handle Buttons completely rebuilt and restored.")
