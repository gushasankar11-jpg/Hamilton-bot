import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Replace the entire handle_buttons to include Advanced
pattern = re.compile(r'(@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("f_"\)\)\s*)?def handle_buttons\(call\):.*?(?=\n@bot\.|\ndef |\nclass |\Z)', re.DOTALL)
content = pattern.sub('', content)

master_handler = '''
@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    
    try:
        uid = call.from_user.id
        data = call.data
        if uid not in _state: _state[uid] = {}
        state = _state[uid]
        db = get_pyq_db()

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

            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
            _b().edit_message_text(f"📚 <b>{mode.capitalize()} Mode</b>\\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        if data.startswith("f_back:"):
            if data.split(":")[1] == "main":
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"), InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
                kb.add(InlineKeyboardButton("📝 Test", callback_data="f_mode:test"), InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"))
                _b().edit_message_text("📚 <b>Exam Engine</b>\\nSelect Mode:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        # --- JEE MAIN CHAPTER-WISE ---
        if data == "f_pyq:practice":
            kb = InlineKeyboardMarkup(row_width=3)
            for subj in db.get("practice", {}).keys():
                kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
            _b().edit_message_text("📖 <b>JEE Main PYQ Practice</b>\\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        if data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            kb = InlineKeyboardMarkup(row_width=1)
            for ch in db.get("practice", {}).get(subj, {}).keys():
                kb.add(InlineKeyboardButton(ch[:40], callback_data=f"f_pyq_ch:{ch[:40]}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        if data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            q_data = db.get("practice", {}).get(subj, {}).get(ch)
            if not q_data or not q_data.get("priority"):
                _b().answer_callback_query(call.id, "No questions found in this chapter.", show_alert=True)
                return

            state["mode"] = "pyq"; state["subj"] = subj; state["chapter"] = ch
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0; state["pyq_is_paper"] = False
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            def run_cd_ch():
                cdown = _b().send_message(uid, "📄 <b>Starting Practice...</b>\\n\\n5...")
                for n in [4, 3, 2, 1]:
                    time.sleep(1)
                    try: _b().edit_message_text(f"📄 <b>Starting Practice...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                    except: pass
                time.sleep(1)
                _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                time.sleep(0.5)
                send_pyq_q(uid)
            threading.Thread(target=run_cd_ch, daemon=True).start()
            return

        # --- JEE ADV CHAPTER-WISE (THE MISSING BUTTONS) ---
        if data == "f_pyq_adv:practice":
            kb = InlineKeyboardMarkup(row_width=3)
            for subj in db.get("practice_adv", {}).keys():
                kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_adv_sub:{subj}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
            _b().edit_message_text("🔥 <b>JEE Adv PYQ Practice</b>\\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        if data.startswith("f_pyq_adv_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            state["is_adv"] = True
            kb = InlineKeyboardMarkup(row_width=1)
            for ch in db.get("practice_adv", {}).get(subj, {}).keys():
                kb.add(InlineKeyboardButton(ch[:40], callback_data=f"f_pyq_adv_ch:{ch[:40]}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq_adv:practice"))
            _b().edit_message_text(f"🔥 <b>{subj} - Adv Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        if data.startswith("f_pyq_adv_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            q_data = db.get("practice_adv", {}).get(subj, {}).get(ch)
            if not q_data or not q_data.get("priority"):
                _b().answer_callback_query(call.id, "No questions found in this chapter.", show_alert=True)
                return

            state["mode"] = "pyq"; state["subj"] = subj; state["chapter"] = ch
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0; state["pyq_is_paper"] = False
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            def run_cd_adv():
                cdown = _b().send_message(uid, "📄 <b>Starting Adv Practice...</b>\\n\\n5...")
                for n in [4, 3, 2, 1]:
                    time.sleep(1)
                    try: _b().edit_message_text(f"📄 <b>Starting Adv Practice...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                    except: pass
                time.sleep(1)
                _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                time.sleep(0.5)
                send_pyq_q(uid)
            threading.Thread(target=run_cd_adv, daemon=True).start()
            return

        # --- PAPERS (From previous fix) ---
        if data.startswith("f_pyq_papers_cat:"):
            cat = data.split(":", 1)[1].strip().upper()
            years = {}
            for p_name, p_data in db.get("papers", {}).items():
                if str(p_data.get("exam_type", "JEE MAIN")).strip().upper() == cat:
                    y = str(p_data.get("year", "Unknown"))
                    years[y] = years.get(y, 0) + 1
            if not years: return
                
            kb = InlineKeyboardMarkup(row_width=3)
            for y in sorted(years.keys(), reverse=True):
                kb.add(InlineKeyboardButton(f"📅 {y} ({years[y]})", callback_data=f"f_pyq_paper_year:{cat}:{y}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
            _b().edit_message_text(f"📝 <b>{cat} - Select Year</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        if data.startswith("f_pyq_paper_year:"):
            _, cat, year = data.split(":", 2)
            state["paper_list"] = []
            kb = InlineKeyboardMarkup(row_width=1)
            for p_name, p_data in db.get("papers", {}).items():
                if str(p_data.get("exam_type", "JEE MAIN")).strip().upper() == cat and str(p_data.get("year")) == year:
                    state["paper_list"].append(p_name)
                    short = p_name.replace(f"{cat} ", "").replace(f"{year} ", "")
                    kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_pyq_paper_idx:{len(state['paper_list'])-1}"))
            kb.add(InlineKeyboardButton("🔙 Years", callback_data=f"f_pyq_papers_cat:{cat}"))
            _b().edit_message_text(f"📝 <b>{cat} {year} - Select Paper</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        if data.startswith("f_pyq_paper_idx:"):
            idx = int(data.split(":")[1])
            paper_name = state.get("paper_list", [])[idx]
            paper_data = db.get("papers", {}).get(paper_name)
            if not paper_data: return
            
            state["mode"] = "pyq"; state["subj"] = "Full Paper"; state["chapter"] = paper_name
            state["pyq_questions"] = paper_data.get("questions", [])
            state["pyq_index"] = 0; state["pyq_is_paper"] = True
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            inst_img = paper_data.get("instructions_img")
            if inst_img and os.path.exists(inst_img):
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ I have read the instructions, Start Test", callback_data="f_start_paper"))
                with open(inst_img, "rb") as f:
                    _b().send_photo(uid, f, caption="📜 <b>Instructions</b>", parse_mode="HTML", reply_markup=kb)
            else:
                def run_cd_paper():
                    cdown = _b().send_message(uid, "📄 <b>Starting Paper...</b>\\n\\n5...")
                    for n in [4, 3, 2, 1]:
                        time.sleep(1)
                        try: _b().edit_message_text(f"📄 <b>Starting Paper...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                        except: pass
                    time.sleep(1)
                    _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                    time.sleep(0.5)
                    send_pyq_q(uid)
                threading.Thread(target=run_cd_paper, daemon=True).start()
            return

        if data == "f_start_paper":
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            def run_cd_start():
                cdown = _b().send_message(uid, "📄 <b>Starting Paper...</b>\\n\\n5...")
                for n in [4, 3, 2, 1]:
                    time.sleep(1)
                    try: _b().edit_message_text(f"📄 <b>Starting Paper...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                    except: pass
                time.sleep(1)
                _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                time.sleep(0.5)
                send_pyq_q(uid)
            threading.Thread(target=run_cd_start, daemon=True).start()
            return

        # --- NAVIGATION ---
        if data.startswith("nav_jump:"):
            target = int(data.split(":")[1])
            state["pyq_timer_active"] = False
            try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
            except: pass
            try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
            except: pass
            try: _b().delete_message(uid, state.get("pyq_photo_msg_id"))
            except: pass
            state["pyq_index"] = target
            send_pyq_q(uid)
            return
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        _b().send_message(uid, f"❌ Error: {e}")
'''
content += "\n\n" + master_handler + "\n"

# 2. Fix send_pyq_q to prevent silent crashes
start_idx = content.find("def send_pyq_q(uid, msg_id=None):")
end_idx = content.find("\ndef ", start_idx + 20)
if end_idx == -1: end_idx = content.find("\n@bot", start_idx)

new_send = '''def send_pyq_q(uid, msg_id=None):
    state = _state.get(uid, {})
    if state.get("mode") != "pyq": return
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)

    if idx >= len(q_list):
        _b().send_message(uid, "🏁 <b>All questions complete!</b>", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop")))
        return

    q = q_list[idx]
    img_path = q.get("img", "")
    
    if not os.path.exists(img_path):
        _b().send_message(uid, f"❌ <b>Image Missing!</b>\\nPath: <code>{img_path}</code>\\nThis question was probably not extracted correctly.")
        return

    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False
    state["pyq_timer_active"] = True

    try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
    except: pass
    try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
    except: pass

    diff = q.get('difficulty', 5)
    diff_str = f"{diff}/10" if isinstance(diff, (int, float)) else str(diff)
    ideal = q.get('ideal_time', 90)
    qtype = q.get('type', 'single').upper()
    
    if state.get("pyq_is_paper"):
        header = f"📝 <b>Question {idx+1}/{len(q_list)}</b>"
    else:
        header = f"📝 <b>PYQ {idx+1}/{len(q_list)}</b>"

    cap = f"{header}\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s | 📊 Diff: {diff_str} | Type: {qtype}"

    kb = InlineKeyboardMarkup(row_width=4)
    if qtype in ["SINGLE", "MCQ"]:
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    elif qtype in ["NUMERICAL", "INTEGER"]:
        state["waiting_for_pyq_numeric"] = True
        cap += "\\n<i>Type your answer below:</i>"
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    else:
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    try:
        with open(img_path, "rb") as f:
            msg = _b().send_photo(uid, f, caption=cap, parse_mode="HTML", reply_markup=kb)
            state["pyq_photo_msg_id"] = msg.message_id
    except Exception as e:
        _b().send_message(uid, f"❌ Telegram Send Error: {e}")
        return

    t_msg = _b().send_message(uid, "⏱ 0s")
    state["pyq_timer_msg_id"] = t_msg.message_id

    nav_kb = _build_pyq_nav(uid)
    if nav_kb:
        n_msg = _b().send_message(uid, "🧭 <b>Navigation:</b>", parse_mode="HTML", reply_markup=nav_kb)
        state["pyq_nav_msg_id"] = n_msg.message_id

    def _timer(uid_, t_msg_id):
        for i in range(1, 301):
            time.sleep(1)
            st = _state.get(uid_, {})
            if not st.get("pyq_timer_active"): break
            try: _b().edit_message_text(f"⏱ {i}s", chat_id=uid_, message_id=t_msg_id)
            except: pass
    threading.Thread(target=_timer, args=(uid, t_msg.message_id), daemon=True).start()

'''
content = content[:start_idx] + new_send + content[end_idx:]

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Patched Advanced buttons AND added crash protection to send_pyq_q.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
