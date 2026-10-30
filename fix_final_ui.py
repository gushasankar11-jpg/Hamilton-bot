import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# --- Fix 1: Maths/Chemistry navigation page ---
start_sub = content.find('        elif data.startswith("f_pyq_sub:"):')
end_sub = content.find('        elif data.startswith("f_pyq_ch:"):')

if start_sub != -1 and end_sub != -1:
    new_sub_block = '''        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json
            chapters = []
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                extracted = db.get("practice", {}).get(subj, {})
                chapters = list(extracted.keys())
            except Exception:
                pass

            kb = InlineKeyboardMarkup(row_width=1)
            if not chapters:
                # Show a proper page instead of an alert
                msg = f"⏳ <b>{subj} - Still Processing</b>\\n\\nNo chapters have been extracted yet. Hamilton is working on it in the background. Please check back later."
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
                _b().edit_message_text(msg, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return

            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - Extracted PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

'''
    content = content[:start_sub] + new_sub_block + content[end_sub:]
    print("✅ Fixed Maths/Chemistry navigation.")

# --- Fix 2: PYQ Chapter Click (Adding absolute path check & crash reporter) ---
start_ch = content.find('        elif data.startswith("f_pyq_ch:"):')
end_ch = content.find('        elif data == "f_back:"', start_ch)
if end_ch == -1: end_ch = content.find('        elif data.startswith("f_back:")', start_ch)

if start_ch != -1 and end_ch != -1:
    new_ch_block = '''        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json, os
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                q_data = db[subj][ch]
            except Exception as e:
                _b().answer_callback_query(call.id, f"❌ Error loading DB: {e}", show_alert=True)
                return

            if not q_data.get("priority") and not q_data.get("normal"):
                _b().answer_callback_query(call.id, "⚠️ No questions found in this chapter.", show_alert=True)
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0
            
            # Verify the image path exists before trying to send
            first_q = state["pyq_questions"][0] if state["pyq_questions"] else None
            if not first_q:
                _b().answer_callback_query(call.id, "❌ Priority list is empty.", show_alert=True)
                return
                
            if not os.path.exists(first_q["img"]):
                _b().send_message(uid, f"❌ <b>Database Error:</b> Image file missing at `{first_q['img']}`. The extraction might have failed to save the image.", parse_mode="HTML")
                return
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            try:
                send_pyq_q(uid)
            except Exception as e:
                _b().send_message(uid, f"❌ UI Crash: {e}")
                print(f"PYQ UI CRASH: {e}")

'''
    content = content[:start_ch] + new_ch_block + content[end_ch:]
    print("✅ Fixed PYQ chapter click (Added path validation).")

# --- Fix 3: Ensure send_pyq_q handles missing images gracefully ---
if "def send_pyq_q(uid, msg_id=None):" in content:
    start_func = content.find("def send_pyq_q(uid, msg_id=None):")
    end_func = content.find("def clean_math", start_func)
    if end_func != -1:
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

    phase_name = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
    diff_raw = q.get('difficulty', 5)
    try:
        diff_num = int(float(diff_raw))
        diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
        diff_str = f"{diff_num}/10 ({diff_text})"
    except:
        diff_str = str(diff_raw)
        
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {diff_str}"
    
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
        _b().send_message(uid, f"❌ Failed to send photo: {e}\\nPath: {q['img']}")
"""
        content = content[:start_func] + new_func + content[end_func:]
        print("✅ Upgraded send_pyq_q with image checks.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py syntax OK.")
except SyntaxError as e:
    print("❌ Syntax Error:", e)
