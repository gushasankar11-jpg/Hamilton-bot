import ast

path = "corporate_pipeline.py"
content = open(path).read()

# The old logic that was failing
old_logic = '''                # Chapter Extraction
                chapter = "Unknown"
                for line in page_text.split('\\n')[:10]:
                    line = line.strip()
                    if len(line) > 5 and not line.isdigit() and "downloaded" not in line.lower() and "jeemain" not in line.lower():
                        if line.isupper() or len(line) > 10:
                            chapter = line[:25]
                            break'''

# The new smart logic
new_logic = '''                # Chapter Extraction (Smart)
                chapter = "Unknown"
                lines = [l.strip() for l in page_text.split('\\n') if l.strip()]
                
                # 1. Try to get it from the running header (Top of page)
                if lines:
                    header_line = lines[0]
                    # Ignore page numbers like "1.7", "Page 12", or watermarks
                    if not re.match(r'^\\d+\\.\\d+', header_line) and "downloaded" not in header_line.lower() and "jeemain" not in header_line.lower():
                        # Remove numbers at the end of the line (like "1.7")
                        clean_header = re.sub(r'\\s+\\d+\\.\\d+$', '', header_line).strip()
                        if len(clean_header) > 3:
                            chapter = clean_header[:25]
                            
                # 2. If header fails, try the filename
                if chapter == "Unknown":
                    fn = os.path.basename(pdf_path).replace(".pdf", "").replace(".PDF", "")
                    fn = fn.replace("Cengage", "").replace("JEE Main", "").replace("JEE Adv", "").replace("Previous Year Questions", "").strip()
                    if len(fn) > 3:
                        chapter = fn[:25]

                # Clean up the final chapter name
                chapter = re.sub(r'[^a-zA-Z0-9\\s]', '', chapter).strip()
                if not chapter: chapter = "Unknown"'''

if old_logic in content:
    content = content.replace(old_logic, new_logic)
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ Patched: Chapter extraction is now 10x smarter.")
    except SyntaxError as e:
        print(f"❌ Syntax Error: {e}")
else:
    print("⚠️ Could not find the old logic block. The file might already be patched.")
