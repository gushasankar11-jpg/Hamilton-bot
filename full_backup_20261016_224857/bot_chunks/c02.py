# ==========================================================
# bot.py — Chunk 2: start, onboarding, mode, status
# ==========================================================

@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.chat.id
    p = get_or_create_profile(uid)

    if not p.get("secured"):
        save_profile(uid, p)
        bot.reply_to(message,
            "🙏 *Namaskaram, Aspirant!*\n\n"
            "You stand in the final stretch of your *Intermediate journey* — "
            "balancing board studies with deep, focused preparation for your "
            "competitive exams.\n\n"
            "I am *Hamilton Study AI* *(by Hemanth and Krishna Publications)*, "
            "your personal exam mentor — built to walk beside you every single "
            "day until your rank is sealed.\n\n"
            "🔒 *To begin, send your activation key.*",
            parse_mode="Markdown")
        return

    if p.get("onboarding_step") and p["onboarding_step"] != "done":
        _run_onboarding(uid)
        return

    bot.reply_to(message,
        f"🙏 Welcome back, {p.get('name', 'Aspirant')}!\n\n"
        "Type /mode to set up or change exams, or /health to see progress.",
        parse_mode="Markdown")


def _run_onboarding(uid):
    p = load_profile(uid)
    step = p.get("onboarding_step")
    if step == "name":
        msg = bot.send_message(uid, "📝 What is your name?")
        bot.register_next_step_handler(msg, _onboarding_name)
    elif step == "institute":
        msg = bot.send_message(uid, "🏫 Which institute / school / college?")
        bot.register_next_step_handler(msg, _onboarding_institute)
    elif step == "level":
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("Junior", "Senior", "Dropper")
        msg = bot.send_message(uid,
            "🎓 Are you a Junior, Senior, or Dropper?\n\n"
            "• Junior — 1st year Intermediate\n"
            "• Senior — 2nd year Intermediate\n"
            "• Dropper — Already passed Intermediate, taking a gap year",
            reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_level)
    else:
        bot.send_message(uid, "✅ Setup complete. Type /mode to begin.")


def _onboarding_name(message):
    uid = message.chat.id
    name = (message.text or "").strip()[:40]
    if not name or len(name) < 2:
        bot.reply_to(message, "Please type your name (at least 2 characters).")
        return
    p = load_profile(uid)
    p["name"] = name
    p["onboarding_step"] = "institute"
    save_profile(uid, p)
    _run_onboarding(uid)


def _onboarding_institute(message):
    uid = message.chat.id
    inst = (message.text or "").strip()[:60]
    if not inst or len(inst) < 2:
        bot.reply_to(message, "Please type your institute name.")
        return
    p = load_profile(uid)
    p["institute"] = inst
    p["onboarding_step"] = "level"
    save_profile(uid, p)
    _run_onboarding(uid)


def _onboarding_level(message):
    uid = message.chat.id
    txt = (message.text or "").strip().lower()
    if txt not in ("junior", "senior", "dropper"):
        bot.reply_to(message, "Please tap one of: Junior / Senior / Dropper")
        return
    p = load_profile(uid)
    p["level"] = txt.capitalize()
    p["onboarding_step"] = "done"
    if not p.get("hku_id"):
        p["hku_id"] = allocate_user_id(uid)
    save_profile(uid, p)
    bot.reply_to(message,
        f"✅ *Profile saved*\n\n"
        f"👤 {p['name']}\n"
        f"🏫 {p['institute']}\n"
        f"🎓 {p['level']}\n"
        f"🆔 Your Hamilton ID: *{p['hku_id']}*\n\n"
        "Now let's set up your exam plan.\n"
        "Type /mode to begin.",
        reply_markup=telebot.types.ReplyKeyboardRemove(),
        parse_mode="Markdown")
    try_send_sticker(uid, "welcome")


# ==========================================================
# /mode
# ==========================================================
@bot.message_handler(commands=['mode'])
def cmd_mode(message):
    uid = message.chat.id
    p = load_profile(uid)
    if not p or not p.get("secured"):
        bot.reply_to(message, "🔒 Activate first.")
        return
    if p.get("exams") and p.get("target_year"):
        current = ", ".join(EXAM_NAMES[e] for e in p["exams"])
        msg = bot.reply_to(message,
            f"🎯 *Current setup:*\n"
            f"Exams: {current}\n"
            f"Priority: {EXAM_NAMES.get(p.get('priority','—'), '—')}\n"
            f"Year: {p.get('target_year')}\n\n"
            "Change setup? Type *YES* or *NO*.",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, _mode_confirm)
        return
    _mode_start(uid)


def _mode_confirm(message):
    uid = message.chat.id
    if (message.text or "").strip().lower() == "yes":
        _mode_start(uid)
    else:
        bot.reply_to(message, "✅ Setup unchanged.")


def _mode_start(uid):
    msg = bot.send_message(uid,
        "🎯 *Choose your target exam(s):*\n\n"
        "*A* → JEE Advanced\n*B* → JEE Mains\n*C* → EAMCET\n\n"
        "Reply combo: `A`, `B`, `C`, `AB`, `BC`, `AC`, `ABC`",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, _mode_exams)


def _mode_exams(message):
    uid = message.chat.id
    p = load_profile(uid)
    txt = (message.text or "").strip().upper()
    sel = [EXAM_OPTIONS[c] for c in txt if c in EXAM_OPTIONS]
    if not sel:
        bot.reply_to(message, "❌ Invalid. Send A, B, C, AB, BC, AC or ABC.")
        return
    p["exams"] = sel
    p["priority"] = None
    p["priority_pct"] = 100
    p["target_year"] = None
    p["target_marks"] = {}
    save_profile(uid, p)
    if len(sel) == 1:
        p["priority"] = sel[0]
        p["priority_pct"] = 100
        save_profile(uid, p)
        _mode_ask_year(uid)
        return
    names = " / ".join(EXAM_NAMES[e] for e in sel)
    msg = bot.reply_to(message,
        f"🎯 Active: {names}\n\n*Which is PRIMARY?* Reply exact name.",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, _mode_priority)


def _mode_priority(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip()
    chosen = next((e for e in p["exams"] if EXAM_NAMES[e].lower() == t.lower()), None)
    if not chosen:
        bot.reply_to(message, "❌ Not recognised.")
        return
    p["priority"] = chosen
    save_profile(uid, p)
    msg = bot.reply_to(message,
        f"✅ Primary: {EXAM_NAMES[chosen]}\n\n"
        "*Priority focus %?* Reply 100/80/70/60/50 or number 50–100",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, _mode_pct)


def _mode_pct(message):
    uid = message.chat.id
    p = load_profile(uid)
    try:
        pct = int((message.text or "").strip())
        if pct < 50 or pct > 100:
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Send 50–100.")
        return
    p["priority_pct"] = pct
    save_profile(uid, p)
    _mode_ask_year(uid)


def _mode_ask_year(uid):
    current = datetime.now().year
    max_yr = current + MAX_FUTURE_YEARS
    msg = bot.send_message(uid,
        f"📅 *Which YEAR are you targeting?*\n\n"
        f"Type year (e.g., `{current+1}`). Range: {current}–{max_yr}",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, _mode_year)


def _mode_year(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip()
    current = datetime.now().year
    max_yr = current + MAX_FUTURE_YEARS
    if not t.isdigit():
        bot.reply_to(message, f"❌ Type a year like {current+1}.")
        return
    yr = int(t)
    if yr < current:
        bot.reply_to(message, f"❌ That year passed. Try {current+1}+.")
        return
    if yr > max_yr:
        bot.reply_to(message, f"🤔 Seriously? Max {max_yr}.")
        return
    p["target_year"] = yr
    save_profile(uid, p)
    _mode_start_marks(uid)


def _mode_start_marks(uid):
    p = load_profile(uid)
    p["_marks_queue"] = list(p["exams"])
    p["target_marks"] = {}
    save_profile(uid, p)
    _mode_ask_next_mark(uid)


def _mode_ask_next_mark(uid):
    p = load_profile(uid)
    queue = p.get("_marks_queue", [])
    if not queue:
        _mode_finish(uid)
        return
    exam = queue.pop(0)
    p["_marks_queue"] = queue
    save_profile(uid, p)
    max_m = MAX_MARKS.get(exam, 100)
    msg = bot.send_message(uid,
        f"🎯 *Expected marks for {EXAM_NAMES[exam]}?*\n\n"
        f"Max: *{max_m}*\nType your expected marks.",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, _mode_capture_marks, exam, max_m)


def _mode_capture_marks(message, exam, max_m):
    uid = message.chat.id
    p = load_profile(uid)
    try:
        val = int((message.text or "").strip())
        if val < 0 or val > max_m:
            raise ValueError
    except ValueError:
        bot.reply_to(message, f"❌ Send 0–{max_m}.")
        p["_marks_queue"].insert(0, exam)
        save_profile(uid, p)
        _mode_ask_next_mark(uid)
        return
    p.setdefault("target_marks", {})
    p["target_marks"][exam] = val
    save_profile(uid, p)
    _mode_ask_next_mark(uid)


def _mode_finish(uid):
    p = load_profile(uid)
    names = ", ".join(EXAM_NAMES[e] for e in p["exams"])
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "   ✅ *SETUP COMPLETE*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"👤 {p['name']}",
        f"🏫 {p['institute']}",
        f"🎓 {p['level']}",
        f"🆔 {p.get('hku_id', '—')}",
        "",
        f"📚 Exams: {names}",
    ]
    if p.get("priority") and len(p["exams"]) > 1:
        lines.append(f"🎯 Priority: {EXAM_NAMES[p['priority']]} ({p['priority_pct']}%)")
    lines.append(f"📅 Target year: {p['target_year']}")
    targets = p.get("target_marks", {})
    if targets:
        lines.append("")
        lines.append("🎯 Expected marks:")
        for e in p["exams"]:
            if e in targets:
                max_m = MAX_MARKS.get(e, 100)
                lines.append(f"   {EXAM_NAMES[e]}: {targets[e]} / {max_m}")
    lines += [
        "",
        "Next steps:",
        "👉 /select — pick chapters",
        "👉 /exam — start practice",
        "👉 /health — see progress",
    ]
    bot.send_message(uid, "\n".join(lines),
                     reply_markup=telebot.types.ReplyKeyboardRemove(),
                     parse_mode="Markdown")


# ==========================================================
# /status
# ==========================================================
@bot.message_handler(commands=['status'])
def cmd_status(message):
    uid = message.chat.id
    p = load_profile(uid)
    if not p or not p.get("secured"):
        bot.reply_to(message, "🔒 Not activated.")
        return
    lines = ["📊 *Your Status*\n"]
    lines.append(f"👤 {p.get('name', '—')}")
    lines.append(f"🏫 {p.get('institute', '—')}")
    lines.append(f"🎓 {p.get('level', '—')}")
    lines.append(f"🆔 {p.get('hku_id', '—')}")
    lines.append("")
    if p.get("exams"):
        lines.append(f"📚 Exams: {', '.join(EXAM_NAMES.get(e,e) for e in p['exams'])}")
    if p.get("target_year"):
        lines.append(f"📅 Year: {p['target_year']}")
    if p.get("target_marks"):
        lines.append("🎯 Targets:")
        for e, m in p["target_marks"].items():
            max_m = MAX_MARKS.get(e, 100)
            lines.append(f"   {EXAM_NAMES.get(e,e)}: {m} / {max_m}")
    if p.get("selected_chapters"):
        lines.append("")
        lines.append("📖 Selected chapters:")
        for s, chs in p["selected_chapters"].items():
            lines.append(f"   {s}: {len(chs)} chapters")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 2 loaded: start, onboarding, mode, status ready.")
