# ==========================================================
# c30n_sched_viewer.py — Scheduled Broadcasts Viewer
# 4 tabs: Text / Image / File / Exam (coming soon)
# Actions: Reschedule / Cancel
# ==========================================================
import json as _sv_json
import os as _sv_os
from datetime import datetime as _sv_dt

_SV_FILE = "scheduled_broadcasts.json"


def _sv_load():
    if not _sv_os.path.exists(_SV_FILE):
        return []
    try:
        with open(_SV_FILE) as f:
            d = _sv_json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def _sv_save(items):
    tmp = _SV_FILE + ".tmp"
    with open(tmp, "w") as f:
        _sv_json.dump(items, f, indent=2)
    _sv_os.replace(tmp, _SV_FILE)


def _sv_item_title(it):
    """Derive display title."""
    t = it.get("title")
    if t:
        return t[:40]
    # Fallback
    ft = it.get("file_type")
    txt = (it.get("text") or "").strip()
    if ft:
        return f"[{ft}] {txt[:30]}" if txt else f"[{ft}]"
    return (txt[:40] or "(untitled)")


def _sv_item_type(it):
    ft = it.get("file_type")
    if ft in ("photo", "video", "audio", "voice", "video_note"):
        return "image" if ft == "photo" else "file"
    if ft == "document":
        return "file"
    return "text"


def _sv_time_until(scheduled_at_str):
    """Human-readable countdown."""
    try:
        s = scheduled_at_str.strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = _sv_dt.strptime(s, fmt)
                break
            except ValueError:
                continue
        else:
            return "?"
        delta = dt - _sv_dt.now()
        if delta.total_seconds() < 0:
            return "OVERDUE"
        d = delta.days
        h = delta.seconds // 3600
        m = (delta.seconds % 3600) // 60
        if d > 0:
            return f"{d}d {h}h"
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m"
    except Exception:
        return "?"


def _sv_build_list(tab):
    """Return (text, kb) for the given tab."""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    items = _sv_load()
    filtered = [it for it in items if not it.get("sent") and _sv_item_type(it) == tab]
    text = f"📋 *Scheduled Broadcasts — {tab.upper()}*\n\n"
    kb = InlineKeyboardMarkup(row_width=1)
    if not filtered:
        text += "_No pending broadcasts in this category._"
    else:
        text += f"Pending: *{len(filtered)}*\n\nTap to view & manage:"
        for idx, it in enumerate(filtered):
            title = _sv_item_title(it)
            ttl = _sv_time_until(it.get("scheduled_at", ""))
            cb = f"sv_view:{idx}"
            kb.add(InlineKeyboardButton(f"📩 {title} · {ttl}", callback_data=cb))
    # Tab navigation
    tabs = [("text", "✉️ Text"), ("image", "🖼 Image"), ("file", "📎 File"), ("exam", "📝 Exam")]
    row = []
    for t_key, t_label in tabs:
        if t_key == tab:
            t_label = f"• {t_label}"
        row.append(InlineKeyboardButton(t_label, callback_data=f"sv_tab:{t_key}"))
    # two per row
    kb.row(row[0], row[1])
    kb.row(row[2], row[3])
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    return text, kb


@bot.callback_query_handler(func=lambda c: c.data.startswith("sv_tab:"))
def _sv_cb_tab(call):
    uid = call.from_user.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    tab = call.data.split(":")[1]
    if tab == "exam":
        text = "📝 *Exam Broadcasts*\\n\\n_Coming soon — needs Exam Panel (Session 5)._"
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back to Text", callback_data="sv_tab:text"))
        kb.add(InlineKeyboardButton("🔙 Panel", callback_data="admin_back"))
        try:
            bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return
    text, kb = _sv_build_list(tab)
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("sv_view:"))
def _sv_cb_view(call):
    uid = call.from_user.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    try:
        idx = int(call.data.split(":")[1])
    except Exception:
        return
    items = _sv_load()
    pending = [it for it in items if not it.get("sent")]
    if idx >= len(pending):
        bot.answer_callback_query(call.id, "Item gone")
        return
    it = pending[idx]
    title = _sv_item_title(it)
    scheduled = it.get("scheduled_at", "?")
    ttl = _sv_time_until(scheduled)
    recipients_count = len(it.get("recipients", []))
    txt = (it.get("text") or "")[:200]
    file_type = it.get("file_type")
    lines = [
        f"📋 *{title}*",
        "",
        f"⏰ *Fires in:* {ttl}  ({scheduled})",
        f"👥 *Recipients:* {recipients_count}",
        f"📝 *Type:* {_sv_item_type(it)}" + (f" ({file_type})" if file_type else ""),
        "",
    ]
    if txt:
        lines.append(f"💬 *Message:*\\n_{txt}_")
    if file_type:
        lines.append(f"\\n_Attached: {file_type} file_")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📅 Reschedule", callback_data=f"sv_resched:{idx}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"sv_cancel:{idx}"),
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"sv_tab:{_sv_item_type(it)}"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("sv_cancel:"))
def _sv_cb_cancel(call):
    uid = call.from_user.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    try:
        idx = int(call.data.split(":")[1])
    except Exception:
        return
    items = _sv_load()
    pending_indices = [i for i, it in enumerate(items) if not it.get("sent")]
    if idx >= len(pending_indices):
        bot.answer_callback_query(call.id, "Already gone")
        return
    actual_idx = pending_indices[idx]
    removed_title = _sv_item_title(items[actual_idx])
    del items[actual_idx]
    _sv_save(items)
    print(f"[sv] {uid} cancelled schedule: {removed_title}")
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back to List", callback_data="sv_tab:text"))
    try:
        bot.edit_message_text(
            f"✅ *Cancelled:* {removed_title}\\n\\n_Won't fire._",
            chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown"
        )
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("sv_resched:"))
def _sv_cb_resched(call):
    uid = call.from_user.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    try:
        idx = int(call.data.split(":")[1])
    except Exception:
        return
    items = _sv_load()
    pending_indices = [i for i, it in enumerate(items) if not it.get("sent")]
    if idx >= len(pending_indices):
        bot.answer_callback_query(call.id, "Gone")
        return
    actual_idx = pending_indices[idx]
    # Store for next-step
    if not hasattr(bot, "_sv_resched_ctx"):
        bot._sv_resched_ctx = {}
    bot._sv_resched_ctx[uid] = {"idx": actual_idx}
    safe_send(uid,
        "📅 *Enter new schedule* — YYYY-MM-DD HH:MM\\n\\n"
        "_Example: `2026-10-25 18:30`_",
        parse_mode="Markdown")


@bot.message_handler(func=lambda m: hasattr(bot, "_sv_resched_ctx") and m.chat.id in getattr(bot, "_sv_resched_ctx", {}), content_types=['text'])
def _sv_catch_resched(message):
    uid = message.chat.id
    ctx = bot._sv_resched_ctx.pop(uid, None)
    if not ctx:
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        return
    # Parse
    new_dt = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M %p"):
        try:
            new_dt = _sv_dt.strptime(txt, fmt)
            break
        except ValueError:
            continue
    if not new_dt:
        safe_send(uid, "❌ Invalid format. Use `YYYY-MM-DD HH:MM`:", parse_mode="Markdown")
        bot._sv_resched_ctx[uid] = ctx
        return
    if new_dt <= _sv_dt.now():
        safe_send(uid, "❌ Time must be in the future. Try again:")
        bot._sv_resched_ctx[uid] = ctx
        return
    items = _sv_load()
    idx = ctx["idx"]
    if idx >= len(items):
        safe_send(uid, "❌ Item disappeared.")
        return
    old_sched = items[idx].get("scheduled_at", "?")
    items[idx]["scheduled_at"] = new_dt.strftime("%Y-%m-%d %H:%M")
    items[idx]["sent"] = False
    items[idx]["sent_at"] = None
    _sv_save(items)
    print(f"[sv] {uid} rescheduled: {old_sched} → {items[idx]['scheduled_at']}")
    safe_send(uid,
        f"✅ *Rescheduled*\\n\\n"
        f"Was: {old_sched}\\n"
        f"Now: *{items[idx]['scheduled_at']}*",
        parse_mode="Markdown")


print("c30n_sched_viewer: loaded.")
