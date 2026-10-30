import re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# ==========================================
# 1. REPLACE send_pyq_q COMPLETELY
# ==========================================
start_idx = content.find("def send_pyq_q(uid, msg_id=None):")
end_idx = content.find("def clean_math")
if start_idx == -1:
    start_idx = content.find("def send_pyq_q(")
    end_idx = content.find("def ", start_idx + 15)

new_send_pyq = '''def send_pyq_q(uid, msg_id=None):
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
    state["pyq_is_numerical"] = False

    # Check for 5th question numerical rule
    is_num = (idx > 0 and idx % 5 == 0)
    if is_num:
        state["pyq_is_numerical"] = True
        state["waiting_for_pyq_numeric"] = True
        caption = f"🔢 <b>PYQ {idx+1}/{len(q_list)} (Numerical Mode)</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n\\n<i>⚠️ Options are hidden. Please type your numerical answer.</i>"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    else:
        phase = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
        diff = q.get('difficulty', 5)
        diff_str = f"{diff}/10" if isinstance(diff, int) else str(diff)
        caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase})</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {diff_str}"
        kb = InlineKeyboardMarkup(row_width=4)
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
            state["pyq_photo_msg_id"] = msg.message_id
    except Exception as e:
        _b().send_message(uid, f"❌ Image error: {e}")

    # START THE TIMER THREAD
    import threading
    def _live_timer():
        t_msg = _b().send_message(uid, "⏱️ 0s")
        state["pyq_timer_msg_id"] = t_msg.message_id
        state["pyq_timer_active"] = True
        while state.get("pyq_timer_active") and state.get("mode") == "pyq":
            time.sleep(1)
            elapsed = int(time.time() - state.get("q_start_time", time.time()))
            try: _b().edit_message_text(f"⏱️ {elapsed}s", chat_id=uid, message_id=t_msg.message_id)
            except: pass
    threading.Thread(target=_live_timer, daemon=True).start()

'''
if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_send_pyq + "\n" + content[end_idx:]

# ==========================================
# 2. REPLACE THE f_save BLOCK COMPLETELY
# ==========================================
# Find the start of f_save logic inside handle_buttons
save_start = content.find('if data == "f_save":')
if save_start == -1: save_start = content.find('elif data in ("f_save", "f_skip"):')
if save_start == -1: save_start = content.find('elif data == "f_save":')

if save_start != -1:
    # Find the next elif to know where f_save ends
    save_end = content.find('elif data == "f_skip":', save_start)
    if save_end == -1: save_end = content.find('elif data == "f_next_q":', save_start)
    
    new_f_save = '''if data == "f_save":
            if state.get("processing"): return
            state["processing"] = True
            state["pyq_timer_active"] = False # Stop live timer
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            
            if state.get("selected") is None:
                state["processing"] = False
                _b().send_message(uid, "⚠️ Please select an option first.")
                return
                
            is_correct = state["selected"] == state["q"].get("correct_index", 0)
            if is_correct: state["correct"] += 1
            else: state["wrong"] += 1
            
            time_taken = int(time.time() - state.get("q_start_time", time.time()))
            ideal = state["q"].get("ideal_time", 60)
            correct_letter = chr(65 + state["q"].get("correct_index", 0))
            
            # Record health
            try:
                import health
                health.record_attempt(uid, state.get("subj", "Physics"), state.get("chapter", ""), state["q"].get("subtopic", ""), is_correct, time_taken)
            except: pass

            msg = f"✅ <b>Correct!</b>\\n\\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>{correct_letter}</b>.\\n\\n"
            msg += f"⏱️ <b>Time:</b> {time_taken}s (Ideal: {ideal}s)"
            _b().send_message(uid, msg, parse_mode="HTML")

            # On-demand AI Solution
            if state.get("mode") == "pyq" and "img" in state["q"]:
                load_msg = _b().send_message(uid, "🧠 <i>Generating AI Solution...</i>")
                try:
                    from c40_vision_ai import get_vision_solution
                    sol = get_vision_solution(state["q"]["img"])
                    # Clean up the AI header if it added one
                    sol = sol.replace("**Solution:**", "").replace("Ultimate Solution Engine:", "").strip()
                    _b().edit_message_text(f"💡 <b>Solution:</b>\\n{sol}", chat_id=uid, message_id=load_msg.message_id, parse_mode="Markdown")
                except Exception as e:
                    _b().edit_message_text(f"❌ AI Error: {e}", chat_id=uid, message_id=load_msg.message_id)

            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt", callback_data="f_doubt"))
            kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            _b().send_message(uid, "Next step:", reply_markup=kb)
            
        elif data == "f_skip":'''
            
    if save_end != -1:
        content = content[:save_start] + new_f_save + content[save_end + len('elif data == "f_skip":'):]

# ==========================================
# 3. REPLACE f_next_q BLOCK
# ==========================================
next_start = content.find('elif data == "f_next_q":')
if next_start != -1:
    next_end = content.find('elif ', next_start + 20)
    if next_end == -1: next_end = content.find('@bot', next_start)
    
    new_f_next = '''elif data == "f_next_q":
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid) # Clean call, keeps old messages
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()
        '''
    if next_end != -1:
        content = content[:next_start] + new_f_next + content[next_end:]

open(path, "w").write(content)
print("✅ c04_exam.py patched.")
