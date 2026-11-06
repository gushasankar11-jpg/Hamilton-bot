# ==========================================================
# bot.py — Chunk 3: select, health, plan, target, graph
# ==========================================================

@bot.message_handler(commands=['select'])
def cmd_select(message):
    if message.text and message.text.startswith('/plan'):
        return
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    subjects = health.available_subjects()
    if not subjects:
        bot.reply_to(message, "❌ No subjects available.")
        return
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for s in subjects:
        markup.add(s)
    msg = bot.send_message(uid,
        "🎯 *Which subject do you want to select chapters for?*",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _select_subject)


def _select_subject(message):
    uid = message.chat.id
    p = load_profile(uid)
    subj = (message.text or "").strip().capitalize()
    if subj not in health.available_subjects():
        bot.reply_to(message, f"❌ Not available. Try: {', '.join(health.available_subjects())}")
        return
    exam = health.exam_of(p)
    if not exam:
        bot.reply_to(message, "⚠️ Set exam first with /mode.")
        return
    data = health.load_subject_data(subj, exam)
    if not data:
        bot.reply_to(message, f"❌ No data for {subj}.")
        return
    chapter_list = list(data.keys())
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(chapter_list))
    header = f"📚 *{subj}* — {len(chapter_list)} chapters\n\n"
    footer = "\n\nReply numbers `1,4,7,12` or `ALL`."
    full = header + numbered + footer
    if len(full) > 4000:
        safe_send(uid, header + "_(list below)_", parse_mode="Markdown")
        safe_send(uid, numbered[:3900])
        msg = bot.send_message(uid, footer.strip())
        bot.register_next_step_handler(msg, _select_chapters, subj, chapter_list)
    else:
        msg = bot.send_message(uid, full,
                               reply_markup=telebot.types.ReplyKeyboardRemove(),
                               parse_mode="Markdown")
        bot.register_next_step_handler(msg, _select_chapters, subj, chapter_list)


def _select_chapters(message, subj, chapter_list):
    uid = message.chat.id
    p = load_profile(uid)
    txt = (message.text or "").strip()
    if txt.upper() == "ALL":
        chosen = chapter_list
    else:
        try:
            idxs = [int(x.strip()) - 1 for x in txt.split(",") if x.strip()]
            chosen = [chapter_list[i] for i in idxs if 0 <= i < len(chapter_list)]
        except Exception:
            bot.reply_to(message, "❌ Invalid. Try /select again.")
            return
    if not chosen:
        bot.reply_to(message, "❌ No valid chapters.")
        return
    p.setdefault("selected_chapters", {})
    p["selected_chapters"][subj] = chosen
    save_profile(uid, p)
    safe_send(uid,
        f"✅ *{subj}: {len(chosen)} chapters selected*\n\n"
        "Add more with /select, or view progress with /health.",
        parse_mode="Markdown")


# ==========================================================
# /health
# ==========================================================
@bot.message_handler(commands=['health'])
def cmd_health(message):
    if message.text and message.text.startswith('/plan'):
        return
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) > 1:
        subj = parts[1].strip().capitalize()
        if subj not in health.available_subjects():
            bot.reply_to(message, f"❌ '{subj}' not available.")
            return
        exam = health.exam_of(p)
        ch_map = health.chapter_health_map(p, subj, exam, only_selected=False)
        lines = [f"📗 *{subj}* — Chapter Health\n"]
        for ch, d in sorted(ch_map.items(),
                            key=lambda x: (x[1]["health"] is None,
                                          x[1]["health"] if x[1]["health"] is not None else 0)):
            h = d["health"]
            hstr = f"{h:.1f}" if h is not None else "—"
            lines.append(f"• {ch[:35]}: {hstr}")
        safe_send(uid, "\n".join(lines), parse_mode="Markdown")
        return

    r = health.overall_health(p)
    days_left = None
    if p.get("priority") and p.get("target_year"):
        days_left = _days_until_exam(p["priority"], p["target_year"])

    if SVG_ENABLED and r.get("overall") is not None:
        subj_data = {s: d["health"] for s, d in r["subjects"].items()}
        svg = svg_templates.combined_progress(r["overall"], subj_data)
        path = svg_renderer.render_svg(svg, name=f"health_{uid}")
        if path and safe_send_photo(uid, path):
            svg_renderer.cleanup_file(path)
            if days_left is not None:
                safe_send(uid, f"⏳ {days_left} days left for primary exam.",
                          parse_mode="Markdown")
        else:
            if path:
                svg_renderer.cleanup_file(path)
            safe_send(uid, _health_text(r, days_left), parse_mode="Markdown")
    else:
        safe_send(uid, _health_text(r, days_left), parse_mode="Markdown")


def _health_text(r, days_left=None):
    if r.get("overall") is None:
        return "📭 No practice data yet. /exam to start."
    lines = [f"❤️ *Overall: {r['overall']}/100*"]
    if days_left is not None:
        lines.append(f"⏳ {days_left} days left")
    lines.append("")
    for subj, d in r["subjects"].items():
        h = d["health"]
        hstr = f"{h}/100" if h is not None else "Not started"
        lines.append(f"📘 {subj}: {hstr}")
    return "\n".join(lines)


# ==========================================================
# /plan
# ==========================================================
def cmd_plan(message):
    if message.text and message.text.startswith('/plan'):
        return
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    r = health.overall_health(p)
    if r["overall"] is None:
#         bot.reply_to(message, "📭 No data yet. /exam first.")
        return
    primary = p.get("priority") or p["exams"][0]
    lines = ["📋 *YOUR STUDY PLAN*", ""]
    lines.append(f"🎯 *Primary:* {EXAM_NAMES[primary]} {p.get('target_year','')}")
    targets = p.get("target_marks", {})
    if isinstance(targets, dict) and primary in targets:
        max_m = MAX_MARKS.get(primary, 100)
        lines.append(f"Target: {targets[primary]} / {max_m} marks")
    lines.append(f"Current health: *{r['overall']}/100*")
    lines.append("")
    lines.append("📘 *Subject health:*")
    for s, d in r["subjects"].items():
        if d["health"] is not None:
            lines.append(f"   {s}: {d['health']}/100")
    other = [e for e in p["exams"] if e != primary]
    if other:
        lines.append("")
        lines.append("📚 *Secondary exams:*")
        for e in other:
            tag = f" — target {targets.get(e,'—')}" if isinstance(targets, dict) else ""
            lines.append(f"   {EXAM_NAMES[e]}{tag}")
    lines.append("")
    lines.append("Next: /health · /exam · /target")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


# ==========================================================
# /target
# ==========================================================
@bot.message_handler(commands=['target'])
def cmd_target(message):
    if message.text and message.text.startswith('/plan'):
        return
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    p["_marks_queue"] = list(p["exams"])
    save_profile(uid, p)
    _mode_ask_next_mark(uid)


# ==========================================================
# /graph
# ==========================================================
@bot.message_handler(commands=['graph'])
def cmd_graph(message):
    if message.text and message.text.startswith('/plan'):
        return
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    r = health.overall_health(p)
    if r["overall"] is None:
#         bot.reply_to(message, "📭 No data yet. /exam first.")
        return
    subj_data = {s: d["health"] for s, d in r["subjects"].items()}
    svg = svg_templates.combined_progress(r["overall"], subj_data)
    path = svg_renderer.render_svg(svg, name=f"graph_{uid}")
    if path:
        safe_send_photo(uid, path, caption=f"Overall: {r['overall']}/100")
        svg_renderer.cleanup_file(path)
    else:
        safe_send(uid, f"📊 Overall: {r['overall']}/100")


print("bot.py Chunk 3 loaded: select, health, plan, target, graph ready.")
