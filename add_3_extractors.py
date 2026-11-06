import ast

path = "corporate_pipeline.py"
content = open(path).read()

# 1. Change single W2 to 3 Extractors in run_pipeline
old_w2_start = '''    t_w2 = threading.Thread(target=w2_extractor, daemon=True)'''
new_w2_start = '''    extractors = [threading.Thread(target=w2_extractor, daemon=True) for _ in range(3)]'''

if old_w2_start in content:
    content = content.replace(old_w2_start, new_w2_start)

old_w2_join = '''    q_scanned.put(None); t_w2.join()'''
new_w2_join = '''    for _ in range(3): q_scanned.put(None)
    for e in extractors: e.join()'''

if old_w2_join in content:
    content = content.replace(old_w2_join, new_w2_join)

# 2. Fix the start sequence
old_start = '''    t_w0.start(); t_w1.start(); t_w2.start()'''
new_start = '''    t_w0.start(); t_w1.start()
    for e in extractors: e.start()'''

if old_start in content:
    content = content.replace(old_start, new_start)

# 3. Ensure State Updater is pushing Queue sizes correctly
old_state = '''                data["Manager"]["q_pages"] = q_pages.qsize()
                data["Manager"]["q_scanned"] = q_scanned.qsize()
                data["Manager"]["q_extracted"] = q_extracted.qsize()'''
new_state = '''                data["Manager"]["q_pages"] = q_pages.qsize()
                data["Manager"]["q_scanned"] = q_scanned.qsize()
                data["Manager"]["q_extracted"] = q_extracted.qsize()
                data["Manager"]["q_cropped"] = q_cropped.qsize()'''

if old_state in content:
    content = content.replace(old_state, new_state)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Patched: 3 Extractors added and Queue sizes fixed.")
except SyntaxError as e:
    print(f"❌ Syntax Error: {e}")
