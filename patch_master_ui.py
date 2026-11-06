import ast, re

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# --- A. FORCE REPLACE f_save BLOCK ---
# We find the exact line where f_save is processed
start_match = re.search(r'(\s*)if data == "f_save":', content)
if not start_match:
    start_match = re.search(r'(\s*)elif data == "f_save":', content)

if start_match:
    start_idx = start_match.start()
    # Find the next elif to know where it ends
    rest = content[start_idx:]
    end_match = re.search(r'\n\s*elif data == "f_skip":', rest)
    if end_match:
        end_idx = start_idx + end_match.end()
        
        # The new clean block
        fast_save = '''            if data == "f_save":
                if state.get("processing"): return
                state["processing"] = True
                state["pyq_timer_active"] = False
                try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
                except: pass
                
                if state.get("selected") is None:
                    state["processing"] = False
                    _b().send_message(uid, "⚠️ Please select an option first.")
                    return
                
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                if is_correct:
                    msg = f"✅ <b>Correct!</b>  ⏱ {time_taken}s / Ideal {ideal}s"
                else:
                    msg = f"❌ <b>Wrong.</b> Answer: <b>{correct_letter}</b>  ⏱ {time_taken}s / Ideal {ideal}s"

                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("💡 Get AI Solution", callback_data="f_solution"), InlineKeyboardButton("▶️ Next", callback_data="f_next_q"))
                kb.add(InlineKeyboardButton("💬 Doubt", callback_data="f_doubt"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                
                # Instant response!
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":'''
        
        content = content[:start_idx] + fast_save + content[end_idx:]
        print("✅ f_save block replaced (Instant save, no freeze).")

# --- B. ADD YEAR NAVIGATION BUTTON IN send_pyq_q ---
# We inject a "Filter by Year" button at the bottom of the keyboard
if "f_year_filter" not in content:
    # Add the button to send_pyq_q
    old_kb = '''        kb = InlineKeyboardMarkup(row_width=4)
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))'''
    
    new_kb = '''        kb = InlineKeyboardMarkup(row_width=4)
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        kb.add(InlineKeyboardButton("📅 Filter by Year", callback_data="f_year_filter"))'''
    
    if old_kb in content:
        content = content.replace(old_kb, new_kb)
        print("✅ Added 'Filter by Year' button to UI.")

    # Add the callback handler for f_year_filter
    if 'data == "f_year_filter"' not in content:
        marker = 'elif data == "f_next_q":'
        year_handler = '''elif data == "f_year_filter":
            # Find all unique years in this chapter
            q_list = state.get("pyq_questions", [])
            years = set()
            for q in q_list:
                src = q.get("source", "")
                import re
                m = re.search(r'(20\\d\\d)', src)
                if m: years.add(m.group(1))
            
            years = sorted(list(years), reverse=True)
            kb = InlineKeyboardMarkup(row_width=3)
            for y in years:
                kb.add(InlineKeyboardButton(y, callback_data=f"f_year_jump:{y}"))
            kb.add(InlineKeyboardButton("🔙 All Years", callback_data="f_year_jump:all"))
            _b().send_message(uid, "📅 <b>Select Year to Filter:</b>", reply_markup=kb)
            
        elif data.startswith("f_year_jump:"):
            year = data.split(":")[1]
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            original = state.get("pyq_original_list", [])
            if not original:
                original = state.get("pyq_questions", [])
                state["pyq_original_list"] = original[:] # Save backup
            
            if year == "all":
                state["pyq_questions"] = original
            else:
                filtered = [q for q in original if year in q.get("source", "")]
                if not filtered:
                    _b().send_message(uid, f"⚠️ No questions found for {year}.")
                    return
                state["pyq_questions"] = filtered
            
            state["pyq_index"] = 0
            send_pyq_q(uid)
            
        elif data == "f_next_q":'''
        content = content.replace(marker, year_handler, 1)
        print("✅ Added Year Navigation handlers.")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c04_exam.py saved perfectly.")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
