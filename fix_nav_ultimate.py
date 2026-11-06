import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Delete old _build_pyq_nav and replace with clean version
nav_start = content.find("def _build_pyq_nav(uid):")
if nav_start != -1:
    nav_end = content.find("def send_pyq_q", nav_start)
    if nav_end == -1: nav_end = content.find("\ndef ", nav_start + 20)
    
    new_nav_func = '''def _build_pyq_nav(uid):
    st = _state.get(uid, {})
    q_list = st.get("pyq_questions", [])
    current = st.get("pyq_index", 0)
    if not q_list: return None

    if st.get("pyq_is_paper"):
        kb = InlineKeyboardMarkup(row_width=6)
        row = []
        for i in range(len(q_list)):
            if i == current: emoji = "⚪"
            elif q_list[i].get("_attempted"): emoji = "🟢"
            elif q_list[i].get("_skipped"): emoji = "⚫"
            else: emoji = "▫️"
            row.append(InlineKeyboardButton(f"{emoji}{i+1}", callback_data=f"nav_jump:{i}"))
            if len(row) == 6:
                kb.row(*row)
                row = []
        if row: kb.row(*row)
        return kb

    view = st.get("nav_view", "topics")
    if view == "topics":
        topics = {}
        for q in q_list:
            t = q.get("subtopic", "General")
            topics[t] = topics.get(t, 0) + 1
        st["_nav_topics"] = list(topics.keys())
        kb = InlineKeyboardMarkup(row_width=2)
        for idx, t in enumerate(st["_nav_topics"]):
            kb.add(InlineKeyboardButton(f"📁 {t[:20]} ({topics[t]})", callback_data=f"nav_topic:{idx}"))
        return kb
    elif view == "years":
        topic = st.get("nav_topic", "")
        years = {}
        for q in q_list:
            if q.get("subtopic") != topic: continue
            src = q.get("source", "")
            m = re.search(r'(20\\d\\d)', src)
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
                m = re.search(r'(20\\d\\d)', src)
                if (m.group(1) if m else "?") != year: continue
            matching.append((i, q))
        kb = InlineKeyboardMarkup(row_width=6)
        row = []
        for i, q in matching:
            if i == current: emoji = "⚪"
            elif q.get("_attempted"): emoji = "🟢"
            elif q.get("_skipped"): emoji = "⚫"
            else: emoji = "▫️"
            row.append(InlineKeyboardButton(f"{emoji}{i+1}", callback_data=f"nav_jump:{i}"))
            if len(row) == 6:
                kb.row(*row)
                row = []
        if row: kb.row(*row)
        kb.add(InlineKeyboardButton("🔙 Years", callback_data="nav_back_year"))
        return kb
    return None

'''
    content = content[:nav_start] + new_nav_func + content[nav_end:]

# 2. Fix the navigation handlers inside handle_buttons
# We look for the block and replace it
old_nav_block = '''if data.startswith("nav_jump:"):
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
            return'''

new_nav_block = '''if data.startswith("nav_jump:"):
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
            return

        if data == "nav_topics":
            state["nav_view"] = "topics"
            state["nav_topic"] = None
            state["nav_year"] = None
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=_build_pyq_nav(uid))
            return

        if data == "nav_back_year":
            state["nav_view"] = "years"
            state["nav_year"] = None
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=_build_pyq_nav(uid))
            return

        if data.startswith("nav_topic:"):
            idx_t = int(data.split(":")[1])
            topics_list = state.get("_nav_topics", [])
            if idx_t < len(topics_list):
                state["nav_topic"] = topics_list[idx_t]
                state["nav_view"] = "years"
                state["nav_year"] = None
                _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=_build_pyq_nav(uid))
            return

        if data.startswith("nav_year:"):
            state["nav_year"] = data.split(":", 1)[1]
            state["nav_view"] = "questions"
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=_build_pyq_nav(uid))
            return'''

if old_nav_block in content:
    content = content.replace(old_nav_block, new_nav_block)
    print("✅ Navigation handlers replaced exactly.")
else:
    print("⚠️ Navigation handler block not found. It might already be patched.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py syntax is PERFECT.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
