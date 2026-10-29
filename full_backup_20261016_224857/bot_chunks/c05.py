from ai_client import convert_latex_envs
# ==========================================================
# bot.py — Chunk 5: poll handlers, practice feedback, doubt border
# ==========================================================

# ==========================================================
# INLINE BUTTON HELPERS
# ==========================================================
def _practice_footer_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("▶️ Continue", callback_data="prac_continue"),
        telebot.types.InlineKeyboardButton("🔖 Bookmark", callback_data="prac_bookmark"),
        telebot.types.InlineKeyboardButton("⏹ Stop", callback_data="prac_stop"),
    )
    return markup


def _test_footer_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("⏹ Stop Test", callback_data="test_stop"),
    )
    return markup


def _concept_footer_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("⏹ Stop Test", callback_data="concept_stop"),
    )
    return markup


def _doubt_continue_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("▶️ Continue to next question",
                                            callback_data="prac_continue"),
        telebot.types.InlineKeyboardButton("⏹ Stop Practice",
                                            callback_data="prac_stop"),
    )
    return markup


# ==========================================================
# UNIFIED POLL HANDLER
# ==========================================================
@bot.poll_answer_handler()
def on_poll_answer(poll_answer):
    uid = poll_answer.user.id
    sess = exam_engine.get_session(uid)
    if not sess:
        return
    mode = sess.get("mode", "practice")
    if mode == "practice":
        _handle_practice_poll(uid, sess, poll_answer)
    elif mode == "test":
        _handle_test_poll(uid, sess, poll_answer)
    elif mode == "conceptual":
        _handle_conceptual_poll(uid, sess, poll_answer)


# ==========================================================
# HEALTH DELTA HELPERS
# ==========================================================
def _record_and_delta(uid, subject, chapter, subtopic, concept, correct,
                       time_taken, ideal_time, difficulty):
    p = load_profile(uid) or {}
    key = f"{subject}::{chapter}::{subtopic}"
    before = p.get("subtopic_stats", {}).get(key, {}).get("health")
    _, after = health.record_attempt(uid, subject, chapter, subtopic, concept,
                                      correct, int(time_taken), ideal_time,
                                      difficulty=difficulty)
    return before, after


def _health_delta_text(before, after):
    if after is None:
        return ""
    if before is None:
        return f"\n📊 Health: *{after}/100* (first attempt)"
    delta = round(after - before, 1)
    sign = "+" if delta >= 0 else ""
    return f"\n📊 Health: {before} → *{after}* ({sign}{delta})"


# ==========================================================
# PRACTICE POLL HANDLER
# ==========================================================
def _handle_practice_poll(uid, sess, poll_answer):
    q = sess.get("current_q")
    if not q:
        return
    timer_manager.stop_question_timer(bot, uid)
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    options = q.get("options", [])
    time_taken = time.time() - sess.get("current_started", time.time())
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["questions_done"] = sess.get("questions_done", 0) + 1

    meta = sess.get("current_meta", {})
    subj = meta.get("subject", "")
    chapter = meta.get("chapter", "")
    subtopic = meta.get("subtopic", "")
    difficulty = q.get("difficulty", "medium")

    # ============ SKIP ============
    if selected == len(options):
        sess["skipped"] = sess.get("skipped", 0) + 1
        try:
            before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                               False, time_taken,
                                               int(q.get("ideal_time_sec", 60)),
                                               difficulty)
            delta_str = _health_delta_text(before, after)
        except Exception:
            delta_str = ""
        msg = (
            f"🚪 *Skipped*\n\n"
            f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 60)}s)\n\n"
            f"📖 *Solution:*\n{convert_latex_envs(q.get('explanation', '(none)'))}\n\n"
            f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
            + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}\n"
            + delta_str
        )
        safe_send(uid, msg + _countdown_footer(uid),
                  parse_mode="Markdown",
                  reply_markup=_practice_footer_buttons())
        sess["last_q"] = q
        sess["last_meta"] = meta
        sess["current_q"] = None
        return

    # ============ ANSWER ============
    correct = (int(selected) == int(q.get("correct_index", -1)))
    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    try:
        before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                           correct, time_taken,
                                           int(q.get("ideal_time_sec", 60)),
                                           difficulty)
        delta_str = _health_delta_text(before, after)

        # SVG bar
        if SVG_ENABLED and before is not None and after is not None:
            svg = svg_templates.health_delta_bar(subtopic or "Subtopic", before, after)
            path = svg_renderer.render_svg(svg, name=f"hd_{uid}_{int(time.time())}")
            if path:
                safe_send_photo(uid, path)
                svg_renderer.cleanup_file(path)
    except Exception:
        delta_str = ""

    if correct:
        head = "✅ *Correct!*"
    else:
        user_letter = chr(65 + int(selected)) if 0 <= selected <= 25 else "?"
        correct_letter = chr(65 + int(q.get("correct_index", 0)))
        head = f"❌ *Wrong* — You chose *{user_letter}*, correct is *{correct_letter}*"

    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal: {q.get('ideal_time_sec', 60)}s)\n\n"
        f"📖 *Solution:*\n{convert_latex_envs(q.get('explanation', ''))}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}\n"
        + delta_str
    )
    safe_send(uid, msg + _countdown_footer(uid),
              parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    sess["last_q"] = q
    sess["last_meta"] = meta
    sess["current_q"] = None


# ==========================================================
# NUMERICAL ANSWER HANDLER
# ==========================================================
def _handle_numerical_answer(uid, text):
    pending = PENDING_NUMERICAL.pop(uid, None)
    if not pending:
        return
    timer_manager.stop_question_timer(bot, uid)
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]

    sess = exam_engine.get_session(uid)
    if not sess:
        return
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["questions_done"] = sess.get("questions_done", 0) + 1

    try:
        val = float(text.replace(",", "").replace(" ", "").strip())
    except Exception:
        PENDING_NUMERICAL[uid] = pending
        safe_send(uid, "⚠️ Please send a valid number.")
        return

    correct_val = q.get("correct_value", 0)
    try:
        correct = abs(val - float(correct_val)) < 1e-6
    except Exception:
        correct = False

    subj = meta.get("subject", "")
    chapter = meta.get("chapter", "")
    subtopic = meta.get("subtopic", "")
    difficulty = q.get("difficulty", "medium")

    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    try:
        before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                           correct, time_taken,
                                           int(q.get("ideal_time_sec", 90)),
                                           difficulty)
        delta_str = _health_delta_text(before, after)
    except Exception:
        delta_str = ""

    if correct:
        head = "✅ *Correct!*"
    else:
        head = f"❌ *Wrong* — correct value: *{correct_val}*"

    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 90)}s)\n"
        f"Your answer: `{text}`\n\n"
        f"📖 *Solution:*\n{convert_latex_envs(q.get('explanation', ''))}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}\n"
        + delta_str
    )
    safe_send(uid, msg + _countdown_footer(uid),
              parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    sess["last_q"] = q
    sess["last_meta"] = meta
    sess["current_q"] = None


# ==========================================================
# INLINE CALLBACKS — practice
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "prac_continue")
def _cb_prac_continue(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass
    if exam_engine.get_session(uid):
        _send_next_practice(uid)
    else:
        safe_send(uid, "Session ended. Use /exam to start again.")


@bot.callback_query_handler(func=lambda c: c.data == "prac_bookmark")
def _cb_prac_bookmark(call):
    uid = call.message.chat.id
    sess = exam_engine.get_session(uid)
    if not sess or not sess.get("last_q"):
        bot.answer_callback_query(call.id, "No question to bookmark.")
        return
    bpath = os.path.join(BOOKMARK_DIR, f"{uid}.json")
    bm = []
    if os.path.exists(bpath):
        try:
            with open(bpath) as f:
                bm = json.load(f)
        except Exception:
            bm = []
    q = sess["last_q"]
    entry = {
        "timestamp": datetime.now().isoformat(),
        "subject": sess.get("last_meta", {}).get("subject", ""),
        "chapter": sess.get("last_meta", {}).get("chapter", ""),
        "subtopic": sess.get("last_meta", {}).get("subtopic", ""),
        "question": q.get("question", ""),
        "options": q.get("options", []),
        "correct_index": q.get("correct_index"),
        "explanation": q.get("explanation", ""),
    }
    if any(b.get("question") == entry["question"] for b in bm):
        bot.answer_callback_query(call.id, "Already bookmarked.")
        return
    bm.append(entry)
    with open(bpath, "w") as f:
        json.dump(bm, f, indent=2, ensure_ascii=False)
    bot.answer_callback_query(call.id, f"Bookmarked! Total: {len(bm)}")


@bot.callback_query_handler(func=lambda c: c.data == "prac_stop")
def _cb_prac_stop(call):
    uid = call.message.chat.id
    _do_stop(uid)
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass


# ==========================================================
# NEXT / BOOKMARK / STOP (text commands)
# ==========================================================
@bot.message_handler(commands=['next'])
def cmd_next(message):
    uid = message.chat.id
    PENDING_NUMERICAL.pop(uid, None)
    timer_manager.stop_question_timer(bot, uid)
    sess = exam_engine.get_session(uid)
    if not sess:
        bot.reply_to(message, "Start with /exam first.")
        return
    if sess.get("mode") == "practice":
        _send_next_practice(uid)
    else:
        bot.reply_to(message, "Use the buttons to continue.")


@bot.message_handler(commands=['bookmark'])
def cmd_bookmark(message):
    uid = message.chat.id
    sess = exam_engine.get_session(uid)
    if not sess or not sess.get("last_q"):
        bot.reply_to(message, "No recent question to bookmark.")
        return
    bpath = os.path.join(BOOKMARK_DIR, f"{uid}.json")
    bm = []
    if os.path.exists(bpath):
        try:
            with open(bpath) as f:
                bm = json.load(f)
        except Exception:
            bm = []
    q = sess["last_q"]
    entry = {
        "timestamp": datetime.now().isoformat(),
        "subject": sess.get("last_meta", {}).get("subject", ""),
        "chapter": sess.get("last_meta", {}).get("chapter", ""),
        "subtopic": sess.get("last_meta", {}).get("subtopic", ""),
        "question": q.get("question", ""),
        "options": q.get("options", []),
        "correct_index": q.get("correct_index"),
        "explanation": q.get("explanation", ""),
    }
    if any(b.get("question") == entry["question"] for b in bm):
        bot.reply_to(message, "🔖 Already bookmarked.")
        return
    bm.append(entry)
    with open(bpath, "w") as f:
        json.dump(bm, f, indent=2, ensure_ascii=False)
    bot.reply_to(message, f"🔖 Bookmarked! You have {len(bm)} saved.")


@bot.message_handler(commands=['bookmarks'])
def cmd_bookmarks(message):
    uid = message.chat.id
    bpath = os.path.join(BOOKMARK_DIR, f"{uid}.json")
    if not os.path.exists(bpath):
        bot.reply_to(message, "📭 No bookmarks yet.")
        return
    with open(bpath) as f:
        bm = json.load(f)
    if not bm:
        bot.reply_to(message, "📭 No bookmarks yet.")
        return
    lines = [f"🔖 *Bookmarks* ({len(bm)})\n"]
    for i, b in enumerate(bm[:15], 1):
        lines.append(f"{i}. [{b.get('subject','?')} · {b.get('chapter','?')[:25]}]")
        lines.append(f"   {b.get('question','')[:70]}...")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    uid = message.chat.id
    _do_stop(uid)


def _do_stop(uid):
    p = load_profile(uid)
    timer_manager.stop_all_timers(bot, uid)
    PENDING_NUMERICAL.pop(uid, None)
    sess = exam_engine.get_session(uid)
    if not sess:
        if p and p.get("_practice_active"):
            p["_practice_active"] = False
            save_profile(uid, p)
        safe_send(uid, "No active session.")
        return
    if p:
        p["_practice_active"] = False
        save_profile(uid, p)

    mode = sess.get("mode", "practice")
    if mode == "conceptual":
        safe_send(uid, exam_engine.conceptual_report(uid), parse_mode="Markdown")
    elif mode == "test":
        _test_finish(uid)
        return
    else:
        safe_send(uid, exam_engine.session_report(uid), parse_mode="Markdown")

    exam_engine.end_session(uid)
    PRELOAD_QUEUE.pop(uid, None)
    WAITING_DOUBT.pop(uid, None)


print("bot.py Chunk 5 loaded: practice handlers + doubt border ready.")
