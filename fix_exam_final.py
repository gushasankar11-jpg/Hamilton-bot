import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Delete any existing f_ handlers to stop duplicates
pattern = re.compile(r'@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("f_"\)\)\s*\ndef handle_buttons\(call\):.*?(?=\n@bot\.|\ndef |\nclass |\Z)', re.DOTALL)
content = pattern.sub('', content)
print("✅ Removed old duplicate handlers.")

# 2. Add the Global Cache mechanism at the top of the file
if "_PYQ_CACHE" not in content:
    cache_code = '''
import json, os, time, threading

_PYQ_CACHE = None
_PYQ_CACHE_TIME = 0

def get_pyq_db():
    """Loads the DB into memory. Only reads from disk if the file is newer."""
    global _PYQ_CACHE, _PYQ_CACHE_TIME
    db_path = "data/pyq_master.json"
    try:
        mtime = os.path.getmtime(db_path)
    except:
        mtime = 0
        
    if _PYQ_CACHE is None or mtime > _PYQ_CACHE_TIME:
        print("[CACHE] Loading pyq_master.json into memory...")
        try:
            with open(db_path, "r") as f:
                _PYQ_CACHE = json.load(f)
            _PYQ_CACHE_TIME = mtime
        except Exception as e:
            print(f"[CACHE] Error loading DB: {e}")
            if _PYQ_CACHE is None: _PYQ_CACHE = {"papers": {}, "practice": {}, "practice_adv": {}}
    return _PYQ_CACHE
'''
    content = content.replace("def _b(): return", cache_code + "\ndef _b(): return", 1)
    print("✅ Added Global Cache.")

# 3. Build the new, clean Master Handler
master_handler = '''
@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]
    db = get_pyq_db()

    # --- MAIN MENU ---
    if data.startswith("f_mode:"):
        mode = data.split(":")[1]
        _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
        
        if mode == "pyq":
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(InlineKeyboardButton("📖 JEE Main Chapter-wise", callback_data="f_pyq:practice"))
            kb.add(InlineKeyboardButton("🔥 JEE Adv Chapter-wise", callback_data="f_pyq_adv:practice"))
            kb.add(InlineKeyboardButton("📝 JEE Main Papers", callback_data="f_pyq_papers_cat:JEE MAIN"))
            kb.add(InlineKeyboardButton("🔥 JEE Adv Papers", callback_data="f_pyq_papers_cat:JEE ADV"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text("🔍 <b>PYQ Explorer</b>\\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            return

        kb = InlineKeyboardMarkup(row_width=3)
        kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
        _b().edit_message_text(f"📚 <b>{mode.capitalize()} Mode</b>\\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    # --- BACK BUTTON ---
    if data.startswith("f_back:"):
        target = data.split(":")[1]
        if target == "main":
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"), InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
            kb.add(InlineKeyboardButton("📝 Test", callback_data="f_mode:test"), InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"))
            _b().edit_message_text("📚 <b>Exam Engine</b>\\nSelect Mode:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    # --- PAPER NAVIGATION ---
    if data.startswith("f_pyq_papers_cat:"):
        cat = data.split(":", 1)[1]
        papers = db.get("papers", {})
        
        years = {}
        for p_name, p_data in papers.items():
            if p_data.get("exam_type", "JEE MAIN") == cat:
                y = p_data.get("year", "Unknown")
                years[y] = years.get(y, 0) + 1
                
        if not years:
            _b().answer_callback_query(call.id, f"⏳ {cat} papers are still extracting.", show_alert=True)
            return
            
        kb = InlineKeyboardMarkup(row_width=3)
        for y in sorted(years.keys(), reverse=True):
            kb.add(InlineKeyboardButton(f"📅 {y} ({years[y]})", callback_data=f"f_pyq_paper_year:{cat}:{y}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
        _b().edit_message_text(f"📝 <b>{cat} - Select Year</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_paper_year:"):
        _, cat, year = data.split(":", 2)
        papers = db.get("papers", {})
        
        kb = InlineKeyboardMarkup(row_width=1)
        for p_name, p_data in papers.items():
            if p_data.get("exam_type") == cat and p_data.get("year") == year:
                short = p_name.replace(f"{cat} ", "").replace(f"{year} ", "")
                kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_pyq_paper:{p_name}"))
        
        kb.add(InlineKeyboardButton("🔙 Years", callback_data=f"f_pyq_papers_cat:{cat}"))
        _b().edit_message_text(f"📝 <b>{cat} {year} - Select Paper</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_paper:"):
        paper_name = data.split(":", 1)[1]
        paper_data = db.get("papers", {}).get(paper_name)
        if not paper_data:
            _b().answer_callback_query(call.id, "Paper not found.", show_alert=True)
            return
        
        state["mode"] = "pyq"
        state["subj"] = "Full Paper"
        state["chapter"] = paper_name
        state["pyq_phase"] = "priority"
        state["pyq_questions"] = paper_data.get("questions", [])
        state["pyq_normal"] = []
        state["pyq_index"] = 0
        state["pyq_is_paper"] = True
        
        try: _b().delete_message(uid, call.message.message_id)
        except: pass
        
        # RUN COUNTDOWN IN BACKGROUND THREAD
        def run_countdown():
            cdown = _b().send_message(uid, "📄 <b>Starting Paper Test...</b>\\n\\n5...")
            for n in [4, 3, 2, 1]:
                time.sleep(1)
                try: _b().edit_message_text(f"📄 <b>Starting Paper Test...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                except: pass
            time.sleep(1)
            try: _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
            except: pass
            time.sleep(0.5)
            send_pyq_q(uid)
            
        threading.Thread(target=run_countdown, daemon=True).start()
        return

    # --- CHAPTER NAVIGATION ---
    if data.startswith("f_pyq_sub:"):
        subj = data.split(":")[1]
        state["pyq_subj"] = subj
        state["is_adv"] = False
        kb = InlineKeyboardMarkup(row_width=1)
        chapters = list(db.get("practice", {}).get(subj, {}).keys())
        for ch in chapters:
            kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
        _b().edit_message_text(f"📖 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("f_pyq_ch:"):
        ch = data.split(":", 1)[1]
        subj = state.get("pyq_subj")
        q_data = db.get("practice", {}).get(subj, {}).get(ch)
        if not q_data:
            _b().answer_callback_query(call.id, "No questions found.", show_alert=True)
            return

        state["mode"] = "pyq"
        state["subj"] = subj
        state["chapter"] = ch
        state["pyq_phase"] = "priority"
        state["pyq_questions"] = q_data.get("priority", [])
        state["pyq_normal"] = q_data.get("normal", [])
        state["pyq_index"] = 0
        state["pyq_is_paper"] = False
        
        try: _b().delete_message(uid, call.message.message_id)
        except: pass
        send_pyq_q(uid)
        return

    # --- NAVIGATION BAR (During test) ---
    if data.startswith("nav_jump:"):
        target = int(data.split(":")[1])
        state["pyq_timer_active"] = False
        try: _b().delete_message(uid, state.get("pyq_timer_msg_id"))
        except: pass
        try: _b().delete_message(uid, state.get("pyq_nav_msg_id"))
        except: pass
        state["pyq_index"] = target
        send_pyq_q(uid)
        return
'''

content += "\n\n" + master_handler + "\n"
try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py rebuilt perfectly.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
