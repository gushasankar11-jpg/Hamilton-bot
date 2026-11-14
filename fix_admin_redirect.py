import ast, shutil, re

FS = "bot_chunks/c03z_store.py"
shutil.copy(FS, FS + ".bak_adminredirect")
cs = open(FS).read()

# Bulletproof regex to find the start of the admin_show_pending function
pattern = re.compile(r'(def admin_show_pending\(call\):\s*import sys\s*auth = sys\.modules\.get\(\'__main__\'\)\.auth\s*session = auth\.get_session\(call\.message\.chat\.id\) if auth else None\s*if not session or session\["role"\] != "primary":\s*return bot\.answer_callback_query\(call\.id, "❌ Unauthorized", show_alert=True\))')

replacement = '''\1
        
    # REDIRECT DIRECTLY TO THE MANAGER LOGISTICS PANEL
    return show_manager_panel(call.message.chat.id)'''

new_cs, count = pattern.subn(replacement, cs)

if count > 0:
    ast.parse(new_cs)
    open(FS, "w").write(new_cs)
    print("✅ c03z_store.py: Admin Orders button will now redirect to the Manager Panel.")
else:
    print("⚠️ Regex failed. Forcing manual insertion...")
    # Fallback: find the function and inject the return statement right after the auth check
    idx = cs.find("def admin_show_pending(call):")
    if idx != -1:
        inject_idx = cs.find('return bot.answer_callback_query(call.id, "❌ Unauthorized", show_alert=True)', idx)
        if inject_idx != -1:
            end_of_line = cs.find('\n', inject_idx) + 1
            cs = cs[:end_of_line] + "    return show_manager_panel(call.message.chat.id)\n" + cs[end_of_line:]
            ast.parse(cs)
            open(FS, "w").write(cs)
            print("✅ Fallback successful. Redirect injected.")

print("════ PATCH COMPLETE ════")
