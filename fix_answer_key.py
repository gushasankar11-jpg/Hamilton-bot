import ast

path = "extract_all.py"
content = open(path).read()

# Add a strict skip for Answer Key pages
old_loop = '''    for page in range(1, total_pages + 1):
        try:
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        except: continue'''
new_loop = '''    for page in range(1, total_pages + 1):
        if "Answer Key" in page_texts[page] or "ANSWER KEY" in page_texts[page] or "Answer key" in page_texts[page]:
            continue # Skip cropping the answer key page entirely
        try:
            xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        except: continue'''
        
if old_loop in content:
    content = content.replace(old_loop, new_loop)
    open(path, "w").write(content)
    print("✅ Patched extract_all.py: Answer Key pages will be ignored.")
else:
    print("⚠️ Pattern not found. Checking if already patched.")
