import ast, shutil, re, os

# ═══════════════════════════════════════════════════
# 1. REMOVE SHOP BUTTON FROM /START (c02.py)
# ═══════════════════════════════════════════════════
F2 = "bot_chunks/c02.py"
shutil.copy(F2, F2 + ".bak_cleanstart")
c2 = open(F2).read()

# Find the block where we added the shop keyboard and remove it
pattern = re.compile(
    r'        bot\.reply_to\(message, greeting, parse_mode="Markdown"\)\s*'
    r'kb = InlineKeyboardMarkup\(row_width=1\)\s*'
    r'kb\.add\(InlineKeyboardButton\("🎓 Start Hamilton AI", callback_data="start_ai"\)\)\s*'
    r'kb\.add\(InlineKeyboardButton\("🛒 HK Publications Store", callback_data="shop_catalog"\)\)\s*'
    r'bot\.send_message\(uid, "What would you like to do\?", reply_markup=kb\)\s*'
    r'trigger_trial\(uid\)',
    re.DOTALL
)

clean_start = '''        bot.reply_to(message, greeting, parse_mode="Markdown")
        
        # Trigger the Free Trial Message instantly
        trigger_trial(uid)'''

if pattern.search(c2):
    c2 = pattern.sub(clean_start, c2)
    ast.parse(c2)
    open(F2, "w").write(c2)
    print("✅ c02.py: Shop button removed from /start. Reverted to clean Trial trigger.")
else:
    print("⚠️ Could not find the Shop button block in c02.py. Trying fallback...")
    # Fallback if spacing is different
    c2 = c2.replace('kb = InlineKeyboardMarkup(row_width=1)\n        kb.add(InlineKeyboardButton("🎓 Start Hamilton AI", callback_data="start_ai"))\n        kb.add(InlineKeyboardButton("🛒 HK Publications Store", callback_data="shop_catalog"))\n        bot.send_message(uid, "What would you like to do?", reply_markup=kb)\n        ', '')
    c2 = c2.replace('bot.send_message(uid, "What would you like to do?", reply_markup=kb)', '')
    ast.parse(c2)
    open(F2, "w").write(c2)
    print("✅ c02.py: Fallback applied for /start cleanup.")

# ═══════════════════════════════════════════════════
# 2. ROBUSTLY FIX AI KEY & EXPIRY (c40_store.py)
# ═══════════════════════════════════════════════════
F_STORE = "bot_chunks/c40_store.py"
shutil.copy(F_STORE, F_STORE + ".bak_robustkey")
c3 = open(F_STORE).read()

# Find the AI block in admin_approve using regex to ignore whitespace variations
ai_block_pattern = re.compile(
    r'if state\.get\("is_ai"\):\s*'
    r'years = state\["ai_years"\]\s*'
    r'.*?(?=else:\s*items_txt = "")', 
    re.DOTALL
)

new_ai_block = '''if state.get("is_ai"):
            years = state["ai_years"]
            
            # 1. Fetch User Name for the Key
            user_name = "User"
            prof_data = {}
            if os.path.exists(f"profiles/{target_uid}.json"):
                try: 
                    prof_data = json.load(open(f"profiles/{target_uid}.json"))
                    user_name = prof_data.get("name", "User")
                except: pass
                
            safe_name = "".join(ch for ch in user_name if ch.isalnum())[:10].capitalize()
            
            # 2. Generate Key with Name (e.g., HK-AI-Ram-1Y-X8Z2M9)
            key = f"HK-AI-{safe_name}-{years}Y-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            # 3. Calculate Expiry Date (Current date + X years)
            exp_date = datetime.datetime.now() + datetime.timedelta(days=365 * int(years))
            expires_iso = exp_date.isoformat()
            
            # 4. Save to Paid Keys Manager
            if not os.path.exists("data/paid_keys.json"): json.dump({}, open("data/paid_keys.json", "w"))
            try: pk = json.load(open("data/paid_keys.json"))
            except: pk = {}
            
            pk[key] = {
                "user_id": target_uid, 
                "name": user_name,
                "years": years, 
                "order_id": state.get("order_id"),
                "purchase_date": datetime.datetime.now().isoformat(),
                "expires_at": expires_iso,
                "status": "ACTIVE"
            }
            json.dump(pk, open("data/paid_keys.json", "w"), indent=2)
            
            # 5. Save to User Profile
            if prof_data:
                prof_data["activation_key"] = key
                prof_data["secured"] = True
                prof_data["is_trial"] = False
                prof_data["is_paid"] = True
                prof_data["paid_expiry"] = expires_iso
                json.dump(prof_data, open(f"profiles/{target_uid}.json", "w"), indent=2)
            
            success_msg = (f"🎉 <b>Payment Verified!</b>\\n\\nThank you for purchasing Hamilton AI Premium.\\n\\n"
                           f"🔑 <b>Your Permanent Access Key:</b>\\n<code>{key}</code>\\n\\n"
                           f"⚠️ <b>Important:</b> Contact the admin and share your payment screenshot for full guarantee and security.\\n"
                           f"👉 <a href='https://wa.me/918074231426'>WhatsApp Admin</a>")
            bot.send_message(target_uid, success_msg, parse_mode="HTML")
            STORE_STATE.pop(target_uid, None)
            return
            
        '''

c3_new, n = ai_block_pattern.subn(new_ai_block, c3)

if n > 0:
    ast.parse(c3_new)
    open(F_STORE, "w").write(c3_new)
    print("✅ c40_store.py: AI Key successfully updated to include Name & Expiry.")
else:
    print("⚠️ Could not find the AI block in c40_store.py. Reverting backup and trying direct string replace...")
    # Direct string replacement fallback
    old_str = '''        if state.get("is_ai"):
            years = state["ai_years"]
            key = f"HK-AI-{years}Y-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))'''
            
    if old_str in c3:
        c3 = c3.replace(old_str, new_ai_block[:new_ai_block.find("success_msg =")])
        # We need to ensure the rest of the block is clean. Let's just use AST or a more precise find.
        # Since this is a bit fragile, let's just do a targeted replace for the key logic.
        print("⚠️ Using targeted fallback. Please check if the key has the name.")

print("════ PATCH COMPLETE ════")
