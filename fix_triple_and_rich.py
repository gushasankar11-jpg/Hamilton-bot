import ast, re

# --- 1. CLEAN c04_exam.py ---
path = "bot_chunks/c04_exam.py"
content = open(path).read()

# Remove ALL handle_buttons to stop triple firing
pattern = re.compile(r'@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("f_"\)\)\s*\ndef handle_buttons\(call\):.*?(?=\n@bot\.|\ndef |\nclass |\Z)', re.DOTALL)
content = pattern.sub('', content)

# Find the f_solution logic and force clean_math + HTML
master_handler = '''
@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    state = _state.get(uid, {})

    if data == "f_solution":
        load = _b().send_message(uid, "🧠 <i>Generating solution...</i>")
        try:
            q_text = state.get("q", {}).get("q_text", "")
            sol = get_ai_solution(q_text, uid)
            
            # FORCE CLEAN_MATH
            clean_sol = clean_math(sol)
            # Telegram 4096 char limit
            if len(clean_sol) > 4000:
                clean_sol = clean_sol[:4000] + "\\n\\n<i>(Truncated)</i>"
                
            _b().edit_message_text(clean_sol, chat_id=uid, message_id=load.message_id, parse_mode="HTML")
        except Exception as e:
            _b().edit_message_text(f"❌ Error: {e}", chat_id=uid, message_id=load.message_id)
        return
    # Add the rest of your f_ handlers here if they were deleted, 
    # BUT to avoid breaking, we just call the old logic if it exists.
'''

# Instead of rewriting ALL handlers, just inject the solution handler at the top of the file
# and let the existing handle_buttons catch it. Wait, that causes duplicates.
# Let's just fix the existing handle_buttons.

# Find the first f_solution handler and replace it
sol_idx = content.find('if data == "f_solution":')
if sol_idx != -1:
    sol_end = content.find('if data == "', sol_idx + 20)
    if sol_end == -1: sol_end = content.find('elif data == "', sol_idx + 20)
    
    new_sol = '''if data == "f_solution":
            load = _b().send_message(uid, "🧠 <i>Generating solution...</i>")
            try:
                q_text = state.get("q", {}).get("q_text", "")
                sol = get_ai_solution(q_text, uid)
                clean_sol = clean_math(sol)
                if len(clean_sol) > 4000:
                    clean_sol = clean_sol[:4000] + "..."
                _b().edit_message_text(clean_sol, chat_id=uid, message_id=load.message_id, parse_mode="HTML")
            except Exception as e:
                _b().edit_message_text(f"❌ Error: {e}", chat_id=uid, message_id=load.message_id)
            return
            
        '''
    content = content[:sol_idx] + new_sol + content[sol_end:]
    print("✅ Fixed f_solution to use clean_math and HTML.")

# Ensure clean_math is defined at the top
if "def clean_math(text):" not in content:
    new_clean = '''def clean_math(text):
    if not text: return ""
    text = text.replace("$$", "").replace("$", "")
    text = re.sub(r'\\\\boxed\\{(.*?)\\}', r'\\1', text)
    text = re.sub(r'\\\\frac\\{(.*?)\\}\\{(.*?)\\}', r'(\\1)/(\\2)', text)
    text = re.sub(r'\\\\sqrt\\{(.*?)\\}', r'√(\\1)', text)
    text = text.replace("\\\\alpha", "α").replace("\\\\beta", "β").replace("\\\\pi", "π")
    text = text.replace("\\\\times", "×").replace("\\\\cdot", "·").replace("\\\\pm", "±")
    text = text.replace("\\\\le", "≤").replace("\\\\ge", "≥").replace("\\\\ne", "≠")
    # Superscripts
    for n, s in [('0','⁰'),('1','¹'),('2','²'),('3','³'),('4','⁴'),('5','⁵'),('6','⁶'),('7','⁷'),('8','⁸'),('9','⁹')]:
        text = text.replace(f"^{{{n}}}", s).replace(f"^{n}", s)
    # Subscripts
    for n, s in [('0','₀'),('1','₁'),('2','₂'),('3','₃'),('4','₄'),('5','₅'),('6','₆'),('7','₇'),('8','₈'),('9','₉')]:
        text = text.replace(f"_{{{n}}}", s).replace(f"_{n}", s)
        
    text = re.sub(r'\\\\([a-zA-Z]+)', r'\\1', text)
    text = re.sub(r'\\*\\*(.*?)\\*\\*', r'<b>\\1</b>', text)
    text = re.sub(r'\\*(.*?)\\*', r'<i>\\1</i>', text)
    return text

'''
    content = new_clean + content
    print("✅ Re-injected clean_math.")

# Fix triple-triggering by ensuring only ONE @bot.callback_query_handler exists for f_
if content.count('@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))') > 1:
    print("⚠️ Multiple f_ handlers found. Cleaning...")
    # (The regex at the top already removed them, so this is just a safety check)

open(path, "w").write(content)

# --- 2. FIX AI PROMPT ---
path_ai = "bot_chunks/c40_vision_ai.py"
ai_content = open(path_ai).read()
# Tell the AI to use Unicode directly instead of LaTeX
ai_content = ai_content.replace('Use EXACTLY this 5-part format:', 'Use EXACTLY this 5-part format. DO NOT use LaTeX formatting like $ or \\boxed. Use Unicode (e.g. y² = 4ax) instead:')
open(path_ai, "w").write(ai_content)
print("✅ AI prompt updated to prefer Unicode.")
