# ==========================================================
# c30r_activity_tracker.py — v2
# - last_seen tracking (profile)
# - session last_activity tracking (for auto-close)
# - incoming msg tracking during admin session/pending
# - lock-in button handler
# ==========================================================
import os as _at_os
import json as _at_json
from datetime import datetime as _at_dt
import admin_auth as _at_auth

def _touch_user_activity(uid, incoming_msg_id=None):
    try:
        if not uid: return
        try:
            sess = _at_auth.get_session(uid)
            if sess:
                sess["last_activity"] = _at_dt.now().isoformat()
        except Exception:
            pass
        if incoming_msg_id:
            try:
                has = bool(_at_auth.get_session(uid))
                if not has:
                    for _mn, _mo in __import__("sys").modules.items():
                        if hasattr(_mo, "PENDING_AUTH_FLOW") and uid in _mo.PENDING_AUTH_FLOW:
                            has = True
                            break
                if not has:
                    for _mn, _mo in __import__("sys").modules.items():
                        if hasattr(_mo, "PENDING_ADMIN_FLOW") and uid in _mo.PENDING_ADMIN_FLOW:
                            has = True
                            break
                if not has:
                    try:
                        _trk_g = globals().get("_ADMIN_MSGS")
                        if _trk_g and _trk_g.get(int(uid)):
                            has = True
                    except Exception:
                        pass
                if has:
                    _trk = globals().get("track_admin_msg")
                    if _trk:
                        _trk(uid, incoming_msg_id)
            except Exception:
                pass
        pdir = globals().get("PROFILE_DIR") or "profiles"
        path = _at_os.path.join(pdir, f"{uid}.json")
        if not _at_os.path.exists(path): return
        with open(path) as f:
            p = _at_json.load(f)
        if not p.get("secured"): return
        p["last_seen"] = _at_dt.now().isoformat()
        with open(path, "w") as f:
            _at_json.dump(p, f, indent=2)
    except Exception as e:
        print(f"[at] touch err: {e}")


try:
    _orig_pnu = bot.process_new_updates
    def _at_patched_pnu(updates):
        try:
            for u in updates:
                if getattr(u, "message", None):
                    fu = getattr(u.message, "from_user", None)
                    if fu:
                        _touch_user_activity(fu.id, getattr(u.message, "message_id", None))
                if getattr(u, "callback_query", None):
                    fu = getattr(u.callback_query, "from_user", None)
                    if fu:
                        _touch_user_activity(fu.id)
        except Exception as e:
            print(f"[at] pnu err: {e}")
        return _orig_pnu(updates)
    bot.process_new_updates = _at_patched_pnu
    print("[at] activity tracker installed (v2, session+incoming)")
except Exception as e:
    print(f"[at] install FAILED: {e}")


@bot.callback_query_handler(func=lambda c: c.data == "admin_lockin_btn")
def _cb_admin_lockin_btn(call):
    try:
        _s = _at_auth.get_session(call.from_user.id)
        if not _s or _s.get("role") != "primary":
            bot.answer_callback_query(call.id, "Primary only")
            return
    except Exception:
        pass
    try:
        bot.answer_callback_query(call.id, "Generating lock-in code...")
        result = _at_auth.generate_lockin_code()
        if isinstance(result, tuple) and len(result) >= 2:
            code, mins = result[0], result[1]
        else:
            code, mins = str(result), 10
        safe_send(
            call.from_user.id,
            f"🔑 *Lock-in Code Generated*\n\n"
            f"`{code}`\n\n"
            f"Valid for *{mins} minutes*.\n"
            f"Copy exactly as shown.",
            parse_mode="Markdown",
        )
        print(f"[lockin_btn] code for {call.from_user.id}: {code}")
    except Exception as e:
        print(f"[lockin_btn] FAILED: {e}")
        safe_send(call.from_user.id, f"⚠️ Lock-in generation failed: {e}")


print("c30r_activity_tracker: loaded (v2).")
