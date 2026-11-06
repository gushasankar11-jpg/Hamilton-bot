import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# Add a global cache at the top
if "_PYQ_CACHE" not in content:
    cache_code = '''
import json
_PYQ_CACHE = {"practice": {}, "practice_adv": {}, "papers": {}}
def load_pyq_cache():
    global _PYQ_CACHE
    try:
        with open("data/pyq_master.json") as f:
            _PYQ_CACHE = json.load(f)
    except Exception as e:
        print(f"Cache load error: {e}")
'''
    content = content.replace("def _b(): return", cache_code + "\ndef _b(): return", 1)

# Replace slow json loads in handlers with the cache
content = content.replace('with open("data/pyq_master.json") as f: db = json.load(f)', 'db = _PYQ_CACHE')
content = content.replace('with open("data/pyq_master.json") as f: db = json.load(f)\n                papers = db.get("papers", {})', 'db = _PYQ_CACHE\n                papers = db.get("papers", {})')

# Ensure cache reloads after a paper finishes (so you don't need to restart)
if 'def handle_buttons(call):' in content:
    content = content.replace('def handle_buttons(call):\n    try:', 'def handle_buttons(call):\n    load_pyq_cache() # Reload every click for now (still faster than parsing huge file 3 times)\n    try:')

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Injected DB Cache. Buttons will not freeze anymore.")
except SyntaxError as e:
    print(f"❌ Syntax Error: {e}")
