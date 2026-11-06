path = "ai_engine_final.py"
content = open(path).read()

old_func = '''def ask_ai_group(blocks_text):
    prompt = f"""
    You are an expert educational content analyzer.
    Group the blocks into distinct items using these STRICT rules:
    1. "theory": Conceptual text, paragraphs, formulas, and definitions.
    2. "illustration": The example/illustration header (e.g. "Example 1.1") AND the complete question AND its full solution. Group all three together.
    3. "exercise": The exercise header AND individual questions (Q1, Q2, Q3) separately.
    
    Return ONLY JSON:
    {{
      "items": [
        {{"type": "theory", "start_id": 1, "end_id": 15}},
        {{"type": "illustration", "start_id": 16, "end_id": 25}},
        {{"type": "exercise", "start_id": 26, "end_id": 28}}
      ]
    }}
    Blocks:
    {blocks_text}
    """
    try:
        res = ai_client._route_call("You are a JSON API.", prompt)
        res = res.replace("```json", "").replace("```", "").strip()
        return json.loads(res)
    except: return None'''

new_func = '''def ask_ai_group(blocks_text):
    prompt = f"""
    You are an expert educational content analyzer.
    Group the blocks into distinct items using these STRICT rules:
    1. "theory": Conceptual text, paragraphs, formulas, and definitions.
    2. "illustration": The example/illustration header (e.g. "Example 1.1") AND the complete question AND its full solution. Group all three together.
    3. "exercise": The exercise header AND individual questions (Q1, Q2, Q3) separately.
    
    Return ONLY JSON:
    {{
      "items": [
        {{"type": "theory", "start_id": 1, "end_id": 15}},
        {{"type": "illustration", "start_id": 16, "end_id": 25}},
        {{"type": "exercise", "start_id": 26, "end_id": 28}}
      ]
    }}
    Blocks:
    {blocks_text}
    """
    try:
        res = ai_client._route_call("You are a JSON API. Output ONLY a valid JSON object.", prompt)
        # Bulletproof extraction (finds JSON even if AI adds text around it)
        match = re.search(r'\\{.*\\}', res, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        print(f"⚠️ AI returned invalid JSON format: {res[:100]}...")
        return None
    except Exception as e:
        print(f"⚠️ AI Grouping Error: {e}")
        return None'''

if old_func in content:
    content = content.replace(old_func, new_func)
    open(path, "w").write(content)
    print("✅ Patched ai_engine_final.py with bulletproof parsing.")
else:
    print("⚠️ Could not find ask_ai_group. Are you sure the file exists?")
