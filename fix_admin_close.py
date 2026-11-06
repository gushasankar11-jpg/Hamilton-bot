import ast

path = "bot_chunks/c30b_admin.py"
content = open(path).read()

old_func = '''@bot.callback_query_handler(func=lambda c: c.data == "admin_close")
def _cb_admin_close(call):
    uid = call.from_user.id
    try:
        bot.answer_callback_query(call.id, "Closing...")
    except Exception:
        pass
    deleted = 0'''

new_func = '''@bot.callback_query_handler(func=lambda c: c.data == "admin_close")
def _cb_admin_close(call):
    uid = call.from_user.id
    try:
        bot.answer_callback_query(call.id, "Closing...")
    except Exception:
        pass
        
    # --- CLOSE ACTIVE TWO-WAY CHATS ---
    import sys as _sys_close
    _closed_targets = []
    for _mn, _mo in _sys_close.modules.items():
        # Clear admin pending input flow
        if hasattr(_mo, "PENDING_ADMIN_FLOW"):
            if _mo.PENDING_ADMIN_FLOW.pop(uid, None):
                print(f"[admin_close] Cleared PENDING_ADMIN_FLOW for {uid}")
        
        # Clear TWO_WAY_CHAT where this admin is the one chatting
        if hasattr(_mo, "TWO_WAY_CHAT"):
            to_remove = []
            for target_uid, data in _mo.TWO_WAY_CHAT.items():
                if data.get("admin_uid") == uid:
                    to_remove.append(target_uid)
            for t in to_remove:
                _mo.TWO_WAY_CHAT.pop(t, None)
                _closed_targets.append(t)
    
    # Notify the users that the chat was closed by the admin
    for t in _closed_targets:
        try:
            bot.send_message(t, "🔒 The admin has closed this chat session. You can continue using the bot normally.")
        except Exception as e:
            print(f"[admin_close] failed to notify {t}: {e}")

    deleted = 0'''

if old_func in content:
    content = content.replace(old_func, new_func)
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ Patched c30b_admin.py: admin_close now terminates the chat.")
    except SyntaxError as e:
        print(f"❌ Syntax Error: {e}")
else:
    print("⚠️ Could not find the exact function. Pattern mismatch.")
