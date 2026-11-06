import json, os, time, datetime, threading
import datetime as _safe_dt
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

ROUTINE_DIR = "data/routines"
os.makedirs(ROUTINE_DIR, exist_ok=True)

def _rp(uid): return f"{ROUTINE_DIR}/{uid}.json"
def _load(uid):
    p = _rp(uid)
    if not os.path.exists(p): return None
    try: return json.load(open(p))
    except: return None
def _save(uid, d):
    try: json.dump(d, open(_rp(uid), "w"), indent=2)
    except: pass
def _today(): return _safe_dt.date.today().isoformat()
def _hm(): return _safe_dt.datetime.now().strftime("%H:%M")
def _to_min(s):
    try: h, m = s.split(":"); return int(h)*60 + int(m)
    except: return None

EMO = {"wake":"🌅","sleep":"😴","breakfast":"🍳","lunch":"🍱","dinner":"🍽️","theory":"📚","pyq":"🧮","revision":"🔄","college":"🏫","study":"📖","break":"☕","hygiene":"🚿","travel":"🚌","other":"⏰"}
STUDY_TYPES = ("theory","pyq","revision","study")

def init_daily_routine(uid, blocks):
    r = {"date": _today(), "blocks": [], "summary_sent": False}
    for i, b in enumerate(blocks):
        r["blocks"].append({"idx":i,"time":b.get("time","00:00"),"end":b.get("end",""),
            "task":b.get("task","Task"),"type":b.get("type","other"),
            "subject":b.get("subject",""),"chapter":b.get("chapter",""),
            "status":"pending","notified_at":None,"nagged_at":None,
            "snooze_until":None,"msg_id":None,"done_at":None,"missed_at":None})
    _save(uid, r)
    return r

def _stats(r):
    done = [b for b in r["blocks"] if b["status"]=="done"]
    skipped = [b for b in r["blocks"] if b["status"]=="skipped"]
    missed = [b for b in r["blocks"] if b["status"]=="missed"]
    pending = [b for b in r["blocks"] if b["status"]=="pending"]
    plan_study = sum((_to_min(b.get("end","")) or 0) - (_to_min(b["time"]) or 0) for b in r["blocks"] if b.get("type") in STUDY_TYPES and b.get("end"))
    done_study = sum((_to_min(b.get("end","")) or 0) - (_to_min(b["time"]) or 0) for b in done if b.get("type") in STUDY_TYPES and b.get("end"))
    pyq_done = len([b for b in done if b.get("type")=="pyq"])
    pyq_plan = len([b for b in r["blocks"] if b.get("type")=="pyq"])
    total = len(r["blocks"])
    completion = round(100*len(done)/total,1) if total else 0
    return {"done":done,"skipped":skipped,"missed":missed,"pending":pending,
            "plan_study":plan_study,"done_study":done_study,
            "pyq_done":pyq_done,"pyq_plan":pyq_plan,"total":total,"completion":completion}

def _verdict(st):
    p = st["completion"]
    if p >= 80: return "🏆 <b>ON TRACK</b> — keep this pace, you'll hit target."
    if p >= 50: return "⚡ <b>PARTIAL</b> — push harder, you're slipping."
    if p >= 25: return "⚠️ <b>BEHIND</b> — this pace won't hit your target. Fix tonight."
    return "🚨 <b>WAY BEHIND</b> — emergency reset. Restart tomorrow with discipline."

def _kb(uid, idx, block):
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("✅ Done", callback_data=f"rt_done:{idx}"), InlineKeyboardButton("⏭ Skip", callback_data=f"rt_skip:{idx}"))
    if block.get("type")=="pyq":
        kb.row(InlineKeyboardButton("🎯 Open PYQ Menu", callback_data=f"rt_pyq:{idx}"))
    kb.row(InlineKeyboardButton("⏰ Snooze 10m", callback_data=f"rt_snooze:{idx}"))
    return kb

def _fmt_block(block):
    em = EMO.get(block.get("type",""), "⏰")
    lines = [f"{em} <b>{block['task']}</b>"]
    tm = block["time"] + (f" – {block['end']}" if block.get("end") else "")
    lines.append(f"⏰ {tm}")
    now_min = _to_min(_hm()); end_min = _to_min(block.get("end",""))
    if end_min is not None and now_min is not None:
        d = end_min - now_min
        if d > 0: lines.append(f"⏳ {d} min left" if d < 60 else f"⏳ {d//60}h {d%60}m left")
        else: lines.append("⏱ Time up")
    if block.get("subject"): lines.append(f"📖 {block['subject']}")
    if block.get("chapter"): lines.append(f"📑 {block['chapter']}")
    return "\n".join(lines)

def _fire(uid, r, block):
    try:
        m = bot.send_message(uid, _fmt_block(block), parse_mode="HTML", reply_markup=_kb(uid, block["idx"], block))
        block["msg_id"] = m.message_id; block["notified_at"] = _hm(); _save(uid, r)
    except Exception as e: print(f"[rt] fire err: {e}", flush=True)

def _nag(uid, r, block):
    try:
        bot.send_message(uid, f"🔔 <b>COACH:</b> '{block['task']}' (due {block['time']}) still not marked. What happened?", reply_markup=_kb(uid, block["idx"], block))
        block["nagged_at"] = _hm(); _save(uid, r)
    except: pass

def _next(uid, r, cur):
    nxt = next((b for b in r["blocks"] if b["idx"] > cur and b["status"]=="pending"), None)
    try:
        if nxt: bot.send_message(uid, f"➡️ Next up: <b>{nxt['task']}</b> at {nxt['time']}", parse_mode="HTML")
        else: bot.send_message(uid, "🎉 All blocks handled for today. Use /today for full report.")
    except: pass

def _daily_summary(uid, r):
    st = _stats(r)
    lines = [f"📊 <b>DAILY REPORT — {r['date']}</b>", ""]
    lines.append(f"✅ Done: <b>{len(st['done'])}</b> / {st['total']}")
    if st["skipped"]: lines.append(f"⏭ Skipped: {len(st['skipped'])}")
    if st["missed"]: lines.append(f"❌ Missed (no confirm): {len(st['missed'])}")
    if st["pending"]: lines.append(f"⏳ Still pending: {len(st['pending'])}")
    if st["plan_study"]:
        ph, pm = st["plan_study"]//60, st["plan_study"]%60
        dh, dm = st["done_study"]//60, st["done_study"]%60
        lines.append(f"📚 Study: <b>{dh}h {dm}m</b> done / <b>{ph}h {pm}m</b> planned")
    if st["pyq_plan"]:
        lines.append(f"🧮 PYQs: <b>{st['pyq_done']}</b> done / <b>{st['pyq_plan']}</b> planned")
    if st["done"]:
        lines.append("\n<b>✅ Completed:</b>")
        for b in st["done"][:10]: lines.append(f"• {b['task']} (at {b.get('done_at','?')})")
    if st["missed"]:
        lines.append("\n<b>❌ Not submitted / Missed:</b>")
        for b in st["missed"][:10]: lines.append(f"• {b['task']} — was due {b['time']}")
    if st["pending"]:
        lines.append("\n<b>⏳ Not done yet:</b>")
        for b in st["pending"][:10]: lines.append(f"• {b['task']} — {b['time']}")
    lines.append("")
    lines.append(_verdict(st))
    try: bot.send_message(uid, "\n".join(lines), parse_mode="HTML")
    except: pass

def routine_worker():
    while True:
        try:
            time.sleep(30)
            if not os.path.isdir(ROUTINE_DIR): continue
            for f in os.listdir(ROUTINE_DIR):
                if not f.endswith(".json"): continue
                try: uid = int(f.replace(".json",""))
                except: continue
                try: r = json.load(open(f"{ROUTINE_DIR}/{f}"))
                except: continue
                if r.get("date") != _today():
                    try: _daily_summary(uid, r)
                    except: pass
                    for b in r.get("blocks", []):
                        b.update({"status":"pending","notified_at":None,"nagged_at":None,"snooze_until":None,"msg_id":None,"done_at":None,"missed_at":None})
                    r["date"] = _today(); r["summary_sent"] = False; _save(uid, r)
                now = _hm(); now_min = _to_min(now)
                if now_min is None: continue
                for b in r.get("blocks", []):
                    if b.get("status") != "pending": continue
                    bt = _to_min(b["time"])
                    if bt is None: continue
                    if b.get("snooze_until"):
                        if now >= b["snooze_until"]:
                            b["snooze_until"]=None; b["notified_at"]=None; b["nagged_at"]=None; _save(uid, r)
                        else: continue
                    if now_min > bt + 30 and not b.get("notified_at") and not b.get("nagged_at"):
                        b["status"]="missed"; b["missed_at"]=now; _save(uid, r)
                        try: bot.send_message(uid, f"❌ <b>MISSED:</b> '{b['task']}' was due at {b['time']}. If you did it, mark done:", reply_markup=_kb(uid, b["idx"], b))
                        except: pass
                        continue
                    if now_min >= bt and not b.get("notified_at"): _fire(uid, r, b)
                    elif b.get("notified_at") and not b.get("nagged_at"):
                        nf = _to_min(b["notified_at"])
                        if nf is not None and now_min - nf >= 15: _nag(uid, r, b)
                if now == "22:00" and not r.get("summary_sent"):
                    _daily_summary(uid, r); r["summary_sent"]=True; _save(uid, r)
        except Exception as e: print(f"[rt] worker err: {e}", flush=True)

try:
    threading.Thread(target=routine_worker, daemon=True).start()
    print("✅ c01zz_routine_tracker: worker started", flush=True)
except Exception as e: print(f"[rt] thread fail: {e}", flush=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rt_"))
def handle_routine_cb(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    uid = call.message.chat.id
    try: parts = call.data.split(":"); action = parts[0]; idx = int(parts[1])
    except: return
    r = _load(uid)
    if not r: return
    block = next((b for b in r["blocks"] if b["idx"] == idx), None)
    if not block: return
    if action == "rt_done":
        block["status"]="done"; block["done_at"]=_hm(); _save(uid, r)
        try: bot.edit_message_text(f"✅ <b>{block['task']}</b> — done at {block['done_at']}", chat_id=uid, message_id=call.message.message_id)
        except: pass
        _next(uid, r, idx)
    elif action == "rt_skip":
        block["status"]="skipped"; _save(uid, r)
        try: bot.edit_message_text(f"⏭ <b>{block['task']}</b> — skipped", chat_id=uid, message_id=call.message.message_id)
        except: pass
        _next(uid, r, idx)
    elif action == "rt_snooze":
        block["snooze_until"]=(_safe_dt.datetime.now()+_safe_dt.timedelta(minutes=10)).strftime("%H:%M")
        block["notified_at"]=None; block["nagged_at"]=None; block["status"]="pending"; _save(uid, r)
        try: bot.edit_message_text(f"⏰ <b>{block['task']}</b> — snoozed 10 min", chat_id=uid, message_id=call.message.message_id)
        except: pass
    elif action == "rt_pyq":
        subj = block.get("subject","") or "any subject"; ch = block.get("chapter","")
        kb = InlineKeyboardMarkup(); kb.row(InlineKeyboardButton("📖 Open PYQ Menu", callback_data="f_mode:pyq"))
        msg = f"🎯 <b>PYQ Time</b>\n📖 {subj}" + (f" → {ch}" if ch else "") + "\n\nTap below → PYQs → pick chapter → start solving."
        try: bot.send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
        except: pass

@bot.message_handler(commands=['today','report'])
def cmd_today(message):
    uid = message.chat.id; r = _load(uid)
    if not r: bot.send_message(uid, "No routine yet. Use /plan or /testroutine."); return
    _daily_summary(uid, r)

@bot.message_handler(commands=['pending'])
def cmd_pending(message):
    uid = message.chat.id; r = _load(uid)
    if not r: bot.send_message(uid, "No routine."); return
    st = _stats(r)
    if not st["pending"]: bot.send_message(uid, "🎉 Nothing pending!"); return
    lines = ["⏳ <b>Pending today:</b>"]
    for b in st["pending"]:
        lines.append(f"• {b['task']} — {b['time']}" + (f" ({b['subject']})" if b.get("subject") else ""))
    bot.send_message(uid, "\n".join(lines), parse_mode="HTML")

@bot.message_handler(commands=['testroutine'])
def cmd_testroutine(message):
    uid = message.chat.id; now = _safe_dt.datetime.now()
    specs = [("Wake up & hydrate","wake",""),("Breakfast","breakfast",""),("Math theory","theory","Maths"),("Math PYQs","pyq","Maths")]
    blocks = []
    for i, (task, typ, subj) in enumerate(specs):
        t = (now + _safe_dt.timedelta(minutes=(i+1)*2)).strftime("%H:%M")
        e = (now + _safe_dt.timedelta(minutes=(i+1)*2 + 1)).strftime("%H:%M")
        blocks.append({"time":t,"end":e,"task":task,"type":typ,"subject":subj,"chapter":""})
    init_daily_routine(uid, blocks)
    bot.send_message(uid, f"✅ Test routine: {len(blocks)} blocks, 2 min apart. First fires in ~2 min. Use /today to see live.")
