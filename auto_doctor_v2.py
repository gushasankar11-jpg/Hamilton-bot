import os, re, ast, subprocess, time, urllib.request, json, sys

print("🩺 STARTING DOCTOR V2 (Robust Token Check)...")
print("=" * 50)

os.system('pkill -9 -f "python.*bot\\.py"')
time.sleep(1)

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

print("\n[2] Extracting Token from c01.py...")
c01_content = open("bot_chunks/c01.py").read()

# Look for ANY string that looks like a Telegram token (digits:letters)
token_match = re.search(r'[\'"](\d{8,10}:[a-zA-Z0-9_-]{35})[\'"]', c01_content)

if token_match:
    token = token_match.group(1)
    print(f"  ✅ Token found: {token[:10]}...{token[-4:]}")
else:
    print("  ❌ Token NOT found in c01.py. Here is the top of the file:")
    print("\n".join(c01_content.split("\n")[:20]))
    sys.exit(1)

print("\n[3] Starting Bot...")
os.system("nohup python -u bot.py > bot.log 2>&1 &")
time.sleep(5)

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

print("\n[6] Starting Paper Extractor...")
os.system("nohup python3 extract_papers_ai.py > paper_extract.log 2>&1 &")
print("  ✅ Extractor started.")
print("=" * 50)
