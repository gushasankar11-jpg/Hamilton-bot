import ast, shutil, re, datetime

FS = "bot_chunks/c03z_store.py"
shutil.copy(FS, FS + ".bak_allbugs")
cs = open(FS).read()

# 1. FIX LOCATION & ADD DATE SELECTION
old_loc = re.search(r'    elif data\.startswith\("loc:"\):.*?(?=    elif data == "confirm_pay":)', cs, re.DOTALL)
if old_loc:
    new_loc = '''    elif data.startswith("loc:"):
        loc = data.split(":")[1]
        state = _get_cart(uid)
        state["location"] = loc
        
        # Generate Date Buttons (Min 3 days, Max 5 days)
        import datetime as _dt2
        now = _dt2.datetime.now()
        d3 = (now + _dt2.timedelta(days=3)).strftime("%Y-%m-%d")
        d4 = (now + _dt2.timedelta(days=4)).strftime("%Y-%m-%d")
        d5 = (now + _dt2.timedelta(days=5)).strftime("%Y-%m-%d")
        
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton(f"{d3} (Evening 7-9 PM)", callback_data=f"del_date:{d3} Evening"))
        kb.add(InlineKeyboardButton(f"{d4} (Evening 7-9 PM)", callback_data=f"del_date:{d4} Evening"))
        kb.add(InlineKeyboardButton(f"{d5} (Sunday 10 AM - 7 PM)", callback_data=f"del_date:{d5} Sunday"))
        kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="shop_buy"))
        
        msg = "📅 <b>Select Delivery Date & Time</b>\\n\\n<i>Delivery requires a minimum of 3 days.</i>"
        try: bot.edit_message_text(msg, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        except: pass

    elif data.startswith("del_date:"):
        _, date, slot = data.split(":")
        state = _get_cart(uid)
        state["delivery_date"] = f"{date} ({slot})"
        
        total_qty = sum(qty for qty in state["cart"].values())
        discount = total_qty * 30
        base_total = sum(PRODUCTS[pid]["price"] * qty for pid, qty in state["cart"].items())
        final_total = max(0, base_total - discount) + (50 if state.get("location") == "Nellore" else 0)
        
        state["final_amount"] = final_total
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Confirm & Pay", callback_data="confirm_pay"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="shop_buy"))
        
        msg = f"📦 Base Total: ₹{base_total}\\n🎉 <b>Discount: -₹{discount}</b>\\n💵 Delivery: {'₹50' if state.get('location') == 'Nellore' else 'Contact Admin'}\\n💰 <b>Final Amount: ₹{final_total}</b>\\n\\nAre you sure you want to proceed to payment?"
        try: bot.edit_message_text(msg, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        except: pass

'''
    cs = cs[:old_loc.start()] + new_loc + cs[old_loc.end():]

# 2. FIX MIXED CART (BOOK + AI) MESSAGES IN ADMIN APPROVE
old_approve = re.search(r'            if action == "admin_approve":.*?(?=            elif action == "admin_reject":)', cs, re.DOTALL)
if old_approve:
    new_approve = '''            if action == "admin_approve":
                try: bot.edit_message_text("✅ Payment Approved!", chat_id=call.message.chat.id, message_id=call.message.message_id)
                except: pass
                
                cart = state.get("cart", {})
                ai_items = {pid: qty for pid, qty in cart.items() if PRODUCTS[pid].get("is_ai")}
                book_items = {pid: qty for pid, qty in cart.items() if not PRODUCTS[pid].get("is_ai")}
                
                prof_data = {}
                if os.path.exists(f"profiles/{target_uid}.json"):
                    try: 
                        prof_data = json.load(open(f"profiles/{target_uid}.json"))
                    except: pass
                
                # Name is strictly taken from what they typed in the store
                user_name = state.get("order_name") or prof_data.get("name") or "User"
                safe_name = "".join(ch for ch in user_name if ch.isalnum())[:10].capitalize()
                
                # --- 1. PROCESS AI ---
                if ai_items:
                    # If they clicked [+] 2 times, it's 2 years
                    ai_pid = list(ai_items.keys())[0]
                    qty_years = ai_items[ai_pid]
                    
                    key = f"HK-AI-{safe_name}-{qty_years}Y-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    exp_date = _dt.datetime.now() + _dt.timedelta(days=365 * qty_years)
                    expires_iso = exp_date.isoformat()
                    
                    if not os.path.exists("data/paid_keys.json"): json.dump({}, open("data/paid_keys.json", "w"))
                    try: pk = json.load(open("data/paid_keys.json"))
                    except: pk = {}
                    pk[key] = {"user_id": target_uid, "name": user_name, "years": qty_years, "order_id": state.get("order_id"), "purchase_date": _dt.datetime.now().isoformat(), "expires_at": expires_iso, "status": "ACTIVE"}
                    json.dump(pk, open("data/paid_keys.json", "w"), indent=2)
                    
                    # Do not auto-secure if they are buying for someone else
                    if prof_data and user_name == prof_data.get("name"):
                        prof_data["activation_key"] = key
                        prof_data["secured"] = True
                        prof_data["is_trial"] = False
                        prof_data["is_paid"] = True
                        prof_data["paid_expiry"] = expires_iso
                        json.dump(prof_data, open(f"profiles/{target_uid}.json", "w"), indent=2)
                    
                    ai_msg = f"🎉 <b>Hamilton AI Access Verified!</b>\\n\\n"
                    ai_msg += f"👤 Name: <b>{user_name}</b>\\n"
                    ai_msg += f"🔑 Key: <code>{key}</code>\\n"
                    ai_msg += f"⏳ Expires: {exp_date.strftime('%d-%b-%Y')}\\n\\n"
                    ai_msg += f"⚠️ <b>Need help?</b> <a href='https://wa.me/918074231426'>Contact Admin</a>"
                    bot.send_message(target_uid, ai_msg, parse_mode="HTML")
                    
                # --- 2. PROCESS BOOKS ---
                if book_items:
                    orders_data = _load_orders()
                    uid_str = str(target_uid)
                    if uid_str not in orders_data: orders_data[uid_str] = []
                    items_txt = ""
                    for pid, qty in book_items.items():
                        p = PRODUCTS[pid]
                        items_txt += f"- {p['name']} x{qty}\\n"
                    
                    # Calculate Book Total Separately for the list
                    book_total = sum(PRODUCTS[pid]["price"] * qty for pid, qty in book_items.items())
                    book_total = max(0, book_total - (sum(book_items.values()) * 30)) + (50 if state.get('location') == 'Nellore' else 0)
                    
                    orders_data[uid_str].append({
                        "name": user_name,
                        "items": items_txt,
                        "total": book_total,
                        "delivery_date": state.get("delivery_date", "Not Set"),
                        "location": state.get("location", "Unknown"),
                        "status": "PENDING",
                        "order_id": state.get("order_id", "HK-ORD-XXXX"),
                        "contacted_admin": False,
                        "date": _dt.datetime.now().isoformat()
                    })
                    _save_orders(orders_data)
                    
                    book_msg = f"🎉 <b>Book Order Approved!</b>\\n\\n"
                    book_msg += f"📦 <b>Items:</b>\\n{items_txt}\\n"
                    book_msg += f"📅 <b>Delivery:</b> {state.get('delivery_date')}\\n"
                    book_msg += f"📍 <b>Location:</b> {state.get('location')}\\n\\n"
                    book_msg += f"⚠️ <b>Contact Admin:</b> <a href='https://wa.me/918074231426'>WhatsApp</a>\\n"
                    book_msg += f"📢 <b>Order Proof:</b> <a href='https://t.me/HKonlinepurchasingproof'>Channel</a>"
                    bot.send_message(target_uid, book_msg, parse_mode="HTML")
                    
                # 3. POST TO PROOF CHANNEL
                try:
                    items_list = "".join([f"• {PRODUCTS[pid]['name']} (x{qty})\\n" for pid, qty in cart.items()])
                    proof_msg = f"✅ <b>PAYMENT VERIFIED</b>\\n👤 {user_name}\\n🏷 {state.get('order_id')}\\n💰 ₹{state['total_amount']}\\n\\n{items_list}"
                    bot.send_message(PROOF_CHANNEL, proof_msg, parse_mode="HTML")
                except: pass
                
                STORE_STATE.pop(target_uid, None)

'''
    cs = cs[:old_approve.start()] + new_approve + cs[old_approve.end():]

# 3. FIX /orders PENDING LIST
old_orders = re.search(r'@bot\.message_handler\(commands=\[\'orders\'\]\).*?(?=def render_shop_menu)', cs, re.DOTALL)
if old_orders:
    new_orders = '''@bot.message_handler(commands=['orders'])
def cmd_admin_orders(message):
    uid = message.chat.id
    if str(uid) != str(ADMIN_GROUP_ID) and uid != 8857708587:
        return
    
    orders = _load_orders()
    try: pk = json.load(open("data/paid_keys.json"))
    except: pk = {}
    
    completed = []
    for user_id, u_orders in orders.items():
        for o in u_orders:
            completed.append((user_id, o))
            
    completed.sort(key=lambda x: x[1].get('date', ''), reverse=True)
    pending = [c for c in completed if c[1].get('status') == 'PENDING']
    delivered = [c for c in completed if c[1].get('status') == 'DELIVERED']
    
    txt = "📊 <b>ADMIN DASHBOARD</b>\\n➖➖➖➖➖➖➖➖\\n\\n"
    txt += f"⏳ <b>PENDING BOOK DELIVERIES ({len(pending)}):</b>\\n"
    if not pending:
        txt += "None\\n"
    else:
        for uid_str, o in pending:
            txt += f"👤 {o.get('name', 'User')}\\n🏷 {o.get('order_id')}\\n💰 ₹{o.get('total')} | 📅 {o.get('delivery_date')}\\n📍 {o.get('location')}\\n➖\\n"
            
    txt += f"\\n✅ <b>DELIVERED BOOKS ({len(delivered)}):</b>\\n"
    for uid_str, o in delivered:
        txt += f"✅ {o.get('name', 'User')} | ₹{o.get('total')} | {o.get('delivery_date')}\\n"
        
    txt += f"\\n🤖 <b>TOTAL AI KEYS SOLD:</b> {len(pk)}"
    
    bot.send_message(uid, txt, parse_mode="HTML")

'''
    cs = cs[:old_orders.start()] + new_orders + cs[old_orders.end():]

ast.parse(cs)
open(FS, "w").write(cs)
print("✅ c03z_store.py patched.")

# 4. FIX c01.py KEY EXPIRY (Allows HK-AI keys)
F01 = "bot_chunks/c01.py"
shutil.copy(F01, F01 + ".bak_keyfix")
c01 = open(F01).read()

old_key_check = re.search(r'    if not profile.get\("secured"\):\n        return False\n    used_key = profile.get\("activation_key"\)\n    if not used_key:\n        return False', c01)
if old_key_check:
    new_key_check = '''    if not profile.get("secured"):
        return False
    used_key = profile.get("activation_key")
    if not used_key:
        return False
        
    # --- ALLOW PAID AI KEYS ---
    if used_key.startswith("HK-AI-"):
        try:
            import json, datetime
            pk = json.load(open("data/paid_keys.json")) if os.path.exists("data/paid_keys.json") else {}
            if used_key in pk:
                exp = datetime.datetime.fromisoformat(pk[used_key]["expires_at"])
                if datetime.datetime.now() > exp:
                    safe_send(uid, "⏳ Your Hamilton AI Paid Plan has expired. Please contact Admin.", parse_mode="HTML")
                    return True
                return False # Valid AI key, do not expire
        except Exception as e:
            print(f"AI Key check err: {e}")
    # --------------------------'''
    c01 = c01[:old_key_check.start()] + new_key_check + c01[old_key_check.end():]
    ast.parse(c01)
    open(F01, "w").write(c01)
    print("✅ c01.py patched (HK-AI keys recognized).")

print("════ PATCH COMPLETE ════")
