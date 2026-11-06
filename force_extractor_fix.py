import ast

path = "extract_all.py"
content = open(path).read()

# Find where it starts checking pages and inject the missing page_texts loop
if "page_texts = {}" not in content:
    # Find the line that says "log(f"  🗺️ Mapping coords...")" or just before it
    marker = 'log(f"  🗺️ Mapping coords...")'
    if marker in content:
        fix_code = '''    page_texts = {}
    for page in range(1, total_pages + 1):
        try:
            page_texts[page] = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        except: page_texts[page] = ""

'''
        content = content.replace(marker, fix_code + marker)
        open(path, "w").write(content)
        print("✅ Extractor patched successfully.")
    else:
        # Fallback: find the exact line where q_coords is defined and put it above
        marker2 = "q_coords = {}"
        if marker2 in content:
            fix_code = '''    page_texts = {}
    for p_idx in range(1, total_pages + 1):
        try:
            page_texts[p_idx] = subprocess.run(["pdftotext", "-f", str(p_idx), "-l", str(p_idx), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        except: page_texts[p_idx] = ""
'''
            content = content.replace(marker2, fix_code + "\n    " + marker2, 1)
            open(path, "w").write(content)
            print("✅ Extractor patched via fallback.")
        else:
            print("⚠️ Could not find insertion point.")
else:
    print("✅ Extractor already has page_texts defined.")
