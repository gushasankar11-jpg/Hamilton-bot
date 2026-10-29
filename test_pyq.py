import sys
sys.path.insert(0, '.')
import time
import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
import ai_client

TOKEN = config.TELEGRAM_TOKEN
bot = telebot.TeleBot(TOKEN)
MY_ID = 8857708587

PYQ_STATE = {}

@bot.message_handler(commands=['start_pyq'])
def start_isolated_pyq(message):
    uid = message.chat.id
    if uid != MY_ID:
        safe_send(uid, "Unauthorized")
        return
        
    PYQ_STATE[uid] = {"q_num": 1, "max_q": 3, "year": 2024}
    safe_send(uid, "🚀 *Forced PYQ Test Started!*\nChapter: Motion in a Straight Line\n\nFetching from 2024...", parse_mode="Markdown")
    
    fetch_and_send_pyq(uid)

def fetch_and_send_pyq(uid):
    state = PYQ_STATE.get(uid)
    if not state: return
    
    if state["q_num"] > state["max_q"]:
        safe_send(uid, "🏁 PYQ Test Complete.")
        PYQ_STATE.pop(uid, None)
        return

    safe_send(uid, f"⏳ Forcing AI to retrieve real PYQ for {state['year']}...", parse_mode="Markdown")
    
    exam = "JEE_ADV"
    chapter = "Motion in a Straight Line"
    year = state["year"]
    
    # THE FORCEFUL PROMPT
    prompt = f"You are an expert JEE Advanced Physics teacher. Retrieve a REAL, authentic Previous Year Question (PYQ) from JEE Advanced {year} for the chapter '{chapter}'. "
    prompt += "Do NOT say you don't know. You MUST retrieve a valid question from your training data. "
    prompt += "STRICT RULES: "
    prompt += "1. ALL math must be in LaTeX (use $ for inline, $$ for block). No plain text math. "
    prompt += "2. Output strictly as JSON: {\\\"question\\\":\\\"...\\\", \\\"options\\\":[\\\"$A$\\\",\\\"$B$\\\",\\\"$C$\\\",\\\"$D$\\\"], \\\"correct_index\\\":0, \\\"explanation\\\":\\\"...\\\", \\\"year\\\":\\\"...\\\"}"
    
    # Call AI
    raw = ai_client._orig_ask_raw(exam, prompt, system_override="You are a direct retrieval API. Output ONLY valid JSON. Do not include markdown formatting like ```json. Start directly with { and end with }.")
    
    if not raw:
        safe_send(uid, f"❌ AI connection failed for {year}.")
        state["year"] -= 1
        state["q_num"] += 1
        fetch_and_send_pyq(uid)
        return
        
    # Parse JSON
    import re
    try:
        txt = raw.strip()
        if txt.startswith("```"): txt = re.sub(r"^```(?:json)?\\s*", "", txt); txt = re.sub(r"\\s*```\\s*$", "", txt)
        first = txt.find("{"); last = txt.rfind("}")
        data = json.loads(txt[first:last+1])
    except Exception as e:
        safe_send(uid, f"❌ AI returned invalid JSON: {e}\\n\\nRaw: {raw[:100]}")
        state["year"] -= 1
        state["q_num"] += 1
        fetch_and_send_pyq(uid)
        return

    # Send the question
    body = f"📝 *Question {state['q_num']}/{state['max_q']}* (JEE Adv {data.get('year', year)})\n\n"
    body += f"{data.get('question')}\n\n"
    
    options = data.get("options", [])
    kb = InlineKeyboardMarkup(row_width=4)
    btns = []
    for i, opt in enumerate(options[:4]):
        letter = chr(65+i)
        btns.append(InlineKeyboardButton(letter, callback_data=f"pyq_ans:{i}"))
        body += f"*{letter})* {opt}\n"
    kb.add(*btns)
    
    safe_send(uid, body, parse_mode="Markdown", reply_markup=kb)
    
    # Increment for next time
    state["year"] -= 1
    state["q_num"] += 1

@bot.callback_query_handler(func=lambda call: call.data.startswith("pyq_ans:"))
def handle_pyq_ans(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id, "Answer recorded.")
    try: bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except: pass
    fetch_and_send_pyq(uid)

def safe_send(uid, text, **kwargs):
    try: return bot.send_message(uid, text, **kwargs)
    except Exception as e: print(e)

if __name__ == "__main__":
    print("🤖 FORCED PYQ Test Bot running...")
    bot.infinity_polling()
