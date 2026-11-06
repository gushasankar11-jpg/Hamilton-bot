# Loads FIRST (c00zz < c01) — answers every callback instantly
try:
    @bot.middleware_handler(update_types=['callback_query'])
    def _instant_answer(bot_instance, call):
        try: bot_instance.answer_callback_query(call.id)
        except: pass
    print("✅ c00zz: instant callback middleware loaded", flush=True)
except AttributeError:
    @bot.callback_query_handler(func=lambda c: True)
    def _instant_answer_fallback(call):
        try: bot.answer_callback_query(call.id)
        except: pass
    print("⚠️ c00zz: fallback handler (older telebot)", flush=True)

import glob as _gl, os as _os, random as _rnd

@bot.message_handler(commands=['sample'])
def cmd_sample_crops(message):
    uid = message.chat.id
    files = []
    for f in _gl.glob('pyq_images/extracted_books_v3/**/*.png', recursive=True):
        try:
            if _os.path.getsize(f) > 40000:
                files.append(f)
        except: pass
    if not files:
        bot.send_message(uid, "No crops ≥40KB yet.")
        return
    bot.send_message(uid, f"📤 Sending 3 of {len(files)} sample crops...")
    for f in _rnd.sample(files, min(3, len(files))):
        try:
            with open(f, 'rb') as fh:
                bot.send_photo(uid, fh, caption=f.split('/')[-1])
        except Exception as e:
            bot.send_message(uid, f"⚠️ {f}: {e}")
