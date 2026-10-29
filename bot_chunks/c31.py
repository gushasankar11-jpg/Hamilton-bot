# ==========================================================
# c31 — Developer credit footer
# ==========================================================

_ORIG_SEND_C31 = safe_send
_ORIG_EDIT_C31 = safe_edit


def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    if text and "Developed by Vishnavi Gokarnam" not in text:
        text = text.rstrip() + "\n\n_Developed by Vishnavi Gokarnam_"
    return _ORIG_SEND_C31(chat_id, text, parse_mode=parse_mode,
                           reply_markup=reply_markup)


def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    if text and "Developed by Vishnavi Gokarnam" not in text:
        text = text.rstrip() + "\n\n_Developed by Vishnavi Gokarnam_"
    return _ORIG_EDIT_C31(chat_id, message_id, text, parse_mode=parse_mode,
                           reply_markup=reply_markup)


print("bot.py Chunk 31 loaded: developer credit footer ready.")


# ==========================================================
# BOOT
# ==========================================================
print("🚀 Hamilton Study AI is live.")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=20)
    except Exception as e:
        print(f"⚠️ Polling crashed: {e}")
        print("🔄 Restarting in 5 seconds...")
        _time.sleep(5)
        continue
