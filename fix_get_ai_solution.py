import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# ===== 1. Add fallback get_ai_solution inline (uses ai_client which is loaded) =====
if "def get_ai_solution(" not in content:
    fallback = '''
def get_ai_solution(q_text):
    """Fallback AI solution — uses ai_client which is always loaded."""
    if not q_text:
        return "❌ No question text available."
    prompt = f"""Solve this JEE Main question with SHORTCUT-focused approach.

Question: {q_text}

Use EXACTLY this 5-part format:

**1. General Process:** Standard textbook approach (1-2 lines)
**2. Shortcut:** Fastest trick to solve in exam
**3. Guess & Predict:** How to eliminate wrong options or guess if stuck
**4. Skip Calculation:** Round-off / approximation tricks
**5. Formula:** Core formula used

Emphasize shortcuts, guessing strategy, and skip-calculation tricks."""
    try:
        import ai_client
        return ai_client.ask_ai(prompt)
    except Exception as e:
        return f"❌ AI Error: {e}"

'''
    # Insert before def clean_math (very top of file after imports)
    marker = "def clean_math(text):"
    content = content.replace(marker, fallback + "\n" + marker, 1)
    print("✅ Added fallback get_ai_solution")
else:
    print("✅ get_ai_solution already exists")

# ===== 2. Fix the f_solution handler — remove any `from c40` import =====
content = re.sub(r'from c40_vision_ai import[^\n]*\n', '', content)
print("✅ Removed bad c40 imports")

# ===== 3. Ensure the f_solution handler catches errors =====
sol_start = content.find('elif data == "f_solution":')
if sol_start != -1:
    sol_end = content.find('\n        elif data', sol_start + 30)
    if sol_end == -1:
        sol_end = content.find('\n        @bot', sol_start + 30)
    
    if sol_end != -1:
        new_sol = '''elif data == "f_solution":
            try: _b().answer_callback_query(call.id, "Generating...")
            except: pass
            load = _b().send_message(uid, "🧠 <i>Generating solution...</i>")
            try:
                q_text = state.get("q", {}).get("q_text", "")
                if not q_text:
                    _b().edit_message_text("❌ No question text in DB.", chat_id=uid, message_id=load.message_id)
                else:
                    sol = get_ai_solution(q_text)
                    _b().edit_message_text(sol, chat_id=uid, message_id=load.message_id, parse_mode="Markdown")
            except Exception as e:
                _b().edit_message_text(f"❌ Error: {e}", chat_id=uid, message_id=load.message_id)
            
            # Re-show navigation bar
            nav_kb = _build_pyq_nav(uid)
            if nav_kb:
                n_msg = _b().send_message(uid, "🧭 <b>Navigation:</b>", parse_mode="HTML", reply_markup=nav_kb)
                state["pyq_nav_msg_id"] = n_msg.message_id
        '''
        content = content[:sol_start] + new_sol + content[sol_end:]
        print("✅ f_solution handler cleaned")

# ===== 4. Fix the doubt handler in c09.py too (probably has same issue) =====
path_c09 = "bot_chunks/c09.py"
c09_content = open(path_c09).read()

# Find the doubt handler that uses get_ai_solution or ai_client
if "get_ai_solution" in c09_content or "waiting_for_doubt" in c09_content:
    # Make sure it uses ai_client directly
    c09_content = re.sub(r'from c40_vision_ai import[^\n]*\n', '', c09_content)
    # Find doubt handler pattern and inject fallback
    if "def get_ai_solution(" not in c09_content and "import ai_client" in c09_content:
        pass  # already has ai_client
    
    try:
        ast.parse(c09_content)
        open(path_c09, "w").write(c09_content)
        print("✅ c09.py cleaned")
    except SyntaxError as e:
        print(f"⚠️ c09 syntax: {e}")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("\n✅ c04_exam.py — syntax OK")
except SyntaxError as e:
    print(f"\n❌ SYNTAX ERROR: {e}")
