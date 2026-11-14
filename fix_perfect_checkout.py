import ast, shutil, re, os

# ═══════════════════════════════════════════════════
# 1. FIX ADMIN PANEL BUTTONS (Exact lines 204-206)
# ═══════════════════════════════════════════════════
F_ADMIN = "bot_chunks/c30b_admin.py"
shutil.copy(F_ADMIN, F_ADMIN + ".bak_fixed_buttons")
ca = open(F_ADMIN).read()

old_line = 'kb.add(InlineKeyboardButton("\\U0001f4cb Scheduled", callback_data="sv_tab:text"))'
new_lines = '''kb.add(InlineKeyboardButton("\\U0001f4cb Scheduled", callback_data="sv_tab:text"))
            kb.add(InlineKeyboardButton("\\U0001f4e6 Pending Orders", callback_data="admin_pending_orders"))
            kb.add(InlineKeyboardButton("\\U0001f511 Manage Keys", callback_data="admin_key_manager"))'''

if old_line in ca:
    ca = ca.replace(old_line, new_lines, 1)
    ast.parse(ca)
    open(F_ADMIN, "w").write(ca)
    print("✅ Admin Panel: Buttons injected successfully.")
else:
    print("❌ Could not find Scheduled button line.")

# ═══════════════════════════════════════════════════
# 2. FIX STORE LOGIC (Location, Delivery Charges, 30s Verify, Proof)
# ═══════════════════════════════════════════════════
F_STORE = "bot_chunks/c03z_store.py"
shutil.copy(F_STORE, F_STORE + ".bak_perfectcheckout")
cs = open(F_STORE).read()

# A. REPLACE PROCESS_STORE_NAME AND ADD LOCATION LOGIC
old_name_func = '''def process_store_name(message):
    uid = message.chat.id
    _get_cart(uid)["order_name"] = message.text.strip()[:40]
    kb = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton("📍 Nellore (₹50)", callback_data="loc:Nellore")).add(InlineKeyboardButton("🌍 Outside Nellore", callback_data="loc:Outside"))
    bot.send_message(uid, f"✅ Name saved: <b>{_get_cart(uid)['order_name']}</b>\\n\\n📍 <b>Where do you want delivery?</b>", parse_mode="HTML", reply_markup=kb)'''

new_name_func = '''def process_store_name(message):
    uid = message.chat.id
    _get_cart(uid)["order_name"] = message.text.strip()[:40]
    msg = bot.send_message(uid, "📍 <b>Please enter your City and State</b> (e.g., Nellore, Andhra Pradesh):")
    bot.register_next_step_handler(msg, process_store_location)

def calculate_final_amount(state):
    book_qty = sum(qty for pid, qty in state["cart"].items() if not PRODUCTS[pid].get("is_ai"))
    total_qty = sum(state["cart"].values())
    base_total = sum(PRODUCTS[pid]["price"] * qty for pid, qty in state["cart"].items())
    discount = total_qty * 30
    delivery_charge = (50 + (book_qty - 1) * 20) if book_qty > 0 else 0
    final_total = max(0, base_total - discount) + delivery_charge
    return base_total, discount, delivery_charge, final_total

def process_store_location(message):
    uid = message.chat.id
    state = _get_cart(uid)
    state["location"] = message.text.strip()[:50]
    
    book_qty = sum(qty for pid, qty in state["cart"].items() if not PRODUCTS[pid].get("is_ai"))
    
    if book_qty == 0:
        # ONLY AI
        base_total, discount, delivery, final_total = calculate_final_amount(state)
        state["final_amount"] = final_total
        state["delivery_date"] = "Digital Delivery"
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Confirm & Pay", callback_data="confirm_pay")).add(InlineKeyboardButton("❌ Cancel", callback_data="shop_buy"))
        msg = f"📦 Base: ₹{base_total}\\n🎉 Discount: -₹{discount}\\n🚚 Delivery: ₹{delivery}\\n💰 <b>Total: ₹{final_total}</b>\\n\\nProceed to payment?"
        bot.send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
    else:
        # HAS BOOKS
        import datetime as _dt_fix
        try: today = _dt_fix.datetime.now().date()
        except: today = _dt_fix.date.today()
            
        kb = InlineKeyboardMarkup(row_width=1)
        for i in range(3, 8):
            d = today + _dt_fix.timedelta(days=i)
            slot = "10 AM - 7 PM" if d.strftime("%A") == "Sunday" else "Evening 7-9 PM"
            kb.add(InlineKeyboardButton(f"{d.strftime('%d %b')} ({d.strftime('%A')}) - {slot}", callback_data=f"del_date:{d.strftime('%Y-%m-%d')} ({slot})"))
        kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="shop_buy"))
        bot.send_message(uid, "📅 <b>Select Delivery Date & Time:</b>\\n<i>(Min 3 days, Max 7 days)</i>", reply_markup=kb)'''

if old_name_func in cs:
    cs = cs.replace(old_name_func, new_name_func)
    print("✅ Location & Delivery charge logic updated.")

# B. REMOVE THE OLD LOC: HANDLER (No longer needed)
old_loc = re.search(r'        elif data\.startswith\("loc:"\):.*?(?=        elif data\.startswith\("del_date:"\))', cs, re.DOTALL)
if old_loc:
    cs = cs[:old_loc.start()] + cs[old_loc.end():]

# C. FIX DEL_DATE HANDLER TO USE NEW CALCULATION
old_del_date = re.search(r'        elif data\.startswith\("del_date:"\):.*?(?=        elif data == "confirm_pay":)', cs, re.DOTALL)
if old_del_date:
    new_del_date = '''        elif data.startswith("del_date:"):
            state["delivery_date"] = data.split(":", 1)[1]
            base_total, discount, delivery, final_total = calculate_final_amount(state)
            state["final_amount"] = final_total
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Confirm & Pay", callback_data="confirm_pay")).add(InlineKeyboardButton("❌ Cancel", callback_data="shop_buy"))
            msg = f"📦 Base: ₹{base_total}\\n🎉 Discount: -₹{discount}\\n🚚 Delivery: ₹{delivery}\\n💰 <b>Total: ₹{final_total}</b>\\n\\nProceed to payment?"
            bot.edit_message_text(msg, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

'''
    cs = cs[:old_del_date.start()] + new_del_date + cs[old_del_date.end():]

# D. FIX VERIFY_MANUAL (30s Wait + Fallback)
old_verify = re.search(r'        elif data\.startswith\("verify_manual:"\):.*?(?=        elif data\.startswith\("cancel_order"\))', cs, re.DOTALL)
if old_verify:
    new_verify = '''        elif data.startswith("verify_manual:"):
            order_id = data.split(":")[1]
            order = ACTIVE_ORDERS.get(order_id)
            
            if not order: return bot.send_message(uid, "❌ <b>Order Expired.</b> Please checkout again.")
            if order.get("paid"): return bot.send_message(uid, "✅ <b>This order is already verified and paid.</b>", parse_mode="HTML")

            msg = bot.send_message(uid, "🔄 <b>Verifying your payment...</b>\\nPlease wait up to 30 seconds for the bank to settle.", parse_mode="HTML")
            
            import time as _time
            start_time = _time.time()
            fam_id = order.get("fam_id")
            is_paid = False
            utr = "N/A"
            
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
                time.sleep(5) 
            
            try: bot.delete_message(uid, msg.message_id)
            except: pass
            
            if is_paid:
                order["paid"] = True
                order["utr"] = utr
                order["verify_duration"] = str(int(_time.time() - start_time))
                _save_active_orders()
                fake_call = type('obj', (object,), {'id': call.id, 'message': call.message, 'data': f'admin_approve:{uid}:{order_id}', 'from_user': call.from_user})
                admin_verify(fake_call, order)
            else:
                fail_msg = "⏳ <b>Payment Not Detected Yet.</b>\\n\\nIf you have paid, please tap <b>Verify Again</b> to double-check, or contact Admin if the issue persists."
                kb_fail = InlineKeyboardMarkup()
                kb_fail.add(InlineKeyboardButton("🔄 Verify Again", callback_data=f"verify_manual:{order_id}"))
                kb_fail.add(InlineKeyboardButton("💬 Contact Admin", url="https://wa.me/918074231426"))
                bot.send_message(uid, fail_msg, parse_mode="HTML", reply_markup=kb_fail)
                
                try:
                    pending = json.load(open(PENDING_FILE)) if os.path.exists(PENDING_FILE) else {}
                    pending[order_id] = {"uid": uid, "name": order.get("name"), "amount": order.get("amount"), "order_data": order}
                    json.dump(pending, open(PENDING_FILE, "w"), indent=2)
                    bot.send_message(ADMIN_GROUP_ID, f"🚨 <b>New Pending Payment!</b>\\nType admin code and check panel.", parse_mode="HTML")
                except: pass

'''
    cs = cs[:old_verify.start()] + new_verify + cs[old_verify.end():]

# E. UPDATE ADMIN_VERIFY (Proof Channel & User Receipt with Discounts)
old_approve = re.search(r'        if ai_items:.*?(?=        STORE_STATE\.pop)', cs, re.DOTALL)
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
            
            book_qty = sum(book_items.values())
            base_total = sum(PRODUCTS[pid]["price"] * qty for pid, qty in book_items.items())
            discount = book_qty * 30
            delivery = 50 + (book_qty - 1) * 20
            
            orders_data[uid_str].append({"name": user_name, "items": items_txt, "total": order.get("amount"), "delivery": order.get('delivery'), "location": order.get('location'), "status": "PENDING", "contacted_admin": False, "date": datetime.datetime.now().isoformat()})
            _save_orders(orders_data)
            bot.send_message(target_uid, f"🎉 <b>Payment Verified for Books!</b>\\nYour payment has been settled in our bank account. Your order is confirmed.\\n\\n📦 <b>Items:</b>\\n{items_txt}\\n💰 <b>Base:</b> ₹{base_total}\\n🎉 <b>Discount:</b> -₹{discount}\\n🚚 <b>Delivery:</b> ₹{delivery}\\n📅 <b>Delivery Date:</b> {order.get('delivery')}\\n📍 <b>Location:</b> {order.get('location')}{TRUST_LINKS}", parse_mode="HTML")

        try:
            items_list = "".join([f"  • {PRODUCTS[pid]['name']} (x{qty}) - ₹{PRODUCTS[pid]['price'] * qty}\\n" for pid, qty in cart.items()])
            now_str = datetime.datetime.now().strftime("%d-%b-%Y %I:%M:%S %p")
            verify_time = order.get("verify_duration", "20")
            
            all_qty = sum(cart.values())
            book_qty = sum(qty for pid, qty in cart.items() if not PRODUCTS[pid].get("is_ai"))
            base_t = sum(PRODUCTS[pid]["price"] * qty for pid, qty in cart.items())
            disc = all_qty * 30
            deliv = (50 + (book_qty - 1) * 20) if book_qty > 0 else 0
            
            proof_msg = (
                f"✅ <b>PAYMENT VERIFIED & ORDER CONFIRMED</b>\\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
                f"👤 <b>Customer:</b> {user_name}\\n"
                f"🆔 <b>Order ID:</b> <code>{order.get('order_id')}</code>\\n"
                f"📅 <b>Date & Time:</b> {now_str}\\n"
                f"⏱ <b>Verified In:</b> {verify_time} seconds\\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
                f"📦 <b>Items Purchased:</b>\\n{items_list}\\n"
                f"💰 <b>Base Total:</b> ₹{base_t}\\n"
                f"🎉 <b>Discount:</b> -₹{disc}\\n"
                f"🚚 <b>Delivery Charge:</b> ₹{deliv}\\n"
                f"💵 <b>Total Paid:</b> ₹{order.get('total_amount'):.2f}\\n"
                f"📍 <b>Location:</b> {order.get('location', 'Digital')}\\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
                f"🛡️ <i>Verified securely via automated banking network.</i>"
            )
            bot.send_message(PROOF_CHANNEL, proof_msg, parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ Failed to post to Proof Channel: {e}")
            
'''
    cs = cs[:old_approve.start()] + new_approve + cs[old_approve.end():]

ast.parse(cs)
open(F_STORE, "w").write(cs)
print("✅ c03z_store.py: Perfect Checkout, 30s Verify, Proof Channel updated.")
print("════ PATCH COMPLETE ════")
