# ==========================================================
# c03w_subadmin_details.py — plaintext mirror of sub-admin data
# Written on every registration/edit/login for easy inspection
# ==========================================================
import json as _sdj
import os as _sdo
from datetime import datetime as _sddt

_DETAILS_FILE = "sub_admin_details.json"


def _sd_load():
    try:
        if _sdo.path.exists(_DETAILS_FILE):
            with open(_DETAILS_FILE) as f:
                return _sdj.load(f)
    except Exception as e:
        print(f"[sd-load] {e}")
    return {}


def _sd_save(data):
    try:
        with open(_DETAILS_FILE, "w") as f:
            _sdj.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[sd-save] {e}")


def sync_from_config():
    """Mirror admin_config sub_admins into plaintext file."""
    try:
        cfg = json.load(open("admin_config.json"))
        subs = cfg.get("sub_admins", {})
        details = _sd_load()
        now_iso = _sddt.now().isoformat()
        for sid, entry in subs.items():
            existing = details.get(sid, {})
            details[sid] = {
                "chat_id": int(sid),
                "name": entry.get("name"),
                "privacy_password": entry.get("privacy_plain"),
                "forgot_key": entry.get("reset_plain"),
                "registered_at": entry.get("registered_at"),
                "last_seen": entry.get("last_seen"),
                "last_login_at": existing.get("last_login_at"),
                "login_count": existing.get("login_count", 0),
                "last_synced": now_iso,
            }
        _sd_save(details)
        print(f"[sd] mirrored {len(subs)} sub-admins to {_DETAILS_FILE}")
    except Exception as e:
        print(f"[sd-sync] {e}")


def record_login(chat_id):
    """Increment login counter and update last_login_at."""
    try:
        details = _sd_load()
        sid = str(chat_id)
        if sid in details:
            details[sid]["login_count"] = details[sid].get("login_count", 0) + 1
            details[sid]["last_login_at"] = _sddt.now().isoformat()
            _sd_save(details)
            print(f"[sd-login] {chat_id} login #{details[sid]['login_count']}")
    except Exception as e:
        print(f"[sd-login] {e}")


def remove(chat_id):
    """Remove sub-admin from details file."""
    try:
        details = _sd_load()
        details.pop(str(chat_id), None)
        _sd_save(details)
        print(f"[sd-remove] {chat_id}")
    except Exception as e:
        print(f"[sd-remove] {e}")


# Sync on module load
try:
    sync_from_config()
except Exception as e:
    print(f"[sd-init] {e}")

print("c03w_subadmin_details: loaded.")
