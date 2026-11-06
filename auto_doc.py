import os, re, ast, subprocess, time, sys

print("🩺 STARTING AUTOMATIC DIAGNOSIS & FIX...")
print("=" * 50)

# 1. KILL OLD BOTS
os.system('pkill -9 -f "python.*bot\\.py"')
time.sleep(1)

# 2. FIND & FIX SYNTAX ERRORS
print("\n[1] Checking for Syntax Errors...")
for f in sorted(os.listdir("bot_chunks")):
    if f.endswith(".py"):
        path = os.path.join("bot_chunks", f)
        content = open(path).read()
        try:
            ast.parse(content)
        except SyntaxError as e:
            print(f"  ❌ Syntax Error in {f} at line {e.lineno}: {e.msg}")
            if "expected an indented block" in e.msg:
                print(f"  🔧 Fixing empty try block in {f}...")
                content = re.sub(r'try:\n(\s*)except', r'try:\n\1    pass\nexcept', content)
                open(path, "w").write(content)

# 3. FIND & FIX DUPLICATE EXAM HANDLERS
print("\n[2] Checking for Duplicate Exam Handlers...")
path_exam = "bot_chunks/c04_exam.py"
if os.path.exists(path_exam):
    content = open(path_exam).read()
    count = content.count('def handle_buttons(call):')
    if count > 1:
        print(f"  🚨 Found {count} handle_buttons in c04_exam.py! Removing duplicates...")
        parts = content.split('@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))')
        # Keep the first handler, discard the rest
        content = parts[0] + '@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))' + parts[1]
        open(path_exam, "w").write(content)
        print("  ✅ Duplicates removed.")
    else:
        print("  ✅ Only one handle_buttons found.")

# 4. FIND & FIX COMMAND BLOCKERS (/plan issue)
print("\n[3] Checking for Command Blockers in c09.py...")
path_c09 = "bot_chunks/c09.py"
if os.path.exists(path_c09):
    content = open(path_c09).read()
    old_func = "func=lambda m: not _in_subreg_flow(m.chat.id),"
    new_func = "func=lambda m: not _in_subreg_flow(m.chat.id) and m.text and not m.text.startswith('/'),"
    if old_func in content:
        print("  🚨 Found catch-all text handler in c09.py! Patching to ignore commands...")
        content = content.replace(old_func, new_func)
        open(path_c09, "w").write(content)
        print("  ✅ c09.py patched.")
    else:
        print("  ✅ c09.py already ignores commands.")

# 5. REBUILD AND START
print("\n[4] Rebuilding Bot...")
with open("bot.py.new", "w") as out:
    for f in sorted(os.listdir("bot_chunks")):
        if f.endswith(".py") and f.startswith("c"):
            with open(os.path.join("bot_chunks", f), "r") as chunk:
                out.write(chunk.read())
                out.write("\n\n")

try:
    compile(open("bot.py.new").read(), "bot.py.new", "exec")
    print("  ✅ BUILD OK")
    os.system("mv bot.py.new bot.py")
except SyntaxError as e:
    print(f"  ❌ BUILD FAILED: {e}")
    sys.exit(1)

print("\n[5] Starting Bot...")
os.system("nohup python -u bot.py > bot.log 2>&1 &")
time.sleep(5)

# 6. SHOW LOG & TEST CONNECTION
print("\n[6] Last 10 Lines of Bot Log:")
os.system("tail -n 10 bot.log")

print("\n[7] Testing Telegram Connection...")
try:
    c01 = open("bot_chunks/c01.py").read()
    token = re.search(r'TeleBot\([\'"]([^\'"]+)[\'"]\)', c01).group(1)
    import urllib.request, json
    res = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    data = json.loads(res.read().decode())
    if data.get("ok"):
        print(f"  ✅ BOT IS RESPONDING! (@{data['result']['username']})")
    else:
        print("  ❌ Bot API Error.")
except Exception as e:
    print(f"  ❌ Connection Failed: {e}")

print("\n[8] Starting Paper Extractor...")
os.system("nohup python3 extract_papers_ai.py > paper_extract.log 2>&1 &")
print("  ✅ Extractor started.")
print("=" * 50)
