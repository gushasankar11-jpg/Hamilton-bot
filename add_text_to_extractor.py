path = "perfect_extractor.py"
content = open(path).read()

old = '''                q_obj = {
                    "q_num": q_num,
                    "type": ans_data["type"],
                    "correct_index": ans_data.get("correct_index", -1),
                    "ideal_time": ideal,
                    "difficulty": diff_num,
                    "source": f"JEE Main {year}" if year > 0 else "JEE Main",
                    "subtopic": chapter_name,
                    "explanation": "💡 (Click 'Doubt in Explanation' to generate 5-part AI solution)",
                    "img": q_filename
                }'''

new = '''                q_obj = {
                    "q_num": q_num,
                    "type": ans_data["type"],
                    "correct_index": ans_data.get("correct_index", -1),
                    "ideal_time": ideal,
                    "difficulty": diff_num,
                    "source": f"JEE Main {year}" if year > 0 else "JEE Main",
                    "subtopic": chapter_name,
                    "q_text": q_text[:1500],
                    "explanation": "💡 (Click 'Doubt' for AI 5-part solution)",
                    "img": q_filename
                }'''

if old in content:
    content = content.replace(old, new)
    open(path, "w").write(content)
    print("✅ Extractor now saves q_text")
else:
    print("⚠️ Pattern not found")
