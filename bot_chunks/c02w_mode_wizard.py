# ==========================================================
# c02w_mode_wizard.py — /mode exam configuration wizard v2
# Flow: summary → confirm → one-by-one → save
# ==========================================================
import admin_auth as _mw_auth

_MODE_WIZARD_STATE = {}


def _mw_exams_list():
    try:
        from config import EXAM_NAMES
        return list(EXAM_NAMES.items())
    except Exception:
        return [("JEE_ADV", "JEE Advanced"), ("JEE_MAIN", "JEE Mains"), ("EAMCET", "EAMCET")]


def _mw_exam_name(key):
    for k, v in _mw_exams_list():
        if k == key:
            return v
    return key


def _mw_exam_total(key):
    totals = {"JEE_ADV": 360, "JEE_MAIN": 300, "EAMCET": 160}
    return totals.get(key, 100)


def _mw_build_summary(uid, p):
    """Build the 'confirm or change' summary."""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    exams = p.get("exams") or []
    prio = p.get("priority")
    pct = p.get("priority_pct", 70)
    marks = p.get("target_marks") or {}
    year = p.get("target_year")
    if not exams:
        return None, None
    lines = ["📋 *Your Current Exam Config*", ""]
    lines.append(f"🎯 *Priority:* {_mw_exam_name(prio)} ({pct}% focus)")
    lines.append(f"📅 *Year:* {year}")
    lines.append("")
    lines.append("*Exams & target marks:*")
    for k in exams:
        name = _mw_exam_name(k)
        m = marks.get(k, 0)
        total = _mw_exam_total(k)
        star = "⭐ " if k == prio else "   "
        lines.append(f"{star}{name}: *{m}/{total}*")
    lines.append("")
    lines.append("_Keep this configuration or change it?_")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Keep", callback_data="mw_keep"),
        InlineKeyboardButton("✏️ Change", callback_data="mw_change"),
    )
    return text, kb


@bot.message_handler(commands=['mode'])
def _mw_cmd_mode(message):
    uid = message.chat.id
    try:
        ready, reason = _profile_ready(uid)
        if not ready:
            _send_setup_prompt(uid, reason)
            return
    except Exception as _e:
        print(f"[mw-mode] profile err: {_e}")
    p = load_profile(uid)
    exams = p.get("exams") or []
    year = p.get("target_year")

    # If already configured → show summary with Keep/Change
    if exams and year:
        text, kb = _mw_build_summary(uid, p)
        bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb)
        print(f"[mw] {uid} → summary shown")
        return

    # No config yet → go straight into change flow
    _mw_start_change(uid)


@bot.callback_query_handler(func=lambda c: c.data == "mw_keep")
def _mw_cb_keep(call):
    uid = call.from_user.id
    try:
        bot.edit_message_text(
            "✅ *Configuration unchanged.*\n\n_Tip: use /exam for quick practice._",
            chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown"
        )
    except Exception:
        pass
    bot.answer_callback_query(call.id, "Kept")


@bot.callback_query_handler(func=lambda c: c.data == "mw_change")
def _mw_cb_change(call):
    uid = call.from_user.id
    try:
        bot.edit_message_text(
            "✏️ *Reconfiguring...*\n\nStarting fresh.",
            chat_id=uid, message_id=call.message.message_id
        )
    except Exception:
        pass
    _mw_start_change(uid)


def _mw_start_change(uid):
    """Begin wizard — Step 1: select exams."""
    p = load_profile(uid)
    existing = set(p.get("exams") or [])
    _MODE_WIZARD_STATE[uid] = {
        "step": "select",
        "selected": existing,
        "priority": p.get("priority"),
        "priority_pct": p.get("priority_pct", 70),
        "target_marks": dict(p.get("target_marks") or {}),
        "target_year": p.get("target_year"),
    }
    _mw_show_select(uid)


def _mw_build_selector(selected):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    exams = _mw_exams_list()
    buttons = []
    for key, name in exams:
        mark = "✅ " if key in selected else "⬜ "
        buttons.append(InlineKeyboardButton(f"{mark}{name}", callback_data=f"mw_toggle:{key}"))
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            kb.row(buttons[i], buttons[i + 1])
        else:
            kb.row(buttons[i])
    kb.add(InlineKeyboardButton("✅ Done", callback_data="mw_done"))
    return kb


def _mw_build_selector_text(selected):
    lines = ["📚 *Configure Your Exams*", ""]
    lines.append("*Step 1/5 — Which exams are you writing?*")
    lines.append("_Tap to toggle. Select at least one._")
    lines.append("")
    if selected:
        lines.append(f"Selected: *{len(selected)}*")
        for k in sorted(selected):
            lines.append(f"  • {_mw_exam_name(k)}")
    else:
        lines.append("_Nothing selected yet._")
    return "\n".join(lines)


def _mw_show_select(uid, msg_id=None):
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    st["step"] = "select"
    _MODE_WIZARD_STATE[uid] = st
    text = _mw_build_selector_text(st["selected"])
    kb = _mw_build_selector(st["selected"])
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id=uid, message_id=msg_id, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    else:
        safe_send(uid, text, parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mw_toggle:"))
def _mw_cb_toggle(call):
    uid = call.from_user.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        bot.answer_callback_query(call.id, "Send /mode again")
        return
    try:
        key = call.data.split(":")[1]
    except Exception:
        return
    sel = st["selected"]
    if key in sel:
        sel.remove(key)
    else:
        sel.add(key)
    st["selected"] = sel
    _MODE_WIZARD_STATE[uid] = st
    try:
        bot.edit_message_text(
            _mw_build_selector_text(sel),
            chat_id=uid, message_id=call.message.message_id,
            reply_markup=_mw_build_selector(sel), parse_mode="Markdown"
        )
    except Exception:
        pass
    bot.answer_callback_query(call.id, f"{len(sel)} selected")


@bot.callback_query_handler(func=lambda c: c.data == "mw_done")
def _mw_cb_done(call):
    uid = call.from_user.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    sel = st["selected"]
    if not sel:
        bot.answer_callback_query(call.id, "Select at least one exam")
        return
    if len(sel) == 1:
        only = list(sel)[0]
        st["priority"] = only
        st["priority_pct"] = 100
        _MODE_WIZARD_STATE[uid] = st
        _mw_ask_marks(uid, call.message.message_id)
        return
    # Ask priority
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    for k in sorted(sel):
        kb.add(InlineKeyboardButton(_mw_exam_name(k), callback_data=f"mw_prio:{k}"))
    text = (
        "📚 *Step 2/5 — Priority Exam*\n\n"
        "_Notes, plan & short notes will focus on this exam._\n\n"
        "Which exam is your main focus?"
    )
    st["step"] = "priority"
    _MODE_WIZARD_STATE[uid] = st
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("mw_prio:"))
def _mw_cb_prio(call):
    uid = call.from_user.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    try:
        key = call.data.split(":")[1]
    except Exception:
        return
    st["priority"] = key
    st["step"] = "await_pct"
    _MODE_WIZARD_STATE[uid] = st
    text = (
        f"📚 *Step 3/5 — Priority Percentage*\n\n"
        f"You picked *{_mw_exam_name(key)}* as priority.\n\n"
        f"How much *%* of your study time should go to this exam?\n"
        f"_Example: 70_"
    )
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except Exception:
        safe_send(uid, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: (
    m.chat.id in _MODE_WIZARD_STATE and
    _MODE_WIZARD_STATE[m.chat.id].get("step") == "await_pct"
), content_types=['text'])
def _mw_catch_pct(message):
    uid = message.chat.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        _MODE_WIZARD_STATE.pop(uid, None)
        return
    try:
        pct = int(txt)
        if pct < 1 or pct > 100:
            bot.reply_to(message, "Enter a number 1–100:")
            return
    except Exception:
        bot.reply_to(message, "Enter a number 1–100:")
        return
    st["priority_pct"] = pct
    st["step"] = "marks"
    st["marks_queue"] = sorted(st["selected"])
    _MODE_WIZARD_STATE[uid] = st
    _mw_ask_marks(uid)


def _mw_ask_marks(uid, msg_id=None):
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    queue = st.get("marks_queue") or []
    if not queue:
        _mw_ask_year(uid, msg_id)
        return
    cur = queue[0]
    total = _mw_exam_total(cur)
    name = _mw_exam_name(cur)
    text = (
        f"📚 *Step 4/5 — Target Marks*\n\n"
        f"{name}: out of *{total}*\n\n"
        f"Enter your target marks (1–{total}):"
    )
    st["step"] = "await_mark"
    _MODE_WIZARD_STATE[uid] = st
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id=uid, message_id=msg_id, parse_mode="Markdown")
        except Exception:
            pass
    else:
        safe_send(uid, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: (
    m.chat.id in _MODE_WIZARD_STATE and
    _MODE_WIZARD_STATE[m.chat.id].get("step") == "await_mark"
), content_types=['text'])
def _mw_catch_mark(message):
    uid = message.chat.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        _MODE_WIZARD_STATE.pop(uid, None)
        return
    queue = st.get("marks_queue") or []
    if not queue:
        return
    cur = queue[0]
    total = _mw_exam_total(cur)
    try:
        val = int(txt)
        if val < 1 or val > total:
            bot.reply_to(message, f"Enter 1–{total}:")
            return
    except Exception:
        bot.reply_to(message, f"Enter 1–{total}:")
        return
    st["target_marks"][cur] = val
    st["marks_queue"] = queue[1:]
    _MODE_WIZARD_STATE[uid] = st
    _mw_ask_marks(uid)


def _mw_ask_year(uid, msg_id=None):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    st["step"] = "await_year"
    _MODE_WIZARD_STATE[uid] = st
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("2027", callback_data="mw_year:2027"),
        InlineKeyboardButton("2028", callback_data="mw_year:2028"),
        InlineKeyboardButton("2029", callback_data="mw_year:2029"),
    )
    text = (
        "📚 *Step 5/5 — Target Year*\n\n"
        "Which year are you writing the exam?"
    )
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id=uid, message_id=msg_id, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    else:
        safe_send(uid, text, parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mw_year:"))
def _mw_cb_year(call):
    uid = call.from_user.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    try:
        year = int(call.data.split(":")[1])
    except Exception:
        return
    p = load_profile(uid)
    p["exams"] = sorted(st["selected"])
    p["priority"] = st["priority"]
    p["priority_pct"] = st["priority_pct"]
    p["target_marks"] = st["target_marks"]
    p["target_year"] = year
    save_profile(uid, p)
    _MODE_WIZARD_STATE.pop(uid, None)
    prio_name = _mw_exam_name(st["priority"])
    lines = ["✅ *Configuration Saved!*", ""]
    lines.append(f"🎯 *Priority:* {prio_name} ({st['priority_pct']}%)")
    lines.append(f"📅 *Year:* {year}")
    lines.append("")
    lines.append("*Exams & targets:*")
    for k in sorted(st["selected"]):
        name = _mw_exam_name(k)
        marks = st["target_marks"].get(k, 0)
        total = _mw_exam_total(k)
        star = "⭐" if k == st["priority"] else "  "
        lines.append(f"{star} {name}: *{marks}/{total}*")
    lines.append("")
    lines.append("_Type /mode anytime to view or change._")
    text = "\n".join(lines)
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except Exception:
        safe_send(uid, text, parse_mode="Markdown")
    print(f"[mw] {uid} saved: exams={p['exams']} prio={p['priority']} pct={st['priority_pct']} year={year}")


print("c02w_mode_wizard: loaded (v2).")
