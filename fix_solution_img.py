import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# Find the f_solution handler
sol_idx = content.find('if data == "f_solution":')
if sol_idx != -1:
    sol_end = content.find('if data == "f_doubt":', sol_idx + 20)
    
    if sol_end != -1:
        new_sol_handler = '''if data == "f_solution":
            q = state.get("q", {})
            sol_img = q.get("solution_img")
            
            # 1. If we have the extracted book solution, send it instantly
            if sol_img and os.path.exists(sol_img):
                try:
                    with open(sol_img, "rb") as f:
                        _b().send_photo(uid, f, caption="📖 <b>Official Solution</b>\\n<i>If you have a doubt about this step, click 'Doubt'.</i>", parse_mode="HTML")
                except Exception as e:
                    _b().send_message(uid, f"❌ Error sending solution image: {e}")
            else:
                # 2. Fallback to AI (For MS Chauhan or missing solutions)
                load = _b().send_message(uid, "🧠 <i>Official solution not found. Generating AI solution...</i>")
                try:
                    q_text = q.get("q_text", "")
                    sol = get_ai_solution(q_text, uid)
                    clean_sol = clean_math(sol)
                    if len(clean_sol) > 4000: clean_sol = clean_sol[:4000] + "..."
                    _b().edit_message_text(clean_sol, chat_id=uid, message_id=load.message_id, parse_mode="HTML")
                except Exception as e:
                    _b().edit_message_text(f"❌ Error: {e}", chat_id=uid, message_id=load.message_id)
                    
        elif data == "f_doubt":'''
        
        content = content[:sol_idx] + new_sol_handler + content[sol_end:]
        print("✅ UI updated: Will send solution images first, fallback to AI text.")
    else:
        print("⚠️ Could not find end of f_solution block.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
