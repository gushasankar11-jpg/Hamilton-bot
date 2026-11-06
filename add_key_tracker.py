import ast

# --- PATCH PIPELINE ---
path_corp = "corporate_pipeline.py"
content = open(path_corp).read()

# 1. Add Global Cooldown Dict
if "KEY_COOLDOWNS = {}" not in content:
    content = content.replace("BANNED_KEYS = set()", "BANNED_KEYS = set()\nKEY_COOLDOWNS = {}")

# 2. Extract wait time from error and store it
old_error = '''                err = data["error"]["message"]
                log_error(f"Key {k_idx+1} failed: {err}")
                update_state("Manager", "Error encountered", error=err)'''
                
new_error = '''                err = data["error"]["message"]
                log_error(f"Key {k_idx+1} failed: {err}")
                
                # Extract cooldown time (e.g., "14m19s", "17h13m", "30s")
                import re as _re
                wait_match = _re.search(r'(?:retry in|try again in|wait)\s+((?:\d+h)?(?:\s*\d+m)?(?:\s*\d+s)?)', err, _re.IGNORECASE)
                wait_sec = 0
                if wait_match:
                    time_str = wait_match.group(1).replace(" ", "")
                    h = _re.search(r'(\d+)h', time_str)
                    m = _re.search(r'(\d+)m', time_str)
                    s = _re.search(r'(\d+)s', time_str)
                    if h: wait_sec += int(h.group(1)) * 3600
                    if m: wait_sec += int(m.group(1)) * 60
                    if s: wait_sec += int(s.group(1))
                
                if wait_sec > 0:
                    KEY_COOLDOWNS[key] = time.time() + wait_sec
                    log_error(f"Key {k_idx+1} cooling down for {wait_sec}s")
                elif "limit: 0" in err or "daily" in err.lower():
                    BANNED_KEYS.add(key)
                    log_error(f"Key {k_idx+1} Banned (Daily Limit)")'''

if old_error in content:
    content = content.replace(old_error, new_error)

# 3. Skip keys currently in cooldown
old_loop = '''    for k_idx, key in enumerate(keys):
        if key in BANNED_KEYS: continue'''
new_loop = '''    for k_idx, key in enumerate(keys):
        if key in BANNED_KEYS: continue
        if time.time() < KEY_COOLDOWNS.get(key, 0): 
            continue # Skip if still cooling down'''

if old_loop in content:
    content = content.replace(old_loop, new_loop)

# 4. Send cooldowns to state file for dashboard
if '"key_cooldowns":' not in content:
    content = content.replace('if extra: data[role].update(extra)', 
                              'if extra: data[role].update(extra)\n        if role == "Manager": data[role]["key_cooldowns"] = KEY_COOLDOWNS')

try:
    ast.parse(content)
    open(path_corp, "w").write(content)
    print("✅ Patched Pipeline: Cooldown parsing added.")
except Exception as e:
    print(f"❌ Pipeline Patch Failed: {e}")

# --- PATCH DASHBOARD ---
path_dash = "dashboard_corporate.py"
content_dash = open(path_dash).read()

# Replace the dashboard with the new one that shows the Key Table
new_dash = '''import os, json, time
STATE_FILE = "data/company_state.json"
ERROR_LOG = "data/manager_errors.log"

def clear(): os.system('clear' if os.name == 'posix' else 'cls')

while True:
    clear()
    print("=" * 105)
    print(" 🏢 HAMILTON CORP - PIPELINE + KEY COOLDOWNS")
    print("=" * 105)
    
    if not os.path.exists(STATE_FILE):
        print("Waiting for Boss...")
        time.sleep(2)
        continue
        
    try:
        data = json.load(open(STATE_FILE))
    except:
        time.sleep(2)
        continue
        
    boss = data.get("Boss", {})
    mgr = data.get("Manager", {})
    
    print(f"👑 BOSS  : {boss.get('status','Idle')}")
    print(f"🕵️ MGR   : {mgr.get('status','Idle')} | Avg: {mgr.get('avg_time','-')} | ETA: {mgr.get('eta','-')}")
    print("-" * 105)
    
    # LIVE KEY STATUS TABLE
    print(" 🔑 API KEY STATUS")
    cooldowns = mgr.get("key_cooldowns", {})
    now = time.time()
    
    for i in range(1, 9):
        status = "🟢 Active"
        if i <= 4:
            # Assuming 4 Gemini, 4 Groq for display
            key_name = f"Gemini {i}"
        else:
            key_name = f"Groq {i-4}"
            
        # We don't have the actual key strings here, so we just display a generic summary
        # In a real scenario, we'd map the index to the key string.
        # For now, we check how many keys are cooling down.
        
    # Simple summary based on cooldown dict size
    cooling_count = sum(1 for k, v in cooldowns.items() if v > now)
    banned_count = len(cooldowns) - cooling_count # Rough estimate
    
    print(f"   Total Keys: 8 | 🟢 Active: {8 - cooling_count - banned_count} | 🟡 Cooling: {cooling_count} | 🔴 Banned: {banned_count}")
    
    # Show the exact cooldown timer for keys currently cooling
    for k, t in cooldowns.items():
        if t > now:
            rem = int(t - now)
            print(f"   ⏳ Key ending in ... {rem//60}m {rem%60}s (Key string: ...{k[-6:]})")
            
    print("-" * 105)
    print(f"{'ROLE':<18} | {'STATUS':<25} | {'PAGE':<8} | {'TIME'}")
    print("-" * 105)
    
    roles = ["W0_Preprocessor", "W1_Scanner", "W2_Extractor", "W4_QA", "W6_Inspector"]
    for r in roles:
        w = data.get(r, {})
        stat = w.get('status', '💤 Idle')
        page = w.get('page', 0)
        t = w.get('time_per_page', '-')
        
        if "✅" in stat or "Done" in stat: color = "\\033[92m"
        elif "⏭️" in stat: color = "\\033[93m"
        elif "❌" in stat: color = "\\033[91m"
        else: color = "\\033[0m"
        
        print(f"{color}{r:<18}\\033[0m | {color}{stat:<25}\\033[0m | Pg {page:<5} | {t}")
        
    print("=" * 105)
    time.sleep(2)
'''
open(path_dash, "w").write(new_dash)
print("✅ Patched Dashboard: Added Key Cooldown Table.")
