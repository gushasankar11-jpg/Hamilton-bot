import json, os, random, string
import datetime as _dt

def trigger_trial(uid):
    try:
        os.makedirs("data", exist_ok=True)
        trials_file = "data/trial_keys.json"
        trials = {}
        if os.path.exists(trials_file):
            try: trials = json.load(open(trials_file))
            except: pass

        # Check if user already generated a key
        existing_key = None
        for k, v in trials.items():
            if v.get("generated_for") == uid:
                existing_key = k
                break

        if not existing_key:
            existing_key = "TRIAL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            expires = (_dt.datetime.now() + _dt.timedelta(days=5)).isoformat()
            trials[existing_key] = {"expires_at": expires, "used_by": None, "generated_for": uid, "is_used": False}
            json.dump(trials, open(trials_file, "w"), indent=2)

        # Save key to profile, but DO NOT set secured=True yet!
        profile_file = f"profiles/{uid}.json"
        p = {}
        if os.path.exists(profile_file):
            try: p = json.load(open(profile_file))
            except: pass
        p["pending_key"] = existing_key
        p["secured"] = False
        json.dump(p, open(profile_file, "w"), indent=2)

        msg = f"""🎉 <b>Hamilton Study AI — Free Trial Access!</b>

Welcome to Hamilton Study AI!

You have been selected to experience our limited-period FREE TRIAL.

🔑 <b>Your Personal Activation Key</b>
Your unique activation key has been generated exclusively for you:
<code>{existing_key}</code>

📋 <b>How to Activate Your Trial</b>
Tap the key above to copy it, then paste it here and send it to unlock your access.

⏳ <b>Trial Information</b>
Each activation key is unique.
The key is intended for one registered device only.
The activation key is valid for a maximum of 5 days from generation.

⚠️ Do not share your activation key with others.

Enjoy your free trial!
Hamilton Study AI — Your Preparation. Your Progress."""
        bot.send_message(uid, msg, parse_mode="HTML")
    except Exception as e:
        print(f"Trial error: {e}")


def get_trial_timer(uid):
    import json, os
    import datetime as _dt
    p_file = f"profiles/{uid}.json"
    if os.path.exists(p_file):
        try: p = json.load(open(p_file))
        except: return ""
        if p.get("is_trial") and p.get("trial_expiry"):
            exp = _dt.datetime.fromisoformat(p["trial_expiry"])
            now = _dt.datetime.now()
            if now < exp:
                diff = exp - now
                days = diff.days
                hours, rem = divmod(diff.seconds, 3600)
                mins, secs = divmod(rem, 60)
                return f"\n\n⏳ <b>Free Trial Access</b>\nTime Remaining: <b>{days}d {hours}h {mins}m {secs}s</b>\n<i>Contact Admin for full access: <a href='https://wa.me/918074231426'>WhatsApp</a></i>"
    return ""


@bot.message_handler(commands=['status'])
def cmd_status(message):
    uid = message.chat.id
    timer = get_trial_timer(uid)
    if timer:
        bot.send_message(uid, f"📊 <b>Account Status</b>{timer}", parse_mode="HTML")
    else:
        bot.send_message(uid, "✅ You have Full Access (No active trial timer).")

