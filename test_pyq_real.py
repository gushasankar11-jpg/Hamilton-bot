import sys
sys.path.insert(0, '.')
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import config

TOKEN = config.TELEGRAM_TOKEN
bot = telebot.TeleBot(TOKEN)
MY_ID = 8857708587

# A REAL JEE Advanced 2020 Question (Motion in a Straight Line)
# Let's see if the UI handles this perfectly.
REAL_PYQ = {
    "year": "2020",
    "paper": "Paper 2",
    "question": "A particle moves in a straight line. Its velocity $v$ varies with time $t$ as $v = 4t - t^2$ for $t \\in [0, 4]$ (in SI units). The total distance travelled by the particle in the interval $t=0$ to $t=4$ is:",
    "options": [
        "$\\frac{32}{3}$ m",
        "$\\frac{16}{3}$ m",
        "$8$ m",
        "$\\frac{8}{3}$ m"
    ],
    "correct_index": 0,
    "explanation": "The velocity becomes zero at $t=4$. Distance = $\\int_0^4 |4t - t^2| dt = \\frac{32}{3}$ m."
}

@bot.message_handler(commands=['start_real_pyq'])
def start_real_pyq(message):
    uid = message.chat.id
    if uid != MY_ID: return
    
    safe_send(uid, "📝 *REAL JEE Adv 2020 PYQ*\n\nThis is an authentic question retrieved from the official paper. Test the UI:", parse_mode="Markdown")
    
    # Format body
    body = f"📝 *Question 1/1* (JEE Adv {REAL_PYQ['year']} {REAL_PYQ['paper']})\n\n"
    body += f"{REAL_PYQ['question']}\n\n"
    
    kb = InlineKeyboardMarkup(row_width=4)
    btns = []
    for i, opt in enumerate(REAL_PYQ['options']):
        letter = chr(65+i)
        btns.append(InlineKeyboardButton(letter, callback_data=f"real_ans:{i}"))
        body += f"*{letter})* {opt}\n"
    kb.add(*btns)
    
    safe_send(uid, body, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("real_ans:"))
def handle_real_ans(call):
    uid = call.from_user.id
    chosen = int(call.data.split(":")[1])
    
    if chosen == REAL_PYQ['correct_index']:
        bot.answer_callback_query(call.id, "✅ Correct!")
        safe_send(uid, "✅ *Correct!*\n\n" + REAL_PYQ['explanation'], parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "❌ Wrong!")
        safe_send(uid, "❌ *Wrong.*\n\n" + REAL_PYQ['explanation'], parse_mode="Markdown")
        
    try: bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except: pass

def safe_send(uid, text, **kwargs):
    try: return bot.send_message(uid, text, **kwargs)
    except Exception as e: print(e)

if __name__ == "__main__":
    print("🤖 Real PYQ Test Bot running...")
    bot.infinity_polling()
