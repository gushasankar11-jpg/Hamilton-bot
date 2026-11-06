# ==========================================================
# bot.py — Chunk 17: Multi-correct + progress + logo everywhere
# ==========================================================

# ==========================================================
# Fix 1: MULTI-CORRECT (JEE Advanced) — text-based answer
# ==========================================================
PENDING_MULTI = {}


def _send_multi_correct_question(uid, header_md, question_md, options):
    """
    Sends question as rich message + asks user to type answer.
    Format: 'A,C' or 'AC' or 'A C' etc.
    """
    rich_content = header_md + "\n\n" + question_md + "\n\n"
    for i, opt in enumerate(options[:4]):
        letter = chr(65 + i)
        rich_content += f"**{letter})** {opt}\n"
    rich_content += (
        "\n_🧠 This is a multiple-correct question._\n"
        "_Reply with your answers separated by commas._\n"
        "_Example:_ `A,C`  or  `ACD`  or  `B, D`"
    )

    try:
        rich = markdown_to_rich(rich_content)
        bot.send_rich_message(chat_id=uid, rich_message=rich)
    except Exception as e:
        print(f"[MULTI] fallback: {e}")
        safe_send(uid, rich_content, parse_mode="Markdown")

    # Start question timer
    timer_manager.start_question_timer(bot, uid)


def _parse_multi_answer(text, max_letters=4):
    """Parses 'A,C' / 'ACD' / 'B, D' → sorted list of indices."""
    if not text:
        return []
    clean = text.upper().replace(",", " ").replace(";", " ").replace("/", " ")
    picks = set()
    for ch in clean:
        if ch in "ABCD"[:max_letters]:
            picks.add(ord(ch) - 65)
    return sorted(picks)


def _grade_multi(picks, correct_indices, exam):
    """Returns (correct_bool, partial_score)."""
    if not picks or not correct_indices:
        return False, 0
    correct_set = set(correct_indices)
    pick_set = set(picks)
    if pick_set == correct_set:
        return True, 4      # Advanced: full +4
    if pick_set.issubset(correct_set):
        # Partial: +2 for Advanced
        if exam == "JEE_ADV":
            return False, 2
        return False, 0
    # Any wrong → -2 for Advanced
    if exam == "JEE_ADV":
        return False, -2
    return False, 0


def _handle_multi_answer(uid, text):
    """User replied with multi-correct answer."""
    pending = PENDING_MULTI.pop(uid, None)
    if not pending:
        return False

    timer_manager.stop_question_timer(bot, uid)
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]
    exam = pending.get("exam", "JEE_MAIN")
    is_test = pending.get("is_test", False)

    picks = _parse_multi_answer(text, len(q.get("options", [])))
    if not picks:
        PENDING_MULTI[uid] = pending
        safe_send(uid, "⚠️ Reply with letters like `A,C` or `ACD`.")
        return True

    correct_indices = q.get("correct_indices") or []
    correct, partial = _grade_multi(picks, correct_indices, exam)

    sess = exam_engine.get_session(uid)
    if sess:
        sess["questions_done"] = sess.get("questions_done", 0) + 1
        sess["total_time"] = sess.get("total_time", 0) + time_taken
        if correct:
            sess["correct"] = sess.get("correct", 0) + 1
        else:
            sess["wrong"] = sess.get("wrong", 0) + 1
        sess.setdefault("answers_log", []).append({
            "q": q, "meta": meta, "q_type": "multi",
            "user_answer": ",".join(chr(65 + p) for p in picks),
            "correct": correct, "time_taken": time_taken,
        })

    # Silent during test
    if is_test:
        if sess:
            sess["plan_index"] = sess.get("plan_index", 0) + 1
            sess["current_q"] = None
        _send_next_test_q(uid)
        return True

    # Practice/Conceptual feedback
    correct_letters = ",".join(chr(65 + int(i)) for i in correct_indices)
    user_letters = ",".join(chr(65 + p) for p in picks)

    try:
        health.record_attempt(
            uid, meta.get("subject", ""), meta.get("chapter", ""),
            meta.get("subtopic", ""), "", correct,
            int(time_taken), int(q.get("ideal_time_sec", 120)),
            difficulty=q.get("difficulty", "medium"))
    except Exception:
        pass

    if correct:
        head = "✅ *Correct!*"
    elif partial > 0:
        head = f"⚠️ *Partially correct* (+{partial} marks)"
    else:
        head = f"❌ *Wrong* — Your picks: *{user_letters}* · Correct: *{correct_letters}*"

    explanation = _force_math_delims(q.get("explanation", ""))
    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 120)}s)\n\n"
        f"📖 *Solution:*\n{explanation}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}"
    )
    safe_send(uid, msg + _countdown_footer(uid), parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    if sess:
        sess["last_q"] = q
        sess["last_meta"] = meta
        sess["current_q"] = None
    return True


# ==========================================================
# Override test question sender — multi-correct path
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
                safe_send(uid, "⚠️ Could not generate question.")
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

    # Multi-correct → text-based answer
    if q_type == "multi" and q.get("correct_indices"):
        _send_multi_correct_question(uid, header_md, q.get("question", ""),
                                     q.get("options", []))
        PENDING_MULTI[uid] = {"q": q, "meta": q["_meta"],
                               "started": time.time(), "exam": exam,
                               "is_test": True}
        return

    # Numerical
    if q_type == "numerical" or q.get("correct_value") is not None:
        rich_content = (header_md + "\n\n" + q.get("question", "") +
                        "\n\n_Type your answer as a number (or `skip`)._")
        try:
            rich = markdown_to_rich(rich_content)
            bot.send_rich_message(chat_id=uid, rich_message=rich)
        except Exception:
            safe_send(uid, rich_content, parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": q["_meta"],
                                   "started": time.time(), "is_test": True}
        _preload_test(uid, count=3)
        return

    # MCQ → rich + letter poll
    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["plan_index"] = idx + 1
        _send_next_test_q(uid)
        return

    correct_idx = int(q.get("correct_index", 0))
    _send_rich_question_and_poll(uid, header_md, q.get("question", ""),
                                  options, correct_idx, mode="test")
    _preload_test(uid, count=3)


# Same for practice — allow multi-correct if generated
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
        r = random.random()
        if exam in ("JEE_MAIN", "JEE_ADV") and r < 0.20:
            q_type = "numerical"
        elif exam == "JEE_ADV" and r < 0.35:
            q_type = "multi"
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
    sess["current_plan_type"] = q.get("_plan_type", "mcq")

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

    # Multi-correct path
    if q.get("correct_indices"):
        _send_multi_correct_question(uid, header_md, q.get("question", ""),
                                     q.get("options", []))
        PENDING_MULTI[uid] = {"q": q, "meta": meta, "started": time.time(),
                               "exam": exam, "is_test": False}
        _preload_practice(uid, count=2)
        return

    # Numerical path
    if q.get("correct_value") is not None:
        rich_content = (header_md + "\n\n" + q.get("question", "") +
                        "\n\n_Type your answer as a number (or `skip`)._")
        try:
            rich = markdown_to_rich(rich_content)
            bot.send_rich_message(chat_id=uid, rich_message=rich)
        except Exception:
            safe_send(uid, rich_content, parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": meta, "started": time.time()}
        timer_manager.start_question_timer(bot, uid)
        _preload_practice(uid, count=2)
        return

    # MCQ
    options = q.get("options", [])[:4]
    if len(options) < 2:
        tries = _bump_retry(uid)
        if tries >= 3:
            _reset_retry(uid)
            safe_send(uid, "⚠️ Bad format.")
            return
        safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
        time.sleep(2)
        _send_next_practice(uid)
        return
    _reset_retry(uid)

    _send_rich_question_and_poll(uid, header_md, q.get("question", ""),
                                  options, int(q.get("correct_index", 0)),
                                  mode="practice")
    timer_manager.start_question_timer(bot, uid)
    _preload_practice(uid, count=2)


# ==========================================================
# Fix 2: Progress graph — richer (chapter + rank + marks)
# ==========================================================
def _rich_progress_svg(profile):
    """
    Returns an SVG string containing:
    - Overall bar
    - Subject bars
    - Top 5 weak chapters
    - Predicted rank + percentile
    - Expected vs target marks
    """
    from config import MAX_MARKS, SVG_COLOR_BG, SVG_COLOR_TEXT

    r = health.overall_health(profile)
    overall = r.get("overall") or 0
    primary = profile.get("priority") or (profile.get("exams") or ["—"])[0]
    pct = health.predict_percentile(r.get("overall"))
    _, tier = health.estimate_rank(profile)

    targets = profile.get("target_marks", {}) or {}
    target_marks = targets.get(primary, 0) if isinstance(targets, dict) else 0
    max_marks = MAX_MARKS.get(primary, 100)
    expected_marks = int((r.get("overall") or 0) / 100 * max_marks)

    # Weak chapters
    weak = []
    for subj, sdata in r["subjects"].items():
        ch_map = health.chapter_health_map(profile, subj, primary, only_selected=True)
        for ch, cd in ch_map.items():
            if cd.get("health") is not None:
                weak.append((cd["health"], f"{subj[:3]}·{ch[:22]}"))
    weak.sort()
    weak5 = weak[:5]

    def _col(h):
        if h is None: return "#444"
        if h >= 85: return "#28a745"
        if h >= 70: return "#ffc107"
        if h >= 55: return "#fd7e14"
        return "#dc3545"

    W = 820
    H = 720
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    parts.append(f'<rect width="{W}" height="{H}" fill="{SVG_COLOR_BG}" rx="16"/>')
    parts.append(f'<text x="{W//2}" y="45" font-size="26" font-weight="bold" fill="{SVG_COLOR_TEXT}" '
                 f'font-family="Arial" text-anchor="middle">HAMILTON PROGRESS REPORT</text>')

    # Overall bar
    ow = int(overall / 100 * 700)
    oc = _col(overall)
    parts.append(f'<text x="40" y="95" font-size="16" fill="#ccc" font-family="Arial">Overall Health</text>')
    parts.append(f'<rect x="40" y="105" width="700" height="30" fill="#222" rx="15"/>')
    parts.append(f'<rect x="40" y="105" width="{ow}" height="30" fill="{oc}" rx="15"/>')
    parts.append(f'<text x="760" y="128" font-size="22" font-weight="bold" fill="{oc}" font-family="Arial">{overall:.1f}</text>')

    # Subject bars
    parts.append(f'<text x="40" y="175" font-size="14" fill="#888" font-family="Arial">SUBJECT-WISE</text>')
    y = 195
    for subj, sdata in r["subjects"].items():
        h = sdata["health"]
        col = _col(h)
        bw = int((h or 0) / 100 * 700)
        txt = f"{h:.1f}" if h is not None else "—"
        parts.append(f'<text x="40" y="{y+4}" font-size="14" fill="#ddd" font-family="Arial">{subj}</text>')
        parts.append(f'<rect x="40" y="{y+12}" width="700" height="22" fill="#222" rx="11"/>')
        parts.append(f'<rect x="40" y="{y+12}" width="{bw}" height="22" fill="{col}" rx="11"/>')
        parts.append(f'<text x="760" y="{y+30}" font-size="15" font-weight="bold" fill="{col}" font-family="Arial">{txt}</text>')
        y += 50

    # Weak chapters
    parts.append(f'<text x="40" y="{y+20}" font-size="14" fill="#888" font-family="Arial">TOP 5 WEAK CHAPTERS (focus here)</text>')
    y += 45
    for h, name in weak5:
        col = _col(h)
        bw = int((h or 0) / 100 * 700)
        parts.append(f'<text x="40" y="{y+4}" font-size="12" fill="#ddd" font-family="Arial">{name}</text>')
        parts.append(f'<rect x="40" y="{y+12}" width="700" height="18" fill="#222" rx="9"/>')
        parts.append(f'<rect x="40" y="{y+12}" width="{bw}" height="18" fill="{col}" rx="9"/>')
        parts.append(f'<text x="760" y="{y+26}" font-size="13" fill="{col}" font-family="Arial">{h:.0f}</text>')
        y += 45

    # Rank + Percentile
    parts.append(f'<text x="40" y="{y+20}" font-size="14" fill="#888" font-family="Arial">PREDICTED RANK</text>')
    parts.append(f'<text x="40" y="{y+55}" font-size="28" font-weight="bold" fill="#00d4ff" font-family="Arial">{tier}</text>')
    parts.append(f'<text x="40" y="{y+85}" font-size="18" fill="#00d4ff" font-family="Arial">Percentile: {pct:.1f}</text>')
    y += 100

    # Marks target
    parts.append(f'<text x="40" y="{y+20}" font-size="14" fill="#888" font-family="Arial">MARKS</text>')
    parts.append(f'<text x="40" y="{y+55}" font-size="22" font-weight="bold" fill="#ffc107" font-family="Arial">Expected: {expected_marks} / {max_marks}</text>')
    parts.append(f'<text x="40" y="{y+85}" font-size="18" fill="#888" font-family="Arial">Your target: {target_marks} / {max_marks}</text>')

    parts.append('</svg>')
    return "".join(parts)


# Override /graph to use the rich SVG
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

    svg = _rich_progress_svg(p)
    path = svg_renderer.render_svg(svg, name=f"graph_{uid}")
    if path:
        safe_send_photo(uid, path, caption=f"📊 Progress Report — Overall {r['overall']}/100")
        svg_renderer.cleanup_file(path)
    else:
        safe_send(uid, f"📊 Overall: {r['overall']}/100")


print("bot.py Chunk 17 loaded: multi-correct + rich progress ready.")

