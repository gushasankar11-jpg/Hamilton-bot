import ast

path = "corporate_pipeline.py"
content = open(path).read()

# 1. Fix W1 Scanner (Only look for exercises)
old_w1 = '''        prompt = f"""Return ONLY a JSON object. Merged image: Top Pg {p1}, Bottom Pg {p2}.
        Does it contain EXERCISES/SOLUTIONS? List question numbers starting on Pg {p1}.
        Return JSON: {{"extract": true, "expected_questions": [1, 2]}}"""'''
new_w1 = '''        prompt = f"""Return ONLY a JSON object. Merged image: Top Pg {p1}, Bottom Pg {p2}.
        Does it contain EXERCISE questions (MCQs/Numericals)? IGNORE Theory and Illustrations/Examples.
        List exercise question numbers starting on Pg {p1}.
        Return JSON: {{"extract": true, "expected_questions": [1, 2]}}"""'''
if old_w1 in content: content = content.replace(old_w1, new_w1)

# 2. Fix W2 Extractor (Only extract exercises, explicitly ignore illustrations)
old_w2 = '''        prompt = f"""Return ONLY a JSON object. ONLY extract questions STARTING on Pg {p1}.
        Return JSON: {{"chapter": "Name", "questions": [{{"q_num": 1, "box": [ymin, xmin, ymax, xmax]}}], "solutions": []}}"""'''
new_w2 = '''        prompt = f"""Return ONLY a JSON object. 
        ONLY extract EXERCISE QUESTIONS (e.g., Q1, Q2, Q3) starting on Pg {p1}.
        IGNORE ALL Theory, Examples, and Illustrations.
        Return JSON: {{"chapter": "Name", "questions": [{{"q_num": 1, "box": [ymin, xmin, ymax, xmax]}}], "solutions": []}}"""'''
if old_w2 in content: content = content.replace(old_w2, new_w2)

# 3. Fix W4 QA (Add the word JSON so Groq doesn't reject it)
old_w4 = '''            qa = manager_api_call('{"perfect": true}', crop_b64, "W4_QA")'''
new_w4 = '''            qa = manager_api_call('Return ONLY a JSON object: {"perfect": true}', crop_b64, "W4_QA")'''
if old_w4 in content: content = content.replace(old_w4, new_w4)

# Save the patched file
try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Pipeline patched successfully! Prompts are now strict.")
except SyntaxError as e:
    print(f"❌ Syntax Error: {e}")
