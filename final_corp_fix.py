import ast, json, os, glob

# --- 1. PATCH PIPELINE ---
path_corp = "corporate_pipeline.py"
content = open(path_corp).read()

# Fix ETA and Time Tracking
content = content.replace(
    "TOTAL_PAGES_PROCESSED = 0\nBANNED_KEYS = set()",
    "TOTAL_PAGES_PROCESSED = 0\nBANNED_KEYS = set()\nWORKER_TIMES = {\"W1\": [], \"W2\": [], \"W4\": [], \"W5\": []}\nTOTAL_BOOK_PAGES = 0"
)

# Add page counting at start
content = content.replace(
    "pdfs = glob.glob(f\"{BOOKS_DIR}/**/*.pdf\", recursive=True)",
    "pdfs = glob.glob(f\"{BOOKS_DIR}/**/*.pdf\", recursive=True)\n    global TOTAL_BOOK_PAGES\n    for p in pdfs:\n        try:\n            with pdfplumber.open(p) as _p: TOTAL_BOOK_PAGES += len(_p.pages)\n        except: pass"
)

# Wrap W1 Time
content = content.replace(
    "scan = w1_scanner(img_b64, p1, p2)",
    "t_w1 = time.time()\n            scan = w1_scanner(img_b64, p1, p2)\n            WORKER_TIMES['W1'].append(time.time() - t_w1)"
)

# Wrap W2 Time
content = content.replace(
    "boxes = w2_extractor(img_b64, p1, p2)",
    "t_w2 = time.time()\n            boxes = w2_extractor(img_b64, p1, p2)\n            WORKER_TIMES['W2'].append(time.time() - t_w2)"
)

# Wrap W4 Time
content = content.replace(
    "qa = w4_qa_check(crop_b64)",
    "t_w4 = time.time()\n                    qa = w4_qa_check(crop_b64)\n                    WORKER_TIMES['W4'].append(time.time() - t_w4)"
)

# Fix ETA Calculation block
old_eta = '''            # TIME CALCULATION
            t_end = time.time()
            elapsed = t_end - t_start
            TOTAL_PAGES_PROCESSED += 1
            
            avg_time = (t_end - GLOBAL_START_TIME) / TOTAL_PAGES_PROCESSED
            total_pages_all_books = 2000 # estimate
            pages_left = total_pages_all_books - TOTAL_PAGES_PROCESSED
            eta_mins = (pages_left * avg_time) / 60
            
            update_state("Manager", "Time Tracked", extra={
                "time_per_page": f"{int(elapsed)}s",
                "avg_time": f"{int(avg_time)}s",
                "eta": f"{int(eta_mins)}m left",
                "restart_wait": "0s"
            })'''

new_eta = '''            # TIME CALCULATION (Accurate)
            t_end = time.time()
            elapsed = t_end - t_start
            TOTAL_PAGES_PROCESSED += 1
            
            # Calculate true average time based ONLY on active processing (not sleep time)
            active_processing_time = sum([sum(v) for v in WORKER_TIMES.values()])
            avg_time_per_page = active_processing_time / TOTAL_PAGES_PROCESSED if TOTAL_PAGES_PROCESSED > 0 else 0
            
            pages_left = TOTAL_BOOK_PAGES - TOTAL_PAGES_PROCESSED
            eta_mins = (pages_left * avg_time_per_page) / 60 if pages_left > 0 else 0
            
            avg_w1 = int(sum(WORKER_TIMES['W1']) / len(WORKER_TIMES['W1'])) if WORKER_TIMES['W1'] else 0
            avg_w2 = int(sum(WORKER_TIMES['W2']) / len(WORKER_TIMES['W2'])) if WORKER_TIMES['W2'] else 0
            avg_w4 = int(sum(WORKER_TIMES['W4']) / len(WORKER_TIMES['W4'])) if WORKER_TIMES['W4'] else 0
            
            update_state("Manager", "Time Tracked", extra={
                "time_per_page": f"{int(elapsed)}s",
                "avg_time": f"{int(avg_time_per_page)}s",
                "eta": f"{int(eta_mins)}m left",
                "w1_avg": f"{avg_w1}s",
                "w2_avg": f"{avg_w2}s",
                "w4_avg": f"{avg_w4}s"
            })'''

if old_eta in content:
    content = content.replace(old_eta, new_eta)
else:
    print("⚠️ Could not find ETA block. The replace string might have slight differences.")

try:
    ast.parse(content)
    open(path_corp, "w").write(content)
    print("✅ Pipeline Patched: Worker Times and ETA fixed.")
except Exception as e:
    print(f"❌ Pipeline Patch Failed: {e}")


# --- 2. PATCH DASHBOARD ---
path_dash = "dashboard_corporate.py"
new_dash = '''import os, json, time
STATE_FILE = "data/company_state.json"
ERROR_LOG = "data/manager_errors.log"

def clear(): os.system('clear' if os.name == 'posix' else 'cls')

while True:
    clear()
    print("=" * 105)
    print(" 🏢 HAMILTON CORP - FULL DASHBOARD")
    print("=" * 105)
    
    if not os.path.exists(STATE_FILE):
        print("Waiting for Boss...")
        time.sleep(2)
        continue
        
    try: data = json.load(open(STATE_FILE))
    except: time.sleep(2); continue
        
    boss = data.get("Boss", {})
    mgr = data.get("Manager", {})
    
    print(f"👑 BOSS  : {boss.get('status','Idle')}")
    print(f"🕵️ MGR   : {mgr.get('status','Idle')} | Total Avg: {mgr.get('avg_time','-')} | ETA: {mgr.get('eta','-')}")
    print("-" * 105)
    
    # WORKER AVERAGE TIMES
    print(" ⏱️ WORKER AVERAGE TIMES (Who is slow?)")
    print(f"   W1 Scanner: {mgr.get('w1_avg','-')} | W2 Extractor: {mgr.get('w2_avg','-')} | W4 QA: {mgr.get('w4_avg','-')}")
    print("-" * 105)

    # LIVE KEY STATUS
    print(" 🔑 API KEY STATUS")
    cooldowns = mgr.get("key_cooldowns", {})
    now = time.time()
    cooling_count = sum(1 for k, v in cooldowns.items() if v > now)
    banned_count = len(cooldowns) - cooling_count
    
    print(f"   Total Keys: 8 | 🟢 Active: {8 - cooling_count - banned_count} | 🟡 Cooling: {cooling_count} | 🔴 Banned: {banned_count}")
    for k, t in cooldowns.items():
        if t > now:
            rem = int(t - now)
            print(f"   ⏳ Key ending in ... {rem//60}m {rem%60}s (Key string: ...{k[-6:]})")
            
    print("-" * 105)
    print(f"{'ROLE':<18} | {'STATUS':<25} | {'PAGE':<8} | {'TIME'}")
    print("-" * 105)
    
    roles = ["W0_Preprocessor [Python]", "W1_Scanner", "W2_Extractor", "W4_QA", "W6_Inspector"]
    role_keys = ["W0_Preprocessor", "W1_Scanner", "W2_Extractor", "W4_QA", "W6_Inspector"]
    
    for i, r in enumerate(roles):
        w = data.get(role_keys[i], {})
        stat = w.get('status', '💤 Idle')
        page = w.get('page', 0)
        t = w.get('time_per_page', '-')
        
        if "✅" in stat or "Done" in stat: color = "\\033[92m"
        elif "⏭️" in stat: color = "\\033[93m"
        elif "❌" in stat: color = "\\033[91m"
        else: color = "\\033[0m"
        
        print(f"{color}{r:<25}\\033[0m | {color}{stat:<25}\\033[0m | Pg {page:<5} | {t}")
        
    print("=" * 105)
    print(" [ MANAGER ERROR LOG - LAST 3 ] ")
    if os.path.exists(ERROR_LOG):
        with open(ERROR_LOG, "r") as f:
            lines = f.readlines()[-3:]
            for line in lines: print("  " + line.strip())
    else:
        print("  No errors.")
            
    print("=" * 105)
    time.sleep(2)
'''
open(path_dash, "w").write(new_dash)
print("✅ Dashboard Patched: Error log restored, Worker Times added.")
