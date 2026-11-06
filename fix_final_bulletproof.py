import ast
import re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# The EXACT block that was broken (we will replace it with perfect indentation)
# We look for "if data == "f_save":" and replace everything up to "elif data == "f_skip":"

clean_block = '''            if data == "f_save":
                if state.get("processing"): return
                state["processing"] = True
                state["pyq_timer_active"] = False
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
                
                try:
                    import health
                    health.record_attempt(uid, state.get("subj", "Physics"), state.get("chapter", ""), state["q"].get("subtopic", ""), is_correct, time_taken)
                except: pass

                msg = "✅ <b>Correct!</b>\\n\\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>{correct_letter}</b>.\\n\\n"
                msg += f"⏱️ <b>Time:</b> {time_taken}s (Ideal: {ideal}s)"
                _b().send_message(uid, msg, parse_mode="HTML")

                # AI Vision Solution
                if state.get("mode") == "pyq" and "img" in state["q"]:
                    load_msg = _b().send_message(uid, "🧠 <i>Generating AI Solution...</i>")
                    try:
                        from c40_vision_ai import get_vision_solution
                        sol = get_vision_solution(state["q"]["img"])
                        # Clean up the AI's formatting
                        sol = sol.replace("**Solution:**", "").replace("Ultimate Solution Engine:", "").replace("Here is the solution:", "").strip()
                        _b().edit_message_text(f"💡 <b>Solution:</b>\\n{sol}", chat_id=uid, message_id=load_msg.message_id, parse_mode="Markdown")
                    except Exception as e:
                        _b().edit_message_text(f"❌ AI Error: {e}", chat_id=uid, message_id=load_msg.message_id)

                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, "Next step:", reply_markup=kb)
                
            elif data == "f_skip":'''

# Locate the broken block using regex to find exact line positions
start_match = re.search(r'\n(\s*)if data == "f_save":', content)
if not start_match:
    print("❌ Could not find f_save block. Aborting.")
    exit(1)

start_pos = start_match.start(1)
rest = content[start_pos:]
elif_match = re.search(r'\n\s*elif data == "f_skip":', rest)

if not elif_match:
    print("❌ Could not find f_skip block. Aborting.")
    exit(1)

end_pos = start_pos + elif_match.end()

# Replace
new_content = content[:start_pos] + clean_block + content[end_pos:]

# BULLETPROOF CHECK: If it fails, it will not save
try:
    ast.parse(new_content)
    open(path, "w").write(new_content)
    print("✅ SYNTAX IS PERFECT. c04_exam.py saved.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}. File NOT saved.")
