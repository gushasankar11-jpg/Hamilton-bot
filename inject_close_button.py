import ast

# --- PATCH 1: c09.py (Add button when chat starts) ---
path_c09 = "bot_chunks/c09.py"
content_c09 = open(path_c09).read()

old_c09 = '''                    try:
                        safe_send(uid,
                            f"🔗 *Chat opened with user {_target}*\\n"
                            f"Type `/end_chat {_target}` to close when done.",
                            parse_mode="Markdown")
                    except Exception:
                        pass'''

new_c09 = '''                    try:
                        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                        close_kb = InlineKeyboardMarkup()
                        close_kb.add(InlineKeyboardButton("❌ Close Chat", callback_data=f"admin_close_chat:{_target}"))
                        bot.send_message(uid,
                            f"🔗 *Chat opened with user {_target}*\\n"
                            f"Messages are now forwarded. Click below to close.",
                            parse_mode="Markdown", reply_markup=close_kb)
                    except Exception as e:
                        print(f"[chat_open_kb_err] {e}")'''

if old_c09 in content_c09:
    content_c09 = content_c09.replace(old_c09, new_c09)
    try:
        ast.parse(content_c09)
        open(path_c09, "w").write(content_c09)
        print("✅ Patched c09.py: Added Close Chat button on chat start.")
    except Exception as e:
        print(f"❌ c09.py patch failed: {e}")
else:
    print("⚠️ c09.py pattern not found.")

# --- PATCH 2: c30b_admin.py (Handle the new button click) ---
path_admin = "bot_chunks/c30b_admin.py"
content_admin = open(path_admin).read()

new_handler = '''
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_close_chat:"))
def _cb_admin_close_chat(call):
    uid = call.from_user.id
    try:
        target_uid = int(call.data.split(":")[1])
    except:
        return
        
    import sys as _sys_close
    for _mn, _mo in _sys_close.modules.items():
        if hasattr(_mo, "TWO_WAY_CHAT"):
            if target_uid in _mo.TWO_WAY_CHAT:
                _mo.TWO_WAY_CHAT.pop(target_uid, None)
        if hasattr(_mo, "PENDING_ADMIN_FLOW"):
            if uid in _mo.PENDING_ADMIN_FLOW:
                _mo.PENDING_ADMIN_FLOW.pop(uid, None)

    try:
        bot.answer_callback_query(call.id, "Chat Closed")
        bot.edit_message_text("🔒 *Chat closed with user.*", chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except:
        pass
        
    try:
        bot.send_message(target_uid, "🔒 The admin has closed this chat session. You can now continue using the bot normally.")
    except:
        pass
'''

if "admin_close_chat:" not in content_admin:
    # Insert before the final print statement
    marker = 'print("c30b_admin: loaded (panel v2).")'
    content_admin = content_admin.replace(marker, new_handler + "\n\n" + marker)
    try:
        ast.parse(content_admin)
        open(path_admin, "w").write(content_admin)
        print("✅ Patched c30b_admin.py: Added handler for Close Chat button.")
    except Exception as e:
        print(f"❌ c30b_admin.py patch failed: {e}")
else:
    print("✅ c30b_admin.py already has the handler.")

