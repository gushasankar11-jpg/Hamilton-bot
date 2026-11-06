import ast, re

path = "bot_chunks/c04_exam.py"
lines = open(path).readlines()

# 1. Find the f_solution block
start_idx = -1
for i, line in enumerate(lines):
    if 'if data == "f_solution":' in line:
        start_idx = i
        break

if start_idx == -1:
    print("❌ Could not find f_solution block.")
    exit(1)

# 2. Determine its indentation
indent = lines[start_idx][:len(lines[start_idx]) - len(lines[start_idx].lstrip())]
indent_next = indent + "    "
indent_next2 = indent_next + "    "

# 3. Find the end of the block (next elif/else at the same indent)
end_idx = -1
for i in range(start_idx + 1, len(lines)):
    if lines[i].startswith(indent + "elif ") or lines[i].startswith(indent + "else:"):
        end_idx = i
        break
    if lines[i].startswith(indent + "if data == "): # Sometimes developers use `if` instead of `elif`
        end_idx = i
        break

if end_idx == -1:
    print("❌ Could not find end of f_solution block.")
    exit(1)

# 4. Build the new block with perfect indentation
new_block = f'''{indent}if data == "f_solution":
{indent_next}q = state.get("q", {{}})
{indent_next}sol_img = q.get("solution_img")
{indent_next}
{indent_next}# 1. Send Image if available
{indent_next}if sol_img and os.path.exists(sol_img):
{indent_next2}try:
{indent_next2}    with open(sol_img, "rb") as f:
{indent_next2}        _b().send_photo(uid, f, caption="📖 <b>Official Solution</b>\\n<i>If you have a doubt, click 'Doubt'.</i>", parse_mode="HTML")
{indent_next2}except Exception as e:
{indent_next2}    _b().send_message(uid, f"❌ Error sending solution image: {{e}}")
{indent_next}else:
{indent_next2}# 2. Fallback to AI (for MS Chauhan or missing solutions)
{indent_next2}load = _b().send_message(uid, "🧠 <i>Official solution not found. Generating AI solution...</i>")
{indent_next2}try:
{indent_next2}    q_text = q.get("q_text", "")
{indent_next2}    sol = get_ai_solution(q_text, uid)
{indent_next2}    clean_sol = clean_math(sol)
{indent_next2}    if len(clean_sol) > 4000: clean_sol = clean_sol[:4000] + "..."
{indent_next2}    _b().edit_message_text(clean_sol, chat_id=uid, message_id=load.message_id, parse_mode="HTML")
{indent_next2}except Exception as e:
{indent_next2}    _b().edit_message_text(f"❌ Error: {{e}}", chat_id=uid, message_id=load.message_id)
{indent_next}return

'''

# 5. Replace the lines
lines = lines[:start_idx] + [new_block] + lines[end_idx:]
new_content = "".join(lines)

try:
    ast.parse(new_content)
    open(path, "w").write(new_content)
    print("✅ UI updated perfectly. No syntax errors.")
except SyntaxError as e:
    print(f"❌ STILL BROKEN: {e}")
    print("The file was NOT saved.")
