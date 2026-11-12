# ==========================================================
# c02.py — Start, Onboarding, Mode, Status
# ==========================================================
def _run_onboarding(uid):
    p = load_profile(uid)
    step = p.get("onboarding_step")
    
    if step == "name":
        msg = bot.send_message(uid, 
            "📝 *What is your name?*\n\n"
            "⚠️ _Please enter your genuine full real name._\n"
            "_Short forms and fake names are not accepted._", 
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_name)
    elif step == "institute":
        msg = bot.send_message(uid, "🏫 *Which institute / school / college?*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_institute)
    elif step == "phone":
        msg = bot.send_message(uid, "📱 *Enter your 10-digit mobile number:*\n\n_Example: 9876543210_", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_phone)
    elif step == "level":
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("Junior", "Senior", "Dropper")
        msg = bot.send_message(uid, "🎓 *Junior, Senior, or Dropper?*", reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_level)
    else:
        bot.send_message(uid, "✅ Setup complete. Type /mode to begin.")

def _onboarding_name(message):
    uid = message.chat.id
    n = (message.text or "").strip()[:40]
    
    if not n or len(n) < 3:
        msg = bot.reply_to(message, "❌ Name must be at least 3 characters long. Please enter your real full name:")
        bot.register_next_step_handler(msg, _onboarding_name)
        return

    p = load_profile(uid)
    p.setdefault("name_strikes", 0)

    if p["name_strikes"] >= 3:
        bot.reply_to(message, "🔒 Locked out. Contact admin on WhatsApp to verify your name.")
        return

    # Hardcoded blocklist for obvious fake names
    fake_names = ["raichu", "pikachu", "charizard", "naruto", "goku", "luffy", "batman", "superman", "ironman", "spiderman"]
    if n.lower() in fake_names:
        p["name_strikes"] += 1
        save_profile(uid, p)
        left = 3 - p["name_strikes"]
        if left > 0:
            msg = bot.reply_to(message, f"❌ This name seems fake or fictional.\n⚠️ You have *{left} attempts left*.\n\nEnter your real full name:", parse_mode="Markdown")
            bot.register_next_step_handler(msg, _onboarding_name)
        else:
            bot.reply_to(message, "🔒 Locked out. Contact admin on WhatsApp to verify your name.")
        return

    try:
        import ai_client, json, re
        prompt = f'Analyze the name: "{n}". Is this a real human name, or is it a fictional character (like Pokemon), a keyboard smash, or a fake name? Real names like "Rahul" or "Ram" are valid. Fictional names like "Raichu" or "Pikachu" are fake. Return ONLY JSON: {{"is_fictional": true/false, "fake_probability": 0-100}}'
        resp = ai_client.ask_hamilton("JEE_MAIN", prompt) 
        m = re.search(r'\{.*\}', str(resp), re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            prob = data.get("fake_probability", 0)
            if prob > 20:
                p["name_strikes"] += 1
                save_profile(uid, p)
                left = 3 - p["name_strikes"]
                if left > 0:
                    msg = bot.reply_to(message, f"❌ This name seems fake or fictional. (Fake Score: {prob}%)\n⚠️ You have *{left} attempts left*.\n\nEnter your real full name:", parse_mode="Markdown")
                    bot.register_next_step_handler(msg, _onboarding_name)
                else:
                    bot.reply_to(message, "🔒 Locked out. Contact admin on WhatsApp to verify your name.")
                return
    except Exception as e:
        print(f"AI Name Check Error: {e}")

    bot.reply_to(message, f"✅ Name accepted: *{n}*", parse_mode="Markdown")
    p["name"] = n
    p["onboarding_step"] = "institute"
    save_profile(uid, p)
    _run_onboarding(uid)

def _onboarding_institute(message):
    uid = message.chat.id
    i = (message.text or "").strip()[:60]
    
    if not i or len(i) < 3:
        msg = bot.reply_to(message, "❌ Institute name must be at least 3 characters long. Please enter your real institute:")
        bot.register_next_step_handler(msg, _onboarding_institute)
        return

    p = load_profile(uid)
    p.setdefault("institute_strikes", 0)

    if p["institute_strikes"] >= 3:
        bot.reply_to(message, "🔒 Locked out. Contact admin on WhatsApp to verify your institute.")
        return

    try:
        import ai_client, json, re
        prompt = f'Check if the following educational institute/school/college exists in the real world (like a real geographical location on Google Maps). Name: "{i}". Return ONLY JSON: {{"is_fictional": true/false, "fake_probability": 0-100}}'
        resp = ai_client.ask_hamilton("JEE_MAIN", prompt) 
        m = re.search(r'\{.*\}', str(resp), re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            prob = data.get("fake_probability", 0)
            if prob > 20:
                p["institute_strikes"] += 1
                save_profile(uid, p)
                left = 3 - p["institute_strikes"]
                if left > 0:
                    msg = bot.reply_to(message, f"❌ This institute seems fake or fictional. (Fake Score: {prob}%)\n⚠️ You have *{left} attempts left*.\n\nEnter your real institute name:", parse_mode="Markdown")
                    bot.register_next_step_handler(msg, _onboarding_institute)
                else:
                    bot.reply_to(message, "🔒 Locked out. Contact admin on WhatsApp to verify your institute.")
                return
    except Exception as e:
        print(f"AI Institute Check Error: {e}")

    bot.reply_to(message, f"✅ Institute accepted: *{i}*", parse_mode="Markdown")
    p["institute"] = i
    p["onboarding_step"] = "phone"
    save_profile(uid, p)
    _run_onboarding(uid)

def _onboarding_phone(message):
    import re
    uid = message.chat.id
    raw = (message.text or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in "6789":
        bot.reply_to(message, "❌ Please enter a valid 10-digit Indian mobile number.\nExample: `9876543210`", parse_mode="Markdown")
        return
    p = load_profile(uid)
    p["phone"] = digits
    p["onboarding_step"] = "level"
    save_profile(uid, p)
    _run_onboarding(uid)

def _onboarding_level(message):
    uid = message.chat.id
    t = (message.text or "").strip().lower()
    if t not in ("junior", "senior", "dropper"):
        bot.reply_to(message, "Tap one of: Junior / Senior / Dropper")
        return
    p = load_profile(uid)
    p["level"] = t.capitalize()
    p["onboarding_step"] = "done"
    if not p.get("hku_id"):
        p["hku_id"] = allocate_user_id(uid)
    save_profile(uid, p)
    
    try:
        import admin_auth as _aa
        _aa.mark_new_user(uid, p.get("name", "?"), p.get("phone", "?"))
    except Exception: pass
    
    bot.reply_to(message,
        f"✅ *Profile saved*\n\n👤 {p['name']}\n🏫 {p['institute']}\n🎓 {p['level']}\n📱 {p['phone']}\n🆔 {p['hku_id']}\n\nType /mode to begin.",
        reply_markup=telebot.types.ReplyKeyboardRemove(),
        parse_mode="Markdown")

# ==========================================================
# /start, /mode, /status, etc...
# ==========================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.chat.id
    p = get_or_create_profile(uid)
    
    # If not yet activated (no key provided)
    if not p.get("secured"):
        save_profile(uid, p)
        greeting = (
            "🙏 *Namaskaram, Aspirant!*\n\n"
            "Welcome to the *Hamilton Study AI* platform. You are here to dedicate your upcoming days to participate in the race of competitive exams and emerge victorious.\n\n"
            "You stand in the final stretch of your Intermediate journey — balancing board studies with deep, focused preparation. "
            "I am your personal exam mentor, built by *Hemanth and Krishna Publications*, to walk beside you every single day until your rank is sealed.\n\n"
            "Your goal is not just to pass. Your goal is to *rise above the noise* and claim the rank you were born for.\n\n"
            "🔒 *Send your activation key to begin your journey.*"
        )
        bot.reply_to(message, greeting, parse_mode="Markdown")
        
        # Trigger the Free Trial Message instantly
        trigger_trial(uid)
        return

    # If activated but still in the middle of onboarding
    if p.get("onboarding_step") and p["onboarding_step"] != "done":
        _run_onboarding(uid)
        return
        
    # If fully registered
    bot.reply_to(message, 
        f"🙏 *Welcome back, {p.get('name', 'Aspirant')}!*\n\n"
        "Type /mode to continue your preparation.\n"
        "Type /clear_data if you want to wipe your profile and start over.", 
        parse_mode="Markdown")

# OLD_MODE_DISABLED: @bot.message_handler(commands=['mode'])
# OLD_MODE_DISABLED: def cmd_mode(message):
# OLD_MODE_DISABLED:     uid = message.chat.id
# OLD_MODE_DISABLED:     try:
# OLD_MODE_DISABLED:         ready, reason = _profile_ready(uid)
# OLD_MODE_DISABLED:         if not ready:
# OLD_MODE_DISABLED:             _send_setup_prompt(uid, reason)
# OLD_MODE_DISABLED:             return
# OLD_MODE_DISABLED:     except Exception as _e:
# OLD_MODE_DISABLED:         print(f"[mode] profile err: {_e}")
# OLD_MODE_DISABLED:     # Step 1: Ask which exam FIRST
# OLD_MODE_DISABLED:     p = load_profile(uid)
# OLD_MODE_DISABLED:     exams = p.get("exams") or []
# OLD_MODE_DISABLED:     if not exams:
# OLD_MODE_DISABLED:         bot.send_message(uid, "\u26a0\ufe0f No exams set. Use /start to configure.")
# OLD_MODE_DISABLED:         return
# OLD_MODE_DISABLED:     if len(exams) == 1:
# OLD_MODE_DISABLED:         # Only one exam — set it and go straight to mode
# OLD_MODE_DISABLED:         p["_exam_chosen"] = exams[0]
# OLD_MODE_DISABLED:         save_profile(uid, p)
# OLD_MODE_DISABLED:         _ask_mode_after_exam(uid)
# OLD_MODE_DISABLED:         return
# OLD_MODE_DISABLED:     # Multiple exams — ask which
# OLD_MODE_DISABLED:     from telebot.types import ReplyKeyboardMarkup
# OLD_MODE_DISABLED:     kb = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
# OLD_MODE_DISABLED:     for e in exams:
# OLD_MODE_DISABLED:         try:
# OLD_MODE_DISABLED:             kb.add(EXAM_NAMES[e])
# OLD_MODE_DISABLED:         except Exception:
# OLD_MODE_DISABLED:             kb.add(e)
# OLD_MODE_DISABLED:     msg = bot.send_message(
# OLD_MODE_DISABLED:         uid,
# OLD_MODE_DISABLED:         "\U0001f4da *Step 1/2 \u2014 Which exam?*\n\n"
# OLD_MODE_DISABLED:         "_You can change priority anytime with /select_",
# OLD_MODE_DISABLED:         reply_markup=kb, parse_mode="Markdown"
# OLD_MODE_DISABLED:     )
# OLD_MODE_DISABLED:     bot.register_next_step_handler(msg, _mode_choose_exam)
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: def _mode_choose_exam(message):
# OLD_MODE_DISABLED:     """User picked an exam. Save it, then ask mode."""
# OLD_MODE_DISABLED:     uid = message.chat.id
# OLD_MODE_DISABLED:     t = (message.text or "").strip()
# OLD_MODE_DISABLED:     p = load_profile(uid)
# OLD_MODE_DISABLED:     exams = p.get("exams") or []
# OLD_MODE_DISABLED:     # Match user's choice to exam key
# OLD_MODE_DISABLED:     chosen = None
# OLD_MODE_DISABLED:     for e in exams:
# OLD_MODE_DISABLED:         try:
# OLD_MODE_DISABLED:             if EXAM_NAMES[e].lower() == t.lower():
# OLD_MODE_DISABLED:                 chosen = e
# OLD_MODE_DISABLED:                 break
# OLD_MODE_DISABLED:         except Exception:
# OLD_MODE_DISABLED:             if e.lower() == t.lower():
# OLD_MODE_DISABLED:                 chosen = e
# OLD_MODE_DISABLED:                 break
# OLD_MODE_DISABLED:     if not chosen:
# OLD_MODE_DISABLED:         bot.reply_to(message, "Tap one of the exams shown above.")
# OLD_MODE_DISABLED:         return
# OLD_MODE_DISABLED:     p["_exam_chosen"] = chosen
# OLD_MODE_DISABLED:     save_profile(uid, p)
# OLD_MODE_DISABLED:     _ask_mode_after_exam(uid)
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: def _ask_mode_after_exam(uid):
# OLD_MODE_DISABLED:     """After exam chosen, ask Practice/Test/Conceptual."""
# OLD_MODE_DISABLED:     from telebot.types import ReplyKeyboardMarkup
# OLD_MODE_DISABLED:     p = load_profile(uid)
# OLD_MODE_DISABLED:     exam_key = p.get("_exam_chosen", "")
# OLD_MODE_DISABLED:     exam_name = exam_key
# OLD_MODE_DISABLED:     try:
# OLD_MODE_DISABLED:         exam_name = EXAM_NAMES.get(exam_key, exam_key)
# OLD_MODE_DISABLED:     except Exception:
# OLD_MODE_DISABLED:         pass
# OLD_MODE_DISABLED:     kb = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
# OLD_MODE_DISABLED:     kb.add("Practice", "Test", "Conceptual")
# OLD_MODE_DISABLED:     msg = bot.send_message(
# OLD_MODE_DISABLED:         uid,
# OLD_MODE_DISABLED:         f"\U0001f4da *Step 2/2 \u2014 Mode for {exam_name}*\n\n"
# OLD_MODE_DISABLED:         "\u2022 *Practice* \u2014 casual learning\n"
# OLD_MODE_DISABLED:         "\u2022 *Test* \u2014 full exam simulation\n"
# OLD_MODE_DISABLED:         "\u2022 *Conceptual* \u2014 theory & exceptions focus",
# OLD_MODE_DISABLED:         reply_markup=kb, parse_mode="Markdown"
# OLD_MODE_DISABLED:     )
# OLD_MODE_DISABLED:     # _exam_mode expects Practice/Test/Conceptual text
# OLD_MODE_DISABLED:     handler = globals().get("_exam_mode")
# OLD_MODE_DISABLED:     if handler:
# OLD_MODE_DISABLED:         bot.register_next_step_handler(msg, handler)
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
@bot.message_handler(commands=['status'])
def cmd_status(message):
    pass

@bot.message_handler(commands=['clear_data'])
def cmd_clear_data(message):
    uid = message.chat.id
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("❌ Yes, Delete Everything", callback_data="admin_confirm_wipe"),
        InlineKeyboardButton("Cancel", callback_data="admin_cancel_wipe")
    )
    bot.reply_to(message, 
        "⚠️ *WARNING* ⚠️\n\n"
        "This will permanently delete your profile, name, phone, health, and all progress.\n"
        "You will have to register from scratch.\n\n"
        "Are you sure?", 
        reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "admin_confirm_wipe")
def _cb_confirm_wipe(call):
    uid = call.message.chat.id
    # Delete Profile
    prof_path = f"profiles/{uid}.json"
    if os.path.exists(prof_path):
        os.remove(prof_path)
    # Delete Bookmarks
    bm_path = f"bookmarks/{uid}.json"
    if os.path.exists(bm_path):
        os.remove(bm_path)
        
    try:
        bot.edit_message_text("✅ *Data completely wiped.*\n\nSend /start to register again.", 
                              chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "admin_cancel_wipe")
def _cb_cancel_wipe(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
