import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# A. Replace send_pyq_q to handle Priority -> Normal transition
start_idx = content.find("def send_pyq_q(uid, msg_id=None):")
end_idx = content.find("def clean_math")
new_func = """def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    # Phase 1: Priority Done -> Prompt for Normal
    if idx >= len(q_list) and state.get("pyq_phase") == "priority" and state.get("pyq_normal"):
        state["pyq_phase"] = "normal"
        state["pyq_questions"] = state["pyq_normal"]
        state["pyq_index"] = 0
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("▶️ Continue with Normal Questions", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
        _b().send_message(uid, "🎓 <b>You have completed all Priority (High-Yield) questions for this chapter.</b>\\n\\nDo you want to continue with the remaining normal questions?", reply_markup=kb)
        return

    # Everything Done
    if idx >= len(q_list):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🛑 Stop & View Result", callback_data="f_stop"))
        _b().send_message(uid, "🏁 <b>All questions from this chapter are completed!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False

    phase_name = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {q.get('difficulty', 5)}/10"
    
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

# B. Patch f_pyq_ch to load priority and normal
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
            state["pyq_questions"] = q_data # flat list
            state["pyq_index"] = 0
            state["pyq_warned"] = False'''

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
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0'''
content = content.replace(old_pyq, new_pyq)

# C. Add f_pyq_cont handler
if 'data == "f_pyq_cont"' not in content:
    marker = '        elif data == "f_next_q":'
    new_handler = '''        elif data == "f_pyq_cont":
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_next_q":'''
    content = content.replace(marker, new_handler)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Patched c04_exam.py: Priority -> Normal logic applied.")
except SyntaxError as e:
    print("❌ SYNTAX ERROR:", e)
