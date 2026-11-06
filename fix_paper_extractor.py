path = "extract_all.py"
content = open(path).read()

# We will inject the page_texts definition right before it's used.
# Find the line where it starts mapping coordinates
marker = '    log(f"  🗺️ Mapping coords...")'
if marker in content:
    # Insert the text extraction loop before mapping
    fix_code = '''    page_texts = {}
    for page in range(1, total_pages + 1):
        try:
            page_texts[page] = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
        except: page_texts[page] = ""

'''
    content = content.replace(marker, fix_code + marker)
    open(path, "w").write(content)
    print("✅ Fixed: Added missing page_texts definition.")
else:
    print("⚠️ Could not find mapping marker. The script might already be fixed.")
