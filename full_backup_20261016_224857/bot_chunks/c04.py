# ==========================================================
# bot.py — Chunk 4: exam + practice + chapter picker + clear_data
# ==========================================================

# ==========================================================
# /exam
# ==========================================================
@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    if not p.get("selected_chapters"):
        bot.reply_to(message,
            "⚠️ *No chapters selected yet.*\n\nType /select first.",
            parse_mode="Markdown")
        return
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("Practice", "Test", "Conceptual")
    msg = bot.send_message(uid,
        "🎯 *Choose exam mode:*\n\n"
        "📚 *Practice* — one question at a time, instant feedback\n"
        "📝 *Test* — full paper with timer, results at end\n"
        "🧠 *Conceptual* — chapter coverage test",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _exam_mode)


def _exam_mode(message):
    uid = message.chat.id
    t = (message.text or "").strip().lower()
    if t == "practice":
        _pick_exam_for_mode(uid, "practice")
    elif t == "test":
        _pick_exam_for_mode(uid, "test")
    elif t == "conceptual":
        _pick_exam_for_mode(uid, "conceptual")
    else:
        bot.reply_to(message, "Tap Practice / Test / Conceptual.")


def _pick_exam_for_mode(uid, mode):
    p = load_profile(uid)
    p["_exam_mode_chosen"] = mode
    p["_exam_chosen"] = None
    save_profile(uid, p)
    if len(p["exams"]) == 1:
        p["_exam_chosen"] = p["exams"][0]
        save_profile(uid, p)
        _exam_after_pick(uid)
        return
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for e in p["exams"]:
        markup.add(EXAM_NAMES[e])
    msg = bot.send_message(uid, "📚 *Which exam?*",
                           reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _exam_pick_exam)


def _exam_pick_exam(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip()
    chosen = next((e for e in p["exams"] if EXAM_NAMES[e].lower() == t.lower()), None)
    if not chosen:
        bot.reply_to(message, "❌ Pick one shown.")
        return
    p["_exam_chosen"] = chosen
    save_profile(uid, p)
    _exam_after_pick(uid)


def _exam_after_pick(uid):
    p = load_profile(uid)
    mode = p.get("_exam_mode_chosen")
    if mode == "practice":
        _practice_ask_chapter_mode(uid)
    elif mode == "test":
        _test_ask_subjects(uid)
    elif mode == "conceptual":
        _concept_pick_type(uid)


# ==========================================================
# PRACTICE — chapter mode picker
# ==========================================================
def _practice_ask_chapter_mode(uid):
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("My selected chapters", "Pick from full syllabus")
    msg = bot.send_message(uid,
        "📖 *Which chapters to practice from?*\n\n"
        "• *My selected* — your focus chapters\n"
        "• *Full syllabus* — pick any chapters now",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _practice_capture_chapter_mode)


def _practice_capture_chapter_mode(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip().lower()
    if "full" in t:
        p["_practice_chapter_mode"] = "custom"
        p["_practice_custom_chapters"] = None
        save_profile(uid, p)
        _practice_pick_subject_full(uid)
    elif "select" in t:
        p["_practice_chapter_mode"] = "selected"
        p["_practice_custom_chapters"] = None
        save_profile(uid, p)
        _practice_ask_difficulty(uid)
    else:
        bot.reply_to(message, "Tap one option.")


def _practice_pick_subject_full(uid):
    p = load_profile(uid)
    exam = p.get("_exam_chosen") or p.get("priority") or health.exam_of(p)
    subjects = health.available_subjects()
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for s in subjects:
        markup.add(s)
    msg = bot.send_message(uid, "📚 *Which subject?*",
                           reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _practice_capture_subject_full, exam)


def _practice_capture_subject_full(message, exam):
    uid = message.chat.id
    p = load_profile(uid)
    subj = (message.text or "").strip().capitalize()
    if subj not in health.available_subjects():
        bot.reply_to(message, "❌ Invalid subject.")
        return
    data = health.load_subject_data(subj, exam)
    if not data:
        bot.reply_to(message, f"❌ No data for {subj}.")
        return
    chapter_list = list(data.keys())
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(chapter_list))
    header = f"📚 *{subj}* — {len(chapter_list)} chapters\n\n"
    footer = "\n\nReply numbers `1,4,7` or `ALL`."
    full = header + numbered + footer
    if len(full) > 4000:
        safe_send(uid, header + "_(list below)_", parse_mode="Markdown")
        safe_send(uid, numbered[:3900])
        msg = bot.send_message(uid, footer.strip())
        bot.register_next_step_handler(msg, _practice_capture_chapters_full, subj, chapter_list)
    else:
        msg = bot.send_message(uid, full,
                               reply_markup=telebot.types.ReplyKeyboardRemove(),
                               parse_mode="Markdown")
        bot.register_next_step_handler(msg, _practice_capture_chapters_full, subj, chapter_list)


def _practice_capture_chapters_full(message, subj, chapter_list):
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
            bot.reply_to(message, "❌ Invalid. Try /exam again.")
            return
    if not chosen:
        bot.reply_to(message, "❌ No valid chapters.")
        return
    p["_practice_custom_chapters"] = {subj: chosen}
    save_profile(uid, p)
    safe_send(uid, f"✅ {subj}: {len(chosen)} chapters selected for this session.")
    _practice_ask_difficulty(uid)


# ==========================================================
# PRACTICE — difficulty
# ==========================================================
def _practice_ask_difficulty(uid):
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("Level 1", "Level 2", "Level 3")
    msg = bot.send_message(uid,
        "🎯 *Difficulty level?*\n\n"
        "• Level 1 — Basic\n"
        "• Level 2 — Standard\n"
        "• Level 3 — Real IIT depth",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _practice_capture_difficulty)


def _practice_capture_difficulty(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip().lower()
    if "1" in t:
        p["_practice_level"] = "easy"
    elif "2" in t:
        p["_practice_level"] = "medium"
    elif "3" in t:
        p["_practice_level"] = "hard"
    else:
        bot.reply_to(message, "Tap Level 1 / 2 / 3.")
        return
    save_profile(uid, p)
    _start_practice(uid)


# ==========================================================
# PRACTICE — start
# ==========================================================
def _pick_subject_for_practice(profile):
    custom = profile.get("_practice_custom_chapters")
    if custom:
        for s, chs in custom.items():
            if chs and s in health.available_subjects():
                return s
    selected = profile.get("selected_chapters", {})
    for s, chs in selected.items():
        if chs and s in health.available_subjects():
            return s
    subjects = health.available_subjects()
    return subjects[0] if subjects else None


def _start_practice(uid):
    p = load_profile(uid)
    exam = p.get("_exam_chosen") or p.get("priority") or health.exam_of(p)
    p["_practice_active"] = True
    p["_practice_exam"] = exam
    save_profile(uid, p)
    exam_engine.new_practice_session(uid, exam=exam)
    PRELOAD_QUEUE[uid] = []
    bot.send_message(uid,
        f"🚀 *Practice started* ({EXAM_NAMES.get(exam, exam)})\n\n"
        "Tap your answer. Use /next for next, /stop to end.\n"
        "_You can ask doubts anytime — I'll answer, then send the next question._",
        reply_markup=telebot.types.ReplyKeyboardRemove(),
        parse_mode="Markdown")
    _preload_practice(uid, count=2)
    _send_next_practice(uid)


def _preload_practice(uid, count=2):
    def _job():
        try:
            p = load_profile(uid)
            exam = p.get("_practice_exam")
            level = p.get("_practice_level", "medium")
            if not exam:
                return
            custom = p.get("_practice_custom_chapters")
            queue = PRELOAD_QUEUE.setdefault(uid, [])
            attempts = 0
            while len(queue) < count and attempts < 6:
                attempts += 1
                subj = _pick_subject_for_practice(p)
                if not subj:
                    return
                allowed = None
                if custom and custom.get(subj):
                    allowed = custom[subj]
                pick = exam_engine.pick_next_subtopic(p, subj, exam,
                                                     allowed_chapters=allowed)
                if not pick:
                    return
                _, ch, sub = pick
                q_type = "mcq"
                if exam in ("JEE_MAIN", "JEE_ADV") and random.random() < 0.25:
                    q_type = "numerical"
                q = exam_engine.generate_question(exam, subj, ch, sub,
                                                   q_type=q_type, difficulty=level)
                if q:
                    q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}
                    queue.append(q)
                else:
                    time.sleep(1)
        except Exception:
            pass
    threading.Thread(target=_job, daemon=True).start()


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
        pick = exam_engine.pick_next_subtopic(p, subj, exam,
                                             allowed_chapters=allowed)
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

    # Average time for this subtopic
    avg_time = None
    key = f"{meta['subject']}::{meta['chapter']}::{meta['subtopic']}"
    stat = p.get("subtopic_stats", {}).get(key)
    if stat and stat.get("attempts", 0) > 0:
        avg_time = stat.get("avg_time", 0)

    header_lines = [
        f"[{EXAM_NAMES.get(exam, exam)} | {meta['subject']} | Practice | Q{q_num}]",
        f"📌 Source: {st}" + (f" · {sd}" if sd else ""),
        f"⚡ Difficulty: {difficulty_str(diff)} | ⏱️ Ideal: {ideal}s",
    ]
    if avg_time:
        header_lines.append(f"📈 Your avg: {int(avg_time)}s")
    header_lines.append(f"📖 {meta['chapter']} → {meta['subtopic']}")
    header = "\n".join(header_lines)
    full_q = f"{header}\n\n{q['question']}"

    svg_code = q.get("svg")
    if svg_code and SVG_ENABLED:
        path = svg_renderer.render_svg(svg_code, name=f"q_{uid}")
        if path:
            safe_send_photo(uid, path)
            svg_renderer.cleanup_file(path)

    if q.get("correct_value") is not None:
        safe_send(uid,
            f"📝 *Numerical Question*\n\n{full_q}\n\n_Type your answer as a number._",
            parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": meta, "started": time.time()}
        timer_manager.start_question_timer(bot, uid)
        return

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

    options_skip = options + ["🚪 Skip"]
    try:
        if len(full_q) <= 290:
            bot.send_poll(chat_id=uid, question=full_q[:300],
                          options=options_skip[:10], type="quiz",
                          correct_option_id=int(q.get("correct_index", 0)),
                          explanation="See solution below.",
                          is_anonymous=False)
        else:
            safe_send(uid, f"📝 *Question*\n\n{full_q}", parse_mode="Markdown")
            time.sleep(0.4)
            bot.send_poll(chat_id=uid, question="👆 Tap your answer:",
                          options=options_skip[:10], type="quiz",
                          correct_option_id=int(q.get("correct_index", 0)),
                          explanation="See below.",
                          is_anonymous=False)
        timer_manager.start_question_timer(bot, uid)
        _preload_practice(uid, count=2)
    except Exception as e:
        safe_send(uid, f"🔄 Retry... {e}")
        time.sleep(1)
        _send_next_practice(uid)


# ==========================================================
# /clear_data — student can wipe all their data
# ==========================================================
@bot.message_handler(commands=['clear_data'])
def cmd_clear_data(message):
    uid = message.chat.id
    p = load_profile(uid)
    if not p or not p.get("secured"):
        bot.reply_to(message, "🔒 Not activated.")
        return
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("🗑 Yes, delete everything",
                                            callback_data="clear_data_yes"),
        telebot.types.InlineKeyboardButton("❌ Cancel",
                                            callback_data="clear_data_no"),
    )
    bot.reply_to(message,
        "⚠️ *Delete ALL your data?*\n\n"
        "This will permanently remove:\n"
        "• Your selected chapters\n"
        "• All attempt history\n"
        "• Health and progress data\n"
        "• All your stats\n\n"
        "You will need to restart setup with /mode.\n\n"
        "*This cannot be undone.*",
        reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("clear_data_"))
def _clear_data_callback(call):
    uid = call.message.chat.id
    if call.data == "clear_data_yes":
        # Keep only secured + name + institute + level + hku_id
        p = load_profile(uid) or {}
        new = new_profile()
        new["secured"] = True
        new["name"] = p.get("name")
        new["institute"] = p.get("institute")
        new["level"] = p.get("level")
        new["hku_id"] = p.get("hku_id")
        new["story_shown"] = True
        new["activation_key"] = p.get("activation_key")
        new["onboarding_step"] = "done"
        save_profile(uid, new)
        try:
            bot.edit_message_text(chat_id=uid, message_id=call.message.message_id,
                                  text="✅ *All your data has been cleared.*\n\n"
                                       "Your account is reset. Type /mode to start fresh.",
                                  parse_mode="Markdown")
        except Exception:
            safe_send(uid, "✅ All your data has been cleared. Type /mode to start fresh.")
    else:
        try:
            bot.edit_message_text(chat_id=uid, message_id=call.message.message_id,
                                  text="❌ Cancelled. Your data is safe.",
                                  parse_mode="Markdown")
        except Exception:
            safe_send(uid, "❌ Cancelled.")


print("bot.py Chunk 4 loaded: exam + practice + chapter picker + clear_data ready.")
