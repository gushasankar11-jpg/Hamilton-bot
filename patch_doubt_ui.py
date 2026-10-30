import ast

# ==========================================
# PATCH c04_exam.py (Difficulty Format + Doubt Button)
# ==========================================
path_exam = "bot_chunks/c04_exam.py"
content = open(path_exam).read()

# 1. Update Difficulty formatting in send_pyq_q
old_caption = """    phase_name = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {q.get('difficulty', 5)}/10\""""
new_caption = """    phase_name = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
    
    # Format Difficulty as "8 (Hard)"
    diff_num = q.get('difficulty', 5)
    if isinstance(diff_num, int):
        diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
        diff_str = f"{diff_num} ({diff_text})"
    else:
        diff_str = str(diff_num)
        
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\\n📅 {q.get('source', 'JEE Main')}\\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\\n📊 Difficulty: {diff_str}\""""
if old_caption in content:
    content = content.replace(old_caption, new_caption)
    print("✅ Difficulty format updated.")

# 2. Add "Doubt in Explanation" button in f_save
old_save_kb = """                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)"""
new_save_kb = """                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)"""
if old_save_kb in content:
    content = content.replace(old_save_kb, new_save_kb)
    print("✅ Doubt button added to f_save.")

# 3. Add f_doubt handler in callbacks
if 'data == "f_doubt"' not in content:
    marker = '        elif data == "f_next_q":'
    doubt_handler = '''        elif data == "f_doubt":
            state["waiting_for_doubt"] = True
            _b().send_message(uid, "💬 <b>Please type your doubt about this question or explanation.</b>\\nHamilton will answer it for you.", parse_mode="HTML")
            
        elif data == "f_next_q":'''
    content = content.replace(marker, doubt_handler)
    print("✅ f_doubt callback added.")

try:
    ast.parse(content)
    open(path_exam, "w").write(content)
except SyntaxError as e:
    print("❌ c04_exam Syntax Error:", e)


# ==========================================
# PATCH c09.py (Handle the Doubt Text)
# ==========================================
path_c09 = "bot_chunks/c09.py"
content_c09 = open(path_c09).read()

# Inject the doubt handler right at the start of free_text_handler
if 'state.get("waiting_for_doubt")' not in content_c09:
    old_text_handler = """def free_text_handler(message):
    uid = message.chat.id"""
    new_text_handler = """def free_text_handler(message):
    uid = message.chat.id
    
    # --- DOUBT HANDLER ---
    st = _state.get(uid, {})
    if st.get("waiting_for_doubt"):
        st["waiting_for_doubt"] = False
        q = st.get("q", {})
        exp = q.get("explanation", "")
        doubt = message.text
        
        msg = _b().send_message(uid, "🤔 <i>Analyzing your doubt...</i>", parse_mode="HTML")
        
        prompt = f"Question context: {q.get('subtopic', '')}\\nExplanation: {exp}\\n\\nStudent's doubt: {doubt}\\n\\nAnswer clearly and concisely."
        
        try:
            import ai_client
            reply = ai_client.ask_ai(prompt)
            _b().edit_message_text(f"💡 <b>Answer to your doubt:</b>\\n\\n{reply}", chat_id=uid, message_id=msg.message_id, parse_mode="Markdown")
        except Exception as e:
            _b().edit_message_text(f"❌ AI Error: {e}", chat_id=uid, message_id=msg.message_id)
        return
    # --------------------"""
    
    if old_text_handler in content_c09:
        content_c09 = content_c09.replace(old_text_handler, new_text_handler)
        try:
            ast.parse(content_c09)
            open(path_c09, "w").write(content_c09)
            print("✅ Doubt text handler added to c09.py.")
        except SyntaxError as e:
            print("❌ c09 Syntax Error:", e)
    else:
        print("⚠️ free_text_handler pattern not found in c09.py.")
else:
    print("⏭️ Doubt handler already exists in c09.py.")

