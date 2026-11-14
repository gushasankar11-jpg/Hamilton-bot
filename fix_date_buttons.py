import ast, shutil, re

FS = "bot_chunks/c03z_store.py"
shutil.copy(FS, FS + ".bak_datefix")
cs = open(FS).read()

# 1. FIX THE LOCATION HANDLER TO GENERATE PROPER DATE BUTTONS
old_loc = re.search(r'    elif data\.startswith\("loc:"\):.*?(?=    elif data == "confirm_pay":)', cs, re.DOTALL)
if old_loc:
    new_loc = '''    elif data.startswith("loc:"):
        loc = data.split(":")[1]
        state = _get_cart(uid)
        state["location"] = loc
        
        # Use strict localized import to avoid the shadowing bug
        import datetime as _dt_fix
        
        today = _dt_fix.date.today()
        kb = InlineKeyboardMarkup(row_width=1)
        
        # Give options from Day 3 to Day 7 (5 options total)
        for i in range(3, 8):
            d = today + _dt_fix.timedelta(days=i)
            day_name = d.strftime("%A")
            
            if day_name == "Sunday":
                slot = "10 AM - 7 PM"
            else:
                slot = "Evening 7-9 PM"
                
            btn_text = f"{d.strftime('%d %b')} ({day_name}) - {slot}"
            cb_data = f"del_date:{d.strftime('%Y-%m-%d')} ({slot})"
            kb.add(InlineKeyboardButton(btn_text, callback_data=cb_data))
            
        kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="shop_buy"))
        try: 
            bot.edit_message_text("📅 <b>Select Delivery Date & Time:</b>\\n<i>(Minimum 3 days, Maximum 7 days)</i>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
        except: pass

    elif data.startswith("del_date:"):
        d_val = data.split(":", 1)[1]
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
print("✅ Date selection fixed: Day 3 to Day 7 buttons added with Sunday detection.")
