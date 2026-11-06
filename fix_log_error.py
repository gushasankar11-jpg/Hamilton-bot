path = "extract_books_universal.py"
content = open(path).read()

# Replace the log() call that has end="\r" with a standard print()
content = content.replace(
    'log(f"    Page {page}/{total_pages} extracted...", end="\\r")',
    'print(f"    Page {page}/{total_pages} extracted...", end="\\r", flush=True)'
)

open(path, "w").write(content)
print("✅ Fixed log() TypeError.")
