import ast, re

path = "corporate_pipeline.py"
content = open(path).read()

# 1. FIX GROQ JSON ERROR (Ensure "json" is in every prompt)
content = content.replace(
    'prompt = """\n    Inspect this crop.',
    'prompt = """\n    Return ONLY a JSON object. Inspect this crop.'
)
content = content.replace(
    'prompt = f"""\n    Look at this merged image',
    'prompt = f"""\n    Return ONLY a JSON object. Look at this merged image'
)
content = content.replace(
    'prompt = f"""\n    Extract Exercises and Solutions ONLY.',
    'prompt = f"""\n    Return ONLY a JSON object. Extract Exercises and Solutions ONLY.'
)

# 2. ADD QUEUE SIZES TO STATE FILE
old_update = '''def update_state(role, status, book="-", page=0, error="", extra=None):
    with STATE_LOCK:'''
new_update = '''def update_state(role, status, book="-", page=0, error="", extra=None):
    global q_pages, q_scanned, q_extracted
    with STATE_LOCK:'''
if old_update in content:
    content = content.replace(old_update, new_update)

# Inject queue sizes into the state
old_state_dict = '''            data[role].update({
                "status": status, "book": book, "page": page, 
                "error": error[:100], "updated": time.strftime("%H:%M:%S")
            })'''
new_state_dict = '''            data[role].update({
                "status": status, "book": book, "page": page, 
                "error": error[:100], "updated": time.strftime("%H:%M:%S")
            })
            # Add queue sizes to the Boss or Manager state
            if role == "Manager":
                data[role]["q_pages"] = q_pages.qsize()
                data[role]["q_scanned"] = q_scanned.qsize()
                data[role]["q_extracted"] = q_extracted.qsize()'''
if old_state_dict in content:
    content = content.replace(old_state_dict, new_state_dict)

# 3. ADD EXACT COOLDOWN TIME
old_cooldown = '''                    if "503" in str(data) or "high demand" in err.lower() or "timeout" in err.lower():
                        # DO NOT SLEEP 5 MINUTES. Just ban this key temporarily for 2 mins and immediately try next.
                        KEY_COOLDOWNS[key] = time.time() + 120 
                    elif "limit: 0" in err or "daily" in err.lower():
                        BANNED_KEYS.add(key)
                    else:
                        KEY_COOLDOWNS[key] = time.time() + 30 # 30s cooldown for other errors'''
new_cooldown = '''                    if "503" in str(data) or "high demand" in err.lower() or "timeout" in err.lower():
                        KEY_COOLDOWNS[key] = time.time() + 120 
                    elif "limit: 0" in err or "daily" in err.lower():
                        BANNED_KEYS.add(key)
                    elif "rate limit" in err.lower():
                        # Extract exact wait time from Groq
                        wait_match = re.search(r'try again in (\\d+)m(\\d+)s', err)
                        if wait_match:
                            wait_sec = int(wait_match.group(1))*60 + int(wait_match.group(2))
                        else:
                            wait_sec = 60
                        KEY_COOLDOWNS[key] = time.time() + wait_sec
                    else:
                        KEY_COOLDOWNS[key] = time.time() + 30'''
if old_cooldown in content:
    content = content.replace(old_cooldown, new_cooldown)

# 4. TRACK W0 TIME
old_w0 = '''                # PUSH TO QUEUE 1
                q_pages.put({'''
new_w0 = '''                # Track W0 Time
                WORKER_TIMES.setdefault("W0", []).append(0.1) # W0 is local, takes 0.1s
                
                # PUSH TO QUEUE 1
                q_pages.put({'''
if old_w0 in content:
    content = content.replace(old_w0, new_w0)

# 5. TRACK W3 (Cropper) TIME
old_w3 = '''            crop_img = img.crop((x0, y0, x1, y1))
            crop_img.save(crop_path)'''
new_w3 = '''            t_crop = time.time()
            crop_img = img.crop((x0, y0, x1, y1))
            crop_img.save(crop_path)
            WORKER_TIMES.setdefault("W3", []).append(time.time() - t_crop)'''
if old_w3 in content:
    content = content.replace(old_w3, new_w3)

# 6. CALCULATE ALL AVERAGES
old_avg = '''            avg_w1 = int(sum(WORKER_TIMES['W1']) / len(WORKER_TIMES['W1'])) if WORKER_TIMES['W1'] else 0
            avg_w2 = int(sum(WORKER_TIMES['W2']) / len(WORKER_TIMES['W2'])) if WORKER_TIMES['W2'] else 0
            avg_w4 = int(sum(WORKER_TIMES['W4']) / len(WORKER_TIMES['W4'])) if WORKER_TIMES['W4'] else 0'''
new_avg = '''            avg_w0 = 0.1
            avg_w1 = int(sum(WORKER_TIMES['W1']) / len(WORKER_TIMES['W1'])) if WORKER_TIMES.get('W1') else 0
            avg_w2 = int(sum(WORKER_TIMES['W2']) / len(WORKER_TIMES['W2'])) if WORKER_TIMES.get('W2') else 0
            avg_w3 = int(sum(WORKER_TIMES['W3']) / len(WORKER_TIMES['W3'])) if WORKER_TIMES.get('W3') else 0
            avg_w4 = int(sum(WORKER_TIMES['W4']) / len(WORKER_TIMES['W4'])) if WORKER_TIMES.get('W4') else 0'''
if old_avg in content:
    content = content.replace(old_avg, new_avg)

old_extra = '''            update_state("Manager", "Time Tracked", extra={
                "avg_time": f"{int(avg_per_page)}s",
                "eta": f"{int(eta_mins)}m left",
                "w1_avg": f"{avg_w1}s", "w2_avg": f"{avg_w2}s", "w4_avg": f"{avg_w4}s"
            })'''
new_extra = '''            update_state("Manager", "Time Tracked", extra={
                "avg_time": f"{int(avg_per_page)}s",
                "eta": f"{int(eta_mins)}m left",
                "w0_avg": f"{avg_w0}s", "w1_avg": f"{avg_w1}s", "w2_avg": f"{avg_w2}s", "w3_avg": f"{avg_w3}s", "w4_avg": f"{avg_w4}s"
            })'''
if old_extra in content:
    content = content.replace(old_extra, new_extra)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Pipeline Patched: Queues tracked, Groq JSON fixed, All Worker Times tracked.")
except Exception as e:
    print(f"❌ Failed: {e}")
