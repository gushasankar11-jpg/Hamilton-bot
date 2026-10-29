# ==========================================================
# bot.py — Chunk 10: missing features (overrides + help menu)
# ==========================================================

# ==========================================================
# UPDATED — No-key message with new pricing + admin contact
# ==========================================================
def _no_key_message(short=False):
    if short:
        return (
            "🔒 Hamilton needs an activation key.\n\n"
            f"💰 Price: *₹169* (fixed)\n"
            f"_May vary on your year of selection._\n\n"
            f"📞 Contact admin *Krishna Vamsi* at *Hemanth and Krishna Publications*:\n"
            f"WhatsApp *{WHATSAPP_CONTACT}*"
        )
    return (
        "🔒 *Hamilton needs an activation key to begin.*\n\n"
        f"💰 *Price: ₹169* — fixed for all exams.\n"
        f"_Note: Price may vary based on your year of selection._\n\n"
        f"📞 To get your key, message admin *Krishna Vamsi* at "
        f"*Hemanth and Krishna Publications*:\n"
        f"WhatsApp *{WHATSAPP_CONTACT}*\n\n"
        f"Once you receive your key, send it here to unlock Hamilton."
    )


# ==========================================================
# DEVICE BINDING — one key, one device
# ==========================================================
def _check_key_binding(uid, key):
    """
    Returns (allowed, reason).
    If key unbound → binds it to uid and allows.
    If key already bound to same uid → allows.
    If key bound to different uid → rejects.
    """
    keys = load_keys()
    if key not in keys:
        return False, "invalid"
    info = keys[key]
    if not isinstance(info, dict):
        # Old format — bind and allow
        keys[key] = {"year": None, "bound_to": str(uid),
                     "bound_at": datetime.now().isoformat()}
        with open(KEYS_FILE, "w") as f:
            json.dump(keys, f, indent=2)
        return True, "bound"

    bound_to = info.get("bound_to")
    if bound_to is None:
        info["bound_to"] = str(uid)
        info["bound_at"] = datetime.now().isoformat()
        keys[key] = info
        with open(KEYS_FILE, "w") as f:
            json.dump(keys, f, indent=2)
        return True, "bound"
    if str(bound_to) == str(uid):
        return True, "same_device"
    return False, "other_device"


# ==========================================================
# /help — menu with everything
# ==========================================================
# DISABLED_MASTER: @bot.message_handler(commands=['help'])
def cmd_help(message):
    uid = message.chat.id
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Group commands logically
    kb.row(
        InlineKeyboardButton("📚 Study", callback_data="help_cat:study"),
        InlineKeyboardButton("🧪 Test & Practice", callback_data="help_cat:test")
    )
    kb.row(
        InlineKeyboardButton("📊 Profile & Stats", callback_data="help_cat:profile"),
        InlineKeyboardButton("⚙️ System", callback_data="help_cat:system")
    )
    kb.add(InlineKeyboardButton("❌ Close Help", callback_data="help_close"))
    
    try:
        safe_send(uid, "🤖 *Hamilton Help Menu*\n\nTap a category below to see commands and what they do.", parse_mode="Markdown", reply_markup=kb)
        print(f"[help] sent to {uid}")
    except Exception as e:
        print(f"[help-err] {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("help_cat:"))
def cb_help_cat(call):
    cat = call.data.split(":")[1]
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    
    if cat == "study":
        kb.row(
            InlineKeyboardButton("/mode", callback_data="help_cmd:mode"),
            InlineKeyboardButton("/select", callback_data="help_cmd:select")
        )
        kb.row(
            InlineKeyboardButton("/notes", callback_data="help_cmd:notes"),
            InlineKeyboardButton("/plan", callback_data="help_cmd:plan")
        )
        text = "📚 *Study Commands*\n\nTap a command to learn what it does."
        
    elif cat == "test":
        kb.row(
            InlineKeyboardButton("/exam", callback_data="help_cmd:exam"),
            InlineKeyboardButton("/pyq", callback_data="help_cmd:pyq")
        )
        kb.row(
            InlineKeyboardButton("/stop", callback_data="help_cmd:stop"),
            InlineKeyboardButton("/bookmarks", callback_data="help_cmd:bookmarks")
        )
        text = "🧪 *Test & Practice Commands*\n\nTap a command to learn what it does."
        
    elif cat == "profile":
        kb.row(
            InlineKeyboardButton("/status", callback_data="help_cmd:status"),
            InlineKeyboardButton("/health", callback_data="help_cmd:health")
        )
        kb.row(
            InlineKeyboardButton("/leaderboard", callback_data="help_cmd:leaderboard"),
            InlineKeyboardButton("/find", callback_data="help_cmd:find")
        )
        text = "📊 *Profile & Stats*\n\nTap a command to learn what it does."
        
    elif cat == "system":
        kb.row(
            InlineKeyboardButton("/start", callback_data="help_cmd:start"),
            InlineKeyboardButton("/cancel", callback_data="help_cmd:cancel")
        )
        kb.row(
            InlineKeyboardButton("/clear_data", callback_data="help_cmd:clear_data")
        )
        text = "⚙️ *System Commands*\n\nTap a command to learn what it does."
        
    kb.add(InlineKeyboardButton("🔙 Back to Categories", callback_data="help_back"))
    
    try:
        bot.edit_message_text(text, chat_id=call.from_user.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("help_cmd:"))
def cb_help_cmd(call):
    cmd = call.data.split(":")[1]
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    
    descriptions = {
        "start": "🚀 *Start*\nInitializes your Hamilton journey. Asks for your name, institute, phone, and level.",
        "mode": "📚 *Mode*\nSet up your exams (JEE Adv, Mains, EAMCET), priority exam, target year, and target marks.",
        "select": "🎯 *Select*\nPick the specific chapters you want to focus on. Feeds into tests and notes.",
        "exam": "🧪 *Exam*\nEnter Practice, Test, or Conceptual mode. Practice gives casual questions. Test simulates the real exam with a timer. Conceptual focuses on deep theory.",
        "pyq": "📝 *PYQ*\nPrevious Year Questions. Practice REAL questions from past JEE/EAMCET papers, filtered by year and chapter.",
        "notes": "📖 *Notes*\nGenerates structured short notes for a chapter, delivered as a PDF.",
        "plan": "📅 *Plan*\nGenerates a day-by-day study schedule based on your available hours and target marks.",
        "status": "👤 *Status*\nShows your current profile summary, including level, target marks, and streak.",
        "health": "❤️ *Health*\nShows your readiness and concept mastery across all three subjects.",
        "leaderboard": "🏆 *Leaderboard*\nShows the top performers based on their Health score and Subject average.",
        "find": "🔍 *Find*\nSearch for another user by their HKU ID.",
        "bookmarks": "🔖 *Bookmarks*\nView all the questions you have saved for later review.",
        "stop": "🛑 *Stop*\nEnds your current test or practice session immediately.",
        "clear_data": "⚠️ *Clear Data*\nDeletes your entire profile and progress from the bot. This cannot be undone.",
        "cancel": "✖️ *Cancel*\nAborts any active setup (like /mode or test generation) and returns to normal chat."
    }
    
    desc = descriptions.get(cmd, "No description available.")
    try:
        bot.edit_message_text(desc, chat_id=call.from_user.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "help_back")
def cb_help_back(call):
    try:
        cmd_help(call.message)
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "help_close")
def cb_help_close(call):
    try:
        bot.delete_message(call.from_user.id, call.message.message_id)
    except: pass
    bot.answer_callback_query(call.id, "Closed")
