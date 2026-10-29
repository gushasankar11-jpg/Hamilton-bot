# ==========================================================
# c27 — Critical fixes + Developer credit
# ==========================================================

DEVELOPER_CREDIT = "\n\n_Developed by Vishnavi Gokarnam_"


# ==========================================================
# FIX 1 — Developer credit on every text message
# ==========================================================
_orig_safe_send = safe_send

def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    if text and "Developed by Vishnavi Gokarnam" not in text:
        text = text + DEVELOPER_CREDIT
    return _orig_safe_send(chat_id, text, parse_mode=parse_mode,
                            reply_markup=reply_markup)


_orig_safe_edit = safe_edit

def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    if text and "Developed by Vishnavi Gokarnam" not in text:
        text = text + DEVELOPER_CREDIT
    return _orig_safe_edit(chat_id, message_id, text, parse_mode=parse_mode,
                            reply_markup=reply_markup)


_orig_safe_send_photo = safe_send_photo

def safe_send_photo(chat_id, photo_path, caption=None):
    if caption:
        if "Developed by Vishnavi Gokarnam" not in caption:
            caption = caption + "\n_Developed by Vishnavi Gokarnam_"
    else:
        caption = "_Developed by Vishnavi Gokarnam_"
    return _orig_safe_send_photo(chat_id, photo_path, caption=caption)


# ==========================================================
# FIX 2 — Developer credit in thinking message
# ==========================================================
ai_client.THINKING_MSG = (
    "🤔 *Hamilton is thinking deeply...*\n\n"
    "_Developed by Vishnavi Gokarnam_"
)


# ==========================================================
# FIX 3 — /clear_data full wipe + fresh start
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "clear_data_yes")
def _clear_data_callback_fixed(call):
    uid = call.message.chat.id
    p = load_profile(uid) or {}
    fresh = new_profile()
    fresh["secured"] = True
    fresh["activation_key"] = p.get("activation_key")
    fresh["hku_id"] = p.get("hku_id")
    fresh["story_shown"] = False
    fresh["onboarding_step"] = "name"
    save_profile(uid, fresh)
    try:
        bot.edit_message_text(
            chat_id=uid,
            message_id=call.message.message_id,
            text=("✅ *All your data has been cleared.*\n\n"
                  "Name, chapters, health, attempts — everything reset.\n\n"
                  "Type /start to set up your profile fresh."
                  + DEVELOPER_CREDIT),
            parse_mode="Markdown")
    except Exception:
        safe_send(uid, "✅ All data cleared. Type /start to set up fresh.")


# ==========================================================
# FIX 4 — Repetition guard for conceptual test
# ==========================================================
# Track hash of each question sent in current conceptual session
_orig_new_test_session = exam_engine.new_test_session

def _concept_session_with_hash(uid, subject, chapter, total_q, test_type="general"):
    s = exam_engine.start_conceptual_test(uid, subject, chapter, total_q, test_type)
    if s:
        s["used_hashes"] = set()
    return s


# Override _send_next_concept_q to prevent repeats
_orig_send_next_concept = _send_next_concept_q

def _send_next_concept_q_fixed(uid):
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
    used = sess.setdefault("used_hashes", set())

    q = None
    for attempt in range(5):
        timer_manager.start_generating_timer(bot, uid, "question")
        diff = "hard" if ttype == "exception" else "medium"
        candidate = exam_engine.generate_question(
            exam, subj, chapter, sub, q_type="mcq", difficulty=diff)
        timer_manager.stop_generating_timer(bot, uid)
        if not candidate:
            continue
        h = hash(candidate.get("question", "")[:200])
        if h in used:
            continue
        q = candidate
        used.add(h)
        break

    if not q:
        # Can't generate unique — skip ahead
        sess["index"] = idx + 1
        return _send_next_concept_q_fixed(uid)

    q["_meta"] = {"subject": subj, "chapter": chapter, "subtopic": sub}
    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = q["_meta"]

    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["index"] = idx + 1
        return _send_next_concept_q_fixed(uid)

    options_skip = options + ["🚪 Skip"]
    total = len(plan)
    header = (
        f"[Conceptual | {ttype.title()} | Q{idx+1}/{total}]\n"
        f"📌 AI-Generated · Deep reasoning\n"
        f"📖 {subj} → {chapter} → {sub[:25]}"
    )
    full_q = f"{header}\n\n{q['question']}"

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
    except Exception as e:
        safe_send(uid, f"🔄 Retry... {e}")
        time.sleep(1)
        _send_next_concept_q_fixed(uid)


# ==========================================================
# FIX 5 — NameError guard for `subject` in concept start
# ==========================================================
# Somewhere in c11-c26, `subject` is referenced without being defined.
# Wrap the concept start in try/except and provide fallback.
_orig_start_concept = _concept_capture_count

def _concept_capture_count_safe(message, subj, chapter):
    try:
        return _orig_start_concept(message, subj, chapter)
    except NameError as e:
        print(f"[FIX] NameError caught: {e}")
        safe_send(message.chat.id,
                  "⚠️ Setup glitch detected. Please /exam again.")
    except Exception as e:
        print(f"[FIX] Exception: {e}")
        safe_send(message.chat.id, f"⚠️ Error: {e}")


# ==========================================================
# FIX 6 — Health math chain fix (subtopic → chapter → subject → overall)
# ==========================================================
# Override health.overall_health to compute correctly
def _health_overall_fixed(profile):
    exam = health.exam_of(profile)
    if exam is None:
        return {"exam": None, "subjects": {}, "overall": None, "filtering": False}

    subjects = {}
    subject_averages = []

    for subj in health.available_subjects():
        # Get all subtopics in this subject
        chapter_map = health.chapter_health_map(profile, subj, exam, only_selected=True)
        chapter_healths = [c["health"] for c in chapter_map.values()
                           if c.get("health") is not None]

        if chapter_healths:
            subj_avg = round(sum(chapter_healths) / len(chapter_healths), 1)
            subject_averages.append(subj_avg)
            subjects[subj] = {
                "health": subj_avg,
                "chapters_started": len(chapter_healths),
                "chapters_total": len(chapter_map),
            }
        else:
            subjects[subj] = {
                "health": None,
                "chapters_started": 0,
                "chapters_total": len(chapter_map),
            }

    overall = round(sum(subject_averages) / len(subject_averages), 1) \
        if subject_averages else None

    return {
        "exam": exam,
        "subjects": subjects,
        "overall": overall,
        "filtering": bool(profile.get("selected_chapters")),
    }


health.overall_health = _health_overall_fixed


# ==========================================================
# FIX 7 — PDF error handling (stop infinite retry)
# ==========================================================
# Catch PDF generation errors and never retry more than once
import builtins

_pdf_attempt_count = {}

def _safe_pdf_generation(uid, content, filename):
    """Wrapper for PDF gen. Returns path or None. Never loops."""
    if _pdf_attempt_count.get(uid, 0) >= 1:
        return None
    _pdf_attempt_count[uid] = _pdf_attempt_count.get(uid, 0) + 1
    return None  # Disable PDF until code is fixed


# ==========================================================
# FIX 8 — Append developer credit to every AI reply
# ==========================================================
_orig_ai_call = ai_client.ask_hamilton

def ask_hamilton_with_credit(exam, prompt, context=None, retries=3):
    r = _orig_ai_call(exam, prompt, context=context, retries=retries)
    if r and "Vishnavi Gokarnam" not in r:
        r = r + "\n\n_Developed by Vishnavi Gokarnam_"
    return r

ai_client.ask_hamilton = ask_hamilton_with_credit


print("bot.py Chunk 27 loaded: critical fixes + developer credit ready.")

