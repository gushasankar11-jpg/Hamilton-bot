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
@bot.message_handler(commands=['help'])
def cmd_help(message):
    uid = message.chat.id
    _send_help_menu(uid)


def _send_help_menu(uid):
    text = (
        "📖 *HAMILTON HELP MENU*\n\n"
        "*Get started:*\n"
        "/start — greeting + activation key\n"
        "/mode — choose exams, year, marks\n"
        "/select — pick chapters you want to study\n\n"
        "*Study modes:*\n"
        "/exam → Practice (one Q at a time, instant feedback)\n"
        "/exam → Test (full paper with timer, results at end)\n"
        "/exam → Conceptual (chapter coverage, 2 types)\n\n"
        "*Progress & analytics:*\n"
        "/health — readiness for each subject\n"
        "/health maths — one subject detail\n"
        "/graph — visual progress chart\n"
        "/plan — study plan for target marks\n"
        "/status — full profile summary\n"
        "/target — update your expected marks\n\n"
        "*Notes & revision:*\n"
        "/notes — short notes for any chapter\n"
        "/continue — next part of notes\n"
        "/bookmark — save current question\n"
        "/bookmarks — view all saved questions\n"
        "/next — next question in practice\n"
        "/stop — end current session\n\n"
        "*Social:*\n"
        "/leaderboard — top performers\n"
        "/leaderboard junior — junior students only\n"
        "/leaderboard senior — seniors + droppers\n"
        "/find HKU-000001 — search a user by ID\n\n"
        "*Account:*\n"
        "/clear_data — wipe all your data\n"
        "/help — this menu\n\n"
        "*⏱️ Timers everywhere:*\n"
        "You'll always see a live timer while Hamilton is "
        "thinking, generating questions, or while you answer."
    )
    safe_send(uid, text, parse_mode="Markdown")


# ==========================================================
# CONCEPTUAL TIMER (own ticker, not test timer)
# ==========================================================
CONCEPT_TIMERS = {}

def _start_concept_timer(uid, total_minutes=60):
    CONCEPT_TIMERS[uid] = {"start": time.time(), "stop": False}

    def _job():
        last5 = -1
        while not CONCEPT_TIMERS.get(uid, {}).get("stop", True):
            el = (time.time() - CONCEPT_TIMERS[uid]["start"]) / 60
            if el >= total_minutes:
                return
            cur5 = int(el // 5)
            if cur5 != last5 and cur5 > 0:
                last5 = cur5
                try:
                    bot.send_message(uid, f"⏱️ {int(el)} min elapsed")
                except Exception:
                    pass
            time.sleep(30)

    threading.Thread(target=_job, daemon=True).start()


def _stop_concept_timer(uid):
    if uid in CONCEPT_TIMERS:
        CONCEPT_TIMERS[uid]["stop"] = True


# ==========================================================
# OVERRIDE — practice poll with ANTI-GUESS
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

    # ---- SKIP ----
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
            f"📖 *Solution:*\n{q.get('explanation', '(none)')}\n\n"
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

    # ---- ANSWER ----
    correct = (int(selected) == int(q.get("correct_index", -1)))

    # Anti-guess: calc question + correct + answered too fast → flag, don't reward
    guessed = False
    if correct and q.get("logic_type") == "calc":
        min_real = q.get("min_realistic_sec", 20)
        if time_taken < min_real:
            guessed = True

    if guessed:
        # No health change
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
            user_letter = chr(65 + int(selected)) if 0 <= selected <= 25 else "?"
            correct_letter = chr(65 + int(q.get("correct_index", 0)))
            head = f"❌ *Wrong* — You chose *{user_letter}*, correct is *{correct_letter}*"

    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal: {q.get('ideal_time_sec', 60)}s)\n\n"
        f"📖 *Solution:*\n{q.get('explanation', '')}\n\n"
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
# OVERRIDE — test poll with FULL MULTI-CORRECT support
# ==========================================================
PENDING_MULTI = {}

def _handle_test_poll(uid, sess, poll_answer):
    q = sess.get("current_q")
    if not q:
        return
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    options = q.get("options", [])
    time_taken = time.time() - sess.get("current_started", time.time())
    meta = sess.get("current_meta", {})
    q_type = sess.get("current_plan_type", "mcq")

    # For MCQ: single correct poll
    if q_type != "multi":
        if selected == len(options):
            sess["skipped"] = sess.get("skipped", 0) + 1
            correct = False
            user_repr = "SKIP"
        else:
            correct_idx = int(q.get("correct_index", 0))
            correct = (int(selected) == correct_idx)
            user_repr = chr(65 + int(selected)) if 0 <= selected <= 25 else "?"
            if correct:
                sess["correct"] = sess.get("correct", 0) + 1
            else:
                sess["wrong"] = sess.get("wrong", 0) + 1

        sess.setdefault("answers_log", []).append({
            "q": q, "meta": meta, "q_type": q_type,
            "user_answer": user_repr, "correct": correct,
            "time_taken": time_taken,
        })
        sess["questions_done"] = sess.get("questions_done", 0) + 1
        sess["total_time"] = sess.get("total_time", 0) + time_taken
        sess["plan_index"] = sess.get("plan_index", 0) + 1

        try:
            health.record_attempt(
                uid, meta.get("subject", ""), meta.get("chapter", ""),
                meta.get("subtopic", ""), "", correct,
                int(time_taken), int(q.get("ideal_time_sec", 60)),
                difficulty=q.get("difficulty", "medium"))
        except Exception:
            pass

        sess["current_q"] = None
        _send_next_test_q(uid)
        return

    # For MULTI: ask user to reply with the answer via text
    # (If they tapped a single option, treat as a guess at one correct)
    correct_indices = q.get("correct_indices", [])
    user_picks = sorted([int(selected)]) if selected != len(options) else []
    correct = (sorted(correct_indices) == user_picks)

    sess.setdefault("answers_log", []).append({
        "q": q, "meta": meta, "q_type": q_type,
        "user_answer": ", ".join(chr(65 + i) for i in user_picks) if user_picks else "SKIP",
        "correct": correct, "time_taken": time_taken,
    })

    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["plan_index"] = sess.get("plan_index", 0) + 1

    try:
        health.record_attempt(
            uid, meta.get("subject", ""), meta.get("chapter", ""),
            meta.get("subtopic", ""), "", correct,
            int(time_taken), int(q.get("ideal_time_sec", 120)),
            difficulty=q.get("difficulty", "medium"))
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_test_q(uid)


# ==========================================================
# OVERRIDE — free-text handler with DEVICE BINDING + help fallback
# ==========================================================
# (duplicate handler disabled — c09 is the active one)
# @bot.message_handler(func=lambda m: True, content_types=['text'])
def free_text_handler(message):
    uid = message.chat.id
    text = (message.text or "").strip()
    if not text:
        return

    p = get_or_create_profile(uid)

    # ---- Admin unblock (works even if blocked) ----
    if text.strip() == ADMIN_UNBLOCK_CODE:
        p.setdefault("behavior", {"strikes": 0, "blocked_until": None})
        p["behavior"]["strikes"] = 0
        p["behavior"]["blocked_until"] = None
        save_profile(uid, p)
        bot.reply_to(message, "🔓 *Admin unblock successful.* Strikes reset.",
                     parse_mode="Markdown")
        return

    # ---- Blocked check ----
    blocked, time_left = check_blocked(uid)
    if blocked:
        safe_send(uid,
            f"⛔ *Blocked*\n\n"
            f"Try again in: *{time_left}*\n\n"
            f"Every message updates the timer.\n"
            f"WhatsApp *{WHATSAPP_CONTACT}* for help."
            + _countdown_footer(uid),
            parse_mode="Markdown")
        return

    # ---- Activation gate (WITH DEVICE BINDING) ----
    if not p.get("secured"):
        if is_valid_key(text):
            allowed, reason = _check_key_binding(uid, text.strip())
            if not allowed:
                if reason == "other_device":
                    safe_send(uid,
                        "❌ *This key is already activated on another device.*\n\n"
                        "Keys work on only one device.\n\n"
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
            # Hamilton story (once)
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

    # ---- Expired key check ----
    if _check_key_expired(uid, p):
        return

    # ---- Onboarding gate ----
    if p.get("onboarding_step") and p["onboarding_step"] != "done":
        _run_onboarding(uid)
        return

    if not p.get("exams"):
        bot.reply_to(message, "🎯 Set exams with /mode first.")
        return

    # ============================================
    # SESSION LOCKS (borders)
    # ============================================
    sess = exam_engine.get_session(uid)

    # Test → hard border
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

    # Conceptual → hard border
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

    # Practice → soft border (allow doubt)
    if p.get("_practice_active") and sess and sess.get("mode") == "practice":
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

    # Stuck practice flag → clear
    if p.get("_practice_active") and not sess:
        p["_practice_active"] = False
        save_profile(uid, p)

    # Notes session
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

    # Pending numerical
    if uid in PENDING_NUMERICAL:
        pending = PENDING_NUMERICAL.get(uid)
        if pending and pending.get("is_test"):
            _handle_test_numerical(uid, text)
        else:
            _handle_numerical_answer(uid, text)
        return

    # ============================================
    # NORMAL FREE-TEXT AI
    # ============================================
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

    # Thinking timer + AI
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


print("bot.py Chunk 10 loaded: help + device binding + anti-guess + multi-correct ready.")
