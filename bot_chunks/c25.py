# ==========================================================
# bot.py — Chunk 25: AUTO notes (no /continue needed)
# ==========================================================

from notes_engine import analyze_chapter, generate_page
import threading as _threading


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
        f"_Generating all {total} pages automatically. This may take a few minutes._",
        parse_mode="Markdown")
    time.sleep(0.5)

    # Background thread — sends all pages without asking /continue
    def _worker():
        for _ in range(total + 2):  # safety cap
            p2 = load_profile(uid)
            st = p2.get("_notes_state")
            if not st:
                break
            curr = st.get("current_part", 0)
            tot = st.get("total_parts", 1)
            if curr >= tot:
                break

            group = st["groups"][curr]
            part_num = curr + 1

            timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{tot}")
            page_text = generate_page(
                st["exam"], st["subject"], st["chapter"],
                part_num, tot, group, st.get("chapter_type", "mixed"))
            timer_manager.stop_generating_timer(bot, uid)

            if not page_text:
                safe_send(uid, f"⚠️ Page {part_num} failed. Stopping.")
                break

            header = f"# {st['chapter']} — Page {part_num}/{tot}\n\n"
            content = header + page_text
            try:
                import os
                os.makedirs("notes_files", exist_ok=True)
                safe_name = st['chapter'].replace(' ', '_').replace('/', '_')
                fname = f"notes_files/{safe_name}_p{part_num}.md"
                with open(fname, "w") as nf:
                    nf.write(content)
                with open(fname, "rb") as nf:
                    bot.send_document(uid, nf,
                        caption=f"📝 {st['chapter']} — Page {part_num}/{tot}")
                try:
                    os.remove(fname)
                except Exception:
                    pass
            except Exception as e:
                print(f"[NOTES-FILE] {e}")
                safe_send(uid, content)

            st["current_part"] = part_num
            p2["_notes_state"] = st
            save_profile(uid, p2)
            time.sleep(0.7)

        # Final
        p3 = load_profile(uid)
        st3 = p3.get("_notes_state")
        if st3 and st3.get("current_part", 0) >= st3.get("total_parts", 1):
            p3.pop("_notes_state", None)
            save_profile(uid, p3)
            safe_send(uid,
                f"✅ *All {st3['total_parts']} pages delivered* for {st3['chapter']}.",
                parse_mode="Markdown")

    _threading.Thread(target=_worker, daemon=True).start()


# Old /continue handlers now redundant, but keep a friendly message
@bot.message_handler(commands=['continue'])
def cmd_continue(message):
    uid = message.chat.id
    safe_send(uid,
        "ℹ️ Notes now generate **automatically** — no `/continue` needed.\n"
        "If the bot stopped early, just run `/notes` again.",
        parse_mode="Markdown")


print("bot.py Chunk 25 loaded: AUTO notes ready.")

