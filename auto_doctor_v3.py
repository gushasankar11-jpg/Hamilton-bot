import os, re, ast, subprocess, time, urllib.request, json, sys

print("🩺 STARTING DOCTOR V3 (Universal Token Search)...")
print("=" * 50)

os.system('pkill -9 -f "python.*bot\\.py"')
time.sleep(1)

# 1. REBUILD BOT
print("[1] Rebuilding Bot...")
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

# 2. UNIVERSAL TOKEN SEARCH
print("\n[2] Searching for Token in ALL files...")
token = None

# The most robust Telegram token regex
token_pattern = re.compile(r'\b([0-9]{8,10}:[a-zA-Z0-9_-]{35})\b')

# Files to search
files_to_check = ["bot.py", "config.py"]
for f in os.listdir("bot_chunks"):
    if f.endswith(".py"):
        files_to_check.append(os.path.join("bot_chunks", f))

for file_path in files_to_check:
    if os.path.exists(file_path):
        content = open(file_path).read()
        match = token_pattern.search(content)
        if match:
            token = match.group(1)
            print(f"  ✅ Token found in {file_path}: ...{token[-6:]}")
            break

if not token:
    print("  ❌ Token NOT found anywhere! Please check your files.")
    sys.exit(1)

# 3. START BOT
print("\n[3] Starting Bot...")
os.system("nohup python -u bot.py > bot.log 2>&1 &")
time.sleep(5)

# 4. PING TELEGRAM
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

print("\n[5] Last 5 Lines of Bot Log:")
os.system("tail -n 5 bot.log")

# 5. START EXTRACTOR
print("\n[6] Starting Paper Extractor...")
os.system("nohup python3 extract_papers_ai.py > paper_extract.log 2>&1 &")
print("  ✅ Extractor started.")
print("=" * 50)
