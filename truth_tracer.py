import os, re, ast, subprocess, time, urllib.request, json, sys

print("🩺 STARTING TRUTH TRACER...")
print("=" * 50)

# 1. KILL ALL PYTHON
os.system('pkill -9 -f "python"')
time.sleep(1)

# 2. GET TOKEN FROM CONFIG
print("[1] Reading Token from config.py...")
try:
    import config
    token = config.BOT_TOKEN
    print(f"  ✅ Token found: ...{token[-6:]}")
except Exception as e:
    print(f"  ❌ Could not import config.py: {e}")
    sys.exit(1)

# 3. DELETE WEBHOOK (Fixes 99% of silent bots)
print("\n[2] Deleting Telegram Webhook...")
try:
    url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    urllib.request.urlopen(url, timeout=10)
    print("  ✅ Webhook cleared. Polling is now enabled.")
except Exception as e:
    print(f"  ❌ Failed to clear webhook: {e}")

# 4. PATCH BOT TO ENABLE TELEGRAM DEBUG LOGGING
print("\n[3] Enabling Raw Telegram Update Logging...")
path = "bot_chunks/c100_router.py"
if os.path.exists(path):
    content = open(path).read()
    if "import logging" not in content:
        content = "import logging\ntelebot.logger.setLevel(logging.DEBUG)\n" + content
        open(path, "w").write(content)
        print("  ✅ Debug logging injected into c100_router.py.")

# 5. REBUILD
print("\n[4] Rebuilding Bot...")
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

# 6. START BOT
print("\n[5] Starting Bot...")
os.system("nohup python -u bot.py > bot.log 2>&1 &")
time.sleep(5)
print("  ✅ Bot started in background.")
print("=" * 50)
