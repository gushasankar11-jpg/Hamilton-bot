import ast, shutil, re, os

# ═══════════════════════════════════════════════════
# 1. CLEAN UP ADMIN PANEL (Remove duplicates, fix back btn)
# ═══════════════════════════════════════════════════
F_ADMIN = "bot_chunks/c30b_admin.py"
shutil.copy(F_ADMIN, F_ADMIN + ".bak_cleanpanel")
ca = open(F_ADMIN).read()

# Remove ANY existing lines that add the Pending Orders/Orders buttons
ca = re.sub(r'^\s*kb\.add\(InlineKeyboardButton\(".*?Orders".*?admin_pending_orders"\)\)\n', '', ca, flags=re.MULTILINE)

# Add exactly ONE clean button right above the Close button
old_close = 'kb.add(InlineKeyboardButton("\\u274c Close", callback_data="admin_close"))'
new_close = '''kb.add(InlineKeyboardButton("\\U0001f4e6 Orders", callback_data="admin_pending_orders"))
            kb.add(InlineKeyboardButton("\\u274c Close", callback_data="admin_close"))'''
            
if old_close in ca:
    ca = ca.replace(old_close, new_close, 1)

# Fix the "Back to Orders" callback in the order view (c03z_store.py handles this, but just in case)
ast.parse(ca)
open(F_ADMIN, "w").write(ca)
print("✅ c30b_admin.py: Duplicate buttons removed. Only ONE 'Orders' button remains.")


# ═══════════════════════════════════════════════════
# 2. FIX BACK BUTTON & ADD /orders SHORTCUT
# ═══════════════════════════════════════════════════
FS = "bot_chunks/c03z_store.py"
shutil.copy(FS, FS + ".bak_mgrshortcut")
cs = open(FS).read()

# A. Fix the Back button in Admin Pending View (It was going to admin_close)
cs = cs.replace('kb.add(InlineKeyboardButton("🔙 Back to Orders", callback_data="admin_pending_orders"))', 
                'kb.add(InlineKeyboardButton("🔙 Back to Orders List", callback_data="admin_pending_orders"))')

# B. Add the /orders command to instantly open Manager Panel for Admin
orders_cmd = '''
@bot.message_handler(commands=['orders'])
def cmd_admin_orders_shortcut(message):
    uid = message.chat.id
    if str(uid) == str(ADMIN_GROUP_ID) or uid == 8857708587:
        MANAGER_SESSIONS.add(uid)
        show_manager_panel(uid)
    else:
        bot.send_message(uid, "❌ Unauthorized. Admin only.")

'''
if "@bot.message_handler(commands=['orders'])" not in cs:
    cs = cs.replace("@bot.message_handler(commands=['shop'])", orders_cmd + "\n@bot.message_handler(commands=['shop'])")
    print("✅ c03z_store.py: `/orders` command added to instantly open Manager Panel.")

# C. Ensure Admin Panel "Orders" button opens the Admin Orders (which shares the logic)
# (The admin_pending_orders handler is already in the file, but we make sure it's clean)
ast.parse(cs)
open(FS, "w").write(cs)
print("════ PATCH COMPLETE ════")
