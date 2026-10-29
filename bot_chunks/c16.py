# ==========================================================
# bot.py — Chunk 16: Notes fix (AI-driven pages + apps + exceptions)
# ==========================================================

NOTES_BATCH_SIZE = 10      # API calls per batch before /continue


def _ask_ai_page_estimate(exam, chapter, subject, subtopics, concepts):
    """Ask AI how many pages are needed for exhaustive notes."""
    topics = "\n".join(f"- {s}" for s in subtopics)
    concept_list = "\n".join(f"- {c}" for c in concepts[:60])

    prompt = (
        f"Chapter: {chapter} ({subject}, {exam})\n"
        f"Subtopics ({len(subtopics)}):\n{topics}\n\n"
        f"Key concepts ({len(concepts)}):\n{concept_list}\n\n"
        "Task: Estimate how many PAGES of short notes are needed to make "
        "a student JEE-ready on this chapter, where each page contains:\n"
        "• definitions + every formula\n"
        "• 2-3 traps\n"
        "• as many applications as needed to solve ALL possible PYQs\n"
        "• exceptional cases\n"
        "• shortcuts\n\n"
        "Rule: one page ≈ one subtopic fully covered with all formulas.\n"
        "Reply with ONLY a single number (the page count). No text."
    )
    try:
        raw = ai_client.ask_hamilton(exam, prompt)
    except Exception:
        return None
    if not raw:
        return None
    import re
    m = re.search(r"\d+", raw)
    if not m:
        return None
    n = int(m.group(0))
    if n < 1:
        n = 1
    if n > 60:
        n = 60
    return n


def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics_list = []
    all_concepts = []
    for sub, val in subs.items():
        cl = val.get("adv", []) if isinstance(val, dict) else val
        subtopics_list.append({"name": sub, "concepts": list(cl)})
        all_concepts.extend(list(cl))

    total_concepts = len(all_concepts)
    total_subtopics = len(subtopics_list)

    # Ask AI for page estimate
    calc_msg = bot.send_message(uid, "⏱️ Analyzing chapter scope…")
    total_pages = _ask_ai_page_estimate(
        exam, chapter, subject,
        [s["name"] for s in subtopics_list],
        all_concepts
    )
    if not total_pages:
        # Fallback: 1 page per subtopic
        total_pages = max(2, total_subtopics)

    try:
        bot.delete_message(uid, calc_msg.message_id)
    except Exception:
        pass

    # Build one group per page (each group = 1 subtopic, or split if subtopic huge)
    groups = []
    for st in subtopics_list:
        concepts = st["concepts"]
        if len(concepts) <= 12:
            groups.append([st])
        else:
            # Split large subtopic into chunks of ~10 concepts
            for i in range(0, len(concepts), 10):
                chunk = concepts[i:i + 10]
                groups.append([{"name": f"{st['name']} (part {i//10 + 1})",
                                "concepts": chunk}])

    # If AI estimated more pages than groups, that's fine — we just use groups
    # If AI estimated fewer, split further
    while len(groups) < total_pages and any(len(g[0]["concepts"]) > 4 for g in groups):
        groups.sort(key=lambda g: len(g[0]["concepts"]), reverse=True)
        big = groups.pop(0)
        st = big[0]
        half = len(st["concepts"]) // 2
        groups.append([{"name": st["name"] + " (a)",
                        "concepts": st["concepts"][:half]}])
        groups.append([{"name": st["name"] + " (b)",
                        "concepts": st["concepts"][half:]}])

    total_parts = len(groups)

    p["_notes_state"] = {
        "subject": subject,
        "chapter": chapter,
        "exam": exam,
        "groups": groups,
        "current_part": 0,
        "total_parts": total_parts,
        "concepts_total": total_concepts,
        "subtopics_total": total_subtopics,
        "pages_this_request": 0,
        "last_notes": "",
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *{chapter}*\n\n"
        f"📖 Subtopics: *{total_subtopics}*\n"
        f"🧠 Concepts: *{total_concepts}*\n"
        f"📄 Pages required: *{total_parts}*\n\n"
        f"_Pages will be generated one by one. "
        f"Every {NOTES_BATCH_SIZE} pages I'll ask you to /continue._",
        parse_mode="Markdown")
    time.sleep(0.6)
    _send_next_notes_part(uid)


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

    if pages_this_req >= NOTES_BATCH_SIZE:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_Batch of {NOTES_BATCH_SIZE} complete._\n"
            f"Type `/continue` for the next batch.",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    topics_text = ""
    for st in group:
        topics_text += f"\n### {st['name']}\n"
        for c in st["concepts"]:
            topics_text += f"- {c}\n"

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    prompt = (
        f"You are writing EXHAUSTIVE JEE short notes — Page {part_num} of {total}.\n"
        f"Chapter: {state['chapter']} ({state['subject']}, {state['exam']})\n\n"
        f"Subtopics to fully cover on this page:\n{topics_text}\n\n"
        "MANDATORY RULES:\n"
        "1. Write EVERY formula related to these subtopics — no skipping.\n"
        "2. Include formulas LINKED from other chapters (e.g., if intensity or "
        "force appears, list all its forms from every relevant chapter).\n"
        "3. Structure for each subtopic:\n"
        "   ### <Subtopic name>\n"
        "   **Definition** — one line\n"
        "   **Formulas** — every formula with variable meanings\n"
        "   **Traps** — 2-3 common mistakes\n"
        "   **Applications** — include AS MANY as needed so a student can "
        "solve ANY previous-year question on this subtopic. Do not limit to 3.\n"
        "   **Exceptional cases** — edge conditions, anomalies\n"
        "   **Shortcut** — if any\n"
        "4. Use $$...$$ for display math, $...$ for inline math.\n"
        "5. Friendly senior voice: 'Hey, look at this…'\n"
        "6. No title — bot adds header.\n"
        "7. Depth over brevity. Be thorough.\n"
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
    state["last_notes"] = notes[:1200]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


@bot.message_handler(commands=['continue_disabled_' + 'c16'])
def cmd_continue(message):
    uid = message.chat.id
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes in progress. Type /notes to start.")
        return
    state["pages_this_request"] = 0
    p["_notes_state"] = state
    save_profile(uid, p)
    _send_next_notes_part(uid)


print("bot.py Chunk 16 loaded: notes AI-estimated pages + apps + exceptions.")

