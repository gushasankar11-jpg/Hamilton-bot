import ast, shutil

F = "bot_chunks/c03z_store.py"
shutil.copy(F, F + ".bak_fixv2")
c = open(F).read()

# ═══════════════════════════════════════════════════
# 1. FIX THE CART BUTTON (Delete + Send New)
# ═══════════════════════════════════════════════════
import re
old_show_cart = re.search(r'def show_cart\(uid, msg_id\):.*?except: pass', c, re.DOTALL)

if old_show_cart:
    new_show_cart = '''def show_cart(uid, msg_id):
    # Delete the old message so Telegram NEVER throws a "message is not modified" error
    try: bot.delete_message(uid, msg_id)
    except: pass

    state = _get_cart(uid)
    cart = state["cart"]

    if not cart:
        txt = "🛒 <b>Your Cart is Empty!</b>\\n\\nPlease add items from the shop."
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to Shop", callback_data="shop_buy"))
        bot.send_message(uid, txt, parse_mode="HTML", reply_markup=kb)
        return

    total = 0
    kb = InlineKeyboardMarkup()

    # Grid layout: [-] Name/Qty [+] for every product
    for pid, qty in cart.items():
        p = PRODUCTS[pid]
        total += p["price"] * qty
        
        name_short = p['name'][:15] + "..." if len(p['name']) > 15 else p['name']
        if p.get("is_ai"):
            name_short = f"🤖 {state.get('ai_recipient', 'Me')}"

        kb.row(
            InlineKeyboardButton("-", callback_data=f"rem_prod:{pid}"),
            InlineKeyboardButton(f"{qty}x {name_short}", callback_data="ignore"),
            InlineKeyboardButton("+", callback_data=f"add_prod:{pid}")
        )

    kb.add(InlineKeyboardButton(f"✅ Continue to Pay ₹{total}", callback_data="checkout"))
    kb.add(InlineKeyboardButton("🔙 Back to Shop", callback_data="shop_buy"))

    txt = "🛒 <b>Your Cart:</b>\\nClick <b>-</b> to remove, <b>+</b> to add."
    bot.send_message(uid, txt, parse_mode="HTML", reply_markup=kb)'''
    
    c = c[:old_show_cart.start()] + new_show_cart + c[old_show_cart.end():]
    print("✅ FIX 1: Cart updated (Deletes old message, shows exact + and -).")
else:
    print("⚠️ Could not find show_cart function.")

# ═══════════════════════════════════════════════════
# 2. FIX THE WHATSAPP LINK
# ═══════════════════════════════════════════════════
old_details = re.search(r'elif data\.startswith\("det_prod:"\):.*?except Exception as e: print\(f"Details error: \{e\}"\)', c, re.DOTALL)

if old_details:
    new_details = '''elif data.startswith("det_prod:"):
        pid = data.split(":")[1]
        p = PRODUCTS[pid]
        
        # Send the link as plain text to guarantee it turns blue and clickable
        txt = f"📦 <b>{p['name']}</b>\\n💰 Price: ₹{p['price']}\\n\\n👇 <b>Tap the link below to view reviews on WhatsApp:</b>\\n{p['link']}"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back to Details", callback_data="shop_details"))
        
        try: 
            bot.edit_message_text(txt, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        except Exception as e: 
            print(f"Details error: {e}")'''
            
    c = c[:old_details.start()] + new_details + c[old_details.end():]
    print("✅ FIX 2: WhatsApp link is now plain text (forces clickable link).")
else:
    print("⚠️ Could not find det_prod block.")

# ═══════════════════════════════════════════════════
# 3. ENSURE CART BUTTONS FROM ADD/REMOVE CALL THE NEW FUNCTION
# ═══════════════════════════════════════════════════
# The add/rem logic already calls show_cart(uid, call.message.message_id), so it will now automatically use the new delete-and-send method.

ast.parse(c)
open(F, "w").write(c)
print("════ SURGICAL PATCH COMPLETE ════")
