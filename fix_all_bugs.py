import ast, re, os

# ==========================================
# PATCH 1: Fix Text Formatting (c04_exam.py)
# ==========================================
path_exam = "bot_chunks/c04_exam.py"
content_exam = open(path_exam).read()

# Safely inject replacements into clean_math
if "def clean_math(text):" in content_exam and "text.replace('#', '')" not in content_exam:
    content_exam = content_exam.replace(
        "def clean_math(text):",
        "def clean_math(text):\n    if not text: return \"\"\n    text = text.replace('#', '').replace('*', '')"
    )
    try:
        ast.parse(content_exam)
        open(path_exam, "w").write(content_exam)
        print("✅ PATCH 1: clean_math formatting fixed (# and * stripped)")
    except SyntaxError as e:
        print(f"❌ PATCH 1 FAILED: {e}")
else:
    print("⏭️ PATCH 1: Already applied or clean_math not found.")

# ==========================================
# PATCH 2: Profanity Filter (c09.py)
# ==========================================
path_c09 = "bot_chunks/c09.py"
content_c09 = open(path_c09).read()

if "def free_text_handler(message):" in content_c09 and "Profanity detected" not in content_c09:
    # We inject the filter right at the start of the function
    filter_code = """
def free_text_handler(message):
    uid = message.chat.id
    import json, time, os, re
    try:
        BAD_WORDS = ['fuck', 'shit', 'bitch', 'asshole', 'dick', 'bastard', 'slut', 'whore']
        txt = (message.text or '').lower()
        if any(re.search(r'\\b' + w + r'\\b', txt) for w in BAD_WORDS):
            bf = 'data/blocked_users.json'
            blocks = {}
            if os.path.exists(bf):
                try: blocks = json.load(open(bf))
                except: pass
            blocks[str(uid)] = time.time() + 86400  # 24 hours
            json.dump(blocks, open(bf, 'w'))
            safe_send(uid, "🚫 Profanity detected. You are blocked for 24 hours.")
            return
    except Exception as e:
        print(f"Profanity filter error: {e}")
"""
    content_c09 = content_c09.replace("def free_text_handler(message):\n    uid = message.chat.id", filter_code)
    try:
        ast.parse(content_c09)
        open(path_c09, "w").write(content_c09)
        print("✅ PATCH 2: Profanity filter added (24h block)")
    except SyntaxError as e:
        print(f"❌ PATCH 2 FAILED: {e}")
else:
    print("⏭️ PATCH 2: Already applied or free_text_handler not found.")

# ==========================================
# PATCH 3: Fix Prediction Bug (c21.py)
# ==========================================
path_c21 = "bot_chunks/c21.py"
if os.path.exists(path_c21):
    content_c21 = open(path_c21).read()
    if "out of 90" in content_c21:
        content_c21 = content_c21.replace("out of 90", "out of 300")
        try:
            ast.parse(content_c21)
            open(path_c21, "w").write(content_c21)
            print("✅ PATCH 3: Fixed prediction bug (90 -> 300 marks)")
        except SyntaxError as e:
            print(f"❌ PATCH 3 FAILED: {e}")
    else:
        print("⏭️ PATCH 3: 'out of 90' not found. It might be handled by AI prompt or already fixed.")
else:
    print("❌ PATCH 3: c21.py not found.")

