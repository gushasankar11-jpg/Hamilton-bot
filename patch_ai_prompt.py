path = "bot_chunks/c40_vision_ai.py"
content = open(path).read()

old_prompt_start = 'def get_ai_solution(q_text):'
old_prompt_end = '\ndef ai_scan_questions'

if old_prompt_start in content:
    start = content.find(old_prompt_start)
    end = content.find(old_prompt_end)
    if end == -1: end = len(content)
    
    new_func = '''def get_ai_solution(q_text):
    if not q_text:
        return "❌ No question text available."
    prompt = f"""Solve this JEE Main question with a SHORTCUT-focused approach.

Question: {q_text}

Use EXACTLY this 5-part format:

**1. General Process:** Standard textbook approach (brief, 1-2 lines)
**2. Shortcut:** Fastest trick to solve in exam (main focus)
**3. Guess & Predict:** How to eliminate wrong options or guess if stuck
**4. Skip Calculation:** Round-off / approximation tricks to skip long math
**5. Formula:** Core formula used

Emphasize shortcuts, guessing strategy, and skip-calculation tricks. Keep each part tight (1-2 sentences)."""
    return _call_ai(prompt, max_tokens=600)

'''
    content = content[:start] + new_func + content[end:]
    open(path, "w").write(content)
    print("✅ AI prompt updated with shortcut focus")
else:
    print("⚠️ Function not found")
