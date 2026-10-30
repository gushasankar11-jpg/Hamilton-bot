import ast

path_exam = "bot_chunks/c04_exam.py"
content = open(path_exam).read()

old_diff = """    diff_num = q.get('difficulty', 5)
    if isinstance(diff_num, int):
        diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
        diff_str = f"{diff_num} ({diff_text})"
    else:
        diff_str = str(diff_num)"""

new_diff = """    diff_raw = q.get('difficulty', 5)
    try:
        diff_num = int(float(diff_raw)) # Handle cases where AI returns "8.0"
        diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
        diff_str = f"{diff_num}/10 ({diff_text})"
    except:
        diff_str = str(diff_raw)"""

if old_diff in content:
    content = content.replace(old_diff, new_diff)
    try:
        ast.parse(content)
        open(path_exam, "w").write(content)
        print("✅ Difficulty format changed to X/10 (Level).")
    except SyntaxError as e:
        print("❌ Syntax Error:", e)
else:
    print("⚠️ Pattern not found. Already patched?")
