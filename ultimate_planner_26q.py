import os, ast

# 1. FIX c09.py (Strict command ignore)
path_c09 = "bot_chunks/c09.py"
if os.path.exists(path_c09):
    content = open(path_c09).read()
    if "def free_text_handler(message):" in content:
        content = content.replace(
            "def free_text_handler(message):\n",
            "def free_text_handler(message):\n    if message.text and message.text.startswith('/'): return # Ignore commands\n"
        )
        open(path_c09, "w").write(content)
        print("✅ c09.py: Interceptor permanently fixed.")

# 2. FIX Exam Center Freeze (Short index callbacks)
path_exam = "bot_chunks/c04_exam.py"
if os.path.exists(path_exam):
    content = open(path_exam).read()
    old_btn = 'kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_pyq_paper:{p_name}"))'
    new_btn = '''if "paper_list" not in state: state["paper_list"] = []
                    state["paper_list"].append(p_name)
                    kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_paper_idx:{len(state['paper_list'])-1}"))'''
    
    if old_btn in content:
        content = content.replace(old_btn, new_btn)
    
    if 'f_paper_idx:' not in content:
        new_handler = '''
        elif data.startswith("f_paper_idx:"):
            idx = int(data.split(":")[1])
            paper_name = state.get("paper_list", [])[idx]
            import json
            with open("data/pyq_master.json") as f: db = json.load(f)
            paper_data = db.get("papers", {}).get(paper_name)
            if not paper_data: return
            
            state["mode"] = "pyq"
            state["subj"] = "Full Paper"
            state["chapter"] = paper_name
            state["pyq_questions"] = paper_data.get("questions", [])
            state["pyq_index"] = 0
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            send_pyq_q(uid)
            return
'''
        if 'elif data.startswith("f_back:")' in content:
            content = content.replace('elif data.startswith("f_back:")', new_handler + '\n        elif data.startswith("f_back:")', 1)
            
    try:
        ast.parse(content)
        open(path_exam, "w").write(content)
    except SyntaxError as e:
        print(f"❌ c04_exam.py Syntax Error: {e}")

# 3. CREATE THE 26-QUESTION PLANNER WITH VISION AI
planner_code = '''import telebot, json, os, time, datetime, threading, base64
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

PLANNER_STATE = {}

QUESTIONS = [
    {"s": 1, "t": "Wake up time", "p": "1️⃣ <b>What time do you wake up?</b>\n<i>Type time (e.g. 6:00), click AM/PM.</i>", "type": "time"},
    {"s": 2, "t": "Sleep time", "p": "2️⃣ <b>What time do you go to sleep?</b>", "type": "time"},
    {"s": 3, "t": "School/College", "p": "3️⃣ <b>Do you attend school or college?</b>", "type": "btn", "o": ["Yes", "No"]},
    {"s": 4, "t": "College start", "p": "4️⃣ <b>If yes, what time does it start?</b>", "type": "time"},
    {"s": 5, "t": "College end", "p": "5️⃣ <b>What time does it end?</b>", "type": "time"},
    {"s": 6, "t": "Travel time", "p": "6️⃣ <b>One-way travel time?</b>", "type": "btn", "o": ["15m", "30m", "45m", "1h"]},
    {"s": 7, "t": "Meal times", "p": "7️⃣ <b>Meal times? (e.g. 8 AM, 2 PM, 8 PM)</b>", "type": "text"},
    {"s": 8, "t": "Fixed activities", "p": "8️⃣ <b>Any other fixed daily activities?</b>", "type": "btn", "o": ["Skip"]},
    {"s": 9, "t": "Maths progress", "p": "9️⃣ <b>Maths chapters completed?</b>", "type": "btn", "o": ["0-5", "6-10", "11-15", "15+"]},
    {"s": 10, "t": "Physics progress", "p": "🔟 <b>Physics chapters completed?</b>", "type": "btn", "o": ["0-5", "6-10", "11-15", "15+"]},
    {"s": 11, "t": "Chemistry progress", "p": "1️⃣1️⃣ <b>Chemistry chapters completed?</b>", "type": "btn", "o": ["0-5", "6-10", "11-15", "15+"]},
    {"s": 12, "t": "Mastered", "p": "1️⃣2️⃣ <b>Which chapters are MASTERED?</b>", "type": "btn", "o": ["Skip"]},
    {"s": 13, "t": "Skip List", "p": "1️⃣3️⃣ <b>Chapters you want to SKIP?</b>", "type": "btn", "o": ["Skip"]},
    {"s": 14, "t": "Maths accuracy", "p": "1️⃣4️⃣ <b>Maths accuracy?</b>", "type": "btn", "o": ["<50%", "50-70%", "70-85%", "85%+"]},
    {"s": 15, "t": "Physics accuracy", "p": "1️⃣5️⃣ <b>Physics accuracy?</b>", "type": "btn", "o": ["<50%", "50-70%", "70-85%", "85%+"]},
    {"s": 16, "t": "Chemistry accuracy", "p": "1️⃣6️⃣ <b>Chemistry accuracy?</b>", "type": "btn", "o": ["<50%", "50-70%", "70-85%", "85%+"]},
    {"s": 17, "t": "Learning speed", "p": "1️⃣7️⃣ <b>Hours to learn a new chapter?</b>", "type": "btn", "o": ["1-2 hrs", "3-4 hrs", "5-6 hrs", "6+ hrs"]},
    {"s": 18, "t": "Practice speed", "p": "1️⃣8️⃣ <b>Hours to practice solved problems?</b>", "type": "btn", "o": ["1-2 hrs", "3-4 hrs", "5-6 hrs", "6+ hrs"]},
    {"s": 19, "t": "Study style", "p": "1️⃣9️⃣ <b>Preferred study style?</b>", "type": "btn", "o": ["Long study block", "Multiple short sessions"]},
    {"s": 20, "t": "Revision style", "p": "2️⃣0️⃣ <b>Revision preference?</b>", "type": "btn", "o": ["Daily 30-min", "Weekly full revision"]},
    {"s": 21, "t": "Grand Tests", "p": "2️⃣1️⃣ <b>Days before exam to start Grand Tests?</b>", "type": "btn", "o": ["15 days", "20 days", "25 days"]},
    {"s": 22, "t": "Target marks", "p": "2️⃣2️⃣ <b>Confirm target marks (e.g. 150)</b>", "type": "text"},
    {"s": 23, "t": "Priority exam", "p": "2️⃣3️⃣ <b>Confirm priority exam.</b>", "type": "btn", "o": ["JEE Main", "JEE Adv", "AP EAPCET"]},
    {"s": 24, "t": "Time left", "p": "2️⃣4️⃣ <b>Days remaining until exam? (e.g. 80)</b>", "type": "text"},
    {"s": 25, "t": "Teaching Schedule", "p": "2️⃣5️⃣ <b>Upload Institute Teaching Schedule.</b>\\n<i>Send a PDF or Image. Click Skip if none.</i>", "type": "btn", "o": ["Skip"]},
    {"s": 26, "t": "Exam Schedule", "p": "2️⃣6️⃣ <b>Upload Institute Exam Schedule (Dates).</b>\\n<i>Send a PDF or Image. Click Skip if none.</i>", "type": "btn", "o": ["Skip"]}
]

def get_time_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("AM", "PM")
    return kb

def get_btn_kb(opts):
    kb = InlineKeyboardMarkup(row_width=2)
    for o in opts: kb.add(InlineKeyboardButton(o, callback_data=f"p_{o}"))
    return kb

# VISION AI ANALYZER FOR ANY FILE
def analyze_file_with_ai(file_bytes, mime_type, prompt_text):
    import ai_client
    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    if not gemini_keys: return "AI Keys unavailable."
    key = gemini_keys[0]
    
    img_b64 = base64.b64encode(file_bytes).decode('utf-8')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [
            {"text": prompt_text},
            {"inlineData": {"mimeType": mime_type, "data": img_b64}}
        ]}],
        "generationConfig": {"temperature": 0.1}
    }
    try:
        import requests
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=45)
        data = res.json()
        if "error" not in data:
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except: pass
    return "Could not analyze file."

# ==========================================
# NOTIFICATION ENGINE
# ==========================================
def notification_worker():
    while True:
        time.sleep(30)
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")
        if not os.path.exists("profiles"): continue
        for f in os.listdir("profiles"):
            if f.endswith("_plan.json"):
                uid = int(f.replace("_plan.json", ""))
                try:
                    plan = json.load(open(f"profiles/{f}"))
                    if not plan.get("completed"): continue
                    wake_time = plan.get("ans", {}).get("1", "06:00").replace(" AM", "").replace(" PM", "")
                    if wake_time == current_time and not plan.get("wake_sent"):
                        bot.send_message(uid, "🌅 <b>Good Morning!</b>\\nTime to wake up and start your day.", parse_mode="HTML")
                        plan["wake_sent"] = True
                        json.dump(plan, open(f"profiles/{f}", "w"))
                    if current_time == "00:00":
                        plan["wake_sent"] = False
                        json.dump(plan, open(f"profiles/{f}", "w"))
                except: pass

threading.Thread(target=notification_worker, daemon=True).start()

# ==========================================
# PLANNER LOGIC
# ==========================================
@bot.message_handler(commands=['plan'])
def start_planner(message):
    uid = message.chat.id
    os.makedirs("profiles", exist_ok=True)
    plan_file = f"profiles/{uid}_plan.json"
    
    if os.path.exists(plan_file):
        try:
            plan = json.load(open(plan_file))
            if plan.get("completed"):
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(InlineKeyboardButton("🔄 Start Fresh", callback_data="p_fresh"))
                kb.add(InlineKeyboardButton("✏️ Edit Specific Step", callback_data="p_edit_menu"))
                bot.send_message(uid, "🧠 <b>You already have a plan registered.</b>", parse_mode="HTML", reply_markup=kb)
                return
        except: pass
        
    PLANNER_STATE[uid] = {"active": True, "step": 1, "answers": {}}
    bot.send_message(uid, "🧠 <b>Hamilton AI Planner (26 Steps)</b>\\n\\n" + QUESTIONS[0]["p"], parse_mode="HTML", reply_markup=get_time_kb())

@bot.callback_query_handler(func=lambda c: c.data in ["p_fresh", "p_edit_menu", "p_cancel"])
def handle_plan_menu(call):
    uid = call.message.chat.id
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    if call.data == "p_fresh":
        PLANNER_STATE[uid] = {"active": True, "step": 1, "answers": {}}
        bot.send_message(uid, "🔄 <b>Wiped Old Plan.</b>\\n\\n" + QUESTIONS[0]["p"], parse_mode="HTML", reply_markup=get_time_kb())
    elif call.data == "p_edit_menu":
        kb = InlineKeyboardMarkup(row_width=2)
        for q in QUESTIONS:
            kb.add(InlineKeyboardButton(f"{q['s']}. {q['t']}", callback_data=f"p_edit_{q['s']}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="p_cancel"))
        bot.send_message(uid, "✏️ <b>Select step to edit:</b>", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_edit_"))
def handle_edit_step(call):
    uid = call.message.chat.id
    step = int(call.data.split("_")[2])
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    PLANNER_STATE[uid] = {"active": True, "step": step, "answers": {}}
    q = QUESTIONS[step-1]
    kb = get_time_kb() if q["type"] == "time" else (get_btn_kb(q["o"]) if q["type"] == "btn" else None)
    bot.send_message(uid, f"✏️ <b>Editing Step {step}: {q['t']}</b>\\n\\n{q['p']}", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_") and PLANNER_STATE.get(c.message.chat.id, {}).get("active") and c.data not in ["p_fresh", "p_edit_menu", "p_cancel"] and not c.data.startswith("p_edit_"))
def handle_inline_btn(call):
    uid = call.message.chat.id
    st = PLANNER_STATE[uid]
    ans = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    st["answers"][str(st["step"])] = ans
    if st["step"] == 3 and ans == "No": st["step"] = 6
    else: st["step"] += 1
    advance_wizard(uid)

@bot.message_handler(func=lambda m: PLANNER_STATE.get(m.chat.id, {}).get("active") and QUESTIONS[PLANNER_STATE[m.chat.id]["step"]-1]["type"] in ["time", "text"])
def handle_text_input(message):
    uid = message.chat.id
    st = PLANNER_STATE[uid]
    text = message.text.strip()
    bot.send_message(uid, f"✅ Saved: {text}", reply_markup=ReplyKeyboardRemove())
    st["answers"][str(st["step"])] = text
    st["step"] += 1
    advance_wizard(uid)

# --- FILE UPLOAD HANDLER (PDF & Images) ---
@bot.message_handler(content_types=['document', 'photo'])
def handle_planner_file(message):
    uid = message.chat.id
    if uid not in PLANNER_STATE or not PLANNER_STATE[uid].get("active"): return
    if PLANNER_STATE[uid]["step"] not in [25, 26]: return
    
    msg = bot.reply_to(message, "📄 <i>Analyzing your file with AI...</i>", parse_mode="HTML")
    try:
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            mime = "image/jpeg"
        else:
            file_info = bot.get_file(message.document.file_id)
            mime = "application/pdf" if message.document.file_name.endswith('.pdf') else "image/jpeg"
            
        downloaded = bot.download_file(file_info.file_path)
        
        prompt = "Analyze this document/image. Extract all schedule details, dates, times, and subject names clearly."
        ai_text = analyze_file_with_ai(downloaded, mime, prompt)
        
        PLANNER_STATE[uid]["answers"][str(PLANNER_STATE[uid]["step"])] = f"[File Analyzed]: {ai_text[:1500]}"
        PLANNER_STATE[uid]["step"] += 1
        bot.edit_message_text("✅ File analyzed and saved!", chat_id=uid, message_id=msg.message_id)
        advance_wizard(uid)
    except Exception as e:
        bot.edit_message_text(f"❌ File Error: {e}. Click Skip.", chat_id=uid, message_id=msg.message_id)

def advance_wizard(uid):
    st = PLANNER_STATE[uid]
    if st["step"] > 26:
        return finish_planning(uid)
    q = QUESTIONS[st["step"]-1]
    kb = get_time_kb() if q["type"] == "time" else (get_btn_kb(q["o"]) if q["type"] == "btn" else None)
    bot.send_message(uid, q["p"], parse_mode="HTML", reply_markup=kb)

def finish_planning(uid):
    st = PLANNER_STATE[uid]
    st["active"] = False
    msg = bot.send_message(uid, "🧠 <i>Generating your 2 MD Files...</i>", parse_mode="HTML")
    json.dump({"completed": True, "ans": st["answers"], "wake_sent": False}, open(f"profiles/{uid}_plan.json", "w"))
    
    prompt = "Create TWO comprehensive JEE Study Plans in Markdown based on these answers:\\n"
    for k, v in st["answers"].items(): prompt += f"Q{k}: {v}\\n"
    prompt += "\\n===FILE_SEPARATOR===\\n"
    prompt += "File 1: DAILY ROUTINE. Hour-by-hour schedule.\\n"
    prompt += "File 2: MASTER PLAN. Day-by-day plan to exam. Include which chapters, materials, mock test websites, and PYQs. Balance this with the uploaded institute schedule.\\n"
    
    try:
        import ai_client
        response = ai_client.ask_hamilton("JEE_MAIN", prompt)
        parts = response.split("===FILE_SEPARATOR===")
        daily_md = parts[0].strip()
        master_md = parts[1].strip() if len(parts) > 1 else "Master Plan generation failed."
        
        open(f"profiles/{uid}_daily.md", "w").write(daily_md)
        open(f"profiles/{uid}_master.md", "w").write(master_md)
        
        bot.edit_message_text("✅ <b>Your 2 Plans are ready!</b>", chat_id=uid, message_id=msg.message_id, parse_mode="HTML")
        bot.send_document(uid, open(f"profiles/{uid}_daily.md", "rb"), caption="📅 Daily Routine")
        bot.send_document(uid, open(f"profiles/{uid}_master.md", "rb"), caption="🗺️ Master Plan (Today to Exam)")
    except Exception as e:
        bot.edit_message_text(f"❌ AI Error: {e}", chat_id=uid, message_id=msg.message_id)

print("✅ c50_planner: 26 Questions + Vision AI Upload loaded.")
'''

open("bot_chunks/c50_planner.py", "w").write(planner_code)
print("✅ Planner created.")

# REBUILD
with open("bot.py.new", "w") as out:
    for f in sorted(os.listdir("bot_chunks")):
        if f.endswith(".py") and f.startswith("c"):
            with open(os.path.join("bot_chunks", f), "r") as chunk:
                out.write(chunk.read())
                out.write("\n\n")

try:
    compile(open("bot.py.new").read(), "bot.py.new", "exec")
    os.system("mv bot.py.new bot.py")
    print("✅ BUILD OK")
except SyntaxError as e:
    print(f"❌ BUILD FAILED: {e}")
