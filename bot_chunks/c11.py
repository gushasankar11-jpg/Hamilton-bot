# ==========================================================
# bot.py — Chunk 11: Rich text overrides
# ==========================================================

from rich_formatter import markdown_to_rich

# Keep a reference to the original safe_send
_original_safe_send = safe_send
_original_safe_edit = safe_edit


def _looks_like_rich(text):
    """Detect if text contains markdown/LaTeX that benefits from rich rendering."""
    if not text:
        return False
    indicators = ["$$", "$", "**", "##", "# ", "\\(", "\\[", "\\frac",
                  "\\tau", "\\int", "\\sum", "\\alpha", "\\beta", "\\vec",
                  "\\sqrt", "\\begin{", "\\end{"]
    return any(ind in text for ind in indicators)


def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    """
    If text looks like markdown/LaTeX content → send as Telegram Rich message.
    Otherwise → send as plain text (with Markdown fallback).
    """
    if not text:
        return

    # Long text → split (keep existing logic)
    if len(text) > TELEGRAM_MSG_LIMIT:
        while len(text) > TELEGRAM_MSG_LIMIT:
            cut = text.rfind("\n", 0, TELEGRAM_MSG_LIMIT)
            if cut == -1:
                cut = TELEGRAM_MSG_LIMIT
            chunk = text[:cut]
            _send_rich_or_plain(chat_id, chunk, parse_mode, None)
            text = text[cut:].lstrip()
            time.sleep(0.3)
        if text:
            _send_rich_or_plain(chat_id, text, parse_mode, reply_markup)
        return

    _send_rich_or_plain(chat_id, text, parse_mode, reply_markup)


def _send_rich_or_plain(chat_id, text, parse_mode, reply_markup):
    if _looks_like_rich(text):
        try:
            rich = markdown_to_rich(text)
            bot.send_rich_message(
                chat_id=chat_id,
                rich_message=rich,
                reply_markup=reply_markup,
            )
            return
        except Exception as e:
            print(f"[RICH] Failed: {e}. Falling back to plain.")

    # Plain fallback
    try:
        bot.send_message(chat_id, text, parse_mode=parse_mode,
                         reply_markup=reply_markup)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=reply_markup)


def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    """
    For rich content → try editing to rich. If fails → delete + send new.
    For plain → edit normally.
    """
    if not text:
        return

    if _looks_like_rich(text):
        # Try editing to rich
        try:
            rich = markdown_to_rich(text)
            # Try edit — pyTelegramBotAPI may or may not expose editRichMessage
            try:
                bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=text[:TELEGRAM_MSG_LIMIT], parse_mode=parse_mode)
                # If plain edit worked, but we wanted rich... fallback:
                # Actually delete + send rich for better result
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception:
                    pass
                bot.send_rich_message(
                    chat_id=chat_id, rich_message=rich,
                    reply_markup=reply_markup)
                return
            except Exception:
                # Couldn't edit — send new
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception:
                    pass
                bot.send_rich_message(
                    chat_id=chat_id, rich_message=rich,
                    reply_markup=reply_markup)
                return
        except Exception as e:
            print(f"[RICH-EDIT] Failed: {e}")

    # Plain edit fallback
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                              text=text[:TELEGRAM_MSG_LIMIT],
                              parse_mode=parse_mode,
                              reply_markup=reply_markup)
    except Exception:
        try:
            bot.send_message(chat_id, text, parse_mode=parse_mode,
                             reply_markup=reply_markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=reply_markup)


print("bot.py Chunk 11 loaded: rich text overrides ready.")

