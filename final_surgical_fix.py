import ast, os, re

# 1. Fix c09.py to strictly ignore ALL commands
path_c09 = "bot_chunks/c09.py"
if os.path.exists(path_c09):
    content = open(path_c09).read()
    old_func = "func=lambda m: not _in_subreg_flow(m.chat.id),"
    new_func = "func=lambda m: not _in_subreg_flow(m.chat.id) and m.text and not m.text.startswith('/'),"
    if old_func in content:
        content = content.replace(old_func, new_func)
        open(path_c09, "w").write(content)
        print("✅ c09.py: Interceptor now strictly ignores commands.")

# 2. Disable the broken auto-cleanup script
path_cleanup = "bot_chunks/c30s_admin_cleanup.py"
if os.path.exists(path_cleanup):
    content = open(path_cleanup).read()
    # Find the thread start and comment it out
    if "autoclose thread started" in content:
        # Just comment out all delete_message calls to prevent crashes
        content = content.replace("bot.delete_message", "# bot.delete_message")
        open(path_cleanup, "w").write(content)
        print("✅ c30s: Disabled broken auto-delete (Exam buttons will not vanish).")

# 3. Ensure c04_exam.py has only ONE handle_buttons function
path_exam = "bot_chunks/c04_exam.py"
if os.path.exists(path_exam):
    content = open(path_exam).read()
    parts = content.split("@bot.callback_query_handler(func=lambda c: c.data.startswith(\"f_\"))")
    if len(parts) > 2:
        print(f"🚨 Found {len(parts)-1} duplicate exam handlers! Cleaning...")
        # Keep imports and the first handler, discard the rest
        content = parts[0] + "@bot.callback_query_handler(func=lambda c: c.data.startswith(\"f_\"))" + parts[1]
        open(path_exam, "w").write(content)
        print("✅ c04_exam.py: Removed duplicates.")
    else:
        print("✅ c04_exam.py: No duplicates found.")

# 4. Fix the Paper Extractor prompt to be extremely strict
path_extract = "extract_papers_ai.py"
if os.path.exists(path_extract):
    content = open(path_extract).read()
    old_prompt = '''prompt = f"""
    Analyze this JEE paper page. Extract exactly the questions on this page.
    Return ONLY JSON: {{"questions": [{{"q_num": 1, "type": "mcq", "box": [ymin, xmin, ymax, xmax]}}]}}
    Max {expected_qs} questions.
    """'''
    new_prompt = '''prompt = f"""
    Analyze this JEE paper page. Extract exactly the questions on this page.
    DO NOT extract the Answer Key or Instructions.
    Return ONLY JSON: {{"questions": [{{"q_num": 1, "type": "mcq", "box": [ymin, xmin, ymax, xmax]}}]}}
    Max {expected_qs} questions.
    """'''
    if old_prompt in content:
        content = content.replace(old_prompt, new_prompt)
        open(path_extract, "w").write(content)
        print("✅ Extractor prompt is now strict.")

print("🎉 All fixes applied.")
