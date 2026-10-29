# ==========================================================
# bot.py — Chunk 22: Interactive /find + /list_ids (admin)
# ==========================================================

@bot.message_handler(commands=['find'])
def cmd_find(message):
    uid = message.chat.id
    parts = message.text.strip().split()

    # If ID given directly → search
    if len(parts) >= 2:
        _do_find(uid, parts[1].strip().upper())
        return

    # Else → prompt for ID
    msg = bot.send_message(uid,
        "🔍 *Find a user*\n\n"
        "Please enter the user's *HKU ID*.\n"
        "Format: `HKU-XXXXXX` (6 X marks)\n\n"
        "_Type the full ID and send._",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, _find_capture)


def _find_capture(message):
    uid = message.chat.id
    text = (message.text or "").strip().upper()
    if text.startswith("/"):
        # User sent a command instead of ID
        bot.reply_to(message, "❌ Cancelled. Type /find again.")
        return
    _do_find(uid, text)


def _do_find(uid, hku):
    if not hku.startswith("HKU-"):
        safe_send(uid, "❌ ID must start with `HKU-` followed by 6 characters.",
                  parse_mode="Markdown")
        return

    found_uid = find_user_by_hku_id(hku)
    if not found_uid:
        safe_send(uid,
            f"❌ No user found with ID `{hku}`.\n\n"
            "_Send the ID exactly as printed (uppercase, with the HKU- prefix)._",
            parse_mode="Markdown")
        return

    try:
        target = load_profile(int(found_uid))
    except Exception:
        target = load_profile(found_uid)

    if not target or not target.get("secured"):
        safe_send(uid, "❌ Profile not available.")
        return

    stats = _profile_stats(target)

    lines = [
        f"🔍 *Profile — {target.get('name','—')}*",
        "",
        f"🆔 `{hku}`",
        f"🏫 {target.get('institute','—')}",
        f"🎓 {target.get('level','—')}",
        f"📚 {', '.join(EXAM_NAMES.get(e,e) for e in target.get('exams',[]))}",
        f"📅 Year: {target.get('target_year','—')}",
        "",
        "━━━ 📖 Chapters ━━━",
    ]
    for subj, count in stats["chapters_per_subject"].items():
        lines.append(f"   {subj}: {count} chapters")
    lines.append(f"   Total: {stats['total_chapters']}")

    lines += [
        "",
        "━━━ 📊 Attempts (all modes) ━━━",
        f"Total attempted: *{stats['attempts']}*",
        f"✅ Correct: {stats['correct']}",
        f"❌ Wrong: {stats['wrong']}",
        f"🎯 Accuracy: *{stats['accuracy']}%*",
        "",
        "━━━ 🧪 Test History ━━━",
        f"Tests written: *{stats['test_count']}*",
    ]

    for t in stats["tests"][-3:]:
        lines.append(f"   • {t['exam']}: {t['total_score']}/{t['total_max']}")

    lines += [
        "",
        "━━━ ❤️ Health ━━━",
        f"Overall: *{stats['overall_health'] or 0}/100*",
    ]
    for subj, sd in stats["subjects"].items():
        h = sd.get("health")
        if h is not None:
            lines.append(f"   {subj}: {h}/100")

    lines += [
        "",
        "━━━ 🏆 Rank Prediction (from tests) ━━━",
        f"Tier: *{stats['rank_tier']}*",
        f"Percentile: *{stats['percentile']}*",
    ]

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")

    if SVG_ENABLED and stats["overall_health"] is not None:
        subj_data = {s: d.get("health") for s, d in stats["subjects"].items()}
        svg = svg_templates.combined_progress(stats["overall_health"], subj_data)
        path = svg_renderer.render_svg(svg, name=f"find_{found_uid}")
        if path:
            safe_send_photo(uid, path,
                            caption=f"{target.get('name','')} — Progress")
            svg_renderer.cleanup_file(path)


# ----------------------------------------------------------
# ADMIN — /list_ids (see all registered HKU IDs)
# ----------------------------------------------------------
@bot.message_handler(commands=['list_ids'])
def cmd_list_ids(message):
    uid = message.chat.id
    if uid != ADMIN_CHAT_ID:
        return
    data = _load_user_ids()
    mapping = data.get("mapping", {})
    if not mapping:
        bot.reply_to(message, "No users registered yet.")
        return
    lines = [f"📋 *Registered users* ({len(mapping)})\n"]
    for chat_id, hku in sorted(mapping.items(), key=lambda x: x[1]):
        p = load_profile(chat_id)
        name = p.get("name", "—") if p else "—"
        secured = "✅" if (p and p.get("secured")) else "❌"
        lines.append(f"{secured} `{hku}` — {name}")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 22 loaded: interactive /find + /list_ids ready.")

