import ast, os

# 1. Remove old /plan handler from c03.py
path_c03 = "bot_chunks/c03.py"
if os.path.exists(path_c03):
    content = open(path_c03).read()
    lines = content.split("\n")
    new_lines = []
    skip = False
    for i, line in enumerate(lines):
        if "@bot.message_handler(commands=['plan'])" in line:
            skip = True
            print("✅ Found old /plan handler in c03.py. Removing it...")
            continue
        if skip:
            if line.startswith("def ") or (line.startswith("@bot")):
                skip = False
                new_lines.append(line)
            continue
        new_lines.append(line)
    
    new_content = "\n".join(new_lines)
    try:
        ast.parse(new_content)
        open(path_c03, "w").write(new_content)
        print("✅ c03.py cleaned.")
    except SyntaxError as e:
        print(f"❌ c03.py Syntax Error: {e}")

# 2. Fix c09.py to ignore commands completely
path_c09 = "bot_chunks/c09.py"
if os.path.exists(path_c09):
    content = open(path_c09).read()
    
    old_filter = '''@bot.message_handler(
    func=lambda m: not _in_subreg_flow(m.chat.id),
    content_types=['text']
)'''
    new_filter = '''@bot.message_handler(
    func=lambda m: not _in_subreg_flow(m.chat.id) and not (m.text and m.text.startswith('/')),
    content_types=['text']
)'''
    
    if old_filter in content:
        content = content.replace(old_filter, new_filter)
        try:
            ast.parse(content)
            open(path_c09, "w").write(content)
            print("✅ c09.py filter updated (ignores all /commands).")
        except SyntaxError as e:
            print(f"❌ c09.py Syntax Error: {e}")
    else:
        print("⚠️ Could not find exact filter in c09.py")

print("✅ Interceptors fixed.")
