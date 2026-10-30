import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Deduplicate by finding the first _show_chapters and keeping only the first block
marker = "def _show_chapters(uid, msg_id):"
parts = content.split(marker)

if len(parts) > 2:
    print(f"🚨 Found {len(parts)-1} duplicate blocks! Cleaning...")
    # Keep the imports, the first _show_chapters, and the code that follows it
    content = parts[0] + marker + parts[1]
    print("✅ Deduplicated c04_exam.py successfully.")
else:
    print("No duplicates found.")

# 2. Ensure the PYQ UI is properly patched in the clean file
if "pyq_master.json" not in content:
    print("⚠️ PYQ patch missing in clean file. Re-injecting...")
    old_pyq = '''        elif data.startswith("f_pyq_ch:"):'''
    start_idx = content.find(old_pyq)
    if start_idx != -1:
        end_idx = content.find('        elif data == "f_back:"', start_idx)
        if end_idx == -1: end_idx = content.find('        elif data.startswith("f_back:")', start_idx)
        
        if end_idx != -1:
            new_block = '''        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                q_data = db[subj][ch]
            except Exception as e:
                _b().answer_callback_query(call.id, "No questions found for this chapter.")
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            send_pyq_q(uid)

'''
            content = content[:start_idx] + new_block + content[end_idx:]
            print("✅ Re-patched f_pyq_ch handler.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py is now clean and syntax-valid.")
except SyntaxError as e:
    print("❌ Syntax Error:", e)
