import json, os, time, threading, sys, re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

_state = {}

def _b(): return sys.modules['__main__'].bot

def get_db():
    try: return json.load(open("data/pyq_master.json"))
    except: return {"practice": {}, "practice_adv": {}, "papers": {}}

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    uid = message.chat.id
    _state[uid] = {"active": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"), InlineKeyboardButton("📝 Test", callback_data="f_mode:test"))
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(uid, "🎓 <b>Exam Center</b>\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith('f_'))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]
    db = get_db()

    try:
        if data == "f_mode:pyq":
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(InlineKeyboardButton("📖 JEE Main Chapter-wise", callback_data="f_pyq_main"))
            kb.add(InlineKeyboardButton("📝 JEE Main Papers", callback_data="f_paper_main"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back"))
            _b().edit_message_text("🔍 <b>PYQ Explorer</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "f_pyq_main":
            kb = InlineKeyboardMarkup(row_width=3)
            for s in ["Physics", "Chemistry", "Maths"]:
                kb.add(InlineKeyboardButton(s, callback_data=f"f_subj:{s}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_mode:pyq"))
            _b().edit_message_text("📚 <b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, reply_markup=kb)

        elif data.startswith("f_subj:"):
            subj = data.split(":")[1]
            state["subj"] = subj
            chs = list(db.get("practice", {}).get(subj, {}).keys())
            state["chs"] = chs
            kb = InlineKeyboardMarkup(row_width=1)
            for i, ch in enumerate(chs[:40]):
                kb.add(InlineKeyboardButton(ch[:40], callback_data=f"f_ch:{i}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq_main"))
            _b().edit_message_text(f"📚 <b>{subj} Chapters:</b>", chat_id=uid, message_id=call.message.message_id, reply_markup=kb)

        elif data.startswith("f_ch:"):
            idx = int(data.split(":")[1])
            ch = state["chs"][idx]
            state["ch"] = ch
            
            qs = db.get("practice", {}).get(state["subj"], {}).get(ch, {}).get("normal", [])
            count = len(qs)
            
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton(f"📝 Start ({count} Qs)", callback_data="f_start"))
            kb.add(InlineKeyboardButton("🌊 Flow", callback_data="f_flow"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"f_subj:{state['subj']}"))
            _b().edit_message_text(f"📚 <b>{state['subj']} - {ch}</b>\n\nTotal Questions: {count}", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data in ["f_start", "f_flow"]:
            qs = db.get("practice", {}).get(state["subj"], {}).get(state["ch"], {}).get("normal", [])
            if not qs:
                _b().answer_callback_query(call.id, "❌ No questions found in DB.", show_alert=True)
                return
            
            state["qs"] = qs
            state["idx"] = 0
            state["active"] = True
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            send_question(uid)

        elif data.startswith("f_ans:"):
            ans = int(data.split(":")[1])
            # Just visual feedback for now
            _b().answer_callback_query(call.id, f"Selected Option {chr(65+ans)}")

        elif data == "f_next":
            state["idx"] += 1
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            send_question(uid)

        elif data == "f_skip":
            state["idx"] += 1
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            send_question(uid)

        elif data == "f_stop":
            state["active"] = False
            _b().edit_message_text("🛑 <b>Practice Stopped.</b>", chat_id=uid, message_id=call.message.message_id)

        elif data == "f_back":
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            cmd_exam(call.message)
            
    except Exception as e:
        _b().answer_callback_query(call.id, f"⚠️ Error: {e}", show_alert=True)
        print(f"Exam error: {e}")

def send_question(uid):
    state = _state.get(uid, {})
    qs = state.get("qs", [])
    idx = state.get("idx", 0)

    if not state.get("active"):
        return

    if idx >= len(qs):
        _b().send_message(uid, "🏁 <b>All questions complete!</b>")
        state["active"] = False
        return

    q = qs[idx]
    img_path = q.get("img")

    if not img_path or not os.path.exists(img_path):
        _b().send_message(uid, f"⚠️ Image missing for Q{idx+1}. Skipping...")
        state["idx"] += 1
        return send_question(uid)

    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    cap = f"Q{idx+1}/{len(qs)} | {state.get('ch')}"

    try:
        with open(img_path, "rb") as f:
            _b().send_photo(uid, f, caption=cap, reply_markup=kb)
    except Exception as e:
        _b().send_message(uid, f"❌ Error downloading image: {e}")
        return

    t_msg = _b().send_message(uid, "⏱ 0s")
    
    def timer():
        for i in range(1, 301):
            time.sleep(1)
            if state.get("idx") != idx or not state.get("active"): break
            try: _b().edit_message_text(f"⏱ {i}s", chat_id=uid, message_id=t_msg.message_id)
            except: pass
    
    threading.Thread(target=timer, daemon=True).start()
