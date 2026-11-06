import re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# A. Replace send_pyq_q with timer-via-caption version
start = content.find("def send_pyq_q(")
end = content.find("\ndef ", start + 20)
if start == -1:
    print("❌ send_pyq_q not found")
    exit(1)

new_func = '''def send_pyq_q(uid, msg_id=None):
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
            kb.add(InlineKeyboardButton("▶️ Continue Normal", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
            _b().send_message(uid, "🎓 <b>Priority completed.</b>\\n\\nContinue with normal questions?", reply_markup=kb)
            return
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().send_message(uid, "🏁 <b>All questions complete!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False
    state["pyq_is_numerical"] = False
    state["pyq_timer_active"] = True

    is_num = (idx > 0 and idx % 5 == 0)
    diff = q.get('difficulty', 5)
    diff_str = f"{diff}/10" if isinstance(diff, (int, float)) else str(diff)
    ideal = q.get('ideal_time', 90)

    if is_num:
        state["pyq_is_numerical"] = True
        state["waiting_for_pyq_numeric"] = True
        base_cap = f"🔢 <b>PYQ {idx+1}/{len(q_list)} (NUMERICAL)</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal: {ideal}s\\n\\n<i>Options hidden. Type your answer.</i>"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    else:
        phase = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
        base_cap = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase})</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal: {ideal}s\\n📊 Difficulty: {diff_str}"
        kb = InlineKeyboardMarkup(row_width=4)
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=base_cap + "\\n\\n⏱ 0s", parse_mode="HTML", reply_markup=kb)
            state["pyq_photo_msg_id"] = msg.message_id
            state["pyq_base_caption"] = base_cap
    except Exception as e:
        _b().send_message(uid, f"❌ Image missing: {e}")
        return

    # LIVE TIMER via caption edit
    import threading
    def _timer(uid_, msg_id, base_cap_):
        for sec in range(1, 301, 2):
            time.sleep(2)
            st = _state.get(uid_, {})
            if not st.get("pyq_timer_active"): break
            try:
                _b().edit_message_caption(f"{base_cap_}\\n\\n⏱ {sec}s", chat_id=uid_, message_id=msg_id)
            except:
                pass
    threading.Thread(target=_timer, args=(uid, msg.message_id, base_cap), daemon=True).start()

'''
content = content[:start] + new_func + content[end:]

# B. Replace f_save block with FAST version (no AI call)
save_start = content.find('if data == "f_save":')
if save_start == -1:
    save_start = content.find('elif data == "f_save":')
if save_start == -1:
    save_start = content.find('elif data in ("f_save", "f_skip"):')

if save_start != -1:
    save_end = content.find('elif data == "f_skip":', save_start)
    if save_end == -1:
        save_end = content.find('elif data == "f_next_q":', save_start)
    
    fast_save = '''if data == "f_save":
                if state.get("processing"): return
                state["processing"] = True
                state["pyq_timer_active"] = False
                try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
                except: pass
                
                if state.get("selected") is None:
                    state["processing"] = False
                    _b().send_message(uid, "⚠️ Select an option first.")
                    return
                
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    health.record_attempt(uid, state.get("subj", "Physics"), state.get("chapter", ""), state["q"].get("subtopic", ""), is_correct, time_taken)
                except: pass

                if is_correct:
                    msg = f"✅ <b>Correct!</b>  ⏱ {time_taken}s / Ideal {ideal}s"
                else:
                    msg = f"❌ <b>Wrong.</b> Answer: <b>{correct_letter}</b>  ⏱ {time_taken}s / Ideal {ideal}s"

                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("💡 Get AI Solution", callback_data="f_solution"), InlineKeyboardButton("▶️ Next", callback_data="f_next_q"))
                kb.add(InlineKeyboardButton("💬 Doubt", callback_data="f_doubt"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":'''

    content = content[:save_start] + fast_save + content[save_end + len('elif data == "f_skip":'):]

# C. Add f_solution callback (AI solution on demand)
if 'data == "f_solution"' not in content:
    marker = 'elif data == "f_next_q":'
    sol_block = '''elif data == "f_solution":
            try: _b().answer_callback_query(call.id, "Generating...")
            except: pass
            load = _b().send_message(uid, "🧠 <i>Generating solution...</i>")
            try:
                from c40_vision_ai import get_ai_solution
                q_text = state["q"].get("q_text", "")
                sol = get_ai_solution(q_text)
                _b().edit_message_text(sol, chat_id=uid, message_id=load.message_id, parse_mode="Markdown")
            except Exception as e:
                _b().edit_message_text(f"❌ {e}", chat_id=uid, message_id=load.message_id)
            
        elif data == "f_next_q":'''
    content = content.replace(marker, sol_block, 1)

# D. Add f_scan callback (AI scan button appears at chapter start)
# We'll add this in the f_pyq_ch handler later; just add the callback now
if 'data == "f_scan"' not in content:
    marker2 = 'elif data == "f_solution":'
    scan_block = '''elif data == "f_scan":
            try: _b().answer_callback_query(call.id, "Scanning...")
            except: pass
            load = _b().send_message(uid, "🤖 <i>AI scanning questions (batches of 10)...</i>")
            try:
                from c40_vision_ai import ai_scan_questions
                q_list = state.get("pyq_questions", [])
                scores = ai_scan_questions(q_list[:40])
                # Re-sort by score (highest first), unscored go to end
                q_list.sort(key=lambda q: scores.get(q["q_num"], 0), reverse=True)
                state["pyq_questions"] = q_list
                state["pyq_index"] = 0
                _b().edit_message_text(f"✅ Scanned {len(scores)} questions. Serving best first.", chat_id=uid, message_id=load.message_id)
                send_pyq_q(uid)
            except Exception as e:
                _b().edit_message_text(f"❌ Scan failed: {e}", chat_id=uid, message_id=load.message_id)
            
        elif data == "f_solution":'''
    content = content.replace(marker2, scan_block, 1)

open(path, "w").write(content)
print("✅ c04_exam.py patched (timer via caption, fast save, AI solution on-demand, AI scan)")
