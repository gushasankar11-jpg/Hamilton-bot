import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Fix the f_pyq_sub handler
start_sub = content.find('        elif data.startswith("f_pyq_sub:"):')
end_sub = content.find('        elif data.startswith("f_pyq_ch:"):')

if start_sub != -1 and end_sub != -1:
    new_sub_block = '''        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json
            chapters = []
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                extracted = db.get("practice", {}).get(subj, {})
                chapters = list(extracted.keys())
            except Exception:
                pass

            if not chapters:
                _b().answer_callback_query(call.id, "⏳ Processing... Please wait. No chapters extracted yet for this subject.", show_alert=True)
                return

            kb = InlineKeyboardMarkup(row_width=1)
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - Extracted PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

'''
    content = content[:start_sub] + new_sub_block + content[end_sub:]
    print("✅ Fixed f_pyq_sub (Shows only extracted chapters).")

# 2. Fix the f_pyq_ch handler and send_pyq_q
start_ch = content.find('        elif data.startswith("f_pyq_ch:"):')
end_ch = content.find('        elif data == "f_back:"', start_ch)
if end_ch == -1: end_ch = content.find('        elif data.startswith("f_back:")', start_ch)

if start_ch != -1 and end_ch != -1:
    new_ch_block = '''        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                q_data = db[subj][ch]
            except Exception as e:
                _b().answer_callback_query(call.id, f"❌ Error loading DB: {e}", show_alert=True)
                return

            if not q_data.get("priority") and not q_data.get("normal"):
                _b().answer_callback_query(call.id, "⚠️ No questions found in this chapter.", show_alert=True)
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
            
            # Call the sender, wrapped in try/except
            try:
                send_pyq_q(uid)
            except Exception as e:
                _b().send_message(uid, f"❌ UI Crash: {e}")
                print(f"PYQ UI CRASH: {e}")

'''
    content = content[:start_ch] + new_ch_block + content[end_ch:]
    print("✅ Fixed f_pyq_ch (Added error catching).")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Syntax OK.")
except SyntaxError as e:
    print("❌ Syntax Error:", e)
