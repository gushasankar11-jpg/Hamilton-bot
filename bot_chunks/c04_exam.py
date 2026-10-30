import json
import time
import threading
import sys
import re
import html
import random
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

_state = {}
def _b(): return sys.modules['__main__'].bot


def format_ultimate_solution(q):
    exp = q.get('explanation', '')
    if not exp: return "💡 <i>Solution generation pending for this PYQ...</i>"
    return f"💡 <b>Ultimate Solution Engine:</b>\n1. <b>General Process:</b> ...\n2. <b>Different Angle:</b> ...\n3. <b>Shortcut:</b> ...\n4. <b>Generalize:</b> ...\n5. <b>Formula:</b> ...\n\n<i>(AI extracting from PDF text...)</i>\n\n{clean_math(exp)}"

def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    if not text: return ""
    t = str(text)
    t = html.unescape(t).replace("*", "").replace("_", " ")
    t = t.replace("\\alpha", "α").replace("\\beta", "β").replace("\\theta", "θ").replace("\\pi", "π")
    t = t.replace("\\times", "×").replace("\\cdot", "•").replace("\\sqrt", "√").replace("\\infty", "∞")
    t = t.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "").replace("$", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    sup = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    t = re.sub(r'\^([0-9+\-]+)', lambda m: m.group(1).translate(sup), t)
    t = re.sub(r'_([0-9]+)', lambda m: m.group(1).translate(sub), t)
    return t.strip()

def _extract_chapters(raw_data):
    chapters = set()
    if isinstance(raw_data, dict):
        for k, v in raw_data.items():
            if isinstance(v, dict) and "chapter" in v: chapters.add(v["chapter"])
            else: chapters.add(k)
    elif isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                ch = item.get("chapter") or item.get("name") or item.get("topic")
                if ch: chapters.add(ch)
    return sorted(list(chapters))

def _animate_gen(uid, msg_id, count):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if not state.get("generating"): return
        try: _b().edit_message_text(f"⏳ Generating Q{count}... ({elapsed}s)", chat_id=uid, message_id=msg_id, parse_mode="HTML")
        except: pass

def _run_floating_timer(uid, timer_msg_id, question_msg_id):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id)
            except: pass
            return
        try: 
            _b().edit_message_text(f"⏱️ <b>Time Taken:</b> {elapsed}s", chat_id=uid, message_id=timer_msg_id, parse_mode="HTML")
        except: pass

def _strip_old_buttons(uid):
    state = _state.get(uid, {})
    old_msg = state.get("msg_id")
    if old_msg:
        try: _b().edit_message_reply_markup(uid, old_msg, reply_markup=None)
        except: pass
    state["msg_id"] = None

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
        InlineKeyboardButton("📝 Test", callback_data="f_mode:test")
    )
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(message.chat.id, "🎓 <b>Exam Center</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['conceptual'])
def cmd_conceptual(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"),
        InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional")
    )
    _b().send_message(message.chat.id, "🧠 <b>Concept Mastery</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

def _show_chapters(uid, msg_id):
    state = _state[uid]
    chapters = state.get("chapters", [])
    page = state.get("page", 0)
    start, end = page * 5, (page + 1) * 5
    chunk = chapters[start:end]
    
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(chunk):
        kb.add(InlineKeyboardButton(f"{start + i + 1}. {ch[:25]}", callback_data=f"f_ch:{ch}"))
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="f_page:-1"))
    if end < len(chapters): nav.append(InlineKeyboardButton("Next ➡️", callback_data="f_page:1"))
    if nav: kb.row(*nav)
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="f_back:sub"))
    
    try: _b().edit_message_text(f"📚 <b>Select Chapter:</b>\n(Showing {start+1}-{min(end, len(chapters))} of {len(chapters)})", chat_id=uid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]

    if data.startswith("f_ans:") and state.get("processing"): return
        
    try:
        if data.startswith("f_mode:"):
            mode = data.split(":")[1]
            _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
            
            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )
                kb.add(InlineKeyboardButton("🚧 JEE Adv (Coming Soon)", callback_data="f_soon"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("Physics", callback_data="f_sub:Physics"),
                InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"),
                InlineKeyboardButton("Maths", callback_data="f_sub:Maths")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "f_soon":
            _b().answer_callback_query(call.id, "Coming Soon!", show_alert=True)

        elif data.startswith("f_pyq:"):
            ptype = data.split(":")[1]
            import json
            try:
                with open("data/pyq_db.json") as f: db = json.load(f)
            except: db = {"practice": {}, "papers": {}}

            if ptype == "practice":
                kb = InlineKeyboardMarkup(row_width=3)
                for subj in db.get("practice", {}).keys():
                    kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📖 <b>PYQ Practice</b>\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            
            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                years = list(db.get("papers", {}).keys())
                if not years:
                    _b().answer_callback_query(call.id, "No papers uploaded yet.")
                    return
                for yr in years:
                    kb.add(InlineKeyboardButton(yr, callback_data=f"f_pyq_yr:{yr}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\nSelect Year:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json, re
            with open("data/pyq_db.json") as f: db = json.load(f)
            chapters = list(db.get("practice", {}).get(subj, {}).keys())

            # --- Syllabus-order anchor map (PDF coarse chapter -> syllabus fine chapter) ---
            _PYQ_OVERRIDES = {
                "Atoms and Nuclei": "Atomic Physics",
                "Capacitor": "Capacitor and Capacitance",
                "Center of Mass and Collision": "System of Particles and Centre of Mass",
                "Current Electricity": "Electric Current and Circuits",
                "Dual Nature of Radiation": "Dual Nature of Radiation and Matter",
                "Electrostatics": "Coulomb's Law and Electric Field",
                "Geometrical Optics": "Geometrical Optics: Part 1",
                "Heat and Thermodynamics": "Thermodynamics",
                "Laws of Motion": "Newton's Laws of Motion (Without Friction)",
                "Magnetic Effect of Current": "Magnetic Field and Magnetic Forces",
            }

            _syl_list = []
            try:
                _syl = json.load(open(f"data/jee_main_{subj.lower()}.json"))
                _syl_list = list(_syl.keys())
            except Exception:
                _syl_list = []

            def _pyq_pos(ch):
                if not _syl_list: return (2, 9999)
                if ch in _syl_list: return (0, _syl_list.index(ch))
                mapped = _PYQ_OVERRIDES.get(ch)
                if mapped and mapped in _syl_list: return (1, _syl_list.index(mapped))
                words = [w.lower() for w in re.findall(r"[A-Za-z]+", ch) if len(w) > 4]
                best_score, best_pos = 0, 9999
                for i, sc in enumerate(_syl_list):
                    s = sum(1 for w in words if w in sc.lower())
                    if s > best_score or (s == best_score and s > 0 and i < best_pos):
                        best_score, best_pos = s, i
                return (1, best_pos) if best_score > 0 else (2, 9999)

            chapters.sort(key=_pyq_pos)

            kb = InlineKeyboardMarkup(row_width=1)
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_ch:"):
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
            cmd_exam(call.message)

        elif data.startswith("f_back:"):
            target = data.split(":")[1]
            if target == "main": cmd_exam(call.message)
            elif target == "sub":
                mode = state.get("mode", "practice")
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_sub:"):
            subj = data.split(":")[1]
            state["subj"] = subj
            exam = state.get("exam", "jee_adv").lower()
            fn = f"data/{exam}_{subj.lower()}.json"
            try:
                with open(fn) as f: chapters = _extract_chapters(json.load(f))
            except: chapters = ["Motion in a Straight Line", "Units and Measurements"]
            state["chapters"] = chapters
            state["page"] = 0
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_page:"):
            state["page"] += int(data.split(":")[1])
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_ch:"):
            ch = data.split(":", 1)[1]
            state["chapter"] = ch
            state["q_count"] = 0
            _b().edit_message_text(f"⏳ Generating Q1...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
            threading.Thread(target=_generate_next, args=(uid, call.message.message_id), daemon=True).start()

        elif data.startswith("f_ans:"):
            if state.get("processing") or state.get("selected") is not None: return
            state["selected"] = int(data.split(":")[1])
            sel = state["selected"]
            kb = InlineKeyboardMarkup(row_width=4)
            kb.row(*[InlineKeyboardButton(f"{'✅' if i == sel else ''}{chr(65+i)}", callback_data=f"f_ans:{i}") for i in range(4)])
            kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            state["kb"] = kb
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
            except: pass

        elif data in ("f_save", "f_skip"):
            if state.get("processing") or state.get("generating"): return
            state["processing"] = True
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            _b().send_message(uid, "🔎 <b>Verifying your response...</b>", parse_mode="HTML")
            
            if data == "f_save":
                if state.get("selected") is None: 
                    state["processing"] = False
                    return
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    q_subtopic = state["q"].get("subtopic", "General")
                    health.record_attempt(uid, state["subj"], state["chapter"], q_subtopic, is_correct, time_taken)
                except: pass
                
                msg = f"✅ <b>Correct!</b>\n\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\n\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)\n\n"
                msg += format_ultimate_solution(state['q'])
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":
                state["skipped"] += 1
                if state.get("q"):
                    correct = state["q"].get("correct_index", 0)
                    exp = clean_math(state["q"].get("explanation", ""))
                    msg = f"⏭ <b>Correct Answer: Option {chr(65+correct)}</b>\n\n📝 <b>Explanation:</b>\n{exp}"
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
            
            state["selected"] = None
            state["processing"] = False

        elif data == "f_pyq_cont":
            state["pyq_phase"] = "skipped"
            state["pyq_questions"] = state.get("pyq_skipped", [])
            state["pyq_index"] = 0
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_doubt":
            state["waiting_for_doubt"] = True
            _b().send_message(uid, "💬 <b>Please type your doubt about this question or explanation.</b>\nHamilton will answer it for you.", parse_mode="HTML")
            
        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

        elif data == "f_stop":
            state["active"] = False
            if state.get("mode") == "pyq":
                c = state.get("correct", 0)
                w = state.get("wrong", 0)
                s = state.get("skipped", 0)
                msg = f"🛑 <b>PYQ Practice Stopped</b>\n\n✅ Correct: {c}\n❌ Wrong: {w}\n⏭ Skipped: {s}"
                _b().send_message(uid, msg, parse_mode="HTML")
            state["processing"] = False
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            _generate_report(uid)
            
        elif data == "f_retry":
            if state.get("generating"): return
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

    except Exception as e:
        print(f"[ROUTER-ERR] {e}")

def _generate_report(uid):
    state = _state.get(uid, {})
    total = state.get("correct", 0) + state.get("wrong", 0) + state.get("skipped", 0)
    if total == 0:
        _b().send_message(uid, "🛑 Session stopped.")
        return
    acc = (state["correct"] / total) * 100 if total > 0 else 0
    health_delta = (state["correct"] * 1.5) - (state["wrong"] * 1.0)
    msg = f"🏁 <b>SESSION REPORT</b>\n\n📊 <b>Attempted:</b> {total}\n✅ <b>Correct:</b> {state['correct']}\n❌ <b>Wrong:</b> {state['wrong']}\n⏭ <b>Skipped:</b> {state['skipped']}\n\n🎯 <b>Accuracy:</b> {acc:.1f}%\n❤️ <b>Health Update:</b> {health_delta:+.1f}%\n\n📚 <i>Want a personal Mastery Analyzer? Contact us on WhatsApp:</i> <a href='https://wa.me/918074231426'>H&K Publications</a>"
    _b().send_message(uid, msg, parse_mode="HTML", disable_web_page_preview=True)

def _generate_next(uid, msg_id=None):
    state = _state.get(uid, {})
    if not state.get("active"): return
    state["generating"] = True
    state["q_count"] = state.get("q_count", 0) + 1
    count = state["q_count"]
    
    if count > 100:
        state["active"] = False
        _b().send_message(uid, "🎉 <b>Mastery Complete!</b> You have covered the entire syllabus.")
        return

    if msg_id: loader_msg = msg_id
    else:
        msg = _b().send_message(uid, f"⏳ Generating Q{count}...", parse_mode="HTML")
        loader_msg = msg.message_id
        threading.Thread(target=_animate_gen, args=(uid, loader_msg, count), daemon=True).start()

    import ai_client
    mode = state.get("mode", "practice")
    diff = random.randint(3, 9)
    ideal_time = {3: 45, 4: 60, 5: 75, 6: 90, 7: 90, 8: 100, 9: 110}.get(diff, 90)
    source = random.choice(["JEE Adv 2023", "JEE Main 2024", "Arihant", "Cengage", "JEE Adv 2021"])
    q_type = random.choice(["MCQ", "Multi-Correct", "Numerical", "Integer", "Assertion-Reason", "Statement-based", "Match-the-following", "Passage-based", "Matrix"])
    
    prompt = f"Generate a JEE question for '{state['chapter']}' (Subject: {state['subj']}).\n"
    prompt += f"Target Difficulty: {diff}/10. Question Type: {q_type}. Source: {source}.\n"
    prompt += "RULES:\n1. Output strictly as JSON.\n2. NO LATEX. Use Unicode (α, √, π, ⁰, ²).\n3. Explanation must be direct and concise.\n"
    prompt += '{"question":"...", "subtopic":"...", "concept":"...", "options":["A","B","C","D"], "correct_index":0, "explanation":"..."}\n'

    q = None
    for attempt in range(3):
        try:
            raw = ai_client._call_groq(0, "Output ONLY valid JSON.", prompt, max_tokens=1200, temperature=0.7)
            if not raw or not raw.strip(): continue
            txt = raw.strip()
            if txt.startswith("```"): txt = re.sub(r"^```(?:json)?\s*", "", txt); txt = re.sub(r"\s*```\s*$", "", txt)
            first, last = txt.find("{"), txt.rfind("}")
            if first == -1 or last == -1: continue
            q = json.loads(txt[first:last+1])
            if "question" in q and "options" in q:
                q["difficulty"] = diff
                q["ideal_time"] = ideal_time
                q["source"] = source
                q["q_type"] = q_type
                break
        except Exception:
            q = None
            time.sleep(1)
            
    if not q:
        try: _b().delete_message(uid, loader_msg)
        except: pass
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🔄 Retry", callback_data="f_retry"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().send_message(uid, "⚠️ <b>AI faced an error generating this question.</b>\n\nClick Retry to try again.", parse_mode="HTML", reply_markup=kb)
        state["generating"] = False
        return
        
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    
    header = f"<b>[{mode.upper()} | Q{count}]</b>\n"
    header += f"📖 <b>{state['chapter']}</b> → {q.get('subtopic', 'General')}\n"
    header += f"🧠 Concept: {q.get('concept', 'General')}\n"
    header += f"🎯 Pattern: {q.get('q_type', 'MCQ')} | Difficulty: {q.get('difficulty', 5)}/10 | ⏱️ Ideal: {q.get('ideal_time', 60)}s\n"
    header += f"🏷️ Source: {q.get('source', 'AI')}\n"
    header += "━━━━━━━━━━━━━━━\n\n"
    
    body = header + f"{clean_math(q.get('question', ''))}\n\n"
    for i, opt in enumerate(q.get("options", [])[:4]):
        body += f"<b>{chr(65+i)})</b> {clean_math(opt)}\n"
        
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    state["kb"] = kb
    state["generating"] = False
    state["processing"] = False
    
    try:
        _b().delete_message(uid, loader_msg)
        msg = _b().send_message(uid, body, parse_mode="HTML", reply_markup=kb)
        state["msg_id"] = msg.message_id
        state["question_msg_id"] = msg.message_id
        
        timer_msg = _b().send_message(uid, "⏱️ <b>Time Taken:</b> 0s", parse_mode="HTML")
        threading.Thread(target=_run_floating_timer, args=(uid, timer_msg.message_id, msg.message_id), daemon=True).start()
    except Exception as e:
        print(f"[SEND-ERR] {e}")

print("✅ c04_exam: FINAL PYQ & EXAM ENGINE LOADED.")


def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    # Phase 1: Priority Done -> Prompt for Normal
    if idx >= len(q_list) and state.get("pyq_phase") == "priority" and state.get("pyq_normal"):
        state["pyq_phase"] = "normal"
        state["pyq_questions"] = state["pyq_normal"]
        state["pyq_index"] = 0
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("▶️ Continue with Normal Questions", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
        _b().send_message(uid, "🎓 <b>You have completed all Priority (High-Yield) questions for this chapter.</b>\n\nDo you want to continue with the remaining normal questions?", reply_markup=kb)
        return

    # Everything Done
    if idx >= len(q_list):
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
    
    # Format Difficulty as "8 (Hard)"
    diff_num = q.get('difficulty', 5)
    if isinstance(diff_num, int):
        diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
        diff_str = f"{diff_num} ({diff_text})"
    else:
        diff_str = str(diff_num)
        
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\n📅 {q.get('source', 'JEE Main')}\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\n📊 Difficulty: {diff_str}"
    
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

def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    if not text: return ""
    t = str(text)
    t = html.unescape(t).replace("*", "").replace("_", " ")
    t = t.replace("\\alpha", "α").replace("\\beta", "β").replace("\\theta", "θ").replace("\\pi", "π")
    t = t.replace("\\times", "×").replace("\\cdot", "•").replace("\\sqrt", "√").replace("\\infty", "∞")
    t = t.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "").replace("$", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    sup = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    t = re.sub(r'\^([0-9+\-]+)', lambda m: m.group(1).translate(sup), t)
    t = re.sub(r'_([0-9]+)', lambda m: m.group(1).translate(sub), t)
    return t.strip()

def _extract_chapters(raw_data):
    chapters = set()
    if isinstance(raw_data, dict):
        for k, v in raw_data.items():
            if isinstance(v, dict) and "chapter" in v: chapters.add(v["chapter"])
            else: chapters.add(k)
    elif isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                ch = item.get("chapter") or item.get("name") or item.get("topic")
                if ch: chapters.add(ch)
    return sorted(list(chapters))

def _animate_gen(uid, msg_id, count):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if not state.get("generating"): return
        try: _b().edit_message_text(f"⏳ Generating Q{count}... ({elapsed}s)", chat_id=uid, message_id=msg_id, parse_mode="HTML")
        except: pass

def _run_floating_timer(uid, timer_msg_id, question_msg_id):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id)
            except: pass
            return
        try: 
            _b().edit_message_text(f"⏱️ <b>Time Taken:</b> {elapsed}s", chat_id=uid, message_id=timer_msg_id, parse_mode="HTML")
        except: pass

def _strip_old_buttons(uid):
    state = _state.get(uid, {})
    old_msg = state.get("msg_id")
    if old_msg:
        try: _b().edit_message_reply_markup(uid, old_msg, reply_markup=None)
        except: pass
    state["msg_id"] = None

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
        InlineKeyboardButton("📝 Test", callback_data="f_mode:test")
    )
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(message.chat.id, "🎓 <b>Exam Center</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['conceptual'])
def cmd_conceptual(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"),
        InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional")
    )
    _b().send_message(message.chat.id, "🧠 <b>Concept Mastery</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

def _show_chapters(uid, msg_id):
    state = _state[uid]
    chapters = state.get("chapters", [])
    page = state.get("page", 0)
    start, end = page * 5, (page + 1) * 5
    chunk = chapters[start:end]
    
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(chunk):
        kb.add(InlineKeyboardButton(f"{start + i + 1}. {ch[:25]}", callback_data=f"f_ch:{ch}"))
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="f_page:-1"))
    if end < len(chapters): nav.append(InlineKeyboardButton("Next ➡️", callback_data="f_page:1"))
    if nav: kb.row(*nav)
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="f_back:sub"))
    
    try: _b().edit_message_text(f"📚 <b>Select Chapter:</b>\n(Showing {start+1}-{min(end, len(chapters))} of {len(chapters)})", chat_id=uid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]

    if data.startswith("f_ans:") and state.get("processing"): return
        
    try:
        if data.startswith("f_mode:"):
            mode = data.split(":")[1]
            _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
            
            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )
                kb.add(InlineKeyboardButton("🚧 JEE Adv (Coming Soon)", callback_data="f_soon"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("Physics", callback_data="f_sub:Physics"),
                InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"),
                InlineKeyboardButton("Maths", callback_data="f_sub:Maths")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "f_soon":
            _b().answer_callback_query(call.id, "Coming Soon!", show_alert=True)

        elif data.startswith("f_pyq:"):
            ptype = data.split(":")[1]
            import json
            try:
                with open("data/pyq_db.json") as f: db = json.load(f)
            except: db = {"practice": {}, "papers": {}}

            if ptype == "practice":
                kb = InlineKeyboardMarkup(row_width=3)
                for subj in db.get("practice", {}).keys():
                    kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📖 <b>PYQ Practice</b>\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            
            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                years = list(db.get("papers", {}).keys())
                if not years:
                    _b().answer_callback_query(call.id, "No papers uploaded yet.")
                    return
                for yr in years:
                    kb.add(InlineKeyboardButton(yr, callback_data=f"f_pyq_yr:{yr}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\nSelect Year:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json, re
            with open("data/pyq_db.json") as f: db = json.load(f)
            chapters = list(db.get("practice", {}).get(subj, {}).keys())

            # --- Syllabus-order anchor map (PDF coarse chapter -> syllabus fine chapter) ---
            _PYQ_OVERRIDES = {
                "Atoms and Nuclei": "Atomic Physics",
                "Capacitor": "Capacitor and Capacitance",
                "Center of Mass and Collision": "System of Particles and Centre of Mass",
                "Current Electricity": "Electric Current and Circuits",
                "Dual Nature of Radiation": "Dual Nature of Radiation and Matter",
                "Electrostatics": "Coulomb's Law and Electric Field",
                "Geometrical Optics": "Geometrical Optics: Part 1",
                "Heat and Thermodynamics": "Thermodynamics",
                "Laws of Motion": "Newton's Laws of Motion (Without Friction)",
                "Magnetic Effect of Current": "Magnetic Field and Magnetic Forces",
            }

            _syl_list = []
            try:
                _syl = json.load(open(f"data/jee_main_{subj.lower()}.json"))
                _syl_list = list(_syl.keys())
            except Exception:
                _syl_list = []

            def _pyq_pos(ch):
                if not _syl_list: return (2, 9999)
                if ch in _syl_list: return (0, _syl_list.index(ch))
                mapped = _PYQ_OVERRIDES.get(ch)
                if mapped and mapped in _syl_list: return (1, _syl_list.index(mapped))
                words = [w.lower() for w in re.findall(r"[A-Za-z]+", ch) if len(w) > 4]
                best_score, best_pos = 0, 9999
                for i, sc in enumerate(_syl_list):
                    s = sum(1 for w in words if w in sc.lower())
                    if s > best_score or (s == best_score and s > 0 and i < best_pos):
                        best_score, best_pos = s, i
                return (1, best_pos) if best_score > 0 else (2, 9999)

            chapters.sort(key=_pyq_pos)

            kb = InlineKeyboardMarkup(row_width=1)
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_ch:"):
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
            cmd_exam(call.message)

        elif data.startswith("f_back:"):
            target = data.split(":")[1]
            if target == "main": cmd_exam(call.message)
            elif target == "sub":
                mode = state.get("mode", "practice")
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_sub:"):
            subj = data.split(":")[1]
            state["subj"] = subj
            exam = state.get("exam", "jee_adv").lower()
            fn = f"data/{exam}_{subj.lower()}.json"
            try:
                with open(fn) as f: chapters = _extract_chapters(json.load(f))
            except: chapters = ["Motion in a Straight Line", "Units and Measurements"]
            state["chapters"] = chapters
            state["page"] = 0
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_page:"):
            state["page"] += int(data.split(":")[1])
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_ch:"):
            ch = data.split(":", 1)[1]
            state["chapter"] = ch
            state["q_count"] = 0
            _b().edit_message_text(f"⏳ Generating Q1...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
            threading.Thread(target=_generate_next, args=(uid, call.message.message_id), daemon=True).start()

        elif data.startswith("f_ans:"):
            if state.get("processing") or state.get("selected") is not None: return
            state["selected"] = int(data.split(":")[1])
            sel = state["selected"]
            kb = InlineKeyboardMarkup(row_width=4)
            kb.row(*[InlineKeyboardButton(f"{'✅' if i == sel else ''}{chr(65+i)}", callback_data=f"f_ans:{i}") for i in range(4)])
            kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            state["kb"] = kb
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
            except: pass

        elif data in ("f_save", "f_skip"):
            if state.get("processing") or state.get("generating"): return
            state["processing"] = True
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            _b().send_message(uid, "🔎 <b>Verifying your response...</b>", parse_mode="HTML")
            
            if data == "f_save":
                if state.get("selected") is None: 
                    state["processing"] = False
                    return
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    q_subtopic = state["q"].get("subtopic", "General")
                    health.record_attempt(uid, state["subj"], state["chapter"], q_subtopic, is_correct, time_taken)
                except: pass
                
                msg = f"✅ <b>Correct!</b>\n\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\n\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)\n\n"
                msg += format_ultimate_solution(state['q'])
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":
                state["skipped"] += 1
                if state.get("q"):
                    correct = state["q"].get("correct_index", 0)
                    exp = clean_math(state["q"].get("explanation", ""))
                    msg = f"⏭ <b>Correct Answer: Option {chr(65+correct)}</b>\n\n📝 <b>Explanation:</b>\n{exp}"
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
            
            state["selected"] = None
            state["processing"] = False

        elif data == "f_pyq_cont":
            state["pyq_phase"] = "skipped"
            state["pyq_questions"] = state.get("pyq_skipped", [])
            state["pyq_index"] = 0
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_doubt":
            state["waiting_for_doubt"] = True
            _b().send_message(uid, "💬 <b>Please type your doubt about this question or explanation.</b>\nHamilton will answer it for you.", parse_mode="HTML")
            
        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

        elif data == "f_stop":
            state["active"] = False
            if state.get("mode") == "pyq":
                c = state.get("correct", 0)
                w = state.get("wrong", 0)
                s = state.get("skipped", 0)
                msg = f"🛑 <b>PYQ Practice Stopped</b>\n\n✅ Correct: {c}\n❌ Wrong: {w}\n⏭ Skipped: {s}"
                _b().send_message(uid, msg, parse_mode="HTML")
            state["processing"] = False
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            _generate_report(uid)
            
        elif data == "f_retry":
            if state.get("generating"): return
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

    except Exception as e:
        print(f"[ROUTER-ERR] {e}")

def _generate_report(uid):
    state = _state.get(uid, {})
    total = state.get("correct", 0) + state.get("wrong", 0) + state.get("skipped", 0)
    if total == 0:
        _b().send_message(uid, "🛑 Session stopped.")
        return
    acc = (state["correct"] / total) * 100 if total > 0 else 0
    health_delta = (state["correct"] * 1.5) - (state["wrong"] * 1.0)
    msg = f"🏁 <b>SESSION REPORT</b>\n\n📊 <b>Attempted:</b> {total}\n✅ <b>Correct:</b> {state['correct']}\n❌ <b>Wrong:</b> {state['wrong']}\n⏭ <b>Skipped:</b> {state['skipped']}\n\n🎯 <b>Accuracy:</b> {acc:.1f}%\n❤️ <b>Health Update:</b> {health_delta:+.1f}%\n\n📚 <i>Want a personal Mastery Analyzer? Contact us on WhatsApp:</i> <a href='https://wa.me/918074231426'>H&K Publications</a>"
    _b().send_message(uid, msg, parse_mode="HTML", disable_web_page_preview=True)

def _generate_next(uid, msg_id=None):
    state = _state.get(uid, {})
    if not state.get("active"): return
    state["generating"] = True
    state["q_count"] = state.get("q_count", 0) + 1
    count = state["q_count"]
    
    if count > 100:
        state["active"] = False
        _b().send_message(uid, "🎉 <b>Mastery Complete!</b> You have covered the entire syllabus.")
        return

    if msg_id: loader_msg = msg_id
    else:
        msg = _b().send_message(uid, f"⏳ Generating Q{count}...", parse_mode="HTML")
        loader_msg = msg.message_id
        threading.Thread(target=_animate_gen, args=(uid, loader_msg, count), daemon=True).start()

    import ai_client
    mode = state.get("mode", "practice")
    diff = random.randint(3, 9)
    ideal_time = {3: 45, 4: 60, 5: 75, 6: 90, 7: 90, 8: 100, 9: 110}.get(diff, 90)
    source = random.choice(["JEE Adv 2023", "JEE Main 2024", "Arihant", "Cengage", "JEE Adv 2021"])
    q_type = random.choice(["MCQ", "Multi-Correct", "Numerical", "Integer", "Assertion-Reason", "Statement-based", "Match-the-following", "Passage-based", "Matrix"])
    
    prompt = f"Generate a JEE question for '{state['chapter']}' (Subject: {state['subj']}).\n"
    prompt += f"Target Difficulty: {diff}/10. Question Type: {q_type}. Source: {source}.\n"
    prompt += "RULES:\n1. Output strictly as JSON.\n2. NO LATEX. Use Unicode (α, √, π, ⁰, ²).\n3. Explanation must be direct and concise.\n"
    prompt += '{"question":"...", "subtopic":"...", "concept":"...", "options":["A","B","C","D"], "correct_index":0, "explanation":"..."}\n'

    q = None
    for attempt in range(3):
        try:
            raw = ai_client._call_groq(0, "Output ONLY valid JSON.", prompt, max_tokens=1200, temperature=0.7)
            if not raw or not raw.strip(): continue
            txt = raw.strip()
            if txt.startswith("```"): txt = re.sub(r"^```(?:json)?\s*", "", txt); txt = re.sub(r"\s*```\s*$", "", txt)
            first, last = txt.find("{"), txt.rfind("}")
            if first == -1 or last == -1: continue
            q = json.loads(txt[first:last+1])
            if "question" in q and "options" in q:
                q["difficulty"] = diff
                q["ideal_time"] = ideal_time
                q["source"] = source
                q["q_type"] = q_type
                break
        except Exception:
            q = None
            time.sleep(1)
            
    if not q:
        try: _b().delete_message(uid, loader_msg)
        except: pass
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🔄 Retry", callback_data="f_retry"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().send_message(uid, "⚠️ <b>AI faced an error generating this question.</b>\n\nClick Retry to try again.", parse_mode="HTML", reply_markup=kb)
        state["generating"] = False
        return
        
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    
    header = f"<b>[{mode.upper()} | Q{count}]</b>\n"
    header += f"📖 <b>{state['chapter']}</b> → {q.get('subtopic', 'General')}\n"
    header += f"🧠 Concept: {q.get('concept', 'General')}\n"
    header += f"🎯 Pattern: {q.get('q_type', 'MCQ')} | Difficulty: {q.get('difficulty', 5)}/10 | ⏱️ Ideal: {q.get('ideal_time', 60)}s\n"
    header += f"🏷️ Source: {q.get('source', 'AI')}\n"
    header += "━━━━━━━━━━━━━━━\n\n"
    
    body = header + f"{clean_math(q.get('question', ''))}\n\n"
    for i, opt in enumerate(q.get("options", [])[:4]):
        body += f"<b>{chr(65+i)})</b> {clean_math(opt)}\n"
        
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    state["kb"] = kb
    state["generating"] = False
    state["processing"] = False
    
    try:
        _b().delete_message(uid, loader_msg)
        msg = _b().send_message(uid, body, parse_mode="HTML", reply_markup=kb)
        state["msg_id"] = msg.message_id
        state["question_msg_id"] = msg.message_id
        
        timer_msg = _b().send_message(uid, "⏱️ <b>Time Taken:</b> 0s", parse_mode="HTML")
        threading.Thread(target=_run_floating_timer, args=(uid, timer_msg.message_id, msg.message_id), daemon=True).start()
    except Exception as e:
        print(f"[SEND-ERR] {e}")

print("✅ c04_exam: FINAL PYQ & EXAM ENGINE LOADED.")


def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    # Phase 1: Priority Done -> Prompt for Normal
    if idx >= len(q_list) and state.get("pyq_phase") == "priority" and state.get("pyq_normal"):
        state["pyq_phase"] = "normal"
        state["pyq_questions"] = state["pyq_normal"]
        state["pyq_index"] = 0
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("▶️ Continue with Normal Questions", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
        _b().send_message(uid, "🎓 <b>You have completed all Priority (High-Yield) questions for this chapter.</b>\n\nDo you want to continue with the remaining normal questions?", reply_markup=kb)
        return

    # Everything Done
    if idx >= len(q_list):
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
    
    # Format Difficulty as "8 (Hard)"
    diff_num = q.get('difficulty', 5)
    if isinstance(diff_num, int):
        diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
        diff_str = f"{diff_num} ({diff_text})"
    else:
        diff_str = str(diff_num)
        
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\n📅 {q.get('source', 'JEE Main')}\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\n📊 Difficulty: {diff_str}"
    
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

def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    if not text: return ""
    t = str(text)
    t = html.unescape(t).replace("*", "").replace("_", " ")
    t = t.replace("\\alpha", "α").replace("\\beta", "β").replace("\\theta", "θ").replace("\\pi", "π")
    t = t.replace("\\times", "×").replace("\\cdot", "•").replace("\\sqrt", "√").replace("\\infty", "∞")
    t = t.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "").replace("$", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    sup = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    t = re.sub(r'\^([0-9+\-]+)', lambda m: m.group(1).translate(sup), t)
    t = re.sub(r'_([0-9]+)', lambda m: m.group(1).translate(sub), t)
    return t.strip()

def _extract_chapters(raw_data):
    chapters = set()
    if isinstance(raw_data, dict):
        for k, v in raw_data.items():
            if isinstance(v, dict) and "chapter" in v: chapters.add(v["chapter"])
            else: chapters.add(k)
    elif isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                ch = item.get("chapter") or item.get("name") or item.get("topic")
                if ch: chapters.add(ch)
    return sorted(list(chapters))

def _animate_gen(uid, msg_id, count):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if not state.get("generating"): return
        try: _b().edit_message_text(f"⏳ Generating Q{count}... ({elapsed}s)", chat_id=uid, message_id=msg_id, parse_mode="HTML")
        except: pass

def _run_floating_timer(uid, timer_msg_id, question_msg_id):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id)
            except: pass
            return
        try: 
            _b().edit_message_text(f"⏱️ <b>Time Taken:</b> {elapsed}s", chat_id=uid, message_id=timer_msg_id, parse_mode="HTML")
        except: pass

def _strip_old_buttons(uid):
    state = _state.get(uid, {})
    old_msg = state.get("msg_id")
    if old_msg:
        try: _b().edit_message_reply_markup(uid, old_msg, reply_markup=None)
        except: pass
    state["msg_id"] = None

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
        InlineKeyboardButton("📝 Test", callback_data="f_mode:test")
    )
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(message.chat.id, "🎓 <b>Exam Center</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['conceptual'])
def cmd_conceptual(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"),
        InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional")
    )
    _b().send_message(message.chat.id, "🧠 <b>Concept Mastery</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

def _show_chapters(uid, msg_id):
    state = _state[uid]
    chapters = state.get("chapters", [])
    page = state.get("page", 0)
    start, end = page * 5, (page + 1) * 5
    chunk = chapters[start:end]
    
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(chunk):
        kb.add(InlineKeyboardButton(f"{start + i + 1}. {ch[:25]}", callback_data=f"f_ch:{ch}"))
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="f_page:-1"))
    if end < len(chapters): nav.append(InlineKeyboardButton("Next ➡️", callback_data="f_page:1"))
    if nav: kb.row(*nav)
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="f_back:sub"))
    
    try: _b().edit_message_text(f"📚 <b>Select Chapter:</b>\n(Showing {start+1}-{min(end, len(chapters))} of {len(chapters)})", chat_id=uid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]

    if data.startswith("f_ans:") and state.get("processing"): return
        
    try:
        if data.startswith("f_mode:"):
            mode = data.split(":")[1]
            _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
            
            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )
                kb.add(InlineKeyboardButton("🚧 JEE Adv (Coming Soon)", callback_data="f_soon"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("Physics", callback_data="f_sub:Physics"),
                InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"),
                InlineKeyboardButton("Maths", callback_data="f_sub:Maths")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "f_soon":
            _b().answer_callback_query(call.id, "Coming Soon!", show_alert=True)

        elif data.startswith("f_pyq:"):
            ptype = data.split(":")[1]
            import json
            try:
                with open("data/pyq_db.json") as f: db = json.load(f)
            except: db = {"practice": {}, "papers": {}}

            if ptype == "practice":
                kb = InlineKeyboardMarkup(row_width=3)
                for subj in db.get("practice", {}).keys():
                    kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📖 <b>PYQ Practice</b>\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            
            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                years = list(db.get("papers", {}).keys())
                if not years:
                    _b().answer_callback_query(call.id, "No papers uploaded yet.")
                    return
                for yr in years:
                    kb.add(InlineKeyboardButton(yr, callback_data=f"f_pyq_yr:{yr}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\nSelect Year:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json, re
            with open("data/pyq_db.json") as f: db = json.load(f)
            chapters = list(db.get("practice", {}).get(subj, {}).keys())

            # --- Syllabus-order anchor map (PDF coarse chapter -> syllabus fine chapter) ---
            _PYQ_OVERRIDES = {
                "Atoms and Nuclei": "Atomic Physics",
                "Capacitor": "Capacitor and Capacitance",
                "Center of Mass and Collision": "System of Particles and Centre of Mass",
                "Current Electricity": "Electric Current and Circuits",
                "Dual Nature of Radiation": "Dual Nature of Radiation and Matter",
                "Electrostatics": "Coulomb's Law and Electric Field",
                "Geometrical Optics": "Geometrical Optics: Part 1",
                "Heat and Thermodynamics": "Thermodynamics",
                "Laws of Motion": "Newton's Laws of Motion (Without Friction)",
                "Magnetic Effect of Current": "Magnetic Field and Magnetic Forces",
            }

            _syl_list = []
            try:
                _syl = json.load(open(f"data/jee_main_{subj.lower()}.json"))
                _syl_list = list(_syl.keys())
            except Exception:
                _syl_list = []

            def _pyq_pos(ch):
                if not _syl_list: return (2, 9999)
                if ch in _syl_list: return (0, _syl_list.index(ch))
                mapped = _PYQ_OVERRIDES.get(ch)
                if mapped and mapped in _syl_list: return (1, _syl_list.index(mapped))
                words = [w.lower() for w in re.findall(r"[A-Za-z]+", ch) if len(w) > 4]
                best_score, best_pos = 0, 9999
                for i, sc in enumerate(_syl_list):
                    s = sum(1 for w in words if w in sc.lower())
                    if s > best_score or (s == best_score and s > 0 and i < best_pos):
                        best_score, best_pos = s, i
                return (1, best_pos) if best_score > 0 else (2, 9999)

            chapters.sort(key=_pyq_pos)

            kb = InlineKeyboardMarkup(row_width=1)
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_ch:"):
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
            cmd_exam(call.message)

        elif data.startswith("f_back:"):
            target = data.split(":")[1]
            if target == "main": cmd_exam(call.message)
            elif target == "sub":
                mode = state.get("mode", "practice")
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_sub:"):
            subj = data.split(":")[1]
            state["subj"] = subj
            exam = state.get("exam", "jee_adv").lower()
            fn = f"data/{exam}_{subj.lower()}.json"
            try:
                with open(fn) as f: chapters = _extract_chapters(json.load(f))
            except: chapters = ["Motion in a Straight Line", "Units and Measurements"]
            state["chapters"] = chapters
            state["page"] = 0
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_page:"):
            state["page"] += int(data.split(":")[1])
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_ch:"):
            ch = data.split(":", 1)[1]
            state["chapter"] = ch
            state["q_count"] = 0
            _b().edit_message_text(f"⏳ Generating Q1...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
            threading.Thread(target=_generate_next, args=(uid, call.message.message_id), daemon=True).start()

        elif data.startswith("f_ans:"):
            if state.get("processing") or state.get("selected") is not None: return
            state["selected"] = int(data.split(":")[1])
            sel = state["selected"]
            kb = InlineKeyboardMarkup(row_width=4)
            kb.row(*[InlineKeyboardButton(f"{'✅' if i == sel else ''}{chr(65+i)}", callback_data=f"f_ans:{i}") for i in range(4)])
            kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            state["kb"] = kb
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
            except: pass

        elif data in ("f_save", "f_skip"):
            if state.get("processing") or state.get("generating"): return
            state["processing"] = True
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            _b().send_message(uid, "🔎 <b>Verifying your response...</b>", parse_mode="HTML")
            
            if data == "f_save":
                if state.get("selected") is None: 
                    state["processing"] = False
                    return
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    q_subtopic = state["q"].get("subtopic", "General")
                    health.record_attempt(uid, state["subj"], state["chapter"], q_subtopic, is_correct, time_taken)
                except: pass
                
                msg = f"✅ <b>Correct!</b>\n\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\n\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)\n\n"
                msg += format_ultimate_solution(state['q'])
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":
                state["skipped"] += 1
                if state.get("q"):
                    correct = state["q"].get("correct_index", 0)
                    exp = clean_math(state["q"].get("explanation", ""))
                    msg = f"⏭ <b>Correct Answer: Option {chr(65+correct)}</b>\n\n📝 <b>Explanation:</b>\n{exp}"
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
            
            state["selected"] = None
            state["processing"] = False

        elif data == "f_pyq_cont":
            state["pyq_phase"] = "skipped"
            state["pyq_questions"] = state.get("pyq_skipped", [])
            state["pyq_index"] = 0
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_doubt":
            state["waiting_for_doubt"] = True
            _b().send_message(uid, "💬 <b>Please type your doubt about this question or explanation.</b>\nHamilton will answer it for you.", parse_mode="HTML")
            
        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

        elif data == "f_stop":
            state["active"] = False
            if state.get("mode") == "pyq":
                c = state.get("correct", 0)
                w = state.get("wrong", 0)
                s = state.get("skipped", 0)
                msg = f"🛑 <b>PYQ Practice Stopped</b>\n\n✅ Correct: {c}\n❌ Wrong: {w}\n⏭ Skipped: {s}"
                _b().send_message(uid, msg, parse_mode="HTML")
            state["processing"] = False
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            _generate_report(uid)
            
        elif data == "f_retry":
            if state.get("generating"): return
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

    except Exception as e:
        print(f"[ROUTER-ERR] {e}")

def _generate_report(uid):
    state = _state.get(uid, {})
    total = state.get("correct", 0) + state.get("wrong", 0) + state.get("skipped", 0)
    if total == 0:
        _b().send_message(uid, "🛑 Session stopped.")
        return
    acc = (state["correct"] / total) * 100 if total > 0 else 0
    health_delta = (state["correct"] * 1.5) - (state["wrong"] * 1.0)
    msg = f"🏁 <b>SESSION REPORT</b>\n\n📊 <b>Attempted:</b> {total}\n✅ <b>Correct:</b> {state['correct']}\n❌ <b>Wrong:</b> {state['wrong']}\n⏭ <b>Skipped:</b> {state['skipped']}\n\n🎯 <b>Accuracy:</b> {acc:.1f}%\n❤️ <b>Health Update:</b> {health_delta:+.1f}%\n\n📚 <i>Want a personal Mastery Analyzer? Contact us on WhatsApp:</i> <a href='https://wa.me/918074231426'>H&K Publications</a>"
    _b().send_message(uid, msg, parse_mode="HTML", disable_web_page_preview=True)

def _generate_next(uid, msg_id=None):
    state = _state.get(uid, {})
    if not state.get("active"): return
    state["generating"] = True
    state["q_count"] = state.get("q_count", 0) + 1
    count = state["q_count"]
    
    if count > 100:
        state["active"] = False
        _b().send_message(uid, "🎉 <b>Mastery Complete!</b> You have covered the entire syllabus.")
        return

    if msg_id: loader_msg = msg_id
    else:
        msg = _b().send_message(uid, f"⏳ Generating Q{count}...", parse_mode="HTML")
        loader_msg = msg.message_id
        threading.Thread(target=_animate_gen, args=(uid, loader_msg, count), daemon=True).start()

    import ai_client
    mode = state.get("mode", "practice")
    diff = random.randint(3, 9)
    ideal_time = {3: 45, 4: 60, 5: 75, 6: 90, 7: 90, 8: 100, 9: 110}.get(diff, 90)
    source = random.choice(["JEE Adv 2023", "JEE Main 2024", "Arihant", "Cengage", "JEE Adv 2021"])
    q_type = random.choice(["MCQ", "Multi-Correct", "Numerical", "Integer", "Assertion-Reason", "Statement-based", "Match-the-following", "Passage-based", "Matrix"])
    
    prompt = f"Generate a JEE question for '{state['chapter']}' (Subject: {state['subj']}).\n"
    prompt += f"Target Difficulty: {diff}/10. Question Type: {q_type}. Source: {source}.\n"
    prompt += "RULES:\n1. Output strictly as JSON.\n2. NO LATEX. Use Unicode (α, √, π, ⁰, ²).\n3. Explanation must be direct and concise.\n"
    prompt += '{"question":"...", "subtopic":"...", "concept":"...", "options":["A","B","C","D"], "correct_index":0, "explanation":"..."}\n'

    q = None
    for attempt in range(3):
        try:
            raw = ai_client._call_groq(0, "Output ONLY valid JSON.", prompt, max_tokens=1200, temperature=0.7)
            if not raw or not raw.strip(): continue
            txt = raw.strip()
            if txt.startswith("```"): txt = re.sub(r"^```(?:json)?\s*", "", txt); txt = re.sub(r"\s*```\s*$", "", txt)
            first, last = txt.find("{"), txt.rfind("}")
            if first == -1 or last == -1: continue
            q = json.loads(txt[first:last+1])
            if "question" in q and "options" in q:
                q["difficulty"] = diff
                q["ideal_time"] = ideal_time
                q["source"] = source
                q["q_type"] = q_type
                break
        except Exception:
            q = None
            time.sleep(1)
            
    if not q:
        try: _b().delete_message(uid, loader_msg)
        except: pass
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🔄 Retry", callback_data="f_retry"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().send_message(uid, "⚠️ <b>AI faced an error generating this question.</b>\n\nClick Retry to try again.", parse_mode="HTML", reply_markup=kb)
        state["generating"] = False
        return
        
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    
    header = f"<b>[{mode.upper()} | Q{count}]</b>\n"
    header += f"📖 <b>{state['chapter']}</b> → {q.get('subtopic', 'General')}\n"
    header += f"🧠 Concept: {q.get('concept', 'General')}\n"
    header += f"🎯 Pattern: {q.get('q_type', 'MCQ')} | Difficulty: {q.get('difficulty', 5)}/10 | ⏱️ Ideal: {q.get('ideal_time', 60)}s\n"
    header += f"🏷️ Source: {q.get('source', 'AI')}\n"
    header += "━━━━━━━━━━━━━━━\n\n"
    
    body = header + f"{clean_math(q.get('question', ''))}\n\n"
    for i, opt in enumerate(q.get("options", [])[:4]):
        body += f"<b>{chr(65+i)})</b> {clean_math(opt)}\n"
        
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    state["kb"] = kb
    state["generating"] = False
    state["processing"] = False
    
    try:
        _b().delete_message(uid, loader_msg)
        msg = _b().send_message(uid, body, parse_mode="HTML", reply_markup=kb)
        state["msg_id"] = msg.message_id
        state["question_msg_id"] = msg.message_id
        
        timer_msg = _b().send_message(uid, "⏱️ <b>Time Taken:</b> 0s", parse_mode="HTML")
        threading.Thread(target=_run_floating_timer, args=(uid, timer_msg.message_id, msg.message_id), daemon=True).start()
    except Exception as e:
        print(f"[SEND-ERR] {e}")

print("✅ c04_exam: FINAL PYQ & EXAM ENGINE LOADED.")


def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    # 60-Question Checkpoint (Only triggers once)
    if idx == 60 and not state.get("pyq_warned"):
        state["pyq_warned"] = True
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("▶️ Continue Remaining", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
        _b().send_message(uid, "🎓 <b>You have completed 60 PYQs for conceptual understanding in depth.</b>\n\nThis chapter has more questions. Do you want to continue with the older/skipped questions, or stop and see your result?", reply_markup=kb)
        return

    # If user finished all questions in the DB
    if idx >= len(q_list):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🛑 Stop & View Result", callback_data="f_stop"))
        _b().send_message(uid, "🏁 <b>All PYQs from this chapter are completed!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False

    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)}</b>\n📅 {q.get('source', 'JEE Main')}\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\n📊 Difficulty: {q.get('difficulty', 'Medium')}"
    
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

def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    if not text: return ""
    t = str(text)
    t = html.unescape(t).replace("*", "").replace("_", " ")
    t = t.replace("\\alpha", "α").replace("\\beta", "β").replace("\\theta", "θ").replace("\\pi", "π")
    t = t.replace("\\times", "×").replace("\\cdot", "•").replace("\\sqrt", "√").replace("\\infty", "∞")
    t = t.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "").replace("$", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    sup = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    t = re.sub(r'\^([0-9+\-]+)', lambda m: m.group(1).translate(sup), t)
    t = re.sub(r'_([0-9]+)', lambda m: m.group(1).translate(sub), t)
    return t.strip()

def _extract_chapters(raw_data):
    chapters = set()
    if isinstance(raw_data, dict):
        for k, v in raw_data.items():
            if isinstance(v, dict) and "chapter" in v: chapters.add(v["chapter"])
            else: chapters.add(k)
    elif isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                ch = item.get("chapter") or item.get("name") or item.get("topic")
                if ch: chapters.add(ch)
    return sorted(list(chapters))

def _animate_gen(uid, msg_id, count):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if not state.get("generating"): return
        try: _b().edit_message_text(f"⏳ Generating Q{count}... ({elapsed}s)", chat_id=uid, message_id=msg_id, parse_mode="HTML")
        except: pass

def _run_floating_timer(uid, timer_msg_id, question_msg_id):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id)
            except: pass
            return
        try: 
            _b().edit_message_text(f"⏱️ <b>Time Taken:</b> {elapsed}s", chat_id=uid, message_id=timer_msg_id, parse_mode="HTML")
        except: pass

def _strip_old_buttons(uid):
    state = _state.get(uid, {})
    old_msg = state.get("msg_id")
    if old_msg:
        try: _b().edit_message_reply_markup(uid, old_msg, reply_markup=None)
        except: pass
    state["msg_id"] = None

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
        InlineKeyboardButton("📝 Test", callback_data="f_mode:test")
    )
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(message.chat.id, "🎓 <b>Exam Center</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['conceptual'])
def cmd_conceptual(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"),
        InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional")
    )
    _b().send_message(message.chat.id, "🧠 <b>Concept Mastery</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

def _show_chapters(uid, msg_id):
    state = _state[uid]
    chapters = state.get("chapters", [])
    page = state.get("page", 0)
    start, end = page * 5, (page + 1) * 5
    chunk = chapters[start:end]
    
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(chunk):
        kb.add(InlineKeyboardButton(f"{start + i + 1}. {ch[:25]}", callback_data=f"f_ch:{ch}"))
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="f_page:-1"))
    if end < len(chapters): nav.append(InlineKeyboardButton("Next ➡️", callback_data="f_page:1"))
    if nav: kb.row(*nav)
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="f_back:sub"))
    
    try: _b().edit_message_text(f"📚 <b>Select Chapter:</b>\n(Showing {start+1}-{min(end, len(chapters))} of {len(chapters)})", chat_id=uid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]

    if data.startswith("f_ans:") and state.get("processing"): return
        
    try:
        if data.startswith("f_mode:"):
            mode = data.split(":")[1]
            _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
            
            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )
                kb.add(InlineKeyboardButton("🚧 JEE Adv (Coming Soon)", callback_data="f_soon"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("Physics", callback_data="f_sub:Physics"),
                InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"),
                InlineKeyboardButton("Maths", callback_data="f_sub:Maths")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "f_soon":
            _b().answer_callback_query(call.id, "Coming Soon!", show_alert=True)

        elif data.startswith("f_pyq:"):
            ptype = data.split(":")[1]
            import json
            try:
                with open("data/pyq_db.json") as f: db = json.load(f)
            except: db = {"practice": {}, "papers": {}}

            if ptype == "practice":
                kb = InlineKeyboardMarkup(row_width=3)
                for subj in db.get("practice", {}).keys():
                    kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📖 <b>PYQ Practice</b>\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            
            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                years = list(db.get("papers", {}).keys())
                if not years:
                    _b().answer_callback_query(call.id, "No papers uploaded yet.")
                    return
                for yr in years:
                    kb.add(InlineKeyboardButton(yr, callback_data=f"f_pyq_yr:{yr}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\nSelect Year:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json, re
            with open("data/pyq_db.json") as f: db = json.load(f)
            chapters = list(db.get("practice", {}).get(subj, {}).keys())

            # --- Syllabus-order anchor map (PDF coarse chapter -> syllabus fine chapter) ---
            _PYQ_OVERRIDES = {
                "Atoms and Nuclei": "Atomic Physics",
                "Capacitor": "Capacitor and Capacitance",
                "Center of Mass and Collision": "System of Particles and Centre of Mass",
                "Current Electricity": "Electric Current and Circuits",
                "Dual Nature of Radiation": "Dual Nature of Radiation and Matter",
                "Electrostatics": "Coulomb's Law and Electric Field",
                "Geometrical Optics": "Geometrical Optics: Part 1",
                "Heat and Thermodynamics": "Thermodynamics",
                "Laws of Motion": "Newton's Laws of Motion (Without Friction)",
                "Magnetic Effect of Current": "Magnetic Field and Magnetic Forces",
            }

            _syl_list = []
            try:
                _syl = json.load(open(f"data/jee_main_{subj.lower()}.json"))
                _syl_list = list(_syl.keys())
            except Exception:
                _syl_list = []

            def _pyq_pos(ch):
                if not _syl_list: return (2, 9999)
                if ch in _syl_list: return (0, _syl_list.index(ch))
                mapped = _PYQ_OVERRIDES.get(ch)
                if mapped and mapped in _syl_list: return (1, _syl_list.index(mapped))
                words = [w.lower() for w in re.findall(r"[A-Za-z]+", ch) if len(w) > 4]
                best_score, best_pos = 0, 9999
                for i, sc in enumerate(_syl_list):
                    s = sum(1 for w in words if w in sc.lower())
                    if s > best_score or (s == best_score and s > 0 and i < best_pos):
                        best_score, best_pos = s, i
                return (1, best_pos) if best_score > 0 else (2, 9999)

            chapters.sort(key=_pyq_pos)

            kb = InlineKeyboardMarkup(row_width=1)
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_ch:"):
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
            cmd_exam(call.message)

        elif data.startswith("f_back:"):
            target = data.split(":")[1]
            if target == "main": cmd_exam(call.message)
            elif target == "sub":
                mode = state.get("mode", "practice")
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_sub:"):
            subj = data.split(":")[1]
            state["subj"] = subj
            exam = state.get("exam", "jee_adv").lower()
            fn = f"data/{exam}_{subj.lower()}.json"
            try:
                with open(fn) as f: chapters = _extract_chapters(json.load(f))
            except: chapters = ["Motion in a Straight Line", "Units and Measurements"]
            state["chapters"] = chapters
            state["page"] = 0
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_page:"):
            state["page"] += int(data.split(":")[1])
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_ch:"):
            ch = data.split(":", 1)[1]
            state["chapter"] = ch
            state["q_count"] = 0
            _b().edit_message_text(f"⏳ Generating Q1...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
            threading.Thread(target=_generate_next, args=(uid, call.message.message_id), daemon=True).start()

        elif data.startswith("f_ans:"):
            if state.get("processing") or state.get("selected") is not None: return
            state["selected"] = int(data.split(":")[1])
            sel = state["selected"]
            kb = InlineKeyboardMarkup(row_width=4)
            kb.row(*[InlineKeyboardButton(f"{'✅' if i == sel else ''}{chr(65+i)}", callback_data=f"f_ans:{i}") for i in range(4)])
            kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            state["kb"] = kb
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
            except: pass

        elif data in ("f_save", "f_skip"):
            if state.get("processing") or state.get("generating"): return
            state["processing"] = True
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            _b().send_message(uid, "🔎 <b>Verifying your response...</b>", parse_mode="HTML")
            
            if data == "f_save":
                if state.get("selected") is None: 
                    state["processing"] = False
                    return
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    q_subtopic = state["q"].get("subtopic", "General")
                    health.record_attempt(uid, state["subj"], state["chapter"], q_subtopic, is_correct, time_taken)
                except: pass
                
                msg = f"✅ <b>Correct!</b>\n\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\n\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)\n\n"
                msg += format_ultimate_solution(state['q'])
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":
                state["skipped"] += 1
                if state.get("q"):
                    correct = state["q"].get("correct_index", 0)
                    exp = clean_math(state["q"].get("explanation", ""))
                    msg = f"⏭ <b>Correct Answer: Option {chr(65+correct)}</b>\n\n📝 <b>Explanation:</b>\n{exp}"
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
            
            state["selected"] = None
            state["processing"] = False

        elif data == "f_pyq_cont":
            state["pyq_phase"] = "skipped"
            state["pyq_questions"] = state.get("pyq_skipped", [])
            state["pyq_index"] = 0
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_doubt":
            state["waiting_for_doubt"] = True
            _b().send_message(uid, "💬 <b>Please type your doubt about this question or explanation.</b>\nHamilton will answer it for you.", parse_mode="HTML")
            
        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

        elif data == "f_stop":
            state["active"] = False
            if state.get("mode") == "pyq":
                c = state.get("correct", 0)
                w = state.get("wrong", 0)
                s = state.get("skipped", 0)
                msg = f"🛑 <b>PYQ Practice Stopped</b>\n\n✅ Correct: {c}\n❌ Wrong: {w}\n⏭ Skipped: {s}"
                _b().send_message(uid, msg, parse_mode="HTML")
            state["processing"] = False
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            _generate_report(uid)
            
        elif data == "f_retry":
            if state.get("generating"): return
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

    except Exception as e:
        print(f"[ROUTER-ERR] {e}")

def _generate_report(uid):
    state = _state.get(uid, {})
    total = state.get("correct", 0) + state.get("wrong", 0) + state.get("skipped", 0)
    if total == 0:
        _b().send_message(uid, "🛑 Session stopped.")
        return
    acc = (state["correct"] / total) * 100 if total > 0 else 0
    health_delta = (state["correct"] * 1.5) - (state["wrong"] * 1.0)
    msg = f"🏁 <b>SESSION REPORT</b>\n\n📊 <b>Attempted:</b> {total}\n✅ <b>Correct:</b> {state['correct']}\n❌ <b>Wrong:</b> {state['wrong']}\n⏭ <b>Skipped:</b> {state['skipped']}\n\n🎯 <b>Accuracy:</b> {acc:.1f}%\n❤️ <b>Health Update:</b> {health_delta:+.1f}%\n\n📚 <i>Want a personal Mastery Analyzer? Contact us on WhatsApp:</i> <a href='https://wa.me/918074231426'>H&K Publications</a>"
    _b().send_message(uid, msg, parse_mode="HTML", disable_web_page_preview=True)

def _generate_next(uid, msg_id=None):
    state = _state.get(uid, {})
    if not state.get("active"): return
    state["generating"] = True
    state["q_count"] = state.get("q_count", 0) + 1
    count = state["q_count"]
    
    if count > 100:
        state["active"] = False
        _b().send_message(uid, "🎉 <b>Mastery Complete!</b> You have covered the entire syllabus.")
        return

    if msg_id: loader_msg = msg_id
    else:
        msg = _b().send_message(uid, f"⏳ Generating Q{count}...", parse_mode="HTML")
        loader_msg = msg.message_id
        threading.Thread(target=_animate_gen, args=(uid, loader_msg, count), daemon=True).start()

    import ai_client
    mode = state.get("mode", "practice")
    diff = random.randint(3, 9)
    ideal_time = {3: 45, 4: 60, 5: 75, 6: 90, 7: 90, 8: 100, 9: 110}.get(diff, 90)
    source = random.choice(["JEE Adv 2023", "JEE Main 2024", "Arihant", "Cengage", "JEE Adv 2021"])
    q_type = random.choice(["MCQ", "Multi-Correct", "Numerical", "Integer", "Assertion-Reason", "Statement-based", "Match-the-following", "Passage-based", "Matrix"])
    
    prompt = f"Generate a JEE question for '{state['chapter']}' (Subject: {state['subj']}).\n"
    prompt += f"Target Difficulty: {diff}/10. Question Type: {q_type}. Source: {source}.\n"
    prompt += "RULES:\n1. Output strictly as JSON.\n2. NO LATEX. Use Unicode (α, √, π, ⁰, ²).\n3. Explanation must be direct and concise.\n"
    prompt += '{"question":"...", "subtopic":"...", "concept":"...", "options":["A","B","C","D"], "correct_index":0, "explanation":"..."}\n'

    q = None
    for attempt in range(3):
        try:
            raw = ai_client._call_groq(0, "Output ONLY valid JSON.", prompt, max_tokens=1200, temperature=0.7)
            if not raw or not raw.strip(): continue
            txt = raw.strip()
            if txt.startswith("```"): txt = re.sub(r"^```(?:json)?\s*", "", txt); txt = re.sub(r"\s*```\s*$", "", txt)
            first, last = txt.find("{"), txt.rfind("}")
            if first == -1 or last == -1: continue
            q = json.loads(txt[first:last+1])
            if "question" in q and "options" in q:
                q["difficulty"] = diff
                q["ideal_time"] = ideal_time
                q["source"] = source
                q["q_type"] = q_type
                break
        except Exception:
            q = None
            time.sleep(1)
            
    if not q:
        try: _b().delete_message(uid, loader_msg)
        except: pass
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🔄 Retry", callback_data="f_retry"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().send_message(uid, "⚠️ <b>AI faced an error generating this question.</b>\n\nClick Retry to try again.", parse_mode="HTML", reply_markup=kb)
        state["generating"] = False
        return
        
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    
    header = f"<b>[{mode.upper()} | Q{count}]</b>\n"
    header += f"📖 <b>{state['chapter']}</b> → {q.get('subtopic', 'General')}\n"
    header += f"🧠 Concept: {q.get('concept', 'General')}\n"
    header += f"🎯 Pattern: {q.get('q_type', 'MCQ')} | Difficulty: {q.get('difficulty', 5)}/10 | ⏱️ Ideal: {q.get('ideal_time', 60)}s\n"
    header += f"🏷️ Source: {q.get('source', 'AI')}\n"
    header += "━━━━━━━━━━━━━━━\n\n"
    
    body = header + f"{clean_math(q.get('question', ''))}\n\n"
    for i, opt in enumerate(q.get("options", [])[:4]):
        body += f"<b>{chr(65+i)})</b> {clean_math(opt)}\n"
        
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    state["kb"] = kb
    state["generating"] = False
    state["processing"] = False
    
    try:
        _b().delete_message(uid, loader_msg)
        msg = _b().send_message(uid, body, parse_mode="HTML", reply_markup=kb)
        state["msg_id"] = msg.message_id
        state["question_msg_id"] = msg.message_id
        
        timer_msg = _b().send_message(uid, "⏱️ <b>Time Taken:</b> 0s", parse_mode="HTML")
        threading.Thread(target=_run_floating_timer, args=(uid, timer_msg.message_id, msg.message_id), daemon=True).start()
    except Exception as e:
        print(f"[SEND-ERR] {e}")

print("✅ c04_exam: FINAL PYQ & EXAM ENGINE LOADED.")


def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    # Check if current phase is done
    if idx >= len(q_list):
        if state.get("pyq_phase") == "eligible" and state.get("pyq_skipped"):
            # Transition to Phase 2
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("▶️ Continue Older", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
            _b().send_message(uid, "🎓 <b>You have completed enough PYQ revision for conceptual understanding in depth.</b>\n\nIf you want to continue with older/skipped PYQs, click Continue. Or click Stop to get your result.", reply_markup=kb)
        else:
            # Everything done
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🛑 Stop & View Result", callback_data="f_stop"))
            _b().send_message(uid, "🏁 <b>All PYQs from this chapter are completed!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False

    phase_name = "Core" if state.get("pyq_phase") == "eligible" else "Older"
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\n📅 {q.get('source', 'JEE Main')}\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\n📊 Difficulty: {q.get('difficulty', 'Medium')}"
    
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

def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    if not text: return ""
    t = str(text)
    t = html.unescape(t).replace("*", "").replace("_", " ")
    t = t.replace("\\alpha", "α").replace("\\beta", "β").replace("\\theta", "θ").replace("\\pi", "π")
    t = t.replace("\\times", "×").replace("\\cdot", "•").replace("\\sqrt", "√").replace("\\infty", "∞")
    t = t.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "").replace("$", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    sup = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    t = re.sub(r'\^([0-9+\-]+)', lambda m: m.group(1).translate(sup), t)
    t = re.sub(r'_([0-9]+)', lambda m: m.group(1).translate(sub), t)
    return t.strip()

def _extract_chapters(raw_data):
    chapters = set()
    if isinstance(raw_data, dict):
        for k, v in raw_data.items():
            if isinstance(v, dict) and "chapter" in v: chapters.add(v["chapter"])
            else: chapters.add(k)
    elif isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                ch = item.get("chapter") or item.get("name") or item.get("topic")
                if ch: chapters.add(ch)
    return sorted(list(chapters))

def _animate_gen(uid, msg_id, count):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if not state.get("generating"): return
        try: _b().edit_message_text(f"⏳ Generating Q{count}... ({elapsed}s)", chat_id=uid, message_id=msg_id, parse_mode="HTML")
        except: pass

def _run_floating_timer(uid, timer_msg_id, question_msg_id):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id)
            except: pass
            return
        try: 
            _b().edit_message_text(f"⏱️ <b>Time Taken:</b> {elapsed}s", chat_id=uid, message_id=timer_msg_id, parse_mode="HTML")
        except: pass

def _strip_old_buttons(uid):
    state = _state.get(uid, {})
    old_msg = state.get("msg_id")
    if old_msg:
        try: _b().edit_message_reply_markup(uid, old_msg, reply_markup=None)
        except: pass
    state["msg_id"] = None

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
        InlineKeyboardButton("📝 Test", callback_data="f_mode:test")
    )
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(message.chat.id, "🎓 <b>Exam Center</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['conceptual'])
def cmd_conceptual(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"),
        InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional")
    )
    _b().send_message(message.chat.id, "🧠 <b>Concept Mastery</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

def _show_chapters(uid, msg_id):
    state = _state[uid]
    chapters = state.get("chapters", [])
    page = state.get("page", 0)
    start, end = page * 5, (page + 1) * 5
    chunk = chapters[start:end]
    
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(chunk):
        kb.add(InlineKeyboardButton(f"{start + i + 1}. {ch[:25]}", callback_data=f"f_ch:{ch}"))
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="f_page:-1"))
    if end < len(chapters): nav.append(InlineKeyboardButton("Next ➡️", callback_data="f_page:1"))
    if nav: kb.row(*nav)
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="f_back:sub"))
    
    try: _b().edit_message_text(f"📚 <b>Select Chapter:</b>\n(Showing {start+1}-{min(end, len(chapters))} of {len(chapters)})", chat_id=uid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]

    if data.startswith("f_ans:") and state.get("processing"): return
        
    try:
        if data.startswith("f_mode:"):
            mode = data.split(":")[1]
            _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
            
            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )
                kb.add(InlineKeyboardButton("🚧 JEE Adv (Coming Soon)", callback_data="f_soon"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("Physics", callback_data="f_sub:Physics"),
                InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"),
                InlineKeyboardButton("Maths", callback_data="f_sub:Maths")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "f_soon":
            _b().answer_callback_query(call.id, "Coming Soon!", show_alert=True)

        elif data.startswith("f_pyq:"):
            ptype = data.split(":")[1]
            import json
            try:
                with open("data/pyq_db.json") as f: db = json.load(f)
            except: db = {"practice": {}, "papers": {}}

            if ptype == "practice":
                kb = InlineKeyboardMarkup(row_width=3)
                for subj in db.get("practice", {}).keys():
                    kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📖 <b>PYQ Practice</b>\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            
            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                years = list(db.get("papers", {}).keys())
                if not years:
                    _b().answer_callback_query(call.id, "No papers uploaded yet.")
                    return
                for yr in years:
                    kb.add(InlineKeyboardButton(yr, callback_data=f"f_pyq_yr:{yr}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\nSelect Year:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json, re
            with open("data/pyq_db.json") as f: db = json.load(f)
            chapters = list(db.get("practice", {}).get(subj, {}).keys())

            # --- Syllabus-order anchor map (PDF coarse chapter -> syllabus fine chapter) ---
            _PYQ_OVERRIDES = {
                "Atoms and Nuclei": "Atomic Physics",
                "Capacitor": "Capacitor and Capacitance",
                "Center of Mass and Collision": "System of Particles and Centre of Mass",
                "Current Electricity": "Electric Current and Circuits",
                "Dual Nature of Radiation": "Dual Nature of Radiation and Matter",
                "Electrostatics": "Coulomb's Law and Electric Field",
                "Geometrical Optics": "Geometrical Optics: Part 1",
                "Heat and Thermodynamics": "Thermodynamics",
                "Laws of Motion": "Newton's Laws of Motion (Without Friction)",
                "Magnetic Effect of Current": "Magnetic Field and Magnetic Forces",
            }

            _syl_list = []
            try:
                _syl = json.load(open(f"data/jee_main_{subj.lower()}.json"))
                _syl_list = list(_syl.keys())
            except Exception:
                _syl_list = []

            def _pyq_pos(ch):
                if not _syl_list: return (2, 9999)
                if ch in _syl_list: return (0, _syl_list.index(ch))
                mapped = _PYQ_OVERRIDES.get(ch)
                if mapped and mapped in _syl_list: return (1, _syl_list.index(mapped))
                words = [w.lower() for w in re.findall(r"[A-Za-z]+", ch) if len(w) > 4]
                best_score, best_pos = 0, 9999
                for i, sc in enumerate(_syl_list):
                    s = sum(1 for w in words if w in sc.lower())
                    if s > best_score or (s == best_score and s > 0 and i < best_pos):
                        best_score, best_pos = s, i
                return (1, best_pos) if best_score > 0 else (2, 9999)

            chapters.sort(key=_pyq_pos)

            kb = InlineKeyboardMarkup(row_width=1)
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_ch:"):
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
            cmd_exam(call.message)

        elif data.startswith("f_back:"):
            target = data.split(":")[1]
            if target == "main": cmd_exam(call.message)
            elif target == "sub":
                mode = state.get("mode", "practice")
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_sub:"):
            subj = data.split(":")[1]
            state["subj"] = subj
            exam = state.get("exam", "jee_adv").lower()
            fn = f"data/{exam}_{subj.lower()}.json"
            try:
                with open(fn) as f: chapters = _extract_chapters(json.load(f))
            except: chapters = ["Motion in a Straight Line", "Units and Measurements"]
            state["chapters"] = chapters
            state["page"] = 0
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_page:"):
            state["page"] += int(data.split(":")[1])
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_ch:"):
            ch = data.split(":", 1)[1]
            state["chapter"] = ch
            state["q_count"] = 0
            _b().edit_message_text(f"⏳ Generating Q1...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
            threading.Thread(target=_generate_next, args=(uid, call.message.message_id), daemon=True).start()

        elif data.startswith("f_ans:"):
            if state.get("processing") or state.get("selected") is not None: return
            state["selected"] = int(data.split(":")[1])
            sel = state["selected"]
            kb = InlineKeyboardMarkup(row_width=4)
            kb.row(*[InlineKeyboardButton(f"{'✅' if i == sel else ''}{chr(65+i)}", callback_data=f"f_ans:{i}") for i in range(4)])
            kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            state["kb"] = kb
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
            except: pass

        elif data in ("f_save", "f_skip"):
            if state.get("processing") or state.get("generating"): return
            state["processing"] = True
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            _b().send_message(uid, "🔎 <b>Verifying your response...</b>", parse_mode="HTML")
            
            if data == "f_save":
                if state.get("selected") is None: 
                    state["processing"] = False
                    return
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    q_subtopic = state["q"].get("subtopic", "General")
                    health.record_attempt(uid, state["subj"], state["chapter"], q_subtopic, is_correct, time_taken)
                except: pass
                
                msg = f"✅ <b>Correct!</b>\n\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\n\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)\n\n"
                msg += format_ultimate_solution(state['q'])
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":
                state["skipped"] += 1
                if state.get("q"):
                    correct = state["q"].get("correct_index", 0)
                    exp = clean_math(state["q"].get("explanation", ""))
                    msg = f"⏭ <b>Correct Answer: Option {chr(65+correct)}</b>\n\n📝 <b>Explanation:</b>\n{exp}"
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
            
            state["selected"] = None
            state["processing"] = False

        elif data == "f_pyq_cont":
            state["pyq_phase"] = "skipped"
            state["pyq_questions"] = state.get("pyq_skipped", [])
            state["pyq_index"] = 0
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_doubt":
            state["waiting_for_doubt"] = True
            _b().send_message(uid, "💬 <b>Please type your doubt about this question or explanation.</b>\nHamilton will answer it for you.", parse_mode="HTML")
            
        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

        elif data == "f_stop":
            state["active"] = False
            if state.get("mode") == "pyq":
                c = state.get("correct", 0)
                w = state.get("wrong", 0)
                s = state.get("skipped", 0)
                msg = f"🛑 <b>PYQ Practice Stopped</b>\n\n✅ Correct: {c}\n❌ Wrong: {w}\n⏭ Skipped: {s}"
                _b().send_message(uid, msg, parse_mode="HTML")
            state["processing"] = False
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            _generate_report(uid)
            
        elif data == "f_retry":
            if state.get("generating"): return
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

    except Exception as e:
        print(f"[ROUTER-ERR] {e}")

def _generate_report(uid):
    state = _state.get(uid, {})
    total = state.get("correct", 0) + state.get("wrong", 0) + state.get("skipped", 0)
    if total == 0:
        _b().send_message(uid, "🛑 Session stopped.")
        return
    acc = (state["correct"] / total) * 100 if total > 0 else 0
    health_delta = (state["correct"] * 1.5) - (state["wrong"] * 1.0)
    msg = f"🏁 <b>SESSION REPORT</b>\n\n📊 <b>Attempted:</b> {total}\n✅ <b>Correct:</b> {state['correct']}\n❌ <b>Wrong:</b> {state['wrong']}\n⏭ <b>Skipped:</b> {state['skipped']}\n\n🎯 <b>Accuracy:</b> {acc:.1f}%\n❤️ <b>Health Update:</b> {health_delta:+.1f}%\n\n📚 <i>Want a personal Mastery Analyzer? Contact us on WhatsApp:</i> <a href='https://wa.me/918074231426'>H&K Publications</a>"
    _b().send_message(uid, msg, parse_mode="HTML", disable_web_page_preview=True)

def _generate_next(uid, msg_id=None):
    state = _state.get(uid, {})
    if not state.get("active"): return
    state["generating"] = True
    state["q_count"] = state.get("q_count", 0) + 1
    count = state["q_count"]
    
    if count > 100:
        state["active"] = False
        _b().send_message(uid, "🎉 <b>Mastery Complete!</b> You have covered the entire syllabus.")
        return

    if msg_id: loader_msg = msg_id
    else:
        msg = _b().send_message(uid, f"⏳ Generating Q{count}...", parse_mode="HTML")
        loader_msg = msg.message_id
        threading.Thread(target=_animate_gen, args=(uid, loader_msg, count), daemon=True).start()

    import ai_client
    mode = state.get("mode", "practice")
    diff = random.randint(3, 9)
    ideal_time = {3: 45, 4: 60, 5: 75, 6: 90, 7: 90, 8: 100, 9: 110}.get(diff, 90)
    source = random.choice(["JEE Adv 2023", "JEE Main 2024", "Arihant", "Cengage", "JEE Adv 2021"])
    q_type = random.choice(["MCQ", "Multi-Correct", "Numerical", "Integer", "Assertion-Reason", "Statement-based", "Match-the-following", "Passage-based", "Matrix"])
    
    prompt = f"Generate a JEE question for '{state['chapter']}' (Subject: {state['subj']}).\n"
    prompt += f"Target Difficulty: {diff}/10. Question Type: {q_type}. Source: {source}.\n"
    prompt += "RULES:\n1. Output strictly as JSON.\n2. NO LATEX. Use Unicode (α, √, π, ⁰, ²).\n3. Explanation must be direct and concise.\n"
    prompt += '{"question":"...", "subtopic":"...", "concept":"...", "options":["A","B","C","D"], "correct_index":0, "explanation":"..."}\n'

    q = None
    for attempt in range(3):
        try:
            raw = ai_client._call_groq(0, "Output ONLY valid JSON.", prompt, max_tokens=1200, temperature=0.7)
            if not raw or not raw.strip(): continue
            txt = raw.strip()
            if txt.startswith("```"): txt = re.sub(r"^```(?:json)?\s*", "", txt); txt = re.sub(r"\s*```\s*$", "", txt)
            first, last = txt.find("{"), txt.rfind("}")
            if first == -1 or last == -1: continue
            q = json.loads(txt[first:last+1])
            if "question" in q and "options" in q:
                q["difficulty"] = diff
                q["ideal_time"] = ideal_time
                q["source"] = source
                q["q_type"] = q_type
                break
        except Exception:
            q = None
            time.sleep(1)
            
    if not q:
        try: _b().delete_message(uid, loader_msg)
        except: pass
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🔄 Retry", callback_data="f_retry"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().send_message(uid, "⚠️ <b>AI faced an error generating this question.</b>\n\nClick Retry to try again.", parse_mode="HTML", reply_markup=kb)
        state["generating"] = False
        return
        
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    
    header = f"<b>[{mode.upper()} | Q{count}]</b>\n"
    header += f"📖 <b>{state['chapter']}</b> → {q.get('subtopic', 'General')}\n"
    header += f"🧠 Concept: {q.get('concept', 'General')}\n"
    header += f"🎯 Pattern: {q.get('q_type', 'MCQ')} | Difficulty: {q.get('difficulty', 5)}/10 | ⏱️ Ideal: {q.get('ideal_time', 60)}s\n"
    header += f"🏷️ Source: {q.get('source', 'AI')}\n"
    header += "━━━━━━━━━━━━━━━\n\n"
    
    body = header + f"{clean_math(q.get('question', ''))}\n\n"
    for i, opt in enumerate(q.get("options", [])[:4]):
        body += f"<b>{chr(65+i)})</b> {clean_math(opt)}\n"
        
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    state["kb"] = kb
    state["generating"] = False
    state["processing"] = False
    
    try:
        _b().delete_message(uid, loader_msg)
        msg = _b().send_message(uid, body, parse_mode="HTML", reply_markup=kb)
        state["msg_id"] = msg.message_id
        state["question_msg_id"] = msg.message_id
        
        timer_msg = _b().send_message(uid, "⏱️ <b>Time Taken:</b> 0s", parse_mode="HTML")
        threading.Thread(target=_run_floating_timer, args=(uid, timer_msg.message_id, msg.message_id), daemon=True).start()
    except Exception as e:
        print(f"[SEND-ERR] {e}")

print("✅ c04_exam: FINAL PYQ & EXAM ENGINE LOADED.")


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
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)}</b>\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\n📊 Difficulty: {q.get('difficulty', 'Medium')}"
    
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
