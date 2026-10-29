# ==========================================================
# bot.py — Chunk 6: test setup (subjects, chapters, papers, start counter)
# ==========================================================

# ==========================================================
# TEST — ask chapter mode
# ==========================================================
def _test_ask_subjects(uid):
    p = load_profile(uid)
    p["_test_subjects"] = None
    p["_test_custom_chapters"] = None
    p["_test_chapter_mode"] = None
    p["_test_papers"] = 1
    save_profile(uid, p)

    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("My selected chapters", "Pick from full syllabus")
    msg = bot.send_message(uid,
        "📖 *Which chapters for this Test?*\n\n"
        "• *My selected* — your focus chapters\n"
        "• *Full syllabus* — pick chapters now from all 3 subjects",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _test_capture_chapter_mode)


def _test_capture_chapter_mode(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip().lower()
    if "full" in t:
        p["_test_chapter_mode"] = "custom"
        p["_test_custom_chapters"] = {}
        p["_test_subject_queue"] = ["Maths", "Physics", "Chemistry"]
        save_profile(uid, p)
        _test_ask_next_subject_chapters(uid)
    elif "select" in t:
        p["_test_chapter_mode"] = "selected"
        # Use profile.selected_chapters as allowed
        p["_test_custom_chapters"] = None
        save_profile(uid, p)
        _test_ask_papers(uid)
    else:
        bot.reply_to(message, "Tap one option.")


# ==========================================================
# TEST — full DB: pick chapters per subject
# ==========================================================
def _test_ask_next_subject_chapters(uid):
    p = load_profile(uid)
    queue = p.get("_test_subject_queue", [])
    if not queue:
        # All 3 subjects done
        _test_ask_papers(uid)
        return

    subj = queue[0]
    exam = p.get("_exam_chosen") or p.get("priority") or health.exam_of(p)
    data = health.load_subject_data(subj, exam)
    if not data:
        # Skip missing subject
        p["_test_subject_queue"] = queue[1:]
        save_profile(uid, p)
        _test_ask_next_subject_chapters(uid)
        return

    chapter_list = list(data.keys())
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(chapter_list))
    header = f"📚 *{subj}* — {len(chapter_list)} chapters\n\n"
    footer = f"\n\nReply numbers `1,4,7` or `ALL`.\n_(Subject {len(queue)} of 3)_"
    full = header + numbered + footer

    if len(full) > 4000:
        safe_send(uid, header + "_(list below)_", parse_mode="Markdown")
        safe_send(uid, numbered[:3900])
        msg = bot.send_message(uid, footer.strip())
        bot.register_next_step_handler(msg, _test_capture_subject_chapters, subj, chapter_list)
    else:
        msg = bot.send_message(uid, full,
                               reply_markup=telebot.types.ReplyKeyboardRemove(),
                               parse_mode="Markdown")
        bot.register_next_step_handler(msg, _test_capture_subject_chapters, subj, chapter_list)


def _test_capture_subject_chapters(message, subj, chapter_list):
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
            bot.reply_to(message, "❌ Invalid. Try again.")
            return

    if not chosen:
        bot.reply_to(message, "❌ No chapters selected.")
        return

    p.setdefault("_test_custom_chapters", {})
    p["_test_custom_chapters"][subj] = chosen
    p["_test_subject_queue"] = p.get("_test_subject_queue", [])[1:]
    save_profile(uid, p)

    safe_send(uid, f"✅ {subj}: {len(chosen)} chapters selected.")
    time.sleep(0.5)
    _test_ask_next_subject_chapters(uid)


# ==========================================================
# TEST — papers (Advanced only)
# ==========================================================
def _test_ask_papers(uid):
    p = load_profile(uid)
    exam = p.get("_exam_chosen") or p.get("priority") or health.exam_of(p)

    if exam == "JEE_ADV":
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("One Paper", "Both Papers")
        msg = bot.send_message(uid,
            "📄 *JEE Advanced — papers?*\n\n"
            "• *One Paper* — 180 min, single session\n"
            "• *Both Papers* — Paper 1, short break, Paper 2",
            reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(msg, _test_capture_papers)
        return

    # Mains / EAMCET → single paper
    p["_test_papers"] = 1
    save_profile(uid, p)
    _test_prestart(uid)


def _test_capture_papers(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip().lower()
    if "both" in t:
        p["_test_papers"] = 2
    elif "one" in t:
        p["_test_papers"] = 1
    else:
        bot.reply_to(message, "Tap One Paper or Both Papers.")
        return
    save_profile(uid, p)
    _test_prestart(uid)


# ==========================================================
# TEST — pre-start + counter
# ==========================================================
def _test_prestart(uid):
    p = load_profile(uid)
    exam = p.get("_exam_chosen") or p.get("priority") or health.exam_of(p)
    chapter_mode = p.get("_test_chapter_mode", "selected")
    custom = p.get("_test_custom_chapters")
    papers = p.get("_test_papers", 1)

    # Build allowed chapters
    if chapter_mode == "custom" and custom:
        allowed = custom
        subjects = [s for s in custom.keys() if custom[s]]
    else:
        # Use profile.selected_chapters
        sel = p.get("selected_chapters", {})
        allowed = {s: list(chs) for s, chs in sel.items() if chs}
        subjects = list(allowed.keys())

    # Force 3 subjects (Maths, Physics, Chemistry)
    for s in ["Maths", "Physics", "Chemistry"]:
        if s not in subjects:
            # Add all chapters of that subject if user hasn't selected any
            data = health.load_subject_data(s, exam)
            if data:
                allowed[s] = list(data.keys())
                subjects.append(s)

    if not subjects:
        bot.send_message(uid, "❌ No subjects available.")
        return

    p["_test_exam"] = exam
    p["_test_allowed"] = allowed
    p["_test_subject_list"] = subjects
    save_profile(uid, p)

    papers_txt = "1 paper" if papers == 1 else "2 papers"
    safe_send(uid,
        f"📝 *Test starting*\n\n"
        f"Exam: {EXAM_NAMES.get(exam, exam)}\n"
        f"Subjects: {', '.join(subjects)}\n"
        f"Papers: {papers_txt}\n\n"
        f"⚠️ Timer runs silently.\n"
        f"⚠️ No feedback during test.\n"
        f"⚠️ Use /stop to submit early.\n\n"
        f"*Get ready. Starting in...*",
        parse_mode="Markdown")

    # 5-4-3-2-1
    for i in [5, 4, 3, 2, 1]:
        try:
            m = bot.send_message(uid, f"⏱️ *{i}*", parse_mode="Markdown")
            time.sleep(1)
            try:
                bot.delete_message(uid, m.message_id)
            except Exception:
                pass
        except Exception:
            break

    bot.send_message(uid, "🚀 *Go!*")

    # Create test session with plan
    _test_start_paper(uid)


# ==========================================================
# TEST — start paper 1 or 2
# ==========================================================
def _test_start_paper(uid):
    p = load_profile(uid)
    exam = p.get("_test_exam")
    subjects = p.get("_test_subject_list", [])
    allowed = p.get("_test_allowed", {})
    papers = p.get("_test_papers", 1)

    paper_num = 1
    sess = exam_engine.get_session(uid)
    if sess and sess.get("mode") == "test":
        paper_num = sess.get("current_paper", 1)

    # Build plan for this paper
    plan = exam_engine.build_test_plan(exam, subjects, allowed)

    # Duration per paper
    dur = DURATION_MIN.get(exam, 180)

    SESSIONS = exam_engine.SESSIONS
    if uid not in SESSIONS:
        exam_engine.new_test_session(uid, exam, subjects, allowed, papers=papers)
    sess = exam_engine.get_session(uid)
    sess["mode"] = "test"
    sess["exam"] = exam
    sess["subjects"] = subjects
    sess["allowed_chapters"] = allowed
    sess["papers"] = papers
    sess["current_paper"] = paper_num
    sess["plan"] = plan
    sess["plan_index"] = 0
    sess["questions_done"] = 0
    sess["correct"] = 0
    sess["wrong"] = 0
    sess["skipped"] = 0
    sess["total_time"] = 0
    sess["current_q"] = None
    sess["current_meta"] = None
    sess["current_started"] = None
    sess["answers_log"] = []
    sess["paper_scores"] = sess.get("paper_scores", [])

    PRELOAD_QUEUE[uid] = []

    safe_send(uid,
        f"📝 *Paper {paper_num} started*\n\n"
        f"Duration: {dur} min\n"
        f"Questions: {len(plan)}\n\n"
        f"Answer each question. No feedback until the end.",
        parse_mode="Markdown")

    # Start timer
    timer_manager.start_test_timer(bot, uid, dur, on_time_up=_test_paper_time_up)

    # Preload first few
    _preload_test(uid, count=3)

    # Send first question
    _send_next_test_q(uid)


# ==========================================================
# TEST — preload
# ==========================================================
def _preload_test(uid, count=3):
    def _job():
        try:
            p = load_profile(uid)
            sess = exam_engine.get_session(uid)
            if not sess or sess.get("mode") != "test":
                return
            exam = sess.get("exam")
            level = p.get("_practice_level", "medium")
            queue = PRELOAD_QUEUE.setdefault(uid, [])
            attempts = 0
            while len(queue) < count and attempts < 8:
                attempts += 1
                idx = sess.get("plan_index", 0) + len(queue)
                plan = sess.get("plan", [])
                if idx >= len(plan):
                    return
                subj, ch, sub, q_type, diff = plan[idx]
                q = exam_engine.generate_question(exam, subj, ch, sub,
                                                   q_type=q_type, difficulty=diff)
                if q:
                    q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}
                    q["_plan_type"] = q_type
                    queue.append(q)
                else:
                    time.sleep(1)
        except Exception:
            pass
    threading.Thread(target=_job, daemon=True).start()


# ==========================================================
# TEST — send next question
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
                safe_send(uid, "⚠️ Could not generate question. Please try /exam again.")
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

    # Section tag — for Mains use A/B; for Advanced use random section names
    section = _section_tag_for(exam, q_type, n_done, n_total)

    header = (
        f"[{EXAM_NAMES.get(exam, exam)} | {subj} | {section} | Q{n_done+1}/{n_total}]\n"
        f"📌 Source: {st}" + (f" · {sd}" if sd else "") + "\n"
        f"⚡ {difficulty_str(diff)} | ⏱️ Ideal: {ideal}s\n"
        f"📖 {q['_meta']['chapter']} → {sub}"
    )
    full_q = f"{header}\n\n{q['question']}"

    # SVG
    svg_code = q.get("svg")
    if svg_code and SVG_ENABLED:
        path = svg_renderer.render_svg(svg_code, name=f"tq_{uid}")
        if path:
            safe_send_photo(uid, path)
            svg_renderer.cleanup_file(path)

    # Numerical
    if q_type == "numerical" or q.get("correct_value") is not None:
        safe_send(uid,
            f"📝 *Numerical Question*\n\n{full_q}\n\n_Type your answer as a number._",
            parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": q["_meta"],
                                   "started": time.time(), "is_test": True}
        return

    # MCQ / Multi / Match → send as poll (single-correct for MCQ / Multi fallback)
    options = q.get("options", [])[:4]
    if len(options) < 2:
        # Bad format → advance
        sess["plan_index"] = idx + 1
        _send_next_test_q(uid)
        return

    options_skip = options + ["🚪 Skip"]

    correct_idx = int(q.get("correct_index", 0))
    if q_type == "multi" and q.get("correct_indices"):
        # Multi-correct — send as poll with first correct for now
        correct_idx = int(q["correct_indices"][0]) if q["correct_indices"] else 0

    try:
        if len(full_q) <= 290:
            bot.send_poll(chat_id=uid, question=full_q[:300],
                          options=options_skip[:10], type="quiz",
                          correct_option_id=correct_idx,
                          explanation="Result in final report.",
                          is_anonymous=False)
        else:
            safe_send(uid, f"📝 *Question*\n\n{full_q}", parse_mode="Markdown")
            time.sleep(0.4)
            bot.send_poll(chat_id=uid, question="👆 Tap your answer:",
                          options=options_skip[:10], type="quiz",
                          correct_option_id=correct_idx,
                          explanation="Result in final report.",
                          is_anonymous=False)
        _preload_test(uid, count=3)
    except Exception as e:
        safe_send(uid, f"🔄 Retry... {e}")
        time.sleep(1)
        _send_next_test_q(uid)


def _section_tag_for(exam, q_type, n_done, n_total):
    if exam == "JEE_MAIN":
        # Section A = MCQ (1-20), Section B = Numerical (21-25) per subject
        # Simplified: first 20 are MCQ → Sec A; rest → Sec B
        if q_type == "numerical":
            return "Section B"
        return "Section A"
    elif exam == "JEE_ADV":
        # Random section per real IIT pattern
        return random.choice(["Section 1", "Section 2", "Section 3", "Section 4"])
    else:
        return "Section A"


print("bot.py Chunk 6 loaded: test setup ready.")
