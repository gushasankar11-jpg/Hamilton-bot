import ast

path = "corporate_pipeline.py"
content = open(path).read()

# Replace the entire state_updater function with the flawless one
old_updater_start = content.find("def state_updater():")
old_updater_end = content.find("def update_state(", old_updater_start)

if old_updater_start != -1 and old_updater_end != -1:
    new_updater = '''def state_updater():
    global TOTAL_PAGES_PROCESSED
    while True:
        with STATE_LOCK:
            with open(STATE_FILE + ".lock", "w") as lockfile:
                fcntl.flock(lockfile, fcntl.LOCK_EX)
                data = {}
                if os.path.exists(STATE_FILE):
                    try: data = json.load(open(STATE_FILE))
                    except: pass
                
                if "Manager" not in data: data["Manager"] = {}
                
                # 1. Live Queue Sizes
                data["Manager"]["q_pages"] = q_pages.qsize()
                data["Manager"]["q_scanned"] = q_scanned.qsize()
                data["Manager"]["q_extracted"] = q_extracted.qsize()
                
                # 2. Live Average Times
                for w in WORKER_TIMES:
                    if WORKER_TIMES[w]:
                        data["Manager"][f"{w.lower()}_avg"] = f"{int(sum(WORKER_TIMES[w]) / len(WORKER_TIMES[w]))}s"
                    else:
                        data["Manager"][f"{w.lower()}_avg"] = "-"
                
                # 3. ETA and Total Avg Time per Image
                active_time = sum([sum(v) for v in WORKER_TIMES.values()])
                avg_per_page = active_time / TOTAL_PAGES_PROCESSED if TOTAL_PAGES_PROCESSED > 0 else 0
                pages_left = TOTAL_BOOK_PAGES - TOTAL_PAGES_PROCESSED
                eta_mins = (pages_left * avg_per_page) / 60 if pages_left > 0 else 0
                
                data["Manager"]["avg_time"] = f"{int(avg_per_page)}s"
                data["Manager"]["eta"] = f"{int(eta_mins)}m left"
                data["Manager"]["total_active"] = f"{int(active_time)}s"
                
                # 4. Cooldowns & Bans
                data["Manager"]["key_cooldowns"] = KEY_COOLDOWNS
                data["Manager"]["banned_keys"] = BANNED_KEYS
                
                tmp = STATE_FILE + ".tmp"
                json.dump(data, open(tmp, "w"), indent=2)
                os.replace(tmp, STATE_FILE)
                fcntl.flock(lockfile, fcntl.LOCK_UN)
        time.sleep(1)

'''
    content = content[:old_updater_start] + new_updater + content[old_updater_end:]
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ Pipeline State Updater patched. Sending all live data.")
    except Exception as e:
        print(f"❌ Patch Failed: {e}")
else:
    print("⚠️ Could not find state_updater function.")
