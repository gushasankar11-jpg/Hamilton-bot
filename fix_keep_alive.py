import ast

path = "corporate_pipeline.py"
content = open(path).read()

# 1. Fix W0 preprocessor crashing on bad PDFs
old_w0 = '''        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            for page_num in range(1, total_pages):
                p1, p2 = page_num, min(page_num + 1, total_pages)
                
                page = pdf.pages[p1 - 1]
                page_text = page.extract_text() or ""'''

new_w0 = '''        try:
            pdf = pdfplumber.open(pdf_path)
            total_pages = len(pdf.pages)
        except Exception as e:
            log_error(f"W0 Error: Cannot open {book_name} - {e}")
            continue
            
        with pdf:
            for page_num in range(1, total_pages):
                p1, p2 = page_num, min(page_num + 1, total_pages)
                
                page = pdf.pages[p1 - 1]
                page_text = page.extract_text() or ""'''

if old_w0 in content:
    content = content.replace(old_w0, new_w0)
    print("✅ W0 secured against bad PDFs.")

# 2. Add Infinite Loop at the end of run_pipeline so it doesn't exit
old_run = '''    t_w0.start(); t_w1.start()
    for e in extractors: e.start()
    for c in croppers: c.start()
    t_w4.start()

if __name__ == "__main__":
    run_pipeline()'''

new_run = '''    t_w0.start(); t_w1.start()
    for e in extractors: e.start()
    for c in croppers: c.start()
    t_w4.start()
    
    # KEEP THE MAIN THREAD ALIVE FOREVER
    while True:
        time.sleep(1)

if __name__ == "__main__":
    run_pipeline()'''

if old_run in content:
    content = content.replace(old_run, new_run)
    print("✅ Main thread keep-alive added. The script will not exit.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Pipeline Patched successfully.")
except SyntaxError as e:
    print(f"❌ Syntax Error: {e}")
