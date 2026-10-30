import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Replace send_pyq_q completely
start_idx = content.find("def send_pyq_q(uid, msg_id=None):")
end_idx = content.find("def clean_math")
if start_idx == -1:
    print("❌ send_pyq_q not found")
    exit()

new_func = """def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    if idx >= len(q_list):
        if state.get("pyq_phase") == "priority" and state.get("pyq_normal"):
            state["pyq_phase"] = "normal"
            state["pyq_questions"] = state["pyq_normal"]
            state["pyq_index"] = 0
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("▶️ Continue with Normal", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
            _b().send_message(uid, "🎓 <b>You have completed all Priority questions.</b>\\n\\nDo you want to continue with the remaining normal questions?", reply_markup=kb)
            return

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🛑 Stop & View Result", callback_data="f_stop"))
        _b().send_message(uid, "🏁 <b>All questions from this chapter are completed!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False
    state["pyq_is_numerical"] = False # Reset flag

    # --- 5th Question Numerical Logic ---
    is_num = (idx > 0 and idx % 5 == 0)
    if is_num:
        state["pyq_is_numerical"] = True
        # Tell the user to type the answer
        state["waiting_for_pyq_numeric"] = True
        caption = f"🔢 <b>PYQ {idx+1}/{len(q_list)} (Numerical Mode)</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n\\n<i>⚠️ Options are hidden. Please type your numerical answer.</i>"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    else:
        phase_name = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
        diff_raw = q.get('difficulty', 5)
        try:
            diff_num = int(float(diff_raw))
            diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
            diff_str = f"{diff_num}/10 ({diff_text})"
        except: diff_str = str(diff_raw)
            
        caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {diff_str}"
        kb = InlineKeyboardMarkup(row_width=4)
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    # Clean up previous photo, but NOT the solution text
    if state.get("pyq_photo_msg_id"):
        try: _b().delete_message(uid, state["pyq_photo_msg_id"])
        except: pass
    
    # Send Photo
    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
            state["pyq_photo_msg_id"] = msg.message_id
            
            # Start Frontend Timer
            import threading
            def _timer():
                t_msg = _b().send_message(uid, "⏱️ 0s")
                state["pyq_timer_msg_id"] = t_msg.message_id
                state["pyq_timer_active"] = True
                while state.get("pyq_timer_active") and state.get("mode") == "pyq":
                    elapsed = int(time.time() - state.get("q_start_time", time.time()))
                    try:
                        _b().edit_message_text(f"⏱️ {elapsed}s", chat_id=uid, message_id=t_msg.message_id)
                    except: pass
                    time.sleep(2) # update every 2 seconds to avoid rate limits
            threading.Thread(target=_timer, daemon=True).start()

    except Exception as e:
        _b().send_message(uid, f"❌ Failed to send photo: {e}\\nPath: {q['img']}")

"""
content = content[:start_idx] + new_func + content[end_idx:]

# 2. Stop timer when answer is submitted or skipped
content = content.replace('state["processing"] = True', 'state["processing"] = True\n            state["pyq_timer_active"] = False')
content = content.replace('state["pyq_index"] += 1\n                send_pyq_q', 'state["pyq_timer_active"] = False\n                state["pyq_index"] += 1\n                send_pyq_q')

# 3. Fix f_next_q so it doesn't delete the solution message
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
                send_pyq_q(uid) # <-- No msg_id passed, so solution stays!
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()'''
if old_next in content:
    content = content.replace(old_next, new_next)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py patched: Live timer, Solution kept, 5th question numerical flag.")
except SyntaxError as e:
    print("❌ SYNTAX ERROR:", e)
