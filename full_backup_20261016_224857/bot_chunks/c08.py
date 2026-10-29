# ==========================================================
# bot.py — Chunk 8: conceptual mode (General + Exception)
# ==========================================================

# ==========================================================
# CONCEPTUAL — ask type
# ==========================================================
def _concept_pick_type(uid):
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("General Conceptual", "Exception Test")
    msg = bot.send_message(uid,
        "🧠 *Which type of Conceptual test?*\n\n"
        "• *General* — full chapter theory + concepts\n"
        "• *Exception* — edge cases, anomalies, tricky parts",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _concept_capture_type)


def _concept_capture_type(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip().lower()
    if "except" in t:
        p["_concept_type"] = "exception"
    else:
        p["_concept_type"] = "general"
    save_profile(uid, p)

    # Which chapter? Use selected chapters only for conceptual (they're the ones being tested)
    sel = p.get("selected_chapters", {})
    subjects = [s for s in ["Maths", "Physics", "Chemistry"] if sel.get(s)]
    if not subjects:
        # Fallback: all subjects available
        subjects = health.available_subjects()
    if not subjects:
        bot.send_message(uid, "❌ No subjects available.")
        return
    if len(subjects) == 1:
        _concept_ask_chapter(uid, subjects[0])
        return
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for s in subjects:
        markup.add(s)
    msg = bot.send_message(uid, "📚 *Which subject?*",
                           reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _concept_capture_subject)


def _concept_capture_subject(message):
    uid = message.chat.id
    p = load_profile(uid)
    subj = (message.text or "").strip().capitalize()
    if subj not in health.available_subjects():
        bot.reply_to(message, "❌ Invalid subject.")
        return
    _concept_ask_chapter(uid, subj)


# ==========================================================
# CONCEPTUAL — pick chapter
# ==========================================================
def _concept_ask_chapter(uid, subj):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"

    # Use selected chapters if available
    sel_ch = p.get("selected_chapters", {}).get(subj, [])
    if sel_ch:
        chapter_list = sel_ch
    else:
        data = health.load_subject_data(subj, exam)
        if not data:
            bot.send_message(uid, f"❌ No data for {subj}.")
            return
        chapter_list = list(data.keys())

    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(chapter_list))
    header = f"🧠 *{subj}* — pick a chapter:\n\n{numbered}\n\n"
    footer = "Reply with the number."

    full = header + footer
    if len(full) > 4000:
        safe_send(uid, f"🧠 *{subj}* — chapters:", parse_mode="Markdown")
        safe_send(uid, numbered[:3900])
        msg = bot.send_message(uid, footer)
        bot.register_next_step_handler(msg, _concept_capture_chapter, subj, chapter_list)
    else:
        msg = bot.send_message(uid, header + footer, parse_mode="Markdown")
        bot.register_next_step_handler(msg, _concept_capture_chapter, subj, chapter_list)


def _concept_capture_chapter(message, subj, chapter_list):
    uid = message.chat.id
    try:
        idx = int((message.text or "").strip()) - 1
        if idx < 0 or idx >= len(chapter_list):
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Invalid number.")
        return
    chapter = chapter_list[idx]

    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("40", "60", "80", "100")
    msg = bot.send_message(uid,
        f"🧠 *{chapter}*\n\nHow many questions? (min 40)\nReply 40, 60, 80, or 100",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _concept_capture_count, subj, chapter)


# ==========================================================
# CONCEPTUAL — pick count + start
# ==========================================================
def _concept_capture_count(message, subj, chapter):
    uid = message.chat.id
    try:
        n = int((message.text or "").strip())
        if n < 40 or n > 100:
            raise ValueError
    except ValueError:
        bot.reply_to(message, "Send a number between 40 and 100.")
        return

    p = load_profile(uid)
    ttype = p.get("_concept_type", "general")

    sess = exam_engine.start_conceptual_test(uid, subj, chapter, n, test_type=ttype)
    if not sess:
        bot.reply_to(message, "❌ Could not start. Try /exam again.")
        return
    sess["exam"] = p.get("priority") or health.exam_of(p) or "JEE_MAIN"

    PRELOAD_QUEUE[uid] = []

    safe_send(uid,
        f"🧠 *Conceptual Test ({ttype.title()}) started*\n\n"
        f"Subject: {subj}\n"
        f"Chapter: {chapter}\n"
        f"Questions: {n}\n\n"
        f"⚠️ No feedback until end.\n"
        f"⚠️ Use /stop to submit early.\n\n"
        f"*Get ready...*",
        parse_mode="Markdown")

    time.sleep(1)
    bot.send_message(uid, "🚀 *Go!*")
    _preload_concept(uid, count=3)
    _send_next_concept_q(uid)


# ==========================================================
# CONCEPTUAL — preload
# ==========================================================
def _preload_concept(uid, count=3):
    def _job():
        try:
            p = load_profile(uid)
            sess = exam_engine.get_session(uid)
            if not sess or sess.get("mode") != "conceptual":
                return
            exam = sess.get("exam")
            subj = sess.get("subject")
            chapter = sess.get("chapter")
            plan = sess.get("plan", [])
            idx = sess.get("index", 0)
            ttype = sess.get("test_type", "general")
            queue = PRELOAD_QUEUE.setdefault(uid, [])
            attempts = 0
            while len(queue) < count and idx + len(queue) < len(plan) and attempts < 8:
                attempts += 1
                sub = plan[idx + len(queue)]
                diff = "hard" if ttype == "exception" else "medium"
                q = exam_engine.generate_question(exam, subj, chapter, sub,
                                                   q_type="mcq", difficulty=diff)
                if q:
                    q["_meta"] = {"subject": subj, "chapter": chapter, "subtopic": sub}
                    queue.append(q)
                else:
                    time.sleep(1)
        except Exception:
            pass
    threading.Thread(target=_job, daemon=True).start()


# ==========================================================
# CONCEPTUAL — send next question
# ==========================================================
def _send_next_concept_q(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "conceptual":
        return

    plan = sess.get("plan", [])
    idx = sess.get("index", 0)
    if idx >= len(plan):
        _concept_finish(uid)
        return

    exam = sess.get("exam")
    subj = sess.get("subject")
    chapter = sess.get("chapter")
    sub = plan[idx]
    ttype = sess.get("test_type", "general")

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        diff = "hard" if ttype == "exception" else "medium"
        q = exam_engine.generate_question(exam, subj, chapter, sub,
                                           q_type="mcq", difficulty=diff)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question. Try /exam again.")
                _concept_finish(uid)
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_concept_q(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": chapter, "subtopic": sub}

    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = q["_meta"]

    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["index"] = idx + 1
        _send_next_concept_q(uid)
        return
    options_skip = options + ["🚪 Skip"]

    total = len(plan)
    header = (
        f"[Conceptual | {ttype.title()} | Q{idx+1}/{total}]\n"
        f"📌 AI-Generated · Deep reasoning\n"
        f"📖 {subj} → {chapter} → {sub[:25]}"
    )
    full_q = f"{header}\n\n{q['question']}"

    svg_code = q.get("svg")
    if svg_code and SVG_ENABLED:
        path = svg_renderer.render_svg(svg_code, name=f"cq_{uid}")
        if path:
            safe_send_photo(uid, path)
            svg_renderer.cleanup_file(path)

    try:
        if len(full_q) <= 290:
            bot.send_poll(chat_id=uid, question=full_q[:300],
                          options=options_skip[:10], type="quiz",
                          correct_option_id=int(q.get("correct_index", 0)),
                          explanation="Result in final report.",
                          is_anonymous=False)
        else:
            safe_send(uid, f"📝 *Question*\n\n{full_q}", parse_mode="Markdown")
            time.sleep(0.4)
            bot.send_poll(chat_id=uid, question="👆 Tap your answer:",
                          options=options_skip[:10], type="quiz",
                          correct_option_id=int(q.get("correct_index", 0)),
                          explanation="Result in final report.",
                          is_anonymous=False)
        _preload_concept(uid, count=3)
    except Exception as e:
        safe_send(uid, f"🔄 Retry... {e}")
        time.sleep(1)
        _send_next_concept_q(uid)


# ==========================================================
# CONCEPTUAL — poll handler (silent)
# ==========================================================
def _handle_conceptual_poll(uid, sess, poll_answer):
    q = sess.get("current_q")
    if not q:
        return

    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    options = q.get("options", [])
    time_taken = time.time() - sess.get("current_started", time.time())
    meta = sess.get("current_meta", {})
    subtopic = meta.get("subtopic", "Unknown")

    if selected == len(options):
        correct = False
        sess["skipped"] = sess.get("skipped", 0) + 1
    else:
        correct = (int(selected) == int(q.get("correct_index", -1)))
        if correct:
            sess["correct"] = sess.get("correct", 0) + 1
        else:
            sess["wrong"] = sess.get("wrong", 0) + 1

    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["index"] = sess.get("index", 0) + 1

    # Track subtopic stats
    try:
        exam_engine.record_conceptual_attempt(uid, subtopic, correct)
    except Exception:
        pass

    # Record to health silently
    try:
        health.record_attempt(
            uid,
            meta.get("subject", ""),
            meta.get("chapter", ""),
            subtopic,
            "",
            correct,
            int(time_taken),
            int(q.get("ideal_time_sec", 60)),
            difficulty=q.get("difficulty", "medium"),
        )
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_concept_q(uid)


# ==========================================================
# CONCEPTUAL — finish report
# ==========================================================
def _concept_finish(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "conceptual":
        return

    safe_send(uid, exam_engine.conceptual_report(uid), parse_mode="Markdown")

    # Health delta SVG
    if SVG_ENABLED:
        p = load_profile(uid)
        r = health.overall_health(p)
        if r.get("overall") is not None:
            subj_data = {s: d["health"] for s, d in r["subjects"].items()}
            svg = svg_templates.combined_progress(r["overall"], subj_data)
            path = svg_renderer.render_svg(svg, name=f"cq_graph_{uid}")
            if path:
                safe_send_photo(uid, path, caption=f"Updated overall: {r['overall']}/100")
                svg_renderer.cleanup_file(path)

    exam_engine.end_session(uid)
    PRELOAD_QUEUE.pop(uid, None)


# ==========================================================
# CONCEPTUAL — inline callback (stop)
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "concept_stop")
def _cb_concept_stop(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass
    _concept_finish(uid)


print("bot.py Chunk 8 loaded: conceptual mode (General + Exception) ready.")
