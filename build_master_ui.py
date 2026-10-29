import ast, os

# ==========================================
# 1. FIX THE CROPPER (Stop at ExamGOAL Footer)
# ==========================================
crop_script = """import subprocess, re, os, json
from PIL import Image

def process_pdf_page(pdf, page_num, out_dir, start_q=17, end_q=19):
    os.makedirs(out_dir, exist_ok=True)
    img_base = os.path.join(out_dir, f"page{page_num}")
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page_num), "-l", str(page_num), "-singlefile", pdf, img_base], check=True)
    img_path = img_base + ".png"
    img = Image.open(img_path)
    img_w, img_h = img.size

    xml_out = subprocess.run(["pdftotext", "-bbox", "-f", str(page_num), "-l", str(page_num), pdf, "-"], capture_output=True, text=True).stdout
    matches = re.findall(r'<word xMin="[\\d\\.]+" yMin="([\\d\\.]+)"[^>]*>Q(\\d+)\\.</word>', xml_out)
    
    # Find the footer Y-coord to stop cropping
    footer_match = re.search(r'<word xMin="[\\d\\.]+" yMin="([\\d\\.]+)"[^>]*>Keep</word>', xml_out)
    footer_y = float(footer_match.group(1)) if footer_match else img_h

    scale = 150.0 / 72.0 
    
    for i, (y_str, q_num) in enumerate(matches):
        q_num = int(q_num)
        if q_num < start_q or q_num > end_q: continue
        
        y_min = float(y_str) * scale
        if i + 1 < len(matches):
            y_max = float(matches[i+1][0]) * scale - 15
        else:
            y_max = footer_y * scale - 15 # Cut before the footer
            
        crop_top = max(0, y_min - 15)
        crop_bottom = min(img_h, y_max)
        
        cropped = img.crop((0, int(crop_top), img_w, int(crop_bottom)))
        cropped.save(os.path.join(out_dir, f"q{q_num}.png"))
        print(f"✂️ Cropped Q{q_num}")

if __name__ == "__main__":
    pdf = "pyq_pdfs/jee_main/practice/Physics/JEE Main Heat and Thermodynamics Previous Year Questions with Answer Key.pdf"
    process_pdf_page(pdf, 6, "pyq_images/test_crop")
"""
with open("process_pdfs.py", "w") as f: f.write(crop_script)
print("✅ Cropper fixed (stops at footer)")


# ==========================================
# 2. THE MASTER NAVIGATION UI (c04d_exam_ui.py)
# ==========================================
ui_code = '''import telebot
import json
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Reuse bot
def _b():
    try: return _b()
    except: return bot

# 9-Type Engine Mapping & 6/10 Rule Placeholder
def get_next_question(session, current_q):
    # Here is where the 6/10 rule lives. 
    # 60% chance of PYQ, 40% chance of AI/Difficulty Mix.
    # For now, we just serve the next sequential PYQ from our cropped images.
    return current_q + 1

@bot.message_handler(commands=['nav_test'])
def start_nav_test(message):
    uid = message.chat.id
    # Init session state
    try: _state[uid] = {}
    except: pass
    
    _state[uid].update({
        "exam_active": True,
        "current_q": 17,
        "visited": [17],
        "attempted": {}, # q_num: "A", "B", etc.
        "answers": json.load(open("data/temp_answers.json")) if os.path.exists("data/temp_answers.json") else {}
    })
    
    send_nav_question(uid, 17)

def send_nav_question(uid, q_num):
    st = _state.get(uid, {})
    st["current_q"] = q_num
    if q_num not in st["visited"]: st["visited"].append(q_num)
    
    # Metadata (Hardcoded for test, to be fetched from DB later)
    meta = {"time": 90, "diff": "Medium (6/10)", "year": "2026 Jan Shift 1"}
    if q_num == 18: meta = {"time": 120, "diff": "Hard (8/10)", "year": "2026 Jan Shift 1"}
    if q_num == 19: meta = {"time": 75, "diff": "Easy (4/10)", "year": "2026 Jan Shift 1"}
    
    caption = f"📝 <b>Question {q_num}</b> | {meta['year']}\\n⏱ Ideal Time: {meta['time']}s | 📊 Difficulty: {meta['diff']}"
    
    # Build Keyboard
    kb = InlineKeyboardMarkup(row_width=4)
    
    # 9-Type Options (A, B, C, D for standard MCQ)
    opts = ["A", "B", "C", "D"]
    kb.add(*[InlineKeyboardButton(opt, callback_data=f"nav_ans:{q_num}:{opt}") for opt in opts])
    
    # Submit Button
    kb.add(InlineKeyboardButton("🚀 Submit Answer", callback_data=f"nav_submit:{q_num}"))
    
    # Navigation Bar (Green/White/Black)
    nav_row = []
    for i in [17, 18, 19]:
        if i == q_num: emoji = "⚪" # Current
        elif i in st.get("attempted", {}): emoji = "🟢" # Attempted
        elif i in st.get("visited", []): emoji = "⚫" # Visited/Skipped
        else: emoji = "▫️" # Not visited
        nav_row.append(InlineKeyboardButton(emoji, callback_data=f"nav_jump:{i}"))
    kb.add(*nav_row)
    
    # Send or Edit
    if "msg_id" in st:
        try:
            _b().delete_message(uid, st["msg_id"])
            _b().delete_message(uid, st["timer_id"])
        except: pass
    
    img_path = f"pyq_images/test_crop/q{q_num}.png"
    try:
        with open(img_path, "rb") as f:
            msg = _b().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
            st["msg_id"] = msg.message_id
    except Exception as e:
        _b().send_message(uid, f"❌ Missing {img_path}")
        return

@bot.callback_query_handler(func=lambda call: call.data.startswith("nav_ans:"))
def nav_answer(call):
    uid = call.message.chat.id
    _, q_num, opt = call.data.split(":")
    q_num = int(q_num)
    
    _state[uid]["temp_ans"] = opt
    _b().answer_callback_query(call.id, f"Selected {opt}. Click Submit.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("nav_submit:"))
def nav_submit(call):
    uid = call.message.chat.id
    q_num = int(call.data.split(":")[1])
    st = _state.get(uid, {})
    
    user_opt = st.get("temp_ans")
    if not user_opt:
        _b().answer_callback_query(call.id, "⚠️ Please select an option first!", show_alert=True)
        return
        
    st["attempted"][q_num] = user_opt
    correct_opt = st.get("answers", {}).get(str(q_num), "Unknown")
    
    if user_opt == correct_opt:
        _b().answer_callback_query(call.id, "✅ Correct!")
        _b().send_message(uid, f"✅ <b>Correct!</b> You chose {user_opt}.")
    else:
        _b().answer_callback_query(call.id, "❌ Wrong!")
        _b().send_message(uid, f"❌ <b>Wrong.</b> You chose {user_opt}. Correct is {correct_opt}.")
        
    # Send the 5-Part Ultimate Solution Prompt here (Placeholder)
    _b().send_message(uid, "💡 <i>[Ultimate Solution Engine (Process, Shortcut, Generalization, Formula) goes here]</i>", parse_mode="HTML")
    
    # Move to Next Question
    if q_num < 19:
        time.sleep(1.5)
        send_nav_question(uid, q_num + 1)
    else:
        _b().send_message(uid, "🏁 <b>Exam Complete!</b> You finished the test.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("nav_jump:"))
def nav_jump(call):
    uid = call.message.chat.id
    q_num = int(call.data.split(":")[1])
    _b().answer_callback_query(call.id, f"Jumping to Q{q_num}...")
    send_nav_question(uid, q_num)

print("✅ c04d_exam_ui: Master Navigation Bar loaded.")
'''

with open("bot_chunks/c04d_exam_ui.py", "w") as f:
    f.write(ui_code)
    
try:
    ast.parse(ui_code)
    print("✅ c04d_exam_ui.py syntax OK")
except SyntaxError as e:
    print(f"❌ UI Syntax Error: {e}")

