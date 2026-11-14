import datetime as _dt_safe
import os, json, time, threading, datetime, requests, random, string
from io import BytesIO
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
try:
    import qrcode
except ImportError:
    pass

ADMIN_GROUP_ID = 8857708587
PROOF_CHANNEL = "@HKonlinepurchasingproof"
STORE_STATE = {}

ACTIVE_ORDERS_FILE = "data/active_orders.json"
PENDING_FILE = "data/pending_payments.json"
def _load_active_orders():
    if not os.path.exists(ACTIVE_ORDERS_FILE): return {}
    try: return json.load(open(ACTIVE_ORDERS_FILE))
    except: return {}
def _save_active_orders():
    os.makedirs("data", exist_ok=True)
    json.dump(ACTIVE_ORDERS, open(ACTIVE_ORDERS_FILE, "w"), indent=2)

ACTIVE_ORDERS = _load_active_orders()
 # PERSISTENT MEMORY FOR PAYMENTS
ORDERS_FILE = "data/user_orders.json"

PRODUCTS = {
    "1": {"name": "📘 Analyser Module", "price": 249, "cost": 100, "link": "https://wa.me/p/29345775085017763/918074231426"},
    "3": {"name": "📕 BIPC Edition (NEET)", "price": 679, "cost": 470, "link": "https://wa.me/p/37659707166953822/918074231426"},
    "4": {"name": "📙 JEE Complete All-in-One", "price": 859, "cost": 580, "link": "https://wa.me/p/27602087376124822/918074231426"},
    "5": {"name": "🧪 Organic Chemistry", "price": 369, "cost": 190, "link": "https://wa.me/p/37197185153261563/918074231426"},
    "6": {"name": "📗 JEE Slim Edition", "price": 699, "cost": 460, "link": "https://wa.me/p/38161400123451221/918074231426"},
    "7": {"name": "📘 MPC Edition", "price": 699, "cost": 470, "link": "https://wa.me/p/36883482691295177/918074231426"},
    "8": {"name": "⚛️ Physics", "price": 369, "cost": 230, "link": "https://wa.me/p/27177195635293074/918074231426"},
    "9": {"name": "📐 Mathematics", "price": 319, "cost": 150, "link": "https://wa.me/p/28258833240380540/918074231426"},
    "10": {"name": "🧪 Chemistry", "price": 329, "cost": 190, "link": "https://wa.me/p/27775224768808817/918074231426"},
    "ai_1y": {"name": "🤖 Hamilton AI Plan (1 Year)", "price": 299, "cost": 0, "is_ai": True, "years": 1, "link": "https://wa.me/p/28858350743773416/918074231426"}
}

FAMGATEWAY_API_KEY = "fam_e90eb23d48d77a1312e9845512c35bb47879e923"
CREATE_ORDER_URL = "https://famgateway.in/api/create-order"
CHECK_STATUS_URL = "https://famgateway.in/api/checkout-status.php"

def _load_orders():
    if not os.path.exists(ORDERS_FILE): return {}
    try: return json.load(open(ORDERS_FILE))
    except: return {}

def _save_orders(data):
    os.makedirs("data", exist_ok=True)
    json.dump(data, open(ORDERS_FILE, "w"), indent=2)

def _get_cart(uid):
    if uid not in STORE_STATE: 
        STORE_STATE[uid] = {"cart": {}, "ai_recipient": None, "pending_ai": None, "final_amount": 0}
    return STORE_STATE[uid]

def _get_ai_slots():
    try: pk = json.load(open("data/paid_keys.json"))
    except: pk = {}
    sold = len(pk)
    return max(0, 90 - sold), sold

def get_next_order_id():
    os.makedirs("data", exist_ok=True)
    counter_file = "data/order_counter.json"
    try: data = json.load(open(counter_file)) if os.path.exists(counter_file) else {"count": 0}
    except: data = {"count": 0}
    data["count"] += 1
    json.dump(data, open(counter_file, "w"))
    return f"HK-ORD-{str(data['count']).zfill(4)}"

def create_fam_order(order_id, amount, name):
    headers = {"Authorization": f"Bearer {FAMGATEWAY_API_KEY}", "Content-Type": "application/json"}
    payload = {"amount": str(amount), "order_id": order_id, "customer_name": name}
    try:
        r = requests.post(CREATE_ORDER_URL, json=payload, headers=headers, timeout=10)
        return r.json()
    except: return None

def check_fam_status(order_id):
    try:
        # Reduced timeout to 5 seconds to prevent freezing
        r = requests.get(f"{CHECK_STATUS_URL}?order_id={order_id}", timeout=5)
        return r.json()
    except Exception as e:
        print(f"API Check Timeout: {e}")
        return None


@bot.message_handler(commands=['test_fam'])
def cmd_test_fam(message):
    uid = message.chat.id
    bot.send_message(uid, "⏳ Generating ₹1 Test QR from Gateway...")
    
    order_id = get_next_order_id()
    api_res = create_fam_order(order_id, 1, "Test User")
    
    if not api_res or api_res.get("status") != "success":
        return bot.send_message(uid, f"❌ API Error: {api_res}")
        
    data = api_res.get("data", {})
    upi_intent = data.get("upi_intent")
    fam_id = data.get("order_id")
    
    if not upi_intent:
        return bot.send_message(uid, "❌ No UPI intent in response.")
        
    expiry_time = time.time() + 300
    ACTIVE_ORDERS[order_id] = {
        "order_id": order_id,
        "name": "Test User",
        "amount": 1,
        "fam_id": fam_id,
        "paid": False,
        "expired": False,
        "expiry": expiry_time
    }
    _save_active_orders()
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Verify ₹1 Payment", callback_data=f"verify_manual:{order_id}"))
    fam_show_id = f"HK Publications {fam_id}"
    caption = f"🧪 <b>TEST QR</b>\n🏷 <b>Order ID:</b> <code>{fam_show_id}</code>\n💰 <b>Amount: ₹1.00</b>\n\nPay this and click Verify."
    
    import qrcode
    from io import BytesIO
    bio = BytesIO()
    qr = qrcode.make(upi_intent)
    qr.save(bio, "PNG")
    bio.seek(0)
    
    photo_msg = bot.send_photo(uid, bio, caption=caption, parse_mode="HTML", reply_markup=kb)
    
    # SEND THE LIVE TIMER
    t_msg = bot.send_message(uid, "⏳ <b>Time Remaining:</b> 05:00", parse_mode="HTML")
    
    ACTIVE_ORDERS[order_id]["photo_msg_id"] = photo_msg.message_id
    ACTIVE_ORDERS[order_id]["timer_msg_id"] = t_msg.message_id
    _save_active_orders()
    
    def run_live_timer(msg_id, o_id):
        while True:
            rem = int(expiry_time - time.time())
            if rem < 0: rem = 0
            mins, secs = divmod(rem, 60)
            try: bot.edit_message_text(f"⏳ <b>Time Remaining:</b> {mins:02d}:{secs:02d}", chat_id=uid, message_id=msg_id, parse_mode="HTML")
            except: pass
            if rem == 0:
                if o_id in ACTIVE_ORDERS:
                    ACTIVE_ORDERS[o_id]["expired"] = True
                    _save_active_orders()
                    try: bot.delete_message(uid, ACTIVE_ORDERS[o_id].get("photo_msg_id"))
                    except: pass
                    try: bot.delete_message(uid, msg_id)
                    except: pass
                    try: bot.send_message(uid, "❌ <b>Scanner Expired!</b>\nPlease checkout again.", parse_mode="HTML")
                    except: pass
                break
            time.sleep(0.5)
            
    threading.Thread(target=run_live_timer, args=(t_msg.message_id, order_id), daemon=True).start()


def fam_auto_verify_worker():
    """Checks pending FamGateway orders every 15 seconds. If paid, auto-delivers."""
    while True:
        time.sleep(15)
        for oid, order in list(ACTIVE_ORDERS.items()):
            if order.get("paid"): continue
            
            fam_id = order.get("fam_id")
            if not fam_id: continue
            
            api_res = check_fam_status(fam_id)
            if api_res:
                res_str = str(api_res).lower()
                if "success" in res_str or "completed" in res_str or "paid" in res_str:
                    if "pending" not in res_str and "failed" not in res_str:
                        # IT IS PAID! Auto-fulfill.
                        order["paid"] = True
                        order["utr"] = "AUTO_" + str(random.randint(100000, 999999))
                        order["verify_duration"] = "Auto"
                        _save_active_orders()
                        
                        uid = order.get("uid")
                        if uid:
                            try: bot.send_message(uid, "🎉 <b>Payment Verified Automatically!</b>\nYour order is confirmed.", parse_mode="HTML")
                            except: pass
                        try:
                            fake_call = type('obj', (object,), {'id': 0, 'message': type('obj', (object,), {'chat': type('obj', (object,), {'id': ADMIN_GROUP_ID})})(), 'data': f'admin_approve:{uid}:{oid}', 'from_user': type('obj', (object,), {'id': uid})()})
                            admin_verify(fake_call, order)
                        except: pass

try:
    threading.Thread(target=fam_auto_verify_worker, daemon=True).start()
    print("✅ FamGateway Auto-Verify Worker Started")
except: pass

@bot.message_handler(commands=['cost'])
def cmd_cost(message):
    if str(message.chat.id) != str(ADMIN_GROUP_ID) and message.chat.id != 8857708587: return
    orders = _load_orders()
    today = _dt_safe.date.today().isoformat()
    total_print_cost = 0
    total_orders = 0
    total_books = 0
    
    for uid, u_orders in orders.items():
        for o in u_orders:
            if o.get("date", "").startswith(today) and o.get("status") != "CANCELLED":
                total_orders += 1
                # Recalculate cost from cart/items
                for pid, qty in o.get("cart_raw", {}).items():
                    if not PRODUCTS[pid].get("is_ai"):
                        total_print_cost += PRODUCTS[pid]["cost"] * qty
                        total_books += qty
                        
    msg = f"💰 <b>Today's Print Cost Report</b>\n\n📦 Orders: {total_orders}\n📚 Books: {total_books}\n💸 To Pay Manager: ₹{total_print_cost}"
    bot.send_message(message.chat.id, msg, parse_mode="HTML")


@bot.message_handler(commands=['shop'])
def cmd_shop(message):
    uid = message.chat.id
    STORE_STATE[uid] = {"cart": {}, "ai_recipient": None, "pending_ai": None, "final_amount": 0}
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🛒 Buy Books & AI", callback_data="shop_buy"))
    kb.add(InlineKeyboardButton("📄 View Product Details", callback_data="shop_details"))
    kb.add(InlineKeyboardButton("🤖 Hamilton AI Limits", callback_data="shop_ai_limit"))
    kb.add(InlineKeyboardButton("📦 My Pending Orders", callback_data="shop_orders"))
    kb.add(InlineKeyboardButton("📢 View Purchase Proofs", url="https://t.me/HKonlinepurchasingproof"))
    bot.send_message(uid, "🏪 <b>Welcome to HK Publications!</b>", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("shop_", "add_prod:", "rem_prod:", "det_prod:", "loc:", "ai_for:", "contact_admin:", "admin_approve:", "admin_reject:", "del_date:", "cancel_order")) or c.data in ["checkout", "ignore", "ai_confirm:yes", "shop_exit", "shop_continue", "confirm_pay"] or c.data.startswith("verify_manual:"))
def handle_store_callback(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    data = call.data
    uid = call.message.chat.id
    state = _get_cart(uid)

    try:
        if data == "shop_buy": render_shop_menu(uid, call.message.message_id)
        elif data == "shop_details":
            kb = InlineKeyboardMarkup(row_width=1)
            for pid, p in PRODUCTS.items(): kb.add(InlineKeyboardButton(f"{p['name']}", callback_data=f"det_prod:{pid}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="shop_main"))
            bot.edit_message_text("📄 <b>Product Details</b>", chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="HTML")
        elif data.startswith("det_prod:"):
            p = PRODUCTS[data.split(":")[1]]
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔗 Open WhatsApp Link", url=p['link'])).add(InlineKeyboardButton("🔙 Back", callback_data="shop_details"))
            bot.edit_message_text(f"📦 <b>{p['name']}</b>\n💰 Price: ₹{p['price']}", chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="HTML")
        elif data == "shop_ai_limit":
            avail, sold = _get_ai_slots()
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🛒 Buy Now", callback_data="shop_buy")) if avail > 0 else InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="shop_main"))
            bot.edit_message_text(f"🤖 <b>Hamilton AI Premium</b>\n\nTotal Seats: 90\nRegistered: {sold}\nRemaining: {avail}", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        elif data == "shop_orders":
            orders_data = _load_orders().get(str(uid), [])
            if not orders_data: return bot.edit_message_text("📦 No pending orders.", chat_id=uid, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="shop_main")))
            kb = InlineKeyboardMarkup(); msg = "📦 <b>Your Orders:</b>\n\n"
            for idx, o in enumerate(orders_data):
                msg += f"🛒 <b>Order {idx+1}:</b>\n📅 Delivery: {o.get('delivery')}\n💰 Total: ₹{o.get('total')}\n"
                if not o.get("contacted_admin"): kb.add(InlineKeyboardButton(f"Contact Admin (Order {idx+1})", callback_data=f"contact_admin:{idx}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="shop_main"))
            bot.edit_message_text(msg, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        elif data.startswith("contact_admin:"):
            idx = data.split(":")[1]; orders_data = _load_orders()
            if str(uid) in orders_data and int(idx) < len(orders_data[str(uid)]):
                orders_data[str(uid)][int(idx)]["contacted_admin"] = True; _save_orders(orders_data)
                bot.send_message(uid, "👉 <a href='https://wa.me/918074231426'>Message Admin</a>", parse_mode="HTML")
            handle_store_callback(type('obj', (object,), {'id': call.id, 'message': call.message, 'data': 'shop_orders'})())
        elif data == "shop_main": cmd_shop(call.message)
        elif data.startswith("add_prod:"):
            pid = data.split(":")[1]
            if PRODUCTS[pid].get("is_ai"):
                if _get_ai_slots()[0] <= 0: return bot.answer_callback_query(call.id, "❌ Sold Out!", show_alert=True)
                state["pending_ai"] = pid
                kb = InlineKeyboardMarkup().add(InlineKeyboardButton("👤 For Me", callback_data="ai_for:me")).add(InlineKeyboardButton("🎁 For Someone Else", callback_data="ai_for:other"))
                return bot.edit_message_text(f"🤖 <b>{PRODUCTS[pid]['name']}</b>\nWho is this for?", chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="HTML")
            state["cart"][pid] = state["cart"].get(pid, 0) + 1
            render_shop_menu(uid, call.message.message_id)
        elif data.startswith("rem_prod:"):
            pid = data.split(":")[1]
            if pid in state["cart"]:
                state["cart"][pid] -= 1
                if state["cart"][pid] <= 0: del state["cart"][pid]
            render_shop_menu(uid, call.message.message_id)
        elif data.startswith("ai_for:"):
            if data.split(":")[1] == "me":
                p = load_profile(uid)
                if p.get("secured") and p.get("is_paid"):
                    state["ai_recipient"] = p.get("name", "Me")
                    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Yes, Buy Another", callback_data="ai_confirm:yes")).add(InlineKeyboardButton("❌ Cancel", callback_data="shop_buy"))
                    return bot.edit_message_text("⚠️ You already have an active plan. Buy another?", chat_id=uid, message_id=call.message.message_id, reply_markup=kb)
                state["ai_recipient"] = p.get("name", "Me")
                state["cart"][state["pending_ai"]] = state["cart"].get(state["pending_ai"], 0) + 1
                render_shop_menu(uid, call.message.message_id)
            else:
                msg = bot.send_message(uid, "🎁 Enter the name of the person:")
                bot.register_next_step_handler(msg, process_ai_recipient_name)
        elif data == "ai_confirm:yes":
            state["cart"][state["pending_ai"]] = state["cart"].get(state["pending_ai"], 0) + 1
            render_shop_menu(uid, call.message.message_id)
        elif data == "checkout":
            if not state["cart"]: return
            msg = bot.send_message(uid, "📝 <b>Enter your Full Name for delivery:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, process_store_name)
        elif data.startswith("del_date:"):
            state["delivery_date"] = data.split(":", 1)[1]
            base_t, disc, deliv, final_t = calculate_final_amount(state)
            state["final_amount"] = final_t
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Confirm & Pay", callback_data="confirm_pay")).add(InlineKeyboardButton("❌ Cancel", callback_data="shop_buy"))
            msg = f"📦 Base: ₹{base_t}\n🎉 Discount: -₹{disc}\n🚚 Delivery: ₹{deliv}\n💰 <b>Total: ₹{final_t}</b>\n\nProceed to payment?"
            bot.edit_message_text(msg, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "confirm_pay":
            if state.get("active_order_id") and time.time() < state.get("qr_expiry", 0):
                return bot.send_message(uid, "⚠️ <b>Scanner already sent!</b>\nPlease complete payment using the previous QR.", parse_mode="HTML")
            try: bot.delete_message(uid, call.message.message_id)
            except: pass
            if state.get("location") == "Outside": bot.send_message(uid, "⚠️ External delivery charges apply. Contact Admin after payment.", parse_mode="HTML")
            generate_qr(uid, state["final_amount"])
        elif data.startswith("verify_manual:"):
            order_id = data.split(":")[1]
            order = ACTIVE_ORDERS.get(order_id)
            
            if not order: return bot.send_message(uid, "❌ <b>Order Expired.</b> Please checkout again.")
            if order.get("paid"): return bot.send_message(uid, "✅ <b>This order is already verified and paid.</b>", parse_mode="HTML")

            msg = bot.send_message(uid, "🔄 <b>Verifying your payment...</b>\nPlease wait up to 30 seconds for the bank to settle.", parse_mode="HTML")
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
                fail_msg = "⏳ <b>Payment Not Detected Yet.</b>\n\nIf you have paid, please tap <b>Verify Again</b> to double-check, or contact Admin if the issue persists."
                kb_fail = InlineKeyboardMarkup()
                kb_fail.add(InlineKeyboardButton("🔄 Verify Again", callback_data=f"verify_manual:{order_id}"))
                kb_fail.add(InlineKeyboardButton("💬 Contact Admin", url="https://wa.me/918074231426"))
                bot.send_message(uid, fail_msg, parse_mode="HTML", reply_markup=kb_fail)
                
                try:
                    pending = json.load(open(PENDING_FILE)) if os.path.exists(PENDING_FILE) else {}
                    pending[order_id] = {"uid": uid, "name": order.get("name"), "amount": order.get("amount"), "order_data": order}
                    json.dump(pending, open(PENDING_FILE, "w"), indent=2)
                    bot.send_message(ADMIN_GROUP_ID, f"🚨 <b>New Pending Payment!</b>\nType admin code and check panel.", parse_mode="HTML")
                except: pass

        elif data.startswith("cancel_order"):
            order_id = data.split(":")[1] if ":" in data else None
            if order_id and order_id in ACTIVE_ORDERS:
                ACTIVE_ORDERS[order_id]["expired"] = True
                _save_active_orders()
            try: bot.delete_message(uid, call.message.message_id)
            except: pass
            bot.send_message(uid, "❌ Order Cancelled.")
        elif data.startswith("admin_approve:") or data.startswith("admin_reject:"):
            admin_verify(call)
        elif data in ["shop_exit", "shop_continue"]:
            if data == "shop_exit":
                STORE_STATE.pop(uid, None)
                bot.edit_message_text("✅ Exited store.", chat_id=uid, message_id=call.message.message_id)
            else: cmd_shop(call.message)
    except Exception as e:
        print(f"Store Error: {e}")
        bot.send_message(uid, f"⚠️ System Error: {e}")

def process_store_name(message):
    uid = message.chat.id
    _get_cart(uid)["order_name"] = message.text.strip()[:40]
    msg = bot.send_message(uid, "📞 <b>Please enter your 10-digit Phone Number:</b>")
    bot.register_next_step_handler(msg, process_store_phone)

def process_store_phone(message):
    uid = message.chat.id
    _get_cart(uid)["phone"] = message.text.strip()[:15]
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
    loc_input = message.text.strip()
    state["location"] = loc_input[:50]
    
    if "nellore" in loc_input.lower():
        msg = bot.send_message(uid, "📍 <b>Please send your exact Google Maps location link or full house address:</b>")
        bot.register_next_step_handler(msg, process_store_map_link)
        return
    else:
        bot.send_message(uid, "⚠️ <b>Note:</b> You are outside Nellore. External delivery charges may apply.")
        state["map_link"] = "Outside Nellore"
        ask_delivery_date(uid)

def process_store_map_link(message):
    uid = message.chat.id
    _get_cart(uid)["map_link"] = message.text.strip()
    ask_delivery_date(uid)

def ask_delivery_date(uid):
    import datetime as _dt_fix
    try: today = _dt_fix.datetime.now().date()
    except: today = _dt_fix.date.today()
        
    kb = InlineKeyboardMarkup(row_width=1)
    for i in range(3, 8):
        d = today + _dt_fix.timedelta(days=i)
        slot = "10 AM - 7 PM" if d.strftime("%A") == "Sunday" else "Evening 7-9 PM"
        kb.add(InlineKeyboardButton(f"{d.strftime('%d %b')} ({d.strftime('%A')}) - {slot}", callback_data=f"del_date:{d.strftime('%Y-%m-%d')} ({slot})"))
    kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="shop_buy"))
    bot.send_message(uid, "📅 <b>Select Delivery Date & Time:</b>\n<i>(Min 3 days, Max 7 days)</i>", reply_markup=kb)

def process_ai_recipient_name(message):
    uid = message.chat.id
    state = _get_cart(uid)
    state["ai_recipient"] = message.text.strip()[:30]
    state["cart"][state["pending_ai"]] = state["cart"].get(state["pending_ai"], 0) + 1
    msg = bot.send_message(uid, "✅ Added to cart.")
    render_shop_menu(uid, msg.message_id)

def render_shop_menu(uid, msg_id):
    state = _get_cart(uid)
    kb = InlineKeyboardMarkup(row_width=3)
    base_total = 0; total_qty = 0
    for pid, p in PRODUCTS.items():
        qty = state["cart"].get(pid, 0)
        base_total += p["price"] * qty; total_qty += qty
        if qty == 0: kb.row(InlineKeyboardButton(f"{p['name'][:15]} - ₹{p['price']}", callback_data=f"add_prod:{pid}"))
        else: kb.row(InlineKeyboardButton("[-]", callback_data=f"rem_prod:{pid}"), InlineKeyboardButton(f"{qty}x {p['name'][:15]}", callback_data="ignore"), InlineKeyboardButton("[+]", callback_data=f"add_prod:{pid}"))
    discount = total_qty * 30
    final_total = max(0, base_total - discount)
    if total_qty > 0: kb.add(InlineKeyboardButton(f"✅ Checkout - ₹{final_total}", callback_data="checkout"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="shop_main"))
    txt = "📚 <b>Select Products:</b>\nClick [+] to add."
    if total_qty > 0: txt += f"\n\n📦 Base: ₹{base_total}\n🎉 <b>DISCOUNT: -₹{discount}</b>\n💰 <b>Total: ₹{final_total}</b>"
    try: bot.edit_message_text(txt, chat_id=uid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    except: pass

def generate_qr(uid, total):
    state = _get_cart(uid)
    order_id = get_next_order_id()
    api_res = create_fam_order(order_id, total, state.get("order_name", "Customer"))
    if not api_res or api_res.get("status") != "success": return bot.send_message(uid, "⚠️ <b>Payment Gateway down.</b> Contact Admin.")
    data = api_res.get("data", {})
    upi_intent = data.get("upi_intent")
    if not upi_intent: return bot.send_message(uid, "⚠️ <b>Gateway Error:</b> No UPI intent.")
    
    expiry_time = time.time() + 300
    state["qr_expiry"] = expiry_time
    
    # SAVE TO PERMANENT MEMORY
    ACTIVE_ORDERS[order_id] = {
        "order_id": order_id,
        "name": state.get("order_name"),
        "phone": state.get("phone", "N/A"),
        "map_link": state.get("map_link", "N/A"),
        "amount": total,
        "cart": state["cart"].copy(),
        "location": state.get("location"),
        "delivery": state.get("delivery_date"),
        "fam_id": data.get("order_id"),
        "paid": False,
        "expired": False,
        "expiry": expiry_time
    }
    _save_active_orders()
    
    exp_time = time.strftime("%I:%M %p", time.localtime(expiry_time))
    cart_txt = "".join([f"  • {p['name']} (x{qty}) - ₹{p['price'] * qty}\n" for pid, qty in state["cart"].items() for p in [PRODUCTS[pid]]])
    fam_show_id = f"HK Publications {data.get('order_id')}"
    caption = f"🧾 <b>OFFICIAL RECEIPT</b>\n➖➖➖➖➖➖➖➖➖➖➖➖\n👤 <b>Customer:</b> {state.get('order_name')}\n🏷 <b>Order ID:</b> <code>{fam_show_id}</code>\n📍 <b>Location:</b> {state.get('location')}\n📅 <b>Delivery:</b> {state.get('delivery_date')}\n\n🛒 <b>Cart:</b>\n{cart_txt}\n💰 <b>Total: ₹{total:.2f}</b>\n➖➖➖➖➖➖➖➖➖➖➖➖\n👇 <b>Scan QR below.</b>"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_manual:{order_id}")).add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_order:{order_id}"))
    
    bio = None
    try:
        qr = qrcode.make(upi_intent)
        bio = BytesIO(); qr.save(bio, "PNG"); bio.seek(0)
    except: pass
    photo_msg = None
    if bio: photo_msg = bot.send_photo(uid, bio, caption=caption, parse_mode="HTML", reply_markup=kb)
    else: photo_msg = bot.send_message(uid, caption + f"\n\n<a href='{upi_intent}'>Click Here</a>", parse_mode="HTML", reply_markup=kb)

    # EXACT 1-SECOND TIMER
    t_msg = bot.send_message(uid, "⏳ <b>Time Remaining:</b> 05:00", parse_mode="HTML")
    
    if order_id in ACTIVE_ORDERS:
        ACTIVE_ORDERS[order_id]["photo_msg_id"] = photo_msg.message_id
        ACTIVE_ORDERS[order_id]["timer_msg_id"] = t_msg.message_id
        _save_active_orders()
    def run_live_timer(msg_id, o_id):
        while True:
            rem = int(expiry_time - time.time())
            if rem < 0: rem = 0
            mins, secs = divmod(rem, 60)
            try: bot.edit_message_text(f"⏳ <b>Time Remaining:</b> {mins:02d}:{secs:02d}", chat_id=uid, message_id=msg_id, parse_mode="HTML")
            except: pass
            if rem == 0:
                if o_id in ACTIVE_ORDERS:
                    ACTIVE_ORDERS[o_id]["expired"] = True
                    _save_active_orders()
                    
                    # DELETE OLD MESSAGES
                    try: bot.delete_message(uid, ACTIVE_ORDERS[o_id].get("photo_msg_id"))
                    except: pass
                    try: bot.delete_message(uid, msg_id) # Timer msg
                    except: pass
                    
                    # SEND NEW EXPIRED MSG
                    try: bot.send_message(uid, "❌ <b>Scanner Expired!</b>\nPlease checkout again.", parse_mode="HTML")
                    except: pass
                break
            time.sleep(0.5) # High precision
    threading.Thread(target=run_live_timer, args=(t_msg.message_id, order_id), daemon=True).start()

def admin_verify(call, order=None):
    parts = call.data.split(":")
    action = parts[0]
    target_uid = int(parts[1])
    
    if not order and len(parts) > 2:
        order_id = parts[2]
        order = ACTIVE_ORDERS.get(order_id)
        
    if not order: 
        try: bot.answer_callback_query(call.id, "❌ Order data missing or expired.", show_alert=True)
        except: pass
        return
    
    if action == "admin_approve":
        try: bot.edit_message_text("✅ Payment Approved!", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        
        cart = order.get("cart", {})
        ai_items = {pid: qty for pid, qty in cart.items() if PRODUCTS[pid].get("is_ai")}
        book_items = {pid: qty for pid, qty in cart.items() if not PRODUCTS[pid].get("is_ai")}
        user_name = order.get("name", "User")
        
        if ai_items:
            years = 1; safe_name = "".join(ch for ch in user_name if ch.isalnum())[:10].capitalize()
            key = f"HK-AI-{safe_name}-{years}Y-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            exp_date = _dt_safe.datetime.now() + _dt_safe.timedelta(days=365 * int(years))
            if not os.path.exists("data/paid_keys.json"): json.dump({}, open("data/paid_keys.json", "w"))
            try: pk = json.load(open("data/paid_keys.json"))
            except: pk = {}
            pk[key] = {"user_id": target_uid, "name": user_name, "years": years, "order_id": call.data, "purchase_date": _dt_safe.datetime.now().isoformat(), "expires_at": exp_date.isoformat(), "status": "ACTIVE"}
            json.dump(pk, open("data/paid_keys.json", "w"), indent=2)
            bot.send_message(target_uid, f"🎉 <b>AI Access Verified!</b>\n\n🔑 Key: <code>{key}</code>\n\n👉 <a href='https://wa.me/918074231426'>Contact Admin</a>", parse_mode="HTML")
            
        if book_items:
            orders_data = _load_orders()
            uid_str = str(target_uid)
            if uid_str not in orders_data: orders_data[uid_str] = []
            items_txt = "".join([f"- {PRODUCTS[pid]['name']} x{qty}\n" for pid, qty in book_items.items()])
            orders_data[uid_str].append({"name": user_name, "items": items_txt, "total": order.get("amount"), "delivery": order.get('delivery'), "location": order.get('location'), "status": "PENDING", "contacted_admin": False, "cart_raw": cart, "date": _dt_safe.datetime.now().isoformat()})
            _save_orders(orders_data)
            bot.send_message(target_uid, f"🎉 <b>Payment Verified Successfully!</b>\n\n🆔 <b>Order ID:</b> <code>{order.get('order_id', 'HK-ORD')}</code>\n🔢 <b>Transaction ID:</b> <code>{order.get('utr', 'N/A')}</code>\n\n📦 <b>Items:</b>\n{items_txt}\n📅 <b>Delivery:</b> {order.get('delivery')}\n📍 <b>Location:</b> {order.get('location')}\n\n👉 <a href='https://wa.me/918074231426'>WhatsApp Admin</a>", parse_mode="HTML")
            
    elif action == "admin_reject":
        try: bot.edit_message_text("❌ Payment Rejected.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        bot.send_message(target_uid, "❌ Payment rejected. Contact Admin.")

print("✅ c03z_store.py: PERFECT REBUILD SUCCESSFUL.", flush=True)


# ═══════════════════════════════════════════════════
# PENDING ORDERS INTEGRATION
# ═══════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "admin_pending_orders")
def admin_show_pending(call):
    # Bypass strict session check because this is called from the Admin Panel
    return show_manager_panel(call.message.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pend_view:"))
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
    
    txt = f"👤 <b>Name:</b> {o.get('name')}\n📞 <b>Phone:</b> {o.get('phone')}\n📍 <b>Location:</b> {o.get('location')}\n🗺️ <b>Map/Address:</b> {o.get('map_link', 'N/A')}\n\n📦 <b>Items:</b>\n{o.get('items')}\n📅 <b>Date:</b> {o.get('delivery')}\n💰 <b>Paid:</b> ₹{o.get('total')}\n🔐 <b>OTP:</b> {o.get('otp', 'Not generated')}"
    try: bot.edit_message_text(txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pend_approve:"))
def admin_pend_approve(call):
    oid = call.data.split(":")[1]
    import json, os
    PENDING_FILE = "data/pending_payments.json"
    try:
        pending = json.load(open(PENDING_FILE))
    except:
        return
        
    if oid not in pending: return
    p = pending[oid]
    
    try:
        fake_call = type('obj', (object,), {
            'id': call.id, 
            'message': call.message, 
            'data': f'admin_approve:{p["uid"]}:{oid}', 
            'from_user': call.from_user
        })
        admin_verify(fake_call, p['order_data'])
    except Exception as e:
        print(f"Admin Approve Error: {e}")
        
    del pending[oid]
    json.dump(pending, open(PENDING_FILE, "w"), indent=2)
    bot.edit_message_text("✅ Order Approved and Receipt Sent!", chat_id=call.message.chat.id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pend_reject:"))
def admin_pend_reject(call):
    oid = call.data.split(":")[1]
    import json, os
    PENDING_FILE = "data/pending_payments.json"
    try:
        pending = json.load(open(PENDING_FILE))
    except:
        return
        
    if oid not in pending: return
    p = pending[oid]
    
    try: bot.send_message(p['uid'], "❌ Your payment was rejected. Please contact Admin.")
    except: pass
    
    del pending[oid]
    json.dump(pending, open(PENDING_FILE, "w"), indent=2)
    bot.edit_message_text("❌ Rejected.", chat_id=call.message.chat.id, message_id=call.message.message_id)




# ═══════════════════════════════════════════════════
# MANAGER LOGISTICS PANEL & OTP SYSTEM (REBUILT)
# ═══════════════════════════════════════════════════
MANAGER_SESSIONS = set()

@bot.message_handler(func=lambda m: m.text == "HK publication order panel access verify")
def manager_login_start(message):
    msg = bot.send_message(message.chat.id, "🔐 <b>Enter Manager Password:</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, manager_login_verify)

def manager_login_verify(message):
    if message.text.strip() == "Kv@ast991":
        MANAGER_SESSIONS.add(message.chat.id)
        show_manager_panel(message.chat.id)
    else:
        bot.send_message(message.chat.id, "❌ Incorrect Password. Access Denied.")

def show_manager_panel(chat_id):
    orders = _load_orders()
    today_str = _dt_safe.date.today().isoformat()
    
    pending_count = 0
    alert_today = 0
    
    for uid, u_orders in orders.items():
        for i, o in enumerate(u_orders):
            if o.get("status") == "DELIVERED": continue
            pending_count += 1
            deliv_date = str(o.get("delivery", ""))[:10]
            if deliv_date == today_str: alert_today += 1
                
    if alert_today > 0:
        bot.send_message(chat_id, f"🚨 <b>ALERT:</b> You have {alert_today} deliveries scheduled for TODAY!", parse_mode="HTML")

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"📦 Pending Orders ({pending_count})", callback_data="mgr_list"))
    kb.add(InlineKeyboardButton("📅 Manage Delivery Date", callback_data="mgr_dates"))
    kb.add(InlineKeyboardButton("🔐 Verify OTP", callback_data="mgr_verify_otp_menu"))
    kb.add(InlineKeyboardButton("❌ Close Panel", callback_data="mgr_close"))
    
    bot.send_message(chat_id, "👨‍💼 <b>Manager Logistics Panel</b>\nSelect an action:", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mgr_"))
def handle_manager_callbacks(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    
    data = call.data
    uid = call.message.chat.id
    
    if data == "mgr_close":
        try: bot.delete_message(uid, call.message.message_id)
        except: pass
        return
        
    if data == "mgr_list":
        orders = _load_orders()
        kb = InlineKeyboardMarkup(row_width=1)
        count = 0
        for u_id, u_orders in orders.items():
            for i, o in enumerate(u_orders):
                if o.get("status") != "DELIVERED":
                    count += 1
                    kb.add(InlineKeyboardButton(f"🛒 {o.get('name')} - {o.get('delivery')[:10]}", callback_data=f"mgr_view:{u_id}:{i}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="mgr_back"))
        try: bot.edit_message_text("📋 <b>Pending Deliveries:</b>", chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="HTML")
        except: pass
        
    elif data == "mgr_dates":
        bot.answer_callback_query(call.id, "Select an order from Pending to change date.", show_alert=True)
        
    elif data == "mgr_verify_otp_menu":
        bot.answer_callback_query(call.id, "OTP is verified inside the specific order.", show_alert=True)

    elif data == "mgr_back":
        try: bot.delete_message(uid, call.message.message_id)
        except: pass
        show_manager_panel(uid)

    elif data.startswith("mgr_view:"):
        _, target_uid, idx = data.split(":")
        idx = int(idx)
        orders = _load_orders()
        if target_uid not in orders or idx >= len(orders[target_uid]): return
        
        o = orders[target_uid][idx]
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("💬 WhatsApp Customer", url=f"https://wa.me/91{o.get('phone', '')}"))
        kb.add(InlineKeyboardButton("📅 Change Delivery Date", callback_data=f"mgr_date:{target_uid}:{idx}"))
        if not o.get("otp"):
            kb.add(InlineKeyboardButton("🔑 Generate OTP Now", callback_data=f"mgr_gen_otp:{target_uid}:{idx}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="mgr_list"))
        
        txt = f"👤 <b>Name:</b> {o.get('name')}\n📞 <b>Phone:</b> {o.get('phone')}\n📍 <b>Location:</b> {o.get('location')}\n🗺️ <b>Map/Address:</b> {o.get('map_link', 'N/A')}\n\n📦 <b>Items:</b>\n{o.get('items')}\n📅 <b>Date:</b> {o.get('delivery')}\n💰 <b>Paid:</b> ₹{o.get('total')}\n🔐 <b>OTP:</b> {o.get('otp', 'Not generated')}"
        try: bot.edit_message_text(txt, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        except: pass

    elif data.startswith("mgr_gen_otp:"):
        _, target_uid, idx = data.split(":")
        idx = int(idx)
        orders = _load_orders()
        o = orders[target_uid][idx]
        
        otp = str(random.randint(10000, 99999))
        o["otp"] = otp
        _save_orders(orders)
        
        try: bot.send_message(int(target_uid), f"🔐 <b>Delivery OTP</b>\nYour order is out for delivery! Share this OTP with the manager:\n\n<code>{otp}</code>", parse_mode="HTML")
        except: pass
        
        bot.answer_callback_query(call.id, f"✅ OTP Generated: {otp}. Sent to customer.", show_alert=True)
        
        # INLINE KEYBOARD FOR OTP
        kb = InlineKeyboardMarkup(row_width=3)
        kb.add(InlineKeyboardButton("1", callback_data="otp_press:1"), InlineKeyboardButton("2", callback_data="otp_press:2"), InlineKeyboardButton("3", callback_data="otp_press:3"))
        kb.add(InlineKeyboardButton("4", callback_data="otp_press:4"), InlineKeyboardButton("5", callback_data="otp_press:5"), InlineKeyboardButton("6", callback_data="otp_press:6"))
        kb.add(InlineKeyboardButton("7", callback_data="otp_press:7"), InlineKeyboardButton("8", callback_data="otp_press:8"), InlineKeyboardButton("9", callback_data="otp_press:9"))
        kb.add(InlineKeyboardButton("0", callback_data="otp_press:0"), InlineKeyboardButton("Clear", callback_data="otp_press:C"), InlineKeyboardButton("Submit", callback_data="otp_press:S"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="mgr_back"))
        
        bot.send_message(uid, f"🔐 <b>Enter OTP for {o.get('name')}</b>\nCurrent: ---", reply_markup=kb, parse_mode="HTML")
        
        if not hasattr(bot, "MANAGER_SESSIONS_OTP"): bot.MANAGER_SESSIONS_OTP = {}
        bot.MANAGER_SESSIONS_OTP[uid] = {"target_uid": target_uid, "idx": idx, "entered": "", "msg_id": None}

@bot.callback_query_handler(func=lambda c: c.data.startswith("otp_press:"))
def handle_otp_press(call):
    uid = call.message.chat.id
    if not hasattr(bot, "MANAGER_SESSIONS_OTP") or uid not in bot.MANAGER_SESSIONS_OTP: return
    
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
            try: bot.send_message(int(state["target_uid"]), "✅ <b>Order Delivered!</b>\nThank you for shopping with HK Publications.", parse_mode="HTML")
            except: pass
            
            del bot.MANAGER_SESSIONS_OTP[uid]
        else:
            bot.answer_callback_query(call.id, "❌ Incorrect OTP. Try again.", show_alert=True)
            state["entered"] = ""
            masked = "---"
            try: bot.edit_message_text(f"🔐 <b>Enter OTP for Order</b>\nCurrent: <code>{masked}</code>", chat_id=uid, message_id=call.message.message_id, reply_markup=call.message.reply_markup, parse_mode="HTML")
            except: pass
        return
    else:
        if len(state["entered"]) < 5: state["entered"] += val
        
    masked = state["entered"] + "-" * (5 - len(state["entered"]))
    try: bot.edit_message_text(f"🔐 <b>Enter OTP for Order</b>\nCurrent: <code>{masked}</code>", chat_id=uid, message_id=call.message.message_id, reply_markup=call.message.reply_markup, parse_mode="HTML")
    except: pass
