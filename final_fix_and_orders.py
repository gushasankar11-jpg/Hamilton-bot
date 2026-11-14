import ast, shutil, os, json

# 1. FIX c09.py SAFELY (Intercept name)
F9 = "bot_chunks/c09.py"
shutil.copy(F9, F9 + ".bak_safe")
c9 = open(F9).read()

if "c03z_store.handle_name_input" not in c9:
    inject = "def free_text_handler(message):\n"
    inject += "    import c03z_store\n"
    inject += "    if message.chat.id in c03z_store.STORE_STATE and c03z_store.STORE_STATE[message.chat.id].get('waiting_for_name'):\n"
    inject += "        c03z_store.handle_name_input(message)\n"
    inject += "        return\n"
    
    c9 = c9.replace("def free_text_handler(message):\n", inject, 1)
    ast.parse(c9)
    open(F9, "w").write(c9)
    print("✅ c09.py patched safely.")

# 2. ADD handle_name_input & /orders TO c03z_store.py
FS = "bot_chunks/c03z_store.py"
shutil.copy(FS, FS + ".bak_orders")
cs = open(FS).read()

new_funcs = '''
def handle_name_input(message):
    uid = message.chat.id
    name = message.text.strip()[:40] if message.text else "Unknown"
    state = _get_cart(uid)
    state["order_name"] = name
    state["waiting_for_name"] = False
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📍 Nellore (₹50 Delivery)", callback_data="loc:Nellore"))
    kb.add(InlineKeyboardButton("🌍 Outside Nellore", callback_data="loc:Outside"))
    kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="shop_buy"))
    
    msg = "✅ Name saved: <b>" + name + "</b>\n\n📍 <b>Where do you want your order delivered?</b>"
    bot.send_message(uid, msg, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['orders'])
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
    recent = completed[:20]
    
    pending = [c for c in completed if not c[1].get('contacted_admin')]
    
    txt = "📊 <b>ADMIN ORDER DASHBOARD</b>\n➖➖➖➖➖➖➖➖➖➖\n\n"
    txt += "⏳ <b>PENDING ORDERS (" + str(len(pending)) + "):</b>\n"
    if not pending:
        txt += "None\n"
    else:
        for uid_str, o in pending:
            txt += f"👤 {o.get('name', 'User')} (ID: {uid_str})\n💰 ₹{o.get('total')} | 📅 {o.get('delivery')}\n📍 {o.get('location')}\n➖\n"
            
    txt += "\n✅ <b>RECENT COMPLETED (" + str(len(recent)) + "):</b>\n"
    for uid_str, o in recent:
        status = "✅" if o.get('contacted_admin') else "⚠️"
        txt += f"{status} {o.get('name', 'User')} | ₹{o.get('total')} | {o.get('delivery')}\n"
        
    txt += "\n🤖 <b>TOTAL AI KEYS SOLD:</b> " + str(len(pk))
    
    bot.send_message(uid, txt, parse_mode="HTML")

'''
if "def handle_name_input(message):" not in cs:
    cs = cs.replace("@bot.callback_query_handler(func=lambda c: True)", new_funcs + "\n@bot.callback_query_handler(func=lambda c: True)")

ast.parse(cs)
open(FS, "w").write(cs)
print("✅ c03z_store.py patched: handle_name_input and /orders added.")

print("════ PATCH COMPLETE ════")
