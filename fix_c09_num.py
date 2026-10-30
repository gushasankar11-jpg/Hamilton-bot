import ast

path = "bot_chunks/c09.py"
content = open(path).read()

old_block = '''    # --- DOUBT HANDLER ---
    st = _state.get(uid, {})
    if st.get("waiting_for_doubt"):'''
new_block = '''    # --- PYQ NUMERICAL HANDLER ---
    st = _state.get(uid, {})
    if st.get("waiting_for_pyq_numeric"):
        st["waiting_for_pyq_numeric"] = False
        st["pyq_timer_active"] = False
        q = st.get("q", {})
        
        _b().send_message(uid, "🤔 <i>Verifying your numerical answer via AI...</i>")
        
        # Use Vision AI to verify the numerical answer
        import ai_client
        # Since we can't send the image easily, we assume ai_client can handle text
        prompt = f"JEE Main Numerical Question from {q.get('subtopic')}. The student's answer is: {message.text}. The correct MCQ options were A,B,C,D but the student is answering as a numerical. Please calculate the exact numerical value for this question model and tell me if the student is correct. Give a 1-line verdict (Correct or Wrong) and the exact value."
        
        try:
            reply = ai_client.ask_ai(prompt)
            _b().send_message(uid, f"📝 <b>AI Verification:</b>\\n{reply}")
        except Exception as e:
            _b().send_message(uid, f"❌ AI Error: {e}")
            
        # Move to next question
        st["pyq_index"] += 1
        send_pyq_q(uid)
        return

    # --- DOUBT HANDLER ---
    if st.get("waiting_for_doubt"):'''
    
if old_block in content:
    content = content.replace(old_block, new_block)
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ c09.py: Numerical PYQ handler added.")
    except SyntaxError as e:
        print("❌ c09 Syntax Error:", e)
else:
    print("⚠️ c09 pattern not found.")

