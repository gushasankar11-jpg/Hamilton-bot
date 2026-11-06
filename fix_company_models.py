import ast

path = "corporate_pipeline.py"
content = open(path).read()

# 1. Update the Models
old_models = '''    gemini_models = ["gemini-2.5-pro", "gemini-3.1-flash-lite"]
    groq_model = "meta-llama/llama-4-scout-17b-16e-instruct"'''
new_models = '''    gemini_models = ["gemini-3.1-pro-preview", "gemini-3.1-flash-lite"]
    groq_model = "qwen/qwen3.8-27b"'''

if old_models in content:
    content = content.replace(old_models, new_models)
    print("✅ Models updated to Gemini 3.1 Pro and Groq Qwen.")

# 2. Fix the Manager's Sleeping Countdown
old_sleep = '''        update_state("Manager", "All Keys Exhausted. Waiting 30s.", error="Rate Limit")
        time.sleep(30)'''
new_sleep = '''        # Countdown timer so the dashboard updates live
        for remaining in range(30, 0, -1):
            update_state("Manager", f"All Keys Exhausted. Sleeping {remaining}s", error="Rate Limit")
            time.sleep(1)'''

if old_sleep in content:
    content = content.replace(old_sleep, new_sleep)
    print("✅ Manager countdown timer fixed.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ corporate_pipeline.py patched perfectly.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
