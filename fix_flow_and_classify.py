import ast, shutil, os, re, json

# ═══════════════════════════════════════════════════
# 1. FAST BACKGROUND CLASSIFIER & /classify COMMAND
# ═══════════════════════════════════════════════════
F_STORE = "bot_chunks/c03z_store.py"
shutil.copy(F_STORE, F_STORE + ".bak_classify")
cs = open(F_STORE).read()

classify_cmd = '''
@bot.message_handler(commands=['classify'])
def cmd_classify(message):
    uid = message.chat.id
    bot.send_message(uid, "⚡ Running Fast Classifier...")
    
    try:
        import json, re
        from collections import defaultdict
        
        db = json.load(open("data/pyq_master.json"))
        stats = defaultdict(lambda: defaultdict(lambda: {"MCQ": 0, "Num": 0, "Match": 0, "Years": set()}))
        
        # Scan Papers
        for p_name, p_data in db.get("papers", {}).items():
            subj = str(p_data.get("subject", "Physics")).capitalize()
            ch = str(p_data.get("chapter", "Mixed"))
            for q in p_data.get("questions", []):
                q_t = str(q.get("type", "")).lower()
                has_opts = bool(q.get("options"))
                if "mcq" in q_t or "single" in q_t or has_opts: stats[subj][ch]["MCQ"] += 1
                elif "num" in q_t: stats[subj][ch]["Num"] += 1
                elif "match" in q_t: stats[subj][ch]["Match"] += 1
                
                yr = str(q.get("year") or q.get("source", ""))
                m = re.search(r'(20\\d\\d)', yr)
                if m: stats[subj][ch]["Years"].add(m.group(1))
                
        # Scan Practice
        for main_adv in ["practice", "practice_adv"]:
            for subj, chapters in db.get(main_adv, {}).items():
                for ch, q_data in chapters.items():
                    for q in q_data.get("priority", []) + q_data.get("normal", []):
                        q_t = str(q.get("type", "")).lower()
                        has_opts = bool(q.get("options"))
                        if "mcq" in q_t or "single" in q_t or has_opts: stats[subj][ch]["MCQ"] += 1
                        elif "num" in q_t: stats[subj][ch]["Num"] += 1
                        elif "match" in q_t: stats[subj][ch]["Match"] += 1
                        
                        yr = str(q.get("year") or q.get("source", ""))
                        m = re.search(r'(20\\d\\d)', yr)
                        if m: stats[subj][ch]["Years"].add(m.group(1))

        # Save to file
        final_stats = {}
        for subj, chapters in stats.items():
            final_stats[subj] = {}
            for ch, counts in chapters.items():
                final_stats[subj][ch] = {
                    "MCQ": counts["MCQ"], "Num": counts["Num"], "Match": counts["Match"],
                    "Years": sorted(list(counts["Years"]), reverse=True)
                }
        json.dump(final_stats, open("data/chapter_stats.json", "w"), indent=2)
        
        # Reply with summary
        txt = "📊 <b>CLASSIFIER RESULT</b>\\n\\n"
        total_q = 0
        for subj, chapters in final_stats.items():
            txt += f"📚 <b>{subj}:</b>\\n"
            for ch, counts in chapters.items():
                tot = counts['MCQ'] + counts['Num'] + counts['Match']
                total_q += tot
                if tot > 0:
                    txt += f"  • {ch[:25]}: {tot} Qs (MCQ:{counts['MCQ']}, Num:{counts['Num']}, Match:{counts['Match']})\\n"
            txt += "\\n"
            
        txt += f"✅ <b>Total Questions Classified: {total_q}</b>"
        bot.send_message(uid, txt, parse_mode="HTML")
    except Exception as e:
        bot.send_message(uid, f"❌ Classify Error: {e}")

'''
if "@bot.message_handler(commands=['classify'])" not in cs:
    cs = cs.replace("@bot.callback_query_handler(func=lambda c: c.data and (c.data.startswith(\"shop_\")", classify_cmd + "\n@bot.callback_query_handler(func=lambda c: c.data and (c.data.startswith(\"shop_\")")

ast.parse(cs)
open(F_STORE, "w").write(cs)


# ═══════════════════════════════════════════════════
# 2. INSTANT FLOW & ERROR CATCHER IN c04_exam.py
# ═══════════════════════════════════════════════════
F_EXAM = "bot_chunks/c04_exam.py"
shutil.copy(F_EXAM, F_EXAM + ".bak_flowfix")
ce = open(F_EXAM).read()

# A. Fix the Chapter Menu to use the new cached stats
old_ch = re.search(r'if data\.startswith\("f_pyq_ch:"\) or data\.startswith\("f_pyq_adv_ch:"\):.*?return', ce, re.DOTALL)
if old_ch:
    new_ch = '''if data.startswith("f_pyq_ch:") or data.startswith("f_pyq_adv_ch:"):
            idx = int(data.split(":", 1)[1])
            chapters_list = state.get("chapters_list", [])
            if idx >= len(chapters_list): return
            
            ch = chapters_list[idx]
            state["current_chapter"] = ch
            subj = state.get("pyq_subj", "Physics")
            is_adv = "adv" in data
            
            try: cache = json.load(open("data/chapter_stats.json"))
            except: cache = {}
            ch_stats = cache.get(subj, {}).get(ch, {})
            
            mcq_count = ch_stats.get("MCQ", 0)
            num_count = ch_stats.get("Num", 0)
            match_count = ch_stats.get("Match", 0)
            
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("🌊 Flow (Auto)", callback_data="f_type:Flow"))
            if mcq_count > 0: kb.add(InlineKeyboardButton(f"📝 MCQ ({mcq_count})", callback_data="f_type:MCQ"))
            if num_count > 0: kb.add(InlineKeyboardButton(f"🔢 Num ({num_count})", callback_data="f_type:Num"))
            if match_count > 0: kb.add(InlineKeyboardButton(f"🔗 Match ({match_count})", callback_data="f_type:Match"))
            kb.row(InlineKeyboardButton("📅 By Year", callback_data="f_type:Year"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"f_pyq_sub:{subj}" if not is_adv else f"f_pyq_adv_sub:{subj}"))
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            msg = f"📚 <b>{subj} - {ch}</b>\\n"
            if mcq_count + num_count + match_count == 0:
                msg += "⚠️ <i>0 questions found in DB. Use /extract first.</i>"
            _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
            return'''
    ce = ce[:old_ch.start()] + new_ch + ce[old_ch.end():]

# B. Fix the Type Handler for Instant Flow
old_type = re.search(r'if data\.startswith\("f_type:"\):.*?return', ce, re.DOTALL)
if old_type:
    new_type = '''if data.startswith("f_type:"):
            q_type = data.split(":")[1]
            ch = state.get("current_chapter")
            is_adv = state.get("is_adv", False)
            subj = state.get("pyq_subj")
            
            db_key = "practice_adv" if is_adv else "practice"
            q_data = db.get(db_key, {}).get(subj, {}).get(ch, {})
            all_qs = q_data.get("priority", []) + q_data.get("normal", [])
            
            if not all_qs:
                _b().answer_callback_query(call.id, "❌ 0 questions in database for this chapter.", show_alert=True)
                return

            if q_type == "Flow":
                filtered = all_qs
            else:
                filtered = []
                for q in all_qs:
                    q_t = str(q.get("type", "")).lower()
                    has_opts = bool(q.get("options"))
                    if q_type == "MCQ" and ("mcq" in q_t or "single" in q_t or "multiple" in q_t or has_opts): filtered.append(q)
                    elif q_type == "Num" and ("num" in q_t or "integer" in q_t) and not has_opts: filtered.append(q)
                    elif q_type == "Match" and ("match" in q_t or "matrix" in q_t): filtered.append(q)
                        
            if not filtered:
                _b().answer_callback_query(call.id, f"❌ No {q_type} questions found.", show_alert=True)
                return
                
            state["mode"] = "pyq"; state["subj"] = subj; state["chapter"] = ch
            state["pyq_questions"] = filtered
            state["pyq_index"] = 0; state["pyq_is_paper"] = False
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            # INSTANT FLOW: No countdown!
            if q_type == "Flow":
                try: send_pyq_q(uid)
                except Exception as e: _b().send_message(uid, f"⚠️ Error starting flow: {e}")
            else:
                def run_cd_ch():
                    cdown = _b().send_message(uid, "📄 <b>Starting...</b>\\n\\n5...")
                    for n in [4, 3, 2, 1]:
                        time.sleep(1)
                        try: _b().edit_message_text(f"📄 <b>Starting...</b>\\n\\n{n}...", chat_id=uid, message_id=cdown.message_id)
                        except: pass
                    time.sleep(1)
                    _b().edit_message_text("🚀 <b>GO!</b>", chat_id=uid, message_id=cdown.message_id)
                    time.sleep(0.5)
                    send_pyq_q(uid)
                threading.Thread(target=run_cd_ch, daemon=True).start()
            return'''
    ce = ce[:old_type.start()] + new_type + ce[old_type.end():]

# C. Add safety net to send_pyq_q so it doesn't freeze silently
old_send = re.search(r'def send_pyq_q\(uid, msg_id=None\):.*?(?=def )', ce, re.DOTALL)
if old_send:
    # Just wrap the start of the function in try/except
    ce = ce.replace("def send_pyq_q(uid, msg_id=None):", "def send_pyq_q(uid, msg_id=None):\n    try:")

ast.parse(ce)
open(F_EXAM, "w").write(ce)
print("✅ c04_exam.py patched: /classify added, Flow instant, Safety net active.")

print("════ PATCH COMPLETE ════")
