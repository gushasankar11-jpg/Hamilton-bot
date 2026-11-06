import os, json, time
STATUS_FILE = "data/worker_status.json"
BOOKS_DIR = "pyq_images/books"

def clear(): os.system('clear' if os.name == 'posix' else 'cls')

def get_totals():
    t = i = e = s = 0
    if not os.path.exists(BOOKS_DIR): return 0, 0, 0, 0
    for root, dirs, files in os.walk(BOOKS_DIR):
        folder = os.path.basename(root)
        count = len([f for f in files if f.endswith('.png')])
        if folder == "theory": t += count
        elif folder == "illustration": i += count
        elif folder == "exercise": e += count
        elif folder == "solution": s += count
    return t, i, e, s

while True:
    clear()
    print("=" * 65)
    print(" 🧠 HAMILTON EXTRACTOR - LIVE STATUS & TOTALS")
    print("=" * 65)
    print(" [ CURRENT TASK ]")
    if not os.path.exists(STATUS_FILE):
        print("   Waiting...")
    else:
        try:
            data = json.load(open(STATUS_FILE))
            print(f"   API USED : {data.get('status', 'Idle')}")
            print(f"   BOOK     : {data.get('book', '-')}")
            print(f"   PAGE     : {data.get('page', 0)} | PAGE ITEMS: {data.get('items', 0)}")
        except: pass
    print("-" * 65)
    t, i, e, s = get_totals()
    print(f"   📘 Theory       : {t:,}")
    print(f"   💡 Illustrations: {i:,}")
    print(f"   📝 Exercises    : {e:,}")
    print(f"   ✅ Solutions    : {s:,}")
    print(f"   ------------------------------")
    print(f"   📦 TOTAL IMAGES : {t+i+e+s:,}")
    print("=" * 65)
    print(" Press Ctrl+C to exit.")
    time.sleep(2)
