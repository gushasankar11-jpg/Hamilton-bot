import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# Find the start and end of the old clean_math function safely
start_marker = "def clean_math(text):"
if start_marker in content:
    start_idx = content.find(start_marker)
    end_idx = content.find("return text", start_idx)
    if end_idx != -1:
        end_idx += len("return text")
        
        new_clean = '''def clean_math(text):
    if not text: return ""
    text = text.replace("$$", "").replace("$", "")
    text = re.sub(r'\\\\boxed\\{(.*?)\\}', r'\\1', text)
    text = re.sub(r'\\\\frac\\{(.*?)\\}\\{(.*?)\\}', r'(\\1)/(\\2)', text)
    text = re.sub(r'\\\\sqrt\\{(.*?)\\}', r'√(\\1)', text)
    symbols = {
        '\\\\alpha': 'α', '\\\\beta': 'β', '\\\\theta': 'θ', '\\\\pi': 'π',
        '\\\\times': '×', '\\\\cdot': '·', '\\\\pm': '±', '\\\\infty': '∞',
        '\\\\le': '≤', '\\\\ge': '≥', '\\\\ne': '≠', '\\\\to': '→',
        '\\\\vec': '', '\\\\hat': ''
    }
    for k, v in symbols.items():
        text = text.replace(k, v)
    supers = {'0':'⁰', '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵', '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹', 'n':'ⁿ'}
    def rep_super(m):
        return ''.join(supers.get(c, c) for c in m.group(1))
    text = re.sub(r'\\^\\{?(\\d+|n)\\}?', rep_super, text)
    subs = {'0':'₀', '1':'₁', '2':'₂', '3':'₃', '4':'₄', '5':'₅', '6':'₆', '7':'₇', '8':'₈', '9':'₉', 'n':'ₙ'}
    def rep_sub(m):
        return ''.join(subs.get(c, c) for c in m.group(1))
    text = re.sub(r'\\_\\{?(\\d+|n)\\}?', rep_sub, text)
    text = re.sub(r'\\\\([a-zA-Z]+)', r'\\1', text)
    text = re.sub(r'\\*\\*(.*?)\\*\\*', r'<b>\\1</b>', text)
    text = re.sub(r'\\*(.*?)\\*', r'<i>\\1</i>', text)
    return text'''
        
        content = content[:start_idx] + new_clean + content[end_idx:]
        open(path, "w").write(content)
        print("✅ clean_math successfully replaced without regex errors.")
    else:
        print("⚠️ Could not find end of clean_math.")
else:
    print("⚠️ clean_math not found.")

# 2. Add Greeting Interceptor to c09.py
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
    open(path_c09, "w").write(c09_content)
    print("✅ c09.py: Greeting interceptor added.")
