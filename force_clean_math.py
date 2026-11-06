import re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Delete all existing clean_math functions
# This regex finds "def clean_math" and deletes until the next "def " or "@bot" or end of file.
pattern = re.compile(r'^def clean_math\(.*?(?=^def |^@bot|\Z)', re.MULTILINE | re.DOTALL)
content = pattern.sub('', content)

# 2. Define the bulletproof version
new_clean = '''def clean_math(text):
    if not text: return ""
    text = text.replace("$$", "").replace("$", "")
    text = re.sub(r'\\\\boxed\\{(.*?)\\}', r'\\1', text)
    text = re.sub(r'\\\\frac\\{(.*?)\\}\\{(.*?)\\}', r'(\\1)/(\\2)', text)
    text = re.sub(r'\\\\sqrt\\{(.*?)\\}', r'√(\\1)', text)
    symbols = {
        '\\\\alpha': 'α', '\\\\beta': 'β', '\\\\theta': 'θ', '\\\\pi': 'π',
        '\\\\times': '×', '\\\\cdot': '·', '\\\\pm': '±', '\\\\infty': '∞',
        '\\\\le': '≤', '\\\\ge': '≥', '\\\\ne': '≠', '\\\\to': '→',
        '\\\\vec': '', '\\\\hat': ''
    }
    for k, v in symbols.items():
        text = text.replace(k, v)
    supers = {'0':'⁰', '1':'¹', '2':'²', '3':'³', '4':'⁴', '5':'⁵', '6':'⁶', '7':'⁷', '8':'⁸', '9':'⁹', 'n':'ⁿ'}
    def rep_super(m):
        return ''.join(supers.get(c, c) for c in m.group(1))
    text = re.sub(r'\\^\\{?(\\d+|n)\\}?', rep_super, text)
    subs = {'0':'₀', '1':'₁', '2':'₂', '3':'₃', '4':'₄', '5':'₅', '6':'₆', '7':'₇', '8':'₈', '9':'₉', 'n':'ₙ'}
    def rep_sub(m):
        return ''.join(subs.get(c, c) for c in m.group(1))
    text = re.sub(r'\\_\\{?(\\d+|n)\\}?', rep_sub, text)
    text = re.sub(r'\\\\([a-zA-Z]+)', r'\\1', text)
    text = re.sub(r'\\*\\*(.*?)\\*\\*', r'<b>\\1</b>', text)
    text = re.sub(r'\\*(.*?)\\*', r'<i>\\1</i>', text)
    return text

'''

# 3. Insert it right after the imports
insert_pos = content.find("def _b():")
if insert_pos == -1:
    insert_pos = content.find("import sys")
    if insert_pos != -1:
        insert_pos = content.find("\n", insert_pos) + 1

content = content[:insert_pos] + new_clean + content[insert_pos:]
print("✅ All old clean_math functions deleted. Perfect version injected at the top.")

open(path, "w").write(content)
