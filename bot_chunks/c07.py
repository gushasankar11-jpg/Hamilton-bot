from ai_client import convert_latex_envs
# ==========================================================
# bot.py — Chunk 7: test poll handler, paper break, finish report
# ==========================================================

# ==========================================================
# TEST — poll handler (silent, save answer, no feedback)
# ==========================================================
def _handle_test_poll(uid, sess, poll_answer):
    q = sess.get("current_q")
    if not q:
        return

    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    options = q.get("options", [])
    time_taken = time.time() - sess.get("current_started", time.time())
    meta = sess.get("current_meta", {})
    q_type = sess.get("current_plan_type", "mcq")

    # Determine correctness
    if selected == len(options):
        # Skipped
        sess["skipped"] = sess.get("skipped", 0) + 1
        correct = False
        user_answer_repr = "SKIP"
    else:
        correct_idx = int(q.get("correct_index", 0))
        if q_type == "multi" and q.get("correct_indices"):
            correct_idx = int(q["correct_indices"][0])
        correct = (int(selected) == correct_idx)
        user_answer_repr = chr(65 + int(selected)) if 0 <= selected <= 25 else "?"
        if correct:
            sess["correct"] = sess.get("correct", 0) + 1
        else:
            sess["wrong"] = sess.get("wrong", 0) + 1

    # Log answer for report
    sess.setdefault("answers_log", []).append({
        "q": q,
        "meta": meta,
        "q_type": q_type,
        "user_answer": user_answer_repr,
        "correct": correct,
        "time_taken": time_taken,
    })

    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["plan_index"] = sess.get("plan_index", 0) + 1

    # Record to health silently
    try:
        health.record_attempt(
            uid,
            meta.get("subject", ""),
            meta.get("chapter", ""),
            meta.get("subtopic", ""),
            "",
            correct,
            int(time_taken),
            int(q.get("ideal_time_sec", 60)),
            difficulty=q.get("difficulty", "medium"),
        )
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_test_q(uid)


# ==========================================================
# TEST — numerical answer during test
# ==========================================================
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
        safe_send(uid, "⚠️ Please send a valid number.")
        return

    try:
        correct_val = float(q.get("correct_value", 0))
        correct = abs(val - correct_val) < 1e-6
    except Exception:
        correct = False
        correct_val = q.get("correct_value", "?")

    q_type = "numerical"
    user_answer_repr = text.strip() if text.strip() else "?"

    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    sess.setdefault("answers_log", []).append({
        "q": q,
        "meta": meta,
        "q_type": q_type,
        "user_answer": user_answer_repr,
        "correct": correct,
        "time_taken": time_taken,
    })

    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["plan_index"] = sess.get("plan_index", 0) + 1

    try:
        health.record_attempt(
            uid,
            meta.get("subject", ""),
            meta.get("chapter", ""),
            meta.get("subtopic", ""),
            "",
            correct,
            int(time_taken),
            int(q.get("ideal_time_sec", 90)),
            difficulty=q.get("difficulty", "medium"),
        )
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_test_q(uid)


# ==========================================================
# TEST — timeout on paper
# ==========================================================
def _test_paper_time_up(uid):
    safe_send(uid, "⏰ Time up. Submitting paper...")
    _test_paper_finish(uid)


# ==========================================================
# TEST — finish a single paper
# ==========================================================
def _test_paper_finish(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return

    timer_manager.stop_test_timer(uid)

    paper = sess.get("current_paper", 1)
    papers = sess.get("papers", 1)

    # Save this paper's score
    p_correct = sess.get("correct", 0)
    p_wrong = sess.get("wrong", 0)
    p_skipped = sess.get("skipped", 0)
    p_log = sess.get("answers_log", [])

    score, max_score = exam_engine.test_paper_score(
        sess.get("exam"), p_correct, p_wrong, p_skipped
    )

    sess.setdefault("paper_scores", []).append({
        "paper": paper,
        "correct": p_correct,
        "wrong": p_wrong,
        "skipped": p_skipped,
        "score": score,
        "max": max_score,
        "log": list(p_log),
    })

    # If more papers to write
    if paper < papers:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton(
                "▶️ Continue to Paper 2",
                callback_data="test_paper2_start"
            ),
            telebot.types.InlineKeyboardButton(
                "⏹ End & Show Results",
                callback_data="test_end_now"
            ),
        )
        safe_send(uid,
            f"🏁 *Paper {paper} submitted*\n\n"
            f"Score: *{score} / {max_score}*\n"
            f"✅ {p_correct}  ❌ {p_wrong}  🚪 {p_skipped}\n\n"
            f"Take a short break.\n"
            f"When ready, tap Continue for Paper {paper+1}.",
            parse_mode="Markdown",
            reply_markup=markup)
        return

    # All papers done → show final report
    _test_finish(uid)


# ==========================================================
# TEST — full finish report with key + explanations
# ==========================================================
def _test_finish(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return

    timer_manager.stop_test_timer(uid)

    exam = sess.get("exam", "JEE_MAIN")
    papers_data = sess.get("paper_scores", [])

    # If no papers submitted yet (rare), grab current
    if not papers_data:
        p_correct = sess.get("correct", 0)
        p_wrong = sess.get("wrong", 0)
        p_skipped = sess.get("skipped", 0)
        log = sess.get("answers_log", [])
        score, max_score = exam_engine.test_paper_score(exam, p_correct, p_wrong, p_skipped)
        papers_data = [{
            "paper": 1,
            "correct": p_correct, "wrong": p_wrong, "skipped": p_skipped,
            "score": score, "max": max_score, "log": log,
        }]

    # Aggregate
    total_correct = sum(p["correct"] for p in papers_data)
    total_wrong = sum(p["wrong"] for p in papers_data)
    total_skipped = sum(p["skipped"] for p in papers_data)
    total_score = sum(p["score"] for p in papers_data)
    total_max = sum(p["max"] for p in papers_data)
    total_time_min = sess.get("total_time", 0) / 60

    # Headline
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "   🏁 *TEST COMPLETE*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━", "",
        f"📘 Exam: {EXAM_NAMES.get(exam, exam)}",
        f"📝 Attempted: {total_correct + total_wrong}",
        f"🚪 Skipped: {total_skipped}",
        f"⏱️ Total time: {round(total_time_min, 1)} min", "",
    ]

    for p in papers_data:
        lines.append(f"📄 *Paper {p['paper']}*: {p['score']} / {p['max']}")
    lines.append("")
    lines.append(f"🏆 *Overall Score: {total_score} / {total_max}*")
    lines.append(f"✅ Correct: {total_correct}  ❌ Wrong: {total_wrong}")
    if (total_correct + total_wrong) > 0:
        acc = round(100 * total_correct / (total_correct + total_wrong), 1)
        lines.append(f"🎯 Accuracy: {acc}%")

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")

    # Health delta SVG
    if SVG_ENABLED:
        p_holder = load_profile(uid)
        r = health.overall_health(p_holder)
        if r.get("overall") is not None:
            subj_data = {s: d["health"] for s, d in r["subjects"].items()}
            svg = svg_templates.combined_progress(r["overall"], subj_data)
            path = svg_renderer.render_svg(svg, name=f"test_graph_{uid}")
            if path:
                safe_send_photo(uid, path, caption=f"Updated overall: {r['overall']}/100")
                svg_renderer.cleanup_file(path)

    # Send full review as separate messages
    _send_full_review(uid, papers_data)

    # Cleanup
    exam_engine.end_session(uid)
    PRELOAD_QUEUE.pop(uid, None)
    PENDING_NUMERICAL.pop(uid, None)


# ==========================================================
# TEST — full question-by-question review with key + friendly explain
# ==========================================================
def _send_full_review(uid, papers_data):
    safe_send(uid,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "   📖 *FULL REVIEW*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "One question at a time with the key and reasoning.",
        parse_mode="Markdown")

    time.sleep(1)

    q_num = 0
    for p in papers_data:
        for item in p["log"]:
            q_num += 1
            _review_one_question(uid, q_num, item)
            time.sleep(0.8)


def _review_one_question(uid, q_num, item):
    q = item["q"]
    meta = item.get("meta", {})
    correct = item["correct"]
    user_answer = item["user_answer"]
    time_taken = item["time_taken"]
    q_type = item.get("q_type", "mcq")

    # Correct answer string
    if q_type == "numerical" or q.get("correct_value") is not None:
        correct_ans = str(q.get("correct_value", "?"))
    elif q.get("correct_indices"):
        correct_ans = ", ".join(chr(65 + int(i)) for i in q["correct_indices"])
    else:
        correct_ans = chr(65 + int(q.get("correct_index", 0)))

    if correct:
        head = f"✅ *Q{q_num}* — Correct"
    else:
        head = f"❌ *Q{q_num}* — Wrong"

    lines = [head]
    lines.append(f"📖 {meta.get('chapter','')} → {meta.get('subtopic','')}")
    lines.append("")
    lines.append(f"📝 *Question:*")
    lines.append(q.get("question", "(question)")[:400])
    lines.append("")
    if q_type != "numerical":
        opts = q.get("options", [])
        for i, opt in enumerate(opts[:4]):
            letter = chr(65 + i)
            marker = " ⬅ your answer" if user_answer == letter else ""
            lines.append(f"{letter}) {opt}{marker}")
        lines.append("")
    lines.append(f"🎯 *Correct answer:* {correct_ans}")
    lines.append(f"✍️ Your answer: {user_answer}")
    lines.append(f"⏱️ {int(time_taken)}s")
    lines.append("")

    # Friendly explanation
    expl = convert_latex_envs(q.get("explanation", "(no explanation)"))
    lines.append(f"📖 *Why:*")
    lines.append(expl[:700])
    lines.append("")

    # Traps
    traps = q.get("traps") or []
    if traps:
        lines.append("⚠️ *Traps:*")
        for t in traps[:3]:
            lines.append(f"• {t}")
        lines.append("")

    # Shortcut
    sc = q.get("shortcut", "")
    if sc:
        lines.append(f"⚡ *Shortcut:* {sc}")
        lines.append("")

    # Source
    st = q.get("source_type", "AI")
    sd = q.get("source_detail", "")
    tag = st + (f" · {sd}" if sd else "")
    lines.append(f"📌 {tag}")

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


# ==========================================================
# TEST — inline callbacks: Paper 2 + End now
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "test_paper2_start")
def _cb_test_paper2_start(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass

    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        safe_send(uid, "Test session ended.")
        return

    # Reset counters for paper 2
    sess["current_paper"] = 2
    sess["correct"] = 0
    sess["wrong"] = 0
    sess["skipped"] = 0
    sess["questions_done"] = 0
    sess["total_time"] = 0
    sess["plan_index"] = 0
    sess["current_q"] = None
    sess["current_meta"] = None
    sess["answers_log"] = []

    # Regenerate plan for paper 2
    p = load_profile(uid)
    exam = sess.get("exam")
    subjects = sess.get("subjects", [])
    allowed = sess.get("allowed_chapters", {})
    plan = exam_engine.build_test_plan(exam, subjects, allowed)
    sess["plan"] = plan

    PRELOAD_QUEUE[uid] = []

    dur = DURATION_MIN.get(exam, 180)
    safe_send(uid,
        f"📄 *Paper 2 started*\n\n"
        f"Duration: {dur} min\n"
        f"Questions: {len(plan)}\n\n"
        f"Good luck. No feedback until the end.",
        parse_mode="Markdown")

    timer_manager.start_test_timer(bot, uid, dur, on_time_up=_test_paper_time_up)
    _preload_test(uid, count=3)
    _send_next_test_q(uid)


@bot.callback_query_handler(func=lambda c: c.data == "test_end_now")
def _cb_test_end_now(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass
    _test_finish(uid)


# ==========================================================
# TEST — inline callback: stop test
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "test_stop")
def _cb_test_stop(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass
    _test_finish(uid)


print("bot.py Chunk 7 loaded: test handler + paper break + review ready.")
