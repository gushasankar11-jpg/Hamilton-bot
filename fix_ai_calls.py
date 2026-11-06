import ast, re

for path in ["bot_chunks/c04_exam.py", "bot_chunks/c09.py"]:
    content = open(path).read()
    
    # Fix: ai_client.ask_ai(prompt) -> ai_client.ask_hamilton(exam, prompt)
    content = content.replace(
        'return ai_client.ask_ai(prompt)',
        'exam = _state.get(uid, {}).get("exam", "JEE_MAIN")\n        return ai_client.ask_hamilton(exam, prompt)'
    )
    content = content.replace(
        'reply = ai_client.ask_ai(prompt)',
        'exam = _state.get(uid, {}).get("exam", "JEE_MAIN")\n            reply = ai_client.ask_hamilton(exam, prompt)'
    )
    content = content.replace(
        'reply = ai_client.ask_ai(prompt)\n',
        'exam = _state.get(uid, {}).get("exam", "JEE_MAIN")\n            reply = ai_client.ask_hamilton(exam, prompt)\n'
    )
    
    # Also fix any _call_groq direct calls to be safe
    if "_call_groq" in content:
        print(f"⚠️ {path} uses _call_groq — will leave for now, but may need fix")
    
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print(f"✅ {path} — AI calls fixed")
    except SyntaxError as e:
        print(f"❌ {path} syntax: {e}")
