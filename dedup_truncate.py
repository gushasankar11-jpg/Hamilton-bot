import ast, shutil, time, re

path = "bot_chunks/c04_exam.py"
backup = path + ".bak_" + str(int(time.time()))
shutil.copy(path, backup)
print(f"✅ Backup: {backup}")

content = open(path).read()
lines = content.split('\n')

# Find all clean_math defs
cm = [i for i, l in enumerate(lines) if l.strip() == 'def clean_math(text):']
print(f"Found 'def clean_math' at lines: {[x+1 for x in cm]}")

if len(cm) >= 2:
    cut = cm[1]  # Keep lines 0..cut-1 (block 1 only)
    print(f"Truncating at line {cut+1} (keeping lines 1-{cut})")
    
    kept = lines[:cut]
    kept.append('')
    kept.append('print("✅ c04_exam.py loaded (deduplicated)")')
    kept.append('')
    new_content = '\n'.join(kept)
    
    try:
        ast.parse(new_content)
        open(path, "w").write(new_content)
        print(f"✅ Truncated! File is now {len(kept)} lines")
        print("✅ Syntax OK")
    except SyntaxError as e:
        print(f"❌ Truncation broke syntax: {e}")
        print(f"Restoring from backup...")
        shutil.copy(backup, path)
        exit(1)
else:
    print("No duplicates found — file is already clean")
