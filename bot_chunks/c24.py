# ==========================================================
# bot.py — Chunk 24: Bulletproof /continue handler
# ==========================================================

@bot.message_handler(commands=['continue'])
def cmd_continue(message):
    uid = message.chat.id
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes in progress. Type /notes to start.")
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)

    if current >= total:
        safe_send(uid, f"✅ All {total} pages already delivered for {state['chapter']}.")
        p.pop("_notes_state", None)
        save_profile(uid, p)
        return

    safe_send(uid, f"▶️ Continuing from page {current+1}…")

    # Directly generate up to 10 pages (no recursion)
    for i in range(NOTES_BATCH):
        p = load_profile(uid)
        state = p.get("_notes_state")
        if not state:
            break
        curr = state.get("current_part", 0)
        tot = state.get("total_parts", 1)
        if curr >= tot:
            break

        group = state["groups"][curr]
        part_num = curr + 1

        timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{tot}")
        page_text = generate_page(
            state["exam"], state["subject"], state["chapter"],
            part_num, tot, group, state.get("chapter_type", "mixed"))
        timer_manager.stop_generating_timer(bot, uid)

        if not page_text:
            safe_send(uid, f"⚠️ Page {part_num} failed. Try /continue again.")
            break

        header = f"# {state['chapter']} — Page {part_num}/{tot}\n\n"
        content = header + page_text
        try:
            import os
            os.makedirs("notes_files", exist_ok=True)
            safe_name = state['chapter'].replace(' ', '_').replace('/', '_')
            fname = f"notes_files/{safe_name}_p{part_num}.md"
            with open(fname, "w") as nf:
                nf.write(content)
            with open(fname, "rb") as nf:
                bot.send_document(uid, nf,
                    caption=f"📝 {state['chapter']} — Page {part_num}/{tot}")
            try:
                os.remove(fname)
            except Exception:
                pass
        except Exception as e:
            print(f"[NOTES-FILE] {e}")
            safe_send(uid, content)

        state["current_part"] = part_num
        state["pages_this_request"] = 0
        p["_notes_state"] = state
        save_profile(uid, p)
        time.sleep(0.5)

    # After batch → show status
    p = load_profile(uid)
    state = p.get("_notes_state")
    if state:
        curr = state.get("current_part", 0)
        tot = state.get("total_parts", 1)
        if curr < tot:
            safe_send(uid,
                f"📄 *{curr}/{tot} pages delivered*\n\n"
                f"_Type_ `/continue` _for the next batch._",
                parse_mode="Markdown")
        else:
            p.pop("_notes_state", None)
            save_profile(uid, p)
            safe_send(uid,
                f"✅ *All {tot} pages delivered* for {state['chapter']}.",
                parse_mode="Markdown")


print("bot.py Chunk 24 loaded: bulletproof /continue ready.")

