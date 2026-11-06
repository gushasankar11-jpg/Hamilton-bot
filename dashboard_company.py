import os, json, time
STATE_FILE = "data/company_state.json"

def clear():
    os.system('clear' if os.name == 'posix' else 'cls')

while True:
    clear()
    print("=" * 95)
    print(" 🏢 HAMILTON EXTRACTION CORP - LIVE WORKSPACE")
    print("=" * 95)
    
    if not os.path.exists(STATE_FILE):
        print("Waiting for company to start...")
        time.sleep(2)
        continue
        
    try:
        data = json.load(open(STATE_FILE))
    except:
        time.sleep(2)
        continue
        
    # Boss
    boss = data.get("Boss", {}).get("1", {})
    print(f"👑 BOSS  : {boss.get('status', 'Idle')} | {boss.get('error', '')}")
    
    # Manager
    mgr = data.get("Manager", {}).get("1", {})
    print(f"🕵️ MGR   : {mgr.get('status', 'Idle')} | Diag: {mgr.get('error', 'None')}")
    print("-" * 95)
    
    print(f"{'ID':<4} | {'ROLE':<8} | {'WORKER STATUS':<22} | {'PAGE':<10} | {'BOOK NAME'}")
    print("-" * 95)
    
    workers = data.get("Worker", {})
    for i in range(1, 9):
        w = workers.get(str(i), {"status": "💤 Idle", "book": "-", "page": 0, "pages_done": 0})
        stat = w.get("status", "Idle")
        book = w.get("book", "-")[:25]
        page = w.get("page", 0)
        done = w.get("pages_done", 0)
        
        if "✅" in stat: color = "\033[92m" # Green
        elif "❌" in stat: color = "\033[91m" # Red
        elif "Cropping" in stat: color = "\033[93m" # Yellow
        else: color = "\033[0m"
        
        print(f"{color}W{i:<3}\033[0m | Worker   | {color}{stat:<22}\033[0m | Pg {page:<3} ({done}) | {book}")
        
    print("=" * 95)
    print(" Press Ctrl+C to exit dashboard. (Company keeps working)")
    time.sleep(2)
