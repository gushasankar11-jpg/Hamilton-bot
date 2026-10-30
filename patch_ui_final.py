import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# A. Replace send_pyq_q completely
start_idx = content.find("def send_pyq_q(uid, msg_id=None):")
end_idx = content.find("def clean_math")
new_func = """def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    # 60-Question Checkpoint (Only triggers once)
    if idx == 60 and not state.get("pyq_warned"):
        state["pyq_warned"] = True
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("▶️ Continue Remaining", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
        _b().send_message(uid, "🎓 <b>You have completed 60 PYQs for conceptual understanding in depth.</b>\\n\\nThis chapter has more questions. Do you want to continue with the older/skipped questions, or stop and see your result?", reply_markup=kb)
        return

    # If user finished all questions in the DB
    if idx >= len(q_list):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🛑 Stop & View Result", callback_data="f_stop"))
        _b().send_message(uid, "🏁 <b>All PYQs from this chapter are completed!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False

    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)}</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {q.get('difficulty', 'Medium')}"
    
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    if msg_id:
        try: _b().delete_message(uid, msg_id)
        except: pass
    
    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
            state["pyq_msg_id"] = msg.message_id
    except Exception as e:
        _b().send_message(uid, f"❌ Image not found: {q['img']}")

"""
content = content[:start_idx] + new_func + content[end_idx:]

# B. Patch f_pyq_ch to load the flat list structure
old_pyq = '''        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                q_data = db[subj][ch]
            except Exception as e:
                _b().answer_callback_query(call.id, "No questions found for this chapter.")
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_phase"] = "eligible"
            state["pyq_questions"] = q_data.get("eligible", [])
            state["pyq_skipped"] = q_data.get("skipped", [])
            state["pyq_index"] = 0'''

new_pyq = '''        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                q_data = db[subj][ch]
            except Exception as e:
                _b().answer_callback_query(call.id, "No questions found for this chapter.")
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_questions"] = q_data # flat list
            state["pyq_index"] = 0
            state["pyq_warned"] = False'''
content = content.replace(old_pyq, new_pyq)

# C. Add f_pyq_cont handler (just increments the index so the 60-warning doesn't trigger again)
if 'data == "f_pyq_cont"' not in content:
    marker = '        elif data == "f_next_q":'
    new_handler = '''        elif data == "f_pyq_cont":
            state["pyq_index"] += 1
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_next_q":'''
    content = content.replace(marker, new_handler)

# D. Fix f_next_q logic
old_next = '''        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()'''

new_next = '''        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()'''
content = content.replace(old_next, new_next)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Patched c04_exam.py: Full list loading & 60-Question Checkpoint applied.")
except SyntaxError as e:
    print("❌ SYNTAX ERROR:", e)

