import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# A. Remove the old broken timer thread
old_timer = """            # Start Frontend Timer
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
            threading.Thread(target=_timer, daemon=True).start()"""
            
new_timer = """            # Simple safe timer
            import threading
            def _timer(msg_id):
                for i in range(1, 300): # Max 5 mins
                    if not state.get("pyq_timer_active") or state.get("mode") != "pyq": break
                    time.sleep(1)
                    try: _b().edit_message_text(f"⏱️ {i}s", chat_id=uid, message_id=msg_id)
                    except: pass
            t_msg = _b().send_message(uid, "⏱️ 0s")
            state["pyq_timer_msg_id"] = t_msg.message_id
            state["pyq_timer_active"] = True
            threading.Thread(target=_timer, args=(t_msg.message_id,), daemon=True).start()"""

if old_timer in content:
    content = content.replace(old_timer, new_timer)
    print("✅ Timer fixed (safe 1s loop)")

# B. Fix f_save to use Vision AI for solutions
old_save = """                msg = f"✅ <b>Correct!</b>\\n\\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\\n\\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)\\n\\n"
                msg += f"📝 <b>Explanation:</b>\\n{clean_math(state['q'].get('explanation', ''))}"
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)"""

new_save = """                msg = f"✅ <b>Correct!</b>\\n\\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\\n\\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)"
                
                if state.get("mode") == "pyq" and "img" in state["q"]:
                    _b().send_message(uid, msg, parse_mode="HTML")
                    load_msg = _b().send_message(uid, "🧠 <i>Generating 5-part AI solution from image...</i>")
                    try:
                        from c40_vision_ai import get_vision_solution
                        sol = get_vision_solution(state["q"]["img"])
                        _b().edit_message_text(sol, chat_id=uid, message_id=load_msg.message_id, parse_mode="Markdown")
                    except Exception as e:
                        _b().edit_message_text(f"❌ AI Error: {e}", chat_id=uid, message_id=load_msg.message_id)
                        
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                    kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, "Select an option:", reply_markup=kb)
                else:
                    msg += f"\\n\\n📝 <b>Explanation:</b>\\n{clean_math(state['q'].get('explanation', ''))}"
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                    kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)"""

if old_save in content:
    content = content.replace(old_save, new_save)
    print("✅ f_save updated to use Vision AI on-demand")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved")
except SyntaxError as e:
    print("❌ SYNTAX ERROR:", e)
