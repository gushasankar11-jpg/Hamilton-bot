import os, ast

print("🔧 Applying Permanent Fixes (V2)...")

# 1. FIX c09.py TEXT HANDLER (Simple String Replace)
path_c09 = "bot_chunks/c09.py"
if os.path.exists(path_c09):
    content = open(path_c09).read()
    target = "def free_text_handler(message):"
    injection = "def free_text_handler(message):\n    if message.text and message.text.startswith('/'): return # Ignore commands"
    
    if target in content and injection not in content:
        content = content.replace(target, injection)
        try:
            ast.parse(content)
            open(path_c09, "w").write(content)
            print("✅ c09.py: Successfully patched text handler.")
        except SyntaxError as e:
            print(f"❌ c09.py Syntax Error: {e}")
    else:
        print("✅ c09.py: Already patched or handler not found.")

# 2. DISABLE BROKEN CLEANUP
path_cleanup = "bot_chunks/c30s_admin_cleanup.py"
if os.path.exists(path_cleanup):
    os.rename(path_cleanup, path_cleanup + ".disabled")
    print("✅ c30s_admin_cleanup.py disabled (Stops button vanishing).")

# 3. FIX EXAM CENTER PAPER BUTTONS (Short Index)
path_exam = "bot_chunks/c04_exam.py"
if os.path.exists(path_exam):
    content = open(path_exam).read()
    
    # Replace the long callback_data string with an index
    old_btn = 'kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_pyq_paper:{p_name}"))'
    new_btn = '''if "paper_list" not in state: state["paper_list"] = []
                    state["paper_list"].append(p_name)
                    kb.add(InlineKeyboardButton(f"📄 {short[:40]}", callback_data=f"f_pyq_paper_idx:{len(state['paper_list'])-1}"))'''
    
    if old_btn in content:
        content = content.replace(old_btn, new_btn)
        print("✅ c04_exam.py: Paper buttons updated to use short Index.")
    else:
        print("⚠️ c04_exam.py: Could not find exact paper button string. (It might already be patched).")

    # Add the handler for the index
    if 'f_pyq_paper_idx:' not in content:
        new_handler = '''
        elif data.startswith("f_pyq_paper_idx:"):
            idx = int(data.split(":")[1])
            paper_name = state.get("paper_list", [])[idx]
            import json
            with open("data/pyq_master.json") as f: db = json.load(f)
            paper_data = db.get("papers", {}).get(paper_name)
            if not paper_data: return
            
            state["mode"] = "pyq"
            state["subj"] = "Full Paper"
            state["chapter"] = paper_name
            state["pyq_questions"] = paper_data.get("questions", [])
            state["pyq_index"] = 0
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            send_pyq_q(uid)
            return
'''
        if 'elif data.startswith("f_back:")' in content:
            content = content.replace('elif data.startswith("f_back:")', new_handler + '\n        elif data.startswith("f_back:")', 1)
            print("✅ c04_exam.py: Added f_pyq_paper_idx handler.")
            
    try:
        ast.parse(content)
        open(path_exam, "w").write(content)
    except SyntaxError as e:
        print(f"❌ c04_exam.py Syntax Error: {e}")

# 4. REBUILD BOT
print("🔨 Rebuilding Bot...")
with open("bot.py.new", "w") as out:
    for f in sorted(os.listdir("bot_chunks")):
        if f.endswith(".py") and f.startswith("c"):
            with open(os.path.join("bot_chunks", f), "r") as chunk:
                out.write(chunk.read())
                out.write("\n\n")

try:
    compile(open("bot.py.new").read(), "bot.py.new", "exec")
    os.system("mv bot.py.new bot.py")
    print("✅ BUILD OK")
except SyntaxError as e:
    print(f"❌ BUILD FAILED: {e}")

