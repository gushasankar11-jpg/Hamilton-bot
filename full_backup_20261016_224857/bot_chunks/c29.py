# ==========================================================
# c29 — Reset cooldowns + NameError safety + Key status
# ==========================================================

import traceback as _tb

# ----------------------------------------------------------
# RESET ALL AI COOLDOWNS ON STARTUP
# ----------------------------------------------------------
try:
    import ai_client as _ac
    if hasattr(_ac, "_COOLDOWN"):
        _ac._COOLDOWN.clear()
    if hasattr(_ac, "_KEY_FAIL_COUNT"):
        _ac._KEY_FAIL_COUNT.clear()
    if hasattr(_ac, "_CURRENT_KEY_INDEX"):
        _ac._CURRENT_KEY_INDEX[0] = 0
    print("[c29] Cooldowns reset")

    # Print key inventory
    try:
        gk = getattr(_ac, "GROQ_KEYS", [])
        gmk = getattr(_ac, "GEMINI_KEYS", [])
        print(f"[c29] Groq keys: {len(gk)}, Gemini keys: {len(gmk)}")
    except Exception:
        pass
except Exception as e:
    print(f"[c29] reset failed: {e}")


# ----------------------------------------------------------
# SAFE WRAPPER — catch NameError in any handler
# ----------------------------------------------------------
def _safe_call(uid, func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except NameError as e:
        print(f"[c29] NameError: {e}")
        _tb.print_exc()
        try:
            safe_send(uid, "⚠️ Minor glitch. Please retry or type /exam again.")
        except Exception:
            pass
    except Exception as e:
        print(f"[c29] Error: {e}")
        _tb.print_exc()
        try:
            safe_send(uid, "⚠️ Something went wrong. Please retry.")
        except Exception:
            pass


# ----------------------------------------------------------
# WRAP POLL HANDLERS (safest place for the NameError)
# ----------------------------------------------------------
_orig_on_poll = on_poll_answer

@bot.poll_answer_handler()
def on_poll_answer_safe(poll_answer):
    uid = poll_answer.user.id
    try:
        return _orig_on_poll(poll_answer)
    except NameError as e:
        print(f"[c29] NameError in poll handler: {e}")
        _tb.print_exc()
        try:
            safe_send(uid, "⚠️ Glitch detected. Please /stop and /exam again.")
        except Exception:
            pass
    except Exception as e:
        print(f"[c29] Error in poll handler: {e}")
        _tb.print_exc()


# ----------------------------------------------------------
# WRAP CONCEPTUAL START (where `subject` was undefined)
# ----------------------------------------------------------
_orig_concept_capture_count = _concept_capture_count

def _concept_capture_count_safe(message, subj, chapter):
    try:
        return _orig_concept_capture_count(message, subj, chapter)
    except NameError as e:
        print(f"[c29] NameError in concept start: {e}")
        _tb.print_exc()
        try:
            safe_send(message.chat.id, "⚠️ Setup glitch. Please /exam again.")
        except Exception:
            pass
    except Exception as e:
        print(f"[c29] Error in concept start: {e}")
        _tb.print_exc()

_concept_capture_count = _concept_capture_count_safe


# ----------------------------------------------------------
# DEBUG COMMAND — /key_status (admin only)
# ----------------------------------------------------------
@bot.message_handler(commands=['key_status'])
def cmd_key_status(message):
    uid = message.chat.id
    if uid != ADMIN_CHAT_ID:
        return
    import ai_client as _ac
    lines = ["🔑 *AI Key Status*\n"]
    gk = getattr(_ac, "GROQ_KEYS", [])
    gmk = getattr(_ac, "GEMINI_KEYS", [])
    lines.append(f"Groq: {len(gk)} keys")
    lines.append(f"Gemini: {len(gmk)} keys")
    lines.append("")
    cd = getattr(_ac, "_COOLDOWN", {})
    if cd:
        lines.append(f"Cooldowns active: {len(cd)}")
        for k, v in list(cd.items())[:5]:
            left = max(0, int(v - time.time()))
            lines.append(f"  {k}: {left}s")
    else:
        lines.append("✅ No active cooldowns")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 29 loaded: cooldowns reset + safety wrappers ready.")

