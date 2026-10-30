import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# Fix the db[subj][ch] -> db["practice"][subj][ch]
old = '''            print(f"[DEBUG] f_pyq_ch clicked: subj={subj} ch={ch}")
            db = None
            q_data = None
            for attempt in range(6):
                try:
                    with open("data/pyq_master.json") as f: db = json.load(f)
                    q_data = db[subj][ch]
                    print(f"[DEBUG] JSON OK (attempt {attempt+1})")
                    break
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON retry {attempt+1}: {e}")
                    import time as _t; _t.sleep(0.3)
                except KeyError as e:
                    _b().send_message(uid, f"❌ Chapter not in DB: {subj}/{ch}")
                    return
                except Exception as e:
                    _b().send_message(uid, f"❌ Load error: {e}")
                    print(f"[DEBUG] Load error: {e}")
                    return
            if q_data is None:
                _b().send_message(uid, "❌ Could not load (extractor busy). Try again in 2 sec.")
                return
'''

new = '''            print(f"[DEBUG] f_pyq_ch clicked: subj={subj} ch={ch}")
            q_data = None
            for attempt in range(6):
                try:
                    with open("data/pyq_master.json") as f: db = json.load(f)
                    q_data = db.get("practice", {}).get(subj, {}).get(ch)
                    if q_data is not None:
                        print(f"[DEBUG] JSON OK (attempt {attempt+1})")
                        break
                    else:
                        # Valid JSON, chapter really missing
                        _b().send_message(uid, f"❌ Chapter not in DB: {subj} / {ch}")
                        return
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON retry {attempt+1}: {e}")
                    import time as _t; _t.sleep(0.3)
                except Exception as e:
                    _b().send_message(uid, f"❌ Load error: {e}")
                    print(f"[DEBUG] Load error: {e}")
                    return
            if q_data is None:
                _b().send_message(uid, "❌ Could not load (extractor busy). Try again in 2 sec.")
                return
'''

if old in content:
    content = content.replace(old, new)
    print("✅ Fixed: db['practice'][subj][ch] access pattern")
else:
    print("⚠️ Debug block not found — trying direct access fix...")
    # Fallback: replace any remaining db[subj][ch] with safe access
    content = content.replace('db[subj][ch]', 'db.get("practice", {}).get(subj, {}).get(ch)')
    print("✅ Applied safe access fallback")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
