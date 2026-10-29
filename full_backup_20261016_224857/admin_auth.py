# ==========================================================
# admin_auth.py — Authentication, sessions, rate-limits, audit
# Storage: admin_config.json (admins), admin_audit.log (events)
# ==========================================================
import os, json, time, hashlib, secrets
from datetime import datetime, timedelta

import config

# ----------------------------------------------------------
# Hashing (PBKDF2-HMAC-SHA256, 200k iterations, per-user salt)
# ----------------------------------------------------------
PBKDF2_ITERATIONS = 200_000

def _hash_secret(secret: str, salt_hex: str = None):
    """Returns (hash_hex, salt_hex). If salt_hex given, reuses it."""
    if salt_hex is None:
        salt = secrets.token_bytes(32)
        salt_hex = salt.hex()
    else:
        salt = bytes.fromhex(salt_hex)
    h = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return h.hex(), salt_hex

def verify_secret(secret: str, hash_hex: str, salt_hex: str) -> bool:
    try:
        computed, _ = _hash_secret(secret, salt_hex)
        return secrets.compare_digest(computed, hash_hex)
    except Exception:
        return False

# ----------------------------------------------------------
# Admin config (persisted JSON)
# ----------------------------------------------------------
def _load_config() -> dict:
    path = config.ADMIN_CONFIG_FILE
    if not os.path.exists(path):
        return {"primary": None, "sub_admins": {}}
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        return {"primary": None, "sub_admins": {}}
    data.setdefault("primary", None)
    data.setdefault("sub_admins", {})
    return data

def _save_config(data: dict):
    path = config.ADMIN_CONFIG_FILE
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

# ----------------------------------------------------------
# Primary admin bootstrap (first-run only)
# ----------------------------------------------------------
def ensure_primary_admin_bootstrapped():
    """Idempotent. Hashes config's ADMIN_PRIVACY_CODE + ADMIN_RESET_KEY once."""
    cfg = _load_config()
    if cfg["primary"] is not None:
        return
    ph, psalt = _hash_secret(config.ADMIN_PRIVACY_CODE)
    rh, rsalt = _hash_secret(config.ADMIN_RESET_KEY)
    cfg["primary"] = {
        "chat_id": None,
        "name": config.ADMIN_NAME,
        "privacy_hash": ph,
        "privacy_salt": psalt,
        "reset_hash": rh,
        "reset_salt": rsalt,
        "created_at": datetime.now().isoformat(),
        "failed_attempts": 0,
        "locked_until": None,
    }
    _save_config(cfg)

# ----------------------------------------------------------
# Sub-admin registry
# ----------------------------------------------------------
def is_sub_admin_registered(chat_id: int) -> bool:
    cfg = _load_config()
    return str(chat_id) in cfg["sub_admins"]

def register_sub_admin(chat_id: int, name: str, privacy_code: str) -> bool:
    cfg = _load_config()
    ph, psalt = _hash_secret(privacy_code)
    cfg["sub_admins"][str(chat_id)] = {
        "name": name,
        "privacy_hash": ph,
        "privacy_salt": psalt,
        "registered_at": datetime.now().isoformat(),
        "first_seen": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat(),
        "failed_attempts": 0,
        "locked_until": None,
    }
    _save_config(cfg)
    audit("sub_admin_registered", chat_id, {"name": name})
    return True

def verify_sub_admin_privacy(chat_id: int, code: str) -> bool:
    cfg = _load_config()
    entry = cfg["sub_admins"].get(str(chat_id))
    if not entry:
        return False
    return verify_secret(code, entry["privacy_hash"], entry["privacy_salt"])

def list_sub_admins():
    cfg = _load_config()
    return [(int(k), v) for k, v in cfg["sub_admins"].items()]

def revoke_sub_admin(chat_id: int) -> bool:
    cfg = _load_config()
    if str(chat_id) in cfg["sub_admins"]:
        del cfg["sub_admins"][str(chat_id)]
        _save_config(cfg)
        audit("sub_admin_revoked", chat_id, {})
        return True
    return False

def update_sub_admin_last_seen(chat_id: int):
    cfg = _load_config()
    entry = cfg["sub_admins"].get(str(chat_id))
    if entry:
        entry["last_seen"] = datetime.now().isoformat()
        _save_config(cfg)

# ----------------------------------------------------------
# Primary admin verification
# ----------------------------------------------------------
def verify_primary_privacy(code: str) -> bool:
    cfg = _load_config()
    primary = cfg["primary"]
    if not primary:
        return False
    return verify_secret(code, primary["privacy_hash"], primary["privacy_salt"])

def verify_primary_reset(code: str) -> bool:
    cfg = _load_config()
    primary = cfg["primary"]
    if not primary:
        return False
    return verify_secret(code, primary["reset_hash"], primary["reset_salt"])

def set_primary_privacy(new_code: str):
    cfg = _load_config()
    ph, psalt = _hash_secret(new_code)
    if cfg["primary"] is None:
        cfg["primary"] = {}
    cfg["primary"]["privacy_hash"] = ph
    cfg["primary"]["privacy_salt"] = psalt
    cfg["primary"]["failed_attempts"] = 0
    cfg["primary"]["locked_until"] = None
    _save_config(cfg)
    audit("primary_privacy_changed", 0, {})

def verify_sub_admin_verify_code(code: str) -> bool:
    return secrets.compare_digest(code.strip(), config.SUB_ADMIN_VERIFY_CODE.strip())

# ----------------------------------------------------------
# Rate limits / lockout
# ----------------------------------------------------------
MAX_FAILED = 3
LOCKOUT_MINUTES = 15

def is_locked(chat_id: int, role: str = "primary") -> tuple:
    cfg = _load_config()
    if role == "primary":
        entry = cfg["primary"]
    else:
        entry = cfg["sub_admins"].get(str(chat_id))
    if not entry:
        return False, 0
    until = entry.get("locked_until")
    if not until:
        return False, 0
    try:
        dt = datetime.fromisoformat(until)
    except Exception:
        return False, 0
    if datetime.now() < dt:
        return True, int((dt - datetime.now()).total_seconds() // 60)
    # expired — reset
    entry["locked_until"] = None
    entry["failed_attempts"] = 0
    _save_config(cfg)
    return False, 0

def record_failed_attempt(chat_id: int, role: str = "primary"):
    cfg = _load_config()
    key = "primary" if role == "primary" else str(chat_id)
    if role == "primary":
        entry = cfg["primary"]
    else:
        entry = cfg["sub_admins"].get(str(chat_id))
    if not entry:
        return
    entry["failed_attempts"] = entry.get("failed_attempts", 0) + 1
    if entry["failed_attempts"] >= MAX_FAILED:
        until = datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
        entry["locked_until"] = until.isoformat()
    _save_config(cfg)

def reset_failed_attempts(chat_id: int, role: str = "primary"):
    cfg = _load_config()
    if role == "primary":
        entry = cfg["primary"]
    else:
        entry = cfg["sub_admins"].get(str(chat_id))
    if not entry:
        return
    entry["failed_attempts"] = 0
    entry["locked_until"] = None
    _save_config(cfg)

# ----------------------------------------------------------
# Sessions (in-memory, per-chat-id)
# ----------------------------------------------------------
_SESSIONS = {}   # {chat_id: {"role": "primary"|"sub", "expires": ts, "pending": {...}}}

def start_session(chat_id: int, role: str):
    _SESSIONS[chat_id] = {
        "role": role,
        "started": time.time(),
        "expires": time.time() + config.ADMIN_SESSION_MINUTES * 60,
        "pending": None,
    }

def touch_session(chat_id: int):
    s = _SESSIONS.get(chat_id)
    if s:
        s["expires"] = time.time() + config.ADMIN_SESSION_MINUTES * 60

def get_session(chat_id: int):
    s = _SESSIONS.get(chat_id)
    if not s:
        return None
    if time.time() > s["expires"]:
        _SESSIONS.pop(chat_id, None)
        return None
    touch_session(chat_id)
    return s

def end_session(chat_id: int):
    _SESSIONS.pop(chat_id, None)

def set_pending_action(chat_id: int, action: dict):
    s = _SESSIONS.get(chat_id)
    if s:
        s["pending"] = action
        s["pending_expires"] = time.time() + 120   # 2 minutes to confirm

def get_pending_action(chat_id: int):
    s = _SESSIONS.get(chat_id)
    if not s or not s.get("pending"):
        return None
    if time.time() > s.get("pending_expires", 0):
        s["pending"] = None
        return None
    return s["pending"]

def clear_pending_action(chat_id: int):
    s = _SESSIONS.get(chat_id)
    if s:
        s["pending"] = None

# ----------------------------------------------------------
# Device tracking
# ----------------------------------------------------------
def note_device(chat_id: int, role: str):
    """Record panel-open timestamp. Simple audit."""
    if role == "sub":
        update_sub_admin_last_seen(chat_id)
    audit("panel_opened", chat_id, {"role": role})

# ----------------------------------------------------------
# Online status
# ----------------------------------------------------------
def is_user_online(last_seen_iso: str) -> bool:
    if not last_seen_iso:
        return False
    try:
        dt = datetime.fromisoformat(last_seen_iso)
        return (datetime.now() - dt) < timedelta(minutes=config.ADMIN_ONLINE_MINUTES)
    except Exception:
        return False

# ----------------------------------------------------------
# Audit log
# ----------------------------------------------------------
def audit(event: str, chat_id: int, extra: dict = None):
    try:
        line = {
            "ts": datetime.now().isoformat(),
            "event": event,
            "chat_id": chat_id,
            "extra": extra or {},
        }
        with open(config.ADMIN_AUDIT_FILE, "a") as f:
            f.write(json.dumps(line) + "\n")
    except Exception:
        pass

def tail_audit(n: int = 20):
    path = config.ADMIN_AUDIT_FILE
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            lines = f.readlines()[-n:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []

# ----------------------------------------------------------
# Init on import
# ----------------------------------------------------------
ensure_primary_admin_bootstrapped()

if __name__ == "__main__":
    print("admin_auth.py self-test")
    ensure_primary_admin_bootstrapped()
    print("  primary bootstrapped:", _load_config()["primary"] is not None)
    print("  verify good privacy:", verify_primary_privacy(config.ADMIN_PRIVACY_CODE))
    print("  verify bad  privacy:", verify_primary_privacy("wrong"))
    print("  verify good reset:  ", verify_primary_reset(config.ADMIN_RESET_KEY))
    print("  verify verify-code: ", verify_sub_admin_verify_code(config.SUB_ADMIN_VERIFY_CODE))
    print("  sub admins count:   ", len(list_sub_admins()))

# ----------------------------------------------------------
# Lock-in codes (10-minute one-time unlock tokens)
# ----------------------------------------------------------
import os as _os_lockin
LOCKIN_TTL_MINUTES = 10
_LOCKIN_CODES = {}   # {code_upper: {"expires": ts, "target": uid_or_None, "created": ts}}

def generate_lockin_code(target_uid=None):
    """Generate a one-time 8-char code valid for 10 minutes."""
    code = secrets.token_hex(4).upper()   # e.g. A3F91C42
    _LOCKIN_CODES[code] = {
        "expires": time.time() + LOCKIN_TTL_MINUTES * 60,
        "target": target_uid,
        "created": time.time(),
    }
    return code, LOCKIN_TTL_MINUTES

def verify_lockin_code(code, requester_uid=None):
    """Returns (ok, info_dict). Code is consumed on success."""
    code = (code or "").strip().upper()
    entry = _LOCKIN_CODES.get(code)
    if not entry:
        return False, None
    if time.time() > entry["expires"]:
        _LOCKIN_CODES.pop(code, None)
        return False, None
    # If code was targeted, only that UID can use it
    if entry["target"] is not None and requester_uid is not None             and entry["target"] != requester_uid:
        return False, None
    _LOCKIN_CODES.pop(code, None)
    return True, entry

def purge_expired_lockins():
    now = time.time()
    for k in list(_LOCKIN_CODES.keys()):
        if _LOCKIN_CODES[k]["expires"] < now:
            _LOCKIN_CODES.pop(k, None)

def unlock_primary():
    cfg = _load_config()
    if cfg.get("primary"):
        cfg["primary"]["failed_attempts"] = 0
        cfg["primary"]["locked_until"] = None
        _save_config(cfg)

def unlock_sub_admin(chat_id):
    cfg = _load_config()
    entry = cfg["sub_admins"].get(str(chat_id))
    if entry:
        entry["failed_attempts"] = 0
        entry["locked_until"] = None
        _save_config(cfg)

def clear_user_block(uid):
    """Remove strike block from a student's profile."""
    path = _os_lockin.path.join("profiles", f"{uid}.json")
    if not _os_lockin.path.exists(path):
        return False
    try:
        with open(path) as f:
            p = json.load(f)
        p.setdefault("behavior", {})["blocked_until"] = None
        p["behavior"]["strikes"] = 0
        with open(path, "w") as f:
            json.dump(p, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def is_hex_lockin_code(text):
    """True if the text looks like one of our lock-in codes."""
    t = (text or "").strip().upper()
    if len(t) != 8:
        return False
    return all(c in "0123456789ABCDEF" for c in t)

