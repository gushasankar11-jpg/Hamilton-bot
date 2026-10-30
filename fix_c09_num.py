path = "bot_chunks/c09.py"
content = open(path).read()

old_text = '''    # --- DOUBT HANDLER ---
    if st.get("waiting_for_doubt"):'''

new_text = '''    # --- PYQ NUMERICAL HANDLER ---
    if st.get("waiting_for_pyq_numeric"):
        st["waiting_for_pyq_numeric"] = False
        st["pyq_timer_active"] = False
        q = st.get("q", {})
        
        _b().send_message(uid, "🤔 <i>Checking your answer...</i>")
        
        # Since the original question had options, we check if the student's text matches the correct option's value
        # (For true numericals, we would compare floats, but here we just pass it to AI)
        prompt = f"The correct option index is {q.get('correct_index', 0)}. The student typed: '{message.text}'. Evaluate if this is likely correct based on standard JEE Main numerical values. Reply '✅ Correct' or '❌ Wrong' followed by a 1-line explanation."
        
        try:
            import ai_client
            reply = ai_client.ask_ai(prompt)
            _b().send_message(uid, reply)
        except:
            _b().send_message(uid, "❌ Could not verify. Moving on.")
            
        st["pyq_index"] += 1
        send_pyq_q(uid)
        return

    # --- DOUBT HANDLER ---
    if st.get("waiting_for_doubt"):'''
    
if old_text in content:
    content = content.replace(old_text, new_text)
    open(path, "w").write(content)
    print("✅ c09.py numerical handler added.")
