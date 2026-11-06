import os, ast

# 1. CLEAN UP BROKEN FILES
if os.path.exists("bot_chunks/c50_planner.py"):
    os.remove("bot_chunks/c50_planner.py")

path_router = "bot_chunks/c100_router.py"
if os.path.exists(path_router):
    content = open(path_router).read()
    content = content.replace("import logging\ntelebot.logger.setLevel(logging.DEBUG)\n", "")
    open(path_router, "w").write(content)

# 2. FIX THE TEXT INTERCEPTOR (Ensures /plan and /exam are never swallowed)
path_c09 = "bot_chunks/c09.py"
if os.path.exists(path_c09):
    content = open(path_c09).read()
    if "def free_text_handler(message):" in content:
        content = content.replace(
            "def free_text_handler(message):",
            "def free_text_handler(message):\n    if message.text and message.text.startswith('/'): return"
        )
        open(path_c09, "w").write(content)

# 3. CREATE THE NEW PERFECT PLANNER
planner_code = '''import telebot, json, os, time, datetime, threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

PLANNER_STATE = {}

def get_time_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("AM", "PM")
    return kb

def get_inline_kb(options, prefix):
    kb = InlineKeyboardMarkup(row_width=2)
    for opt in options:
        kb.add(InlineKeyboardButton(opt, callback_data=f"{prefix}_{opt}"))
    return kb

@bot.message_handler(commands=['plan'])
def start_planner(message):
    uid = message.chat.id
    PLANNER_STATE[uid] = {"active": True, "step": 1, "answers": {}, "last_msg": None}
    try: bot.delete_message(uid, message.message_id)
    except: pass
    advance_wizard(uid)

@bot.message_handler(func=lambda m: PLANNER_STATE.get(m.chat.id, {}).get("active") and PLANNER_STATE[m.chat.id]["step"] in [1, 2, 4, 5, 7, 8, 12, 13, 20, 22, 24])
def handle_text_input(message):
    uid = message.chat.id
    st = PLANNER_STATE[uid]
    step = st["step"]
    text = message.text.strip()
    
    bot.send_message(uid, f"✅ Saved: {text}", reply_markup=ReplyKeyboardRemove())
    try: bot.delete_message(uid, st.get("last_msg"))
    except: pass
    
    st["answers"][step] = text
    st["step"] += 1
    advance_wizard(uid)

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_") and PLANNER_STATE.get(c.message.chat.id, {}).get("active"))
def handle_inline_btn(call):
    uid = call.message.chat.id
    st = PLANNER_STATE[uid]
    step = st["step"]
    ans = call.data.split("_", 1)[1]
    
    bot.answer_callback_query(call.id)
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    
    st["answers"][step] = ans
    if step == 3 and ans == "No": 
        st["step"] = 6
    else: 
        st["step"] += 1
    advance_wizard(uid)

def advance_wizard(uid):
    st = PLANNER_STATE[uid]
    step = st["step"]
    msg = None
    
    if step == 1: 
        msg = bot.send_message(uid, "1️⃣ <b>What time do you wake up?</b>\\nType time (e.g. 6:30), then click AM/PM.", parse_mode="HTML", reply_markup=get_time_kb())
    elif step == 2: 
        msg = bot.send_message(uid, "2️⃣ <b>What time do you sleep?</b>\\nType time (e.g. 11:00), then click AM/PM.", parse_mode="HTML", reply_markup=get_time_kb())
    elif step == 3: 
        msg = bot.send_message(uid, "3️⃣ <b>Do you go to school/college?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["Yes", "No"], "p"))
    elif step == 4: 
        msg = bot.send_message(uid, "4️⃣ <b>College start time?</b>\\nType time, click AM/PM.", parse_mode="HTML", reply_markup=get_time_kb())
    elif step == 5: 
        msg = bot.send_message(uid, "5️⃣ <b>College end time?</b>\\nType time, click AM/PM.", parse_mode="HTML", reply_markup=get_time_kb())
    elif step == 6: 
        msg = bot.send_message(uid, "6️⃣ <b>One-way travel time?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["15m", "30m", "45m", "1h"], "p"))
    elif step == 7: 
        msg = bot.send_message(uid, "7️⃣ <b>Meal times?</b>\\nType (e.g. 8 AM, 2 PM, 8 PM)", parse_mode="HTML")
    elif step == 8: 
        msg = bot.send_message(uid, "8️⃣ <b>Other fixed activities?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 9: 
        msg = bot.send_message(uid, "9️⃣ <b>Maths chapters completed?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["0-5", "6-10", "11-15", "15+"], "p"))
    elif step == 10: 
        msg = bot.send_message(uid, "🔟 <b>Physics chapters completed?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["0-5", "6-10", "11-15", "15+"], "p"))
    elif step == 11: 
        msg = bot.send_message(uid, "1️⃣1️⃣ <b>Chemistry chapters completed?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["0-5", "6-10", "11-15", "15+"], "p"))
    elif step == 12: 
        msg = bot.send_message(uid, "1️⃣2️⃣ <b>Which chapters are MASTERED?</b>\\nType or click Skip.", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 13: 
        msg = bot.send_message(uid, "1️⃣3️⃣ <b>Which chapters to SKIP?</b>\\nType or click Skip.", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 14: 
        msg = bot.send_message(uid, "1️⃣4️⃣ <b>Typical accuracy?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["<50%", "50-70%", "70-85%", "85%+"], "p"))
    elif step == 15: 
        msg = bot.send_message(uid, "1️⃣5️⃣ <b>Time to learn 1 new chapter?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["1 day", "2 days", "3 days", "1 week"], "p"))
    elif step == 16: 
        msg = bot.send_message(uid, "1️⃣6️⃣ <b>Time to practice 1 chapter?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["1 day", "2 days", "3 days", "1 week"], "p"))
    elif step == 17: 
        msg = bot.send_message(uid, "1️⃣7️⃣ <b>Preferred study style?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["Long blocks", "Short sessions"], "p"))
    elif step == 18: 
        msg = bot.send_message(uid, "1️⃣8️⃣ <b>Revision preference?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["Daily", "Weekly", "Both"], "p"))
    elif step == 19: 
        msg = bot.send_message(uid, "1️⃣9️⃣ <b>Days reserved for Grand Tests?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["Sunday", "Saturday", "Both", "None"], "p"))
    elif step == 20: 
        msg = bot.send_message(uid, "2️⃣0️⃣ <b>Confirm target marks? (e.g. 150/300)</b>\\nType target.", parse_mode="HTML")
    elif step == 21: 
        msg = bot.send_message(uid, "2️⃣1️⃣ <b>Confirm priority exam?</b>", parse_mode="HTML", reply_markup=get_inline_kb(["JEE Main", "JEE Adv", "EAPCET"], "p"))
    elif step == 22: 
        msg = bot.send_message(uid, "2️⃣2️⃣ <b>Confirm days left until exam? (e.g. 80)</b>\\nType number.", parse_mode="HTML")
    elif step == 23: 
        msg = bot.send_message(uid, "2️⃣3️⃣ <b>Upload your Institute Schedule PDF.</b>\\nUpload PDF or click Skip.", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 24: 
        msg = bot.send_message(uid, "2️⃣4️⃣ <b>Institute exam schedule? (Dates)</b>\\nType or click Skip.", parse_mode="HTML", reply_markup=get_inline_kb(["Skip"], "p"))
    elif step == 25: 
        return finish_planning(uid)
        
    if msg:
        st["last_msg"] = msg.message_id

@bot.message_handler(content_types=['document'])
def handle_planner_pdf(message):
    uid = message.chat.id
    if uid not in PLANNER_STATE or not PLANNER_STATE[uid].get("active"): return
    if PLANNER_STATE[uid]["step"] == 23:
        msg = bot.reply_to(message, "📄 <i>Analyzing PDF...</i>", parse_mode="HTML")
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_pdf = f"temp_{uid}.pdf"
            with open(temp_pdf, "wb") as f: f.write(downloaded)
            
            import pdfplumber
            text = ""
            with pdfplumber.open(temp_pdf) as pdf:
                text = "\\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            os.remove(temp_pdf)
            
            PLANNER_STATE[uid]["answers"][23] = f"[PDF]: {text[:1500]}"
            PLANNER_STATE[uid]["step"] = 24
            bot.edit_message_text("✅ PDF parsed!", chat_id=uid, message_id=msg.message_id)
            advance_wizard(uid)
        except Exception as e:
            bot.edit_message_text(f"❌ PDF Error. Click Skip.", chat_id=uid, message_id=msg.message_id)

def finish_planning(uid):
    st = PLANNER_STATE[uid]
    st["active"] = False
    msg = bot.send_message(uid, "🧠 <i>Generating your AI Master Plan...</i>", parse_mode="HTML")
    
    prompt = "Create a highly detailed JEE Study Plan in Markdown based on:\\n"
    for k, v in st["answers"].items(): prompt += f"Q{k}: {v}\\n"
    
    try:
        import ai_client
        plan_md = ai_client.ask_hamilton("JEE_MAIN", prompt)
        os.makedirs("profiles", exist_ok=True)
        plan_file = f"profiles/{uid}_plan.md"
        with open(plan_file, "w") as f: f.write(plan_md)
        
        bot.edit_message_text("✅ <b>Plan Generated Successfully!</b>", chat_id=uid, message_id=msg.message_id, parse_mode="HTML")
        bot.send_document(uid, open(plan_file, "rb"), caption="📚 Your AI Master Plan")
    except Exception as e:
        bot.edit_message_text(f"❌ AI Error: {e}", chat_id=uid, message_id=msg.message_id)

print("✅ c50_planner: Brand New Wizard loaded.")
'''

open("bot_chunks/c50_planner.py", "w").write(planner_code)
print("✅ c50_planner.py created successfully.")

# 4. REBUILD BOT
import subprocess
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

