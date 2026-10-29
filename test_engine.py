import sys
sys.path.insert(0, '.')
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import telebot
import exam_engine
import config

# 1. Initialize Bot
TOKEN = config.TELEGRAM_TOKEN
bot = telebot.TeleBot(TOKEN)
MY_ID = 8857708587

# 2. State Tracker for the test
TEST_STATE = {}

# 3. The Test Command
@bot.message_handler(commands=['start_test'])
def start_isolated_test(message):
    uid = message.chat.id
    TEST_STATE[uid] = {"score": 0, "attempted": 0, "q_num": 1, "max_q": 3, "current_answer": None, "q_text": ""}
    
    # Force JEE Adv Physics Chapter
    exam = "JEE_ADV"
    subj = "Physics"
    ch = "Dimensions and Measurement"
    sub = "Physical Quantity"
    
    safe_send(uid, "🚀 *Isolated Test Started!* (3 Questions)", parse_mode="Markdown")
    
    # Generate Q1
    generate_and_send_q(uid, exam, subj, ch, sub)

def generate_and_send_q(uid, exam, subj, ch, sub):
    state = TEST_STATE.get(uid)
    if not state: return
    
    if state["q_num"] > state["max_q"]:
        end_test(uid)
        return
        
    safe_send(uid, f"⏳ Generating Q{state['q_num']}...", parse_mode="Markdown")
    
    # CALL THE AI ENGINE
    q = exam_engine.generate_question(exam, subj, ch, sub, q_type="mcq", difficulty="easy")
    
    if not q:
        safe_send(uid, "❌ AI failed to generate. Check logs.")
        return
        
    state["current_answer"] = q.get("correct_index")
    state["q_text"] = q.get("question")
    
    # Build the UI
    options = q.get("options", [])
    kb = InlineKeyboardMarkup(row_width=4)
    btns = []
    for i, opt in enumerate(options[:4]):
        letter = chr(65+i)
        btns.append(InlineKeyboardButton(letter, callback_data=f"ans:{i}"))
    kb.add(*btns)
    
    # Format Text
    body = f"📝 *Question {state['q_num']}/{state['max_q']}*\n\n{q.get('question')}\n\n"
    for i, opt in enumerate(options[:4]):
        body += f"*{chr(65+i)})* {opt}\n"
        
    safe_send(uid, body, parse_mode="Markdown", reply_markup=kb)

# 4. Handle Answer Clicks
@bot.callback_query_handler(func=lambda call: call.data.startswith("ans:"))
def handle_answer(call):
    uid = call.from_user.id
    state = TEST_STATE.get(uid)
    if not state: return
    
    chosen_idx = int(call.data.split(":")[1])
    correct_idx = state["current_answer"]
    
    if chosen_idx == correct_idx:
        state["score"] += 1
        bot.answer_callback_query(call.id, "✅ Correct!")
    else:
        bot.answer_callback_query(call.id, "❌ Wrong!")
        
    state["attempted"] += 1
    state["q_num"] += 1
    
    # Edit the message to show the chosen answer
    try:
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except: pass
    
    # Send next question
    generate_and_send_q(uid, "JEE_ADV", "Physics", "Dimensions and Measurement", "Physical Quantity")

@bot.message_handler(commands=['end_test'])
def end_test(message_or_uid):
    if hasattr(message_or_uid, 'chat'):
        uid = message_or_uid.chat.id
    else:
        uid = message_or_uid
        
    state = TEST_STATE.get(uid)
    if not state:
        safe_send(uid, "No active test.")
        return
        
    score = state["score"]
    attempted = state["attempted"]
    pct = (score / attempted * 100) if attempted > 0 else 0
    
    report = f"🏁 *TEST COMPLETE*\\n\\n"
    report += f"Attempted: {attempted}\\n"
    report += f"Score: {score}/{attempted}\\n"
    report += f"Percentage: {pct:.1f}%\\n"
    
    safe_send(uid, report, parse_mode="Markdown")
    TEST_STATE.pop(uid, None)

def safe_send(uid, text, **kwargs):
    try:
        return bot.send_message(uid, text, **kwargs)
    except Exception as e:
        print(f"[send-err] {e}")

if __name__ == "__main__":
    print("🤖 Isolated Test Bot running...")
    print("Go to Telegram and send /start_test")
    bot.infinity_polling()
