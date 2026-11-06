import re
print('C50_START_MARK', flush=True)
#####C50_TOP#####
print('##### C50 START EXECUTING #####', flush=True)
import telebot, json, os, time, datetime, threading, base64, requests
import datetime as _safe_dt
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

def _analyze_schedule(ans):
    def _t(s):
        s = str(s).upper().replace(" ","").strip()
        for x in ["🌅","🌙","⏰","😴"]: s = s.replace(x,"")
        try:
            if "AM" in s or "PM" in s:
                pm = "PM" in s; s2 = s.replace("AM","").replace("PM","")
                p = s2.split(":"); h = int(p[0]); mi = int(p[1]) if len(p)>1 else 0
                if pm and h < 12: h += 12
                if not pm and h == 12: h = 0
            else:
                p = s.split(":"); h = int(p[0]); mi = int(p[1]) if len(p)>1 else 0
            return h*60 + mi
        except: return None
    wake = _t(ans.get("1","06:00")); sleep = _t(ans.get("2","23:00"))
    sleep_h = 7.0
    if wake is not None and sleep is not None:
        d = wake - sleep
        if d <= 0: d += 24*60
        sleep_h = round(d/60, 1)
    col_min = 0; a3 = str(ans.get("3",""))
    if "Yes" in a3 or "✅" in a3:
        cs = _t(ans.get("4","08:00")); ce = _t(ans.get("5","14:00"))
        if cs is not None and ce is not None and ce > cs: col_min += ce - cs
        tr = str(ans.get("6","30m"))
        if "15" in tr: col_min += 30
        elif "30" in tr: col_min += 60
        elif "45" in tr: col_min += 90
        elif "1h" in tr or "60" in tr: col_min += 120
    free_h = max(0, (24*60 - sleep_h*60 - col_min - 90 - 30)/60)
    study_day = round(free_h * 0.85, 1)
    days = 78
    try: days = int(str(ans.get("24","78")).split()[0])
    except: pass
    target = 150
    try: target = int(str(ans.get("22","150")).split()[0])
    except: pass
    req = 1200 if target >= 200 else (900 if target >= 150 else (600 if target >= 100 else 400))
    total_study = int(study_day * days); gap = req - total_study
    verdict = "SUFFICIENT" if gap <= 0 else ("TIGHT" if gap < 200 else "INSUFFICIENT")
    return {"sleep_hours": sleep_h, "free_hours": round(free_h,1), "daily_study": study_day,
            "total_study": total_study, "required": req, "gap": gap, "days": days,
            "target": target, "verdict": verdict, "sleep_warn": sleep_h < 7 or sleep_h > 9}



PLANNER_STATE = {}

QUESTIONS = [
    {"s": 1, "t": "Wake up time", "p": "🌅 <b>1. What time do you wake up?</b>\n<i>Type time (e.g. 6:30), click AM/PM.</i>", "type": "time"},
    {"s": 2, "t": "Sleep time", "p": "🌙 <b>2. What time do you go to sleep?</b>\n<i>Type time (e.g. 11:00), click AM/PM.</i>", "type": "time"},
    {"s": 3, "t": "School/College", "p": "🏫 <b>3. Do you attend school or college?</b>", "type": "btn", "o": ["✅ Yes", "❌ No"]},
    {"s": 4, "t": "College start", "p": "🚌 <b>4. If yes, what time does it start?</b>\n<i>Type time, click AM/PM.</i>", "type": "time"},
    {"s": 5, "t": "College end", "p": "🏠 <b>5. What time does it end?</b>\n<i>Type time, click AM/PM.</i>", "type": "time"},
    {"s": 6, "t": "Travel time", "p": "🚗 <b>6. How much time to travel one way?</b>", "type": "btn", "o": ["⏱ 15m", "⏱ 30m", "⏱ 45m", "⏱ 1h"]},
    {"s": 7, "t": "Meal times", "p": "🍽️ <b>7. Breakfast, lunch, and dinner times?</b>\n<i>Type (e.g. 8 AM, 2 PM, 8 PM)</i>", "type": "text"},
    {"s": 8, "t": "Fixed activities", "p": "🏋️ <b>8. Any other fixed daily activities?</b>\n<i>Type or click Skip.</i>", "type": "text"},
    {"s": 9, "t": "Maths progress", "p": "📐 <b>9. Maths chapters completed?</b>", "type": "btn", "o": ["0-5", "6-10", "11-15", "15+"]},
    {"s": 10, "t": "Physics progress", "p": "⚛️ <b>10. Physics chapters completed?</b>", "type": "btn", "o": ["0-5", "6-10", "11-15", "15+"]},
    {"s": 11, "t": "Chemistry progress", "p": "🧪 <b>11. Chemistry chapters completed?</b>", "type": "btn", "o": ["0-5", "6-10", "11-15", "15+"]},
    {"s": 12, "t": "Mastered", "p": "🏆 <b>12. Which chapters are MASTERED?</b>\n<i>Type or click Skip.</i>", "type": "text"},
    {"s": 13, "t": "Skip List", "p": "🚫 <b>13. Chapters you want to SKIP entirely?</b>\n<i>Type or click Skip.</i>", "type": "text"},
    {"s": 14, "t": "Maths accuracy", "p": "📐 <b>14. Typical accuracy in Maths?</b>", "type": "btn", "o": ["<50%", "50-70%", "70-85%", "85%+"]},
    {"s": 15, "t": "Physics accuracy", "p": "⚛️ <b>15. Typical accuracy in Physics?</b>", "type": "btn", "o": ["<50%", "50-70%", "70-85%", "85%+"]},
    {"s": 16, "t": "Chemistry accuracy", "p": "🧪 <b>16. Typical accuracy in Chemistry?</b>", "type": "btn", "o": ["<50%", "50-70%", "70-85%", "85%+"]},
    {"s": 17, "t": "Learning speed", "p": "📖 <b>17. Hours to learn a new chapter?</b>", "type": "btn", "o": ["1-2 hrs", "3-4 hrs", "5-6 hrs", "6+ hrs"]},
    {"s": 18, "t": "Practice speed", "p": "✍️ <b>18. Hours to practice solved problems?</b>", "type": "btn", "o": ["1-2 hrs", "3-4 hrs", "5-6 hrs", "6+ hrs"]},
    {"s": 19, "t": "Study style", "p": "🧠 <b>19. Preferred study style?</b>", "type": "btn", "o": ["Long block", "Short sessions"]},
    {"s": 20, "t": "Revision style", "p": "🔄 <b>20. Revision preference?</b>", "type": "btn", "o": ["Daily 30m", "Weekly full"]},
    {"s": 21, "t": "Grand Tests", "p": "📝 <b>21. Days before exam to start Grand Tests?</b>", "type": "btn", "o": ["15 days", "20 days", "25 days"]},
    {"s": 22, "t": "Target marks", "p": "🎯 <b>22. Confirm target marks (e.g. 150)</b>", "type": "text"},
    {"s": 23, "t": "Priority exam", "p": "📚 <b>23. Confirm priority exam.</b>", "type": "btn", "o": ["JEE Main", "JEE Adv", "AP EAPCET"]},
    {"s": 24, "t": "Time left", "p": "⏳ <b>24. Days remaining until exam? (e.g. 80)</b>", "type": "text"},
    {"s": 25, "t": "Teaching Schedule", "p": "🏫 <b>25. Upload Institute Teaching Schedule.</b>\n<i>Send a PDF or Image. Click Skip if none.</i>", "type": "btn", "o": ["⏭ Skip"]},
    {"s": 26, "t": "Exam Schedule", "p": "🗓️ <b>26. Upload Institute Exam Schedule (Dates).</b>\n<i>Send a PDF or Image. Click Skip if none.</i>", "type": "btn", "o": ["⏭ Skip"]}
]

def get_time_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.row("1","2","3"); kb.row("4","5","6"); kb.row("7","8","9")
    kb.row("0",":","AM"); kb.row("PM","🔙 Back")
    return kb

def get_btn_kb(opts, step):
    kb = InlineKeyboardMarkup(row_width=2)
    for o in opts: kb.add(InlineKeyboardButton(o, callback_data=f"p_{o}"))
    if step > 1: kb.add(InlineKeyboardButton("🔙 Back", callback_data="p_back"))
    return kb

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
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=45)
        data = res.json()
        if "error" not in data:
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except: pass
    return "Could not analyze file."

def notification_worker():
    while True:
        time.sleep(30)
        now = _safe_dt.datetime.now()
        current_time = now.strftime("%H:%M")
        if not os.path.exists("profiles"): continue
        for f in os.listdir("profiles"):
            if f.endswith("_plan.json"):
                uid = int(f.replace("_plan.json", ""))
                try:
                    plan = json.load(open(f"profiles/{f}"))
                    if not plan.get("completed"): continue
                    wake_time = plan.get("ans", {}).get("1", "06:00").replace(" AM", "").replace(" PM", "").replace("🌅 ", "")
                    if wake_time == current_time and not plan.get("wake_sent"):
                        bot.send_message(uid, "🌅 <b>Good Morning!</b>\nTime to wake up and start your day. 🚀", parse_mode="HTML")
                        plan["wake_sent"] = True
                        json.dump(plan, open(f"profiles/{f}", "w"))
                    if current_time == "00:00":
                        plan["wake_sent"] = False
                        json.dump(plan, open(f"profiles/{f}", "w"))
                except: pass

try:
    threading.Thread(target=notification_worker, daemon=True).start()
except Exception as _e:
    print(f"[c50] notif thread failed: {_e}", flush=True)

@bot.message_handler(commands=['plan'])
def start_planner(message):
    try:
        uid = message.chat.id
        os.makedirs("profiles", exist_ok=True)
        plan_file = f"profiles/{uid}_plan.json"
        
        if os.path.exists(plan_file):
            try:
                plan = json.load(open(plan_file))
                if plan.get("completed"):
                    kb = InlineKeyboardMarkup(row_width=1)
                    kb.add(InlineKeyboardButton("📎 Resend last files", callback_data="p_resend"))
                    kb.add(InlineKeyboardButton("🔁 Regenerate plan", callback_data="p_regen"))
                    kb.add(InlineKeyboardButton("🔄 Start Fresh", callback_data="p_fresh"))
                    kb.add(InlineKeyboardButton("✏️ Edit Specific Step", callback_data="p_edit_menu"))
                    bot.send_message(uid, "🧠 <b>You already have a plan registered.</b>\nWhat would you like to do?", parse_mode="HTML", reply_markup=kb)
                    return
            except: pass
            
        PLANNER_STATE[uid] = {"active": True, "step": 1, "answers": {}, "temp_time": ""}
        bot.send_message(uid, "🚀 <b>Welcome to the Hamilton AI Planner (26 Steps)!</b>\nLet's build your perfect study schedule.\n\n" + QUESTIONS[0]["p"], parse_mode="HTML", reply_markup=get_time_kb())
    except Exception as e:
        bot.reply_to(message, f"❌ Planner Error: {e}")

@bot.callback_query_handler(func=lambda c: c.data in ["p_resend","p_regen"])
def handle_resend_regen(call):
    uid = call.message.chat.id
    try: bot.answer_callback_query(call.id)
    except: pass
    if call.data == "p_resend":
        sent = 0
        for path, cap in [(f"profiles/{uid}_daily.md","📅 Daily Routine"),(f"profiles/{uid}_master.md","🗺️ Master Plan")]:
            try:
                if os.path.exists(path):
                    bot.send_document(uid, open(path,"rb"), caption=cap); sent += 1
            except Exception as e:
                try: bot.send_message(uid, f"⚠️ {cap} send fail: {e}")
                except: pass
        if sent == 0: bot.send_message(uid, "⚠️ No files found. Try Regenerate.")
    elif call.data == "p_regen":
        try:
            plan = json.load(open(f"profiles/{uid}_plan.json"))
            PLANNER_STATE[uid] = {"active": True, "step": 1, "answers": plan.get("ans", {}), "temp_time": ""}
            finish_planning(uid)
        except Exception as e:
            bot.send_message(uid, f"❌ Cannot regenerate: {e}")

@bot.callback_query_handler(func=lambda c: c.data in ["p_fresh", "p_edit_menu", "p_cancel"])
def handle_plan_menu(call):
    uid = call.message.chat.id
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    if call.data == "p_fresh":
        PLANNER_STATE[uid] = {"active": True, "step": 1, "answers": {}, "temp_time": ""}
        bot.send_message(uid, "🔄 <b>Wiped Old Plan. Starting fresh...</b>\n\n" + QUESTIONS[0]["p"], parse_mode="HTML", reply_markup=get_time_kb())
    elif call.data == "p_edit_menu":
        kb = InlineKeyboardMarkup(row_width=2)
        for q in QUESTIONS:
            kb.add(InlineKeyboardButton(f"{q['s']}. {q['t']}", callback_data=f"p_edit_{q['s']}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="p_cancel"))
        bot.send_message(uid, "✏️ <b>Select the step you want to edit:</b>", parse_mode="HTML", reply_markup=kb)
    elif call.data == "p_cancel":
        bot.send_message(uid, "❌ Cancelled.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_edit_"))
def handle_edit_step(call):
    uid = call.message.chat.id
    step = int(call.data.split("_")[2])
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    PLANNER_STATE[uid] = {"active": True, "step": step, "answers": {}, "temp_time": ""}
    q = QUESTIONS[step-1]
    kb = get_time_kb() if q["type"] == "time" else (get_btn_kb(q["o"], step) if q["type"] == "btn" else None)
    bot.send_message(uid, f"✏️ <b>Editing Step {step}: {q['t']}</b>\n\n{q['p']}", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "p_back" and PLANNER_STATE.get(c.message.chat.id, {}).get("active"))
def handle_back_btn(call):
    uid = call.message.chat.id
    st = PLANNER_STATE[uid]
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    
    st["step"] -= 1
    if st["step"] < 1: st["step"] = 1
    q = QUESTIONS[st["step"]-1]
    kb = get_time_kb() if q["type"] == "time" else (get_btn_kb(q["o"], st["step"]) if q["type"] == "btn" else None)
    
    # Show previous answer if it exists
    prev_ans = st["answers"].get(str(st["step"]), "")
    prefix = f"🔙 <i>Previous answer: {prev_ans}</i>\n\n" if prev_ans else ""
    bot.send_message(uid, prefix + q["p"], parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_") and PLANNER_STATE.get(c.message.chat.id, {}).get("active") and c.data not in ["p_fresh", "p_edit_menu", "p_cancel", "p_back"] and not c.data.startswith("p_edit_"))
def handle_inline_btn(call):
    uid = call.message.chat.id
    st = PLANNER_STATE[uid]
    ans = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    
    # For time buttons (AM/PM)
    if "AM" in ans or "PM" in ans:
        final_time = f"{st.get('temp_time', '')} {ans}"
        st["answers"][str(st["step"])] = final_time
        st["temp_time"] = ""
    else:
        st["answers"][str(st["step"])] = ans
    
    if st["step"] == 3 and "No" in ans: st["step"] = 6
    else: st["step"] += 1
    advance_wizard(uid)

@bot.message_handler(func=lambda m: PLANNER_STATE.get(m.chat.id, {}).get("active") and QUESTIONS[PLANNER_STATE[m.chat.id]["step"]-1]["type"] in ["time", "text"])
def handle_text_input(message):
    uid = message.chat.id; st = PLANNER_STATE[uid]; q = QUESTIONS[st["step"]-1]
    if q["type"] == "time":
        t = message.text.strip(); low = t.lower()
        if t == "🔙 Back" or low == "back":
            st["step"] = max(1, st["step"] - 1); st["temp_time"] = ""
            advance_wizard(uid); return
        if low in ("am","pm"):
            acc = (st.get("temp_time") or "").strip()
            if not acc:
                bot.send_message(uid, "⚠️ Enter digits first (e.g. 6:30), then tap AM/PM."); return
            full = acc + " " + low.upper()
            st["answers"][str(st["step"])] = full; st["temp_time"] = ""; st["step"] += 1
            bot.send_message(uid, f"✅ Saved: {full}", reply_markup=ReplyKeyboardRemove())
            advance_wizard(uid); return
        if "am" in low or "pm" in low:
            st["answers"][str(st["step"])] = t; st["temp_time"] = ""; st["step"] += 1
            bot.send_message(uid, f"✅ Saved: {t}", reply_markup=ReplyKeyboardRemove())
            advance_wizard(uid); return
        st["temp_time"] = (st.get("temp_time") or "") + t
        bot.send_message(uid, f"⏳ {st['temp_time']} — more digits, or AM/PM, or 🔙 Back."); return
    bot.send_message(uid, f"✅ Saved: {message.text}", reply_markup=ReplyKeyboardRemove())
    st["answers"][str(st["step"])] = message.text; st["step"] += 1
    advance_wizard(uid)

@bot.message_handler(content_types=['document', 'photo'])
def handle_planner_file(message):
    uid = message.chat.id
    if uid not in PLANNER_STATE or not PLANNER_STATE[uid].get("active"): return
    if PLANNER_STATE[uid]["step"] not in [25, 26]: return
    
    msg = bot.reply_to(message, "🧠 <i>Analyzing your file with AI Vision...</i>", parse_mode="HTML")
    try:
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            mime = "image/jpeg"
        else:
            file_info = bot.get_file(message.document.file_id)
            mime = "application/pdf" if message.document.file_name.endswith('.pdf') else "image/jpeg"
            
        downloaded = bot.download_file(file_info.file_path)
        prompt = "Extract all schedule details, dates, times, and subject names from this document/image clearly."
        ai_text = analyze_file_with_ai(downloaded, mime, prompt)
        
        PLANNER_STATE[uid]["answers"][str(PLANNER_STATE[uid]["step"])] = f"📄 [Schedule Details]: {ai_text[:1500]}"
        PLANNER_STATE[uid]["step"] += 1
        bot.edit_message_text("✅ <b>Schedule analyzed and saved!</b> 🎉", chat_id=uid, message_id=msg.message_id, parse_mode="HTML")
        advance_wizard(uid)
    except Exception as e:
        bot.edit_message_text(f"❌ File Error: {e}. Click Skip.", chat_id=uid, message_id=msg.message_id)

def advance_wizard(uid):
    st = PLANNER_STATE[uid]
    if st["step"] > 26:
        return finish_planning(uid)
    q = QUESTIONS[st["step"]-1]
    kb = get_time_kb() if q["type"] == "time" else (get_btn_kb(q["o"], st["step"]) if q["type"] == "btn" else None)
    bot.send_message(uid, q["p"], parse_mode="HTML", reply_markup=kb)

def _ai_call_safe(ek, prompt, label):
    try:
        import ai_client
    except Exception as e:
        return "", f"ai_client import failed: {e}"
    fn = None
    for name in ["ask_hamilton","ask_ai","ask","generate","chat_completion","complete"]:
        f = getattr(ai_client, name, None)
        if callable(f): fn = f; break
    if not fn:
        avail = [n for n in dir(ai_client) if not n.startswith("_") and callable(getattr(ai_client, n, None))]
        return "", f"no ask function. Available: {avail[:8]}"
    try:
        result = fn(ek, prompt)
        if not result: return "", f"{label}: empty response (check API quota/keys)"
        return str(result), None
    except Exception as e:
        return "", f"{label}: {type(e).__name__}: {str(e)[:150]}"

def finish_planning(uid):
    st = PLANNER_STATE[uid]; st["active"] = False
    msg = bot.send_message(uid, "🔍 <i>Step 1/4: Auditing schedule...</i>", parse_mode="HTML")
    try:
        json.dump({"completed": True, "ans": st["answers"], "wake_sent": False, "start_date": _safe_dt.date.today().isoformat()}, open(f"profiles/{uid}_plan.json","w"))
    except Exception as _e:
        print(f"[fp] save plan err: {_e}", flush=True)
    A = _analyze_schedule(st["answers"])
    L = {1:"Wake",2:"Sleep",3:"College",4:"Col start",5:"Col end",6:"Travel",7:"Meals",8:"Fixed",9:"Maths done",10:"Phy done",11:"Chem done",12:"Mastered",13:"Skipped",14:"Maths acc",15:"Phy acc",16:"Chem acc",17:"Learn spd",18:"Practice spd",19:"Style",20:"Revision",21:"GT last N days",22:"Target",23:"Exam",24:"TOTAL days",25:"Teach sched",26:"Exam sched"}
    ctx = ""
    for k, v in st["answers"].items():
        try: lbl = L.get(int(k), f"Q{k}")
        except: lbl = f"Q{k}"
        ctx += f"- {lbl}: {v}\n"
    total = str(st["answers"].get("24","N/A")); gt = str(st["answers"].get("21","N/A"))
    ex = str(st["answers"].get("23","JEE Main"))
    ek = "JEE_ADV" if "Adv" in ex else ("EAPCET" if "EAPCET" in ex.upper() or "EAMCET" in ex.upper() else "JEE_MAIN")
    audit = f"AUDIT: sleep={A['sleep_hours']}h ({'LOW' if A['sleep_warn'] else 'OK'}), free={A['free_hours']}h/d, study={A['daily_study']}h/d, total={A['total_study']}h/{A['days']}d, need~{A['required']}h, gap={A['gap']}h, verdict={A['verdict']}.\n"
    hdr = ("YOU ARE A STRICT JEE COACH. No fluff. Hard truth.\n\nSTUDENT:\n" + ctx + "\n" + audit +
           f"\nRULES:\n1. Total={total}. GT=LAST {gt} of {total}. Never confuse.\n2. If sleep<7h warn.\n3. If gap>0 prescribe extra hrs OR lower target.\n4. Priority: {ex}.\n5. Respect schedules.\n6. Specific chapters.\n7. Resources: NTA Abhyas, PW, Embibe, HC Verma, DC Pandey, NCERT.\n8. Push hard.\n9. FORMAT: Output CLEAN Markdown tables ONLY. Cells must be PLAIN text — NO quotation marks around values, NO backticks inside cells. Do NOT wrap output in ``` fences. Table format: header row | separator row | data rows. No blank lines between rows.\n\n")
    dp = hdr + "TASK: DAILY ROUTINE Markdown table: Time|Activity|Subject/Chapter|Duration|Why. Pomodoro 25/5.\n\nAfter markdown output EXACTLY:\n```json\n{\"blocks\":[{\"time\":\"05:00\",\"end\":\"05:10\",\"task\":\"Wake up\",\"type\":\"wake\",\"subject\":\"\",\"chapter\":\"\"}]}\n```\ntype in: wake,hygiene,breakfast,lunch,dinner,theory,pyq,revision,college,travel,study,break,sleep,other. 24h HH:MM. Valid JSON only."
    mp = hdr + f"TASK: MASTER PLAN Markdown, exactly {total} days. Table: Day#|Date|Subject|Chapter|Material|PYQs|Mock|Why now. Last {gt} days = grand tests."
    sp = hdr + f"TASK: ~250-word PLAIN TEXT strategy: (1) sleep verdict (2) {total}-day phases (3) subject priority (4) last {gt} days (5) reality-check (6) one hard truth."
    icon = "⚠️" if A["sleep_warn"] else "✅"
    m1 = (f"📊 <b>SCHEDULE AUDIT</b>\n\n{icon} Sleep: <b>{A['sleep_hours']}h/night</b> " + ("— below 7-8h" if A["sleep_warn"] else "— healthy") + "\n"
          f"⏱ Free: <b>{A['free_hours']}h/day</b>\n📚 Study: <b>{A['daily_study']}h/day</b>\n"
          f"📈 {A['days']}d: <b>{A['total_study']}h</b>\n🎯 Need for {A['target']}: ~<b>{A['required']}h</b>\n"
          f"📉 Gap: <b>{A['gap']}h</b> → <b>{A['verdict']}</b>")
    try: bot.send_message(uid, m1, parse_mode="HTML")
    except Exception as _e: print(f"[fp] m1 err: {_e}", flush=True)
    try: bot.edit_message_text("📝 <i>Step 2/4: Generating Daily Routine (~30s)...</i>", chat_id=uid, message_id=msg.message_id, parse_mode="HTML")
    except: pass
    dm, err1 = _ai_call_safe(ek, dp, "Daily routine")
    if err1:
        try: bot.send_message(uid, f"⚠️ {err1}")
        except: pass
    blks = []
    if dm:
        _m = re.search(r"```json\s*(\{.*?\})\s*```", dm, re.DOTALL)
        if not _m: _m = re.search(r'(\{"blocks"\s*:\s*\[.*?\]\s*\})', dm, re.DOTALL)
        if _m:
            try:
                raw = _m.group(1) if _m.lastindex else _m.group(0)
                obj = json.loads(raw); blks = obj.get("blocks", []) or []
                if blks:
                    try: init_daily_routine(uid, blks)
                    except Exception as _e1: print(f"[rt] init fail: {_e1}", flush=True)
                dm = dm[:_m.start()] + dm[_m.end():]
            except Exception as _e2: print(f"[rt] json parse fail: {_e2}", flush=True)
        dm = re.sub(r'^```[a-z]*\n', '', dm.strip()).strip()
        dm = re.sub(r'\n```$', '', dm).strip()
        dm = dm + "\n"
        try: open(f"profiles/{uid}_daily.md","w").write(dm)
        except: pass
    try: bot.edit_message_text("🗺️ <i>Step 3/4: Generating Master Plan (~30s)...</i>", chat_id=uid, message_id=msg.message_id, parse_mode="HTML")
    except: pass
    mm, err2 = _ai_call_safe(ek, mp, "Master plan")
    if err2:
        try: bot.send_message(uid, f"⚠️ {err2}")
        except: pass
    if mm:
        mm = re.sub(r'^```[a-z]*\n', '', mm.strip()).strip()
        mm = re.sub(r'\n```$', '', mm).strip()
        mm = mm + "\n"
        try: open(f"profiles/{uid}_master.md","w").write(mm)
        except: pass
    try: bot.edit_message_text("🧠 <i>Step 4/4: Generating Strategy (~15s)...</i>", chat_id=uid, message_id=msg.message_id, parse_mode="HTML")
    except: pass
    sx, err3 = _ai_call_safe(ek, sp, "Strategy")
    if sx:
        try: bot.send_message(uid, "🧠 <b>STRATEGY</b>\n\n" + sx[:3500], parse_mode="HTML")
        except: pass
    try:
        done_msg = "✅ <b>Plan ready!</b>" + (f"\n🔄 Tracker: {len(blks)} blocks. Use /today." if blks else "\n⚠️ No daily blocks from AI.")
        bot.edit_message_text(done_msg, chat_id=uid, message_id=msg.message_id, parse_mode="HTML")
    except: pass
    if dm:
        try: bot.send_document(uid, open(f"profiles/{uid}_daily.md","rb"), caption="📅 Daily Routine")
        except Exception as _e: bot.send_message(uid, f"⚠️ Daily file: {_e}")
    else:
        try: bot.send_message(uid, "❌ Daily Routine not generated (AI failed)")
        except: pass
    if mm:
        try: bot.send_document(uid, open(f"profiles/{uid}_master.md","rb"), caption=f"🗺️ Master Plan ({total} days)")
        except Exception as _e: bot.send_message(uid, f"⚠️ Master file: {_e}")
    else:
        try: bot.send_message(uid, "❌ Master Plan not generated (AI failed)")
        except: pass


@bot.message_handler(commands=["resend","regen"])
def cmd_resend_regen(message):
    uid = message.chat.id
    if "regen" in message.text.lower():
        try:
            plan = json.load(open(f"profiles/{uid}_plan.json"))
            PLANNER_STATE[uid] = {"active": True, "step": 1, "answers": plan.get("ans", {}), "temp_time": ""}
            finish_planning(uid)
        except Exception as e:
            bot.send_message(uid, f"❌ Cannot regenerate: {e}")
        return
    sent = 0
    for path, cap in [(f"profiles/{uid}_daily.md","📅 Daily Routine"),(f"profiles/{uid}_master.md","🗺️ Master Plan")]:
        try:
            if os.path.exists(path):
                bot.send_document(uid, open(path,"rb"), caption=cap); sent += 1
        except: pass
    if sent == 0: bot.send_message(uid, "⚠️ No files found. Try /regen")

print("✅ c50_planner: Master Version (Back Btn + Time Logic + Emojis) loaded.")

#####C50_BOTTOM#####
print('##### C50 FINISHED EXECUTING #####', flush=True)

print('C50_END_MARK', flush=True)
