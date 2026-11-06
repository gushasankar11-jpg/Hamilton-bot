import ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# Find f_pyq: handler for papers mode
papers_handler = '''elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                years = list(db.get("papers", {}).keys())
                if not years:
                    _b().answer_callback_query(call.id, "No papers uploaded yet.")
                    return
                for yr in years:
                    kb.add(InlineKeyboardButton(yr, callback_data=f"f_pyq_yr:{yr}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\\nSelect Year:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)'''

new_papers = '''elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                papers = db.get("papers", {})
                if not papers:
                    _b().answer_callback_query(call.id, "No papers extracted yet.", show_alert=True)
                    _b().send_message(uid, "⚠️ No papers found. Run `python3 extract_papers.py` on your server.")
                    return
                for paper_name, info in papers.items():
                    year = info.get("year", "?")
                    short = paper_name[:35]
                    kb.add(InlineKeyboardButton(f"📅 {year} - {short}", callback_data=f"f_pyq_paper:{paper_name}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text(f"📝 <b>Previous Paper Test</b>\\n{len(papers)} paper(s) available:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)'''

# Replace old handler
old_loop = content.find('elif ptype == "papers":')
if old_loop != -1:
    old_end = content.find('elif data', old_loop + 30)
    if old_end == -1: old_end = content.find('elif data.', old_loop + 30)
    if old_end != -1:
        content = content[:old_loop] + new_papers + content[old_end:]
        print("✅ Papers handler replaced")

# Add f_pyq_paper handler
if 'f_pyq_paper:' not in content:
    marker = 'elif data.startswith("f_pyq_ch:")'
    paper_launch = '''elif data.startswith("f_pyq_paper:"):
            paper_name = data.split(":", 1)[1]
            import json
            with open("data/pyq_master.json") as f: db = json.load(f)
            paper_data = db.get("papers", {}).get(paper_name)
            if not paper_data:
                _b().answer_callback_query(call.id, "Paper not found.", show_alert=True)
                return
            
            state["mode"] = "pyq"
            state["subj"] = "Full Paper"
            state["chapter"] = paper_name
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = paper_data.get("questions", [])
            state["pyq_normal"] = []
            state["pyq_index"] = 0
            state["pyq_is_paper"] = True
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            # Countdown then start
            cdown = _b().send_message(uid, "📄 <b>Starting Paper Test...</b>\\n\\n5...")
            import time as _t
            for n in [4, 3, 2, 1]:
                _t.sleep(1)
                try: _b().edit_message_text(f"📄 <b>Starting Paper Test...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                except: pass
            _t.sleep(1)
            _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
            _t.sleep(0.5)
            send_pyq_q(uid)
            
        elif data.startswith("f_pyq_ch:")'''
    content = content.replace(marker, paper_launch, 1)
    print("✅ f_pyq_paper handler added (with 5-4-3-2-1 countdown!)")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved")
except SyntaxError as e:
    print(f"❌ Syntax: {e}")
