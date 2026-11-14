import ast, shutil, re, os

# ═══════════════════════════════════════════════════
# 1. FIX DELETE BUTTON FREEZE (c30b_admin.py)
# ═══════════════════════════════════════════════════
F_ADMIN = "bot_chunks/c30b_admin.py"
shutil.copy(F_ADMIN, F_ADMIN + ".bak_delfix")
ca = open(F_ADMIN).read()

# Add answer_callback_query to the delete execution function so it never freezes
if "def _cb_delete_user(call):" in ca:
    ca = ca.replace("def _cb_delete_user(call):", "def _cb_delete_user(call):\n    try: bot.answer_callback_query(call.id)\n    except: pass")
else:
    # If the function is named differently, search for it
    match = re.search(r'def _cb_delete_user.*?:', ca)
    if match:
        ca = ca.replace(match.group(0), match.group(0) + "\n    try: bot.answer_callback_query(call.id)\n    except: pass")

# ═══════════════════════════════════════════════════
# 2. AUTO-DELETE ADMIN PANEL AFTER 5 MINUTES (c30b_admin.py)
# ═══════════════════════════════════════════════════
# Find the end of the admin panel message sending
old_panel_send = '''        bot.send_message(chat_id, header, reply_markup=kb, parse_mode="Markdown")'''
# Wait, _show_admin_panel might use edit_message_text or send_message. Let's use a global thread instead.
# We will inject a background worker that clears inactive panels.

auto_delete_worker = '''
import time, threading
ADMIN_PANEL_TIMEOUT = {}

def auto_delete_admin_panels():
    while True:
        time.sleep(60) # Check every minute
        now = time.time()
        for chat_id, msg_data in list(ADMIN_PANEL_TIMEOUT.items()):
            if now - msg_data["time"] > 300: # 5 minutes
                try: bot.delete_message(chat_id, msg_data["msg_id"])
                except: pass
                del ADMIN_PANEL_TIMEOUT[chat_id]

try:
    threading.Thread(target=auto_delete_admin_panels, daemon=True).start()
except: pass
'''
if "def auto_delete_admin_panels()" not in ca:
    ca += auto_delete_worker

# We need to hook into _show_admin_panel to register the timeout
# Find the line that sends the panel message
send_match = re.search(r'(_m = bot\.send_message\(chat_id, header, reply_markup=kb, parse_mode="Markdown"\))', ca)
if not send_match:
    # Maybe it uses edit_message_text or another variable
    send_match = re.search(r'(msg = bot\.send_message\(chat_id, header, reply_markup=kb, parse_mode="Markdown"\))', ca)

if send_match:
    old_line = send_match.group(1)
    var_name = "_m" if "_m = " in old_line else "msg"
    new_line = old_line + f'\n        ADMIN_PANEL_TIMEOUT[chat_id] = {{"msg_id": {var_name}.message_id, "time": __import__("time").time()}}'
    ca = ca.replace(old_line, new_line)

ast.parse(ca)
open(F_ADMIN, "w").write(ca)
print("✅ c30b_admin.py: Delete button fixed. Admin auto-delete worker added.")


# ═══════════════════════════════════════════════════
# 3. FIX INLINE OTP KEYBOARD (c03z_store.py)
# ═══════════════════════════════════════════════════
FS = "bot_chunks/c03z_store.py"
shutil.copy(FS, FS + ".bak_inlineotp")
cs = open(FS).read()

# Find the manager panel code
if "def show_manager_panel(chat_id):" in cs:
    # Replace the OTP generator block
    old_otp = re.search(r'    elif data\.startswith\("mgr_gen_otp:"\):.*?(?=@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("otp_press:")\))', cs, re.DOTALL)
    if old_otp:
        new_otp = '''    elif data.startswith("mgr_gen_otp:"):
        _, target_uid, idx = data.split(":")
        idx = int(idx)
        orders = _load_orders()
        o = orders[target_uid][idx]
        
        otp = str(random.randint(10000, 99999))
        o["otp"] = otp
        _save_orders(orders)
        
        try: bot.send_message(int(target_uid), f"🔐 <b>Delivery OTP</b>\\nYour order is out for delivery! Share this OTP with the manager:\\n\\n<code>{otp}</code>", parse_mode="HTML")
        except: pass
        
        bot.answer_callback_query(call.id, f"✅ OTP Generated: {otp}. Sent to customer.", show_alert=True)
        
        # STRICT INLINE KEYBOARD
        kb = InlineKeyboardMarkup(row_width=3)
        kb.add(InlineKeyboardButton("1", callback_data="otp_press:1"), InlineKeyboardButton("2", callback_data="otp_press:2"), InlineKeyboardButton("3", callback_data="otp_press:3"))
        kb.add(InlineKeyboardButton("4", callback_data="otp_press:4"), InlineKeyboardButton("5", callback_data="otp_press:5"), InlineKeyboardButton("6", callback_data="otp_press:6"))
        kb.add(InlineKeyboardButton("7", callback_data="otp_press:7"), InlineKeyboardButton("8", callback_data="otp_press:8"), InlineKeyboardButton("9", callback_data="otp_press:9"))
        kb.add(InlineKeyboardButton("0", callback_data="otp_press:0"), InlineKeyboardButton("Clear", callback_data="otp_press:C"), InlineKeyboardButton("Submit", callback_data="otp_press:S"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="mgr_back"))
        
        msg = bot.send_message(uid, f"🔐 <b>Enter OTP for {o.get('name')}</b>\\nCurrent: ---", reply_markup=kb, parse_mode="HTML")
        
        if not hasattr(bot, "MANAGER_SESSIONS_OTP"): bot.MANAGER_SESSIONS_OTP = {}
        bot.MANAGER_SESSIONS_OTP[uid] = {"target_uid": target_uid, "idx": idx, "entered": "", "msg_id": msg.message_id}

'''
        cs = cs[:old_otp.start()] + new_otp + cs[old_otp.end():]

# Fix the OTP press handler to ensure it edits the right message
old_press = re.search(r'@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("otp_press:"\)\).*?(?=def |\Z)', cs, re.DOTALL)
if old_press:
    new_press = '''@bot.callback_query_handler(func=lambda c: c.data.startswith("otp_press:"))
def handle_otp_press(call):
    uid = call.message.chat.id
    if not hasattr(bot, "MANAGER_SESSIONS_OTP") or uid not in bot.MANAGER_SESSIONS_OTP: 
        return bot.answer_callback_query(call.id, "Session expired. Please click Generate OTP again.", show_alert=True)
    
    try: bot.answer_callback_query(call.id)
    except: pass
    
    val = call.data.split(":")[1]
    state = bot.MANAGER_SESSIONS_OTP[uid]
    
    if val == "C":
        state["entered"] = ""
    elif val == "S":
        orders = _load_orders()
        o = orders[state["target_uid"]][state["idx"]]
        if state["entered"] == o.get("otp"):
            o["status"] = "DELIVERED"
            o["otp"] = "USED"
            _save_orders(orders)
            
            try: bot.edit_message_text("✅ <b>OTP MATCHED. ORDER DELIVERED!</b>", chat_id=uid, message_id=call.message.message_id)
            except: pass
            try: bot.send_message(int(state["target_uid"]), "✅ <b>Order Delivered!</b>\\nThank you for shopping with HK Publications.", parse_mode="HTML")
            except: pass
            
            del bot.MANAGER_SESSIONS_OTP[uid]
        else:
            bot.answer_callback_query(call.id, "❌ Incorrect OTP. Try again.", show_alert=True)
            state["entered"] = ""
            masked = "---"
            try: bot.edit_message_text(f"🔐 <b>Enter OTP for Order</b>\\nCurrent: <code>{masked}</code>", chat_id=uid, message_id=call.message.message_id, reply_markup=call.message.reply_markup, parse_mode="HTML")
            except: pass
        return
    else:
        if len(state["entered"]) < 5: state["entered"] += val
        
    masked = state["entered"] + "-" * (5 - len(state["entered"]))
    try: bot.edit_message_text(f"🔐 <b>Enter OTP for Order</b>\\nCurrent: <code>{masked}</code>", chat_id=uid, message_id=call.message.message_id, reply_markup=call.message.reply_markup, parse_mode="HTML")
    except: pass

'''
    cs = cs[:old_press.start()] + new_press + cs[old_press.end():]
    print("✅ c03z_store.py: Manager OTP inline keyboard fixed.")

ast.parse(cs)
open(FS, "w").write(cs)
print("════ PATCH COMPLETE ════")
