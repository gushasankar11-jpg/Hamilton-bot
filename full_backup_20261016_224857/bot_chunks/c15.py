# ==========================================================
# bot.py — Chunk 15: Remaining fixes
# ==========================================================

# ----------------------------------------------------------
# Fix: Thinking message with clickable links
# ----------------------------------------------------------
THINKING_MSG = (
    "🤔 *Hamilton is thinking deeply...*\n\n"
    "While you wait, learn something new:\n"
    "🔭 [Astronomy by KV](https://youtube.com/@astronomybykv90306?si=kDYLhYPnJwF697fb)\n"
    "🎥 [Veritasium](https://youtube.com/@veritasium?si=xsimVU5BCg-4zj0X)\n"
    "📚 [H&K Publications books](https://wa.me/918074231426) — *+91 80742 31426*"
)


# ----------------------------------------------------------
# Fix: Notes prompt — exhaustive + no page cap
# ----------------------------------------------------------
def _send_next_notes_part(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes session.")
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)
    pages_this_req = state.get("pages_this_request", 0)

    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.\n\n"
            "Ask me anything, or /notes for another chapter.",
            parse_mode="Markdown")
        return

    if pages_this_req >= 10:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_10-page batch complete. Type_ `/continue` _for the next batch._",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    topics_text = ""
    for st in group:
        topics_text += f"\n## {st['name']}\n"
        for c in st["concepts"]:
            topics_text += f"- {c}\n"

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    prompt = (
        f"Write COMPREHENSIVE JEE short notes — Part {part_num} of {total}.\n"
        f"Chapter: {state['chapter']} ({state['subject']}, {state['exam']})\n\n"
        f"Cover these subtopics exhaustively:\n{topics_text}\n\n"
        "MANDATORY RULES:\n"
        "1. Write EVERY formula relevant to each subtopic — no shortcuts.\n"
        "2. Include formulas LINKED from other chapters (e.g., if current topic "
        "uses intensity, list every intensity formula from wherever it appears).\n"
        "3. For each concept: definition + formula(s) + 2 common traps + 1 shortcut.\n"
        "4. Provide Applications 1, 2, 3 — real-world or other-chapter uses.\n"
        "5. Include 1-2 exceptional cases / edge conditions per concept.\n"
        "6. Use markdown ## headings, **bold** key terms.\n"
        "7. Wrap display equations in $$...$$, inline math in $...$.\n"
        "8. Do NOT give a title — bot adds header.\n"
        "9. Friendly senior voice — 'Hey, look at this...'\n"
        "10. Be EXHAUSTIVE. Do not summarize. Depth > brevity.\n"
    )

    notes = ai_client.ask_hamilton(state["exam"], prompt)
    timer_manager.stop_generating_timer(bot, uid)

    if not notes:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    header = f"## 📝 {state['chapter']} — Page {part_num}/{total}\n\n"
    full = header + notes + _countdown_footer(uid)
    safe_send(uid, full, parse_mode="Markdown")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_this_req + 1
    state["last_notes"] = notes[:800]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


# Better page estimate — no upper cap, based on concept density
def _estimate_pages(subtopics_count, concepts_count):
    if concepts_count <= 0:
        return 1
    # ~8 concepts per page for exhaustive notes
    pages = max(3, (concepts_count + 7) // 8)
    return pages


# ----------------------------------------------------------
# Fix: Exceptional test — filter to anomaly keywords
# ----------------------------------------------------------
EXCEPTION_KEYWORDS = [
    "anomalous", "anomaly", "exception", "exceptional", "special case",
    "edge case", "deviation", "violation", "fails", "limitation",
    "drawback", "counter", "unusual", "trick", "trap",
]


def _filter_exception_subtopics(subtopics, chapter_data):
    """Keep only subtopics/concepts with exception-related keywords."""
    result = []
    for sub in subtopics:
        sub_low = sub.lower()
        if any(k in sub_low for k in EXCEPTION_KEYWORDS):
            result.append(sub)
    if not result:
        # Fallback: use every subtopic but mark difficulty=hard
        result = list(subtopics)
    return result


# Patch: _start_conceptual_test uses filter when type=exception
_orig_start_conceptual = exam_engine.start_conceptual_test


def _start_conceptual_test_patched(uid, subject, chapter, total_q, test_type="general"):
    if test_type != "exception":
        return _orig_start_conceptual(uid, subject, chapter, total_q, test_type)

    profile = health.load_profile(uid) or {}
    exam = health.exam_of(profile) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        return None

    subs = data[chapter]
    all_subs = list(subs.keys())
    filtered = _filter_exception_subtopics(all_subs, subs)

    plan = []
    if total_q >= len(filtered):
        plan = list(filtered)
        while len(plan) < total_q:
            plan.append(random.choice(filtered))
    else:
        plan = random.sample(filtered, total_q)
    random.shuffle(plan)

    SESS = exam_engine.SESSIONS
    SESS[uid] = {
        "mode": "conceptual",
        "test_type": test_type,
        "exam": exam,
        "subject": subject,
        "chapter": chapter,
        "plan": plan,
        "index": 0,
        "total_q": total_q,
        "started_at": time.time(),
        "questions_done": 0,
        "correct": 0,
        "wrong": 0,
        "skipped": 0,
        "total_time": 0,
        "subtopic_stats": {},
        "current_q": None,
        "current_meta": None,
        "current_started": None,
        "last_q": None,
        "last_meta": None,
    }
    return SESS[uid]


exam_engine.start_conceptual_test = _start_conceptual_test_patched


# ----------------------------------------------------------
# Fix: Source attribution — match by subject
# ----------------------------------------------------------
def _fix_source_detail(source_detail, subject):
    """Sanity-check source attribution against subject."""
    if not source_detail:
        return source_detail
    # OP Tandon, MS Chouhan, JD Lee are Chemistry
    chem_only = ["OP Tandon", "MS Chouhan", "JD Lee"]
    # DC Pandey, HC Verma, Irodov are Physics
    phys_only = ["DC Pandey", "HC Verma", "Irodov", "Cengage Physics"]

    for name in chem_only:
        if name in source_detail and subject != "Chemistry":
            return "Material · Cengage"
    for name in phys_only:
        if name in source_detail and subject != "Physics":
            return "Material · Cengage"
    return source_detail


# ----------------------------------------------------------
# Fix: Difficulty tag — cap by exam
# ----------------------------------------------------------
def _cap_difficulty_for_exam(difficulty, exam):
    if exam == "EAMCET" and difficulty == "hard":
        return "medium"
    if exam == "JEE_MAIN" and difficulty == "hard":
        # Mains can have hard, but not extreme
        return "medium"
    return difficulty


# ----------------------------------------------------------
# Fix: Concept timer + verify
# ----------------------------------------------------------
def _start_concept_timer(uid, total_minutes=60):
    if uid in CONCEPT_TIMERS:
        CONCEPT_TIMERS[uid]["stop"] = True
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


# ----------------------------------------------------------
# Fix: Weekly report + /report command
# ----------------------------------------------------------
@bot.message_handler(commands=['report'])
def cmd_report(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    r = health.overall_health(p)
    summary = health.attempts_summary(p)
    pct = health.predict_percentile(r.get("overall"))
    _, tier = health.estimate_rank(p)

    lines = [
        "📊 *WEEKLY REPORT*",
        "",
        f"👤 {p.get('name','—')}",
        f"🆔 {p.get('hku_id','—')}",
        "",
        "━━━ Overall ━━━",
        f"Health: *{r.get('overall') or 0}/100*",
        f"Predicted %ile: *{pct}*",
        f"Rank tier: *{tier}*",
        "",
        "━━━ Attempts ━━━",
        f"Total: {summary['attempted']}",
        f"✅ Correct: {summary['correct']}",
        f"❌ Wrong: {summary['wrong']}",
        f"🎯 Accuracy: {summary['accuracy']}%",
        "",
        "━━━ Target ━━━",
    ]
    targets = p.get("target_marks", {})
    primary = p.get("priority") or (p.get("exams") or ["—"])[0]
    if isinstance(targets, dict) and primary in targets:
        max_m = MAX_MARKS.get(primary, 100)
        cur = targets[primary]
        lines.append(f"Target: *{cur} / {max_m}*")
        gap = max(0, cur - int((r.get('overall') or 0) / 100 * max_m))
        lines.append(f"Gap: *{gap} marks*")
    else:
        lines.append("_Set target with /target_")

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 15 loaded: remaining bug fixes ready.")

