# ==========================================================
# bot.py — Chunk 13: Rich text in all questions
# ==========================================================

# Import rich_formatter helpers (already imported in c11, but safe)
try:
    from rich_formatter import markdown_to_rich
except Exception:
    pass


# ----------------------------------------------------------
# Send rich question + letter-only poll
# ----------------------------------------------------------
def _send_rich_question_and_poll(uid, header_md, question_md, options, correct_index, mode="practice"):
    """
    Sends:
      1. Rich message with full question + options A) B) C) D)
      2. Poll with short letters A/B/C/D/Skip
    Returns nothing.
    """
    # Compose the rich message content
    rich_content = header_md + "\n\n" + question_md
    if options:
        rich_content += "\n\n"
        for i, opt in enumerate(options[:4]):
            letter = chr(65 + i)
            rich_content += f"**{letter})** {opt}\n"

    # Send rich message
    try:
        rich = markdown_to_rich(rich_content)
        bot.send_rich_message(chat_id=uid, rich_message=rich)
    except Exception as e:
        # Fallback to plain text
        print(f"[RICH-Q] fallback: {e}")
        safe_send(uid, rich_content, parse_mode="Markdown")

    time.sleep(0.4)

    # Send short poll
    poll_options = ["A", "B", "C", "D"][:len(options[:4])] + ["🚪 Skip"]
    try:
        bot.send_poll(
            chat_id=uid,
            question="👆 Read the question above. Tap your answer:",
            options=poll_options,
            type="quiz",
            correct_option_id=int(correct_index),
            explanation="See solution below.",
            is_anonymous=False,
        )
    except Exception as e:
        safe_send(uid, f"🔄 Poll error: {e}")


# ==========================================================
# OVERRIDE — _send_next_practice
# ==========================================================
def _send_next_practice(uid):
    p = load_profile(uid)
    exam = p.get("_practice_exam") or health.exam_of(p)
    level = p.get("_practice_level", "medium")
    if not exam:
        safe_send(uid, "❌ Exam not set.")
        return

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        subj = _pick_subject_for_practice(p)
        if not subj:
            timer_manager.stop_generating_timer(bot, uid)
            safe_send(uid, "❌ No chapters available.")
            return
        custom = p.get("_practice_custom_chapters")
        allowed = custom.get(subj) if custom else None
        pick = exam_engine.pick_next_subtopic(p, subj, exam, allowed_chapters=allowed)
        if not pick:
            timer_manager.stop_generating_timer(bot, uid)
            safe_send(uid, "❌ No subtopics found.")
            return
        _, ch, sub = pick
        q_type = "mcq"
        if exam in ("JEE_MAIN", "JEE_ADV") and random.random() < 0.25:
            q_type = "numerical"
        q = exam_engine.generate_question(exam, subj, ch, sub,
                                           q_type=q_type, difficulty=level)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question. Try /exam again.")
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_practice(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}

    meta = q["_meta"]
    sess = exam_engine.get_session(uid)
    if not sess:
        return
    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = meta

    st = q.get("source_type", "AI-Generated")
    sd = q.get("source_detail", "")
    diff = q.get("difficulty", level)
    ideal = q.get("ideal_time_sec", 60)
    q_num = sess.get("questions_done", 0) + 1

    avg_time = None
    key = f"{meta['subject']}::{meta['chapter']}::{meta['subtopic']}"
    stat = p.get("subtopic_stats", {}).get(key)
    if stat and stat.get("attempts", 0) > 0:
        avg_time = stat.get("avg_time", 0)

    header_lines = [
        f"## [{EXAM_NAMES.get(exam, exam)} | {meta['subject']} | Practice | Q{q_num}]",
        f"📌 Source: {st}" + (f" · {sd}" if sd else ""),
        f"⚡ {difficulty_str(diff)} | ⏱️ Ideal: {ideal}s" +
            (f" | 📈 Avg: {int(avg_time)}s" if avg_time else ""),
        f"📖 {meta['chapter']} → {meta['subtopic']}",
    ]
    header_md = "\n".join(header_lines)

    # Numericals go through rich message + text reply (existing flow)
    if q.get("correct_value") is not None:
        rich_content = (header_md + "\n\n" +
                        (q.get("question", "")) +
                        "\n\n_Type your answer as a number._")
        try:
            rich = markdown_to_rich(rich_content)
            bot.send_rich_message(chat_id=uid, rich_message=rich)
        except Exception as e:
            print(f"[RICH-NUM] fallback: {e}")
            safe_send(uid, rich_content, parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": meta, "started": time.time()}
        timer_manager.start_question_timer(bot, uid)
        _preload_practice(uid, count=2)
        return

    # MCQ — send rich question + letter-only poll
    options = q.get("options", [])[:4]
    if len(options) < 2:
        tries = _bump_retry(uid)
        if tries >= 3:
            _reset_retry(uid)
            safe_send(uid, "⚠️ Bad format. Try /exam again.")
            return
        safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
        time.sleep(2)
        _send_next_practice(uid)
        return
    _reset_retry(uid)

    _send_rich_question_and_poll(
        uid, header_md, q.get("question", ""),
        options, int(q.get("correct_index", 0)), mode="practice"
    )
    timer_manager.start_question_timer(bot, uid)
    _preload_practice(uid, count=2)


# ==========================================================
# OVERRIDE — _send_next_test_q
# ==========================================================
def _send_next_test_q(uid):
    p = load_profile(uid)
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return
    plan = sess.get("plan", [])
    idx = sess.get("plan_index", 0)
    if idx >= len(plan):
        _test_paper_finish(uid)
        return

    exam = sess.get("exam")
    subj, ch, sub, q_type, diff = plan[idx]

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        q = exam_engine.generate_question(exam, subj, ch, sub,
                                           q_type=q_type, difficulty=diff)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question. Try /exam again.")
                _test_paper_finish(uid)
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_test_q(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}
        q["_plan_type"] = q_type

    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = q["_meta"]
    sess["current_plan_type"] = q_type

    n_done = sess.get("questions_done", 0)
    n_total = len(plan)
    st = q.get("source_type", "AI-Generated")
    sd = q.get("source_detail", "")
    ideal = q.get("ideal_time_sec", 60)
    section = _section_tag_for(exam, q_type, n_done, n_total)

    header_lines = [
        f"## [{EXAM_NAMES.get(exam, exam)} | {subj} | {section} | Q{n_done+1}/{n_total}]",
        f"📌 Source: {st}" + (f" · {sd}" if sd else ""),
        f"⚡ {difficulty_str(diff)} | ⏱️ Ideal: {ideal}s",
        f"📖 {q['_meta']['chapter']} → {sub}",
    ]
    header_md = "\n".join(header_lines)

    # Numerical path
    if q_type == "numerical" or q.get("correct_value") is not None:
        rich_content = (header_md + "\n\n" + q.get("question", "") +
                        "\n\n_Type your answer as a number._")
        try:
            rich = markdown_to_rich(rich_content)
            bot.send_rich_message(chat_id=uid, rich_message=rich)
        except Exception as e:
            print(f"[RICH-TNUM] fallback: {e}")
            safe_send(uid, rich_content, parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": q["_meta"],
                                   "started": time.time(), "is_test": True}
        _preload_test(uid, count=3)
        return

    # MCQ / Multi / Match → rich + poll
    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["plan_index"] = idx + 1
        _send_next_test_q(uid)
        return

    correct_idx = int(q.get("correct_index", 0))
    if q_type == "multi" and q.get("correct_indices"):
        correct_idx = int(q["correct_indices"][0]) if q["correct_indices"] else 0

    _send_rich_question_and_poll(
        uid, header_md, q.get("question", ""),
        options, correct_idx, mode="test"
    )
    _preload_test(uid, count=3)


# ==========================================================
# OVERRIDE — _send_next_concept_q
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

    total = len(plan)
    header_lines = [
        f"## [Conceptual | {ttype.title()} | Q{idx+1}/{total}]",
        f"📌 AI-Generated · Deep reasoning",
        f"📖 {subj} → {chapter} → {sub[:30]}",
    ]
    header_md = "\n".join(header_lines)

    _send_rich_question_and_poll(
        uid, header_md, q.get("question", ""),
        options, int(q.get("correct_index", 0)), mode="conceptual"
    )
    _preload_concept(uid, count=3)


print("bot.py Chunk 13 loaded: rich questions everywhere ready.")

