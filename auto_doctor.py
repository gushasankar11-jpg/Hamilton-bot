import os, re, ast, subprocess, time, urllib.request, json, sys

print("🩺 STARTING DIAGNOSIS & AUTO-FIX...")
print("=" * 50)

# 1. KILL OLD BOTS
os.system('pkill -9 -f "python.*bot\\.py"')
time.sleep(1)

# 2. DISABLE THE AGGRESSIVE CLEANUP (Which is deleting the buttons)
path_cleanup = "bot_chunks/c30s_admin_cleanup.py"
if os.path.exists(path_cleanup):
    os.rename(path_cleanup, path_cleanup + ".disabled")
    print("✅ Disabled c30s_admin_cleanup.py (Fixed Exam Center disappearing buttons).")

# 3. REBUILD BOT
print("\n[1] Rebuilding Bot...")
with open("bot.py.new", "w") as out:
    for f in sorted(os.listdir("bot_chunks")):
        if f.endswith(".py") and f.startswith("c"):
            with open(os.path.join("bot_chunks", f), "r") as chunk:
                out.write(chunk.read())
                out.write("\n\n")

try:
    compile(open("bot.py.new").read(), "bot.py.new", "exec")
    os.system("mv bot.py.new bot.py")
    print("  ✅ BUILD OK")
except SyntaxError as e:
    print(f"  ❌ BUILD FAILED: {e}")
    sys.exit(1)

# 4. EXTRACT TOKEN (Robust Regex)
print("\n[2] Extracting Bot Token...")
bot_code = open("bot.py").read()
# Matches any string like 1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
token_match = re.search(r'\b(\d{8,10}:[a-zA-Z0-9_-]{35})\b', bot_code)

if token_match:
    token = token_match.group(1)
    print(f"  ✅ Token found: ...{token[-6:]}")
else:
    print("  ❌ Token NOT found in code. Please check c01.py manually.")
    token = None

# 5. START BOT
print("\n[3] Starting Bot...")
os.system("nohup python -u bot.py > bot.log 2>&1 &")
time.sleep(5)

# 6. PING TELEGRAM
if token:
    print("\n[4] Testing Telegram Connection...")
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = urllib.request.urlopen(url, timeout=10)
        data = json.loads(response.read().decode())
        if data.get("ok"):
            print(f"  ✅ BOT IS RESPONDING! (@{data['result']['username']})")
        else:
            print(f"  ❌ Bot API Error: {data}")
    except Exception as e:
        print(f"  ❌ Connection Failed: {e}")

# 7. START EXTRACTOR
print("\n[5] Starting Paper Extractor...")
os.system("nohup python3 extract_papers_ai.py > paper_extract.log 2>&1 &")
print("  ✅ Extractor started.")
print("=" * 50)
