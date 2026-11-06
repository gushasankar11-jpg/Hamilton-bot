import re, ast

path = "bot_chunks/c04_exam.py"
content = open(path).read()

# ============================================
# STEP 1: Remove duplicate handle_buttons functions
# ============================================
starts = [m.start() for m in re.finditer(r'^def handle_buttons\(call\):', content, re.MULTILINE)]
print(f"[1] Found {len(starts)} handle_buttons functions")

if len(starts) > 1:
    ends = []
    for s in starts:
        after = content[s + 10:]
        m = re.search(r'\n(?=@bot\.|def |class |@app\.)', after)
        ends.append(s + 10 + m.start() + 1 if m else len(content))
    
    for i in range(len(starts) - 1, 0, -1):
        pre = content[:starts[i]]
        dec = re.search(r'@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("f_"\)\)\s*$', pre)
        actual_start = dec.start() if dec else starts[i]
        content = content[:actual_start] + content[ends[i]:]
    
    print(f"[1] Removed {len(starts) - 1} duplicate handlers ✓")

# ============================================
# STEP 2: Replace f_save + f_skip block with INSTANT version
# ============================================
save_patterns = ['elif data in ("f_save", "f_skip"):', 'elif data == "f_save":']
save_start = -1
for p in save_patterns:
    idx = content.find(p)
    if idx != -1:
        save_start = idx
        print(f"[2] Found: {p}")
        break

if save_start != -1:
    after = content[save_start + 10:]
    m = re.search(r'\n\s*elif data == "f_stop"', after)
    if not m:
        m = re.search(r'\n\s*elif data == "f_', after)
    
    if m:
        save_end = save_start + 10 + m.start()
        
        new_save = '''elif data in ("f_save", "f_skip"):
            if data == "f_save":
                if state.get("processing"): return
                if state.get("selected") is None:
                    _b().answer_callback_query(call.id, "⚠️ Select an option first")
                    return
                state["processing"] = True
                state["pyq_timer_active"] = False
                try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
                except: pass
                
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] = state.get("correct", 0) + 1
                else: state["wrong"] = state.get("wrong", 0) + 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    health.record_attempt(uid, state.get("subj", "Physics"), state.get("chapter", ""), state["q"].get("subtopic", ""), is_correct, time_taken)
                except: pass

                if is_correct:
                    result_msg = f"✅ <b>Correct!</b>\\n⏱ {time_taken}s / Ideal {ideal}s"
                else:
                    result_msg = f"❌ <b>Wrong.</b>\\nCorrect: <b>{correct_letter}</b>\\n⏱ {time_taken}s / Ideal {ideal}s"

                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("💡 AI Solution", callback_data="f_solution"), InlineKeyboardButton("▶️ Next", callback_data="f_next_q"))
                kb.add(InlineKeyboardButton("💬 Doubt", callback_data="f_doubt"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                
                _b().send_message(uid, result_msg, parse_mode="HTML", reply_markup=kb)
                state["processing"] = False
                
            else:  # f_skip
                state["skipped"] = state.get("skipped", 0) + 1
                state["pyq_timer_active"] = False
                try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
                except: pass
                _b().send_message(uid, f"⏭ Skipped. Correct: <b>{chr(65 + state['q'].get('correct_index', 0))}</b>", parse_mode="HTML")
                state["pyq_index"] += 1
                send_pyq_q(uid)
                
        '''
        content = content[:save_start] + new_save + content[save_end:]
        print(f"[2] f_save/f_skip block replaced with instant version ✓")

# ============================================
# STEP 3: Add f_solution handler (AI solution with shortcut focus)
# ============================================
if 'data == "f_solution"' not in content:
    next_marker = 'elif data == "f_next_q":'
    if next_marker in content:
        solution_handler = '''elif data == "f_solution":
            try: _b().answer_callback_query(call.id, "Generating...")
            except: pass
            load_msg = _b().send_message(uid, "🧠 <i>Generating shortcut-focused solution...</i>")
            try:
                from c40_vision_ai import get_ai_solution
                q_text = state.get("q", {}).get("q_text", "")
                if not q_text:
                    _b().edit_message_text("❌ No question text available for AI.", chat_id=uid, message_id=load_msg.message_id)
                else:
                    sol = get_ai_solution(q_text)
                    _b().edit_message_text(sol, chat_id=uid, message_id=load_msg.message_id, parse_mode="Markdown")
            except Exception as e:
                _b().edit_message_text(f"❌ AI Error: {e}", chat_id=uid, message_id=load_msg.message_id)
            
        elif data == "f_next_q":'''
        content = content.replace(next_marker, solution_handler, 1)
        print(f"[3] f_solution handler added ✓")

# ============================================
# STEP 4: f_next_q should NOT delete messages
# ============================================
next_start = content.find('elif data == "f_next_q":')
if next_start != -1:
    after = content[next_start + 10:]
    m = re.search(r'\n\s*elif data == "f_', after)
    if m:
        next_end = next_start + 10 + m.start()
        new_next = '''elif data == "f_next_q":
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_index"] += 1
                send_pyq_q(uid)
            else:
                import threading
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()
            
        '''
        content = content[:next_start] + new_next + content[next_end:]
        print(f"[4] f_next_q: no more deletions ✓")

# ============================================
# STEP 5: Ensure send_pyq_q does NOT delete old photos
# ============================================
# Comment out any delete_message on pyq_photo_msg_id
content = re.sub(
    r'try:\s*_b\(\)\.delete_message\(uid,\s*state\["pyq_photo_msg_id"\]\)\s*except:\s*pass',
    '# Keep old photo visible (no delete)',
    content
)
print(f"[5] send_pyq_q: old photos preserved ✓")

# ============================================
# SAVE with syntax check
# ============================================
try:
    ast.parse(content)
    open(path, "w").write(content)
    print(f"\n✅ c04_exam.py saved with all fixes")
except SyntaxError as e:
    print(f"\n❌ SYNTAX ERROR: {e}")
    print("File NOT saved — paste this error so I can fix")
