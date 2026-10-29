# ==========================================================
# bot.py — Chunk 19: Better page estimate + better notes prompt
# ==========================================================

# ----------------------------------------------------------
# Fix: Page estimate never below subtopic count
# ----------------------------------------------------------
def _ask_ai_page_estimate(exam, chapter, subject, subtopics, concepts):
    """Ask AI for pages needed. Then enforce minimum = len(subtopics)."""
    topics = "\n".join(f"- {s}" for s in subtopics)
    concept_list = "\n".join(f"- {c}" for c in concepts[:80])

    prompt = (
        f"Chapter: {chapter} ({subject}, {exam})\n"
        f"Subtopics ({len(subtopics)}):\n{topics}\n\n"
        f"Concepts ({len(concepts)}):\n{concept_list}\n\n"
        "Task: Estimate how many A4 PAGES of exhaustive JEE short notes are "
        "needed so a student can solve EVERY PYQ on this chapter.\n\n"
        "Guidelines:\n"
        "• Minimum: 1 page per subtopic (never less).\n"
        "• Matrix-heavy or formula-dense chapters: 2-3 pages per subtopic.\n"
        "• Matrices, determinants, calculus, conics → HIGH page count.\n"
        "• Simple chapters can be 1 page per subtopic.\n\n"
        "Reply with ONLY a single number (integer). No text, no explanation."
    )
    try:
        raw = ai_client.ask_hamilton(exam, prompt)
    except Exception:
        raw = None

    import re
    n = None
    if raw:
        m = re.search(r"\d+", raw)
        if m:
            try:
                n = int(m.group(0))
            except Exception:
                n = None

    # Enforce minimum = subtopic count
    min_pages = max(1, len(subtopics))
    if n is None or n < min_pages:
        n = min_pages
    # Enforce maximum = 3 × subtopics (avoid runaway)
    max_pages = len(subtopics) * 3
    if n > max_pages:
        n = max_pages
    return n


# ----------------------------------------------------------
# Better notes prompt — matrix-aware, formulas-mandatory
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
            f"_Batch of 10 complete._\n"
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
        f"You are writing COMPLETE JEE short notes — Page {part_num} of {total}.\n"
        f"Chapter: {state['chapter']} ({state['subject']}, {state['exam']})\n\n"
        f"Cover these subtopics FULLY on this page:\n{topics_text}\n\n"
        "ABSOLUTE REQUIREMENTS:\n"
        "1. Write EVERY formula relevant to each subtopic. Zero omissions.\n"
        "2. Include formulas from OTHER chapters that connect to these "
        "subtopics (e.g., eigenvalues relate to characteristic polynomials).\n"
        "3. Structure for each subtopic:\n"
        "   ### <Subtopic>\n"
        "   **Definition** — one line\n"
        "   **Formulas** — EVERY formula, each wrapped in $$...$$ or $...$\n"
        "   **Traps** — 2-3 common mistakes students make\n"
        "   **Applications** — as many as needed to solve every possible PYQ. "
        "Do not limit the count. Real-world and cross-chapter uses.\n"
        "   **Exceptional cases** — edge conditions, special scenarios\n"
        "   **Shortcut** — a memory trick or fast method\n\n"
        "4. CRITICAL — MATRICES/DETERMINANTS: use proper LaTeX environments:\n"
        "   $$A = \\begin{bmatrix} 1 & 2 \\\\ 3 & 4 \\end{bmatrix}$$\n"
        "   $$\\det(A) = \\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix} = ad - bc$$\n"
        "   Wrap environment blocks in $$...$$ or they will not render.\n\n"
        "5. All math MUST use $ for inline, $$ for display. Raw LaTeX without "
        "$ markers will be unreadable.\n"
        "6. Friendly senior voice: 'Hey, look at this…'\n"
        "7. Do NOT write a title — the bot adds the header.\n"
        "8. Depth > brevity. Never shorten formulas. Be exhaustive."
    )

    notes = ai_client.ask_hamilton(state["exam"], prompt)
    timer_manager.stop_generating_timer(bot, uid)

    if not notes:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    header = f"## 📝 {state['chapter']} — Page {part_num}/{total}\n\n"
    full = header + notes + _countdown_footer(uid)
    safe_send(uid, full, parse_mode="Markdown")

    # .md file for copyability
    try:
        import os
        os.makedirs("notes_files", exist_ok=True)
        fname = f"notes_files/{state['chapter'].replace(' ','_')}_p{part_num}.md"
        with open(fname, "w") as nf:
            nf.write(f"# {state['chapter']} — Page {part_num}/{total}\n\n")
            nf.write(notes)
        with open(fname, "rb") as nf:
            bot.send_document(uid, nf)
        try:
            os.remove(fname)
        except Exception:
            pass
    except Exception as e:
        print(f"[NOTES-MD] {e}")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_this_req + 1
    state["last_notes"] = notes[:1200]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


print("bot.py Chunk 19 loaded: better page estimate + matrix-aware notes.")

