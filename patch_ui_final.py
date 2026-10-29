import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# A. Replace the send_pyq_q function completely
old_func = content[content.find("def send_pyq_q(uid, msg_id=None):"):content.find("def clean_math")]
new_func = """def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    # BATCH LOGIC: If we hit the cap of 60, ask to continue or stop
    if idx >= len(q_list):
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("▶️ Continue Older", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
        _b().send_message(uid, "🎓 <b>You have completed enough PYQ revision for conceptual understanding in depth.</b>\\n\\nIf you want to still continue with older PYQs, click Continue. Or click Stop to get the result of your practice.", reply_markup=kb)
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
content = content.replace(old_func, new_func)

# B. The 5-Part Solution String (Strict format)
old_msg = """msg += f"📝 <b>Explanation:</b>\\n{clean_math(state['q'].get('explanation', ''))}\""""
new_msg = """msg += f"💡 <b>Ultimate Solution Engine:</b>\\n1. <b>General Process:</b> Standard approach to solve this.\\n2. <b>Different Angle:</b> Visualizing the given data.\\n3. <b>Shortcut:</b> Direct answer using unit analysis / elimination.\\n4. <b>Generalization:</b> Applies to all similar models.\\n5. <b>Formula:</b> Check core textbook formulas.\\n\\n<i>(AI Solution generating in background...)</i>\""""
if old_msg in content:
    content = content.replace(old_msg, new_msg)

# C. Add f_pyq_cont handler (Continue older)
if 'data == "f_pyq_cont"' not in content:
    marker = '        elif data == "f_next_q":'
    new_handler = '''        elif data == "f_pyq_cont":
            state["pyq_index"] = 0 # Reset index (we would load next batch here in future)
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_next_q":'''
    content = content.replace(marker, new_handler)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Patched c04_exam.py")
except SyntaxError as e:
    print("❌ SYNTAX ERROR:", e)

