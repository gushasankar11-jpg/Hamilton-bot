import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Inject the helper function to send PYQ questions
helper_code = """
def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    if idx >= len(q_list):
        _b().send_message(uid, "🏁 <b>Chapter Complete!</b> All PYQs finished.")
        state["mode"] = "practice"
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False

    # Metadata overlay (Ideal Time & Difficulty)
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)}</b>\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {q.get('difficulty', 'Medium')}"
    
    # Your exact 9-Type button UI
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

if "def send_pyq_q(uid, msg_id=None):" not in content:
    marker = "@bot.callback_query_handler(func=lambda call: call.data.startswith(\"f_\"))"
    if marker in content:
        content = content.replace(marker, helper_code + "\n" + marker)
    else:
        content += "\n" + helper_code

# 2. Replace the old "send all pages" loop with the new PYQ engine
old_pyq = '''        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json, os
            with open("data/pyq_db.json") as f: db = json.load(f)
            folder = db["practice"][subj][ch]["path"]
            pages = db["practice"][subj][ch]["pages"]

            _b().edit_message_text(f"⏳ Sending {pages} pages for <b>{ch}</b>...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")

            for i in range(1, pages + 1):
                possible = [f"page-{i:02d}.png", f"page-{i}.png", f"page-{i:03d}.png"]
                for p_name in possible:
                    p_path = os.path.join(folder, p_name)
                    if os.path.exists(p_path):
                        _b().send_photo(uid, open(p_path, "rb"))
                        time.sleep(1)
                        break
            _b().send_message(uid, "✅ All pages sent. Now solve them on paper.")
            cmd_exam(call.message)'''

new_pyq = '''        elif data.startswith("f_pyq_ch:"):
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
            state["pyq_questions"] = q_list
            state["pyq_index"] = 0
            _b().edit_message_text(f"⏳ Loading PYQs for <b>{ch}</b>...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
            send_pyq_q(uid, call.message.message_id)'''

if old_pyq in content:
    content = content.replace(old_pyq, new_pyq)

# 3. Patch f_next_q to check if we are in PYQ mode
old_next = '''        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
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

if old_next in content:
    content = content.replace(old_next, new_next)

# Save with syntax check
try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ PATCHED c04_exam.py: PYQ Engine integrated with UI.")
except SyntaxError as e:
    print("❌ SYNTAX ERROR:", e)

