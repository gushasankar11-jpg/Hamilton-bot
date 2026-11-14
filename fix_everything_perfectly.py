import ast, shutil, re, os

# ═══════════════════════════════════════════════════
# 1. FIX ADMIN PANEL (Exact String Replacement)
# ═══════════════════════════════════════════════════
F_ADMIN = "bot_chunks/c30b_admin.py"
shutil.copy(F_ADMIN, F_ADMIN + ".bak_fixed_syntax")
ca = open(F_ADMIN).read()

# We safely target the Close button to inject our new buttons above it
old_close_btn = 'kb.add(InlineKeyboardButton("\\u274c Close", callback_data="admin_close"))'
new_close_btn = '''kb.add(InlineKeyboardButton("\\U0001f4e6 Pending Orders", callback_data="admin_pending_orders"))
            kb.add(InlineKeyboardButton("\\U0001f511 Manage Keys", callback_data="admin_key_manager"))
            kb.add(InlineKeyboardButton("\\u274c Close", callback_data="admin_close"))'''

if old_close_btn in ca:
    ca = ca.replace(old_close_btn, new_close_btn, 1)
    ast.parse(ca)
    open(F_ADMIN, "w").write(ca)
    print("✅ c30b_admin.py: Buttons added safely to Admin Panel.")
else:
    print("⚠️ Could not find Close button in c30b_admin.py.")


# ═══════════════════════════════════════════════════
# 2. UPDATE STORE: Multi-Item Checkout, 30s Wait, Trust Links
# ═══════════════════════════════════════════════════
F_STORE = "bot_chunks/c03z_store.py"
shutil.copy(F_STORE, F_STORE + ".bak_final_polish")
cs = open(F_STORE).read()

# A. Add Trust Links
if "TRUST_LINKS" not in cs:
    cs = cs.replace('PROOF_CHANNEL = "@HKonlinepurchasingproof"', 'PROOF_CHANNEL = "@HKonlinepurchasingproof"\nTRUST_LINKS = "\\n\\n🌐 <b>Join our Community:</b>\\n📢 Channel: @HKonlinepurchasingproof\\n👥 Group: https://t.me/hamilton_study\\n💬 WhatsApp: https://wa.me/918074231426"')

# B. Fix the Verification Loop (Wait 30 seconds)
old_verify = re.search(r'        elif data\.startswith\("verify_manual:"\):.*?(?=        elif data\.startswith\("cancel_order"\))', cs, re.DOTALL)
if old_verify:
    new_verify = '''        elif data.startswith("verify_manual:"):
            order_id = data.split(":")[1]
            order = ACTIVE_ORDERS.get(order_id)
            
            if not order: 
                return bot.send_message(uid, "❌ <b>Order Expired or Bot Restarted.</b>\\nPlease checkout again.")
            
            if order.get("paid"):
                return bot.send_message(uid, "✅ <b>This order is already verified and paid.</b>", parse_mode="HTML")

            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_manual:{order_id}")).add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_order:{order_id}"))
            msg = bot.send_message(uid, "🔄 <b>Verifying your payment...</b>\\nPlease wait up to 30 seconds for the bank to settle.", parse_mode="HTML")
            
            fam_id = order.get("fam_id")
            is_paid = False
            utr = "N/A"
            
            # Poll FamGateway for 30 seconds
            for attempt in range(6):
                try:
                    api_res = check_fam_status(fam_id)
                    if api_res:
                        res_str = str(api_res).lower()
                        if "success" in res_str or "completed" in res_str or "paid" in res_str:
                            if "pending" not in res_str and "failed" not in res_str:
                                is_paid = True
                                data_res = api_res.get("data", {})
                                if isinstance(data_res, dict):
                                    utr = data_res.get("utr") or data_res.get("transaction_id") or "FAM_TXN"
                                break
                except: pass
                time.sleep(5) # Wait 5 seconds before checking again
            
            try: bot.delete_message(uid, msg.message_id)
            except: pass
            
            if is_paid:
                order["paid"] = True
                order["utr"] = utr
                _save_active_orders()
                
                fake_call = type('obj', (object,), {'id': call.id, 'message': call.message, 'data': f'admin_approve:{uid}:{order_id}', 'from_user': call.from_user})
                admin_verify(fake_call, order)
            else:
                bot.send_message(uid, "⏳ <b>Payment Not Detected.</b>\\nIf money was deducted, please contact Admin.", reply_markup=kb, parse_mode="HTML")
                try:
                    pending = json.load(open(PENDING_FILE)) if os.path.exists(PENDING_FILE) else {}
                    pending[order_id] = {"uid": uid, "name": order.get("name"), "amount": order.get("amount"), "order_data": order}
                    json.dump(pending, open(PENDING_FILE, "w"), indent=2)
                    bot.send_message(ADMIN_GROUP_ID, f"🚨 <b>New Pending Payment!</b>\\nType admin code and check panel.", parse_mode="HTML")
                except: pass

'''
    cs = cs[:old_verify.start()] + new_verify + cs[old_verify.end():]

# C. Fix Admin Approve Multi-Item Logic & Messages
old_approve = re.search(r'        if ai_items:.*?(?=        try:\n            items_list = "")', cs, re.DOTALL)
if old_approve:
    new_approve = '''        if ai_items:
            years = 1; safe_name = "".join(ch for ch in user_name if ch.isalnum())[:10].capitalize()
            key = f"HK-AI-{safe_name}-{years}Y-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            exp_date = datetime.datetime.now() + datetime.timedelta(days=365 * int(years))
            if not os.path.exists("data/paid_keys.json"): json.dump({}, open("data/paid_keys.json", "w"))
            try: pk = json.load(open("data/paid_keys.json"))
            except: pk = {}
            pk[key] = {"user_id": target_uid, "name": user_name, "years": years, "order_id": order.get("order_id"), "purchase_date": datetime.datetime.now().isoformat(), "expires_at": exp_date.isoformat(), "status": "ACTIVE"}
            json.dump(pk, open("data/paid_keys.json", "w"), indent=2)
            bot.send_message(target_uid, f"🎉 <b>Payment Verified for Hamilton AI!</b>\\nYour payment has been settled in our bank account. Your order is confirmed.\\n\\n🔑 <b>Your Key:</b> <code>{key}</code>{TRUST_LINKS}", parse_mode="HTML")
            
        if book_items:
            orders_data = _load_orders()
            uid_str = str(target_uid)
            if uid_str not in orders_data: orders_data[uid_str] = []
            items_txt = "".join([f"- {PRODUCTS[pid]['name']} x{qty}\\n" for pid, qty in book_items.items()])
            orders_data[uid_str].append({"name": user_name, "items": items_txt, "total": order.get("amount"), "delivery": order.get('delivery'), "location": order.get('location'), "status": "PENDING", "contacted_admin": False, "date": datetime.datetime.now().isoformat()})
            _save_orders(orders_data)
            bot.send_message(target_uid, f"🎉 <b>Payment Verified for Books!</b>\\nYour payment has been settled in our bank account. Your order is confirmed.\\n\\n📦 <b>Items:</b>\\n{items_txt}\\n📅 <b>Delivery:</b> {order.get('delivery')}\\n📍 <b>Location:</b> {order.get('location')}{TRUST_LINKS}", parse_mode="HTML")
            
'''
    cs = cs[:old_approve.start()] + new_approve + cs[old_approve.end():]

# D. Add Admin Key Manager & Pending Handlers
handlers = '''

# ═══════════════════════════════════════════════════
# PENDING ORDERS & KEY MANAGER (ADMIN PANEL)
# ═══════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "admin_pending_orders")
def admin_show_pending(call):
    import sys
    auth = sys.modules.get('__main__').auth
    session = auth.get_session(call.message.chat.id) if auth else None
    if not session or session["role"] != "primary":
        return bot.answer_callback_query(call.id, "❌ Unauthorized", show_alert=True)
        
    PENDING_FILE = "data/pending_payments.json"
    try: pending = json.load(open(PENDING_FILE)) if os.path.exists(PENDING_FILE) else {}
    except: pending = {}
        
    if not pending:
        return bot.answer_callback_query(call.id, "✅ No pending orders right now.", show_alert=True)
        
    kb = InlineKeyboardMarkup(row_width=1)
    for oid, p_data in pending.items():
        kb.add(InlineKeyboardButton(f"🛒 {p_data['name']} - ₹{p_data['amount']}", callback_data=f"admin_pend_view:{oid}"))
    kb.add(InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_close"))
    try: bot.edit_message_text("📋 <b>Pending Payments</b>\\nSelect an order to verify:", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pend_view:"))
def admin_pend_view(call):
    oid = call.data.split(":")[1]
    PENDING_FILE = "data/pending_payments.json"
    try: pending = json.load(open(PENDING_FILE))
    except: return bot.answer_callback_query(call.id, "File not found.")
        
    if oid not in pending: return bot.answer_callback_query(call.id, "Order no longer pending.")
        
    p = pending[oid]
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Approve & Send Receipt", callback_data=f"admin_pend_approve:{oid}"))
    kb.add(InlineKeyboardButton("❌ Reject", callback_data=f"admin_pend_reject:{oid}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_pending_orders"))
    txt = f"👤 <b>Name:</b> {p['name']}\\n💰 <b>Amount:</b> ₹{p['amount']}\\n🏷 <b>Order ID:</b> {oid}\\n\\nConfirm approval?"
    try: bot.edit_message_text(txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pend_approve:"))
def admin_pend_approve(call):
    oid = call.data.split(":")[1]
    PENDING_FILE = "data/pending_payments.json"
    try: pending = json.load(open(PENDING_FILE))
    except: return
    if oid not in pending: return
    p = pending[oid]
    try:
        fake_call = type('obj', (object,), {'id': call.id, 'message': call.message, 'data': f'admin_approve:{p["uid"]}:{oid}', 'from_user': call.from_user})
        admin_verify(fake_call, p['order_data'])
    except Exception as e: print(f"Admin Approve Error: {e}")
    del pending[oid]
    json.dump(pending, open(PENDING_FILE, "w"), indent=2)
    bot.edit_message_text("✅ Order Approved and Receipt Sent!", chat_id=call.message.chat.id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pend_reject:"))
def admin_pend_reject(call):
    oid = call.data.split(":")[1]
    PENDING_FILE = "data/pending_payments.json"
    try: pending = json.load(open(PENDING_FILE))
    except: return
    if oid not in pending: return
    p = pending[oid]
    try: bot.send_message(p['uid'], "❌ Your payment was rejected. Please contact Admin.")
    except: pass
    del pending[oid]
    json.dump(pending, open(PENDING_FILE, "w"), indent=2)
    bot.edit_message_text("❌ Rejected.", chat_id=call.message.chat.id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_key_manager")
def admin_key_manager(call):
    import sys
    auth = sys.modules.get('__main__').auth
    session = auth.get_session(call.message.chat.id) if auth else None
    if not session or session["role"] != "primary":
        return bot.answer_callback_query(call.id, "❌ Unauthorized", show_alert=True)
        
    try: pk = json.load(open("data/paid_keys.json"))
    except: pk = {}
    
    if not pk:
        return bot.answer_callback_query(call.id, "✅ No registered keys found.", show_alert=True)
        
    kb = InlineKeyboardMarkup(row_width=1)
    for k, data in pk.items():
        exp = data.get("expires_at", "")[:10]
        kb.add(InlineKeyboardButton(f"🔑 {k[:20]}... ({exp})", callback_data=f"admin_key_view:{k}"))
    kb.add(InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_close"))
    try: bot.edit_message_text(f"🔑 <b>Registered Keys ({len(pk)}/90)</b>\\nSelect a key to manage:", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_key_view:"))
def admin_key_view(call):
    k = call.data.split(":", 1)[1]
    try: pk = json.load(open("data/paid_keys.json"))
    except: pk = {}
    if k not in pk: return bot.answer_callback_query(call.id, "Key not found.")
    
    data = pk[k]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Add 1 Year", callback_data=f"admin_key_ext:{k}"))
    kb.add(InlineKeyboardButton("🗑 Delete Key", callback_data=f"admin_key_del:{k}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_key_manager"))
    
    txt = f"🔑 <b>Key:</b> <code>{k}</code>\\n👤 <b>User:</b> {data.get('name', 'Unknown')} (ID: {data.get('user_id')})\\n📅 <b>Expires:</b> {data.get('expires_at', 'N/A')[:10]}\\n🛒 <b>Order ID:</b> {data.get('order_id')}"
    try: bot.edit_message_text(txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_key_ext:"))
def admin_key_ext(call):
    k = call.data.split(":", 1)[1]
    try: pk = json.load(open("data/paid_keys.json"))
    except: pk = {}
    if k in pk:
        import datetime
        try:
            exp = datetime.datetime.fromisoformat(pk[k]["expires_at"])
            pk[k]["expires_at"] = (exp + datetime.timedelta(days=365)).isoformat()
            json.dump(pk, open("data/paid_keys.json", "w"), indent=2)
            bot.answer_callback_query(call.id, "✅ Extended by 1 Year!")
            admin_key_view(call)
        except: bot.answer_callback_query(call.id, "Error extending key.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_key_del:"))
def admin_key_del(call):
    k = call.data.split(":", 1)[1]
    try: pk = json.load(open("data/paid_keys.json"))
    except: pk = {}
    if k in pk:
        del pk[k]
        json.dump(pk, open("data/paid_keys.json", "w"), indent=2)
        bot.answer_callback_query(call.id, "🗑 Key Deleted!")
        admin_key_manager(call)
'''

if "def admin_key_manager(" not in cs:
    cs += handlers

ast.parse(cs)
open(F_STORE, "w").write(cs)
print("✅ c03z_store.py: Multi-item checkout, 30s wait, Key Manager added.")
print("════ PATCH COMPLETE ════")
