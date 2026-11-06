import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# ==========================================================
# FIX 1: Remove 'from c40_vision_ai import X' — call directly
# ==========================================================
content = content.replace("from c40_vision_ai import get_ai_solution\n                ", "")
content = content.replace("from c40_vision_ai import get_ai_solution\n            ", "")
content = content.replace("from c40_vision_ai import get_ai_solution", "")
content = content.replace("from c40_vision_ai import ai_scan_questions", "")
print("✅ FIX 1: Removed bad module imports (functions are in global namespace)")

# ==========================================================
# FIX 2: Replace _build_pyq_nav with hierarchical version
# ==========================================================
nav_start = content.find("def _build_pyq_nav(uid):")
if nav_start != -1:
    nav_end = content.find("\ndef ", nav_start + 20)
    if nav_end == -1: nav_end = nav_start + 800
    
    new_nav = '''def _build_pyq_nav(uid):
    """Hierarchical navigation: Topics → Years → Questions"""
    st = _state.get(uid, {})
    q_list = st.get("pyq_questions", [])
    current = st.get("pyq_index", 0)
    view = st.get("nav_view", "topics")
    if not q_list: return None

    import re as _re

    if view == "topics":
        topics = {}
        for q in q_list:
            t = q.get("subtopic", "General")
            topics[t] = topics.get(t, 0) + 1
        st["_nav_topics"] = list(topics.keys())
        kb = InlineKeyboardMarkup(row_width=2)
        for idx, t in enumerate(st["_nav_topics"]):
            kb.add(InlineKeyboardButton(f"📁 {t[:25]} ({topics[t]})", callback_data=f"nav_topic:{idx}"))
        return kb

    elif view == "years":
        topic = st.get("nav_topic", "")
        years = {}
        for q in q_list:
            if q.get("subtopic") != topic: continue
            src = q.get("source", "")
            m = _re.search(r'(20\\d\\d)', src)
            y = m.group(1) if m else "?"
            years[y] = years.get(y, 0) + 1
        kb = InlineKeyboardMarkup(row_width=3)
        for y in sorted(years.keys(), reverse=True):
            kb.add(InlineKeyboardButton(f"📅 {y} ({years[y]})", callback_data=f"nav_year:{y}"))
        kb.add(InlineKeyboardButton("🔙 Topics", callback_data="nav_topics"))
        return kb

    elif view == "questions":
        topic = st.get("nav_topic", "")
        year = st.get("nav_year", "")
        matching = []
        for i, q in enumerate(q_list):
            if topic and q.get("subtopic") != topic: continue
            if year:
                src = q.get("source", "")
                m = _re.search(r'(20\\d\\d)', src)
                y = m.group(1) if m else "?"
                if y != year: continue
            matching.append((i, q))
        kb = InlineKeyboardMarkup(row_width=6)
        row = []
        for i, q in matching:
            if i == current: emoji = "⚪"
            elif q.get("_attempted"): emoji = "🟢"
            elif q.get("_skipped"): emoji = "⚫"
            else: emoji = "▫️"
            qtype = q.get("type", "mcq")
            type_char = "N" if qtype == "numerical" else "M"
            row.append(InlineKeyboardButton(f"{emoji}{i+1}{type_char}", callback_data=f"nav_jump:{i}"))
            if len(row) == 6:
                kb.row(*row); row = []
        if row: kb.row(*row)
        kb.add(InlineKeyboardButton("🔙 Years", callback_data="nav_back_year"))
        return kb

    return None

'''
    content = content[:nav_start] + new_nav + content[nav_end:]
    print("✅ FIX 2: Hierarchical nav builder installed")

# ==========================================================
# FIX 3: Update send_pyq_q — separate timer + nav message
# ==========================================================
send_start = content.find("def send_pyq_q(uid, msg_id=None):")
send_end = content.find("\ndef ", send_start + 20)
if send_end == -1: send_end = content.find("\n@bot", send_start)

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
            _b().send_message(uid, "🎓 <b>Priority completed.</b> Continue normal?", reply_markup=kb)
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

    # Clean up old timer & nav from previous question
    try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
    except: pass
    try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
    except: pass

    is_num = (idx > 0 and idx % 5 == 0)
    diff = q.get('difficulty', 5)
    diff_str = f"{diff}/10" if isinstance(diff, (int, float)) else str(diff)
    ideal = q.get('ideal_time', 90)
    qtype = q.get('type', 'mcq').upper()

    if is_num:
        state["pyq_is_numerical"] = True
        state["waiting_for_pyq_numeric"] = True
        cap = f"🔢 <b>PYQ {idx+1}/{len(q_list)} (NUMERICAL)</b>\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s\\n<i>Type your numerical answer.</i>"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    else:
        phase = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
        cap = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase})</b>\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s | 📊 Diff: {diff_str} | Type: {qtype}"
        kb = InlineKeyboardMarkup(row_width=4)
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=cap, parse_mode="HTML", reply_markup=kb)
            state["pyq_photo_msg_id"] = msg.message_id
    except Exception as e:
        _b().send_message(uid, f"❌ Image missing: {e}")
        return

    # SEPARATE TIMER MESSAGE
    t_msg = _b().send_message(uid, "⏱ 0s")
    state["pyq_timer_msg_id"] = t_msg.message_id

    # SEPARATE NAVIGATION MESSAGE
    state["nav_view"] = "topics"
    state["nav_topic"] = None
    state["nav_year"] = None
    nav_kb = _build_pyq_nav(uid)
    if nav_kb:
        n_msg = _b().send_message(uid, "🧭 <b>Navigation:</b>", parse_mode="HTML", reply_markup=nav_kb)
        state["pyq_nav_msg_id"] = n_msg.message_id

    # Timer thread
    import threading
    def _timer(uid_, t_msg_id):
        for i in range(1, 301):
            time.sleep(1)
            st = _state.get(uid_, {})
            if not st.get("pyq_timer_active"): break
            try: _b().edit_message_text(f"⏱ {i}s", chat_id=uid_, message_id=t_msg_id)
            except: pass
    threading.Thread(target=_timer, args=(uid, t_msg.message_id), daemon=True).start()

'''
content = content[:send_start] + new_send + content[send_end:]
print("✅ FIX 3: send_pyq_q updated (separate timer + nav)")

# ==========================================================
# FIX 4: Add nav callbacks (topics / topic / year / back)
# ==========================================================
if 'data == "nav_topics"' not in content:
    marker = 'elif data.startswith("nav_jump:")'
    nav_handlers = '''elif data == "nav_topics":
            state["nav_view"] = "topics"
            state["nav_topic"] = None
            state["nav_year"] = None
            nav_kb = _build_pyq_nav(uid)
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=nav_kb)
            except: pass

        elif data == "nav_back_year":
            state["nav_view"] = "years"
            state["nav_year"] = None
            nav_kb = _build_pyq_nav(uid)
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=nav_kb)
            except: pass

        elif data.startswith("nav_topic:"):
            idx_t = int(data.split(":")[1])
            topics_list = state.get("_nav_topics", [])
            if idx_t < len(topics_list):
                state["nav_topic"] = topics_list[idx_t]
                state["nav_view"] = "years"
                state["nav_year"] = None
                nav_kb = _build_pyq_nav(uid)
                try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=nav_kb)
                except: pass

        elif data.startswith("nav_year:"):
            state["nav_year"] = data.split(":", 1)[1]
            state["nav_view"] = "questions"
            nav_kb = _build_pyq_nav(uid)
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=nav_kb)
            except: pass

        elif data.startswith("nav_jump:")'''
    content = content.replace(marker, nav_handlers, 1)
    print("✅ FIX 4: Nav drill-down callbacks added")

# ==========================================================
# FIX 5: Update nav_jump to use hierarchical state
# ==========================================================
jump_start = content.find('elif data.startswith("nav_jump:"):')
if jump_start != -1:
    jump_end = content.find('\n        elif ', jump_start + 30)
    if jump_end != -1:
        new_jump = '''elif data.startswith("nav_jump:"):
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
        '''
        content = content[:jump_start] + new_jump + content[jump_end:]
        print("✅ FIX 5: nav_jump updated")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("\n✅ ALL FIXES APPLIED — Syntax OK")
except SyntaxError as e:
    print(f"\n❌ SYNTAX ERROR: {e}")
