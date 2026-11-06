import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Add Navigation Bar Builder (insert before send_pyq_q)
if "def _build_pyq_nav(uid):" not in content:
    nav_builder = """
def _build_pyq_nav(uid):
    st = _state.get(uid, {})
    q_list = st.get("pyq_questions", [])
    current = st.get("pyq_index", 0)
    if not q_list: return None
    kb = InlineKeyboardMarkup(row_width=5)
    row = []
    for i, q in enumerate(q_list[:50]): # Show max 50 buttons to avoid giant menus
        if i == current: emoji = "⚪"
        elif q.get("_attempted"): emoji = "🟢"
        elif q.get("_skipped"): emoji = "⚫"
        else: emoji = "▫️"
        row.append(InlineKeyboardButton(emoji, callback_data=f"nav_jump:{i}"))
        if len(row) == 5:
            kb.row(*row)
            row = []
    if row: kb.row(*row)
    return kb

"""
    marker = "def send_pyq_q(uid, msg_id=None):"
    content = content.replace(marker, nav_builder + "\n" + marker, 1)

# 2. Replace send_pyq_q entirely
start = content.find("def send_pyq_q(uid, msg_id=None):")
end = content.find("\ndef ", start + 20)
if end == -1: end = content.find("\n@bot", start)

new_send = '''def send_pyq_q(uid, msg_id=None):
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
            msg = _b().send_photo(uid, f, caption=base_cap, parse_mode="HTML", reply_markup=kb)
            state["pyq_photo_msg_id"] = msg.message_id
    except Exception as e:
        _b().send_message(uid, f"❌ Image missing: {e}")
        return

    # TIMER AS SEPARATE MESSAGE
    t_msg = _b().send_message(uid, "⏱ 0s")
    state["pyq_timer_msg_id"] = t_msg.message_id

    # NAVIGATION BAR AS SEPARATE MESSAGE
    nav_kb = _build_pyq_nav(uid)
    if nav_kb:
        n_msg = _b().send_message(uid, "🧭 <b>Navigation:</b>", parse_mode="HTML", reply_markup=nav_kb)
        state["pyq_nav_msg_id"] = n_msg.message_id

    # Timer thread (updates separate message)
    import threading
    def _timer(uid_, t_msg_id):
        for i in range(1, 300):
            time.sleep(1)
            st = _state.get(uid_, {})
            if not st.get("pyq_timer_active"): break
            try: _b().edit_message_text(f"⏱ {i}s", chat_id=uid_, message_id=t_msg_id)
            except: pass
    threading.Thread(target=_timer, args=(uid, t_msg.message_id), daemon=True).start()

'''
content = content[:start] + new_send + content[end:]

# 3. Replace f_save / f_skip block
save_match = re.search(r'\n(\s*)elif data in \("f_save", "f_skip"\):', content)
if not save_match:
    save_match = re.search(r'\n(\s*)elif data == "f_save":', content)

if save_match:
    indent = save_match.group(1)
    start_pos = save_match.start() + 1
    rest = content[start_pos:]
    end_match = re.search(r'\n' + re.escape(indent) + r'elif ', rest)
    if end_match:
        end_pos = start_pos + end_match.start()
        
        I1 = indent + "    "
        I2 = I1 + "    "
        
        new_save = f'''{indent}elif data in ("f_save", "f_skip"):
{I1}if data == "f_save":
{I2}if state.get("processing"): return
{I2}if state.get("selected") is None:
{I2}    _b().answer_callback_query(call.id, "⚠️ Select an option first")
{I2}    return
{I2}state["processing"] = True
{I2}state["pyq_timer_active"] = False
{I2}state["q"]["_attempted"] = True
{I2}
{I2}# Delete timer & nav
{I2}try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
{I2}except: pass
{I2}try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
{I2}except: pass
{I2}try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
{I2}except: pass
{I2}
{I2}is_correct = state["selected"] == state["q"].get("correct_index", 0)
{I2}if is_correct: state["correct"] = state.get("correct", 0) + 1
{I2}else: state["wrong"] = state.get("wrong", 0) + 1
{I2}
{I2}time_taken = int(time.time() - state.get("q_start_time", time.time()))
{I2}ideal = state["q"].get("ideal_time", 60)
{I2}correct_letter = chr(65 + state["q"].get("correct_index", 0))
{I2}
{I2}if is_correct:
{I2}    result_msg = f"✅ <b>Correct!</b>\\n⏱ {{time_taken}}s / Ideal {{ideal}}s"
{I2}else:
{I2}    result_msg = f"❌ <b>Wrong.</b>\\nCorrect: <b>{{correct_letter}}</b>\\n⏱ {{time_taken}}s / Ideal {{ideal}}s"
{I2}
{I2}kb = InlineKeyboardMarkup(row_width=2)
{I2}kb.add(InlineKeyboardButton("💡 AI Solution", callback_data="f_solution"), InlineKeyboardButton("▶️ Next", callback_data="f_next_q"))
{I2}kb.add(InlineKeyboardButton("💬 Doubt", callback_data="f_doubt"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
{I2}
{I2}_b().send_message(uid, result_msg, parse_mode="HTML", reply_markup=kb)
{I2}state["processing"] = False
{I1}else:
{I2}state["skipped"] = state.get("skipped", 0) + 1
{I2}state["pyq_timer_active"] = False
{I2}state["q"]["_skipped"] = True
{I2}try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
{I2}except: pass
{I2}try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
{I2}except: pass
{I2}try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
{I2}except: pass
{I2}state["pyq_index"] += 1
{I2}send_pyq_q(uid)
'''
        content = content[:start_pos] + new_save + content[end_pos:]

# 4. Add f_solution and nav_jump handlers
if 'data == "f_solution"' not in content:
    marker = 'elif data == "f_next_q":'
    sol_handler = '''elif data == "f_solution":
            try: _b().answer_callback_query(call.id, "Generating...")
            except: pass
            load = _b().send_message(uid, "🧠 <i>Generating solution...</i>")
            try:
                from c40_vision_ai import get_ai_solution
                q_text = state.get("q", {}).get("q_text", "")
                sol = get_ai_solution(q_text)
                _b().edit_message_text(sol, chat_id=uid, message_id=load.message_id, parse_mode="Markdown")
            except Exception as e:
                _b().edit_message_text(f"❌ {e}", chat_id=uid, message_id=load.message_id)
            
            # Re-show navigation bar after solution
            nav_kb = _build_pyq_nav(uid)
            if nav_kb:
                n_msg = _b().send_message(uid, "🧭 <b>Navigation:</b>", parse_mode="HTML", reply_markup=nav_kb)
                state["pyq_nav_msg_id"] = n_msg.message_id
            
        elif data.startswith("nav_jump:"):
            target = int(data.split(":")[1])
            state["pyq_timer_active"] = False
            try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
            except: pass
            try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
            except: pass
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            state["pyq_index"] = target
            send_pyq_q(uid)
            
        elif data == "f_next_q":'''
    content = content.replace(marker, sol_handler, 1)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py patched perfectly (Timer separate, Nav bar separate, Delete on save).")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
