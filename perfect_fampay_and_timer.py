import ast, shutil, re

FS = "bot_chunks/c03z_store.py"
shutil.copy(FS, FS + ".bak_perfect")
cs = open(FS).read()

# 1. FIX THE QR GENERATION TO PARSE FAMGATEWAY DATA & ADD LIVE TIMER
old_qr = re.search(r'def generate_qr\(uid, total\):.*?(?=@bot\.message_handler)', cs, re.DOTALL)
if old_qr:
    new_qr = '''def generate_qr(uid, total):
    import urllib.parse, requests, qrcode, datetime as _dt2
    from io import BytesIO
    
    state = _get_cart(uid)
    order_id = f"HK_{uid}_{int(time.time())}"
    name = state.get("order_name", "Customer")
    
    # 1. Call FamGateway
    api_res = create_fam_order(order_id, total, name)
    if not api_res or api_res.get("status") != "success":
        bot.send_message(uid, "⚠️ <b>Payment Gateway is temporarily down.</b>\\nPlease contact Admin.")
        return
        
    # 2. Extract the UPI Intent from the nested data dict
    data = api_res.get("data", {})
    upi_intent = data.get("upi_intent")
    
    if not upi_intent:
        bot.send_message(uid, "⚠️ <b>Gateway Error:</b> No UPI intent returned.")
        return

    state["order_id"] = order_id
    state["total_amount"] = total
    state["qr_expiry"] = time.time() + 300 
    
    exp_time = (_dt2.datetime.now() + _dt2.timedelta(minutes=5)).strftime("%I:%M %p")
    
    cart_txt = ""
    for pid, qty in state["cart"].items():
        p = PRODUCTS[pid]
        cart_txt += f"  • {p['name']} (x{qty}) - ₹{p['price'] * qty}\\n"
        
    caption = f"🧾 <b>OFFICIAL PAYMENT RECEIPT</b>\\n"
    caption += f"➖➖➖➖➖➖➖➖➖➖➖➖\\n"
    caption += f"👤 <b>Customer:</b> {name}\\n"
    caption += f"🏷 <b>Order ID:</b> <code>{order_id}</code>\\n"
    caption += f"📍 <b>Location:</b> {state.get('location', 'Nellore')}\\n"
    caption += f"📅 <b>Delivery Date:</b> {state.get('delivery_date', 'Not Set')}\\n\\n"
    caption += f"🛒 <b>Cart Details:</b>\\n{cart_txt}\\n"
    caption += f"💰 <b>Total Payable: ₹{total:.2f}</b>\\n"
    caption += f"➖➖➖➖➖➖➖➖➖➖➖➖\\n"
    caption += f"👇 <b>Scan the QR below to pay.</b>"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Verify Payment", callback_data="verify_manual"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_order"))
    
    # Generate QR Locally using the upi_intent
    bio = None
    try:
        qr = qrcode.make(upi_intent)
        bio = BytesIO()
        qr.save(bio, "PNG")
        bio.seek(0)
    except Exception as e:
        print(f"QR Gen Error: {e}")
            
    if bio:
        bot.send_photo(uid, bio, caption=caption, parse_mode="HTML", reply_markup=kb)
    else:
        bot.send_message(uid, caption + f"\\n\\n<a href='{upi_intent}'>Click Here to Pay</a>", parse_mode="HTML", reply_markup=kb)

    # 3. Send Separate Timer Message
    t_msg = bot.send_message(uid, "⏳ <b>Time Remaining:</b> 05:00", parse_mode="HTML")
    
    # 4. Start Live Timer Thread
    def run_live_timer(msg_id, o_id):
        for rem in range(299, -1, -1):
            st = _get_cart(uid)
            # Kill timer if order changed or cancelled
            if st.get("order_id") != o_id or st.get("qr_expiry") is None:
                break
                
            mins, secs = divmod(rem, 60)
            txt = f"⏳ <b>Time Remaining:</b> {mins:02d}:{secs:02d}"
            try: bot.edit_message_text(txt, chat_id=uid, message_id=msg_id, parse_mode="HTML")
            except: pass
            
            if rem == 0:
                try: bot.edit_message_text("❌ <b>Scanner Expired!</b>\\nPlease checkout again.", chat_id=uid, message_id=msg_id, parse_mode="HTML")
                except: pass
                break
                
            time.sleep(1)
            
    threading.Thread(target=run_live_timer, args=(t_msg.message_id, order_id), daemon=True).start()

'''
    cs = cs[:old_qr.start()] + new_qr + cs[old_qr.end():]

# 2. FIX THE DELIVERY DATE LOGIC (3, 4, 5 days from today)
old_loc = re.search(r'    elif data\.startswith\("loc:"\):.*?(?=    elif data == "confirm_pay":)', cs, re.DOTALL)
if old_loc:
    new_loc = '''    elif data.startswith("loc:"):
        loc = data.split(":")[1]
        state = _get_cart(uid)
        state["location"] = loc
        
        import datetime as _dt2
        today = _dt2.date.today()
        
        # Calculate 3, 4, 5 days from today
        dates = []
        for i in range(3, 6):
            d = today + _dt2.timedelta(days=i)
            day_name = d.strftime("%A")
            
            if day_name == "Sunday":
                slot = "10 AM - 7 PM"
            else:
                slot = "Evening 7-9 PM"
                
            dates.append((d.strftime("%Y-%m-%d"), f"{d.strftime('%d %b')} ({day_name}) - {slot}"))
            
        kb = InlineKeyboardMarkup(row_width=1)
        for d_val, d_label in dates:
            kb.add(InlineKeyboardButton(d_label, callback_data=f"del_date:{d_val}"))
        kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="shop_buy"))
        
        try: bot.edit_message_text("📅 <b>Select Delivery Date & Time:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        except: pass

    elif data.startswith("del_date:"):
        d_val = data.split(":")[1]
        state = _get_cart(uid)
        state["delivery_date"] = d_val
        
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

ast.parse(cs)
open(FS, "w").write(cs)
print("✅ FamGateway Parsing Fixed. Live Timer & Delivery Dates added.")
