import ast
path = "bot_chunks/c30p_live_update.py"
content = open(path).read()
if "import sys" not in content:
    content = "import sys\n" + content
if "def bot():" not in content:
    content = content.replace("bot.", "sys.modules['__main__'].bot.")
try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Fixed live update bug.")
except:
    print("⚠️ Could not patch, but will continue.")
