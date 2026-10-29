# ==========================================================
# c30b_admin.py — Admin Delete Panel
# ==========================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def _admin_only(uid):
    return uid == ADMIN_CHAT_ID


def _list_all_users():
    users = []
    if not os.path.isdir(PROFILE_DIR):
        return users
    for fname in os.listdir(PROFILE_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            uid = int(fname.replace(".json", ""))
        except ValueError:
            continue
        try:
            with open(os.path.join(PROFILE_DIR, fname)) as f:
                p = json.load(f)
        except Exception:
            continue
        if not p.get("secured"):
            continue
        users.append((uid, p))
    users.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
    return users


def _days_since(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return (datetime.now() - dt).days
    except Exception:
        return "?"


def _build_user_list_keyboard(users, page=0, per_page=8):
    kb = InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    end = start + per_page
    for uid, p in users[start:end]:
        name = (p.get("name") or "Unknown")[:20]
        hku = p.get("hku_id") or "—"
        days = _days_since(p.get("created_at", ""))
        label = f"🗑 {hku} · {name} · {days}d"
        kb.add(InlineKeyboardButton(label, callback_data=f"admin_del_prompt:{uid}"))
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_page:{page-1}"))
    if end < len(users):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_page:{page+1}"))
    if nav_row:
        kb.row(*nav_row)
    kb.add(InlineKeyboardButton("❌ Close", callback_data="admin_close"))
    return kb


def _show_admin_panel(chat_id, page=0, message_id=None):
    users = _list_all_users()
    if not users:
        text = "🛠 *ADMIN PANEL*\n\nNo registered users found."
        if message_id:
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, parse_mode="Markdown")
        return

    total_pages = max(1, (len(users) + 7) // 8)
    text = ("🛠 *ADMIN PANEL*\n\n"
            f"📊 Total registered users: *{len(users)}*\n"
            f"📄 Page {page+1} / {total_pages}\n\n"
            "• Tap any user to delete\n"
            "• `/find <name or UID>` — search\n"
            "• `/findkey <key>` — users with that key")
    kb = _build_user_list_keyboard(users, page)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                   reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text and m.text.strip() == ADMIN_PANEL_CODE)
def _admin_panel_entry(message):
    if not _admin_only(message.chat.id):
        bot.reply_to(message, "❌ Unknown command.")
        return
    _show_admin_panel(message.chat.id)


@bot.message_handler(commands=['find'])
def _admin_find(message):
    if not _admin_only(message.chat.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: `/find <name or UID>`", parse_mode="Markdown")
        return
    q = parts[1].strip().lower()
    users = _list_all_users()
    matches = []
    for uid, p in users:
        if q in (p.get("name") or "").lower() or q in str(uid):
            matches.append((uid, p))
    if not matches:
        bot.reply_to(message, f"❌ No matches for `{q}`", parse_mode="Markdown")
        return
    text = f"🔍 *{len(matches)} match(es) for '{q}'*\n\n"
    kb = InlineKeyboardMarkup(row_width=1)
    for uid, p in matches[:20]:
        name = (p.get("name") or "Unknown")[:20]
        hku = p.get("hku_id") or "—"
        days = _days_since(p.get("created_at", ""))
        text += f"• `{hku}` — {name} · {days}d\n"
        kb.add(InlineKeyboardButton(f"🗑 Delete {hku} · {name}",
                                     callback_data=f"admin_del_prompt:{uid}"))
    kb.add(InlineKeyboardButton("❌ Close", callback_data="admin_close"))
    bot.reply_to(message, text, reply_markup=kb, parse_mode="Markdown")


@bot.message_handler(commands=['findkey'])
def _admin_findkey(message):
    if not _admin_only(message.chat.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: `/findkey <activation_key>`", parse_mode="Markdown")
        return
    q = parts[1].strip().lower()
    users = _list_all_users()
    matches = [(u, p) for u, p in users if q in (p.get("activation_key") or "").lower()]
    if not matches:
        bot.reply_to(message, f"❌ No users with key `{q}`", parse_mode="Markdown")
        return
    text = f"🔑 *{len(matches)} user(s) with key '{q}'*\n\n"
    kb = InlineKeyboardMarkup(row_width=1)
    for uid, p in matches:
        name = (p.get("name") or "Unknown")[:20]
        hku = p.get("hku_id") or "—"
        days = _days_since(p.get("created_at", ""))
        text += f"• `{hku}` — {name} · {days}d\n"
        kb.add(InlineKeyboardButton(f"🗑 Delete {hku} · {name}",
                                     callback_data=f"admin_del_prompt:{uid}"))
    kb.add(InlineKeyboardButton("❌ Close", callback_data="admin_close"))
    bot.reply_to(message, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_page:"))
def _cb_admin_page(call):
    if not _admin_only(call.message.chat.id):
        return
    try:
        page = int(call.data.split(":")[1])
    except Exception:
        page = 0
    _show_admin_panel(call.message.chat.id, page=page, message_id=call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data == "admin_close")
def _cb_admin_close(call):
    if not _admin_only(call.message.chat.id):
        return
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        try:
            bot.edit_message_text("Closed.", chat_id=call.message.chat.id,
                                   message_id=call.message.message_id)
        except Exception:
            pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_del_prompt:"))
def _cb_admin_del_prompt(call):
    if not _admin_only(call.message.chat.id):
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    p = load_profile(target)
    if not p:
        bot.answer_callback_query(call.id, "User not found")
        return
    name = (p.get("name") or "Unknown")[:30]
    hku = p.get("hku_id") or "—"
    key = p.get("activation_key") or "—"
    days = _days_since(p.get("created_at", ""))
    text = ("⚠️ *DELETE CONFIRMATION*\n\n"
            f"👤 Name: `{name}`\n"
            f"🆔 HKU: `{hku}`\n"
            f"📱 UID: `{target}`\n"
            f"🔑 Key: `{key}`\n"
            f"📅 Registered: {days} days ago\n\n"
            "*Are you sure?* This cannot be undone.")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🗑 YES, DELETE PERMANENTLY",
                                 callback_data=f"admin_del_confirm:{target}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="admin_close"))
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_del_confirm:"))
def _cb_admin_del_confirm(call):
    if not _admin_only(call.message.chat.id):
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    path = os.path.join(PROFILE_DIR, f"{target}.json")
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
    bm = os.path.join(BOOKMARK_DIR, f"{target}.json")
    if os.path.exists(bm):
        try:
            os.remove(bm)
        except Exception:
            pass
    bot.answer_callback_query(call.id, f"✅ UID {target} deleted")
    try:
        bot.edit_message_text(f"✅ *DELETED*\n\nUID `{target}` permanently removed.",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              parse_mode="Markdown")
    except Exception:
        bot.send_message(call.message.chat.id,
                         f"✅ Deleted UID {target}", parse_mode="Markdown")


print("🛠 Admin panel chunk loaded.")
