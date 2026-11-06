import ast, re

path = "bot_chunks/c40_vision_ai.py"
content = open(path).read()

# Find the prompt in get_ai_solution
prompt_pattern = re.compile(r'prompt = f"""Solve this JEE Main question.*?"""', re.DOTALL)
new_prompt = '''prompt = f"""Solve this JEE Main question. 
CRITICAL INSTRUCTION: DO NOT use LaTeX (no $, no \\frac, no \\sqrt). 
Format the output beautifully using basic HTML tags (<b> for bold) and Unicode math symbols (π, √, ², ³, ⁻, ᵃ, ᵇ, ½, ¼).
Make it look exactly like a crystal-clear printed textbook solution.

Use EXACTLY this 5-part format:

<b>1. General Process</b>
[Clear step-by-step text]

<b>2. Shortcut</b>
[Fast trick]

<b>3. Guess & Predict</b>
[Elimination strategy]

<b>4. Skip Calculation</b>
[Approximation tricks]

<b>5. Formula</b>
[Core formula in Unicode]"""'''

content = prompt_pattern.sub(new_prompt, content)
open(path, "w").write(content)
print("✅ AI prompt updated to output HTML & Unicode.")
