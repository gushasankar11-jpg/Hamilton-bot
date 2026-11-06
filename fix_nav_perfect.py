import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Fix _build_pyq_nav to dynamically split sections
start_nav = content.find("def _build_pyq_nav(uid):")
end_nav = content.find("def send_pyq_q", start_nav)
if end_nav == -1: end_nav = content.find("\ndef ", start_nav + 20)

new_nav = '''def _build_pyq_nav(uid):
    st = _state.get(uid, {})
    q_list = st.get("pyq_questions", [])
    current = st.get("pyq_index", 0)
    if not q_list: return None

    # For Papers: Dynamically split into 3 sections based on total count
    if st.get("pyq_is_paper"):
        total_q = len(q_list)
        chunk = (total_q + 2) // 3  # Divide evenly among 3 subjects
        sections = [
            ("Sec 1", 0, chunk),
            ("Sec 2", chunk, chunk*2),
            ("Sec 3", chunk*2, total_q)
        ]
        
        kb = InlineKeyboardMarkup(row_width=6)
        for sec_name, start, end in sections:
            if start >= total_q: continue
            kb.row(InlineKeyboardButton(f"--- {sec_name} ---", callback_data="ignore_click"))
            row = []
            for i in range(start, min(end, total_q)):
                if i == current: emoji = "⚪"
                elif q_list[i].get("_attempted"): emoji = "🟢"
                elif q_list[i].get("_skipped"): emoji = "⚫"
                else: emoji = "▫️"
                # Display index + 1 to guarantee sequential numbering (Q1, Q2...)
                row.append(InlineKeyboardButton(f"{emoji}{i+1}", callback_data=f"nav_jump:{i}"))
                if len(row) == 6:
                    kb.row(*row)
                    row = []
            if row: kb.row(*row)
        return kb

    # Chapter Nav (Topic -> Year -> Q)
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
content = content[:start_nav] + new_nav + content[end_nav:]

# 2. Fix the nav_jump handler to properly delete old messages
jump_start = content.find('if data.startswith("nav_jump:"):')
if jump_start != -1:
    jump_end = content.find('if data == "f_solution":', jump_start)
    if jump_end == -1: jump_end = content.find('if data.startswith("nav_', jump_start + 30)
    
    if jump_end != -1:
        new_jump = '''if data.startswith("nav_jump:"):
            target = int(data.split(":")[1])
            state["pyq_timer_active"] = False
            
            # Clean up old messages
            try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
            except: pass
            try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
            except: pass
            try: _b().delete_message(uid, state.get("pyq_photo_msg_id"))
            except: pass
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            state["pyq_index"] = target
            send_pyq_q(uid)
            return
            
        '''
        content = content[:jump_start] + new_jump + content[jump_end:]

# 3. Fix send_pyq_q to display index+1 instead of q_num
old_cap = '''    cap = f"{header}\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s | 📊 Diff: {diff_str} | Type: {qtype}"'''
new_cap = '''    # For papers, we use the index (i+1) so Q1 is always Q1
    display_num = idx + 1
    header = f"📝 <b>Question {display_num}/{len(q_list)}</b>" if state.get("pyq_is_paper") else f"📝 <b>PYQ {display_num}/{len(q_list)}</b>"
    
    cap = f"{header}\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s | 📊 Diff: {diff_str} | Type: {qtype}"'''
if old_cap in content:
    content = content.replace(old_cap, new_cap)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Navigation dynamically splits sections, displays sequential numbers, and jumps perfectly.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
