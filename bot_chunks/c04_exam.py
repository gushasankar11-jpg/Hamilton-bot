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

def clean_math(text):
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

# ==========================================
# FLOATING TIMER & ANIMATION
# ==========================================
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
        # Stop if user answered, stopped, or question changed
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id) # Delete timer when done
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

# ==========================================
# MENUS
# ==========================================
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

# ==========================================
# ROUTER
# ==========================================
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
                kb.add(InlineKeyboardButton("🚧 EAPCET (Coming Soon)", callback_data="f_soon"))
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
            if ptype == "practice":
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(
                    InlineKeyboardButton("Physics", callback_data="f_sub:Physics"),
                    InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"),
                    InlineKeyboardButton("Maths", callback_data="f_sub:Maths")
                )
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📖 <b>PYQ Practice</b>\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            else:
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\n(Paper selection UI coming in next patch)", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")

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
                msg += f"📝 <b>Explanation:</b>\n{clean_math(state['q'].get('explanation', ''))}"
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
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

        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

        elif data == "f_stop":
            state["active"] = False
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
        # 1. Send Question
        msg = _b().send_message(uid, body, parse_mode="HTML", reply_markup=kb)
        state["msg_id"] = msg.message_id
        state["question_msg_id"] = msg.message_id
        
        # 2. Send Floating Timer Message
        timer_msg = _b().send_message(uid, "⏱️ <b>Time Taken:</b> 0s", parse_mode="HTML")
        
        # 3. Start Timer Thread editing ONLY the timer message
        threading.Thread(target=_run_floating_timer, args=(uid, timer_msg.message_id, msg.message_id), daemon=True).start()
    except Exception as e:
        print(f"[SEND-ERR] {e}")

print("✅ c04_exam: SEPARATE FLOATING TIMER & PYQ MENU LOADED.")
