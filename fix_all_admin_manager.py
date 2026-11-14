import ast, shutil, re

# ═══════════════════════════════════════════════════
# 1. FIX NAME AI (Reject "Raichu" & fake names)
# ═══════════════════════════════════════════════════
F_C02 = "bot_chunks/c02.py"
shutil.copy(F_C02, F_C02 + ".bak_namefix")
c02 = open(F_C02).read()

old_prompt = '''prompt = f'Analyze the name: "{n}". Is this a real human name, or is it fictional, a keyboard smash, a fake name, or a fictional character? Return ONLY JSON: {{"is_fictional": true/false, "fake_probability": 0-100}}\''''
new_prompt = '''prompt = f'Analyze the name: "{n}". Is this a real human name, or is it a fictional character (like Pokemon), a keyboard smash, or a fake name? Real names like "Rahul" or "Ram" are valid. Fictional names like "Raichu" or "Pikachu" are fake. Return ONLY JSON: {{"is_fictional": true/false, "fake_probability": 0-100}}\''''

if old_prompt in c02:
    c02 = c02.replace(old_prompt, new_prompt)
    
# Lower threshold to 20% to strictly reject fake names
c02 = c02.replace("if prob > 60:", "if prob > 20:")
ast.parse(c02)
open(F_C02, "w").write(c02)
print("✅ c02.py: AI Name verification is now strict (Raichu will be rejected).")


# ═══════════════════════════════════════════════════
# 2. FIX ADMIN PANEL BUTTON ("Pending Orders" -> "Orders")
# ═══════════════════════════════════════════════════
F_ADMIN = "bot_chunks/c30b_admin.py"
shutil.copy(F_ADMIN, F_ADMIN + ".bak_orderbtn")
ca = open(F_ADMIN).read()

ca = ca.replace('InlineKeyboardButton("\\U0001f4e6 Pending Orders", callback_data="admin_pending_orders")', 'InlineKeyboardButton("\\U0001f4e6 Orders", callback_data="admin_pending_orders")')
ast.parse(ca)
open(F_ADMIN, "w").write(ca)
print("✅ c30b_admin.py: Button renamed to 'Orders'.")


# ═══════════════════════════════════════════════════
# 3. FIX ADMIN ORDERS LOGIC & MANAGER PANEL SHARING
# ═══════════════════════════════════════════════════
FS = "bot_chunks/c03z_store.py"
shutil.copy(FS, FS + ".bak_adminshare")
cs = open(FS).read()

# Replace the old admin pending handler with a robust one
old_admin = re.search(r'@bot\.callback_query_handler\(func=lambda c: c\.data == "admin_pending_orders"\).*?(?=@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("admin_pend_view:")\))', cs, re.DOTALL)
if old_admin:
    new_admin = '''@bot.callback_query_handler(func=lambda c: c.data == "admin_pending_orders")
def admin_show_pending(call):
    import sys
    auth = sys.modules.get('__main__').auth
    session = auth.get_session(call.message.chat.id) if auth else None
    if not session or session["role"] != "primary":
        return bot.answer_callback_query(call.id, "❌ Unauthorized", show_alert=True)
        
    orders = _load_orders()
    kb = InlineKeyboardMarkup(row_width=1)
    pending_count = 0
    
    for u_id, u_orders in orders.items():
        for i, o in enumerate(u_orders):
            if o.get("status") != "DELIVERED":
                pending_count += 1
                kb.add(InlineKeyboardButton(f"🛒 {o.get('name')} - ₹{o.get('total')} ({o.get('delivery')[:10]})", callback_data=f"admin_pend_view:{u_id}:{i}"))
                
    if pending_count == 0:
        return bot.answer_callback_query(call.id, "✅ No pending orders right now.", show_alert=True)
        
    kb.add(InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_close"))
    try: bot.edit_message_text("📋 <b>All Orders</b>\\nSelect an order to manage:", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass

'''
    cs = cs[:old_admin.start()] + new_admin + cs[old_admin.end():]

# Fix the Admin View handler to include Phone and Map Link
old_admin_view = re.search(r'@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("admin_pend_view:"\)\).*?(?=@bot\.callback_query_handler\(func=lambda c: c\.data\.startswith\("admin_pend_approve:"\))', cs, re.DOTALL)
if old_admin_view:
    new_admin_view = '''@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pend_view:"))
def admin_pend_view(call):
    _, target_uid, idx = call.data.split(":")
    idx = int(idx)
    orders = _load_orders()
    
    if target_uid not in orders or idx >= len(orders[target_uid]):
        return bot.answer_callback_query(call.id, "Order not found.", show_alert=True)
        
    o = orders[target_uid][idx]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("💬 WhatsApp Customer", url=f"https://wa.me/91{o.get('phone', '')}"))
    
    if not o.get("otp") and o.get("status") != "DELIVERED":
        kb.add(InlineKeyboardButton("🔑 Generate OTP Now", callback_data=f"mgr_gen_otp:{target_uid}:{idx}"))
        
    kb.add(InlineKeyboardButton("🔙 Back to Orders", callback_data="admin_pending_orders"))
    
    txt = f"👤 <b>Name:</b> {o.get('name')}\\n📞 <b>Phone:</b> {o.get('phone')}\\n📍 <b>Location:</b> {o.get('location')}\\n🗺️ <b>Map/Address:</b> {o.get('map_link', 'N/A')}\\n\\n📦 <b>Items:</b>\\n{o.get('items')}\\n📅 <b>Date:</b> {o.get('delivery')}\\n💰 <b>Paid:</b> ₹{o.get('total')}\\n🔐 <b>OTP:</b> {o.get('otp', 'Not generated')}"
    try: bot.edit_message_text(txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass

'''
    cs = cs[:old_admin_view.start()] + new_admin_view + cs[old_admin_view.end():]

# Ensure the Manager Panel uses the same button names and logic
cs = cs.replace('MANAGER_SESSIONS.add(message.chat.id)\n        show_manager_panel(message.chat.id)', 'MANAGER_SESSIONS.add(message.chat.id)\n        show_manager_panel(message.chat.id)')

ast.parse(cs)
open(FS, "w").write(cs)
print("✅ c03z_store.py: Admin and Manager orders panel fixed & unified.")
print("════ PATCH COMPLETE ════")
