import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# Find the keyboard builder inside send_pyq_q
old_kb = '''    # --- BUILD UI BASED ON TYPE ---
    kb = InlineKeyboardMarkup(row_width=4)
    
    if qtype in ["SINGLE", "MCQ"]:
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        
    elif qtype == "MULTIPLE" or qtype == "MULTI-CORRECT":'''

new_kb = '''    # --- BUILD UI BASED ON TYPE ---
    kb = InlineKeyboardMarkup(row_width=4)
    
    if qtype in ["SINGLE", "MCQ", "MULTIPLE-CHOICE"]:
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        
    elif qtype in ["NUMERICAL", "INTEGER"]:
        state["waiting_for_pyq_numeric"] = True
        cap += "\\n<i>Type your numerical answer below:</i>"
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        
    elif qtype == "MATRIX":
        kb.row(*[InlineKeyboardButton(f"Col1-{chr(65+i)}", callback_data=f"f_match1:{i}") for i in range(4)])
        kb.row(*[InlineKeyboardButton(f"Col2-{chr(80+i)}", callback_data=f"f_match2:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Submit Match", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"))
        
    elif qtype == "MULTIPLE" or qtype == "MULTI-CORRECT":'''

if old_kb in content:
    content = content.replace(old_kb, new_kb)
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ Patched UI: Now recognizes Numerical, Integer, and Matrix types from the paper extractor.")
    except SyntaxError as e:
        print(f"❌ Syntax Error: {e}")
else:
    print("⚠️ Could not find keyboard builder block.")
