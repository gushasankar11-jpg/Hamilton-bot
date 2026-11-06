import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# 1. Modify f_pyq_paper_idx to show instructions
old_paper = '''        if data.startswith("f_pyq_paper_idx:"):
            idx = int(data.split(":")[1])
            paper_name = state.get("paper_list", [])[idx]
            paper_data = db.get("papers", {}).get(paper_name)
            if not paper_data: return
            
            state["mode"] = "pyq"; state["subj"] = "Full Paper"; state["chapter"] = paper_name
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = paper_data.get("questions", [])
            state["pyq_normal"] = []
            state["pyq_index"] = 0; state["pyq_is_paper"] = True
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            def run_countdown():
                cdown = _b().send_message(uid, "📄 <b>Starting Paper Test...</b>\\n\\n5...")
                for n in [4, 3, 2, 1]:
                    time.sleep(1)
                    try: _b().edit_message_text(f"📄 <b>Starting Paper Test...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                    except: pass
                time.sleep(1)
                _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                time.sleep(0.5)
                send_pyq_q(uid)
            threading.Thread(target=run_countdown, daemon=True).start()
            return'''

new_paper = '''        if data.startswith("f_pyq_paper_idx:"):
            idx = int(data.split(":")[1])
            paper_name = state.get("paper_list", [])[idx]
            paper_data = db.get("papers", {}).get(paper_name)
            if not paper_data: return
            
            state["mode"] = "pyq"; state["subj"] = "Full Paper"; state["chapter"] = paper_name
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = paper_data.get("questions", [])
            state["pyq_normal"] = []
            state["pyq_index"] = 0; state["pyq_is_paper"] = True
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            inst_img = paper_data.get("instructions_img")
            if inst_img and os.path.exists(inst_img):
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ I have read the instructions, Start Test", callback_data="f_start_paper"))
                with open(inst_img, "rb") as f:
                    _b().send_photo(uid, f, caption="📜 <b>Instructions</b>\\nPlease read the instructions carefully before starting.", parse_mode="HTML", reply_markup=kb)
            else:
                # No instructions, start directly
                def run_countdown_direct():
                    cdown = _b().send_message(uid, "📄 <b>Starting Paper Test...</b>\\n\\n5...")
                    for n in [4, 3, 2, 1]:
                        time.sleep(1)
                        try: _b().edit_message_text(f"📄 <b>Starting Paper Test...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                        except: pass
                    time.sleep(1)
                    _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                    time.sleep(0.5)
                    send_pyq_q(uid)
                threading.Thread(target=run_countdown_direct, daemon=True).start()
            return

        if data == "f_start_paper":
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            def run_countdown_start():
                cdown = _b().send_message(uid, "📄 <b>Starting Paper Test...</b>\\n\\n5...")
                for n in [4, 3, 2, 1]:
                    time.sleep(1)
                    try: _b().edit_message_text(f"📄 <b>Starting Paper Test...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                    except: pass
                time.sleep(1)
                _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                time.sleep(0.5)
                send_pyq_q(uid)
            threading.Thread(target=run_countdown_start, daemon=True).start()
            return'''

if old_paper in content:
    content = content.replace(old_paper, new_paper)
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ Patched UI: Instructions -> Start Button -> Countdown.")
    except SyntaxError as e:
        print(f"❌ Syntax Error: {e}")
else:
    print("⚠️ Could not find f_pyq_paper_idx block.")

