import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# Replace the old handler
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
            target = data.split(":")[1]
            if target == "main":
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"), InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
                kb.add(InlineKeyboardButton("📝 Test", callback_data="f_mode:test"), InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"))
                _b().edit_message_text("📚 <b>Exam Engine</b>\\nSelect Mode:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        # --- CHAPTER-WISE (WITH COUNTDOWN) ---
        if data.startswith("f_pyq:practice"):
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
            if not q_data: return

            state["mode"] = "pyq"; state["subj"] = subj; state["chapter"] = ch
            state["pyq_phase"] = "priority"
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

        # --- PAPERS (64-BYTE LIMIT FIXED) ---
        if data.startswith("f_pyq_papers_cat:"):
            cat = data.split(":", 1)[1].strip().upper()
            papers = db.get("papers", {})
            years = {}
            for p_name, p_data in papers.items():
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
            papers = db.get("papers", {})
            
            # Store valid papers in state to avoid Telegram's 64-byte limit
            state["paper_list"] = []
            kb = InlineKeyboardMarkup(row_width=1)
            for p_name, p_data in papers.items():
                if str(p_data.get("exam_type", "JEE MAIN")).strip().upper() == cat and str(p_data.get("year")) == year:
                    state["paper_list"].append(p_name)
                    idx = len(state["paper_list"]) - 1
                    short = p_name.replace(f"{cat} ", "").replace(f"{year} ", "")
                    # Use index for callback data to stay under 64 bytes
                    kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_pyq_paper_idx:{idx}"))
            
            kb.add(InlineKeyboardButton("🔙 Years", callback_data=f"f_pyq_papers_cat:{cat}"))
            _b().edit_message_text(f"📝 <b>{cat} {year} - Select Paper</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        if data.startswith("f_pyq_paper_idx:"):
            idx = int(data.split(":")[1])
            paper_name = state.get("paper_list", [])[idx]
            paper_data = db.get("papers", {}).get(paper_name)
            if not paper_data: return
            
            state["mode"] = "pyq"; state["subj"] = "Full Paper"; state["chapter"] = paper_name
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = paper_data.get("questions", [])
            state["pyq_normal"] = []
            state["pyq_index"] = 0; state["pyq_is_paper"] = True
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            def run_countdown():
                cdown = _b().send_message(uid, "📄 <b>Starting Paper Test...</b>\\n\\n5...")
                for n in [4, 3, 2, 1]:
                    time.sleep(1)
                    try: _b().edit_message_text(f"📄 <b>Starting Paper Test...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                    except: pass
                time.sleep(1)
                _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                time.sleep(0.5)
                send_pyq_q(uid)
            threading.Thread(target=run_countdown, daemon=True).start()
            return

        if data.startswith("nav_jump:"):
            target = int(data.split(":")[1])
            state["pyq_timer_active"] = False
            try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
            except: pass
            try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
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
ast.parse(content)
open(path, "w").write(content)
print("✅ Fixed Telegram 64-byte limit crash and added countdown to Practice.")
