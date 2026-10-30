import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Force replace the f_pyq_ch handler to use pyq_master.json
old_pyq = '''        elif data.startswith("f_pyq_ch:"):'''
start_idx = content.find(old_pyq)
if start_idx != -1:
    # Find the next elif or end of block to replace the whole function
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
                _b().answer_callback_query(call.id, "No questions found for this chapter. (Rebuild needed)")
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0
            
            # Send the FIRST question with the interactive UI
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            send_pyq_q(uid)

'''
        content = content[:start_idx] + new_block + content[end_idx:]
        print("✅ f_pyq_ch handler completely replaced.")

# 2. Ensure send_pyq_q exists and uses the correct format
if "def send_pyq_q(uid, msg_id=None):" not in content:
    print("❌ send_pyq_q is missing! The UI cannot work.")
else:
    print("✅ send_pyq_q exists.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py syntax OK.")
except SyntaxError as e:
    print("❌ Syntax Error:", e)
