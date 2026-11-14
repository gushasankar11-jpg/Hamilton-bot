import threading, time
import admin_auth as auth

ACTIVE_PANELS = {} 

def register_panel(uid, message_id, view="main"):
    ACTIVE_PANELS[uid] = {"msg_id": message_id, "view": view}

def unregister_panel(uid):
    ACTIVE_PANELS.pop(uid, None)

def _live_loop():
    print("[live] Live panel updater started")
    while True:
        try:
            for uid, data in list(ACTIVE_PANELS.items()):
                if not auth.get_session(uid):
                    unregister_panel(uid)
                    continue
                    
                msg_id = data["msg_id"]
                view = data["view"]
                
                try:
                    from bot_chunks.c30b_admin import (
                        _snapshot_counters, build_devices_panel, 
                        build_subs_panel, build_watchlist_panel
                    )
                    role = auth.get_session(uid)["role"]
                    
                    # Rebuild the text AND the keyboard
                    if view == "devices":
                        new_text, new_kb = build_devices_panel(uid)
                    elif view == "subs":
                        new_text, new_kb = build_subs_panel(uid)
                    elif view == "watch":
                        new_text, new_kb = build_watchlist_panel(uid)
                    else:
                        snap = _snapshot_counters()
                        if role == "primary":
                            new_text = (
                                f"🛠 *HAMILTON ADMIN PANEL* `[PRIMARY]`\n\n"
                                f"📊 *LIVE SNAPSHOT* (Updates every 2s)\n"
                                f"  Today: *{snap['today_calls']}* calls · *{snap['today_users']}* users\n"
                                f"  Week:  *{snap['week_calls']}* calls · *{snap['week_users']}* users\n"
                                f"  Total: *{snap['total_calls']}* calls · *{snap['total_users']}* users\n\n"
                                f"🟢 *ONLINE NOW:* *{snap['online_count']}* users active in last 5 min\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━"
                            )
                            # Reconstruct main keyboard
                            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                            new_kb = InlineKeyboardMarkup(row_width=2)
                            new_kb.add(
                                InlineKeyboardButton("👥 Users", callback_data="admin_users:0"),
                                InlineKeyboardButton("🟢 Online Now", callback_data="admin_online"),
                            )
                            new_kb.add(
                                InlineKeyboardButton("🚫 Blocked", callback_data="admin_blocked"),
                                InlineKeyboardButton("⚠️ Watchlist", callback_data="admin_watch"),
                            )
                            new_kb.add(
                                InlineKeyboardButton("📈 Power Users", callback_data="admin_power"),
                                InlineKeyboardButton("📊 Weekly Chart", callback_data="admin_weekly"),
                            )
                            new_kb.add(
                                InlineKeyboardButton("📉 Exam Mix", callback_data="admin_exam_mix"),
                                InlineKeyboardButton("🎓 Level Mix", callback_data="admin_level_mix"),
                            )
                            new_kb.add(
                                InlineKeyboardButton("🔍 Search", callback_data="admin_search_hint"),
                                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                            )
                            new_kb.add(
                                InlineKeyboardButton("💬 Personal Msg", callback_data="admin_pmsg_hint"),
                                InlineKeyboardButton("📱 Devices", callback_data="admin_devices"),
                            )
                            new_kb.add(
                                InlineKeyboardButton("🆕 New Users", callback_data="admin_newusers"),
                                InlineKeyboardButton("🛡️ Sub-Admins", callback_data="admin_subs"),
                            )
                            new_kb.add(
                                InlineKeyboardButton("⏰ Scheduled", callback_data="admin_scheduled"),
                                InlineKeyboardButton("📤 Export CSV", callback_data="admin_export"),
                            )
                            new_kb.add(
                                InlineKeyboardButton("🔑 Generate Lock-in Code", callback_data="admin_lockin_btn"),
                            )
                            new_kb.add(InlineKeyboardButton("❌ Close", callback_data="admin_close"))
                        else:
                            new_text = "Read only..."
                            new_kb = None

                    # Edit message with the rebuilt keyboard
                    _b().edit_message_text(
                        chat_id=uid,
                        message_id=msg_id,
                        text=new_text,
                        parse_mode="Markdown",
                        reply_markup=new_kb
                    )
                    
                except Exception as e:
                    if "message is not modified" not in str(e).lower() and "message to edit not found" not in str(e).lower():
                        print(f"[live] edit fail: {e}")
                        unregister_panel(uid)
        except Exception as e:
            print(f"[live] loop error: {e}")
        time.sleep(2)

threading.Thread(target=_live_loop, daemon=True).start()
print("c30p_live_update: loaded.")
