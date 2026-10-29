# ==========================================================
# bot.py — Chunk 14: Round 1 fixes
# ==========================================================

# ----------------------------------------------------------
# Fix 1: Expanded rich-text detection (catches single * bold too)
# ----------------------------------------------------------
def _looks_like_rich(text):
    if not text:
        return False
    indicators = ["$$", "$", "**", "##", "# ", "\\(", "\\[",
                  "\\frac", "\\tau", "\\int", "\\sum", "\\alpha", "\\beta",
                  "\\vec", "\\sqrt", "\\begin{", "\\end{", "\\sin", "\\cos",
                  "\\theta", "\\mathbf", "\\boldsymbol", "\\times",
                  "\\det", "\\lim", "\\log", "\\pm", "\\infty"]
    return any(ind in text for ind in indicators)


# ----------------------------------------------------------
# Fix 2: Numerical SKIP handling
# ----------------------------------------------------------
def _skip_numerical(uid):
    """User typed 'skip' during a numerical question."""
    pending = PENDING_NUMERICAL.pop(uid, None)
    if not pending:
        return
    timer_manager.stop_question_timer(bot, uid)
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]
    is_test = pending.get("is_test", False)

    sess = exam_engine.get_session(uid)
    if sess:
        sess["skipped"] = sess.get("skipped", 0) + 1
        sess["questions_done"] = sess.get("questions_done", 0) + 1
        sess["total_time"] = sess.get("total_time", 0) + time_taken
        if sess.get("mode") == "test":
            sess["plan_index"] = sess.get("plan_index", 0) + 1
            sess.setdefault("answers_log", []).append({
                "q": q, "meta": meta, "q_type": "numerical",
                "user_answer": "SKIP", "correct": False,
                "time_taken": time_taken,
            })

    correct_val = q.get("correct_value", "?")

    if is_test:
        # Silent skip — no feedback during test
        if sess:
            sess["current_q"] = None
        _send_next_test_q(uid)
        return

    # Practice / Conceptual: show full solution
    msg = (
        f"🚪 *Skipped*\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 90)}s)\n\n"
        f"🎯 *Correct answer:* `{correct_val}`\n\n"
        f"📖 *Solution:*\n{q.get('explanation', '(none)')}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}"
    )
    safe_send(uid, msg + _countdown_footer(uid), parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    if sess:
        sess["last_q"] = q
        sess["last_meta"] = meta
        sess["current_q"] = None


# ----------------------------------------------------------
# Fix 3: Force rich in solutions (wrap safe_send text in $ if missing)
# ----------------------------------------------------------
_orig_record_and_delta = _record_and_delta
_orig_health_delta_text = _health_delta_text


def _force_math_delims(text):
    """
    If explanation contains raw math like \\frac, \\int without $ delimiters,
    wrap suspicious patterns so rich formatter picks them up.
    """
    if not text or "$" in text:
        return text  # already has math markers or no math
    suspicious = ["\\frac", "\\int", "\\sum", "\\sqrt", "\\tau", "\\theta",
                  "\\alpha", "\\beta", "\\vec", "\\begin{", "\\end{",
                  "\\sin", "\\cos", "\\tan", "\\log", "\\det"]
    for s in suspicious:
        if s in text:
            # Wrap the whole text in $$ to trigger math rendering
            return f"$$\n{text}\n$$"
    return text


# Patch the solution message composition by wrapping safe_send calls.
# Simplest: override _handle_practice_poll and _handle_numerical_answer.
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

    explanation = _force_math_delims(q.get("explanation", ""))
    traps = q.get("traps") or []
    shortcut = q.get("shortcut", "")

    # SKIP
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
            f"📖 *Solution:*\n{explanation}\n\n"
            f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (traps or ["(none)"]))
            + f"\n\n⚡ *Shortcut:* {shortcut or '(none)'}\n"
            + delta_str
        )
        safe_send(uid, msg + _countdown_footer(uid),
                  parse_mode="Markdown",
                  reply_markup=_practice_footer_buttons())
        sess["last_q"] = q
        sess["last_meta"] = meta
        sess["current_q"] = None
        return

    # ANSWER
    correct = (int(selected) == int(q.get("correct_index", -1)))

    guessed = False
    if correct and q.get("logic_type") == "calc":
        min_real = q.get("min_realistic_sec", 20)
        if time_taken < min_real:
            guessed = True

    if guessed:
        delta_str = "\n🚫 *Guessing detected — no health change.*"
        head = "⚠️ *Guessed correctly* — but too fast to be real calculation."
        sess["wrong"] = sess.get("wrong", 0) + 1
    else:
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
            ul = chr(65 + int(selected)) if 0 <= selected <= 25 else "?"
            cl = chr(65 + int(q.get("correct_index", 0)))
            head = f"❌ *Wrong* — You chose *{ul}*, correct is *{cl}*"

    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal: {q.get('ideal_time_sec', 60)}s)\n\n"
        f"📖 *Solution:*\n{explanation}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (traps or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {shortcut or '(none)'}\n"
        + delta_str
    )
    safe_send(uid, msg + _countdown_footer(uid),
              parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    sess["last_q"] = q
    sess["last_meta"] = meta
    sess["current_q"] = None


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
        safe_send(uid, "⚠️ Please send a valid number (or type `skip`).",
                  parse_mode="Markdown")
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
    explanation = _force_math_delims(q.get("explanation", ""))

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
        f"📖 *Solution:*\n{explanation}\n\n"
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


def _handle_test_numerical(uid, text):
    pending = PENDING_NUMERICAL.pop(uid, None)
    if not pending:
        return
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]

    sess = exam_engine.get_session(uid)
    if not sess:
        return

    try:
        val = float(text.replace(",", "").replace(" ", "").strip())
    except Exception:
        PENDING_NUMERICAL[uid] = pending
        safe_send(uid, "⚠️ Please send a valid number (or type `skip`).",
                  parse_mode="Markdown")
        return

    try:
        correct_val = float(q.get("correct_value", 0))
        correct = abs(val - correct_val) < 1e-6
    except Exception:
        correct = False
        correct_val = q.get("correct_value", "?")

    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    sess.setdefault("answers_log", []).append({
        "q": q, "meta": meta, "q_type": "numerical",
        "user_answer": text.strip() or "?",
        "correct": correct, "time_taken": time_taken,
    })
    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["plan_index"] = sess.get("plan_index", 0) + 1

    try:
        health.record_attempt(
            uid, meta.get("subject", ""), meta.get("chapter", ""),
            meta.get("subtopic", ""), "", correct,
            int(time_taken), int(q.get("ideal_time_sec", 90)),
            difficulty=q.get("difficulty", "medium"))
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_test_q(uid)


# ----------------------------------------------------------
# Fix 4: HKU-ID backfill + numerical skip in free_text_handler
# ----------------------------------------------------------
# (duplicate handler disabled — c09 is the active one)
# @bot.message_handler(func=lambda m: True, content_types=['text'])
def free_text_handler(message):
    uid = message.chat.id
    text = (message.text or "").strip()
    if not text:
        return

    p = get_or_create_profile(uid)

    # Admin unblock
    if text.strip() == ADMIN_UNBLOCK_CODE:
        p.setdefault("behavior", {"strikes": 0, "blocked_until": None})
        p["behavior"]["strikes"] = 0
        p["behavior"]["blocked_until"] = None
        save_profile(uid, p)
        bot.reply_to(message, "🔓 *Admin unblock successful.* Strikes reset.",
                     parse_mode="Markdown")
        return

    # Blocked check
    blocked, time_left = check_blocked(uid)
    if blocked:
        safe_send(uid,
            f"⛔ *Blocked*\n\n"
            f"Try again in: *{time_left}*\n\n"
            f"WhatsApp *{WHATSAPP_CONTACT}* for help."
            + _countdown_footer(uid),
            parse_mode="Markdown")
        return

    # Activation gate
    if not p.get("secured"):
        if is_valid_key(text):
            allowed, reason = _check_key_binding(uid, text.strip())
            if not allowed:
                if reason == "other_device":
                    safe_send(uid,
                        "❌ *This key is already activated on another device.*\n\n"
                        f"WhatsApp *{WHATSAPP_CONTACT}* if you need help.",
                        parse_mode="Markdown")
                else:
                    safe_send(uid, "❌ Invalid key.")
                return
            p["secured"] = True
            p["activation_key"] = text.strip()
            p["key_expired"] = False
            p["onboarding_step"] = "name"
            save_profile(uid, p)
            if not p.get("story_shown"):
                safe_send(uid, _hamilton_story(), parse_mode="Markdown")
                p["story_shown"] = True
                save_profile(uid, p)
                time.sleep(1)
            bot.reply_to(message, "✅ *Key confirmed. Let's set up your profile.*",
                         parse_mode="Markdown")
            _run_onboarding(uid)
        else:
            p.setdefault("no_key_attempts", 0)
            p["no_key_attempts"] += 1
            save_profile(uid, p)
            if p["no_key_attempts"] <= 2:
                safe_send(uid, _no_key_message(short=False), parse_mode="Markdown")
            else:
                safe_send(uid, _no_key_message(short=True), parse_mode="Markdown")
        return

    # Expired key check
    if _check_key_expired(uid, p):
        return

    # HKU-ID BACKFILL (fix for existing users)
    if not p.get("hku_id"):
        p["hku_id"] = allocate_user_id(uid)
        save_profile(uid, p)

    # Onboarding gate
    if p.get("onboarding_step") and p["onboarding_step"] != "done":
        _run_onboarding(uid)
        return

    if not p.get("exams"):
        bot.reply_to(message, "🎯 Set exams with /mode first.")
        return

    # ============================================
    # NUMERICAL SKIP CHECK (must be FIRST)
    # ============================================
    if uid in PENDING_NUMERICAL:
        low = text.lower().strip()
        if low in ("skip", "/skip"):
            _skip_numerical(uid)
            return
        # Else treat as numerical answer
        pending = PENDING_NUMERICAL.get(uid)
        if pending and pending.get("is_test"):
            _handle_test_numerical(uid, text)
        else:
            _handle_numerical_answer(uid, text)
        return

    # ============================================
    # SESSION LOCKS (borders)
    # ============================================
    sess = exam_engine.get_session(uid)

    if sess and sess.get("mode") == "test":
        q_done = sess.get("questions_done", 0)
        plan = sess.get("plan", [])
        paper = sess.get("current_paper", 1)
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("⏹ Stop Test",
                                                       callback_data="test_stop"))
        safe_send(uid,
            f"📝 *Test in progress* — Paper {paper}, Q{q_done}/{len(plan)}\n\n"
            f"I can't answer questions during the test.\n"
            f"Finish first, then we can talk.",
            parse_mode="Markdown", reply_markup=markup)
        return

    if sess and sess.get("mode") == "conceptual":
        q_done = sess.get("questions_done", 0)
        plan = sess.get("plan", [])
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("⏹ Stop Test",
                                                       callback_data="concept_stop"))
        safe_send(uid,
            f"🧠 *Conceptual test in progress* — Q{q_done}/{len(plan)}\n\n"
            f"I can't answer questions during the test.",
            parse_mode="Markdown", reply_markup=markup)
        return

    if p.get("_practice_active") and sess and sess.get("mode") == "practice":
        # Practice doubt
        exam = sess.get("exam") or health.exam_of(p) or "JEE_MAIN"
        timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
        try:
            answer = ai_client.ask_hamilton(exam, text)
        except Exception:
            answer = None
        timer_manager.stop_thinking_timer(uid)
        if not answer:
            safe_send(uid, "⚠️ Could not answer. Retry or Continue.")
            return
        svg, clean = svg_renderer.detect_svg_in_text(answer)
        final = "💬 *Your doubt answered:*\n\n" + clean
        safe_send(uid, final + _countdown_footer(uid),
                  parse_mode="Markdown",
                  reply_markup=_doubt_continue_buttons())
        if svg and SVG_ENABLED:
            path = svg_renderer.render_svg(svg, name=f"doubt_{uid}")
            if path:
                safe_send_photo(uid, path)
                svg_renderer.cleanup_file(path)
        return

    if p.get("_practice_active") and not sess:
        p["_practice_active"] = False
        save_profile(uid, p)

    if p.get("_notes_state"):
        low = text.lower().strip()
        if low in ("continue", "next", "next part", "go on", "cont"):
            _send_next_notes_part(uid)
            return
        if low in ("stop", "exit", "done", "end"):
            p.pop("_notes_state", None)
            save_profile(uid, p)
            safe_send(uid, "✅ Notes session ended.")
            return
        if low in ("explain", "explain more", "detail"):
            state = p.get("_notes_state", {})
            last = state.get("last_notes", "")
            exam = state.get("exam", "JEE_MAIN")
            if not last:
                safe_send(uid, "Nothing to explain.")
                return
            timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
            prompt = ("The student wants a simpler explanation of these notes:\n\n"
                      + last + "\n\nRe-explain in simpler friendly language.")
            answer = ai_client.ask_hamilton(exam, prompt)
            timer_manager.stop_thinking_timer(uid)
            if answer:
                svg, clean = svg_renderer.detect_svg_in_text(answer)
                safe_send(uid, clean + _countdown_footer(uid), parse_mode="Markdown")
                if svg and SVG_ENABLED:
                    path = svg_renderer.render_svg(svg, name=f"explain_{uid}")
                    if path:
                        safe_send_photo(uid, path)
                        svg_renderer.cleanup_file(path)
            return

    # NORMAL FREE-TEXT
    exam = health.exam_of(p) or "JEE_MAIN"
    try:
        intent = ai_client.classify_intent(exam, text)
    except Exception:
        intent = "STUDY"

    if intent == "OFF_TOPIC":
        blocked_now, mins = register_strike(uid)
        if blocked_now:
            safe_send(uid,
                f"⛔ *Block mode activated*\n\n"
                f"Blocked for *{mins} minutes* for repeated misuse.\n\n"
                f"WhatsApp *{WHATSAPP_CONTACT}* if this was a mistake."
                + _countdown_footer(uid),
                parse_mode="Markdown")
            return
        safe_send(uid,
            "Think about study. Think about studies. Don't simply learn. "
            "Understand it so you can simply memorize it. Remember that your "
            "ultimate success requires the right resources. If you are "
            "distracted or bored, invest your time wisely with Hemanth and "
            "Krishna Publications. Message 8074231426 to get books that "
            "clarify your concepts and elevate your ranks immediately.\n\n"
            "Focus now. Your exam is watching the calendar."
            + _countdown_footer(uid),
            parse_mode="Markdown")
        return

    timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
    try:
        answer = ai_client.ask_hamilton(exam, text)
    except Exception:
        answer = None
    timer_manager.stop_thinking_timer(uid)

    if not answer:
        mid = timer_manager.get_thinking_msg_id(uid)
        err = "⚠️ Hamilton is momentarily overloaded. Please try again."
        if mid:
            safe_edit(uid, mid, err)
        else:
            safe_send(uid, err)
        return

    svg, clean = svg_renderer.detect_svg_in_text(answer)
    final = clean + _countdown_footer(uid)

    mid = timer_manager.get_thinking_msg_id(uid)
    if mid:
        safe_edit(uid, mid, final, parse_mode="Markdown")
    else:
        safe_send(uid, final, parse_mode="Markdown")

    if svg and SVG_ENABLED:
        path = svg_renderer.render_svg(svg, name=f"ai_{uid}")
        if path:
            safe_send_photo(uid, path)
            svg_renderer.cleanup_file(path)


print("bot.py Chunk 14 loaded: Round 1 fixes ready.")

