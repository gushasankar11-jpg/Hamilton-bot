import ast, re, shutil

path = "bot_chunks/c04_exam.py"
shutil.copy(path, path + ".bak_dedup")
print(f"✅ Backup: {path}.bak_dedup")

def load(): return open(path).read()
def save(c, label=""):
    try:
        ast.parse(c)
    except SyntaxError as e:
        print(f"❌ {label} SYNTAX ERROR: {e}")
        return False
    open(path, "w").write(c)
    print(f"✅ {label} saved")
    return True

# ===== STEP 1: Remove duplicate handle_buttons =====
print("\n=== STEP 1: Remove duplicates ===")
content = load()
lines = content.split('\n')
handler_lines = [i for i, l in enumerate(lines) if l.strip() == 'def handle_buttons(call):']
print(f"Found {len(handler_lines)} handle_buttons at lines: {[l+1 for l in handler_lines]}")

if len(handler_lines) > 1:
    to_delete = set()
    for idx in handler_lines[1:]:
        # Find decorator above (must contain callback_query_handler)
        dec = idx - 1
        while dec >= 0 and '@bot.callback_query_handler' not in lines[dec]:
            dec -= 1
        if dec < 0: dec = idx - 1
        
        # Find end: next @bot. decorator or module-level def
        end = idx + 1
        while end < len(lines):
            s = lines[end].strip()
            if s.startswith('@bot.') or (s.startswith('def ') and not lines[end].startswith(' ')) or (s.startswith('class ') and not lines[end].startswith(' ')):
                break
            end += 1
        
        for j in range(dec, end):
            to_delete.add(j)
    
    new_lines = [l for i, l in enumerate(lines) if i not in to_delete]
    new_content = '\n'.join(new_lines)
    print(f"Removed {len(to_delete)} lines of duplicates")
    if not save(new_content, "STEP 1"):
        exit(1)
else:
    print("No duplicates — skipping")

# ===== STEP 2: Replace f_save block with INSTANT version =====
print("\n=== STEP 2: Fix f_save (make instant, no AI) ===")
content = load()

# Find "elif data in ("f_save", "f_skip"):"
m = re.search(r'\n([ \t]*)elif data in \("f_save", "f_skip"\):', content)
if not m:
    m = re.search(r'\n([ \t]*)elif data == "f_save":', content)

if not m:
    print("❌ f_save block not found. Not saving.")
    exit(1)

indent = m.group(1)
start = m.start() + 1  # skip the \n

# Find end - next elif at same or lower indent
rest = content[start:]
end_re = re.compile(r'\n' + re.escape(indent) + r'elif ')
em = end_re.search(rest)
if not em:
    print("❌ End of f_save block not found. Not saving.")
    exit(1)

end = start + em.start()

# Build the new block
I1 = indent + '    '
I2 = I1 + '    '
I3 = I2 + '    '

blk = []
blk.append(f'{indent}elif data in ("f_save", "f_skip"):')
blk.append(f'{I1}if data == "f_save":')
blk.append(f'{I2}if state.get("processing"): return')
blk.append(f'{I2}if state.get("selected") is None:')
blk.append(f'{I3}_b().answer_callback_query(call.id, "⚠️ Select an option")')
blk.append(f'{I3}return')
blk.append(f'{I2}state["processing"] = True')
blk.append(f'{I2}state["pyq_timer_active"] = False')
blk.append(f'{I2}try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)')
blk.append(f'{I2}except: pass')
blk.append('')
blk.append(f'{I2}is_correct = state["selected"] == state["q"].get("correct_index", 0)')
blk.append(f'{I2}if is_correct: state["correct"] = state.get("correct", 0) + 1')
blk.append(f'{I2}else: state["wrong"] = state.get("wrong", 0) + 1')
blk.append('')
blk.append(f'{I2}time_taken = int(time.time() - state.get("q_start_time", time.time()))')
blk.append(f'{I2}ideal = state["q"].get("ideal_time", 60)')
blk.append(f'{I2}correct_letter = chr(65 + state["q"].get("correct_index", 0))')
blk.append('')
blk.append(f'{I2}try:')
blk.append(f'{I3}import health')
blk.append(f'{I3}health.record_attempt(uid, state.get("subj", "Physics"), state.get("chapter", ""), state["q"].get("subtopic", ""), is_correct, time_taken)')
blk.append(f'{I2}except: pass')
blk.append('')
blk.append(f'{I2}if is_correct:')
blk.append(f'{I3}result_msg = f"✅ <b>Correct!</b>\\n⏱ {{time_taken}}s / Ideal {{ideal}}s"')
blk.append(f'{I2}else:')
blk.append(f'{I3}result_msg = f"❌ <b>Wrong.</b>\\nCorrect: <b>{{correct_letter}}</b>\\n⏱ {{time_taken}}s / Ideal {{ideal}}s"')
blk.append('')
blk.append(f'{I2}kb = InlineKeyboardMarkup(row_width=2)')
blk.append(f'{I2}kb.add(InlineKeyboardButton("💡 AI Solution", callback_data="f_solution"), InlineKeyboardButton("▶️ Next", callback_data="f_next_q"))')
blk.append(f'{I2}kb.add(InlineKeyboardButton("💬 Doubt", callback_data="f_doubt"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))')
blk.append('')
blk.append(f'{I2}_b().send_message(uid, result_msg, parse_mode="HTML", reply_markup=kb)')
blk.append(f'{I2}state["processing"] = False')
blk.append(f'{I1}else:')
blk.append(f'{I2}state["skipped"] = state.get("skipped", 0) + 1')
blk.append(f'{I2}state["pyq_timer_active"] = False')
blk.append(f'{I2}try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)')
blk.append(f'{I2}except: pass')
blk.append(f'{I2}state["pyq_index"] += 1')
blk.append(f'{I2}send_pyq_q(uid)')
blk.append('')

new_block = '\n'.join(blk)

content = content[:start] + new_block + content[end:]

# Also remove "Verifying your response" from any surviving spots
content = content.replace('_b().send_message(uid, "🔎 <b>Verifying your response...</b>", parse_mode="HTML")\n', '')

if not save(content, "STEP 2"):
    print("\n❌ Rolling back from backup...")
    shutil.copy(path + ".bak_dedup", path)
    print("✅ File restored to original")
    exit(1)

print("\n🎉 All steps complete!")
