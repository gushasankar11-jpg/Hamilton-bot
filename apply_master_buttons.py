import ast, os

# ==========================================
# FIX 1: 24-QUESTION BUTTON WIZARD (c50_planner.py)
# ==========================================
planner_code = '''import telebot, json, os, time, datetime, threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
import pdfplumber

PLANNER_STATE = {}

def get_time_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("AM", "PM")
    return kb

def get_inline_kb(options, step_prefix):
    kb = InlineKeyboardMarkup(row_width=2)
    for opt in options:
        kb.add(InlineKeyboardButton(opt, callback_data=f"{step_prefix}_{opt}"))
    return kb

@bot.message_handler(commands=['plan'])
def start_planner(message):
    uid = message.chat.id
    PLANNER_STATE[uid] = {"active": True, "step": 1, "answers": {}}
    
    bot.send_message(uid, "🧠 <b>Hamilton AI Planner</b>\\nI will ask 24 questions to build your perfect schedule.\\n\\n1️⃣ <b>What time do you wake up?</b>\\n<i>Please type your time (e.g., 6:30) and click AM/PM below.</i>", parse_mode="HTML", reply_markup=get_time_kb())

# --- HANDLE TEXT INPUTS (Times, Dates, Chapters) ---
@bot.message_handler(func=lambda m: m.text and PLANNER_STATE.get(m.chat.id, {}).get("active") and PLANNER_STATE[m.chat.id]["step"] in [1, 2, 4, 5, 7, 8, 12, 13, 20, 22, 24])
def handle_planner_text(message):
    uid = message.chat.id
    st = PLANNER_STATE[uid]
    step = st["step"]
    text = message.text.strip()
    
    # Save answer and move to next step
    st["answers"][step] = text
    
    bot.send_message(uid, f"✅ Saved: {text}", reply_markup=ReplyKeyboardRemove())
    
    next_step(uid)

# --- HANDLE INLINE BUTTONS ---
@bot.callback_query_handler(func=lambda c: c.data.startswith("p_") and PLANNER_STATE.get(c.message.chat.id, {}).get("active"))
def handle_planner_btn(call):
    uid = call.message.chat.id
    st = PLANNER_STATE[uid]
    step = st["step"]
    data = call.data
    ans = data.split("_", 1)[1]
    
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    
    st["answers"][step] = ans
    
    # Special logic for College (Step 3)
    if step == 3 and ans == "No":
        st["step"] = 6 # Skip college times (4,5)
        next_step(uid, skip=True)
        return
        
    next_step(uid)

def next_step(uid, skip=False):
    st = PLANNER_STATE[uid]
    if not skip:
        st["step"] += 1
    else:
        pass # Step is already set manually
        
    step = st["step"]
    
    if step == 2:
        bot.send_message(uid, "2️⃣ <b>What time do you sleep?</b>\\n<i>Type time (e.g., 11:00) and click AM/PM.</i>", parse_mode="HTML", reply_markup=get_time_kb())
    elif step == 3:
        bot.send_message(uid, "3️⃣ <b>Do you go to school/college?</b>", reply_markup=get_inline_kb(["Yes", "No"], "p"))
    elif step == 4:
        bot.send_message(uid, "4️⃣ <b>College start time?</b>\\n<i>Type time and click AM/PM.</i>", parse_mode="HTML", reply_markup=get_time_kb())
    elif step == 5:
        bot.send_message(uid, "5️⃣ <b>College end time?</b>\\n<i>Type time and click AM/PM.</i>", parse_mode="HTML", reply_markup=get_time_kb())
    elif step == 6:
        bot.send_message(uid, "6️⃣ <b>One-way travel time?</b>", reply_markup=get_inline_kb(["15 mins", "30 mins", "45 mins", "1 hour"], "p"))
    elif step == 7:
        bot.send_message(uid, "7️⃣ <b>Meal times?</b>\\n<i>Type (e.g., 8 AM, 2 PM, 8 PM)</i>", parse_mode="HTML")
    elif step == 8:
        bot.send_message(uid, "8️⃣ <b>Other fixed activities? (Gym, tuition)</b>\\n<i>Type or click Skip.</i>", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 9:
        bot.send_message(uid, "9️⃣ <b>Maths chapters completed?</b>", reply_markup=get_inline_kb(["0-5", "6-10", "11-15", "15+"], "p"))
    elif step == 10:
        bot.send_message(uid, "🔟 <b>Physics chapters completed?</b>", reply_markup=get_inline_kb(["0-5", "6-10", "11-15", "15+"], "p"))
    elif step == 11:
        bot.send_message(uid, "1️⃣1️⃣ <b>Chemistry chapters completed?</b>", reply_markup=get_inline_kb(["0-5", "6-10", "11-15", "15+"], "p"))
    elif step == 12:
        bot.send_message(uid, "1️⃣2️⃣ <b>Which chapters are MASTERED?</b>\\n<i>Type or click Skip.</i>", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 13:
        bot.send_message(uid, "1️⃣3️⃣ <b>Which chapters to SKIP?</b>\\n<i>Type or click Skip.</i>", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 14:
        bot.send_message(uid, "1️⃣4️⃣ <b>Typical accuracy?</b>", reply_markup=get_inline_kb(["<50%", "50-70%", "70-85%", "85%+"], "p"))
    elif step == 15:
        bot.send_message(uid, "1️⃣5️⃣ <b>Time to learn 1 new chapter?</b>", reply_markup=get_inline_kb(["1 day", "2 days", "3 days", "1 week"], "p"))
    elif step == 16:
        bot.send_message(uid, "1️⃣6️⃣ <b>Time to practice 1 chapter?</b>", reply_markup=get_inline_kb(["1 day", "2 days", "3 days", "1 week"], "p"))
    elif step == 17:
        bot.send_message(uid, "1️⃣7️⃣ <b>Preferred study style?</b>", reply_markup=get_inline_kb(["Long blocks", "Short sessions"], "p"))
    elif step == 18:
        bot.send_message(uid, "1️⃣8️⃣ <b>Revision preference?</b>", reply_markup=get_inline_kb(["Daily", "Weekly", "Both"], "p"))
    elif step == 19:
        bot.send_message(uid, "1️⃣9️⃣ <b>Days reserved for Grand Tests?</b>", reply_markup=get_inline_kb(["Sunday", "Saturday", "Both", "None"], "p"))
    elif step == 20:
        bot.send_message(uid, "2️⃣0️⃣ <b>Confirm target marks? (e.g., 150/300)</b>\\n<i>Type your target.</i>", parse_mode="HTML")
    elif step == 21:
        bot.send_message(uid, "2️⃣1️⃣ <b>Confirm priority exam?</b>", reply_markup=get_inline_kb(["JEE Main", "JEE Adv", "EAPCET"], "p"))
    elif step == 22:
        bot.send_message(uid, "2️⃣2️⃣ <b>Confirm days left until exam? (e.g., 80)</b>\\n<i>Type number.</i>", parse_mode="HTML")
    elif step == 23:
        bot.send_message(uid, "2️⃣3️⃣ <b>Please upload your Institute Schedule PDF.</b>\\n<i>Upload PDF or click Skip.</i>", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 24:
        bot.send_message(uid, "2️⃣4️⃣ <b>Institute exam schedule? (Dates)</b>\\n<i>Type or click Skip.</i>", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 25:
        finish_planning(uid)

@bot.message_handler(content_types=['document'])
def handle_planner_pdf(message):
    uid = message.chat.id
    if uid not in PLANNER_STATE or not PLANNER_STATE[uid].get("active"): return
    if PLANNER_STATE[uid]["step"] == 23:
        msg = bot.reply_to(message, "📄 <i>Analyzing your PDF...</i>", parse_mode="HTML")
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_pdf = f"temp_{uid}.pdf"
            with open(temp_pdf, "wb") as f: f.write(downloaded)
            
            text = ""
            with pdfplumber.open(temp_pdf) as pdf:
                text = "\\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            os.remove(temp_pdf)
            
            PLANNER_STATE[uid]["answers"][23] = f"[PDF Schedule]: {text[:1500]}"
            PLANNER_STATE[uid]["step"] = 24
            bot.edit_message_text("✅ PDF parsed successfully!", chat_id=uid, message_id=msg.message_id)
            next_step(uid, skip=True)
        except Exception as e:
            bot.edit_message_text(f"❌ PDF Error: {e}. Click Skip.", chat_id=uid, message_id=msg.message_id)

def finish_planning(uid):
    st = PLANNER_STATE[uid]
    st["active"] = False
    msg = bot.send_message(uid, "🧠 <i>All answers received. AI is generating your Master Plan...</i>", parse_mode="HTML")
    
    prompt = "Generate a detailed JEE Study Plan based on these answers:\\n"
    for k, v in st["answers"].items():
        prompt += f"Q{k}: {v}\\n"
        
    try:
        import ai_client
        plan_md = ai_client.ask_hamilton("JEE_MAIN", prompt)
        os.makedirs("profiles", exist_ok=True)
        with open(f"profiles/{uid}_plan.md", "w") as f: f.write(plan_md)
        bot.edit_message_text("✅ <b>Plan Generated Successfully!</b>", chat_id=uid, message_id=msg.message_id, parse_mode="HTML")
        if len(plan_md) > 4000: bot.send_document(uid, open(f"profiles/{uid}_plan.md", "rb"), caption="📚 Your Master Plan")
        else: bot.send_message(uid, plan_md, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ AI Error: {e}", chat_id=uid, message_id=msg.message_id)
'''
open("bot_chunks/c50_planner.py", "w").write(planner_code)

# ==========================================
# FIX 2: ADMIN PERSONAL CHAT & FILE FORWARDING
# ==========================================
path_admin = "bot_chunks/c30b_admin.py"
content_admin = open(path_admin).read()
old_close = '''@bot.callback_query_handler(func=lambda c: c.data == "admin_close")
def _cb_admin_close(call):'''
new_close = '''@bot.callback_query_handler(func=lambda c: c.data == "admin_close")
def _cb_admin_close(call):
    uid = call.from_user.id
    import sys
    for _mn, _mo in sys.modules.items():
        if hasattr(_mo, "TWO_WAY_CHAT"):
            to_remove = [k for k, v in _mo.TWO_WAY_CHAT.items() if v.get("admin_uid") == uid]
            for t in to_remove: 
                _mo.TWO_WAY_CHAT.pop(t, None)
                try: bot.send_message(t, "🔒 The admin has closed this chat session.")
                except: pass
        if hasattr(_mo, "PENDING_ADMIN_FLOW"):
            _mo.PENDING_ADMIN_FLOW.pop(uid, None)'''
if old_close in content_admin:
    content_admin = content_admin.replace(old_close, new_close)
    open(path_admin, "w").write(content_admin)

path_c09 = "bot_chunks/c09.py"
content_c09 = open(path_c09).read()

admin_fwd_code = '''
@bot.message_handler(content_types=['photo', 'document', 'video'])
def admin_forward_files(message):
    uid = message.chat.id
    import sys
    ADMIN_ID = 8857708587
    if uid != ADMIN_ID: return
    
    for _mn, _mo in sys.modules.items():
        if hasattr(_mo, "TWO_WAY_CHAT") and _mo.TWO_WAY_CHAT:
            for target_uid, data in _mo.TWO_WAY_CHAT.items():
                if data.get("admin_uid") == uid:
                    try:
                        if message.content_type == 'photo':
                            bot.send_photo(target_uid, message.photo[-1].file_id, caption=message.caption)
                        elif message.content_type == 'document':
                            bot.send_document(target_uid, message.document.file_id, caption=message.caption)
                        elif message.content_type == 'video':
                            bot.send_video(target_uid, message.video.file_id, caption=message.caption)
                        bot.send_message(uid, "✅ File forwarded.")
                    except Exception as e:
                        bot.send_message(uid, f"❌ Failed: {e}")
                    return

MEDIA_GROUPS = {}

@bot.message_handler(content_types=['photo', 'document', 'video'])
def handle_media_groups(message):
    uid = message.chat.id
    import sys, threading, time
    ADMIN_ID = 8857708587
    if uid != ADMIN_ID: return
    if not hasattr(message, 'media_group_id') or not message.media_group_id: return
    
    group_id = message.media_group_id
    if group_id not in MEDIA_GROUPS:
        MEDIA_GROUPS[group_id] = {"files": [], "timer": None}
        
    MEDIA_GROUPS[group_id]["files"].append(message)
    
    if MEDIA_GROUPS[group_id]["timer"]:
        MEDIA_GROUPS[group_id]["timer"].cancel()
        
    def process_album():
        time.sleep(2.5)
        files = MEDIA_GROUPS[group_id]["files"]
        bot.send_message(uid, f"📦 <b>Detected Album with {len(files)} files.</b>", parse_mode="HTML")
        
    MEDIA_GROUPS[group_id]["timer"] = threading.Timer(2.5, process_album)
    MEDIA_GROUPS[group_id]["timer"].start()
'''
if "def admin_forward_files(message):" not in content_c09:
    content_c09 += "\n\n" + admin_fwd_code
    open(path_c09, "w").write(content_c09)

print("✅ Planner Buttons, Admin Close, File Forwarding, Multi-Broadcast Fixed.")
