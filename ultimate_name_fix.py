import ast, shutil, re

# 1. FIX THE CHECKOUT IN c03z_store.py (Use simple state flag)
F_STORE = "bot_chunks/c03z_store.py"
shutil.copy(F_STORE, F_STORE + ".bak_ultimate_name")
c_store = open(F_STORE).read()

old_checkout = re.search(r'    elif data == "checkout":.*?return\n', c_store, re.DOTALL)
if old_checkout:
    new_checkout = '''    elif data == "checkout":
        state = _get_cart(uid)
        if not state["cart"]:
            bot.answer_callback_query(call.id, "Your cart is empty!", show_alert=True)
            return
        
        state["waiting_for_name"] = True
        bot.send_message(uid, "📝 <b>Please enter your Full Name for the order delivery:</b>", parse_mode="HTML")
        return
'''
    c_store = c_store[:old_checkout.start()] + new_checkout + c_store[old_checkout.end():]
    ast.parse(c_store)
    open(F_STORE, "w").write(c_store)
    print("✅ Store checkout now uses a clean state flag.")

# 2. FIX THE GLOBAL TEXT HANDLER IN c09.py (Intercept name)
F_C09 = "bot_chunks/c09.py"
shutil.copy(F_C09, F_C09 + ".bak_intercept")
c09 = open(F_C09).read()

# Remove any previously failed interceptors
c09 = re.sub(r'    try:\n        import c03z_store\n        if message\.chat\.id in c03z_store\.STORE_STATE:\n            return\n    except: pass\n', '', c09)

# Find free_text_handler and inject the strict interceptor
if "SHOP INTERCEPTOR" not in c09:
    interceptor = '''
def free_text_handler(message):
    uid = message.chat.id
    
    # --- SHOP INTERCEPTOR ---
    try:
        import c03z_store
        if uid in c03z_store.STORE_STATE and c03z_store.STORE_STATE[uid].get("waiting_for_name"):
            name = message.text.strip()[:40]
            c03z_store.STORE_STATE[uid]["order_name"] = name
            c03z_store.STORE_STATE[uid]["waiting_for_name"] = False
            
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(InlineKeyboardButton("📍 Nellore (₹50 Delivery)", callback_data="loc:Nellore"))
            kb.add(InlineKeyboardButton("🌍 Outside Nellore", callback_data="loc:Outside"))
            kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="shop_buy"))
            bot.send_message(uid, f"✅ Name saved: <b>{name}</b>\\n\\n📍 <b>Where do you want your order delivered?</b>", parse_mode="HTML", reply_markup=kb)
            return
    except Exception as e:
        print(f"Interceptor error: {e}")
    # ------------------------

'''
    # Replace the function definition
    c09 = re.sub(r'def free_text_handler\(message\):\n', interceptor, c09, count=1)
    ast.parse(c09)
    open(F_C09, "w").write(c09)
    print("✅ c09.py patched: Global AI will ignore store name input.")

print("════ PATCH COMPLETE ════")
