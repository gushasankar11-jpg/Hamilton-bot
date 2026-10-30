import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Add JSON retry logic to f_pyq_ch
old = '''            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                q_data = db[subj][ch]
            except Exception as e:
                _b().answer_callback_query(call.id, f"❌ Error loading DB: {e}", show_alert=True)
                return
'''
new = '''            print(f"[DEBUG] f_pyq_ch clicked: subj={subj} ch={ch}")
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
if old in content:
    content = content.replace(old, new)
    print("✅ f_pyq_ch: JSON retry + debug added")
else:
    print("⚠️ f_pyq_ch pattern NOT found — will inspect next")

# 2. Add debug to send_pyq_q entry
old_send = '''def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
'''
new_send = '''def send_pyq_q(uid, msg_id=None):
    print(f"[DEBUG] send_pyq_q: uid={uid}")
    state = _state[uid]
    print(f"[DEBUG] state: mode={state.get('mode')} idx={state.get('pyq_index')} len={len(state.get('pyq_questions', []))}")
    if state.get("mode") != "pyq":
        print(f"[DEBUG] ABORT: mode={state.get('mode')}")
        return
'''
if old_send in content:
    content = content.replace(old_send, new_send)
    print("✅ send_pyq_q: entry debug added")

# 3. Wrap send_photo with detailed prints
old_photo = '''    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
            state["pyq_msg_id"] = msg.message_id
    except Exception as e:
        _b().send_message(uid, f"❌ Failed to send photo: {e}\\nPath: {q['img']}")
'''
new_photo = '''    print(f"[DEBUG] Attempting send_photo: {q['img']}")
    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
            state["pyq_msg_id"] = msg.message_id
        print(f"[DEBUG] send_photo SUCCESS, msg_id={msg.message_id}")
    except Exception as e:
        print(f"[DEBUG] send_photo FAILED: {e}")
        try:
            _b().send_message(uid, f"❌ Failed to send photo: {e}\\nPath: {q['img']}")
        except Exception as e2:
            print(f"[DEBUG] Even fallback failed: {e2}")
'''
if old_photo in content:
    content = content.replace(old_photo, new_photo)
    print("✅ send_photo: detailed debug added")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
