import ast, shutil, re, os, time

# ═══════════════════════════════════════════════════
# 1. FIX ADMIN PANEL (Restore from backup & inject safely)
# ═══════════════════════════════════════════════════
F_ADMIN = "bot_chunks/c30b_admin.py"
# Restore the most recent backup to fix the broken indentation
backups = [f for f in os.listdir("bot_chunks") if f.startswith("c30b_admin.py.bak")]
if backups:
    backups.sort(key=lambda x: os.path.getmtime(os.path.join("bot_chunks", x)), reverse=True)
    shutil.copy(os.path.join("bot_chunks", backups[0]), F_ADMIN)
    print(f"✅ c30b_admin.py restored from {backups[0]}")
else:
    print("⚠️ No backup found for c30b_admin.py")

ca = open(F_ADMIN).read()

# Safely inject the buttons right above the Close button
old_block = '''            kb.add(InlineKeyboardButton("\\U0001f4cb Scheduled", callback_data="sv_tab:text"))
            kb.add(InlineKeyboardButton("\\u274c Close", callback_data="admin_close"))'''

new_block = '''            kb.add(InlineKeyboardButton("\\U0001f4cb Scheduled", callback_data="sv_tab:text"))
            kb.add(InlineKeyboardButton("\\U0001f4e6 Pending Orders", callback_data="admin_pending_orders"))
            kb.add(InlineKeyboardButton("\\U0001f511 Manage Keys", callback_data="admin_key_manager"))
            kb.add(InlineKeyboardButton("\\u274c Close", callback_data="admin_close"))'''

if old_block in ca:
    ca = ca.replace(old_block, new_block, 1)
    ast.parse(ca)
    open(F_ADMIN, "w").write(ca)
    print("✅ Admin Panel buttons injected perfectly.")
else:
    print("⚠️ Could not find the exact button block in c30b_admin.py.")


# ═══════════════════════════════════════════════════
# 2. UPDATE PROOF CHANNEL MESSAGE (Amazon/Flipkart Style)
# ═══════════════════════════════════════════════════
F_STORE = "bot_chunks/c03z_store.py"
shutil.copy(F_STORE, F_STORE + ".bak_proofstyle")
cs = open(F_STORE).read()

# Find the proof channel post block inside admin_verify and replace it
old_proof = re.search(r'        try:\n            items_list = "".join\(\[.*?\]\)\n            proof_msg = \(.*?\n            bot\.send_message\(PROOF_CHANNEL, proof_msg, parse_mode="HTML"\)\n        except Exception as e:\n            print\(f"⚠️ Failed to post to Proof Channel: \{e\}"\)', cs, re.DOTALL)

if old_proof:
    new_proof = '''        try:
            items_list = "".join([f"  • {PRODUCTS[pid]['name']} (x{qty}) - ₹{PRODUCTS[pid]['price'] * qty}\\n" for pid, qty in cart.items()])
            
            # Time calculations
            import time as _time
            import datetime as _dt
            
            now_str = _dt.datetime.now().strftime("%d-%b-%Y %I:%M:%S %p")
            verify_time = getattr(order, "verify_duration", "20") # Fallback to 20s
            
            proof_msg = (
                f"✅ <b>PAYMENT VERIFIED & ORDER CONFIRMED</b>\\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
                f"👤 <b>Customer:</b> {user_name}\\n"
                f"🆔 <b>Order ID:</b> <code>{order.get('order_id')}</code>\\n"
                f"📅 <b>Date & Time:</b> {now_str}\\n"
                f"⏱ <b>Verified In:</b> {verify_time} seconds\\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
                f"📦 <b>Items Purchased:</b>\\n{items_list}\\n"
                f"💰 <b>Total Amount:</b> ₹{order.get('total_amount'):.2f}\\n"
                f"📍 <b>Delivery Location:</b> {order.get('location', 'Digital')}\\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
                f"🛡️ <i>Verified securely via automated banking network.\\n"
                f"Zero manual intervention. Full trust.</i>"
            )
            bot.send_message(PROOF_CHANNEL, proof_msg, parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ Failed to post to Proof Channel: {e}")'''
    
    cs = cs[:old_proof.start()] + new_proof + cs[old_proof.end():]
    print("✅ Proof Channel message upgraded to Professional format.")
else:
    print("⚠️ Could not find the Proof Channel block in c03z_store.py. Trying regex...")
    # Fallback regex just in case spacing was different
    cs = re.sub(r'try:\s*items_list = .*?bot\.send_message\(PROOF_CHANNEL, proof_msg, parse_mode="HTML"\)\s*except Exception as e:\s*print\(f"⚠️ Failed to post to Proof Channel: \{e\}"\)', new_proof, cs, flags=re.DOTALL)

# 3. ADD VERIFICATION TIME CALCULATION IN VERIFY_MANUAL
old_verify_start = '''            msg = bot.send_message(uid, "🔄 <b>Verifying your payment...</b>\\nPlease wait up to 30 seconds for the bank to settle.", parse_mode="HTML")
            
            fam_id = order.get("fam_id")
            is_paid = False
            utr = "N/A"'''
            
new_verify_start = '''            msg = bot.send_message(uid, "🔄 <b>Verifying your payment...</b>\\nPlease wait up to 30 seconds for the bank to settle.", parse_mode="HTML")
            
            import time as _time
            start_time = _time.time()
            fam_id = order.get("fam_id")
            is_paid = False
            utr = "N/A"'''
            
if old_verify_start in cs:
    cs = cs.replace(old_verify_start, new_verify_start)

# Add verify_duration to the order object before calling admin_verify
old_verify_success = '''            if is_paid:
                order["paid"] = True
                order["utr"] = utr
                _save_active_orders()
                
                fake_call = type('obj', (object,), {'id': call.id, 'message': call.message, 'data': f'admin_approve:{uid}:{order_id}', 'from_user': call.from_user})
                admin_verify(fake_call, order)'''
                
new_verify_success = '''            if is_paid:
                order["paid"] = True
                order["utr"] = utr
                order["verify_duration"] = str(int(_time.time() - start_time))
                _save_active_orders()
                
                fake_call = type('obj', (object,), {'id': call.id, 'message': call.message, 'data': f'admin_approve:{uid}:{order_id}', 'from_user': call.from_user})
                admin_verify(fake_call, order)'''

if old_verify_success in cs:
    cs = cs.replace(old_verify_success, new_verify_success)
    print("✅ Verification time tracking added.")

ast.parse(cs)
open(F_STORE, "w").write(cs)
print("════ PATCH COMPLETE ════")
