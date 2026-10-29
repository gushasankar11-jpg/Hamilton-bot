import ast

PATH = "process_pdfs.py"
content = open(PATH).read()

if '"-r", "100"' in content:
    content = content.replace('"-r", "100"', '"-r", "150"')
    try:
        ast.parse(content)
        open(PATH, "w").write(content)
        print("✅ process_pdfs.py patched to 150 DPI")
    except SyntaxError as e:
        print(f"❌ Syntax error: {e}")
else:
    print("⚠️ Already at 150 DPI or pattern not found.")
