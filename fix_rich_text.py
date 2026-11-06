import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Replace clean_math completely with a powerful LaTeX-to-Unicode converter
old_clean = '''def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    return text'''

new_clean = '''def clean_math(text):
    if not text: return ""
    # Remove math delimiters
    text = text.replace("$$", "").replace("$", "")
    # Handle boxed
    text = re.sub(r'\\\\boxed\\{(.*?)\\}', r'\\1', text)
    # Handle fractions
    text = re.sub(r'\\\\frac\\{(.*?)\\}\\{(.*?)\\}', r'(\\1)/(\\2)', text)
    # Handle square roots
    text = re.sub(r'\\\\sqrt\\{(.*?)\\}', r'√(\\1)', text)
    # Greek letters and symbols
    symbols = {
        '\\\\alpha': 'α', '\\\\beta': 'β', '\\\\theta': 'θ', '\\\\pi': 'π',
        '\\\\times': '×', '\\\\cdot': '·', '\\\\pm': '±', '\\\\infty': '∞',
        '\\\\le': '≤', '\\\\ge': '≥', '\\\\ne': '≠', '\\\\to': '→',
        '\\\\vec': '', '\\\\hat': ''
    }
    for k, v in symbols.items():
        text = text.replace(k, v)
        
    # Superscripts (basic)
    supers = {'0':'⁰', '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵', '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹', 'n':'ⁿ'}
    def rep_super(m):
        return ''.join(supers.get(c, c) for c in m.group(1))
    text = re.sub(r'\\^\\{?(\\d+|n)\\}?', rep_super, text)
    
    # Subscripts (basic)
    subs = {'0':'₀', '1':'₁', '2':'₂', '3':'₃', '4':'₄', '5':'₅', '6':'₆', '7':'₇', '8':'₈', '9':'₉', 'n':'ₙ'}
    def rep_sub(m):
        return ''.join(subs.get(c, c) for c in m.group(1))
    text = re.sub(r'\\_\\{?(\\d+|n)\\}?', rep_sub, text)
    
    # Remove remaining backslashes
    text = re.sub(r'\\\\([a-zA-Z]+)', r'\\1', text)
    
    # Convert markdown bold/italic to HTML tags
    text = re.sub(r'\\*\\*(.*?)\\*\\*', r'<b>\\1</b>', text)
    text = re.sub(r'\\*(.*?)\\*', r'<i>\\1</i>', text)
    
    return text'''

if old_clean in content:
    content = content.replace(old_clean, new_clean)
    print("✅ clean_math upgraded for beautiful Unicode output.")
else:
    # Try regex if exact match fails
    content = re.sub(r'def clean_math\(text\):.*?return text', new_clean, content, flags=re.DOTALL)
    print("✅ clean_math upgraded (via regex fallback).")

# 2. Update the solution sender to use HTML and clean_math
old_sol = '''            _b().edit_message_text(sol, chat_id=uid, message_id=load.message_id, parse_mode="Markdown")'''
new_sol = '''            import re as _re
            clean_sol = clean_math(sol)
            # Ensure it doesn't exceed Telegram's 4096 char limit
            if len(clean_sol) > 4000:
                clean_sol = clean_sol[:4000] + "..."
            _b().edit_message_text(clean_sol, chat_id=uid, message_id=load.message_id, parse_mode="HTML")'''

if old_sol in content:
    content = content.replace(old_sol, new_sol)
    print("✅ AI Solution sender updated to HTML + clean_math.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")

# ==========================================
# 3. FIX GREETINGS IN c09.py
# ==========================================
path_c09 = "bot_chunks/c09.py"
c09_content = open(path_c09).read()

greeting_code = '''def free_text_handler(message):
    uid = message.chat.id
    txt = (message.text or "").strip().lower()
    
    # --- GREETING INTERCEPTOR ---
    if txt in ["hi", "hello", "hey", "hii", "hey hamilton", "hello hamilton", "hi hamilton"]:
        safe_send(uid, "👋 Hello! I am Hamilton.\\nType /exam to practice questions or send me an image of a doubt to solve.")
        return
    # ----------------------------'''

if "def free_text_handler(message):\n    uid = message.chat.id" in c09_content:
    c09_content = c09_content.replace("def free_text_handler(message):\n    uid = message.chat.id", greeting_code)
    try:
        ast.parse(c09_content)
        open(path_c09, "w").write(c09_content)
        print("✅ c09.py: Greeting interceptor added.")
    except SyntaxError as e:
        print(f"❌ c09 Syntax Error: {e}")
else:
    print("⚠️ Could not find free_text_handler start in c09.py.")
