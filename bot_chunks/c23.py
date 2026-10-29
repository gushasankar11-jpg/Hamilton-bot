# ==========================================================
# bot.py — Chunk 23: Notes file-only + /continue fix
# ==========================================================

from notes_engine import analyze_chapter, generate_page

NOTES_BATCH = 10


def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics = list(subs.keys())
    concepts = {s: (subs[s].get("adv", []) if isinstance(subs[s], dict) else subs[s])
                for s in subtopics}
    flat = sum(concepts.values(), [])

    calc_msg = bot.send_message(uid, "⏱️ Analyzing chapter scope…")
    analysis = analyze_chapter(exam, subject, chapter, subtopics, flat)
    try:
        bot.delete_message(uid, calc_msg.message_id)
    except Exception:
        pass

    total = analysis["pages_required"]
    ctype = analysis["chapter_type"]

    n = len(subtopics)
    per_page = max(1, (n + total - 1) // total)
    groups = []
    for i in range(0, n, per_page):
        chunk = subtopics[i:i + per_page]
        groups.append([{"name": s, "concepts": concepts[s]} for s in chunk])
    while len(groups) < total and any(len(g) > 1 for g in groups):
        groups.sort(key=len, reverse=True)
        big = groups.pop(0)
        mid = len(big) // 2
        groups.append(big[:mid])
        groups.append(big[mid:])
    total = len(groups)

    p["_notes_state"] = {
        "subject": subject,
        "chapter": chapter,
        "exam": exam,
        "chapter_type": ctype,
        "groups": groups,
        "current_part": 0,
        "total_parts": total,
        "pages_this_request": 0,
        "concepts_total": len(flat),
        "subtopics_total": len(subtopics),
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *{chapter}*\n\n"
        f"📖 Subtopics: *{len(subtopics)}*\n"
        f"🧠 Concepts: *{len(flat)}*\n"
        f"📄 Pages required: *{total}*\n"
        f"🎯 Type: *{ctype}*\n\n"
        f"_Sending .md files one by one. "
        f"Every {NOTES_BATCH} pages I'll ask for_ `/continue` _._",
        parse_mode="Markdown")
    time.sleep(0.6)
    _send_next_notes_part(uid)


def _send_next_notes_part(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)
    pages_req = state.get("pages_this_request", 0)

    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.",
            parse_mode="Markdown")
        return

    if pages_req >= NOTES_BATCH:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_Type_ `/continue` _for the next batch of {NOTES_BATCH}._",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    page_text = generate_page(
        state["exam"], state["subject"], state["chapter"],
        part_num, total, group, state.get("chapter_type", "mixed")
    )

    timer_manager.stop_generating_timer(bot, uid)

    if not page_text:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    # Build .md file
    header = f"# {state['chapter']} — Page {part_num}/{total}\n\n"
    content = header + page_text

    try:
        import os
        os.makedirs("notes_files", exist_ok=True)
        safe_name = state['chapter'].replace(' ', '_').replace('/', '_')
        fname = f"notes_files/{safe_name}_p{part_num}.md"
        with open(fname, "w") as nf:
            nf.write(content)
        with open(fname, "rb") as nf:
            bot.send_document(
                uid, nf,
                caption=f"📝 {state['chapter']} — Page {part_num}/{total}"
            )
        try:
            os.remove(fname)
        except Exception:
            pass
    except Exception as e:
        print(f"[NOTES-FILE] {e}")
        # Fallback inline if file fails
        safe_send(uid, content, parse_mode="Markdown")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_req + 1
    state["last_notes"] = page_text[:800]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


# Aliases — fix any old references
_send_next_notes_batch = _send_next_notes_part


@bot.message_handler(commands=['continue_disabled_' + 'c23'])
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
    safe_send(uid, "▶️ Continuing notes…")
    _send_next_notes_part(uid)


print("bot.py Chunk 23 loaded: notes file-only + continue fixed.")

