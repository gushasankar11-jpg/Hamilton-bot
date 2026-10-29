# ==========================================================
# bot.py — Chunk 12: New page-based notes flow (override)
# ==========================================================

NOTES_MAX_PAGES_PER_REQUEST = 10


def _estimate_pages(subtopics_count, concepts_count):
    """Local math — decide page count from concept count."""
    if concepts_count <= 0:
        return 1
    # Aim for ~10-14 concepts per page
    pages = max(2, (concepts_count + 13) // 14)
    # Cap at reasonable max
    if pages > 20:
        pages = 20
    return pages


def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics_list = []
    for sub, val in subs.items():
        cl = val.get("adv", []) if isinstance(val, dict) else val
        subtopics_list.append({"name": sub, "concepts": list(cl)})

    total_concepts = sum(len(s["concepts"]) for s in subtopics_list)
    total_subtopics = len(subtopics_list)

    # Show "Analyzing" briefly
    calc_msg = bot.send_message(uid, "⏱️ Analyzing chapter scope...")
    time.sleep(1.5)

    total_pages = _estimate_pages(total_subtopics, total_concepts)

    # Delete "analyzing"
    try:
        bot.delete_message(uid, calc_msg.message_id)
    except Exception:
        pass

    # Split subtopics across pages — keep page balance
    n_subs = len(subtopics_list)
    subs_per_page = max(1, (n_subs + total_pages - 1) // total_pages)
    groups = []
    for i in range(0, n_subs, subs_per_page):
        groups.append(subtopics_list[i:i + subs_per_page])

    # Ensure we don't have more groups than total_pages
    if len(groups) > total_pages:
        # Merge extras
        while len(groups) > total_pages:
            last = groups.pop()
            groups[-1].extend(last)
    # Ensure we have at least total_pages groups
    while len(groups) < total_pages and len(groups) < n_subs:
        # Split the largest group
        groups.sort(key=len, reverse=True)
        biggest = groups.pop(0)
        if len(biggest) < 2:
            break
        mid = len(biggest) // 2
        groups.append(biggest[:mid])
        groups.append(biggest[mid:])

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
        f"_Sending pages one by one..._",
        parse_mode="Markdown")
    time.sleep(0.5)
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

    # All pages done?
    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.\n\n"
            "Ask me anything about it, or /notes for another chapter.",
            parse_mode="Markdown")
        return

    # Hit 10-page per-request limit?
    if pages_this_req >= NOTES_MAX_PAGES_PER_REQUEST:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_10-page batch complete. Type_ `/continue` _for the next batch._",
            parse_mode="Markdown")
        p["_notes_state"] = state
        save_profile(uid, p)
        return

    # Generate next page
    group = state["groups"][current]
    part_num = current + 1

    topics_text = ""
    for st in group:
        topics_text += f"\n## {st['name']}\n"
        for c in st["concepts"]:
            topics_text += f"- {c}\n"

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    prompt = (
        f"Write SHORT NOTES Part {part_num} of {total} for JEE preparation.\n"
        f"Chapter: {state['chapter']} ({state['subject']})\n\n"
        f"Cover these subtopics thoroughly:\n{topics_text}\n\n"
        "FORMAT REQUIREMENTS:\n"
        "- Use markdown: ## for subtopic headings, **bold** for key terms\n"
        "- Use $$...$$ for display equations (LaTeX INSIDE the $$)\n"
        "- Use $...$ for inline math\n"
        "- Include definitions, key formulas, traps, shortcuts\n"
        "- Friendly senior tone (Hey, look at this...)\n"
        "- Cover EVERY listed concept\n"
        "- Do NOT include a title — the bot already adds header\n"
    )

    notes = ai_client.ask_hamilton(state["exam"], prompt)
    timer_manager.stop_generating_timer(bot, uid)

    if not notes:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    header = f"📝 *{state['chapter']}* — Page {part_num}/{total}\n\n"
    full = header + notes + _countdown_footer(uid)
    safe_send(uid, full, parse_mode="Markdown")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_this_req + 1
    state["last_notes"] = notes[:800]
    p["_notes_state"] = state
    save_profile(uid, p)

    # Auto-send next page after short delay
    time.sleep(1)
    _send_next_notes_part(uid)


# Override /continue to reset per-request counter
@bot.message_handler(commands=['continue_old_disabled'])
def cmd_continue_old_disabled(message):
    uid = message.chat.id
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        # Maybe a plain continue with nothing pending
        safe_send(uid, "No notes in progress. Type /notes to start.")
        return
    state["pages_this_request"] = 0
    p["_notes_state"] = state
    save_profile(uid, p)
    _send_next_notes_part(uid)


print("bot.py Chunk 12 loaded: new page-based notes flow ready.")

