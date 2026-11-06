import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Replace the exact PYQ menu block
old_menu = '''            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )
                kb.add(InlineKeyboardButton("🚧 JEE Adv (Coming Soon)", callback_data="f_soon"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return'''

new_menu = '''            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(InlineKeyboardButton("📖 JEE Main Chapter-wise", callback_data="f_pyq:practice"))
                kb.add(InlineKeyboardButton("🔥 JEE Adv Chapter-wise", callback_data="f_pyq_adv:practice"))
                kb.add(InlineKeyboardButton("📝 JEE Main Papers", callback_data="f_pyq_papers_cat:JEE MAIN"))
                kb.add(InlineKeyboardButton("🔥 JEE Adv Papers", callback_data="f_pyq_papers_cat:JEE ADV"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return'''

if old_menu in content:
    content = content.replace(old_menu, new_menu)
    print("✅ Main PYQ Menu replaced perfectly.")
else:
    print("⚠️ Menu not found. Trying line-by-line...")
    # Fallback to line-by-line replacement
    lines = content.split('\n')
    new_lines = []
    skip = False
    for i, line in enumerate(lines):
        if 'if mode == "pyq":' in line and 'if' in line:
            new_lines.append(line)
            new_lines.append('                kb = InlineKeyboardMarkup(row_width=1)')
            new_lines.append('                kb.add(InlineKeyboardButton("📖 JEE Main Chapter-wise", callback_data="f_pyq:practice"))')
            new_lines.append('                kb.add(InlineKeyboardButton("🔥 JEE Adv Chapter-wise", callback_data="f_pyq_adv:practice"))')
            new_lines.append('                kb.add(InlineKeyboardButton("📝 JEE Main Papers", callback_data="f_pyq_papers_cat:JEE MAIN"))')
            new_lines.append('                kb.add(InlineKeyboardButton("🔥 JEE Adv Papers", callback_data="f_pyq_papers_cat:JEE ADV"))')
            new_lines.append('                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))')
            new_lines.append('                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)')
            new_lines.append('                return')
            skip = True
        elif skip:
            if 'kb = InlineKeyboardMarkup(row_width=3)' in line:
                skip = False
                new_lines.append(line)
        else:
            new_lines.append(line)
    content = '\n'.join(new_lines)
    print("✅ Menu replaced via fallback.")

# 2. Fix the Back button sending new messages
# Find the f_back handler
back_start = content.find('elif data.startswith("f_back:"):')
if back_start != -1:
    back_end = content.find('elif data', back_start + 20)
    if back_end != -1:
        new_back = '''elif data.startswith("f_back:"):
            target = data.split(":")[1]
            if target == "main":
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"), InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
                kb.add(InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"), InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional"))
                _b().edit_message_text("📚 <b>Exam Engine</b>\\nSelect Mode:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            elif target == "sub":
                mode = state.get("mode", "practice")
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
                _b().edit_message_text("📚 <b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            
        '''
        content = content[:back_start] + new_back + content[back_end:]
        print("✅ Back button fixed (Now edits instead of sending new).")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved perfectly.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
