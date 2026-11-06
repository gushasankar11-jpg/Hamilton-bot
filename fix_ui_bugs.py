import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Fix get_ai_solution uid
content = content.replace('def get_ai_solution(q_text):', 'def get_ai_solution(q_text, uid=None):')
content = content.replace('exam = _state.get(uid, {}).get("exam", "JEE_MAIN")\n        return ai_client.ask_hamilton(exam, prompt)', 'exam = _state.get(uid, {}).get("exam", "JEE_MAIN") if uid else "JEE_MAIN"\n        return ai_client.ask_hamilton(exam, prompt)')
content = content.replace('sol = get_ai_solution(q_text)', 'sol = get_ai_solution(q_text, uid)')
print("✅ Fixed AI Solution uid error.")

# 2. Fix Captions (No Priority for Adv/Papers)
old_cap = '''    if is_num:
        state["pyq_is_numerical"] = True
        state["waiting_for_pyq_numeric"] = True
        cap = f"🔢 <b>PYQ {idx+1}/{len(q_list)} (NUMERICAL)</b>\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s\\n<i>Type your numerical answer.</i>"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    else:
        phase = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
        cap = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase})</b>\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s | 📊 Diff: {diff_str} | Type: {qtype}"'''

new_cap = '''    if state.get("pyq_is_paper"):
        header = f"📝 <b>Question {idx+1}/{len(q_list)}</b>"
    elif state.get("is_adv"):
        header = f"🔥 <b>Adv Q {idx+1}/{len(q_list)}</b>"
    else:
        phase = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
        header = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase})</b>"

    if is_num:
        state["pyq_is_numerical"] = True
        state["waiting_for_pyq_numeric"] = True
        cap = f"🔢 {header} (NUMERICAL)\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s\\n<i>Type your numerical answer.</i>"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    else:
        cap = f"{header}\\n📅 {q.get('source','JEE Main')}\\n⏱ Ideal: {ideal}s | 📊 Diff: {diff_str} | Type: {qtype}"'''
if old_cap in content:
    content = content.replace(old_cap, new_cap)
    print("✅ Captions updated (No Priority for Adv/Papers).")

# 3. Fix Adv Subject Freeze
old_adv_sub = '''    if data.startswith("f_pyq_adv_sub:"):
        subj = data.split(":")[1]
        state["pyq_subj"] = subj
        import json
        try:
            with open("data/pyq_master.json") as f: db = json.load(f)
            chapters = list(db.get("practice_adv", {}).get(subj, {}).keys())
        except: chapters = []
        
        kb = InlineKeyboardMarkup(row_width=1)
        if not chapters:
            _b().send_message(uid, f"⏳ <b>{subj} - Still Processing</b>\\nNo chapters extracted yet for Advanced.")
            return
        
        for ch in chapters:
            kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_adv_ch:{ch}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq_adv:practice"))
        _b().edit_message_text(f"🔥 <b>{subj} - Advanced Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return'''

new_adv_sub = '''    if data.startswith("f_pyq_adv_sub:"):
        subj = data.split(":")[1]
        state["pyq_subj"] = subj
        state["is_adv"] = True
        import json
        try:
            with open("data/pyq_master.json") as f: db = json.load(f)
            chapters = list(db.get("practice_adv", {}).get(subj, {}).keys())
        except Exception as e: 
            chapters = []
            _b().send_message(uid, f"❌ Error loading DB: {e}")
        
        kb = InlineKeyboardMarkup(row_width=1)
        if not chapters:
            _b().send_message(uid, f"⏳ <b>{subj} - Still Processing</b>\\nNo chapters extracted yet for Advanced.")
            return
        
        for ch in chapters:
            kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_adv_ch:{ch}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq_adv:practice"))
        _b().edit_message_text(f"🔥 <b>{subj} - Advanced Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        return'''

if old_adv_sub in content:
    content = content.replace(old_adv_sub, new_adv_sub)
    print("✅ Adv Subject handler fixed (No more freezing).")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
