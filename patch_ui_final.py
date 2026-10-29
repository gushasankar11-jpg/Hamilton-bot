import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# A. Replace send_pyq_q completely
start_idx = content.find("def send_pyq_q(uid, msg_id=None):")
end_idx = content.find("def clean_math")
old_func = content[start_idx:end_idx]

new_func = """def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    # Check if current phase is done
    if idx >= len(q_list):
        if state.get("pyq_phase") == "eligible" and state.get("pyq_skipped"):
            # Transition to Phase 2
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("▶️ Continue Older", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
            _b().send_message(uid, "🎓 <b>You have completed enough PYQ revision for conceptual understanding in depth.</b>\\n\\nIf you want to continue with older/skipped PYQs, click Continue. Or click Stop to get your result.", reply_markup=kb)
        else:
            # Everything done
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🛑 Stop & View Result", callback_data="f_stop"))
            _b().send_message(uid, "🏁 <b>All PYQs from this chapter are completed!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False

    phase_name = "Core" if state.get("pyq_phase") == "eligible" else "Older"
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {q.get('difficulty', 'Medium')}"
    
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

# B. Patch f_pyq_ch to load the two-phase structure
old_pyq = '''        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                q_list = db[subj][ch]
            except Exception as e:
                _b().answer_callback_query(call.id, "No questions found for this chapter.")
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_questions"] = q_list
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
            state["pyq_phase"] = "eligible"
            state["pyq_questions"] = q_data.get("eligible", [])
            state["pyq_skipped"] = q_data.get("skipped", [])
            state["pyq_index"] = 0'''
content = content.replace(old_pyq, new_pyq)

# C. Add f_pyq_cont handler for Phase 2
if 'data == "f_pyq_cont"' not in content:
    marker = '        elif data == "f_next_q":'
    new_handler = '''        elif data == "f_pyq_cont":
            state["pyq_phase"] = "skipped"
            state["pyq_questions"] = state.get("pyq_skipped", [])
            state["pyq_index"] = 0
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_next_q":'''
    content = content.replace(marker, new_handler)

# D. Fix f_next_q to handle phase transition and result stats
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
# Actually the logic is already correct, we just need to make sure f_next_q works. The above is fine.

# E. Fix f_stop to show results
if 'state["mode"] == "pyq"' not in content:
    # Add stats calculation to f_stop if in pyq mode
    old_stop = '''        elif data == "f_stop":
            state["active"] = False'''
    new_stop = '''        elif data == "f_stop":
            state["active"] = False
            if state.get("mode") == "pyq":
                c = state.get("correct", 0)
                w = state.get("wrong", 0)
                s = state.get("skipped", 0)
                msg = f"🛑 <b>PYQ Practice Stopped</b>\\n\\n✅ Correct: {c}\\n❌ Wrong: {w}\\n⏭ Skipped: {s}"
                _b().send_message(uid, msg, parse_mode="HTML")'''
    if old_stop in content:
        content = content.replace(old_stop, new_stop)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Patched c04_exam.py: Two-phase UI & Result logic applied.")
except SyntaxError as e:
    print("❌ SYNTAX ERROR:", e)

