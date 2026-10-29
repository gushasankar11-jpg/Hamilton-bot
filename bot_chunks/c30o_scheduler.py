# ==========================================================
# c30o_scheduler.py — Background scheduler for broadcasts
# ==========================================================
import json, os, time, threading
from datetime import datetime


SCHEDULE_FILE = "scheduled_broadcasts.json"


def _load_schedule():
    if not os.path.exists(SCHEDULE_FILE):
        return []
    try:
        with open(SCHEDULE_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_schedule(items):
    tmp = SCHEDULE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(items, f, indent=2)
    os.replace(tmp, SCHEDULE_FILE)


def _send_scheduled_broadcast(item):
    """Send one scheduled broadcast and mark as sent."""
    text = item.get("text", "")
    recipients = item.get("recipients", [])
    sent = 0
    file_type = item.get("file_type")
    file_id = item.get("file_id")
    
    for uid in recipients:
        try:
            if file_type and file_id:
                cap = text if text else ""
                if file_type == "photo":
                    bot.send_photo(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "video":
                    bot.send_video(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "audio":
                    bot.send_audio(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "document":
                    bot.send_document(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "voice":
                    bot.send_voice(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "video_note":
                    bot.send_video_note(uid, file_id)
            else:
                safe_send(uid,
                    f"📢 <b>ANNOUNCEMENT FROM ADMIN</b>\n\n{text}\n\n<i>— Admin</i>",
                    parse_mode="HTML")
            sent += 1
            time.sleep(0.05)
        except Exception as e:
            pass
    try:
        import admin_auth
        admin_auth.log_broadcast(text, sent, item.get("scheduled_at"))
    except Exception:
        pass
    print(f"[sched] broadcast sent to {sent}/{len(recipients)}")


def _parse_scheduled_time(scheduled_at):
    """Parse scheduled time. Handles 24h AND 12h AM/PM formats."""
    if not scheduled_at:
        return None
    scheduled_at = scheduled_at.strip()
    for fmt in ("%Y-%m-%d %H:%M",
                "%Y-%m-%d %I:%M %p",
                "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(scheduled_at, fmt)
        except ValueError:
            continue
    print(f"[sched] UNPARSEABLE: {scheduled_at!r}")
    return None


def _scheduler_loop():
    """Check every 20 seconds for due broadcasts."""
    print("[sched] background scheduler started")
    while True:
        try:
            items = _load_schedule()
            now = datetime.now()
            changed = False
            for item in items:
                if item.get("sent"):
                    continue
                scheduled_dt = _parse_scheduled_time(item.get("scheduled_at", ""))
                if not scheduled_dt:
                    continue
                if now >= scheduled_dt:
                    print(f"[sched] firing broadcast: {item.get('scheduled_at')}")
                    try:
                        _send_scheduled_broadcast(item)
                    except Exception as e:
                        print(f"[sched] send error: {e}")
                    item["sent"] = True
                    item["sent_at"] = now.isoformat()
                    changed = True
            if changed:
                _save_schedule(items)
        except Exception as e:
            print(f"[sched] loop error: {e}")
        time.sleep(20)


def start_scheduler():
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()
    return t


# Auto-start when loaded
start_scheduler()
print("c30o_scheduler: loaded + scheduler running.")
