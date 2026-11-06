import ast
path = "api_single_extractor.py"
content = open(path).read()

# Add resume check before starting the pages
old_start = '''    print(f"\\n📖 STARTING BOOK: {book_id}")
    try:
        with pdfplumber.open(pdf_path) as pdf_obj:
            total_pages = len(pdf_obj.pages)
            for page_num in range(1, total_pages + 1):'''
new_start = '''    print(f"\\n📖 STARTING BOOK: {book_id}")
    
    # RESUME CHECK
    done_file = os.path.join(out_book_dir, ".done")
    if os.path.exists(done_file):
        print(f" ⏭️ Skipped (Already fully extracted)")
        return
        
    try:
        with pdfplumber.open(pdf_path) as pdf_obj:
            total_pages = len(pdf_obj.pages)
            for page_num in range(1, total_pages + 1):'''

if old_start in content:
    content = content.replace(old_start, new_start)
    
    # Mark as done at the end of the book
    old_end = '''    except Exception as e:
        print(f"❌ Error: {e}")'''
    new_end = '''        # Mark as done
        with open(done_file, "w") as f: f.write("done")
    except Exception as e:
        print(f"❌ Error: {e}")'''
    content = content.replace(old_end, new_end)
    
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Extractor now resumes where it left off.")
else:
    print("⚠️ Could not patch extractor resume logic.")
