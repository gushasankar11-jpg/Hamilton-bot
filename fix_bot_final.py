import ast, os

# 1. Hard disable _auth_text_router in c30a
path_auth = "bot_chunks/c30a_admin_auth.py"
if os.path.exists(path_auth):
    content = open(path_auth).read()
    start_idx = content.find("def _auth_text_router(message):")
    if start_idx != -1:
        end_idx = content.find("\ndef ", start_idx + 20)
        if end_idx == -1: end_idx = len(content)
        
        # Comment out the whole function
        func_body = content[start_idx:end_idx]
        commented = "\n".join(["# " + line for line in func_body.split("\n")])
        content = content[:start_idx] + commented + content[end_idx:]
        
        open(path_auth, "w").write(content)
        print("✅ DISABLED _auth_text_router completely.")

# 2. Fix c09.py to strictly only handle non-commands
path_c09 = "bot_chunks/c09.py"
if os.path.exists(path_c09):
    content = open(path_c09).read()
    if "def free_text_handler(message):" in content:
        content = content.replace(
            "def free_text_handler(message):", 
            "def free_text_handler(message):\n    if message.text and message.text.startswith('/'): return"
        )
        open(path_c09, "w").write(content)
        print("✅ c09.py strictly ignores commands.")

# 3. Ensure c50_planner loads and has a print statement
if not os.path.exists("bot_chunks/c50_planner.py"):
    print("❌ c50_planner.py missing! You need to recreate it.")
else:
    pc = open("bot_chunks/c50_planner.py").read()
    if "✅ c50_planner loaded" not in pc:
        pc += '\nprint("✅ c50_planner loaded.")\n'
        open("bot_chunks/c50_planner.py", "w").write(pc)
        print("✅ c50_planner.py is present.")
