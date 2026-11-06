# ==========================================================
# c30b_admin.py — Admin panel v2 (new format + full features)
# ==========================================================
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import admin_auth as auth

# ==========================================================
# S2b — Sub-admin read-only gate for graphs & actions
# ==========================================================
_GRAPH_CALLBACKS = {
     "admin_weekly", "admin_exam_mix", "admin_level_mix",
    "admin_export", "admin_hist", "admin_subadmins", "admin_reverify",
    "admin_broadcast", "admin_lockin_btn", "admin_keys",
}


def _sub_gate(call):
    """Returns True if user is allowed. Sends toast if blocked."""
    sess = auth.get_session(call.from_user.id)
    if not sess:
        try: bot.answer_callback_query(call.id, "Session expired")
        except Exception: pass
        return False
    if sess.get("role") == "primary":
        return True
    cb = getattr(call, "data", "") or ""
    if cb in _GRAPH_CALLBACKS or cb.startswith("admin_hist") or cb.startswith("admin_sub") or cb.startswith("admin_reverify"):
        try:
            bot.answer_callback_query(call.id, "\u26d4 Read-only: not available")
        except Exception: pass
        return False
    return True



def _list_all_users():
    users = []
    if not os.path.isdir(PROFILE_DIR):
        return users
    for fname in os.listdir(PROFILE_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            uid = int(fname.replace(".json", ""))
        except ValueError:
            continue
        try:
            with open(os.path.join(PROFILE_DIR, fname)) as f:
                p = json.load(f)
        except Exception:
            continue
        if not p.get("secured"):
            continue
        users.append((uid, p))
    users.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
    return users


def _days_since(iso_str):
    try:
        return (datetime.now() - datetime.fromisoformat(iso_str)).days
    except Exception:
        return "?"


def _snapshot_counters():
    """Compute today / week / total counters + online now."""
    today = datetime.now().date()
    week_ago = datetime.now() - timedelta(days=7)
    today_users = 0
    week_users_set = set()
    total_users = 0
    online_count = 0
    online_uids = []
    today_calls = 0
    total_calls = 0
    week_calls = 0
    try:
        with open("data/lifetime_stats.json") as _f:
            _s = json.load(_f)
            total_calls = _s.get("total_calls", 0)
            today_calls = _s.get("daily_calls", {}).get(today.isoformat(), 0)
    except Exception:
        pass
    now = datetime.now()
    for uid, p in _list_all_users():
        total_users += 1
        last_seen = p.get("last_seen")
        if last_seen:
            try:
                dt = datetime.fromisoformat(last_seen)
                if dt.date() == today:
                    today_users += 1
                if dt >= week_ago:
                    week_users_set.add(uid)
                if (now - dt) < timedelta(minutes=5):
                    online_count += 1
                    online_uids.append((uid, p))
            except Exception:
                pass
    return {
        "today_calls": today_calls,
        "today_users": today_users,
        "week_calls": week_calls,
        "week_users": len(week_users_set),
        "total_calls": total_calls,
        "total_users": total_users,
        "online_count": online_count,
        "online_uids": online_uids,
    }



_STATS_MSGS = {}
_BTN_MSGS = {}
_ALL_PANEL_MSGS = {}

def _show_admin_panel(chat_id, page=0, message_id=None):
    session = auth.get_session(chat_id)
    if not session:
        # Delete everything tracked + panel caches
        _del = globals().get("delete_all_admin_msgs")
        if _del:
            try: _del(chat_id)
            except Exception: pass
        for _cn in ("_STATS_MSGS", "_BTN_MSGS", "_ALL_PANEL_MSGS"):
            _cache = globals().get(_cn)
            if _cache is not None:
                try:
                    _old = _cache.pop(chat_id, None)
                    if _old:
                        _olds = _old if isinstance(_old, (list, set, tuple)) else [_old]
                        for _m in _olds:
                            try: bot.delete_message(chat_id, _m)
                            except Exception: pass
                except Exception: pass
        # One brief notice, self-deletes in 8s
        try:
            _m = bot.send_message(chat_id, "\U0001f512 Session expired. Type the admin code to reopen.")
            import threading as _th_exp, time as _t_exp
            def _dn_exp():
                _t_exp.sleep(5)
                try: bot.delete_message(chat_id, _m.message_id)
                except Exception: pass
            _th_exp.Thread(target=_dn_exp, daemon=True).start()
        except Exception:
            pass
        return
    try:
        auth.touch_session(chat_id)
    except Exception:
        pass
    role = session["role"]
    try:
        auth.log_admin_device(chat_id, role)
    except Exception:
        pass
    snap = _snapshot_counters()
    if role == "primary":
        header = (
            "\U0001f6e0 *HAMILTON ADMIN PANEL* [PRIMARY]\n\n"
            "\U0001f4ca *LIVE SNAPSHOT* (updates every 2s)\n"
            f"  Today: *{snap['today_calls']}* calls \u00b7 *{snap['today_users']}* users\n"
            f"  Week:  *{snap['week_users']}* users\n"
            f"  Total: *{snap['total_calls']}* calls \u00b7 *{snap['total_users']}* users\n\n"
            f"\U0001f7e2 *ONLINE NOW:* *{snap['online_count']}* users\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("\U0001f465 Users", callback_data="admin_users:0"),
            InlineKeyboardButton("\U0001f7e2 Online Now", callback_data="admin_online"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f6ab Blocked", callback_data="admin_blocked"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f4c8 Power Users", callback_data="admin_power"),
            InlineKeyboardButton("\U0001f4ca Weekly Chart", callback_data="admin_weekly"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f4c9 Exam Mix", callback_data="admin_exam_mix"),
            InlineKeyboardButton("\U0001f393 Level Mix", callback_data="admin_level_mix"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f50d Search", callback_data="admin_search_hint"),
            InlineKeyboardButton("\U0001f4e2 Broadcast", callback_data="admin_broadcast"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f4ac Personal Msg", callback_data="admin_pmsg_hint"),
            InlineKeyboardButton("\U0001f4f1 Devices", callback_data="admin_devices"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f195 New Users", callback_data="admin_newusers"),
            InlineKeyboardButton("\U0001f4e4 Export CSV", callback_data="admin_export"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f511 Generate Lock-in Code", callback_data="admin_lockin_btn"),
        )
        kb.add(InlineKeyboardButton("\U0001f6e0 Admin", callback_data="admin_hist"))
        kb.add(InlineKeyboardButton("\U0001f6e1 Sub-Admin", callback_data="admin_subadmins"))
        kb.add(InlineKeyboardButton("\U0001f511 API Keys", callback_data="admin_keys"))
        kb.add(InlineKeyboardButton("\U0001f4cb Scheduled", callback_data="sv_tab:text"))
        kb.add(InlineKeyboardButton("\u274c Close", callback_data="admin_close"))
    else:
        header = (
            "\U0001f6e1 *HAMILTON ADMIN PANEL* [READ-ONLY]\n\n"
            "\U0001f4ca *LIVE SNAPSHOT* (updates every 2s)\n"
            f"  Today: *{snap['today_calls']}* calls \u00b7 *{snap['today_users']}* users\n"
            f"  Week:  *{snap['week_users']}* users\n"
            f"  Total: *{snap['total_calls']}* calls\n\n"
            f"\U0001f7e2 *ONLINE NOW:* *{snap['online_count']}* users\n\n"
            "\u26a0\ufe0f _Read-only_"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("\U0001f465 Users", callback_data="admin_users:0"),
            InlineKeyboardButton("\U0001f7e2 Online Now", callback_data="admin_online"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f4c8 Power Users", callback_data="admin_power"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f4ca Weekly Chart", callback_data="admin_weekly"),
            InlineKeyboardButton("\U0001f4c9 Exam Mix", callback_data="admin_exam_mix"),
        )
        kb.add(
            InlineKeyboardButton("\U0001f393 Level Mix", callback_data="admin_level_mix"),
            InlineKeyboardButton("\U0001f50d Search", callback_data="admin_search_hint"),
        )
        kb.add(InlineKeyboardButton("\u274c Close", callback_data="admin_close"))
        # S2b: leave ALL buttons visible for sub-admin (handlers gate them)
    # _sub_admin_keyboard_strip: strip primary-only buttons from sub-admin view
    try:
        if role != "primary":
            _primary_only_cbs = {
                "admin_hist", "admin_subadmins", "admin_keys",
                "admin_reverify", "admin_broadcast", "admin_lockin_btn",
                "admin_weekly", "admin_exam_mix",
                "admin_level_mix", "admin_export"
            }
            _new_rows = []
            for _row in kb.keyboard:
                _keep = [b for b in _row if (getattr(b, 'callback_data', '') or '') not in _primary_only_cbs]
                if _keep:
                    _new_rows.append(_keep)
            kb.keyboard = _new_rows
    except Exception as _e:
        print(f"[sub-keyboard-strip] {_e}")

    stats_id = _STATS_MSGS.get(chat_id)
    stats_ok = False
    if stats_id:
        try:
            bot.edit_message_text(
                header, chat_id=chat_id, message_id=stats_id,
                parse_mode="Markdown", reply_markup=None
            )
            stats_ok = True
        except Exception as _e:
            if "message is not modified" in str(_e).lower():
                stats_ok = True
            else:
                print(f"[panel-stats-edit-fail] {_e}")
                stats_id = None
    if not stats_ok:
        try:
            m = bot.send_message(chat_id, header, parse_mode="Markdown")
            stats_id = m.message_id
            _STATS_MSGS[chat_id] = stats_id
            _ALL_PANEL_MSGS.setdefault(chat_id, set()).add(stats_id)
            _trk = globals().get("track_admin_msg")
            if _trk:
                try: _trk(chat_id, stats_id)
                except Exception: pass
        except Exception as _e:
            print(f"[panel-stats-send-fail] {_e}")
            return
    btn_id = _BTN_MSGS.get(chat_id)
    btn_ok = False
    if btn_id:
        try:
            bot.edit_message_text(
                "\u2699\ufe0f *Controls*",
                chat_id=chat_id, message_id=btn_id,
                parse_mode="Markdown", reply_markup=kb
            )
            btn_ok = True
        except Exception as _e:
            if "message is not modified" in str(_e).lower():
                btn_ok = True
            else:
                print(f"[panel-btn-edit-fail] {_e}")
                btn_id = None
    if not btn_ok:
        try:
            m2 = bot.send_message(chat_id, "\u2699\ufe0f *Controls*", reply_markup=kb)
            btn_id = m2.message_id
            _BTN_MSGS[chat_id] = btn_id
            _ALL_PANEL_MSGS.setdefault(chat_id, set()).add(btn_id)
            _trk = globals().get("track_admin_msg")
            if _trk:
                try: _trk(chat_id, btn_id)
                except Exception: pass
        except Exception as _e:
            print(f"[panel-btn-send-fail] {_e}")
            return
    if message_id and message_id not in (stats_id, btn_id):
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass
    # Delete all tracked msgs not in {stats_id, btn_id}
    try:
        _all = _ALL_PANEL_MSGS.get(chat_id, set())
        for _old in list(_all):
            if _old not in (stats_id, btn_id):
                try:
                    bot.delete_message(chat_id, _old)
                except Exception:
                    pass
        _ALL_PANEL_MSGS[chat_id] = {stats_id, btn_id}
    except Exception:
        pass
    _reg = globals().get("register_panel")
    if _reg:
        try:
            _reg(chat_id, stats_id, header)
        except Exception as _e:
            print(f"[panel-reg-fail] {_e}")



def _show_sub_admin_panel(uid):
    _show_admin_panel(uid)


# ==========================================================
# USERS LIST
# ==========================================================
def _build_user_list_keyboard(users, page=0, per_page=8):
    kb = InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    end = start + per_page
    for uid, p in users[start:end]:
        name = (p.get("name") or "?")[:18]
        hku = p.get("hku_id") or "—"
        st = p.get("strikes_total", 0)
        kb.add(InlineKeyboardButton(
            f"👤 {hku} · {name} · ⚠️{st}",
            callback_data=f"admin_profile:{uid}"
        ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users:{page-1}"))
    if end < len(users):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_users:{page+1}"))
    if nav:
        kb.row(*nav)
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    return kb


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_users:"))
def _cb_users(call):
    uid = call.message.chat.id
    session = auth.get_session(uid)
    if not session:
        return
    try:
        page = int(call.data.split(":")[1])
    except Exception:
        page = 0
    users = _list_all_users()
    if not users:
        text = "👥 *Users*\n\n_No users registered yet._"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    else:
        role = session["role"]
        text = (f"👥 *Users — Page {page+1}*\n"
                f"Total: *{len(users)}*\n"
                f"_{'Full access' if role == 'primary' else 'Read-only'}_")
        kb = _build_user_list_keyboard(users, page)
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id,
                               reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")


# ==========================================================
# USER DETAIL VIEW
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_view:"))
def _cb_view_user(call):
    uid = call.message.chat.id
    session = auth.get_session(uid)
    if not session:
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    p = load_profile(target)
    if not p:
        bot.answer_callback_query(call.id, "Not found")
        return

    name = (p.get("name") or "Unknown")[:40]
    hku = p.get("hku_id") or "—"
    phone = p.get("phone", "—")
    days = _days_since(p.get("created_at", ""))
    last_seen = p.get("last_seen", "never")
    if last_seen and last_seen != "never":
        try:
            ls_dt = datetime.fromisoformat(last_seen)
            mins_ago = int((datetime.now() - ls_dt).total_seconds() // 60)
            if mins_ago < 60:
                last_seen = f"{mins_ago} min ago"
            elif mins_ago < 1440:
                last_seen = f"{mins_ago // 60} hr ago"
            else:
                last_seen = f"{mins_ago // 1440} days ago"
        except Exception:
            pass

    text = (
        f"👤 *{name}*\n"
        f"🆔 `{hku}`\n"
        f"📱 UID `{target}`\n"
        f"📞 Phone: `{phone}`\n"
        f"📅 Joined {days} days ago\n"
        f"🎓 Level: {p.get('level', '—')}\n"
        f"📚 Exams: {', '.join(p.get('exams', [])) or '—'}\n"
        f"👀 Last active: {last_seen}\n\n"
        f"📊 *Usage*\n"
        f"  • Strikes total: *{p.get('strikes_total', 0)}*\n"
        f"  • Blocks: *{p.get('blocks_total', 0)}*\n"
        f"  • API calls: *{p.get('api_calls_total', 0)}*\n"
    )

    kb = InlineKeyboardMarkup(row_width=2)
    is_blocked = bool(p.get("behavior", {}).get("blocked_until"))
    if session["role"] == "primary":
        kb.add(
            InlineKeyboardButton("💬 Message", callback_data=f"admin_pmsg_user:{target}"),
            InlineKeyboardButton("✏️ Edit Name", callback_data=f"admin_edit_name:{target}"),
        )
        kb.add(
            InlineKeyboardButton("🗑 Delete", callback_data=f"admin_del_prompt:{target}"),
            InlineKeyboardButton("⚠️ Watch", callback_data=f"user_watch:{target}"),
        )
        if is_blocked:
            kb.add(InlineKeyboardButton("🔓 Unblock Now", callback_data=f"user_unblock:{target}"))
        else:
            kb.add(InlineKeyboardButton("🚫 Block User", callback_data=f"user_block:{target}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))

    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id,
                               reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")


# ==========================================================
# ONLINE NOW
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "admin_online")
def _cb_online(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    snap = _snapshot_counters()
    if snap["online_count"] == 0:
        text = "🟢 *Online Now*\n\n_No users active in last 5 minutes._"
    else:
        text = f"🟢 *Online Now — {snap['online_count']} users*\n\n"
        for o_uid, p in snap["online_uids"][:30]:
            name = (p.get("name") or "?")[:20]
            hku = p.get("hku_id") or "—"
            text += f"• `{hku}` {name}  (`{o_uid}`)\n"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id,
                               reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")


# ==========================================================
# DEVICES — show admin login history + last activity per user
# ==========================================================
def build_devices_panel(uid):
    entries = auth.list_admin_devices(40)
    text = "📱 *DEVICES & ACTIVITY*\n\nSelect a device to view details."
    kb = InlineKeyboardMarkup(row_width=1)
    
    for i, e in enumerate(entries[-10:]):
        ts = e.get("ts", "")[:16].replace("T", " ")
        role = e.get("role", "?")
        cid = e.get("chat_id", "?")
        kb.add(InlineKeyboardButton(f"📱 {cid} ({role}) - {ts}", callback_data=f"noop"))
        
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    return text, kb

@bot.callback_query_handler(func=lambda c: c.data == "admin_devices")
def _cb_devices(call):
    uid = call.message.chat.id
    if not auth.get_session(uid): return
    text, kb = build_devices_panel(uid)
    
    # Tell live tracker to update this panel
    try:
        _reg_x = globals().get("register_panel")
        if _reg_x: _reg_x(uid, call.message.message_id, "devices")
    except Exception: pass
    
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")


# ==========================================================
# OTHER PANELS (blocked, watchlist, power, weekly, mixes, etc.)
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "admin_blocked")
def _cb_blocked(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    blocked = []
    for u_id, p in _list_all_users():
        beh = p.get("behavior", {})
        if beh.get("blocked_until"):
            blocked.append((u_id, p))
    text = "🚫 *Blocked Users*\n\n"
    if not blocked:
        text += "_No users currently blocked._"
    else:
        for u_id, p in blocked:
            beh = p.get("behavior", {})
            name = (p.get("name") or "?")[:15]
            text += f"• {name} (`{u_id}`)\n  Until: {beh.get('blocked_until', '')[:16]}\n"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id,
                               reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")


def build_watchlist_panel(uid):
    users = sorted(_list_all_users(), key=lambda x: x[1].get("strikes_total", 0), reverse=True)
    text = "⚠️ *Watchlist (top strikes)*\n\nSelect a user to manage:"
    kb = InlineKeyboardMarkup(row_width=1)
    for u_id, p in users[:10]:
        if p.get("strikes_total", 0) == 0:
            break
        name = (p.get("name") or "?")[:15]
        kb.add(InlineKeyboardButton(f"👤 {name} ({p.get('strikes_total')} strikes)", callback_data=f"admin_profile:{u_id}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    return text, kb

@bot.callback_query_handler(func=lambda c: c.data == "admin_watch")
def _cb_watch(call):
    uid = call.message.chat.id
    if not auth.get_session(uid): return
    text, kb = build_watchlist_panel(uid)
    
    try:
        _reg = globals().get("register_panel")
        if _reg: _reg(uid, call.message.message_id, "watch")
    except Exception: pass
    
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data == "admin_power")
def _cb_power(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess:
        return
    role = sess.get("role", "primary")
    _all = _list_all_users()
    _sorted = sorted(_all, key=lambda x: x[1].get("api_calls_total", 0), reverse=True)[:30]
    _lines = ["\U0001f4c8 *POWER USERS*", ""]
    if role == "sub":
        _lines[0] = "\U0001f4c8 *POWER USERS* (read-only)"
    _lines.append(f"*Top {len(_sorted)} by API calls:*")
    _lines.append("")
    for _idx, (_puid, _pup) in enumerate(_sorted, 1):
        _nm = (_pup.get("name") or "?")[:18]
        _calls = _pup.get("api_calls_total", 0)
        _hku = _pup.get("hku_id") or "\u2014"
        _lines.append(f"{_idx}. {_nm} \u00b7 `{_hku}` \u00b7 *{_calls}* calls")
    if role == "primary":
        _lines.append("")
        _lines.append("_Graphs coming soon._")
    _text = "\n".join(_lines)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back"))
    try:
        bot.edit_message_text(_text[:4000], chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, _text[:4000], reply_markup=kb, parse_mode="Markdown")
        except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data in ("admin_weekly", "admin_exam_mix", "admin_level_mix", "admin_export"))
def _cb_stub(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    msg = {
        "admin_weekly": "📊 *Weekly Chart* — coming in Session 5",
        "admin_exam_mix": "📉 *Exam Mix* — coming in Session 6",
        "admin_level_mix": "🎓 *Level Mix* — coming in Session 6",
        "admin_export": "📤 *Export CSV* — coming in Session 6",
    }.get(call.data, "Coming soon")
    bot.answer_callback_query(call.id, msg)


@bot.callback_query_handler(func=lambda c: c.data == "admin_back")
def _cb_back(call):
    _show_admin_panel(call.message.chat.id, page=0,
                      message_id=call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data == "admin_close")
def _cb_admin_close(call):
    uid = call.from_user.id
    import sys
    for _mn, _mo in sys.modules.items():
        if hasattr(_mo, "TWO_WAY_CHAT"):
            to_remove = [k for k, v in _mo.TWO_WAY_CHAT.items() if v.get("admin_uid") == uid]
            for t in to_remove: 
                _mo.TWO_WAY_CHAT.pop(t, None)
                try: bot.send_message(t, "🔒 The admin has closed this chat session.")
                except: pass
        if hasattr(_mo, "PENDING_ADMIN_FLOW"):
            _mo.PENDING_ADMIN_FLOW.pop(uid, None)
    uid = call.from_user.id
    import sys
    for _mn, _mo in sys.modules.items():
        if hasattr(_mo, "TWO_WAY_CHAT"):
            to_remove = [k for k, v in _mo.TWO_WAY_CHAT.items() if v.get("admin_uid") == uid]
            for t in to_remove: 
                _mo.TWO_WAY_CHAT.pop(t, None)
                try: bot.send_message(t, "🔒 The admin has closed this chat session.")
                except: pass
        if hasattr(_mo, "PENDING_ADMIN_FLOW"):
            _mo.PENDING_ADMIN_FLOW.pop(uid, None)
    uid = call.from_user.id
    try:
        bot.answer_callback_query(call.id, "Closing...")
    except Exception:
        pass
        
    # --- CLOSE ACTIVE TWO-WAY CHATS ---
    import sys as _sys_close
    _closed_targets = []
    for _mn, _mo in _sys_close.modules.items():
        # Clear admin pending input flow
        if hasattr(_mo, "PENDING_ADMIN_FLOW"):
            if _mo.PENDING_ADMIN_FLOW.pop(uid, None):
                print(f"[admin_close] Cleared PENDING_ADMIN_FLOW for {uid}")
        
        # Clear TWO_WAY_CHAT where this admin is the one chatting
        if hasattr(_mo, "TWO_WAY_CHAT"):
            to_remove = []
            for target_uid, data in _mo.TWO_WAY_CHAT.items():
                if data.get("admin_uid") == uid:
                    to_remove.append(target_uid)
            for t in to_remove:
                _mo.TWO_WAY_CHAT.pop(t, None)
                _closed_targets.append(t)
    
    # Notify the users that the chat was closed by the admin
    for t in _closed_targets:
        try:
            bot.send_message(t, "🔒 The admin has closed this chat session. You can continue using the bot normally.")
        except Exception as e:
            print(f"[admin_close] failed to notify {t}: {e}")

    deleted = 0
    # 1. Delete every tracked message
    _del = globals().get("delete_all_admin_msgs")
    if _del:
        try:
            deleted, _ = _del(uid)
        except Exception as e:
            print(f"[close] del err: {e}")
    # 2. Directly delete stats + btn cached messages (in case tracking missed)
    for cache_name in ("_STATS_MSGS", "_BTN_MSGS"):
        cache = globals().get(cache_name)
        if cache and uid in cache:
            try:
                mid = cache.pop(uid)
                bot.delete_message(uid, mid)
                deleted += 1
            except Exception as e:
                print(f"[close] {cache_name} del err: {e}")
    # 3. Delete _ALL_PANEL_MSGS orphans
    _all = globals().get("_ALL_PANEL_MSGS")
    if _all and uid in _all:
        for mid in list(_all.get(uid, set())):
            try:
                bot.delete_message(uid, mid)
                deleted += 1
            except Exception:
                pass
        try: _all.pop(uid, None)
        except Exception: pass
    # 4. Clear session
    try:
        auth._SESSIONS.pop(uid, None)
    except Exception:
        pass
    # 5. Clear tracking list
    _trk = globals().get("_ADMIN_MSGS")
    if _trk and uid in _trk:
        try: _trk[uid] = []
        except Exception: pass
    # 6. Unregister panel
    try:
        _unreg = globals().get("unregister_panel")
        if _unreg: _unreg(uid)
    except Exception: pass
    print(f"[close] {uid} deleted={deleted}")
    # 7. Confirmation (self-deletes in 20s)
    try:
        _role_c = ((auth.get_session(uid) or {}).get("role") if hasattr(auth, "get_session") else None)
        _role_c = _role_c or "primary"
        _label = "Sub-admin panel closed" if _role_c == "sub" else "Admin mode closed"
        m = bot.send_message(uid, f"\U0001f44b {_label}. {deleted} messages cleared.")
        import threading as _th_cl, time as _t_cl
        def _dn_cl():
            _t_cl.sleep(5)
            try: bot.delete_message(uid, m.message_id)
            except Exception: pass
        _th_cl.Thread(target=_dn_cl, daemon=True).start()
    except Exception as e:
        print(f"[close] confirm err: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "admin_search_hint")
def _cb_search_hint(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    safe_send(uid, "🔍 Use `/find <name or UID>` to search.")


# ==========================================================
# DELETE FLOW
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_del_prompt:"))
def _cb_del_prompt(call):
    uid = call.message.chat.id
    session = auth.get_session(uid)
    if not session or session["role"] != "primary":
        bot.answer_callback_query(call.id, "Read-only access")
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    p = load_profile(target)
    if not p:
        bot.answer_callback_query(call.id, "User not found")
        return
    name = (p.get("name") or "Unknown")[:30]
    text = (
        f"🗑 *DELETE REQUEST*\n\n"
        f"👤 {name}\n"
        f"📱 UID `{target}`\n"
        f"⚠️ Strikes: {p.get('strikes_total', 0)} · Blocks: {p.get('blocks_total', 0)}\n\n"
        f"Type your *privacy code* to confirm deletion."
    )
    for mod_name, mod in __import__("sys").modules.items():
        if hasattr(mod, "PENDING_ADMIN_FLOW"):
            mod.PENDING_ADMIN_FLOW[uid] = {
                "action": "confirm_delete",
                "data": {"target": target},
                "at": __import__("time").time(),
            }
            break
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="admin_close"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id,
                               reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")


# ==========================================================
# FIND
# ==========================================================
@bot.message_handler(commands=['find'])
def _cmd_find(message):
    uid = message.chat.id
    if not auth.get_session(uid):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: `/find <name or UID>`", parse_mode="Markdown")
        return
    q = parts[1].strip().lower()
    users = _list_all_users()
    matches = [(u, p) for u, p in users
               if q in (p.get("name") or "").lower() or q in str(u)]
    if not matches:
        bot.reply_to(message, f"❌ No matches for `{q}`", parse_mode="Markdown")
        return
    text = f"🔍 *{len(matches)} match(es)*\n\n"
    kb = InlineKeyboardMarkup(row_width=1)
    for u, p in matches[:20]:
        name = (p.get("name") or "?")[:18]
        hku = p.get("hku_id") or "—"
        kb.add(InlineKeyboardButton(f"→ {hku} · {name}", callback_data=f"admin_profile:{u}"))
    kb.add(InlineKeyboardButton("❌ Close", callback_data="admin_close"))
    bot.reply_to(message, text, reply_markup=kb, parse_mode="Markdown")



@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_close_chat:"))
def _cb_admin_close_chat(call):
    uid = call.from_user.id
    try:
        target_uid = int(call.data.split(":")[1])
    except:
        return
        
    import sys as _sys_close
    for _mn, _mo in _sys_close.modules.items():
        if hasattr(_mo, "TWO_WAY_CHAT"):
            if target_uid in _mo.TWO_WAY_CHAT:
                _mo.TWO_WAY_CHAT.pop(target_uid, None)
        if hasattr(_mo, "PENDING_ADMIN_FLOW"):
            if uid in _mo.PENDING_ADMIN_FLOW:
                _mo.PENDING_ADMIN_FLOW.pop(uid, None)

    try:
        bot.answer_callback_query(call.id, "Chat Closed")
        bot.edit_message_text("🔒 *Chat closed with user.*", chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except:
        pass
        
    try:
        bot.send_message(target_uid, "🔒 The admin has closed this chat session. You can now continue using the bot normally.")
    except:
        pass


print("c30b_admin: loaded (panel v2).")

@bot.callback_query_handler(func=lambda c: c.data == "admin_pmsg_hint")
def _cb_pmsg_list(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    users = _list_all_users()[:8]
    kb = InlineKeyboardMarkup(row_width=1)
    for u_id, p in users:
        name = (p.get("name") or "?")[:18]
        hku = p.get("hku_id") or "—"
        kb.add(InlineKeyboardButton(
            f"💬 {hku} · {name}",
            callback_data=f"admin_pmsg_user:{u_id}"
        ))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    try:
        bot.edit_message_text("💬 *Select user to message:*",
                               chat_id=uid, message_id=call.message.message_id,
                               reply_markup=kb, parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, "💬 Select user:", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pmsg_user:"))
def _cb_pmsg_user(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    # Block self-chat
    if target == uid:
        safe_send(uid, "❌ *Cannot message yourself.*\nThis would create a loop.")
        return
    # Set pending state so c09 catches next text as message
    for mod_name, mod in __import__("sys").modules.items():
        if hasattr(mod, "PENDING_ADMIN_FLOW"):
            mod.PENDING_ADMIN_FLOW[uid] = {
                "action": "personal_text",
                "data": {"target_uid": target},
                "at": __import__("time").time(),
            }
            break
    p = load_profile(target) or {}
    safe_send(uid,
        f"📩 *Message to {p.get('name', '?')}*\n\nType your message now:",
        parse_mode="Markdown")


# ---- Admin Block User ----
@bot.callback_query_handler(func=lambda c: c.data.startswith("user_block:"))
def _cb_user_block(call):
    uid = call.message.chat.id
    session = auth.get_session(uid)
    if not session or session["role"] != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("1 hour", callback_data=f"user_block_do:{target}:60"),
        InlineKeyboardButton("6 hours", callback_data=f"user_block_do:{target}:360"),
        InlineKeyboardButton("24 hours", callback_data=f"user_block_do:{target}:1440"),
    )
    kb.add(
        InlineKeyboardButton("7 days", callback_data=f"user_block_do:{target}:10080"),
        InlineKeyboardButton("30 days", callback_data=f"user_block_do:{target}:43200"),
    )
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="admin_back"))
    try:
        bot.edit_message_text("🚫 *Block User for how long?*",
                               chat_id=uid, message_id=call.message.message_id,
                               reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("user_block_do:"))
def _cb_user_block_do(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    parts = call.data.split(":")
    try:
        target = int(parts[1])
        minutes = int(parts[2])
    except Exception:
        return
    p = load_profile(target)
    if not p:
        bot.answer_callback_query(call.id, "User not found")
        return
    p.setdefault("behavior", {})
    from datetime import datetime, timedelta
    until = datetime.now() + timedelta(minutes=minutes)
    p["behavior"]["blocked_until"] = until.isoformat()
    p["behavior"]["blocked_by"] = "admin"
    p["behavior"]["block_reason"] = "blocked by admin for behaviour"
    p["blocks_total"] = p.get("blocks_total", 0) + 1
    p["last_block_at"] = datetime.now().isoformat()
    save_profile(target, p)
    # Message the user
    try:
        safe_send(target,
            f"🚫 *Blocked by Admin*\n\n"
            f"You have been blocked for *{minutes} minutes* due to behaviour.\n\n"
            f"Contact admin to unblock.",
            parse_mode="Markdown")
    except Exception:
        pass
    bot.answer_callback_query(call.id, f"Blocked {target} for {minutes}min")
    _cb_view_user(call)


# ---- Admin Unblock User ----
@bot.callback_query_handler(func=lambda c: c.data.startswith("user_unblock:"))
def _cb_user_unblock(call):
    uid = call.message.chat.id
    session = auth.get_session(uid)
    if not session or session["role"] != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    p = load_profile(target)
    if p:
        p.setdefault("behavior", {})
        p["behavior"]["blocked_until"] = None
        p["behavior"]["blocked_by"] = None
        p["behavior"]["block_reason"] = None
        p["behavior"]["strikes"] = 0
        save_profile(target, p)
        try:
            safe_send(target,
                "🔓 *Unblocked by Admin*\n\nYou can now message the bot again. Welcome back!",
                parse_mode="Markdown")
        except Exception:
            pass
    bot.answer_callback_query(call.id, f"Unblocked {target}")
    _cb_view_user(call)



# ==========================================================
# NEW USERS PAGE (Phase 1)
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "admin_newusers")
def _cb_newusers(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    new_users = [(u, p) for u, p in _list_all_users() if not p.get("hku_id")]
    if not new_users:
        text = "\U0001f195 *New Users*\n\n_No pending registrations._"
        kb = InlineKeyboardMarkup()
    else:
        text = f"\U0001f195 *New Users* \u2014 {len(new_users)} pending"
        kb = InlineKeyboardMarkup(row_width=1)
        for u_id, p in new_users[:20]:
            nm = p.get("name") or "?"
            ct = (p.get("created_at") or "")[:16]
            kb.add(InlineKeyboardButton(
                f"\u23f3 {nm} \u00b7 {ct}",
                callback_data=f"admin_newuser_view:{u_id}"
            ))
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_newuser_view:"))
def _cb_newuser_view(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    target = int(call.data.split(":")[1])
    p = load_profile(target)
    if not p:
        bot.answer_callback_query(call.id, "User not found")
        return
    name = p.get("name") or "?"
    inst = p.get("institute") or "?"
    step = p.get("onboarding_step") or "?"
    created = (p.get("created_at") or "")[:16]
    strikes = p.get("name_strikes", 0)
    no_key = p.get("no_key_attempts", 0)
    hku = p.get("hku_id") or "_Not allotted_"
    text = (
        f"\U0001f195 *New User*\n\n"
        f"Name: {name}\n"
        f"Institute: {inst}\n"
        f"Step: `{step}`\n"
        f"Started: {created}\n"
        f"Name strikes: {strikes}\n"
        f"No-key tries: {no_key}\n"
        f"UID: {hku}"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    if role == "primary":
        if not p.get("hku_id"):
            kb.add(InlineKeyboardButton("\U0001f194 Allot UID", callback_data=f"admin_allot_uid:{target}"))
        kb.add(InlineKeyboardButton("\U0001f4e8 Send Reminder", callback_data=f"admin_reminder:{target}"))
        if strikes > 0 or no_key > 0:
            kb.add(InlineKeyboardButton("\U0001f513 Clear Name Lock", callback_data=f"admin_clear_namelock:{target}"))
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_newusers"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_allot_uid:"))
def _cb_allot_uid(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "\u26d4 Read-only")
        return
    target = int(call.data.split(":")[1])
    p = load_profile(target)
    if not p:
        return
    if p.get("hku_id"):
        bot.answer_callback_query(call.id, f"Already {p['hku_id']}")
        return
    try:
        new_hku = allocate_user_id(target)
        p["hku_id"] = new_hku
        save_profile(target, p)
        bot.answer_callback_query(call.id, f"Allotted {new_hku}")
        _cb_newuser_view(call)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Failed: {str(e)[:50]}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_reminder:"))
def _cb_reminder(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "\u26d4 Read-only")
        return
    target = int(call.data.split(":")[1])
    try:
        safe_send(target, "\U0001f44b Please complete your Hamilton registration by typing /start.")
        bot.answer_callback_query(call.id, "Reminder sent")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Failed: {str(e)[:50]}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_clear_namelock:"))
def _cb_clear_namelock(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "\u26d4 Read-only")
        return
    target = int(call.data.split(":")[1])
    p = load_profile(target)
    if not p:
        return
    p["name_strikes"] = 0
    p["no_key_attempts"] = 0
    p.setdefault("behavior", {})
    p["behavior"]["strikes"] = 0
    p["behavior"]["blocked_until"] = None
    save_profile(target, p)
    bot.answer_callback_query(call.id, "Lock cleared")
    _cb_newuser_view(call)



# ==========================================================
# EDIT NAME — handlers (Phase 2A)
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_edit_name:"))
def _cb_edit_name(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "Read-only access")
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        bot.answer_callback_query(call.id, "Bad target")
        return
    p = load_profile(target)
    if not p:
        bot.answer_callback_query(call.id, "User not found")
        return
    bot.answer_callback_query(call.id, "Type new name below")
    old_name = p.get("name", "?")
    msg = bot.send_message(
        uid,
        f"Edit Name for `{target}`\n\nCurrent: *{old_name}*\n\nSend the new name:",
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, _cb_edit_name_next, target)


def _cb_edit_name_next(message, target):
    uid = message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        return
    txt = (message.text or "").strip()
    if txt.startswith("/"):
        bot.reply_to(message, "Cancelled.")
        return
    new_name = txt[:40]
    if len(new_name) < 2:
        bot.reply_to(message, "Name too short. Try /start then reopen panel.")
        return
    p = load_profile(target)
    if not p:
        bot.reply_to(message, "User not found.")
        return
    old = p.get("name", "?")
    p["name"] = new_name
    save_profile(target, p)
    bot.reply_to(message, f"Name changed\n\n{old} to {new_name}")
    print(f"[edit_name] {uid} changed {target}: {old} to {new_name}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_device_view:"))
def _cb_device_view(call):
    uid = call.message.chat.id
    if not auth.get_session(uid): return
    try:
        target_cid = int(call.data.split(":")[1])
    except Exception:
        return
    entries = [e for e in auth.list_admin_devices(1000) if e.get("chat_id") == target_cid]
    text = f"📱 *Device {target_cid}*\n\nTotal opens: *{len(entries)}*\n\n*Recent:*\n"
    for e in entries[:15]:
        ts = e.get("ts", "")[:19].replace("T", " ")
        text += f"  • {ts} ({e.get('role','?')})\n"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_devices"))
    try:
        bot.edit_message_text(text[:4000], chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text[:4000], reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_profile:"))
def _cb_admin_profile(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess: return
    role = sess.get("role", "sub")
    try:
        target = int(call.data.split(":")[1])
    except Exception: return
    p = load_profile(target)
    if not p:
        bot.answer_callback_query(call.id, "User not found")
        return
    name = p.get("name") or "?"
    hku = p.get("hku_id") or "—"
    inst = p.get("institute") or "—"
    lvl = p.get("level") or "—"
    phone = p.get("phone") or "—"
    created = (p.get("created_at") or "")[:16]
    last = (p.get("last_seen") or "")[:16]
    strikes = p.get("strikes_total", 0)
    blocks = p.get("blocks_total", 0)
    calls = p.get("api_calls_total", 0)
    watched = p.get("watched", False)
    watch_btn = "⚠️ Watching" if watched else "⚪ Watch"
    bu = (p.get("behavior") or {}).get("blocked_until")
    block_line = f"\n🚫 *BLOCKED* until {bu[:16]}" if bu else ""
    text = (
        f"👤 *{name}*\n"
        f"`{hku}` · ID {target}\n\n"
        f"🏫 {inst}\n"
        f"🎓 {lvl}\n"
        f"📱 {phone}\n"
        f"📅 Joined: {created}\n"
        f"👀 Last seen: {last}\n\n"
        f"⚠️ Strikes: *{strikes}*\n"
        f"🚫 Blocks: *{blocks}*\n"
        f"📞 Calls: *{calls}*"
        f"{block_line}"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    if role == "primary":
        kb.add(
            InlineKeyboardButton("✏️ Edit Name", callback_data=f"admin_edit_name:{target}"),
            InlineKeyboardButton("💬 Message", callback_data=f"admin_pmsg_user:{target}"),
        )
        kb.add(
            InlineKeyboardButton(watch_btn, callback_data=f"admin_watch_toggle:{target}"),
            InlineKeyboardButton("⚡ Strikes", callback_data=f"admin_strikes:{target}"),
        )
        if bu:
            kb.add(InlineKeyboardButton("🔓 Unblock", callback_data=f"admin_unblock:{target}"))
        else:
            kb.add(InlineKeyboardButton("🚫 Block 24h", callback_data=f"admin_block_24h:{target}"))
        kb.add(InlineKeyboardButton("🗑 Delete", callback_data=f"admin_delete_user:{target}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_users:0"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_watch_toggle:"))
def _cb_watch_toggle(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "Read-only"); return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    p = load_profile(target)
    if not p: return
    p["watched"] = not p.get("watched", False)
    save_profile(target, p)
    if p["watched"]:
        bot.answer_callback_query(call.id, "Watching ON: any strike = 10-day lock")
        try:
            safe_send(uid, "\u26a0\ufe0f *Strict mode ON* for user " + str(target) + "\n\n_Any single strike triggers a 10-day lock. Unlock requires lock-in code._", parse_mode="Markdown")
        except Exception: pass
    else:
        bot.answer_callback_query(call.id, "Watching OFF")
    call.data = f"admin_profile:{target}"
    _cb_admin_profile(call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_strikes:"))
def _cb_strikes(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "Read-only"); return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    p = load_profile(target)
    if not p: return
    st = p.get("strikes_total", 0)
    text = f"⚡ *Strikes for {p.get('name') or '?'}*\n\nCurrent: *{st}*"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔄 Reset to 0", callback_data=f"admin_strike_reset:{target}"))
    kb.add(InlineKeyboardButton("✏️ Set custom", callback_data=f"admin_strike_custom:{target}"))
    kb.add(InlineKeyboardButton("⚠️ Send Warning", callback_data=f"admin_warn:{target}"))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"admin_profile:{target}"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_strike_reset:"))
def _cb_strike_reset(call):
    uid = call.message.chat.id
    if (auth.get_session(uid) or {}).get("role") != "primary": return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    p = load_profile(target)
    if not p: return
    p["strikes_total"] = 0
    p["behavior"] = {"strikes": 0, "blocked_until": None}
    save_profile(target, p)
    bot.answer_callback_query(call.id, "Reset to 0")
    call.data = f"admin_profile:{target}"
    _cb_admin_profile(call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_strike_custom:"))
def _cb_strike_custom(call):
    uid = call.message.chat.id
    if (auth.get_session(uid) or {}).get("role") != "primary": return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    bot.answer_callback_query(call.id, "Send new count")
    msg = bot.send_message(uid, f"Send new strike count for `{target}` (0-10):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, _strike_custom_step, target)


def _strike_custom_step(message, target):
    uid = message.chat.id
    try:
        n = int((message.text or "").strip())
        if n < 0 or n > 10:
            bot.reply_to(message, "Must be 0-10."); return
        p = load_profile(target)
        if not p: return
        p["strikes_total"] = n
        p.setdefault("behavior", {})["strikes"] = n
        save_profile(target, p)
        bot.reply_to(message, f"Strikes set to {n}.")
    except Exception as e:
        bot.reply_to(message, f"Invalid: {e}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_warn:"))
def _cb_warn(call):
    uid = call.message.chat.id
    if (auth.get_session(uid) or {}).get("role") != "primary": return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    p = load_profile(target) or {}
    strikes = p.get("strikes_total", 0)
    blocks = p.get("blocks_total", 0)
    warn = (
        f"⚠️ *Warning from Admin*\n\n"
        f"You have *{strikes}* strike(s) and *{blocks}* block(s).\n\n"
        f"Continue off-topic and you may be blocked.\n\n"
        f"— H&K Publications"
    )
    try:
        safe_send(target, warn, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "Warning sent")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Failed: {str(e)[:40]}")


@bot.callback_query_handler(func=lambda c: c.data == "admin_keys")
def _cb_keys(call):
    if not _sub_gate(call): return
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess:
        return
    if sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Read-only access")
        return
    try:
        import ai_client
        status = ai_client.key_status()
    except Exception as e:
        try: bot.answer_callback_query(call.id, f"Failed: {str(e)[:50]}")
        except Exception: pass
        return
    lines = ["\U0001f511 *API KEY STATUS*", ""]
    for s in status:
        provider = s["provider"].upper()
        idx = s["index"]
        mask = s["mask"]
        cd = s["cd_left"]
        fails = s["fails"]
        current = "\u25b6\ufe0f " if s["is_current"] else "     "
        if cd > 0:
            state = f"\u23f1 {cd}s cooldown"
        else:
            state = "\u2705 ready"
        lines.append(f"{current}*{provider} #{idx}*")
        lines.append(f"     `{mask}` \u00b7 {state}")
        lines.append(f"     Fails: *{fails}*")
        lines.append("")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("\U0001f504 Refresh", callback_data="admin_keys"))
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back"))
    try:
        bot.edit_message_text(text[:4000], chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text[:4000], reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


# ==========================================================
# S1 — ADMIN DEVICE HISTORY + RE-VERIFY
# ==========================================================
def build_dev_history_panel(uid):
    from datetime import datetime as _dt, timedelta as _td
    entries = auth.list_admin_devices(2000)
    cutoff = _dt.now() - _td(days=100)
    filtered = []
    for e in entries:
        try:
            ts = e.get("ts", "")
            if ts and _dt.fromisoformat(ts) >= cutoff:
                filtered.append(e)
        except Exception:
            pass
    by_dev = {}
    for e in filtered:
        cid = e.get("chat_id")
        if cid is None:
            continue
        if cid not in by_dev:
            by_dev[cid] = []
        by_dev[cid].append(e)
    text = f"\U0001f6e0 *ADMIN DEVICE HISTORY*\n\n*{len(by_dev)}* device(s) \u00b7 last 100 days"
    kb = InlineKeyboardMarkup(row_width=1)
    if not by_dev:
        text += "\n\n_No panel-open history yet._"
    else:
        for cid, evts in list(by_dev.items())[:20]:
            last = evts[0]
            role = last.get("role", "?")
            last_ts = (last.get("ts", "") or "")[:16].replace("T", " ")
            opens = len(evts)
            kb.add(InlineKeyboardButton(
                f"\U0001f4f1 {cid} \u00b7 {role} \u00b7 {opens}x \u00b7 {last_ts}",
                callback_data=f"admin_dev_detail:{cid}"
            ))
    kb.add(InlineKeyboardButton("\U0001f50d Re-verify (cleanup)", callback_data="admin_reverify"))
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back"))
    return text, kb


@bot.callback_query_handler(func=lambda c: c.data == "admin_hist")
def _cb_hist(call):
    if not _sub_gate(call): return
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess:
        bot.answer_callback_query(call.id, "Session expired")
        return
    if sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    text, kb = build_dev_history_panel(uid)
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try:
            bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception as e:
            print(f"[admin_hist] send err: {e}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_dev_detail:"))
def _cb_dev_detail(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    entries = [e for e in auth.list_admin_devices(2000) if e.get("chat_id") == target]
    lines = [f"\U0001f4f1 *Device {target}*", f"Total opens: *{len(entries)}*", "", "*Recent 20:*"]
    for e in entries[:20]:
        ts = (e.get("ts", "") or "")[:19].replace("T", " ")
        lines.append(f"  \u2022 {ts} ({e.get('role', '?')})")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_hist"))
    try:
        bot.edit_message_text(text[:4000], chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try:
            bot.send_message(uid, text[:4000], reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass


@bot.callback_query_handler(func=lambda c: c.data == "admin_reverify")
@bot.callback_query_handler(func=lambda c: c.data == "admin_reverify")
def _cb_reverify(call):
    if not _sub_gate(call): return
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    _adm = globals().get("_ADMIN_MSGS", {})
    _stat = globals().get("_STATS_MSGS", {})
    _btn = globals().get("_BTN_MSGS", {})
    _all = globals().get("_ALL_PANEL_MSGS", {})
    all_uids = set(_adm.keys()) | set(_stat.keys()) | set(_btn.keys()) | set(_all.keys())
    other_count = 0
    for u in all_uids:
        if u == uid: continue
        ids = set()
        ids.update(_adm.get(u, []))
        if u in _stat: ids.add(_stat[u])
        if u in _btn: ids.add(_btn[u])
        ids.update(_all.get(u, set()) if isinstance(_all.get(u), (set, list)) else [])
        other_count += len(ids)
    cur_ids = set()
    cur_ids.update(_adm.get(uid, []))
    cur_all = _all.get(uid, set())
    if isinstance(cur_all, (set, list)):
        cur_ids.update(cur_all)
    keep = set()
    if uid in _stat: keep.add(_stat[uid])
    if uid in _btn: keep.add(_btn[uid])
    cur_delete = cur_ids - keep
    cur_count = len(cur_delete)
    total = other_count + cur_count
    text = (
        f"\U0001f50d *Re-verify \u2014 Deep Cleanup*\n\n"
        f"Total to delete: *{total}*\n\n"
        f"\U0001f4f1 Other devices: *{other_count}*\n"
        f"\U0001f4f2 Old current-device msgs: *{cur_count}*\n"
        f"\u2705 Keeping current panel: *{len(keep)}*\n\n"
        f"Proceed?"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("\u2705 Delete", callback_data="admin_reverify_yes"),
        InlineKeyboardButton("\u274c Cancel", callback_data="admin_hist"),
    )
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass



@bot.callback_query_handler(func=lambda c: c.data == "admin_reverify_yes")
@bot.callback_query_handler(func=lambda c: c.data == "admin_reverify_yes")
def _cb_reverify_yes(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    _adm = globals().get("_ADMIN_MSGS", {})
    _stat = globals().get("_STATS_MSGS", {})
    _btn = globals().get("_BTN_MSGS", {})
    _all = globals().get("_ALL_PANEL_MSGS", {})
    deleted = 0
    failed = 0
    all_uids = set(_adm.keys()) | set(_stat.keys()) | set(_btn.keys()) | set(_all.keys())
    for u in list(all_uids):
        if u == uid: continue
        ids = set()
        ids.update(_adm.get(u, []))
        if u in _stat: ids.add(_stat[u])
        if u in _btn: ids.add(_btn[u])
        _au = _all.get(u)
        if isinstance(_au, (set, list)): ids.update(_au)
        _types = globals().get("_ADMIN_MSG_TYPES", {})
        for mid in ids:
            if _types.get(mid) == "summary": continue
            try:
                bot.delete_message(u, mid)
                deleted += 1
            except Exception:
                failed += 1
        _adm[u] = []
        _stat.pop(u, None)
        _btn.pop(u, None)
        _all.pop(u, None)
        try:
            _unreg = globals().get("unregister_panel")
            if _unreg: _unreg(u)
        except Exception: pass
    keep = set()
    if uid in _stat: keep.add(_stat[uid])
    if uid in _btn: keep.add(_btn[uid])
    cur_ids = set()
    cur_ids.update(_adm.get(uid, []))
    _cu = _all.get(uid)
    if isinstance(_cu, (set, list)): cur_ids.update(_cu)
    _types_c = globals().get("_ADMIN_MSG_TYPES", {})
    for mid in list(cur_ids):
        if mid in keep: continue
        if _types_c.get(mid) == "summary": continue
        try:
            bot.delete_message(uid, mid)
            deleted += 1
        except Exception:
            failed += 1
    _adm[uid] = list(keep)
    _all[uid] = set(keep)
    print(f"[reverify] {uid} deleted={deleted} failed={failed}")
    try:
        _rv_msg = bot.send_message(uid, f"\u2705 Deleted *{deleted}* msgs ({failed} failed)")
        import threading as _th_rv, time as _t_rv
        def _dn_rv():
            _t_rv.sleep(5)
            try: bot.delete_message(uid, _rv_msg.message_id)
            except Exception: pass
        _th_rv.Thread(target=_dn_rv, daemon=True).start()
    except Exception: pass
    try:
        _sp = globals().get("_show_admin_panel")
        if _sp: _sp(uid)
    except Exception: pass




# ==========================================================
# S2 - SUB-ADMIN MANAGEMENT
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "admin_subadmins")
def _cb_subadmins(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    subs = auth.list_sub_admins()
    text = (
        f"\U0001f6e1 *SUB-ADMIN MANAGEMENT*\n\n"
        f"*{len(subs)}* registered sub-admin(s)"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(
        f"\U0001f465 Registered Sub-Admins ({len(subs)})",
        callback_data="admin_sub_list"
    ))
    kb.add(InlineKeyboardButton(
        "\U0001f4f1 Their Activities",
        callback_data="admin_sub_activities"
    ))
    kb.add(InlineKeyboardButton(
        "\U0001f50d Re-verify (close all sessions)",
        callback_data="admin_sub_closeall"
    ))
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data == "admin_sub_list")
def _cb_sub_list(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    subs = auth.list_sub_admins()
    text = f"\U0001f465 *Registered Sub-Admins*\n\n{len(subs)} total"
    kb = InlineKeyboardMarkup(row_width=1)
    if not subs:
        text += "\n\n_None yet._"
    else:
        for sid, s in subs:
            nm = s.get("name", "?")
            ls = (s.get("last_seen", "") or "")[:16].replace("T", " ")
            kb.add(InlineKeyboardButton(
                f"\U0001f6e1 {nm} \u00b7 {sid} \u00b7 {ls}",
                callback_data=f"admin_sub_view:{sid}"
            ))
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_subadmins"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data == "admin_sub_activities")
def _cb_sub_activities(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    subs = auth.list_sub_admins()
    text = f"\U0001f4f1 *Sub-Admin Activities*\n\nClick any sub-admin for login history:"
    kb = InlineKeyboardMarkup(row_width=1)
    if not subs:
        text += "\n\n_No sub-admins registered._"
    else:
        for sid, s in subs:
            nm = s.get("name", "?")
            kb.add(InlineKeyboardButton(
                f"\U0001f4f1 {nm} ({sid})",
                callback_data=f"admin_sub_activity:{sid}"
            ))
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_subadmins"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data == "admin_sub_closeall")
def _cb_sub_closeall_confirm(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    subs = auth.list_sub_admins()
    # count open sessions
    open_count = 0
    try:
        for sid, _ in subs:
            if sid in auth._SESSIONS:
                open_count += 1
    except Exception:
        pass
    text = (
        f"\U0001f50d *Re-verify Sub-Admins*\n\n"
        f"Sub-admins registered: *{len(subs)}*\n"
        f"Currently active sessions: *{open_count}*\n\n"
        f"This will:\n"
        f"  \u2022 Close ALL open sub-admin panels (all devices)\n"
        f"  \u2022 Delete ALL their tracked admin-panel messages\n"
        f"  \u2022 Sub-admins will need to re-login\n\n"
        f"Registrations stay intact."
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("\u2705 Proceed", callback_data="admin_sub_closeall_yes"),
        InlineKeyboardButton("\u274c Cancel", callback_data="admin_subadmins"),
    )
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data == "admin_sub_closeall_yes")
def _cb_sub_closeall_yes(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    subs = auth.list_sub_admins()
    closed = 0
    deleted = 0
    _del_fn = globals().get("delete_all_admin_msgs")
    for sid, _ in subs:
        # close session
        try:
            if sid in auth._SESSIONS:
                auth._SESSIONS.pop(sid, None)
                closed += 1
        except Exception:
            pass
        # delete tracked msgs
        if _del_fn:
            try:
                d, _ = _del_fn(sid)
                deleted += d
            except Exception:
                pass
        # clear caches for that uid
        for cn in ("_STATS_MSGS", "_BTN_MSGS"):
            cc = globals().get(cn)
            if cc and sid in cc:
                try: cc.pop(sid, None)
                except Exception: pass
        # unregister panel
        try:
            _unreg = globals().get("unregister_panel")
            if _unreg: _unreg(sid)
        except Exception: pass
        # notify sub-admin
        try:
            bot.send_message(sid, "\U0001f512 Your sub-admin session was closed by primary admin. Please re-login.")
        except Exception:
            pass
    print(f"[sub-closeall] {uid} closed={closed} deleted={deleted}")
    try:
        _m = bot.send_message(uid, f"\u2705 Closed *{closed}* session(s), deleted *{deleted}* msg(s).", parse_mode="Markdown")
        import threading as _th, time as _t
        def _dn():
            _t.sleep(5)
            try: bot.delete_message(uid, _m.message_id)
            except Exception: pass
        _th.Thread(target=_dn, daemon=True).start()
    except Exception:
        pass
    try:
        call.data = "admin_subadmins"
        _cb_subadmins(call)
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_sub_view:"))
def _cb_sub_view(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    cfg = auth._load_config()
    entry = cfg.get("sub_admins", {}).get(str(target))
    if not entry:
        bot.answer_callback_query(call.id, "No longer exists")
        return
    nm = entry.get("name", "?")
    reg = (entry.get("registered_at", "") or "")[:19].replace("T", " ")
    ls = (entry.get("last_seen", "") or "")[:19].replace("T", " ")
    priv_plain = entry.get("privacy_plain") or "_not stored (old registration)_"
    reset_plain = entry.get("reset_plain") or "_not stored (old registration)_"
    text = (
        f"\U0001f6e1 *Sub-Admin: {nm}*\n\n"
        f"Chat ID: `{target}`\n"
        f"Registered: {reg}\n"
        f"Last seen: {ls}\n\n"
        f"\U0001f510 *Privacy Password:* `{priv_plain}`\n"
        f"\U0001f5dd *Forgot Key:* `{reset_plain}`"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("\u270f\ufe0f Edit Name", callback_data=f"admin_sub_edit_name:{target}"))
    kb.add(InlineKeyboardButton("\U0001f510 Edit Privacy Password", callback_data=f"admin_sub_edit_priv:{target}"))
    kb.add(InlineKeyboardButton("\U0001f5dd Edit Forgot Key", callback_data=f"admin_sub_edit_forgot:{target}"))
    kb.add(InlineKeyboardButton("\U0001f4f1 Activity", callback_data=f"admin_sub_activity:{target}"))
    kb.add(InlineKeyboardButton("\U0001f5d1 Delete Registration", callback_data=f"admin_sub_del:{target}"))
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data="admin_sub_list"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


# ==========================================================
# SUB-ADMIN EDIT HANDLERS
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_sub_edit_name:"))
def _cb_sub_edit_name(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    bot.answer_callback_query(call.id, "Type new name")
    msg = bot.send_message(uid, f"Send new *name* for sub-admin `{target}`:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, _cb_sub_edit_name_next, target)


def _cb_sub_edit_name_next(message, target):
    uid = message.chat.id
    if (auth.get_session(uid) or {}).get("role") != "primary":
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        bot.reply_to(message, "Cancelled.")
        return
    cfg = auth._load_config()
    entry = cfg.get("sub_admins", {}).get(str(target))
    if not entry:
        bot.reply_to(message, "Sub-admin not found.")
        return
    old = entry.get("name", "?")
    entry["name"] = txt[:60]
    auth._save_config(cfg)
    try:
        _sdm2 = globals().get("c03w_subadmin_details")
        if _sdm2:
            _sdm2.sync_from_config()
    except Exception:
        pass
    bot.reply_to(message, f"\u2705 Name changed: {old} → {txt[:60]}")
    print(f"[sub-edit] {uid} changed name of {target}: {old} → {txt[:60]}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_sub_edit_priv:"))
def _cb_sub_edit_priv(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    bot.answer_callback_query(call.id, "Type new password")
    msg = bot.send_message(uid, f"Send new *privacy password* for `{target}` (min 4 chars):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, _cb_sub_edit_priv_next, target)


def _cb_sub_edit_priv_next(message, target):
    uid = message.chat.id
    if (auth.get_session(uid) or {}).get("role") != "primary":
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/") or len(txt) < 4:
        bot.reply_to(message, "Cancelled or too short (min 4).")
        return
    cfg = auth._load_config()
    entry = cfg.get("sub_admins", {}).get(str(target))
    if not entry:
        bot.reply_to(message, "Sub-admin not found.")
        return
    try:
        import hashlib as _h, secrets as _s
        _salt = _s.token_hex(8)
        _hash = _h.sha256((txt + _salt).encode()).hexdigest()
        entry["privacy_hash"] = _hash
        entry["privacy_salt"] = _salt
        entry["privacy_plain"] = txt
        cfg["sub_admins"][str(target)] = entry
        auth._save_config(cfg)
        try:
            _sdm_pv = globals().get("c03w_subadmin_details")
            if _sdm_pv:
                _sdm_pv.sync_from_config()
        except Exception:
            pass
        ph = _hash
        # Verify save worked
        _check_cfg = auth._load_config()
        _check_entry = _check_cfg.get("sub_admins", {}).get(str(target), {})
        _check_ph = _check_entry.get("privacy_hash", "")
        if _check_ph != ph:
            print(f"[sub-edit] WARN: hash mismatch after save! want={ph[:8]} got={_check_ph[:8]}")
        else:
            print(f"[sub-edit] hash verified for {target}")
        bot.reply_to(message, f"\u2705 Privacy password updated for `{target}`", parse_mode="Markdown")
        print(f"[sub-edit] {uid} reset privacy of {target}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_sub_edit_forgot:"))
def _cb_sub_edit_forgot(call):
    uid = call.message.chat.id
    role = (auth.get_session(uid) or {}).get("role", "sub")
    if role != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    bot.answer_callback_query(call.id, "Type new forgot key")
    msg = bot.send_message(uid, f"Send new *forgot key* for `{target}` (min 6 chars):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, _cb_sub_edit_forgot_next, target)


def _cb_sub_edit_forgot_next(message, target):
    uid = message.chat.id
    if (auth.get_session(uid) or {}).get("role") != "primary":
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/") or len(txt) < 6:
        bot.reply_to(message, "Cancelled or too short (min 6).")
        return
    cfg = auth._load_config()
    entry = cfg.get("sub_admins", {}).get(str(target))
    if not entry:
        bot.reply_to(message, "Sub-admin not found.")
        return
    try:
        import hashlib as _h, secrets as _s
        _rsalt = _s.token_hex(8)
        _rhash = _h.sha256((txt + _rsalt).encode()).hexdigest()
        entry["reset_hash"] = _rhash
        entry["reset_salt"] = _rsalt
        entry["reset_plain"] = txt
        auth._save_config(cfg)
        try:
            _sdm_fk = globals().get("c03w_subadmin_details")
            if _sdm_fk:
                _sdm_fk.sync_from_config()
        except Exception:
            pass
        bot.reply_to(message, f"\u2705 Forgot key updated for `{target}`", parse_mode="Markdown")
        print(f"[sub-edit] {uid} reset forgot of {target}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")


# ==========================================================
# BACKFILL: existing sub-admins get placeholder plaintext
# ==========================================================
try:
    _cfg_bf = auth._load_config()
    _changed = False
    for _sid, _e in _cfg_bf.get("sub_admins", {}).items():
        if "privacy_plain" not in _e:
            _e["privacy_plain"] = None
            _changed = True
        if "reset_plain" not in _e:
            _e["reset_plain"] = None
            _changed = True
    if _changed:
        auth._save_config(_cfg_bf)
        print("[3] backfilled plaintext fields for existing sub-admins")
except Exception as _e_bf:
    print(f"[3] backfill err: {_e_bf}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_sub_del:"))
def _cb_sub_del_confirm(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    text = f"\U0001f5d1 *Delete sub-admin {target}?*\n\nThey will need a fresh lock-in to re-register."
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("\u2705 Delete", callback_data=f"admin_sub_del_yes:{target}"),
        InlineKeyboardButton("\u274c Cancel", callback_data=f"admin_sub_view:{target}"),
    )
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_sub_del_yes:"))
def _cb_sub_del_yes(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    ok = auth.revoke_sub_admin(target)
    try:
        auth._SESSIONS.pop(target, None)
    except Exception: pass
    try:
        _sdm3 = globals().get("c03w_subadmin_details")
        if _sdm3:
            _sdm3.remove(target)
    except Exception:
        pass
    # Invalidate lock-in flag so they must re-register
    for _mn, _mo in __import__("sys").modules.items():
        if hasattr(_mo, "_SUB_LOCKIN_OK"):
            try: _mo._SUB_LOCKIN_OK[target] = False
            except Exception: pass
            break
    print(f"[sub-del] {uid} revoked sub-admin {target}: {ok}")
    bot.answer_callback_query(call.id, "Deleted" if ok else "Not found")
    call.data = "admin_subadmins"
    try: _cb_subadmins(call)
    except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_sub_activity:"))
def _cb_sub_activity(call):
    uid = call.message.chat.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    try: target = int(call.data.split(":")[1])
    except Exception: return
    entries = [e for e in auth.list_admin_devices(2000) if e.get("chat_id") == target]
    text = f"\U0001f4f1 *Activity for {target}*\n\nTotal opens: *{len(entries)}*\n\n*Recent 15:*\n"
    for e in entries[:15]:
        ts = (e.get("ts", "") or "")[:19].replace("T", " ")
        text += f"  \u2022 {ts}\n"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("\U0001f519 Back", callback_data=f"admin_sub_view:{target}"))
    try:
        bot.edit_message_text(text[:4000], chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try: bot.send_message(uid, text[:4000], reply_markup=kb, parse_mode="Markdown")
        except Exception: pass
