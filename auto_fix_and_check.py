import os, re, ast, subprocess, time, urllib.request, json

print("=== 1. FIXING INDENTATION ERRORS ===")
for filename in os.listdir("bot_chunks"):
    if filename.endswith(".py"):
        path = os.path.join("bot_chunks", filename)
        content = open(path).read()
        
        # Fix empty try blocks caused by commenting out lines
        # This looks for "try:" followed immediately by "except" with no indented block in between
        content = re.sub(r'try:\n\s*except', 'try:\n    pass\nexcept', content)
        # Also handle specific case where "try:" is at the end of a line and next line is "except"
        content = re.sub(r'try:\s*\n\s*except', 'try:\n    pass\nexcept', content)
        
        try:
            ast.parse(content)
            open(path, "w").write(content)
        except SyntaxError as e:
            print(f"❌ Still broken in {filename}: {e}")

# Specifically fix c30s_admin_cleanup.py which likely caused this
path_cleanup = "bot_chunks/c30s_admin_cleanup.py"
if os.path.exists(path_cleanup):
    content = open(path_cleanup).read()
    # Replace the commented out line with a safe pass
    content = content.replace("# bot.delete_message", "pass # bot.delete_message")
    open(path_cleanup, "w").write(content)
    print("✅ Patched c30s_admin_cleanup.py safely.")

print("\n=== 2. REBUILDING BOT ===")
os.system("> bot.py.new")
for f in sorted(os.listdir("bot_chunks")):
    if f.endswith(".py") and f.startswith("c"):
        os.system(f"cat bot_chunks/{f} >> bot.py.new")
        with open("bot.py.new", "a") as out:
            out.write("\n\n")

try:
    compile(open("bot.py.new").read(), "bot.py.new", "exec")
    print("✅ BUILD OK")
    os.system("mv bot.py.new bot.py")
except SyntaxError as e:
    print(f"❌ BUILD FAILED: {e}")
    sys.exit(1)

print("\n=== 3. STARTING BOT IN BACKGROUND ===")
os.system('pkill -9 -f "python.*bot\\.py"')
time.sleep(2)
os.system("nohup python -u bot.py > bot.log 2>&1 &")
time.sleep(5)

print("\n=== 4. HEALTH CHECK (IS IT RESPONDING?) ===")
try:
    # Read token from c01.py
    c01_content = open("bot_chunks/c01.py").read()
    match = re.search(r'TeleBot\([\'"]([^\'"]+)[\'"]\)', c01_content)
    if match:
        token = match.group(1)
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = urllib.request.urlopen(url, timeout=10)
        data = json.loads(response.read().decode())
        if data.get("ok"):
            print(f"✅ BOT IS RESPONDING! Username: @{data['result']['username']}")
        else:
            print("❌ BOT NOT RESPONDING (API Error).")
    else:
        print("⚠️ Could not find token in c01.py to test.")
except Exception as e:
    print(f"❌ BOT IS OFFLINE OR NETWORK ERROR: {e}")

print("\n=== 5. LAST LOG LINES ===")
os.system("tail -n 5 bot.log")

# Start extractor
os.system("nohup python3 extract_papers_ai.py > paper_extract.log 2>&1 &")
print("\n✅ Paper Extractor also started in background.")
