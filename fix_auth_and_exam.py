import ast, os, re

# ==========================================
# 1. FIX _auth_text_router (Ignore Commands)
# ==========================================
path_auth = "bot_chunks/c30a_admin_auth.py"
if os.path.exists(path_auth):
    content = open(path_auth).read()
    start_idx = content.find("def _auth_text_router(message):")
    
    if start_idx != -1:
        # Find the first line inside the function
        next_line_idx = content.find("\n", start_idx) + 1
        # Inject a command check
        injection = '''    if message.text and message.text.startswith("/"):
        return # Ignore commands, let other handlers process them
'''
        content = content[:next_line_idx] + injection + content[next_line_idx:]
        try:
            ast.parse(content)
            open(path_auth, "w").write(content)
            print("✅ Patched _auth_text_router to ignore commands.")
        except SyntaxError as e:
            print(f"❌ Syntax error in auth patch: {e}")


# ==========================================
# 2. FIX EXAM CENTER (Remove duplicate handlers)
# ==========================================
path_exam = "bot_chunks/c04_exam.py"
if os.path.exists(path_exam):
    content = open(path_exam).read()
    # Find all occurrences of the callback handler
    occurrences = [m.start() for m in re.finditer(r'@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("f_"\)\)\s*\ndef handle_buttons\(call\):', content)]
    
    if len(occurrences) > 1:
        print(f"🚨 Found {len(occurrences)} duplicate handle_buttons functions! Removing extras...")
        # Keep the first one, delete the rest (from @bot down to the next @bot or def)
        for i in range(len(occurrences) - 1, 0, -1):
            start = occurrences[i]
            # Find the next @bot or top-level def
            end_match = re.search(r'\n@bot\.|\ndef |\nclass ', content[start+50:])
            end = start + 50 + end_match.start() if end_match else len(content)
            content = content[:start] + content[end:]
            
        try:
            ast.parse(content)
            open(path_exam, "w").write(content)
            print("✅ Deduplicated handle_buttons in c04_exam.py.")
        except SyntaxError as e:
            print(f"❌ Syntax error in exam deduplication: {e}")
    else:
        print("✅ No duplicate handlers found in c04_exam.py.")

