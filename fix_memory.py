path = "extract_books_fast.py"
content = open(path).read()

# Add garbage collection import
if "import gc" not in content:
    content = content.replace("import os, subprocess, json, re, time", "import os, subprocess, json, re, time, gc")

# Add gc.collect() at the end of the page loop
if "gc.collect()" not in content:
    content = content.replace(
        'img_ocr.close()\n            os.remove(img_ocr_path)',
        'img_ocr.close()\n            os.remove(img_ocr_path)\n            gc.collect() # Free RAM'
    )

open(path, "w").write(content)
print("✅ Memory leak fix applied.")
