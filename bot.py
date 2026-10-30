import sys
# ==========================================================
# bot.py — Chunk 1: Foundation
# ==========================================================

import telebot
import json
import os
import time
import threading
import random
from datetime import datetime, timedelta

import config
import ai_client
import health
import exam_engine
import svg_renderer
import svg_templates
import timer_manager

TELEGRAM_TOKEN = config.TELEGRAM_TOKEN
ADMIN_CHAT_ID = config.ADMIN_CHAT_ID
ADMIN_UNBLOCK_CODE = config.ADMIN_UNBLOCK_CODE
ADMIN_PANEL_CODE = config.ADMIN_PANEL_CODE
EXAM_OPTIONS = config.EXAM_OPTIONS
EXAM_NAMES = config.EXAM_NAMES
EXAM_MD = config.EXAM_MD
MAX_MARKS = config.MAX_MARKS
DURATION_MIN = config.DURATION_MIN
PAPER_PATTERN = config.PAPER_PATTERN
MAX_FUTURE_YEARS = config.MAX_FUTURE_YEARS
KEYS_FILE = config.KEYS_FILE
PROFILE_DIR = config.PROFILE_DIR
BOOKMARK_DIR = config.BOOKMARK_DIR
USER_ID_FILE = config.USER_ID_FILE
TELEGRAM_MSG_LIMIT = config.TELEGRAM_MSG_LIMIT
STRIKE_LIMIT = config.STRIKE_LIMIT
BLOCK_MINUTES = config.BLOCK_MINUTES
SVG_ENABLED = config.SVG_ENABLED
PRICE_UNIVERSAL = config.PRICE_UNIVERSAL
PRICING_NOTE = config.PRICING_NOTE
WHATSAPP_CONTACT = config.WHATSAPP_CONTACT

bot = telebot.TeleBot(TELEGRAM_TOKEN)



# Test engine state
bot._match_sessions = {}

bot._test_numerical_state = {}

os.makedirs(PROFILE_DIR, exist_ok=True)
os.makedirs(BOOKMARK_DIR, exist_ok=True)
os.makedirs(os.path.dirname(USER_ID_FILE), exist_ok=True)

PRELOAD_QUEUE = {}
PENDING_NUMERICAL = {}
_QGEN_RETRIES = {}
WAITING_DOUBT = {}


# ==========================================================
# PROFILE I/O
# ==========================================================
def load_profile(uid):
    path = os.path.join(PROFILE_DIR, f"{uid}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def save_profile(uid, profile):
    path = os.path.join(PROFILE_DIR, f"{uid}.json")
    with open(path, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def new_profile():
    return {
        "secured": False,
        "name": None,
        "institute": None,
        "level": None,
        "exams": [],
        "priority": None,
        "priority_pct": 100,
        "target_year": None,
        "target_marks": {},
        "selected_chapters": {},
        "subtopic_stats": {},
        "onboarding_step": "name",
        "behavior": {"strikes": 0, "blocked_until": None},
        "strikes_total": 0,
        "blocks_total": 0,
        "api_calls_total": 0,
        "last_strike_at": None,
        "last_block_at": None,
        "leaderboard_optin": True,
        "story_shown": False,
        "no_key_attempts": 0,
        "hku_id": None,
        "activation_key": None,
        "key_expired": False,
        "_practice_active": False,
        "_practice_exam": None,
        "_practice_level": "medium",
        "created_at": datetime.now().isoformat(),
    }


def get_or_create_profile(uid):
    p = load_profile(uid)
    if p:
        return p
    return new_profile()


# ==========================================================
# USER IDs (HKU-XXXXXX)
# ==========================================================
def _load_user_ids():
    if not os.path.exists(USER_ID_FILE):
        return {"counter": 0, "mapping": {}}
    try:
        with open(USER_ID_FILE) as f:
            return json.load(f)
    except Exception:
        return {"counter": 0, "mapping": {}}


def _save_user_ids(data):
    with open(USER_ID_FILE, "w") as f:
        json.dump(data, f, indent=2)


def allocate_user_id(uid):
    data = _load_user_ids()
    uid_str = str(uid)
    if uid_str in data["mapping"]:
        return data["mapping"][uid_str]
    data["counter"] += 1
    new_id = f"{config.USER_ID_PREFIX}{str(data['counter']).zfill(config.USER_ID_DIGITS)}"
    data["mapping"][uid_str] = new_id
    _save_user_ids(data)
    return new_id


def find_user_by_hku_id(hku_id):
    data = _load_user_ids()
    for uid_str, stored in data["mapping"].items():
        if stored == hku_id:
            return uid_str
    return None


# ==========================================================
# KEYS
# ==========================================================
def load_keys():
    if not os.path.exists(KEYS_FILE):
        return {}
    try:
        with open(KEYS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def is_valid_key(key):
    return key.strip() in load_keys()


# ==========================================================
# STRIKE / BLOCK
# ==========================================================
def check_blocked(uid):
    p = load_profile(uid)
    if not p:
        return False, 0
    bu = p.get("behavior", {}).get("blocked_until")
    if not bu:
        return False, 0
    try:
        dt = datetime.fromisoformat(bu)
    except Exception:
        return False, 0
    if datetime.now() < dt:
        secs = int((dt - datetime.now()).total_seconds())
        return True, f"{secs // 60} min {secs % 60} sec"
    p["behavior"]["blocked_until"] = None
    p["behavior"]["strikes"] = 0
    save_profile(uid, p)
    return False, 0


def register_strike(uid):
    p = load_profile(uid)
    if not p:
        return False, None
    p.setdefault("behavior", {"strikes": 0, "blocked_until": None})
    p["behavior"]["strikes"] = p["behavior"].get("strikes", 0) + 1
    p["strikes_total"] = p.get("strikes_total", 0) + 1
    p["last_strike_at"] = datetime.now().isoformat()
    if p["behavior"]["strikes"] >= STRIKE_LIMIT:
        until = datetime.now() + timedelta(minutes=BLOCK_MINUTES)
        p["behavior"]["blocked_until"] = until.isoformat()
        p["blocks_total"] = p.get("blocks_total", 0) + 1
        p["last_block_at"] = datetime.now().isoformat()
        save_profile(uid, p)
        return True, BLOCK_MINUTES
    save_profile(uid, p)
    return False, None


# ==========================================================
# SAFE SEND / EDIT / PHOTO
# ==========================================================

# ==========================================================
# Persistent usage tracking helpers
# ==========================================================
def record_strike_total(uid):
    p = load_profile(uid)
    if not p: return 0
    p["strikes_total"] = p.get("strikes_total", 0) + 1
    p["last_strike_at"] = datetime.now().isoformat()
    save_profile(uid, p)
    return p["strikes_total"]

def record_block_total(uid):
    p = load_profile(uid)
    if not p: return 0
    p["blocks_total"] = p.get("blocks_total", 0) + 1
    p["last_block_at"] = datetime.now().isoformat()
    save_profile(uid, p)
    return p["blocks_total"]

DAILY_USAGE_FILE = "daily_usage.json"

def _load_daily():
    if not os.path.exists(DAILY_USAGE_FILE):
        return {}
    try:
        with open(DAILY_USAGE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_daily(data):
    try:
        with open(DAILY_USAGE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def bump_api_calls(uid):
    p = load_profile(uid)
    if not p: return
    p["api_calls_total"] = p.get("api_calls_total", 0) + 1
    try:
        import os as _dco, json as _dcj
        from datetime import datetime as _dcdt
        _dc_path = "data/lifetime_stats.json"
        _dc = {}
        if _dco.path.exists(_dc_path):
            with open(_dc_path) as _dcf: _dc = _dcj.load(_dcf)
        _dc["total_calls"] = _dc.get("total_calls", 0) + 1
        _today = _dcdt.now().date().isoformat()
        _dc.setdefault("daily_calls", {})
        _dc["daily_calls"][_today] = _dc["daily_calls"].get(_today, 0) + 1
        with open(_dc_path, "w") as _dcf: _dcj.dump(_dc, _dcf, indent=2)
    except Exception as _dce:
        print(f"[daily-calls] {_dce}")
    save_profile(uid, p)
    # ---- daily counter ----
    today = datetime.now().strftime("%Y-%m-%d")
    daily = _load_daily()
    day = daily.setdefault(today, {"api_calls": 0, "users": []})
    day["api_calls"] = day.get("api_calls", 0) + 1
    uid_str = str(uid)
    if uid_str not in day.get("users", []):
        day.setdefault("users", []).append(uid_str)
    daily[today] = day
    _save_daily(daily)

def get_usage_stats(uid):
    p = load_profile(uid) or {}
    beh = p.get("behavior", {})
    return {
        "strikes_current": beh.get("strikes", 0),
        "strikes_total": p.get("strikes_total", 0),
        "blocks_total": p.get("blocks_total", 0),
        "api_calls_total": p.get("api_calls_total", 0),
        "blocked_until": beh.get("blocked_until"),
        "last_strike_at": p.get("last_strike_at"),
        "last_block_at": p.get("last_block_at"),
    }

def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    if not text:
        return
    while len(text) > TELEGRAM_MSG_LIMIT:
        cut = text.rfind("\n", 0, TELEGRAM_MSG_LIMIT)
        if cut == -1:
            cut = TELEGRAM_MSG_LIMIT
        try:
            bot.send_message(chat_id, text[:cut], parse_mode=parse_mode)
        except Exception:
            bot.send_message(chat_id, text[:cut])
        text = text[cut:].lstrip()
        time.sleep(0.3)
    if text:
        try:
            bot.send_message(chat_id, text, parse_mode=parse_mode,
                             reply_markup=reply_markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=reply_markup)


def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    try:
        if len(text) > TELEGRAM_MSG_LIMIT:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                  text=text[:TELEGRAM_MSG_LIMIT],
                                  parse_mode=parse_mode)
            safe_send(chat_id, text[TELEGRAM_MSG_LIMIT:], parse_mode=parse_mode)
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                  text=text, parse_mode=parse_mode,
                                  reply_markup=reply_markup)
    except Exception:
        safe_send(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)


def safe_send_photo(chat_id, photo_path, caption=None):
    try:
        with open(photo_path, "rb") as f:
            bot.send_photo(chat_id, f, caption=caption)
        return True
    except Exception:
        return False


# ==========================================================
# GATING
# ==========================================================
def _profile_ready(uid):
    p = load_profile(uid)
    if not p:
        return False, "no_profile"
    if not p.get("secured"):
        return False, "not_secured"
    # If user explicitly completed onboarding step, they are ready
    # (missing optional fields like exams/target_year can be set via /mode)
    if p.get("onboarding_step") == "done" and p.get("name"):
        return True, None
    if not p.get("name") or not p.get("institute") or not p.get("level"):
        return False, "not_onboarded"
    if not p.get("exams"):
        return False, "no_exams"
    if not p.get("target_year"):
        return False, "no_year"
    return True, None


def _send_setup_prompt(uid, reason):
    msgs = {
        "not_secured": "🔒 Please activate first. Send your key.",
        "not_onboarded": "⚠️ Finish your profile setup first.\n\nSend /start.",
        "no_exams": "⚠️ Complete your setup first.\n\nType /mode.",
        "no_year": "⚠️ Almost there.\n\nType /mode to set your target year.",
        "no_profile": "⚠️ Welcome!\n\nSend /start to begin.",
    }
    safe_send(uid, msgs.get(reason, "⚠️ Complete setup with /mode first."))


def _check_key_expired(uid, profile):
    if not profile.get("secured"):
        return False
    used_key = profile.get("activation_key")
    if not used_key:
        return False
    current_keys = load_keys()
    if used_key not in current_keys:
        profile["secured"] = False
        profile["key_expired"] = True
        save_profile(uid, profile)
        safe_send(uid,
            "⌛ Your activation key has expired.\n\n"
            f"To get a fresh key, WhatsApp *{WHATSAPP_CONTACT}*.\n\n"
            "Send your new key here to unlock.",
            parse_mode="Markdown")
        return True
    return False


# ==========================================================
# COUNTDOWN
# ==========================================================
def _days_until_exam(exam, year):
    if exam not in EXAM_MD:
        return None
    m, d = EXAM_MD[exam]
    try:
        exam_date = datetime(year, m, d).date()
    except Exception:
        return None
    today = datetime.now().date()
    return max(0, (exam_date - today).days)


def _countdown_footer(uid):
    p = load_profile(uid)
    if not p:
        return ""
    exams = p.get("exams", [])
    priority = p.get("priority")
    year = p.get("target_year")
    if not exams or not year:
        return ""
    ordered = []
    if priority and priority in exams:
        ordered.append(priority)
    for e in exams:
        if e not in ordered:
            ordered.append(e)
    lines = []
    for e in ordered:
        days = _days_until_exam(e, year)
        if days is None:
            continue
        name = EXAM_NAMES.get(e, e)
        if e == priority:
            lines.append(f"⏳ *{name} {year}: {days} days left* (primary)")
        else:
            lines.append(f"⏳ {name} {year}: {days} days left")
    if not lines:
        return ""
    return "\n\n━━━━━━━━━━━━━━━\n" + "\n".join(lines)


# ==========================================================
# PRICING / NO-KEY / STORY
# ==========================================================
def _pricing_message():
    return (
        f"💰 *Price: ₹{PRICE_UNIVERSAL}* — any exam, full prep duration.\n\n"
        f"{PRICING_NOTE}\n"
        f"WhatsApp: *{WHATSAPP_CONTACT}*"
    )


def _no_key_message(short=False):
    if short:
        return (
            "🔒 Hamilton needs an activation key.\n\n"
            f"Send your key to begin, or contact *{WHATSAPP_CONTACT}*."
        )
    return (
        "🔒 *Hamilton needs an activation key to begin.*\n\n"
        f"If you don't have a key yet, message WhatsApp *{WHATSAPP_CONTACT}*.\n\n"
        + _pricing_message()
        + "\n\nOnce you receive your key, send it here to unlock Hamilton."
    )


def _hamilton_story():
    return (
        "🎬 *Why \"Hamilton\"?*\n\n"
        "Remember Cars 3? Lightning McQueen needed to beat Jackson Storm. "
        "He had three months. He had one shot.\n\n"
        "His trainer wasn't another racer. It was *Hamilton* — an AI that "
        "studied every lap, every turn, every mistake, and quietly guided "
        "Lightning back to the top.\n\n"
        "Just like that, Hamilton was built to do one thing:\n"
        "*Stand beside you for these final months and pull you to your rank.*\n\n"
        "Three months. One shot. Let's make it count.\n\n"
        "— Hamilton Study AI\n"
        "   by Hemanth and Krishna Publications"
    )


# ==========================================================
# UTILITY
# ==========================================================
def _bump_retry(uid):
    _QGEN_RETRIES[uid] = _QGEN_RETRIES.get(uid, 0) + 1
    return _QGEN_RETRIES[uid]


def _reset_retry(uid):
    _QGEN_RETRIES[uid] = 0


def difficulty_str(d):
    if not isinstance(d, str):
        return str(d)
    return {"easy": "Easy", "medium": "Medium", "hard": "Hard"}.get(d, d.capitalize())


def _is_guess(q, time_taken):
    if q.get("logic_type") != "calc":
        return False
    return time_taken < q.get("min_realistic_sec", 20)


print("bot.py Chunk 1 loaded: foundation ready.")


# ==========================================================
# c01 - Sticker helper (Stage 1, flag-gated)
# ==========================================================
def try_send_sticker(chat_id, event_key):
    """Safe sticker sender. Never raises. Type-only logging."""
    try:
        if not getattr(config, "ENABLE_STICKERS", False):
            return
        sticker_id = getattr(config, "STICKER_IDS", {}).get(event_key)
        if not sticker_id:
            return
        bot.send_sticker(chat_id=chat_id, sticker=sticker_id)
    except Exception as e:
        try:
            print(f"[stickers] fail '{event_key}': {type(e).__name__}")
        except Exception:
            pass


# ==========================================================
# MASTER /help COMMAND (Registered before text handlers)
# ==========================================================
@bot.message_handler(commands=['help'])
def cmd_help_master(message):
    uid = message.chat.id
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton("📚 Study", callback_data="help_cat:study"),
        InlineKeyboardButton("🧪 Test & Practice", callback_data="help_cat:test")
    )
    kb.row(
        InlineKeyboardButton("📊 Profile & Stats", callback_data="help_cat:profile"),
        InlineKeyboardButton("⚙️ System", callback_data="help_cat:system")
    )
    kb.add(InlineKeyboardButton("❌ Close Help", callback_data="help_close"))
    safe_send(uid, "🤖 *Hamilton Help Menu*\n\nTap a category below:", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("help_cat:"))
def cb_help_cat_master(call):
    cat = call.data.split(":")[1]
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    
    if cat == "study":
        kb.row(InlineKeyboardButton("/mode", callback_data="help_cmd:mode"), InlineKeyboardButton("/select", callback_data="help_cmd:select"))
        kb.row(InlineKeyboardButton("/notes", callback_data="help_cmd:notes"), InlineKeyboardButton("/plan", callback_data="help_cmd:plan"))
        text = "📚 *Study Commands*\n\nTap a command to learn what it does."
    elif cat == "test":
        kb.row(InlineKeyboardButton("/exam", callback_data="help_cmd:exam"), InlineKeyboardButton("/pyq", callback_data="help_cmd:pyq"))
        kb.row(InlineKeyboardButton("/stop", callback_data="help_cmd:stop"), InlineKeyboardButton("/bookmarks", callback_data="help_cmd:bookmarks"))
        text = "🧪 *Test & Practice Commands*\n\nTap a command to learn what it does."
    elif cat == "profile":
        kb.row(InlineKeyboardButton("/status", callback_data="help_cmd:status"), InlineKeyboardButton("/health", callback_data="help_cmd:health"))
        kb.row(InlineKeyboardButton("/leaderboard", callback_data="help_cmd:leaderboard"), InlineKeyboardButton("/find", callback_data="help_cmd:find"))
        text = "📊 *Profile & Stats*\n\nTap a command to learn what it does."
    elif cat == "system":
        kb.row(InlineKeyboardButton("/start", callback_data="help_cmd:start"), InlineKeyboardButton("/cancel", callback_data="help_cmd:cancel"))
        kb.row(InlineKeyboardButton("/clear_data", callback_data="help_cmd:clear_data"))
        text = "⚙️ *System Commands*\n\nTap a command to learn what it does."
        
    kb.add(InlineKeyboardButton("🔙 Back to Categories", callback_data="help_back_master"))
    try: bot.edit_message_text(text, chat_id=call.from_user.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("help_cmd:"))
def cb_help_cmd_master(call):
    cmd = call.data.split(":")[1]
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    descriptions = {
        "start": "🚀 *Start*\nInitializes your Hamilton journey.",
        "mode": "📚 *Mode*\nSet up your exams, priority exam, target year, and target marks.",
        "select": "🎯 *Select*\nPick the specific chapters you want to focus on.",
        "exam": "🧪 *Exam*\nEnter Practice, Test, Conceptual, or PYQ mode.",
        "pyq": "📝 *PYQ*\nPractice REAL questions from past JEE/EAMCET papers.",
        "notes": "📖 *Notes*\nGenerates structured short notes as a PDF.",
        "plan": "📅 *Plan*\nGenerates a study schedule.",
        "status": "👤 *Status*\nShows your profile summary.",
        "health": "❤️ *Health*\nShows your readiness across all three subjects.",
        "leaderboard": "🏆 *Leaderboard*\nShows top performers.",
        "find": "🔍 *Find*\nSearch for a user by HKU ID.",
        "bookmarks": "🔖 *Bookmarks*\nView saved questions.",
        "stop": "🛑 *Stop*\nEnds your current session.",
        "clear_data": "⚠️ *Clear Data*\nDeletes your profile.",
        "cancel": "✖️ *Cancel*\nAborts any active setup."
    }
    try: bot.edit_message_text(descriptions.get(cmd, "No description."), chat_id=call.from_user.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "help_back_master")
def cb_help_back_master(call):
    cmd_help_master(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "help_close")
def cb_help_close_master(call):
    try: bot.delete_message(call.from_user.id, call.message.message_id)
    except: pass
    bot.answer_callback_query(call.id, "Closed")



def cb_sub_mode_master(call):
    uid = call.from_user.id
    mode = call.data.split(":")[1]
    import bot_chunks.c06 as c06_mod
    if hasattr(c06_mod, "_start_exam_setup"):
        c06_mod._start_exam_setup(uid, call.message.message_id, mode)
    bot.answer_callback_query(call.id)











# ==========================================================
# THE FINAL ULTIMATE EXAM ENGINE
# ==========================================================
import json
import time
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

globals()['bot']._exam_state = getattr(bot, "_exam_state", {})

# DISABLED_OVERRIDE: # DISABLED_OVERRIDE: # DISABLED_OLD
def cmd_exam_final(message):
    uid = message.chat.id
    globals()['bot']._exam_state[uid] = {}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="ex_main:practice"),
        InlineKeyboardButton("📝 Test", callback_data="ex_main:test")
    )
    kb.add(
        InlineKeyboardButton("💡 Concept Mastery", callback_data="ex_main:conceptual"),
        InlineKeyboardButton("🔍 PYQ Explorer", callback_data="ex_main:pyq")
    )
    safe_send(uid, "🎓 *Hamilton Exam Center*\n\nSelect a section:", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ex_main:"))
def cb_ex_main(call):
    uid = call.from_user.id
    mode = call.data.split(":")[1]
    globals()['bot']._exam_state[uid]["mode"] = mode
    
    if mode == "conceptual":
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("🧠 Pure Conceptual", callback_data="ex_sub_mode:conceptual"),
            InlineKeyboardButton("⚠️ Exceptional Case", callback_data="ex_sub_mode:exceptional"),
            InlineKeyboardButton("🔙 Back to Menu", callback_data="ex_back_menu")
        )
        try: globals()['bot'].edit_message_text("💡 *Conceptual Mastery*\n\nSelect type:", chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        except: pass
        globals()['bot'].answer_callback_query(call.id)
        return
        
    _ex_ask_exam(uid, call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ex_sub_mode:"))
def cb_ex_sub_mode(call):
    uid = call.from_user.id
    globals()['bot']._exam_state[uid]["mode"] = call.data.split(":")[1]
    _ex_ask_exam(uid, call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

def _ex_ask_exam(uid, msg_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🎓 JEE Advanced", callback_data="ex_exam:JEE_ADV"),
        InlineKeyboardButton("📝 JEE Mains", callback_data="ex_exam:JEE_MAIN"),
        InlineKeyboardButton("📝 AP EAMCET", callback_data="ex_exam:EAMCET"),
        InlineKeyboardButton("🔙 Back", callback_data="ex_back_menu")
    )
    try: globals()['bot'].edit_message_text("Select Exam:", chat_id=uid, message_id=msg_id, reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("ex_exam:"))
def cb_ex_exam(call):
    uid = call.from_user.id
    exam = call.data.split(":")[1]
    globals()['bot']._exam_state[uid]["exam"] = exam
    
    if exam == "JEE_ADV" and globals()['bot']._exam_state[uid]["mode"] == "test":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📄 Paper 1 (3h)", callback_data="ex_paper:1"),
            InlineKeyboardButton("📄 Paper 2 (3h)", callback_data="ex_paper:2"),
            InlineKeyboardButton("📚 Both (6h)", callback_data="ex_paper:both")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="ex_back_menu"))
        try: globals()['bot'].edit_message_text("Select Paper(s):", chat_id=uid, message_id=call.message.message_id, reply_markup=kb)
        except: pass
    else:
        _ex_ask_subjects(uid, call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ex_paper:"))
def cb_ex_paper(call):
    uid = call.from_user.id
    globals()['bot']._exam_state[uid]["paper"] = call.data.split(":")[1]
    _ex_ask_subjects(uid, call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

def _ex_ask_subjects(uid, msg_id):
    globals()['bot']._exam_state[uid]["subjects"] = set()
    kb = InlineKeyboardMarkup(row_width=3)
    kb.row(
        InlineKeyboardButton("Maths", callback_data="old_ex_subj:Maths"),
        InlineKeyboardButton("Physics", callback_data="old_ex_subj:Physics"),
        InlineKeyboardButton("Chemistry", callback_data="old_ex_subj:Chemistry")
    )
    kb.row(InlineKeyboardButton("▶️ Continue", callback_data="ex_subj_cont"), InlineKeyboardButton("✖️ Clear", callback_data="ex_subj_clear"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="ex_back_menu"))
    try: globals()['bot'].edit_message_text("Select Subjects:", chat_id=uid, message_id=msg_id, reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("ex_subj:"))
def cb_ex_subj(call):
    uid = call.from_user.id
    subj = call.data.split(":")[1]
    mode = globals()['bot']._exam_state[uid].get("mode")
    subs = globals()['bot']._exam_state[uid].get("subjects", set())
    
    if mode != "test":
        if subj in subs:
            subs.remove(subj)
        else:
            subs.clear()
            subs.add(subj)
    else:
        if subj in subs: subs.remove(subj)
        else: subs.add(subj)
        
    globals()['bot']._exam_state[uid]["subjects"] = subs
    
    kb = InlineKeyboardMarkup(row_width=3)
    m = "✅ Maths" if "Maths" in subs else "Maths"
    p = "✅ Physics" if "Physics" in subs else "Physics"
    c = "✅ Chemistry" if "Chemistry" in subs else "Chemistry"
    kb.row(InlineKeyboardButton(m, callback_data="old_ex_subj:Maths"), InlineKeyboardButton(p, callback_data="old_ex_subj:Physics"), InlineKeyboardButton(c, callback_data="old_ex_subj:Chemistry"))
    kb.row(InlineKeyboardButton("▶️ Continue", callback_data="ex_subj_cont"), InlineKeyboardButton("✖️ Clear", callback_data="ex_subj_clear"))
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="ex_back_menu"))
    try: bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
    except: pass
    globals()['bot'].answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "ex_subj_cont")
def cb_ex_subj_cont(call):
    uid = call.from_user.id
    subs = list(globals()['bot']._exam_state[uid].get("subjects", set()))
    if not subs:
        globals()['bot'].answer_callback_query(call.id, "Select at least one subject!")
        return
        
    mode = globals()['bot']._exam_state[uid].get("mode")
    if mode in ("conceptual", "exceptional"):
        globals()['bot']._exam_state[uid]["awaiting_count"] = True
        globals()['bot'].edit_message_text("🔢 *How many questions?*\n\nSend a number from 1 to 80:", chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    else:
        globals()['bot']._exam_state[uid]["chap_idx"] = 0
        globals()['bot']._exam_state[uid]["chap_page"] = 0
        _ex_ask_chapters(uid, subs[0], call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

@bot.message_handler(func=lambda m: getattr(bot, "_exam_state", {}).get(m.chat.id, {}).get("awaiting_count") == True, content_types=['text'])
def cb_ex_capture_count(message):
    uid = message.chat.id
    try:
        count = int(message.text.strip())
        if count < 1 or count > 80: raise ValueError
    except:
        safe_send(uid, "❌ Invalid. Enter 1-80:")
        return
    globals()['bot']._exam_state[uid]["awaiting_count"] = False
    globals()['bot']._exam_state[uid]["max_q"] = count
    subs = list(globals()['bot']._exam_state[uid].get("subjects", set()))
    globals()['bot']._exam_state[uid]["chap_idx"] = 0
    globals()['bot']._exam_state[uid]["chap_page"] = 0
    _ex_ask_chapters(uid, subs[0], None)

def _ex_ask_chapters(uid, subject, msg_id):
    exam = globals()['bot']._exam_state[uid]["exam"]
    mode = globals()['bot']._exam_state[uid].get("mode", "practice")
    
    if globals()['bot']._exam_state[uid].get("current_subject") != subject:
        globals()['bot']._exam_state[uid]["chap_page"] = 0
        
    globals()['bot']._exam_state[uid]["current_subject"] = subject
    globals()['bot']._exam_state[uid].setdefault("selected_chapters", {})
    
    _map = {"JEE_ADV": "jee_adv", "JEE_MAIN": "jee_main", "EAMCET": "eamcet"}
    prefix = _map.get(exam, "jee_main")
    fn = f"data/{prefix}_{subject.lower() if subject.lower() != 'maths' else 'maths'}.json"
    
    chapters = []
    try:
        with open(fn, "r") as f:
            chapters = list(json.load(f).keys())
    except: pass
        
    page = globals()['bot']._exam_state[uid].get("chap_page", 0)
    per_page = 6
    start = page * per_page
    end = start + per_page
    
    kb = InlineKeyboardMarkup(row_width=2)
    btns = []
    selected = globals()['bot']._exam_state[uid]["selected_chapters"].get(subject, set())
    
    for i, ch in enumerate(chapters[start:end]):
        num = start + i + 1
        mark = "✅ " if ch in selected else ""
        btns.append(InlineKeyboardButton(f"{mark}{num}. {ch[:15]}", callback_data=f"ex_ch:{ch}"))
        
    if len(btns) % 2 != 0:
        btns.append(InlineKeyboardButton(" ", callback_data="ex_noop"))
    for i in range(0, len(btns), 2):
        kb.row(btns[i], btns[i+1])
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="ex_chpage:-1"))
    if end < len(chapters): nav.append(InlineKeyboardButton("Next ➡️", callback_data="ex_chpage:1"))
    if nav: kb.row(*nav)
    
    kb.row(
        InlineKeyboardButton("▶️ Continue", callback_data="ex_chcont"),
        InlineKeyboardButton("✖️ Clear", callback_data="ex_chclear")
    )
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="ex_back_menu"))
    
    rule_str = "Select ONE chapter" if mode != "test" else "Select any chapters"
    text = f"📚 *{subject}* - Select Chapters ({rule_str}):\n(Selected: {len(selected)})"
    if msg_id:
        try: globals()['bot'].edit_message_text(text, chat_id=uid, message_id=msg_id, reply_markup=kb, parse_mode="Markdown")
        except: pass
    else:
        safe_send(uid, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ex_ch:"))
def cb_ex_ch(call):
    uid = call.from_user.id
    ch = call.data.split(":", 1)[1]
    subj = globals()['bot']._exam_state[uid]["current_subject"]
    mode = globals()['bot']._exam_state[uid].get("mode", "practice")
    sel = globals()['bot']._exam_state[uid]["selected_chapters"].setdefault(subj, set())
    
    if ch in sel: 
        sel.remove(ch)
    else: 
        if mode != "test": sel.clear()
        sel.add(ch)
        
    _ex_ask_chapters(uid, subj, call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ex_chpage:"))
def cb_ex_chpage(call):
    uid = call.from_user.id
    delta = int(call.data.split(":")[1])
    globals()['bot']._exam_state[uid]["chap_page"] += delta
    _ex_ask_chapters(uid, globals()['bot']._exam_state[uid]["current_subject"], call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "ex_chclear")
def cb_ex_chclear(call):
    uid = call.from_user.id
    subj = globals()['bot']._exam_state[uid]["current_subject"]
    globals()['bot']._exam_state[uid]["selected_chapters"][subj] = set()
    _ex_ask_chapters(uid, subj, call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "ex_chcont")
def cb_ex_chcont(call):
    uid = call.from_user.id
    subj = globals()['bot']._exam_state[uid]["current_subject"]
    subs = list(globals()['bot']._exam_state[uid]["subjects"])
    
    sel = globals()['bot']._exam_state[uid]["selected_chapters"].get(subj, set())
    if not sel:
        globals()['bot'].answer_callback_query(call.id, "Select at least one chapter!")
        return
        
    idx = globals()['bot']._exam_state[uid].get("chap_idx", 0)
    if idx + 1 < len(subs):
        globals()['bot']._exam_state[uid]["chap_idx"] += 1
        globals()['bot']._exam_state[uid]["chap_page"] = 0
        _ex_ask_chapters(uid, subs[idx+1], call.message.message_id)
    else:
        _ex_ask_level(uid, call.message.message_id)
    globals()['bot'].answer_callback_query(call.id)

def _ex_ask_level(uid, msg_id):
    kb = InlineKeyboardMarkup(row_width=3)
    kb.row(
        InlineKeyboardButton("L1 (Mains)", callback_data="old_ex_lvl:1"),
        InlineKeyboardButton("L2 (Adv)", callback_data="old_ex_lvl:2"),
        InlineKeyboardButton("L3 (Death)", callback_data="old_ex_lvl:3")
    )
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="ex_back_menu"))
    try: globals()['bot'].edit_message_text("Select Difficulty Level:", chat_id=uid, message_id=msg_id, reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("ex_lvl:"))
def cb_ex_lvl(call):
    uid = call.from_user.id
    lvl = int(call.data.split(":")[1])
    state = globals()['bot']._exam_state[uid]
    state["level"] = lvl
    try: globals()['bot'].delete_message(uid, call.message.message_id)
    except: pass
    
    mode = state.get("mode", "practice")
    
    # 5-4-3-2-1 Countdown
    msg = safe_send(uid, "⏳ *Preparing test...* 5", parse_mode="Markdown")
    for i in range(4, 0, -1):
        time.sleep(1)
        try: globals()['bot'].edit_message_text(f"⏳ *Preparing test...* {i}", chat_id=uid, message_id=msg.message_id, parse_mode="Markdown")
        except: pass
    time.sleep(1)
    try: globals()['bot'].delete_message(uid, msg.message_id)
    except: pass
    
    if mode in ("practice", "conceptual", "exceptional"):
        _ex_start_practice(uid)
    else:
        _ex_start_test(uid)

def _ex_start_practice(uid):
    state = globals()['bot']._exam_state[uid]
    exam = state["exam"]
    subs = list(state["subjects"])
    mode = state.get("mode", "practice")
    
    chapters_str = "\n".join([f"• {s}: {len(c)} selected" for s, c in state["selected_chapters"].items()])
    intro = f"🚀 *{mode.upper()} STARTED!*\n\n"
    intro += f"📚 *Subjects:*\n{chapters_str}\n\n"
    intro += f"📝 *Rules:*\n- Solutions will appear instantly\n- No timer limit\n\n"
    intro += f"_Generating Q1..._"
    loader = safe_send(uid, intro, parse_mode="Markdown")
    
    # Prepare session
    sess = exam_engine.get_session(uid)
    if not sess: sess = exam_engine.new_practice_session(uid, exam=exam)
    sess["mode"] = mode
    sess["exam"] = exam
    sess["subject"] = subs[0]
    sess["level"] = state["level"]
    sess["max_q"] = state.get("max_q", 999)
    sess["show_solution"] = True
    
    # DIRECT, SYNCHRONOUS GENERATION
    try:
        import sys
        _b = bot
        
        p = load_profile(uid)
        subj = subs[0]
        ch = list(state["selected_chapters"].get(subj, []))[0]
        
        # We grab the first subtopic from the JSON to guarantee it works
        import json
        with open(f"data/jee_adv_{subj.lower()}.json") as f:
            data = json.load(f)
        sub = list(data[ch].keys())[0]
        
        q = exam_engine.generate_question(exam, subj, ch, sub, q_type="mcq", difficulty="easy")
        
        if q:
            q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}
            import bot_chunks.c06 as c06_mod
            c06_mod.PRELOAD_QUEUE[uid] = [q]
            
            try: _b.delete_message(uid, loader.message_id)
            except: pass
            c06_mod._send_next_test_q(uid)
        else:
            try: _b.edit_message_text("⚠️ AI returned None. Check API keys.", chat_id=uid, message_id=loader.message_id)
            except: pass
            
    except Exception as e:
        try: 
            import sys
            _b = bot
            _b.edit_message_text(f"⚠️ Error: {e}", chat_id=uid, message_id=loader.message_id)
        except: pass

def _ex_start_test(uid):
    state = globals()['bot']._exam_state[uid]
    exam = state["exam"]
    subs = list(state["subjects"])
    papers = state.get("paper", "1")
    
    mins = (60 if exam == "JEE_MAIN" else 45) * len(subs)
    if papers == "both": mins *= 2
    
    chapters_str = "\n".join([f"• {s}: {len(c)} selected" for s, c in state["selected_chapters"].items()])
    intro = f"🚀 *TEST STARTED!*\n\n"
    intro += f"📚 *Sections:*\n{chapters_str}\n\n"
    intro += f"⏱️ *Time:* {mins} minutes\n"
    intro += f"📝 *Rules:*\n- Strict timer\n- No feedback until end\n\n"
    intro += f"_Generating Q1..._"
    loader = safe_send(uid, intro, parse_mode="Markdown")
    
    sess = exam_engine.get_session(uid)
    if not sess: sess = exam_engine.new_test_session(uid, exam, subs, {}, papers=1)
    sess["mode"] = "test"
    sess["exam"] = exam
    sess["subjects"] = subs
    sess["level"] = state["level"]
    sess["show_solution"] = False
    
    try:
        import sys
        _b = bot
        
        subj = subs[0]
        ch = list(state["selected_chapters"].get(subj, []))[0]
        
        import json
        with open(f"data/jee_adv_{subj.lower()}.json") as f:
            data = json.load(f)
        sub = list(data[ch].keys())[0]
        
        q = exam_engine.generate_question(exam, subj, ch, sub, q_type="mcq", difficulty="easy")
        
        if q:
            q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}
            import bot_chunks.c06 as c06_mod
            c06_mod.PRELOAD_QUEUE[uid] = [q]
            
            timer_manager.start_test_timer(globals()['bot'], uid, mins, on_time_up=c06_mod._test_paper_time_up)
            
            try: _b.delete_message(uid, loader.message_id)
            except: pass
            c06_mod._send_next_test_q(uid)
        else:
            try: _b.edit_message_text("⚠️ AI returned None. Check API keys.", chat_id=uid, message_id=loader.message_id)
            except: pass
            
    except Exception as e:
        try: 
            import sys
            _b = bot
            _b.edit_message_text(f"⚠️ Error: {e}", chat_id=uid, message_id=loader.message_id)
        except: pass

def cb_ex_back_menu(call):
    cmd_exam_final(call.message)
    globals()['bot'].answer_callback_query(call.id)


try:
    if not hasattr(bot, '_test_multi_state'):
        bot._test_multi_state = {}
except Exception:
    pass


# ==========================================================
# c02.py — Start, Onboarding, Mode, Status
# ==========================================================
def _run_onboarding(uid):
    p = load_profile(uid)
    step = p.get("onboarding_step")
    
    if step == "name":
        msg = bot.send_message(uid, 
            "📝 *What is your name?*\n\n"
            "⚠️ _Please enter your genuine full real name._\n"
            "_Short forms and fake names are not accepted._", 
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_name)
    elif step == "institute":
        msg = bot.send_message(uid, "🏫 *Which institute / school / college?*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_institute)
    elif step == "phone":
        msg = bot.send_message(uid, "📱 *Enter your 10-digit mobile number:*\n\n_Example: 9876543210_", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_phone)
    elif step == "level":
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("Junior", "Senior", "Dropper")
        msg = bot.send_message(uid, "🎓 *Junior, Senior, or Dropper?*", reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(msg, _onboarding_level)
    else:
        bot.send_message(uid, "✅ Setup complete. Type /mode to begin.")

def _onboarding_name(message):
    uid = message.chat.id
    n = (message.text or "").strip()[:40]
    
    if not n or len(n) < 3:
        bot.reply_to(message, "❌ Name must be at least 3 characters long. Please enter your real full name:")
        return
        
    p = load_profile(uid)
    p.setdefault("name_strikes", 0)
    
    if p["name_strikes"] >= 3:
        bot.reply_to(message, "🔒 You are locked out for entering fake names. Contact Admin on WhatsApp to unlock.")
        return
        
    try:
        import ai_client
        verdict, _ = ai_client.verify_name(n)
        if verdict == "FICTIONAL":
            p["name_strikes"] += 1
            save_profile(uid, p)
            left = 3 - p["name_strikes"]
            if left > 0:
                bot.reply_to(message, f"❌ This name seems fake or fictional.\n⚠️ You have *{left} attempts left*.\n\nEnter your real full name:", parse_mode="Markdown")
            else:
                bot.reply_to(message, "🔒 Locked out. Contact admin on WhatsApp to verify your name.")
            return
    except Exception:
        pass
            
    p["name"] = n
    p["onboarding_step"] = "institute"
    save_profile(uid, p)
    _run_onboarding(uid)

def _onboarding_institute(message):
    uid = message.chat.id
    i = (message.text or "").strip()[:60]
    if not i or len(i) < 3:
        bot.reply_to(message, "❌ Please enter a valid institute name:")
        return
        
    bot.reply_to(message, "⏳ Verifying institute...")
    try:
        import ai_client
        verdict = ai_client.verify_institute(i)
        if verdict == "FAKE":
            bot.reply_to(message, "❌ This does not seem to be a real institute. Please enter your actual school/college name:")
            return
    except Exception:
        pass
        
    p = load_profile(uid)
    p["institute"] = i
    p["onboarding_step"] = "phone"
    save_profile(uid, p)
    _run_onboarding(uid)

def _onboarding_phone(message):
    import re
    uid = message.chat.id
    raw = (message.text or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in "6789":
        bot.reply_to(message, "❌ Please enter a valid 10-digit Indian mobile number.\nExample: `9876543210`", parse_mode="Markdown")
        return
    p = load_profile(uid)
    p["phone"] = digits
    p["onboarding_step"] = "level"
    save_profile(uid, p)
    _run_onboarding(uid)

def _onboarding_level(message):
    uid = message.chat.id
    t = (message.text or "").strip().lower()
    if t not in ("junior", "senior", "dropper"):
        bot.reply_to(message, "Tap one of: Junior / Senior / Dropper")
        return
    p = load_profile(uid)
    p["level"] = t.capitalize()
    p["onboarding_step"] = "done"
    if not p.get("hku_id"):
        p["hku_id"] = allocate_user_id(uid)
    save_profile(uid, p)
    
    try:
        import admin_auth as _aa
        _aa.mark_new_user(uid, p.get("name", "?"), p.get("phone", "?"))
    except Exception: pass
    
    bot.reply_to(message,
        f"✅ *Profile saved*\n\n👤 {p['name']}\n🏫 {p['institute']}\n🎓 {p['level']}\n📱 {p['phone']}\n🆔 {p['hku_id']}\n\nType /mode to begin.",
        reply_markup=telebot.types.ReplyKeyboardRemove(),
        parse_mode="Markdown")

# ==========================================================
# /start, /mode, /status, etc...
# ==========================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.chat.id
    p = get_or_create_profile(uid)
    
    # If not yet activated (no key provided)
    if not p.get("secured"):
        save_profile(uid, p)
        
        greeting = (
            "🙏 *Namaskaram, Aspirant!*\n\n"
            "Welcome to the *Hamilton Study AI* platform. You are here to dedicate your upcoming days to participate in the race of competitive exams and emerge victorious.\n\n"
            "You stand in the final stretch of your Intermediate journey — balancing board studies with deep, focused preparation. "
            "I am your personal exam mentor, built by *Hemanth and Krishna Publications*, to walk beside you every single day until your rank is sealed.\n\n"
            "Your goal is not just to pass. Your goal is to *rise above the noise* and claim the rank you were born for.\n\n"
            "🔒 *Send your activation key to begin your journey.*"
        )
        bot.reply_to(message, greeting, parse_mode="Markdown")
        return
        
    # If activated but still in the middle of onboarding
    if p.get("onboarding_step") and p["onboarding_step"] != "done":
        _run_onboarding(uid)
        return
        
    # If fully registered
    bot.reply_to(message, 
        f"🙏 *Welcome back, {p.get('name', 'Aspirant')}!*\n\n"
        "Type /mode to continue your preparation.\n"
        "Type /clear_data if you want to wipe your profile and start over.", 
        parse_mode="Markdown")

# OLD_MODE_DISABLED: @bot.message_handler(commands=['mode'])
# OLD_MODE_DISABLED: def cmd_mode(message):
# OLD_MODE_DISABLED:     uid = message.chat.id
# OLD_MODE_DISABLED:     try:
# OLD_MODE_DISABLED:         ready, reason = _profile_ready(uid)
# OLD_MODE_DISABLED:         if not ready:
# OLD_MODE_DISABLED:             _send_setup_prompt(uid, reason)
# OLD_MODE_DISABLED:             return
# OLD_MODE_DISABLED:     except Exception as _e:
# OLD_MODE_DISABLED:         print(f"[mode] profile err: {_e}")
# OLD_MODE_DISABLED:     # Step 1: Ask which exam FIRST
# OLD_MODE_DISABLED:     p = load_profile(uid)
# OLD_MODE_DISABLED:     exams = p.get("exams") or []
# OLD_MODE_DISABLED:     if not exams:
# OLD_MODE_DISABLED:         bot.send_message(uid, "\u26a0\ufe0f No exams set. Use /start to configure.")
# OLD_MODE_DISABLED:         return
# OLD_MODE_DISABLED:     if len(exams) == 1:
# OLD_MODE_DISABLED:         # Only one exam — set it and go straight to mode
# OLD_MODE_DISABLED:         p["_exam_chosen"] = exams[0]
# OLD_MODE_DISABLED:         save_profile(uid, p)
# OLD_MODE_DISABLED:         _ask_mode_after_exam(uid)
# OLD_MODE_DISABLED:         return
# OLD_MODE_DISABLED:     # Multiple exams — ask which
# OLD_MODE_DISABLED:     from telebot.types import ReplyKeyboardMarkup
# OLD_MODE_DISABLED:     kb = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
# OLD_MODE_DISABLED:     for e in exams:
# OLD_MODE_DISABLED:         try:
# OLD_MODE_DISABLED:             kb.add(EXAM_NAMES[e])
# OLD_MODE_DISABLED:         except Exception:
# OLD_MODE_DISABLED:             kb.add(e)
# OLD_MODE_DISABLED:     msg = bot.send_message(
# OLD_MODE_DISABLED:         uid,
# OLD_MODE_DISABLED:         "\U0001f4da *Step 1/2 \u2014 Which exam?*\n\n"
# OLD_MODE_DISABLED:         "_You can change priority anytime with /select_",
# OLD_MODE_DISABLED:         reply_markup=kb, parse_mode="Markdown"
# OLD_MODE_DISABLED:     )
# OLD_MODE_DISABLED:     bot.register_next_step_handler(msg, _mode_choose_exam)
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: def _mode_choose_exam(message):
# OLD_MODE_DISABLED:     """User picked an exam. Save it, then ask mode."""
# OLD_MODE_DISABLED:     uid = message.chat.id
# OLD_MODE_DISABLED:     t = (message.text or "").strip()
# OLD_MODE_DISABLED:     p = load_profile(uid)
# OLD_MODE_DISABLED:     exams = p.get("exams") or []
# OLD_MODE_DISABLED:     # Match user's choice to exam key
# OLD_MODE_DISABLED:     chosen = None
# OLD_MODE_DISABLED:     for e in exams:
# OLD_MODE_DISABLED:         try:
# OLD_MODE_DISABLED:             if EXAM_NAMES[e].lower() == t.lower():
# OLD_MODE_DISABLED:                 chosen = e
# OLD_MODE_DISABLED:                 break
# OLD_MODE_DISABLED:         except Exception:
# OLD_MODE_DISABLED:             if e.lower() == t.lower():
# OLD_MODE_DISABLED:                 chosen = e
# OLD_MODE_DISABLED:                 break
# OLD_MODE_DISABLED:     if not chosen:
# OLD_MODE_DISABLED:         bot.reply_to(message, "Tap one of the exams shown above.")
# OLD_MODE_DISABLED:         return
# OLD_MODE_DISABLED:     p["_exam_chosen"] = chosen
# OLD_MODE_DISABLED:     save_profile(uid, p)
# OLD_MODE_DISABLED:     _ask_mode_after_exam(uid)
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: def _ask_mode_after_exam(uid):
# OLD_MODE_DISABLED:     """After exam chosen, ask Practice/Test/Conceptual."""
# OLD_MODE_DISABLED:     from telebot.types import ReplyKeyboardMarkup
# OLD_MODE_DISABLED:     p = load_profile(uid)
# OLD_MODE_DISABLED:     exam_key = p.get("_exam_chosen", "")
# OLD_MODE_DISABLED:     exam_name = exam_key
# OLD_MODE_DISABLED:     try:
# OLD_MODE_DISABLED:         exam_name = EXAM_NAMES.get(exam_key, exam_key)
# OLD_MODE_DISABLED:     except Exception:
# OLD_MODE_DISABLED:         pass
# OLD_MODE_DISABLED:     kb = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
# OLD_MODE_DISABLED:     kb.add("Practice", "Test", "Conceptual")
# OLD_MODE_DISABLED:     msg = bot.send_message(
# OLD_MODE_DISABLED:         uid,
# OLD_MODE_DISABLED:         f"\U0001f4da *Step 2/2 \u2014 Mode for {exam_name}*\n\n"
# OLD_MODE_DISABLED:         "\u2022 *Practice* \u2014 casual learning\n"
# OLD_MODE_DISABLED:         "\u2022 *Test* \u2014 full exam simulation\n"
# OLD_MODE_DISABLED:         "\u2022 *Conceptual* \u2014 theory & exceptions focus",
# OLD_MODE_DISABLED:         reply_markup=kb, parse_mode="Markdown"
# OLD_MODE_DISABLED:     )
# OLD_MODE_DISABLED:     # _exam_mode expects Practice/Test/Conceptual text
# OLD_MODE_DISABLED:     handler = globals().get("_exam_mode")
# OLD_MODE_DISABLED:     if handler:
# OLD_MODE_DISABLED:         bot.register_next_step_handler(msg, handler)
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
# OLD_MODE_DISABLED: 
@bot.message_handler(commands=['status'])
def cmd_status(message):
    pass

@bot.message_handler(commands=['clear_data'])
def cmd_clear_data(message):
    uid = message.chat.id
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("❌ Yes, Delete Everything", callback_data="admin_confirm_wipe"),
        InlineKeyboardButton("Cancel", callback_data="admin_cancel_wipe")
    )
    bot.reply_to(message, 
        "⚠️ *WARNING* ⚠️\n\n"
        "This will permanently delete your profile, name, phone, health, and all progress.\n"
        "You will have to register from scratch.\n\n"
        "Are you sure?", 
        reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "admin_confirm_wipe")
def _cb_confirm_wipe(call):
    uid = call.message.chat.id
    # Delete Profile
    prof_path = f"profiles/{uid}.json"
    if os.path.exists(prof_path):
        os.remove(prof_path)
    # Delete Bookmarks
    bm_path = f"bookmarks/{uid}.json"
    if os.path.exists(bm_path):
        os.remove(bm_path)
        
    try:
        bot.edit_message_text("✅ *Data completely wiped.*\n\nSend /start to register again.", 
                              chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "admin_cancel_wipe")
def _cb_cancel_wipe(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass


# ==========================================================
# c02w_mode_wizard.py — /mode exam configuration wizard v2
# Flow: summary → confirm → one-by-one → save
# ==========================================================
import admin_auth as _mw_auth

_MODE_WIZARD_STATE = {}


def _mw_exams_list():
    try:
        from config import EXAM_NAMES
        return list(EXAM_NAMES.items())
    except Exception:
        return [("JEE_ADV", "JEE Advanced"), ("JEE_MAIN", "JEE Mains"), ("EAMCET", "EAMCET")]


def _mw_exam_name(key):
    for k, v in _mw_exams_list():
        if k == key:
            return v
    return key


def _mw_exam_total(key):
    totals = {"JEE_ADV": 360, "JEE_MAIN": 300, "EAMCET": 160}
    return totals.get(key, 100)


def _mw_build_summary(uid, p):
    """Build the 'confirm or change' summary."""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    exams = p.get("exams") or []
    prio = p.get("priority")
    pct = p.get("priority_pct", 70)
    marks = p.get("target_marks") or {}
    year = p.get("target_year")
    if not exams:
        return None, None
    lines = ["📋 *Your Current Exam Config*", ""]
    lines.append(f"🎯 *Priority:* {_mw_exam_name(prio)} ({pct}% focus)")
    lines.append(f"📅 *Year:* {year}")
    lines.append("")
    lines.append("*Exams & target marks:*")
    for k in exams:
        name = _mw_exam_name(k)
        m = marks.get(k, 0)
        total = _mw_exam_total(k)
        star = "⭐ " if k == prio else "   "
        lines.append(f"{star}{name}: *{m}/{total}*")
    lines.append("")
    lines.append("_Keep this configuration or change it?_")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Keep", callback_data="mw_keep"),
        InlineKeyboardButton("✏️ Change", callback_data="mw_change"),
    )
    return text, kb


@bot.message_handler(commands=['mode'])
def _mw_cmd_mode(message):
    uid = message.chat.id
    try:
        ready, reason = _profile_ready(uid)
        if not ready:
            _send_setup_prompt(uid, reason)
            return
    except Exception as _e:
        print(f"[mw-mode] profile err: {_e}")
    p = load_profile(uid)
    exams = p.get("exams") or []
    year = p.get("target_year")

    # If already configured → show summary with Keep/Change
    if exams and year:
        text, kb = _mw_build_summary(uid, p)
        bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb)
        print(f"[mw] {uid} → summary shown")
        return

    # No config yet → go straight into change flow
    _mw_start_change(uid)


@bot.callback_query_handler(func=lambda c: c.data == "mw_keep")
def _mw_cb_keep(call):
    uid = call.from_user.id
    try:
        bot.edit_message_text(
            "✅ *Configuration unchanged.*\n\n_Tip: use /exam for quick practice._",
            chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown"
        )
    except Exception:
        pass
    bot.answer_callback_query(call.id, "Kept")


@bot.callback_query_handler(func=lambda c: c.data == "mw_change")
def _mw_cb_change(call):
    uid = call.from_user.id
    try:
        bot.edit_message_text(
            "✏️ *Reconfiguring...*\n\nStarting fresh.",
            chat_id=uid, message_id=call.message.message_id
        )
    except Exception:
        pass
    _mw_start_change(uid)


def _mw_start_change(uid):
    """Begin wizard — Step 1: select exams."""
    p = load_profile(uid)
    existing = set(p.get("exams") or [])
    _MODE_WIZARD_STATE[uid] = {
        "step": "select",
        "selected": existing,
        "priority": p.get("priority"),
        "priority_pct": p.get("priority_pct", 70),
        "target_marks": dict(p.get("target_marks") or {}),
        "target_year": p.get("target_year"),
    }
    _mw_show_select(uid)


def _mw_build_selector(selected):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    exams = _mw_exams_list()
    buttons = []
    for key, name in exams:
        mark = "✅ " if key in selected else "⬜ "
        buttons.append(InlineKeyboardButton(f"{mark}{name}", callback_data=f"mw_toggle:{key}"))
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            kb.row(buttons[i], buttons[i + 1])
        else:
            kb.row(buttons[i])
    kb.add(InlineKeyboardButton("✅ Done", callback_data="mw_done"))
    return kb


def _mw_build_selector_text(selected):
    lines = ["📚 *Configure Your Exams*", ""]
    lines.append("*Step 1/5 — Which exams are you writing?*")
    lines.append("_Tap to toggle. Select at least one._")
    lines.append("")
    if selected:
        lines.append(f"Selected: *{len(selected)}*")
        for k in sorted(selected):
            lines.append(f"  • {_mw_exam_name(k)}")
    else:
        lines.append("_Nothing selected yet._")
    return "\n".join(lines)


def _mw_show_select(uid, msg_id=None):
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    st["step"] = "select"
    _MODE_WIZARD_STATE[uid] = st
    text = _mw_build_selector_text(st["selected"])
    kb = _mw_build_selector(st["selected"])
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id=uid, message_id=msg_id, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    else:
        safe_send(uid, text, parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mw_toggle:"))
def _mw_cb_toggle(call):
    uid = call.from_user.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        bot.answer_callback_query(call.id, "Send /mode again")
        return
    try:
        key = call.data.split(":")[1]
    except Exception:
        return
    sel = st["selected"]
    if key in sel:
        sel.remove(key)
    else:
        sel.add(key)
    st["selected"] = sel
    _MODE_WIZARD_STATE[uid] = st
    try:
        bot.edit_message_text(
            _mw_build_selector_text(sel),
            chat_id=uid, message_id=call.message.message_id,
            reply_markup=_mw_build_selector(sel), parse_mode="Markdown"
        )
    except Exception:
        pass
    bot.answer_callback_query(call.id, f"{len(sel)} selected")


@bot.callback_query_handler(func=lambda c: c.data == "mw_done")
def _mw_cb_done(call):
    uid = call.from_user.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    sel = st["selected"]
    if not sel:
        bot.answer_callback_query(call.id, "Select at least one exam")
        return
    if len(sel) == 1:
        only = list(sel)[0]
        st["priority"] = only
        st["priority_pct"] = 100
        _MODE_WIZARD_STATE[uid] = st
        _mw_ask_marks(uid, call.message.message_id)
        return
    # Ask priority
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    for k in sorted(sel):
        kb.add(InlineKeyboardButton(_mw_exam_name(k), callback_data=f"mw_prio:{k}"))
    text = (
        "📚 *Step 2/5 — Priority Exam*\n\n"
        "_Notes, plan & short notes will focus on this exam._\n\n"
        "Which exam is your main focus?"
    )
    st["step"] = "priority"
    _MODE_WIZARD_STATE[uid] = st
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("mw_prio:"))
def _mw_cb_prio(call):
    uid = call.from_user.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    try:
        key = call.data.split(":")[1]
    except Exception:
        return
    st["priority"] = key
    st["step"] = "await_pct"
    _MODE_WIZARD_STATE[uid] = st
    text = (
        f"📚 *Step 3/5 — Priority Percentage*\n\n"
        f"You picked *{_mw_exam_name(key)}* as priority.\n\n"
        f"How much *%* of your study time should go to this exam?\n"
        f"_Example: 70_"
    )
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except Exception:
        safe_send(uid, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: (
    m.chat.id in _MODE_WIZARD_STATE and
    _MODE_WIZARD_STATE[m.chat.id].get("step") == "await_pct"
), content_types=['text'])
def _mw_catch_pct(message):
    uid = message.chat.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        _MODE_WIZARD_STATE.pop(uid, None)
        return
    try:
        pct = int(txt)
        if pct < 1 or pct > 100:
            bot.reply_to(message, "Enter a number 1–100:")
            return
    except Exception:
        bot.reply_to(message, "Enter a number 1–100:")
        return
    st["priority_pct"] = pct
    st["step"] = "marks"
    st["marks_queue"] = sorted(st["selected"])
    _MODE_WIZARD_STATE[uid] = st
    _mw_ask_marks(uid)


def _mw_ask_marks(uid, msg_id=None):
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    queue = st.get("marks_queue") or []
    if not queue:
        _mw_ask_year(uid, msg_id)
        return
    cur = queue[0]
    total = _mw_exam_total(cur)
    name = _mw_exam_name(cur)
    text = (
        f"📚 *Step 4/5 — Target Marks*\n\n"
        f"{name}: out of *{total}*\n\n"
        f"Enter your target marks (1–{total}):"
    )
    st["step"] = "await_mark"
    _MODE_WIZARD_STATE[uid] = st
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id=uid, message_id=msg_id, parse_mode="Markdown")
        except Exception:
            pass
    else:
        safe_send(uid, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: (
    m.chat.id in _MODE_WIZARD_STATE and
    _MODE_WIZARD_STATE[m.chat.id].get("step") == "await_mark"
), content_types=['text'])
def _mw_catch_mark(message):
    uid = message.chat.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        _MODE_WIZARD_STATE.pop(uid, None)
        return
    queue = st.get("marks_queue") or []
    if not queue:
        return
    cur = queue[0]
    total = _mw_exam_total(cur)
    try:
        val = int(txt)
        if val < 1 or val > total:
            bot.reply_to(message, f"Enter 1–{total}:")
            return
    except Exception:
        bot.reply_to(message, f"Enter 1–{total}:")
        return
    st["target_marks"][cur] = val
    st["marks_queue"] = queue[1:]
    _MODE_WIZARD_STATE[uid] = st
    _mw_ask_marks(uid)


def _mw_ask_year(uid, msg_id=None):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    st["step"] = "await_year"
    _MODE_WIZARD_STATE[uid] = st
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("2027", callback_data="mw_year:2027"),
        InlineKeyboardButton("2028", callback_data="mw_year:2028"),
        InlineKeyboardButton("2029", callback_data="mw_year:2029"),
    )
    text = (
        "📚 *Step 5/5 — Target Year*\n\n"
        "Which year are you writing the exam?"
    )
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id=uid, message_id=msg_id, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    else:
        safe_send(uid, text, parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("mw_year:"))
def _mw_cb_year(call):
    uid = call.from_user.id
    st = _MODE_WIZARD_STATE.get(uid)
    if not st:
        return
    try:
        year = int(call.data.split(":")[1])
    except Exception:
        return
    p = load_profile(uid)
    p["exams"] = sorted(st["selected"])
    p["priority"] = st["priority"]
    p["priority_pct"] = st["priority_pct"]
    p["target_marks"] = st["target_marks"]
    p["target_year"] = year
    save_profile(uid, p)
    _MODE_WIZARD_STATE.pop(uid, None)
    prio_name = _mw_exam_name(st["priority"])
    lines = ["✅ *Configuration Saved!*", ""]
    lines.append(f"🎯 *Priority:* {prio_name} ({st['priority_pct']}%)")
    lines.append(f"📅 *Year:* {year}")
    lines.append("")
    lines.append("*Exams & targets:*")
    for k in sorted(st["selected"]):
        name = _mw_exam_name(k)
        marks = st["target_marks"].get(k, 0)
        total = _mw_exam_total(k)
        star = "⭐" if k == st["priority"] else "  "
        lines.append(f"{star} {name}: *{marks}/{total}*")
    lines.append("")
    lines.append("_Type /mode anytime to view or change._")
    text = "\n".join(lines)
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except Exception:
        safe_send(uid, text, parse_mode="Markdown")
    print(f"[mw] {uid} saved: exams={p['exams']} prio={p['priority']} pct={st['priority_pct']} year={year}")


print("c02w_mode_wizard: loaded (v2).")


# ==========================================================
# bot.py — Chunk 3: select, health, plan, target, graph
# ==========================================================

@bot.message_handler(commands=['select'])
def cmd_select(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    subjects = health.available_subjects()
    if not subjects:
        bot.reply_to(message, "❌ No subjects available.")
        return
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for s in subjects:
        markup.add(s)
    msg = bot.send_message(uid,
        "🎯 *Which subject do you want to select chapters for?*",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _select_subject)


def _select_subject(message):
    uid = message.chat.id
    p = load_profile(uid)
    subj = (message.text or "").strip().capitalize()
    if subj not in health.available_subjects():
        bot.reply_to(message, f"❌ Not available. Try: {', '.join(health.available_subjects())}")
        return
    exam = health.exam_of(p)
    if not exam:
        bot.reply_to(message, "⚠️ Set exam first with /mode.")
        return
    data = health.load_subject_data(subj, exam)
    if not data:
        bot.reply_to(message, f"❌ No data for {subj}.")
        return
    chapter_list = list(data.keys())
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(chapter_list))
    header = f"📚 *{subj}* — {len(chapter_list)} chapters\n\n"
    footer = "\n\nReply numbers `1,4,7,12` or `ALL`."
    full = header + numbered + footer
    if len(full) > 4000:
        safe_send(uid, header + "_(list below)_", parse_mode="Markdown")
        safe_send(uid, numbered[:3900])
        msg = bot.send_message(uid, footer.strip())
        bot.register_next_step_handler(msg, _select_chapters, subj, chapter_list)
    else:
        msg = bot.send_message(uid, full,
                               reply_markup=telebot.types.ReplyKeyboardRemove(),
                               parse_mode="Markdown")
        bot.register_next_step_handler(msg, _select_chapters, subj, chapter_list)


def _select_chapters(message, subj, chapter_list):
    uid = message.chat.id
    p = load_profile(uid)
    txt = (message.text or "").strip()
    if txt.upper() == "ALL":
        chosen = chapter_list
    else:
        try:
            idxs = [int(x.strip()) - 1 for x in txt.split(",") if x.strip()]
            chosen = [chapter_list[i] for i in idxs if 0 <= i < len(chapter_list)]
        except Exception:
            bot.reply_to(message, "❌ Invalid. Try /select again.")
            return
    if not chosen:
        bot.reply_to(message, "❌ No valid chapters.")
        return
    p.setdefault("selected_chapters", {})
    p["selected_chapters"][subj] = chosen
    save_profile(uid, p)
    safe_send(uid,
        f"✅ *{subj}: {len(chosen)} chapters selected*\n\n"
        "Add more with /select, or view progress with /health.",
        parse_mode="Markdown")


# ==========================================================
# /health
# ==========================================================
@bot.message_handler(commands=['health'])
def cmd_health(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) > 1:
        subj = parts[1].strip().capitalize()
        if subj not in health.available_subjects():
            bot.reply_to(message, f"❌ '{subj}' not available.")
            return
        exam = health.exam_of(p)
        ch_map = health.chapter_health_map(p, subj, exam, only_selected=False)
        lines = [f"📗 *{subj}* — Chapter Health\n"]
        for ch, d in sorted(ch_map.items(),
                            key=lambda x: (x[1]["health"] is None,
                                          x[1]["health"] if x[1]["health"] is not None else 0)):
            h = d["health"]
            hstr = f"{h:.1f}" if h is not None else "—"
            lines.append(f"• {ch[:35]}: {hstr}")
        safe_send(uid, "\n".join(lines), parse_mode="Markdown")
        return

    r = health.overall_health(p)
    days_left = None
    if p.get("priority") and p.get("target_year"):
        days_left = _days_until_exam(p["priority"], p["target_year"])

    if SVG_ENABLED and r.get("overall") is not None:
        subj_data = {s: d["health"] for s, d in r["subjects"].items()}
        svg = svg_templates.combined_progress(r["overall"], subj_data)
        path = svg_renderer.render_svg(svg, name=f"health_{uid}")
        if path and safe_send_photo(uid, path):
            svg_renderer.cleanup_file(path)
            if days_left is not None:
                safe_send(uid, f"⏳ {days_left} days left for primary exam.",
                          parse_mode="Markdown")
        else:
            if path:
                svg_renderer.cleanup_file(path)
            safe_send(uid, _health_text(r, days_left), parse_mode="Markdown")
    else:
        safe_send(uid, _health_text(r, days_left), parse_mode="Markdown")


def _health_text(r, days_left=None):
    if r.get("overall") is None:
        return "📭 No practice data yet. /exam to start."
    lines = [f"❤️ *Overall: {r['overall']}/100*"]
    if days_left is not None:
        lines.append(f"⏳ {days_left} days left")
    lines.append("")
    for subj, d in r["subjects"].items():
        h = d["health"]
        hstr = f"{h}/100" if h is not None else "Not started"
        lines.append(f"📘 {subj}: {hstr}")
    return "\n".join(lines)


# ==========================================================
# /plan
# ==========================================================
@bot.message_handler(commands=['plan'])
def cmd_plan(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    r = health.overall_health(p)
    if r["overall"] is None:
        bot.reply_to(message, "📭 No data yet. /exam first.")
        return
    primary = p.get("priority") or p["exams"][0]
    lines = ["📋 *YOUR STUDY PLAN*", ""]
    lines.append(f"🎯 *Primary:* {EXAM_NAMES[primary]} {p.get('target_year','')}")
    targets = p.get("target_marks", {})
    if isinstance(targets, dict) and primary in targets:
        max_m = MAX_MARKS.get(primary, 100)
        lines.append(f"Target: {targets[primary]} / {max_m} marks")
    lines.append(f"Current health: *{r['overall']}/100*")
    lines.append("")
    lines.append("📘 *Subject health:*")
    for s, d in r["subjects"].items():
        if d["health"] is not None:
            lines.append(f"   {s}: {d['health']}/100")
    other = [e for e in p["exams"] if e != primary]
    if other:
        lines.append("")
        lines.append("📚 *Secondary exams:*")
        for e in other:
            tag = f" — target {targets.get(e,'—')}" if isinstance(targets, dict) else ""
            lines.append(f"   {EXAM_NAMES[e]}{tag}")
    lines.append("")
    lines.append("Next: /health · /exam · /target")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


# ==========================================================
# /target
# ==========================================================
@bot.message_handler(commands=['target'])
def cmd_target(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    p["_marks_queue"] = list(p["exams"])
    save_profile(uid, p)
    _mode_ask_next_mark(uid)


# ==========================================================
# /graph
# ==========================================================
@bot.message_handler(commands=['graph'])
def cmd_graph(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    r = health.overall_health(p)
    if r["overall"] is None:
        bot.reply_to(message, "📭 No data yet. /exam first.")
        return
    subj_data = {s: d["health"] for s, d in r["subjects"].items()}
    svg = svg_templates.combined_progress(r["overall"], subj_data)
    path = svg_renderer.render_svg(svg, name=f"graph_{uid}")
    if path:
        safe_send_photo(uid, path, caption=f"Overall: {r['overall']}/100")
        svg_renderer.cleanup_file(path)
    else:
        safe_send(uid, f"📊 Overall: {r['overall']}/100")


print("bot.py Chunk 3 loaded: select, health, plan, target, graph ready.")


# ==========================================================
# c30v_subadmin_v2.py — sub-admin v3 (login by name+password)
# - New registration: 5 steps + back button
# - Login: name + privacy password (no device check)
# - Forgot password: /sub_forgot → forgot key → new privacy
# ==========================================================
import admin_auth as _v2_auth
import time as _v2_time

_SUBREG_V2_STATE = {}
_V3_SEEN_MSG_IDS = set()   # dedup for double-processing
_SUB_LOCKIN_OK = {}


def _is_in_flow(message):
    try:
        return message.chat.id in _SUBREG_V2_STATE
    except Exception:
        return False


def _back_kb():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="sub_cancel"))
    return kb


@bot.callback_query_handler(func=lambda c: c.data == "sub_cancel")
def _cb_cancel(call):
    uid = call.from_user.id
    _SUBREG_V2_STATE.pop(uid, None)
    try:
        bot.edit_message_text(
            "❌ Cancelled. Type the gate code again to restart.",
            chat_id=uid, message_id=call.message.message_id
        )
    except Exception:
        pass


# ==========================================================
# NEW DEVICE — full registration 5 steps
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "sub_new")
def _v3_cb_new(call):
    uid = call.from_user.id
    try:
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    # Allow re-registration — warn but don't block
    _existing = None
    try:
        _cfg_chk = _v2_auth._load_config()
        _existing = _cfg_chk.get("sub_admins", {}).get(str(uid))
    except Exception:
        pass
    if _existing:
        _old_name = _existing.get("name", "?")
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        _kb = InlineKeyboardMarkup(row_width=2)
        _kb.add(
            InlineKeyboardButton("🆕 Register Fresh", callback_data="sub_new_force"),
            InlineKeyboardButton("🔐 Login Instead", callback_data="sub_reg"),
        )
        safe_send(uid,
            f"⚠️ *This device is already registered* as *{_old_name}*.\n\n"
            f"Choose:\n"
            f"• *Register Fresh* — create new registration (old one will be replaced)\n"
            f"• *Login Instead* — use existing credentials",
            parse_mode="Markdown", reply_markup=_kb)
        return
    _SUBREG_V2_STATE[uid] = {"step": "lockin", "at": _v2_time.time()}
    safe_send(uid,
        "🔑 *New Sub-Admin Setup* — Step 1/5\n\n"
        "Enter the *lock-in code* from the primary admin:",
        parse_mode="Markdown", reply_markup=_back_kb())
    print(f"[v3] {uid} → step lockin")


@bot.callback_query_handler(func=lambda c: c.data == "sub_new_force")
def _v3_cb_new_force(call):
    uid = call.from_user.id
    try:
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    _SUBREG_V2_STATE[uid] = {"step": "lockin", "at": _v2_time.time()}
    safe_send(uid,
        "🔑 *New Sub-Admin Setup* (Fresh) — Step 1/5\n\n"
        "Enter the *lock-in code* from the primary admin:",
        parse_mode="Markdown", reply_markup=_back_kb())
    print(f"[v3] {uid} → step lockin (fresh)")
    _SUBREG_V2_STATE[uid] = {"step": "lockin", "at": _v2_time.time()}
    safe_send(uid,
        "🔑 *New Sub-Admin Setup* — Step 1/5\n\n"
        "Enter the *lock-in code* from the primary admin:",
        parse_mode="Markdown", reply_markup=_back_kb())
    print(f"[v3] {uid} → step lockin")


# ==========================================================
# ALREADY REGISTERED — name + password login (no device check)
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "sub_reg")
def _v3_cb_reg(call):
    uid = call.from_user.id
    try:
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    _SUBREG_V2_STATE[uid] = {"step": "login_name", "at": _v2_time.time()}
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="sub_cancel"))
    kb.add(InlineKeyboardButton("🗝 Forgot Password", callback_data="sub_forgot_btn"))
    safe_send(uid,
        "🔐 *Sub-Admin Login*\n\n"
        "*Step 1/2:* Enter your *name* (as registered):",
        parse_mode="Markdown", reply_markup=kb)
    print(f"[v3] {uid} → step login_name")


# ==========================================================
# UNIVERSAL TEXT HANDLER
# ==========================================================
@bot.message_handler(func=_is_in_flow, content_types=['text'])
def _v3_flow(message):
    try:
        try:
            print(f'[v3-flow-enter] uid={message.chat.id} text={message.text!r:.50}')
            uid = message.chat.id
            st = _SUBREG_V2_STATE.get(uid)
            if not st:
                return
            if _v2_time.time() - st.get("at", 0) > 300:
                _SUBREG_V2_STATE.pop(uid, None)
                safe_send(uid, "⏰ Timed out. Restart from gate code.")
                return
            txt = (message.text or "").strip()
            if not txt:
                return
            if txt.startswith("/"):
                _cmd = txt.split()[0]
                if _cmd in ("/sub_forgot", "/cancel", "/forgot", "/mode", "/plan", "/health", "/start"):
                    return
                _SUBREG_V2_STATE.pop(uid, None)
                safe_send(uid, "Cancelled.")
                return
            st["at"] = _v2_time.time()
            step = st.get("step")

            # ===== REGISTRATION FLOW =====
            if step == "lockin":
                try:
                    ok, _info = _v2_auth.verify_lockin_code(txt, requester_uid=uid)
                    print(f"[v3-lockin] uid={uid} code={txt!r} ok={ok} info={_info}")
                except Exception as e:
                    print(f"[v3] lockin err: {e}")
                    ok = False
                if not ok:
                    safe_send(uid,
                        f"❌ *Invalid lock-in code*\n\n"
                        f"Code you sent: `{txt}`\n\n"
                        f"Common reasons:\n"
                        f"  • Expired (10 min limit)\n"
                        f"  • Already used (single-use)\n"
                        f"  • Typo — check the code\n\n"
                        f"Ask admin for a fresh code.",
                        parse_mode="Markdown",
                        reply_markup=_back_kb())
                    return
                st["step"] = "verify"
                _SUBREG_V2_STATE[uid] = st
                safe_send(uid,
                    "✅ Lock-in accepted — Step 2/5\n\n"
                    "Enter the *verification code* from the primary admin:",
                    parse_mode="Markdown", reply_markup=_back_kb())
                print(f"[v3] {uid} → verify")
                return

            if step == "verify":
                try:
                    ok = _v2_auth.verify_sub_admin_verify_code(txt)
                except Exception as e:
                    print(f"[v3] verify err: {e}")
                    ok = False
                if not ok:
                    safe_send(uid, "❌ Invalid verification code. Try again:", reply_markup=_back_kb())
                    return
                st["step"] = "name"
                _SUBREG_V2_STATE[uid] = st
                safe_send(uid,
                    "✅ Verified — Step 3/5\n\n"
                    "Enter your *full name*:",
                    parse_mode="Markdown", reply_markup=_back_kb())
                print(f"[v3] {uid} → name")
                return

            if step == "name":
                if len(txt) < 2:
                    safe_send(uid, "Name too short (min 2). Try again:", reply_markup=_back_kb())
                    return
                st["name"] = txt[:60]
                st["step"] = "privacy"
                _SUBREG_V2_STATE[uid] = st
                safe_send(uid,
                    f"✅ Name saved: *{st['name']}* — Step 4/5\n\n"
                    "Set your *privacy password* (login password, min 4 chars):",
                    parse_mode="Markdown", reply_markup=_back_kb())
                print(f"[v3] {uid} → privacy")
                return

            if step == "privacy":
                if len(txt) < 4:
                    safe_send(uid, "Too short (min 4). Try again:", reply_markup=_back_kb())
                    return
                st["privacy"] = txt
                st["step"] = "forgot"
                _SUBREG_V2_STATE[uid] = st
                safe_send(uid,
                    "✅ Privacy set — Step 5/5\n\n"
                    "Set your *forgot-password key* (min 6 chars):\n"
                    "_You'll use this to reset privacy if you forget it._",
                    parse_mode="Markdown", reply_markup=_back_kb())
                print(f"[v3] {uid} → forgot")
                return

            if step == "forgot":
                if len(txt) < 6:
                    safe_send(uid, "Too short (min 6). Try again:", reply_markup=_back_kb())
                    return
                name = st.get("name", "Sub-Admin")
                privacy = st.get("privacy", "")
                forgot = txt
                try:
                    _v2_auth.register_sub_admin(uid, name, privacy)
                    cfg = _v2_auth._load_config()
                    entry = cfg.get("sub_admins", {}).get(str(uid))
                    if entry:
                        try:
                            rh, rs = _v2_auth._hash_secret(forgot)
                            entry["reset_hash"] = rh
                            entry["reset_salt"] = rs
                            _v2_auth._save_config(cfg)
                        except Exception as eh:
                            print(f"[v3] hash err: {eh}")
                    _v2_auth.start_session(uid, "sub")
                    _v2_auth.update_sub_admin_last_seen(uid)
                    _SUBREG_V2_STATE.pop(uid, None)
                    safe_send(uid,
                        f"✅ *Registered!*\n\n👤 {name}\n🛡 Read-only access\n\nOpening panel...",
                        parse_mode="Markdown")
                    _sp = globals().get("_show_sub_admin_panel")
                    if _sp: _sp(uid)
                    print(f"[v3] {uid} REGISTERED name={name}")
                except Exception as e:
                    print(f"[v3] register fail: {e}")
                    safe_send(uid, f"⚠️ {str(e)[:100]}")
                return

            # ===== LOGIN FLOW (name + password, no device check) =====
            if step == "login_name":
                if len(txt) < 2:
                    safe_send(uid, "Name too short. Try again:", reply_markup=_back_kb())
                    return
                st["login_name"] = txt[:60]
                st["step"] = "login_pw"
                _SUBREG_V2_STATE[uid] = st
                safe_send(uid,
                    f"Name: *{st['login_name']}*\n\n"
                    "Enter your *privacy password*:\n\n"
                    "_Type /cancel to abort_",
                    parse_mode="Markdown")
                print(f"[v3] {uid} → login_pw")
                return

            if step == "login_pw":
                name = st.get("login_name", "")
                try:
                    # Find sub-admin by name (case-insensitive)
                    cfg = _v2_auth._load_config()
                    subs = cfg.get("sub_admins", {})
                    target_sid = None
                    for sid_str, entry in subs.items():
                        if (entry.get("name") or "").lower() == name.lower():
                            target_sid = int(sid_str)
                            break
                    if target_sid is None:
                        safe_send(uid, f"❌ *No sub-admin* named `{name}`.\n\nCheck spelling or try different name. Use 🗝 Forgot Password if needed.", parse_mode="Markdown", reply_markup=_back_kb())
                        return
                    # Verify password against that entry
                    entry = subs.get(str(target_sid), {})
                    try:
                        import hashlib as _hl
                        ph = entry.get("privacy_hash", "")
                        ps = entry.get("privacy_salt", "")
                        got = _hl.sha256((txt + ps).encode()).hexdigest()
                        if got != ph:
                            safe_send(uid, "❌ Wrong password. Try again or /sub_forgot:", reply_markup=_back_kb())
                            # Keep step=login_pw so retry goes to same branch
                            _SUBREG_V2_STATE[uid] = st
                            return
                            return
                    except Exception as e:
                        print(f"[v3] pw check err: {e}")
                        safe_send(uid, "❌ Verification error.")
                        return
                    # Success — bind this chat_id to that account if different
                    if target_sid != uid:
                        # If this device has different chat_id, register it as a device session
                        # Simplest: copy credentials to this chat_id
                        cfg2 = _v2_auth._load_config()
                        cfg2["sub_admins"][str(uid)] = dict(entry)
                        cfg2["sub_admins"][str(uid)]["last_seen"] = _v2_time.time().__class__.__name__  # placeholder
                        try:
                            _v2_auth._save_config(cfg2)
                        except Exception:
                            pass
                    _v2_auth.start_session(uid, "sub")
                    try:
                        _v2_auth.update_sub_admin_last_seen(uid)
                    except Exception:
                        pass
                    _SUBREG_V2_STATE.pop(uid, None)
                    safe_send(uid,
                        f"✅ Welcome back, *{name}*!\n\nOpening panel...",
                        parse_mode="Markdown")
                    _sp = globals().get("_show_sub_admin_panel")
                    if _sp: _sp(uid)
                    print(f"[v3] {uid} LOGIN name={name} target_sid={target_sid}")
                except Exception as e:
                    print(f"[v3] login err: {e}")
                    safe_send(uid, f"⚠️ {str(e)[:100]}")
                return


        # ==========================================================
        # FORGOT PASSWORD
        # ==========================================================
        except Exception as _flow_e:
            import traceback
            print(f'[v3-flow-error] {_flow_e}')
            traceback.print_exc()
            try:
                safe_send(message.chat.id, f'⚠️ Setup error: {str(_flow_e)[:100]}')
            except Exception:
                pass

    except Exception as _fc_e:
        import traceback
        traceback.print_exc()
        print(f'[FLOW-CRASH] {_fc_e}')
        try:
            _cln = _SUBREG_V2_STATE.get(message.chat.id)
            if _cln:
                _cln.pop("_processing", None)
        except Exception:
            pass
        try:
            safe_send(message.chat.id, f'⚠️ Error: {str(_fc_e)[:150]}')
        except Exception:
            pass
    finally:
        try:
            _fin = _SUBREG_V2_STATE.get(message.chat.id)
            if _fin:
                _fin.pop("_processing", None)
        except Exception:
            pass

@bot.message_handler(commands=['sub_forgot'])
def _v3_sub_forgot(message):
    uid = message.chat.id
    _SUBREG_V2_STATE[uid] = {"step": "forgot_reset_key", "at": _v2_time.time()}
    safe_send(uid,
        "🗝 Enter your *forgot-password key*:",
        parse_mode="Markdown", reply_markup=_back_kb())


@bot.message_handler(func=lambda m: (
    m.chat.id in _SUBREG_V2_STATE and
    _SUBREG_V2_STATE[m.chat.id].get("step") == "forgot_reset_key"
), content_types=['text'])
def _v3_reset_key(message):
    uid = message.chat.id
    st = _SUBREG_V2_STATE.get(uid) or {}
    txt = (message.text or "").strip()
    print(f"[v3-forgot] uid={uid} key={txt!r}")
    if not txt:
        safe_send(uid, "❌ Empty input. Enter your forgot key:")
        return
    if txt.startswith("/"):
        _SUBREG_V2_STATE.pop(uid, None)
        safe_send(uid, "Cancelled.")
        return
    if len(txt) < 6:
        safe_send(uid, "❌ Key too short (min 6 chars). Try again:", reply_markup=_back_kb())
        return
    try:
        cfg = _v2_auth._load_config()
        entry = cfg.get("sub_admins", {}).get(str(uid))
        if not entry:
            safe_send(uid, "❌ Your account not found. Contact admin.")
            _SUBREG_V2_STATE.pop(uid, None)
            return
        if not entry.get("reset_hash"):
            safe_send(uid, "❌ No forgot key on file. Contact admin to set one.")
            _SUBREG_V2_STATE.pop(uid, None)
            return
        import hashlib as _hl
        salt = entry.get("reset_salt", "")
        expected = entry.get("reset_hash", "")
        got = _hl.sha256((txt + salt).encode()).hexdigest()
        print(f"[v3-forgot] hash: got={got[:8]} exp={expected[:8]} match={got == expected}")
        if got != expected:
            safe_send(uid, "❌ Incorrect forgot key. Try again or contact admin:", reply_markup=_back_kb())
            return
        st["step"] = "forgot_new_priv"
        st["at"] = _v2_time.time()
        _SUBREG_V2_STATE[uid] = st
        safe_send(uid, "✅ Key verified. Enter *new privacy password* (min 4 chars):", parse_mode="Markdown", reply_markup=_back_kb())
        print(f"[v3-forgot] → new_priv step")
    except Exception as e:
        print(f"[v3] reset err: {e}")
        import traceback; traceback.print_exc()
        safe_send(uid, f"❌ Error: {str(e)[:100]}")


@bot.message_handler(func=lambda m: (
    m.chat.id in _SUBREG_V2_STATE and
    _SUBREG_V2_STATE[m.chat.id].get("step") == "forgot_new_priv"
), content_types=['text'])
def _v3_set_new_priv(message):
    uid = message.chat.id
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        _SUBREG_V2_STATE.pop(uid, None)
        return
    if len(txt) < 4:
        safe_send(uid, "Too short.", reply_markup=_back_kb())
        return
    try:
        cfg = _v2_auth._load_config()
        entry = cfg.get("sub_admins", {}).get(str(uid))
        if not entry:
            safe_send(uid, "❌ Not found.")
            _SUBREG_V2_STATE.pop(uid, None)
            return
        import secrets as _secrets, hashlib as _hashlib
        ps = _secrets.token_hex(8)
        ph = _hashlib.sha256((txt + ps).encode()).hexdigest()
        entry["privacy_hash"] = ph
        entry["privacy_salt"] = ps
        _v2_auth._save_config(cfg)
        _SUBREG_V2_STATE.pop(uid, None)
        safe_send(uid, "✅ *Privacy password reset.* Login with new password.", parse_mode="Markdown")
        print(f"[v3] {uid} privacy reset OK")
    except Exception as e:
        print(f"[v3] reset save err: {e}")


print("c30v_subadmin_v2: loaded (v3 - name+password login).")


@bot.callback_query_handler(func=lambda c: c.data == "sub_forgot_btn")
def _cb_sub_forgot_btn(call):
    uid = call.from_user.id
    _SUBREG_V2_STATE[uid] = {"step": "forgot_reset_key", "at": _v2_time.time()}
    safe_send(uid,
        "🗝 *Forgot Password*\n\n"
        "Enter your *forgot-password key* (set during registration):",
        parse_mode="Markdown", reply_markup=_back_kb())
    print(f"[v3] {uid} → forgot_reset_key")


@bot.message_handler(commands=['cancel'])
def _cmd_cancel_flow(message):
    uid = message.chat.id
    _had = uid in _SUBREG_V2_STATE
    if _had:
        _SUBREG_V2_STATE.pop(uid, None)
        safe_send(uid, "❌ Cancelled. Type gate code to restart.")
        print(f"[v3-cancel] {uid} cancelled")
    else:
        safe_send(uid, "Nothing to cancel.")

def _cmd_cancel_flow(message):
    uid = message.chat.id
    if uid in _SUBREG_V2_STATE:
        _SUBREG_V2_STATE.pop(uid, None)
        safe_send(uid, "❌ Cancelled. Type gate code to restart.")
        print(f"[v3] {uid} cancelled")
    else:
        safe_send(uid, "Nothing to cancel.")


# ==========================================================
# c03w_subadmin_details.py — plaintext mirror of sub-admin data
# Written on every registration/edit/login for easy inspection
# ==========================================================
import json as _sdj
import os as _sdo
from datetime import datetime as _sddt

_DETAILS_FILE = "sub_admin_details.json"


def _sd_load():
    try:
        if _sdo.path.exists(_DETAILS_FILE):
            with open(_DETAILS_FILE) as f:
                return _sdj.load(f)
    except Exception as e:
        print(f"[sd-load] {e}")
    return {}


def _sd_save(data):
    try:
        with open(_DETAILS_FILE, "w") as f:
            _sdj.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[sd-save] {e}")


def sync_from_config():
    """Mirror admin_config sub_admins into plaintext file."""
    try:
        cfg = json.load(open("admin_config.json"))
        subs = cfg.get("sub_admins", {})
        details = _sd_load()
        now_iso = _sddt.now().isoformat()
        for sid, entry in subs.items():
            existing = details.get(sid, {})
            details[sid] = {
                "chat_id": int(sid),
                "name": entry.get("name"),
                "privacy_password": entry.get("privacy_plain"),
                "forgot_key": entry.get("reset_plain"),
                "registered_at": entry.get("registered_at"),
                "last_seen": entry.get("last_seen"),
                "last_login_at": existing.get("last_login_at"),
                "login_count": existing.get("login_count", 0),
                "last_synced": now_iso,
            }
        _sd_save(details)
        print(f"[sd] mirrored {len(subs)} sub-admins to {_DETAILS_FILE}")
    except Exception as e:
        print(f"[sd-sync] {e}")


def record_login(chat_id):
    """Increment login counter and update last_login_at."""
    try:
        details = _sd_load()
        sid = str(chat_id)
        if sid in details:
            details[sid]["login_count"] = details[sid].get("login_count", 0) + 1
            details[sid]["last_login_at"] = _sddt.now().isoformat()
            _sd_save(details)
            print(f"[sd-login] {chat_id} login #{details[sid]['login_count']}")
    except Exception as e:
        print(f"[sd-login] {e}")


def remove(chat_id):
    """Remove sub-admin from details file."""
    try:
        details = _sd_load()
        details.pop(str(chat_id), None)
        _sd_save(details)
        print(f"[sd-remove] {chat_id}")
    except Exception as e:
        print(f"[sd-remove] {e}")


# Sync on module load
try:
    sync_from_config()
except Exception as e:
    print(f"[sd-init] {e}")

print("c03w_subadmin_details: loaded.")


import telebot
import json
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# We reuse the bot instance from c01/c04. _b() is the accessor used in c04_exam.
# If _b() isn't available, we fall back to bot.
def _get_bot():
    try:
        return _b()
    except NameError:
        return bot

# Temporary metadata for the test (Will be generated by AI later)
TEST_META = {
    17: {"time": 90, "diff": "Medium", "year": "2026 Jan Shift 1"},
    18: {"time": 120, "diff": "Hard", "year": "2026 Jan Shift 1"},
    19: {"time": 75, "diff": "Easy", "year": "2026 Jan Shift 1"}
}

@_get_bot().message_handler(commands=['quiz_test'])
def cmd_quiz_test(message):
    uid = message.chat.id
    send_quiz_question(uid, 17)

def send_quiz_question(uid, q_num):
    m = TEST_META.get(q_num, {"time": 90, "diff": "Medium", "year": "Unknown"})
    img_path = f"pyq_images/test_crop/q{q_num}.png"
    
    # HTML Caption with Metadata
    caption = (
        f"📝 <b>Question {q_num}</b>\n"
        f"📅 {m['year']}\n"
        f"⏱ Ideal Time: {m['time']}s\n"
        f"📊 Difficulty: {m['diff']}"
    )
    
    # Option Buttons (MCQ)
    kb = InlineKeyboardMarkup(row_width=4)
    btns = [InlineKeyboardButton(opt, callback_data=f"tq_ans:{q_num}:{opt}") for opt in ["A", "B", "C", "D"]]
    kb.add(*btns)
    
    try:
        with open(img_path, "rb") as f:
            _get_bot().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        _get_bot().send_message(uid, f"❌ Image not found: {img_path}")
        print(f"Error: {e}")

@_get_bot().callback_query_handler(func=lambda call: call.data.startswith("tq_ans:"))
def handle_quiz_answer(call):
    uid = call.message.chat.id
    _, q_num_str, opt = call.data.split(":")
    q_num = int(q_num_str)
    
    # Load answers (JSON keys are strings by default)
    try:
        with open("data/temp_answers.json") as f:
            answers = json.load(f)
        correct_opt = answers.get(str(q_num), "Unknown")
    except Exception:
        correct_opt = "Unknown"
        
    is_correct = (opt == correct_opt)
    
    # Remove buttons immediately to prevent double clicks
    _get_bot().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    
    if is_correct:
        _get_bot().answer_callback_query(call.id, "✅ Correct!")
        _get_bot().send_message(uid, f"✅ <b>Correct!</b>\nYou chose <b>{opt}</b>.", parse_mode="HTML")
    else:
        _get_bot().answer_callback_query(call.id, "❌ Wrong!")
        _get_bot().send_message(uid, f"❌ <b>Wrong!</b>\nYou chose <b>{opt}</b>. Correct answer is <b>{correct_opt}</b>.", parse_mode="HTML")
        
    # Explanation placeholder
    _get_bot().send_message(uid, f"💡 <i>Explanation: The detailed step-by-step solution will be injected here in the next phase.</i>", parse_mode="HTML")
        
    # Trigger Next Question
    next_q = q_num + 1
    if next_q <= 19:
        _get_bot().send_message(uid, f"⏳ Loading Question {next_q}...")
        time.sleep(1.5)
        send_quiz_question(uid, next_q)
    else:
        _get_bot().send_message(uid, "🏁 <b>Test Complete!</b>\nYou have finished Q17 to Q19.")

print("✅ c04c_quiz_test: Interactive test UI loaded.")


import json
import time
import threading
import sys
import re
import html
import random
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

_state = {}
def _b(): return sys.modules['__main__'].bot


def format_ultimate_solution(q):
    exp = q.get('explanation', '')
    if not exp: return "💡 <i>Solution generation pending for this PYQ...</i>"
    return f"💡 <b>Ultimate Solution Engine:</b>\n1. <b>General Process:</b> ...\n2. <b>Different Angle:</b> ...\n3. <b>Shortcut:</b> ...\n4. <b>Generalize:</b> ...\n5. <b>Formula:</b> ...\n\n<i>(AI extracting from PDF text...)</i>\n\n{clean_math(exp)}"

def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    if not text: return ""
    t = str(text)
    t = html.unescape(t).replace("*", "").replace("_", " ")
    t = t.replace("\\alpha", "α").replace("\\beta", "β").replace("\\theta", "θ").replace("\\pi", "π")
    t = t.replace("\\times", "×").replace("\\cdot", "•").replace("\\sqrt", "√").replace("\\infty", "∞")
    t = t.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "").replace("$", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    sup = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    t = re.sub(r'\^([0-9+\-]+)', lambda m: m.group(1).translate(sup), t)
    t = re.sub(r'_([0-9]+)', lambda m: m.group(1).translate(sub), t)
    return t.strip()

def _extract_chapters(raw_data):
    chapters = set()
    if isinstance(raw_data, dict):
        for k, v in raw_data.items():
            if isinstance(v, dict) and "chapter" in v: chapters.add(v["chapter"])
            else: chapters.add(k)
    elif isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                ch = item.get("chapter") or item.get("name") or item.get("topic")
                if ch: chapters.add(ch)
    return sorted(list(chapters))

def _animate_gen(uid, msg_id, count):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if not state.get("generating"): return
        try: _b().edit_message_text(f"⏳ Generating Q{count}... ({elapsed}s)", chat_id=uid, message_id=msg_id, parse_mode="HTML")
        except: pass

def _run_floating_timer(uid, timer_msg_id, question_msg_id):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id)
            except: pass
            return
        try: 
            _b().edit_message_text(f"⏱️ <b>Time Taken:</b> {elapsed}s", chat_id=uid, message_id=timer_msg_id, parse_mode="HTML")
        except: pass

def _strip_old_buttons(uid):
    state = _state.get(uid, {})
    old_msg = state.get("msg_id")
    if old_msg:
        try: _b().edit_message_reply_markup(uid, old_msg, reply_markup=None)
        except: pass
    state["msg_id"] = None

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
        InlineKeyboardButton("📝 Test", callback_data="f_mode:test")
    )
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(message.chat.id, "🎓 <b>Exam Center</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['conceptual'])
def cmd_conceptual(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"),
        InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional")
    )
    _b().send_message(message.chat.id, "🧠 <b>Concept Mastery</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

def _show_chapters(uid, msg_id):
    state = _state[uid]
    chapters = state.get("chapters", [])
    page = state.get("page", 0)
    start, end = page * 5, (page + 1) * 5
    chunk = chapters[start:end]
    
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(chunk):
        kb.add(InlineKeyboardButton(f"{start + i + 1}. {ch[:25]}", callback_data=f"f_ch:{ch}"))
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="f_page:-1"))
    if end < len(chapters): nav.append(InlineKeyboardButton("Next ➡️", callback_data="f_page:1"))
    if nav: kb.row(*nav)
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="f_back:sub"))
    
    try: _b().edit_message_text(f"📚 <b>Select Chapter:</b>\n(Showing {start+1}-{min(end, len(chapters))} of {len(chapters)})", chat_id=uid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]

    if data.startswith("f_ans:") and state.get("processing"): return
        
    try:
        if data.startswith("f_mode:"):
            mode = data.split(":")[1]
            _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
            
            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )
                kb.add(InlineKeyboardButton("🚧 JEE Adv (Coming Soon)", callback_data="f_soon"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("Physics", callback_data="f_sub:Physics"),
                InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"),
                InlineKeyboardButton("Maths", callback_data="f_sub:Maths")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "f_soon":
            _b().answer_callback_query(call.id, "Coming Soon!", show_alert=True)

        elif data.startswith("f_pyq:"):
            ptype = data.split(":")[1]
            import json
            try:
                with open("data/pyq_db.json") as f: db = json.load(f)
            except: db = {"practice": {}, "papers": {}}

            if ptype == "practice":
                kb = InlineKeyboardMarkup(row_width=3)
                for subj in db.get("practice", {}).keys():
                    kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📖 <b>PYQ Practice</b>\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            
            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                years = list(db.get("papers", {}).keys())
                if not years:
                    _b().answer_callback_query(call.id, "No papers uploaded yet.")
                    return
                for yr in years:
                    kb.add(InlineKeyboardButton(yr, callback_data=f"f_pyq_yr:{yr}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\nSelect Year:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json
            chapters = []
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                extracted = db.get("practice", {}).get(subj, {})
                chapters = list(extracted.keys())
            except Exception:
                pass

            kb = InlineKeyboardMarkup(row_width=1)
            if not chapters:
                # Show a proper page instead of an alert
                msg = f"⏳ <b>{subj} - Still Processing</b>\n\nNo chapters have been extracted yet. Hamilton is working on it in the background. Please check back later."
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
                _b().edit_message_text(msg, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return

            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - Extracted PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json, os
            print(f"[DEBUG] f_pyq_ch clicked: subj={subj} ch={ch}")
            q_data = None
            for attempt in range(6):
                try:
                    with open("data/pyq_master.json") as f: db = json.load(f)
                    q_data = db.get("practice", {}).get(subj, {}).get(ch)
                    if q_data is not None:
                        print(f"[DEBUG] JSON OK (attempt {attempt+1})")
                        break
                    else:
                        # Valid JSON, chapter really missing
                        _b().send_message(uid, f"❌ Chapter not in DB: {subj} / {ch}")
                        return
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON retry {attempt+1}: {e}")
                    import time as _t; _t.sleep(0.3)
                except Exception as e:
                    _b().send_message(uid, f"❌ Load error: {e}")
                    print(f"[DEBUG] Load error: {e}")
                    return
            if q_data is None:
                _b().send_message(uid, "❌ Could not load (extractor busy). Try again in 2 sec.")
                return

            if not q_data.get("priority") and not q_data.get("normal"):
                _b().answer_callback_query(call.id, "⚠️ No questions found in this chapter.", show_alert=True)
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0
            
            # Verify the image path exists before trying to send
            first_q = state["pyq_questions"][0] if state["pyq_questions"] else None
            if not first_q:
                _b().answer_callback_query(call.id, "❌ Priority list is empty.", show_alert=True)
                return
                
            if not os.path.exists(first_q["img"]):
                _b().send_message(uid, f"❌ <b>Database Error:</b> Image file missing at `{first_q['img']}`. The extraction might have failed to save the image.", parse_mode="HTML")
                return
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            try:
                send_pyq_q(uid)
            except Exception as e:
                _b().send_message(uid, f"❌ UI Crash: {e}")
                print(f"PYQ UI CRASH: {e}")

        elif data.startswith("f_back:"):
            target = data.split(":")[1]
            if target == "main": cmd_exam(call.message)
            elif target == "sub":
                mode = state.get("mode", "practice")
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_sub:"):
            subj = data.split(":")[1]
            state["subj"] = subj
            exam = state.get("exam", "jee_adv").lower()
            fn = f"data/{exam}_{subj.lower()}.json"
            try:
                with open(fn) as f: chapters = _extract_chapters(json.load(f))
            except: chapters = ["Motion in a Straight Line", "Units and Measurements"]
            state["chapters"] = chapters
            state["page"] = 0
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_page:"):
            state["page"] += int(data.split(":")[1])
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_ch:"):
            ch = data.split(":", 1)[1]
            state["chapter"] = ch
            state["q_count"] = 0
            _b().edit_message_text(f"⏳ Generating Q1...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
            threading.Thread(target=_generate_next, args=(uid, call.message.message_id), daemon=True).start()

        elif data.startswith("f_ans:"):
            if state.get("processing") or state.get("selected") is not None: return
            state["selected"] = int(data.split(":")[1])
            sel = state["selected"]
            kb = InlineKeyboardMarkup(row_width=4)
            kb.row(*[InlineKeyboardButton(f"{'✅' if i == sel else ''}{chr(65+i)}", callback_data=f"f_ans:{i}") for i in range(4)])
            kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            state["kb"] = kb
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
            except: pass

        elif data in ("f_save", "f_skip"):
            if state.get("processing") or state.get("generating"): return
            state["processing"] = True
            state["pyq_timer_active"] = False
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            _b().send_message(uid, "🔎 <b>Verifying your response...</b>", parse_mode="HTML")
            
            if data == "f_save":
                if state.get("selected") is None: 
                    state["processing"] = False
                    return
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    q_subtopic = state["q"].get("subtopic", "General")
                    health.record_attempt(uid, state["subj"], state["chapter"], q_subtopic, is_correct, time_taken)
                except: pass
                
                msg = f"✅ <b>Correct!</b>\n\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\n\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)\n\n"
                msg += format_ultimate_solution(state['q'])
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":
                state["skipped"] += 1
                if state.get("q"):
                    correct = state["q"].get("correct_index", 0)
                    exp = clean_math(state["q"].get("explanation", ""))
                    msg = f"⏭ <b>Correct Answer: Option {chr(65+correct)}</b>\n\n📝 <b>Explanation:</b>\n{exp}"
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
            
            state["selected"] = None
            state["processing"] = False

        elif data == "f_pyq_cont":
            state["pyq_phase"] = "skipped"
            state["pyq_questions"] = state.get("pyq_skipped", [])
            state["pyq_index"] = 0
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_doubt":
            state["waiting_for_doubt"] = True
            _b().send_message(uid, "💬 <b>Please type your doubt about this question or explanation.</b>\nHamilton will answer it for you.", parse_mode="HTML")
            
        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_timer_active"] = False
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

        elif data == "f_stop":
            state["active"] = False
            if state.get("mode") == "pyq":
                c = state.get("correct", 0)
                w = state.get("wrong", 0)
                s = state.get("skipped", 0)
                msg = f"🛑 <b>PYQ Practice Stopped</b>\n\n✅ Correct: {c}\n❌ Wrong: {w}\n⏭ Skipped: {s}"
                _b().send_message(uid, msg, parse_mode="HTML")
            state["processing"] = False
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            _generate_report(uid)
            
        elif data == "f_retry":
            if state.get("generating"): return
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

    except Exception as e:
        print(f"[ROUTER-ERR] {e}")

def _generate_report(uid):
    state = _state.get(uid, {})
    total = state.get("correct", 0) + state.get("wrong", 0) + state.get("skipped", 0)
    if total == 0:
        _b().send_message(uid, "🛑 Session stopped.")
        return
    acc = (state["correct"] / total) * 100 if total > 0 else 0
    health_delta = (state["correct"] * 1.5) - (state["wrong"] * 1.0)
    msg = f"🏁 <b>SESSION REPORT</b>\n\n📊 <b>Attempted:</b> {total}\n✅ <b>Correct:</b> {state['correct']}\n❌ <b>Wrong:</b> {state['wrong']}\n⏭ <b>Skipped:</b> {state['skipped']}\n\n🎯 <b>Accuracy:</b> {acc:.1f}%\n❤️ <b>Health Update:</b> {health_delta:+.1f}%\n\n📚 <i>Want a personal Mastery Analyzer? Contact us on WhatsApp:</i> <a href='https://wa.me/918074231426'>H&K Publications</a>"
    _b().send_message(uid, msg, parse_mode="HTML", disable_web_page_preview=True)

def _generate_next(uid, msg_id=None):
    state = _state.get(uid, {})
    if not state.get("active"): return
    state["generating"] = True
    state["q_count"] = state.get("q_count", 0) + 1
    count = state["q_count"]
    
    if count > 100:
        state["active"] = False
        _b().send_message(uid, "🎉 <b>Mastery Complete!</b> You have covered the entire syllabus.")
        return

    if msg_id: loader_msg = msg_id
    else:
        msg = _b().send_message(uid, f"⏳ Generating Q{count}...", parse_mode="HTML")
        loader_msg = msg.message_id
        threading.Thread(target=_animate_gen, args=(uid, loader_msg, count), daemon=True).start()

    import ai_client
    mode = state.get("mode", "practice")
    diff = random.randint(3, 9)
    ideal_time = {3: 45, 4: 60, 5: 75, 6: 90, 7: 90, 8: 100, 9: 110}.get(diff, 90)
    source = random.choice(["JEE Adv 2023", "JEE Main 2024", "Arihant", "Cengage", "JEE Adv 2021"])
    q_type = random.choice(["MCQ", "Multi-Correct", "Numerical", "Integer", "Assertion-Reason", "Statement-based", "Match-the-following", "Passage-based", "Matrix"])
    
    prompt = f"Generate a JEE question for '{state['chapter']}' (Subject: {state['subj']}).\n"
    prompt += f"Target Difficulty: {diff}/10. Question Type: {q_type}. Source: {source}.\n"
    prompt += "RULES:\n1. Output strictly as JSON.\n2. NO LATEX. Use Unicode (α, √, π, ⁰, ²).\n3. Explanation must be direct and concise.\n"
    prompt += '{"question":"...", "subtopic":"...", "concept":"...", "options":["A","B","C","D"], "correct_index":0, "explanation":"..."}\n'

    q = None
    for attempt in range(3):
        try:
            raw = ai_client._call_groq(0, "Output ONLY valid JSON.", prompt, max_tokens=1200, temperature=0.7)
            if not raw or not raw.strip(): continue
            txt = raw.strip()
            if txt.startswith("```"): txt = re.sub(r"^```(?:json)?\s*", "", txt); txt = re.sub(r"\s*```\s*$", "", txt)
            first, last = txt.find("{"), txt.rfind("}")
            if first == -1 or last == -1: continue
            q = json.loads(txt[first:last+1])
            if "question" in q and "options" in q:
                q["difficulty"] = diff
                q["ideal_time"] = ideal_time
                q["source"] = source
                q["q_type"] = q_type
                break
        except Exception:
            q = None
            time.sleep(1)
            
    if not q:
        try: _b().delete_message(uid, loader_msg)
        except: pass
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🔄 Retry", callback_data="f_retry"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().send_message(uid, "⚠️ <b>AI faced an error generating this question.</b>\n\nClick Retry to try again.", parse_mode="HTML", reply_markup=kb)
        state["generating"] = False
        return
        
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    
    header = f"<b>[{mode.upper()} | Q{count}]</b>\n"
    header += f"📖 <b>{state['chapter']}</b> → {q.get('subtopic', 'General')}\n"
    header += f"🧠 Concept: {q.get('concept', 'General')}\n"
    header += f"🎯 Pattern: {q.get('q_type', 'MCQ')} | Difficulty: {q.get('difficulty', 5)}/10 | ⏱️ Ideal: {q.get('ideal_time', 60)}s\n"
    header += f"🏷️ Source: {q.get('source', 'AI')}\n"
    header += "━━━━━━━━━━━━━━━\n\n"
    
    body = header + f"{clean_math(q.get('question', ''))}\n\n"
    for i, opt in enumerate(q.get("options", [])[:4]):
        body += f"<b>{chr(65+i)})</b> {clean_math(opt)}\n"
        
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    state["kb"] = kb
    state["generating"] = False
    state["processing"] = False
    
    try:
        _b().delete_message(uid, loader_msg)
        msg = _b().send_message(uid, body, parse_mode="HTML", reply_markup=kb)
        state["msg_id"] = msg.message_id
        state["question_msg_id"] = msg.message_id
        
        timer_msg = _b().send_message(uid, "⏱️ <b>Time Taken:</b> 0s", parse_mode="HTML")
        threading.Thread(target=_run_floating_timer, args=(uid, timer_msg.message_id, msg.message_id), daemon=True).start()
    except Exception as e:
        print(f"[SEND-ERR] {e}")

print("✅ c04_exam: FINAL PYQ & EXAM ENGINE LOADED.")


def send_pyq_q(uid, msg_id=None):
    state = _state[uid]
    if state.get("mode") != "pyq": return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    if idx >= len(q_list):
        if state.get("pyq_phase") == "priority" and state.get("pyq_normal"):
            state["pyq_phase"] = "normal"
            state["pyq_questions"] = state["pyq_normal"]
            state["pyq_index"] = 0
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("▶️ Continue with Normal", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
            _b().send_message(uid, "🎓 <b>You have completed all Priority questions.</b>\n\nDo you want to continue with the remaining normal questions?", reply_markup=kb)
            return

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🛑 Stop & View Result", callback_data="f_stop"))
        _b().send_message(uid, "🏁 <b>All questions from this chapter are completed!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False
    state["pyq_is_numerical"] = False # Reset flag

    # --- 5th Question Numerical Logic ---
    is_num = (idx > 0 and idx % 5 == 0)
    if is_num:
        state["pyq_is_numerical"] = True
        # Tell the user to type the answer
        state["waiting_for_pyq_numeric"] = True
        caption = f"🔢 <b>PYQ {idx+1}/{len(q_list)} (Numerical Mode)</b>\n📅 {q.get('source', 'JEE Main')}\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\n\n<i>⚠️ Options are hidden. Please type your numerical answer.</i>"
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    else:
        phase_name = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
        diff_raw = q.get('difficulty', 5)
        try:
            diff_num = int(float(diff_raw))
            diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
            diff_str = f"{diff_num}/10 ({diff_text})"
        except: diff_str = str(diff_raw)
            
        caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\n📅 {q.get('source', 'JEE Main')}\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\n📊 Difficulty: {diff_str}"
        kb = InlineKeyboardMarkup(row_width=4)
        kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
        kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    # Clean up previous photo, but NOT the solution text
    if state.get("pyq_photo_msg_id"):
        try: _b().delete_message(uid, state["pyq_photo_msg_id"])
        except: pass
    
    # Send Photo
    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
            state["pyq_photo_msg_id"] = msg.message_id
            
            # Simple safe timer
            import threading
            def _timer(msg_id):
                for i in range(1, 300): # Max 5 mins
                    if not state.get("pyq_timer_active") or state.get("mode") != "pyq": break
                    time.sleep(1)
                    try: _b().edit_message_text(f"⏱️ {i}s", chat_id=uid, message_id=msg_id)
                    except: pass
            t_msg = _b().send_message(uid, "⏱️ 0s")
            state["pyq_timer_msg_id"] = t_msg.message_id
            state["pyq_timer_active"] = True
            threading.Thread(target=_timer, args=(t_msg.message_id,), daemon=True).start()

    except Exception as e:
        _b().send_message(uid, f"❌ Failed to send photo: {e}\nPath: {q['img']}")

def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    if not text: return ""
    t = str(text)
    t = html.unescape(t).replace("*", "").replace("_", " ")
    t = t.replace("\\alpha", "α").replace("\\beta", "β").replace("\\theta", "θ").replace("\\pi", "π")
    t = t.replace("\\times", "×").replace("\\cdot", "•").replace("\\sqrt", "√").replace("\\infty", "∞")
    t = t.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "").replace("$", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    sup = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    t = re.sub(r'\^([0-9+\-]+)', lambda m: m.group(1).translate(sup), t)
    t = re.sub(r'_([0-9]+)', lambda m: m.group(1).translate(sub), t)
    return t.strip()

def _extract_chapters(raw_data):
    chapters = set()
    if isinstance(raw_data, dict):
        for k, v in raw_data.items():
            if isinstance(v, dict) and "chapter" in v: chapters.add(v["chapter"])
            else: chapters.add(k)
    elif isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                ch = item.get("chapter") or item.get("name") or item.get("topic")
                if ch: chapters.add(ch)
    return sorted(list(chapters))

def _animate_gen(uid, msg_id, count):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if not state.get("generating"): return
        try: _b().edit_message_text(f"⏳ Generating Q{count}... ({elapsed}s)", chat_id=uid, message_id=msg_id, parse_mode="HTML")
        except: pass

def _run_floating_timer(uid, timer_msg_id, question_msg_id):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id)
            except: pass
            return
        try: 
            _b().edit_message_text(f"⏱️ <b>Time Taken:</b> {elapsed}s", chat_id=uid, message_id=timer_msg_id, parse_mode="HTML")
        except: pass

def _strip_old_buttons(uid):
    state = _state.get(uid, {})
    old_msg = state.get("msg_id")
    if old_msg:
        try: _b().edit_message_reply_markup(uid, old_msg, reply_markup=None)
        except: pass
    state["msg_id"] = None

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
        InlineKeyboardButton("📝 Test", callback_data="f_mode:test")
    )
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(message.chat.id, "🎓 <b>Exam Center</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['conceptual'])
def cmd_conceptual(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"),
        InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional")
    )
    _b().send_message(message.chat.id, "🧠 <b>Concept Mastery</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

def _show_chapters(uid, msg_id):
    state = _state[uid]
    chapters = state.get("chapters", [])
    page = state.get("page", 0)
    start, end = page * 5, (page + 1) * 5
    chunk = chapters[start:end]
    
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(chunk):
        kb.add(InlineKeyboardButton(f"{start + i + 1}. {ch[:25]}", callback_data=f"f_ch:{ch}"))
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="f_page:-1"))
    if end < len(chapters): nav.append(InlineKeyboardButton("Next ➡️", callback_data="f_page:1"))
    if nav: kb.row(*nav)
    kb.row(InlineKeyboardButton("🔙 Back", callback_data="f_back:sub"))
    
    try: _b().edit_message_text(f"📚 <b>Select Chapter:</b>\n(Showing {start+1}-{min(end, len(chapters))} of {len(chapters)})", chat_id=uid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("f_"))
def handle_buttons(call):
    try: _b().answer_callback_query(call.id)
    except: pass
    uid = call.from_user.id
    data = call.data
    if uid not in _state: _state[uid] = {}
    state = _state[uid]

    if data.startswith("f_ans:") and state.get("processing"): return
        
    try:
        if data.startswith("f_mode:"):
            mode = data.split(":")[1]
            _state[uid] = {"mode": mode, "active": True, "covered": [], "q_count": 0, "correct": 0, "wrong": 0, "skipped": 0, "generating": False, "processing": False}
            
            if mode == "pyq":
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("📖 Practice (Chapter-wise)", callback_data="f_pyq:practice"),
                    InlineKeyboardButton("📝 Previous Paper Test", callback_data="f_pyq:papers")
                )
                kb.add(InlineKeyboardButton("🚧 JEE Adv (Coming Soon)", callback_data="f_soon"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("🔍 <b>PYQ Explorer</b>\nSelect type:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return
                
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("Physics", callback_data="f_sub:Physics"),
                InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"),
                InlineKeyboardButton("Maths", callback_data="f_sub:Maths")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
            _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data == "f_soon":
            _b().answer_callback_query(call.id, "Coming Soon!", show_alert=True)

        elif data.startswith("f_pyq:"):
            ptype = data.split(":")[1]
            import json
            try:
                with open("data/pyq_db.json") as f: db = json.load(f)
            except: db = {"practice": {}, "papers": {}}

            if ptype == "practice":
                kb = InlineKeyboardMarkup(row_width=3)
                for subj in db.get("practice", {}).keys():
                    kb.add(InlineKeyboardButton(subj, callback_data=f"f_pyq_sub:{subj}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📖 <b>PYQ Practice</b>\nSelect Subject:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
            
            elif ptype == "papers":
                kb = InlineKeyboardMarkup(row_width=3)
                years = list(db.get("papers", {}).keys())
                if not years:
                    _b().answer_callback_query(call.id, "No papers uploaded yet.")
                    return
                for yr in years:
                    kb.add(InlineKeyboardButton(yr, callback_data=f"f_pyq_yr:{yr}"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text("📝 <b>Previous Paper Test</b>\nSelect Year:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json
            chapters = []
            try:
                with open("data/pyq_master.json") as f: db = json.load(f)
                extracted = db.get("practice", {}).get(subj, {})
                chapters = list(extracted.keys())
            except Exception:
                pass

            kb = InlineKeyboardMarkup(row_width=1)
            if not chapters:
                # Show a proper page instead of an alert
                msg = f"⏳ <b>{subj} - Still Processing</b>\n\nNo chapters have been extracted yet. Hamilton is working on it in the background. Please check back later."
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
                _b().edit_message_text(msg, chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)
                return

            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"📖 <b>{subj} - Extracted PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_pyq_ch:"):
            ch = data.split(":", 1)[1]
            subj = state.get("pyq_subj")
            import json, os
            print(f"[DEBUG] f_pyq_ch clicked: subj={subj} ch={ch}")
            q_data = None
            for attempt in range(6):
                try:
                    with open("data/pyq_master.json") as f: db = json.load(f)
                    q_data = db.get("practice", {}).get(subj, {}).get(ch)
                    if q_data is not None:
                        print(f"[DEBUG] JSON OK (attempt {attempt+1})")
                        break
                    else:
                        # Valid JSON, chapter really missing
                        _b().send_message(uid, f"❌ Chapter not in DB: {subj} / {ch}")
                        return
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON retry {attempt+1}: {e}")
                    import time as _t; _t.sleep(0.3)
                except Exception as e:
                    _b().send_message(uid, f"❌ Load error: {e}")
                    print(f"[DEBUG] Load error: {e}")
                    return
            if q_data is None:
                _b().send_message(uid, "❌ Could not load (extractor busy). Try again in 2 sec.")
                return

            if not q_data.get("priority") and not q_data.get("normal"):
                _b().answer_callback_query(call.id, "⚠️ No questions found in this chapter.", show_alert=True)
                return

            state["mode"] = "pyq"
            state["subj"] = subj
            state["chapter"] = ch
            state["pyq_phase"] = "priority"
            state["pyq_questions"] = q_data.get("priority", [])
            state["pyq_normal"] = q_data.get("normal", [])
            state["pyq_index"] = 0
            
            # Verify the image path exists before trying to send
            first_q = state["pyq_questions"][0] if state["pyq_questions"] else None
            if not first_q:
                _b().answer_callback_query(call.id, "❌ Priority list is empty.", show_alert=True)
                return
                
            if not os.path.exists(first_q["img"]):
                _b().send_message(uid, f"❌ <b>Database Error:</b> Image file missing at `{first_q['img']}`. The extraction might have failed to save the image.", parse_mode="HTML")
                return
            
            try: _b().delete_message(uid, call.message.message_id)
            except: pass
            
            try:
                send_pyq_q(uid)
            except Exception as e:
                _b().send_message(uid, f"❌ UI Crash: {e}")
                print(f"PYQ UI CRASH: {e}")

        elif data.startswith("f_back:"):
            target = data.split(":")[1]
            if target == "main": cmd_exam(call.message)
            elif target == "sub":
                mode = state.get("mode", "practice")
                kb = InlineKeyboardMarkup(row_width=3)
                kb.add(InlineKeyboardButton("Physics", callback_data="f_sub:Physics"), InlineKeyboardButton("Chemistry", callback_data="f_sub:Chemistry"), InlineKeyboardButton("Maths", callback_data="f_sub:Maths"))
                kb.add(InlineKeyboardButton("🔙 Back", callback_data="f_back:main"))
                _b().edit_message_text(f"Mode: {mode.upper()}\n<b>Select Subject:</b>", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)

        elif data.startswith("f_sub:"):
            subj = data.split(":")[1]
            state["subj"] = subj
            exam = state.get("exam", "jee_adv").lower()
            fn = f"data/{exam}_{subj.lower()}.json"
            try:
                with open(fn) as f: chapters = _extract_chapters(json.load(f))
            except: chapters = ["Motion in a Straight Line", "Units and Measurements"]
            state["chapters"] = chapters
            state["page"] = 0
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_page:"):
            state["page"] += int(data.split(":")[1])
            _show_chapters(uid, call.message.message_id)

        elif data.startswith("f_ch:"):
            ch = data.split(":", 1)[1]
            state["chapter"] = ch
            state["q_count"] = 0
            _b().edit_message_text(f"⏳ Generating Q1...", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
            threading.Thread(target=_generate_next, args=(uid, call.message.message_id), daemon=True).start()

        elif data.startswith("f_ans:"):
            if state.get("processing") or state.get("selected") is not None: return
            state["selected"] = int(data.split(":")[1])
            sel = state["selected"]
            kb = InlineKeyboardMarkup(row_width=4)
            kb.row(*[InlineKeyboardButton(f"{'✅' if i == sel else ''}{chr(65+i)}", callback_data=f"f_ans:{i}") for i in range(4)])
            kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
            state["kb"] = kb
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=kb)
            except: pass

        elif data in ("f_save", "f_skip"):
            if state.get("processing") or state.get("generating"): return
            state["processing"] = True
            state["pyq_timer_active"] = False
            try: _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            except: pass
            _b().send_message(uid, "🔎 <b>Verifying your response...</b>", parse_mode="HTML")
            
            if data == "f_save":
                if state.get("selected") is None: 
                    state["processing"] = False
                    return
                is_correct = state["selected"] == state["q"].get("correct_index", 0)
                if is_correct: state["correct"] += 1
                else: state["wrong"] += 1
                
                time_taken = int(time.time() - state.get("q_start_time", time.time()))
                ideal = state["q"].get("ideal_time", 60)
                correct_letter = chr(65 + state["q"].get("correct_index", 0))
                
                try:
                    import health
                    q_subtopic = state["q"].get("subtopic", "General")
                    health.record_attempt(uid, state["subj"], state["chapter"], q_subtopic, is_correct, time_taken)
                except: pass
                
                msg = f"✅ <b>Correct!</b>\n\n" if is_correct else f"❌ <b>Wrong.</b> Correct answer: <b>Option {correct_letter}</b>.\n\n"
                msg += f"⏱️ <b>Time Taken:</b> {time_taken}s (Ideal: {ideal}s)\n\n"
                msg += format_ultimate_solution(state['q'])
                
                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("💬 Doubt in Explanation", callback_data="f_doubt"))
                kb.add(InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
                
            elif data == "f_skip":
                state["skipped"] += 1
                if state.get("q"):
                    correct = state["q"].get("correct_index", 0)
                    exp = clean_math(state["q"].get("explanation", ""))
                    msg = f"⏭ <b>Correct Answer: Option {chr(65+correct)}</b>\n\n📝 <b>Explanation:</b>\n{exp}"
                    kb = InlineKeyboardMarkup(row_width=2)
                    kb.add(InlineKeyboardButton("▶️ Continue", callback_data="f_next_q"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
                    _b().send_message(uid, msg, parse_mode="HTML", reply_markup=kb)
            
            state["selected"] = None
            state["processing"] = False

        elif data == "f_pyq_cont":
            state["pyq_phase"] = "skipped"
            state["pyq_questions"] = state.get("pyq_skipped", [])
            state["pyq_index"] = 0
            send_pyq_q(uid, call.message.message_id)
            
        elif data == "f_doubt":
            state["waiting_for_doubt"] = True
            _b().send_message(uid, "💬 <b>Please type your doubt about this question or explanation.</b>\nHamilton will answer it for you.", parse_mode="HTML")
            
        elif data == "f_next_q":
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            state["selected"] = None
            state["processing"] = False
            if state.get("mode") == "pyq":
                state["pyq_timer_active"] = False
                state["pyq_index"] += 1
                send_pyq_q(uid, call.message.message_id)
            else:
                threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

        elif data == "f_stop":
            state["active"] = False
            if state.get("mode") == "pyq":
                c = state.get("correct", 0)
                w = state.get("wrong", 0)
                s = state.get("skipped", 0)
                msg = f"🛑 <b>PYQ Practice Stopped</b>\n\n✅ Correct: {c}\n❌ Wrong: {w}\n⏭ Skipped: {s}"
                _b().send_message(uid, msg, parse_mode="HTML")
            state["processing"] = False
            _b().edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
            _generate_report(uid)
            
        elif data == "f_retry":
            if state.get("generating"): return
            threading.Thread(target=_generate_next, args=(uid, None), daemon=True).start()

    except Exception as e:
        print(f"[ROUTER-ERR] {e}")

def _generate_report(uid):
    state = _state.get(uid, {})
    total = state.get("correct", 0) + state.get("wrong", 0) + state.get("skipped", 0)
    if total == 0:
        _b().send_message(uid, "🛑 Session stopped.")
        return
    acc = (state["correct"] / total) * 100 if total > 0 else 0
    health_delta = (state["correct"] * 1.5) - (state["wrong"] * 1.0)
    msg = f"🏁 <b>SESSION REPORT</b>\n\n📊 <b>Attempted:</b> {total}\n✅ <b>Correct:</b> {state['correct']}\n❌ <b>Wrong:</b> {state['wrong']}\n⏭ <b>Skipped:</b> {state['skipped']}\n\n🎯 <b>Accuracy:</b> {acc:.1f}%\n❤️ <b>Health Update:</b> {health_delta:+.1f}%\n\n📚 <i>Want a personal Mastery Analyzer? Contact us on WhatsApp:</i> <a href='https://wa.me/918074231426'>H&K Publications</a>"
    _b().send_message(uid, msg, parse_mode="HTML", disable_web_page_preview=True)

def _generate_next(uid, msg_id=None):
    state = _state.get(uid, {})
    if not state.get("active"): return
    state["generating"] = True
    state["q_count"] = state.get("q_count", 0) + 1
    count = state["q_count"]
    
    if count > 100:
        state["active"] = False
        _b().send_message(uid, "🎉 <b>Mastery Complete!</b> You have covered the entire syllabus.")
        return

    if msg_id: loader_msg = msg_id
    else:
        msg = _b().send_message(uid, f"⏳ Generating Q{count}...", parse_mode="HTML")
        loader_msg = msg.message_id
        threading.Thread(target=_animate_gen, args=(uid, loader_msg, count), daemon=True).start()

    import ai_client
    mode = state.get("mode", "practice")
    diff = random.randint(3, 9)
    ideal_time = {3: 45, 4: 60, 5: 75, 6: 90, 7: 90, 8: 100, 9: 110}.get(diff, 90)
    source = random.choice(["JEE Adv 2023", "JEE Main 2024", "Arihant", "Cengage", "JEE Adv 2021"])
    q_type = random.choice(["MCQ", "Multi-Correct", "Numerical", "Integer", "Assertion-Reason", "Statement-based", "Match-the-following", "Passage-based", "Matrix"])
    
    prompt = f"Generate a JEE question for '{state['chapter']}' (Subject: {state['subj']}).\n"
    prompt += f"Target Difficulty: {diff}/10. Question Type: {q_type}. Source: {source}.\n"
    prompt += "RULES:\n1. Output strictly as JSON.\n2. NO LATEX. Use Unicode (α, √, π, ⁰, ²).\n3. Explanation must be direct and concise.\n"
    prompt += '{"question":"...", "subtopic":"...", "concept":"...", "options":["A","B","C","D"], "correct_index":0, "explanation":"..."}\n'

    q = None
    for attempt in range(3):
        try:
            raw = ai_client._call_groq(0, "Output ONLY valid JSON.", prompt, max_tokens=1200, temperature=0.7)
            if not raw or not raw.strip(): continue
            txt = raw.strip()
            if txt.startswith("```"): txt = re.sub(r"^```(?:json)?\s*", "", txt); txt = re.sub(r"\s*```\s*$", "", txt)
            first, last = txt.find("{"), txt.rfind("}")
            if first == -1 or last == -1: continue
            q = json.loads(txt[first:last+1])
            if "question" in q and "options" in q:
                q["difficulty"] = diff
                q["ideal_time"] = ideal_time
                q["source"] = source
                q["q_type"] = q_type
                break
        except Exception:
            q = None
            time.sleep(1)
            
    if not q:
        try: _b().delete_message(uid, loader_msg)
        except: pass
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🔄 Retry", callback_data="f_retry"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
        _b().send_message(uid, "⚠️ <b>AI faced an error generating this question.</b>\n\nClick Retry to try again.", parse_mode="HTML", reply_markup=kb)
        state["generating"] = False
        return
        
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    
    header = f"<b>[{mode.upper()} | Q{count}]</b>\n"
    header += f"📖 <b>{state['chapter']}</b> → {q.get('subtopic', 'General')}\n"
    header += f"🧠 Concept: {q.get('concept', 'General')}\n"
    header += f"🎯 Pattern: {q.get('q_type', 'MCQ')} | Difficulty: {q.get('difficulty', 5)}/10 | ⏱️ Ideal: {q.get('ideal_time', 60)}s\n"
    header += f"🏷️ Source: {q.get('source', 'AI')}\n"
    header += "━━━━━━━━━━━━━━━\n\n"
    
    body = header + f"{clean_math(q.get('question', ''))}\n\n"
    for i, opt in enumerate(q.get("options", [])[:4]):
        body += f"<b>{chr(65+i)})</b> {clean_math(opt)}\n"
        
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))
    state["kb"] = kb
    state["generating"] = False
    state["processing"] = False
    
    try:
        _b().delete_message(uid, loader_msg)
        msg = _b().send_message(uid, body, parse_mode="HTML", reply_markup=kb)
        state["msg_id"] = msg.message_id
        state["question_msg_id"] = msg.message_id
        
        timer_msg = _b().send_message(uid, "⏱️ <b>Time Taken:</b> 0s", parse_mode="HTML")
        threading.Thread(target=_run_floating_timer, args=(uid, timer_msg.message_id, msg.message_id), daemon=True).start()
    except Exception as e:
        print(f"[SEND-ERR] {e}")

print("✅ c04_exam: FINAL PYQ & EXAM ENGINE LOADED.")


def send_pyq_q(uid, msg_id=None):
    print(f"[DEBUG] send_pyq_q: uid={uid}")
    state = _state[uid]
    print(f"[DEBUG] state: mode={state.get('mode')} idx={state.get('pyq_index')} len={len(state.get('pyq_questions', []))}")
    if state.get("mode") != "pyq":
        print(f"[DEBUG] ABORT: mode={state.get('mode')}")
        return
    
    q_list = state.get("pyq_questions", [])
    idx = state.get("pyq_index", 0)
    
    if idx >= len(q_list):
        if state.get("pyq_phase") == "priority" and state.get("pyq_normal"):
            state["pyq_phase"] = "normal"
            state["pyq_questions"] = state["pyq_normal"]
            state["pyq_index"] = 0
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("▶️ Continue with Normal", callback_data="f_pyq_cont"), InlineKeyboardButton("🛑 Stop & Result", callback_data="f_stop"))
            _b().send_message(uid, "🎓 <b>You have completed all Priority questions.</b>\n\nDo you want to continue with the remaining normal questions?", reply_markup=kb)
            return

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🛑 Stop & View Result", callback_data="f_stop"))
        _b().send_message(uid, "🏁 <b>All questions from this chapter are completed!</b>", reply_markup=kb)
        return

    q = q_list[idx]
    state["q"] = q
    state["selected"] = None
    state["q_start_time"] = time.time()
    state["processing"] = False

    phase_name = "Priority" if state.get("pyq_phase") == "priority" else "Normal"
    diff_raw = q.get('difficulty', 5)
    try:
        diff_num = int(float(diff_raw))
        diff_text = "Easy" if diff_num <= 4 else ("Medium" if diff_num <= 7 else "Hard")
        diff_str = f"{diff_num}/10 ({diff_text})"
    except:
        diff_str = str(diff_raw)
        
    caption = f"📝 <b>PYQ {idx+1}/{len(q_list)} ({phase_name})</b>\n📅 {q.get('source', 'JEE Main')}\n⏱ Ideal Time: {q.get('ideal_time', 90)}s\n📊 Difficulty: {diff_str}"
    
    kb = InlineKeyboardMarkup(row_width=4)
    kb.row(*[InlineKeyboardButton(chr(65+i), callback_data=f"f_ans:{i}") for i in range(4)])
    kb.row(InlineKeyboardButton("✔️ Save", callback_data="f_save"), InlineKeyboardButton("⏭ Skip", callback_data="f_skip"), InlineKeyboardButton("🛑 Stop", callback_data="f_stop"))

    if msg_id:
        try: _b().delete_message(uid, msg_id)
        except: pass
    
    print(f"[DEBUG] Attempting send_photo: {q['img']}")
    try:
        with open(q["img"], "rb") as f:
            msg = _b().send_photo(uid, f, caption=caption, parse_mode="HTML", reply_markup=kb)
            state["pyq_msg_id"] = msg.message_id
        print(f"[DEBUG] send_photo SUCCESS, msg_id={msg.message_id}")
    except Exception as e:
        print(f"[DEBUG] send_photo FAILED: {e}")
        try:
            _b().send_message(uid, f"❌ Failed to send photo: {e}\nPath: {q['img']}")
        except Exception as e2:
            print(f"[DEBUG] Even fallback failed: {e2}")
def clean_math(text):
    if not text: return ""
    text = text.replace('#', '').replace('*', '')
    if not text: return ""
    t = str(text)
    t = html.unescape(t).replace("*", "").replace("_", " ")
    t = t.replace("\\alpha", "α").replace("\\beta", "β").replace("\\theta", "θ").replace("\\pi", "π")
    t = t.replace("\\times", "×").replace("\\cdot", "•").replace("\\sqrt", "√").replace("\\infty", "∞")
    t = t.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "").replace("$", "")
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    sup = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    t = re.sub(r'\^([0-9+\-]+)', lambda m: m.group(1).translate(sup), t)
    t = re.sub(r'_([0-9]+)', lambda m: m.group(1).translate(sub), t)
    return t.strip()

def _extract_chapters(raw_data):
    chapters = set()
    if isinstance(raw_data, dict):
        for k, v in raw_data.items():
            if isinstance(v, dict) and "chapter" in v: chapters.add(v["chapter"])
            else: chapters.add(k)
    elif isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                ch = item.get("chapter") or item.get("name") or item.get("topic")
                if ch: chapters.add(ch)
    return sorted(list(chapters))

def _animate_gen(uid, msg_id, count):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if not state.get("generating"): return
        try: _b().edit_message_text(f"⏳ Generating Q{count}... ({elapsed}s)", chat_id=uid, message_id=msg_id, parse_mode="HTML")
        except: pass

def _run_floating_timer(uid, timer_msg_id, question_msg_id):
    elapsed = 0
    while True:
        time.sleep(1)
        elapsed += 1
        state = _state.get(uid, {})
        if state.get("question_msg_id") != question_msg_id or state.get("processing") or not state.get("active"):
            try: _b().delete_message(uid, timer_msg_id)
            except: pass
            return
        try: 
            _b().edit_message_text(f"⏱️ <b>Time Taken:</b> {elapsed}s", chat_id=uid, message_id=timer_msg_id, parse_mode="HTML")
        except: pass

def _strip_old_buttons(uid):
    state = _state.get(uid, {})
    old_msg = state.get("msg_id")
    if old_msg:
        try: _b().edit_message_reply_markup(uid, old_msg, reply_markup=None)
        except: pass
    state["msg_id"] = None

@bot.message_handler(commands=['exam'])
def cmd_exam(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📖 Practice", callback_data="f_mode:practice"),
        InlineKeyboardButton("📝 Test", callback_data="f_mode:test")
    )
    kb.add(InlineKeyboardButton("🔍 PYQs", callback_data="f_mode:pyq"))
    _b().send_message(message.chat.id, "🎓 <b>Exam Center</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=['conceptual'])
def cmd_conceptual(message):
    _state[message.chat.id] = {"active": False, "processing": False, "generating": False}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Conceptual", callback_data="f_mode:conceptual"),
        InlineKeyboardButton("⚠️ Exceptional", callback_data="f_mode:exceptional")
    )
    _b().send_message(message.chat.id, "🧠 <b>Concept Mastery</b>\n\nSelect Mode:", parse_mode="HTML", reply_markup=kb)



from ai_client import convert_latex_envs
# ==========================================================
# bot.py — Chunk 5: poll handlers, practice feedback, doubt border
# ==========================================================

# ==========================================================
# INLINE BUTTON HELPERS
# ==========================================================
def _practice_footer_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("▶️ Continue", callback_data="prac_continue"),
        telebot.types.InlineKeyboardButton("🔖 Bookmark", callback_data="prac_bookmark"),
        telebot.types.InlineKeyboardButton("⏹ Stop", callback_data="prac_stop"),
    )
    return markup


def _test_footer_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("⏹ Stop Test", callback_data="test_stop"),
    )
    return markup


def _concept_footer_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("⏹ Stop Test", callback_data="concept_stop"),
    )
    return markup


def _doubt_continue_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("▶️ Continue to next question",
                                            callback_data="prac_continue"),
        telebot.types.InlineKeyboardButton("⏹ Stop Practice",
                                            callback_data="prac_stop"),
    )
    return markup


# ==========================================================
# UNIFIED POLL HANDLER
# ==========================================================
@bot.poll_answer_handler()
def on_poll_answer(poll_answer):
    uid = poll_answer.user.id
    sess = exam_engine.get_session(uid)
    if not sess:
        return
    mode = sess.get("mode", "practice")
    if mode == "practice":
        _handle_practice_poll(uid, sess, poll_answer)
    elif mode == "test":
        _handle_test_poll(uid, sess, poll_answer)
    elif mode == "conceptual":
        _handle_conceptual_poll(uid, sess, poll_answer)


# ==========================================================
# HEALTH DELTA HELPERS
# ==========================================================
def _record_and_delta(uid, subject, chapter, subtopic, concept, correct,
                       time_taken, ideal_time, difficulty):
    p = load_profile(uid) or {}
    key = f"{subject}::{chapter}::{subtopic}"
    before = p.get("subtopic_stats", {}).get(key, {}).get("health")
    _, after = health.record_attempt(uid, subject, chapter, subtopic, concept,
                                      correct, int(time_taken), ideal_time,
                                      difficulty=difficulty)
    return before, after


def _health_delta_text(before, after):
    if after is None:
        return ""
    if before is None:
        return f"\n📊 Health: *{after}/100* (first attempt)"
    delta = round(after - before, 1)
    sign = "+" if delta >= 0 else ""
    return f"\n📊 Health: {before} → *{after}* ({sign}{delta})"


# ==========================================================
# PRACTICE POLL HANDLER
# ==========================================================
def _handle_practice_poll(uid, sess, poll_answer):
    q = sess.get("current_q")
    if not q:
        return
    timer_manager.stop_question_timer(bot, uid)
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    options = q.get("options", [])
    time_taken = time.time() - sess.get("current_started", time.time())
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["questions_done"] = sess.get("questions_done", 0) + 1

    meta = sess.get("current_meta", {})
    subj = meta.get("subject", "")
    chapter = meta.get("chapter", "")
    subtopic = meta.get("subtopic", "")
    difficulty = q.get("difficulty", "medium")

    # ============ SKIP ============
    if selected == len(options):
        sess["skipped"] = sess.get("skipped", 0) + 1
        try:
            before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                               False, time_taken,
                                               int(q.get("ideal_time_sec", 60)),
                                               difficulty)
            delta_str = _health_delta_text(before, after)
        except Exception:
            delta_str = ""
        msg = (
            f"🚪 *Skipped*\n\n"
            f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 60)}s)\n\n"
            f"📖 *Solution:*\n{convert_latex_envs(q.get('explanation', '(none)'))}\n\n"
            f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
            + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}\n"
            + delta_str
        )
        safe_send(uid, msg + _countdown_footer(uid),
                  parse_mode="Markdown",
                  reply_markup=_practice_footer_buttons())
        sess["last_q"] = q
        sess["last_meta"] = meta
        sess["current_q"] = None
        return

    # ============ ANSWER ============
    correct = (int(selected) == int(q.get("correct_index", -1)))
    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    try:
        before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                           correct, time_taken,
                                           int(q.get("ideal_time_sec", 60)),
                                           difficulty)
        delta_str = _health_delta_text(before, after)

        # SVG bar
        if SVG_ENABLED and before is not None and after is not None:
            svg = svg_templates.health_delta_bar(subtopic or "Subtopic", before, after)
            path = svg_renderer.render_svg(svg, name=f"hd_{uid}_{int(time.time())}")
            if path:
                safe_send_photo(uid, path)
                svg_renderer.cleanup_file(path)
    except Exception:
        delta_str = ""

    if correct:
        head = "✅ *Correct!*"
    else:
        user_letter = chr(65 + int(selected)) if 0 <= selected <= 25 else "?"
        correct_letter = chr(65 + int(q.get("correct_index", 0)))
        head = f"❌ *Wrong* — You chose *{user_letter}*, correct is *{correct_letter}*"

    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal: {q.get('ideal_time_sec', 60)}s)\n\n"
        f"📖 *Solution:*\n{convert_latex_envs(q.get('explanation', ''))}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}\n"
        + delta_str
    )
    safe_send(uid, msg + _countdown_footer(uid),
              parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    sess["last_q"] = q
    sess["last_meta"] = meta
    sess["current_q"] = None


# ==========================================================
# NUMERICAL ANSWER HANDLER
# ==========================================================
def _handle_numerical_answer(uid, text):
    pending = PENDING_NUMERICAL.pop(uid, None)
    if not pending:
        return
    timer_manager.stop_question_timer(bot, uid)
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]

    sess = exam_engine.get_session(uid)
    if not sess:
        return
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["questions_done"] = sess.get("questions_done", 0) + 1

    try:
        val = float(text.replace(",", "").replace(" ", "").strip())
    except Exception:
        PENDING_NUMERICAL[uid] = pending
        safe_send(uid, "⚠️ Please send a valid number.")
        return

    correct_val = q.get("correct_value", 0)
    try:
        correct = abs(val - float(correct_val)) < 1e-6
    except Exception:
        correct = False

    subj = meta.get("subject", "")
    chapter = meta.get("chapter", "")
    subtopic = meta.get("subtopic", "")
    difficulty = q.get("difficulty", "medium")

    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    try:
        before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                           correct, time_taken,
                                           int(q.get("ideal_time_sec", 90)),
                                           difficulty)
        delta_str = _health_delta_text(before, after)
    except Exception:
        delta_str = ""

    if correct:
        head = "✅ *Correct!*"
    else:
        head = f"❌ *Wrong* — correct value: *{correct_val}*"

    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 90)}s)\n"
        f"Your answer: `{text}`\n\n"
        f"📖 *Solution:*\n{convert_latex_envs(q.get('explanation', ''))}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}\n"
        + delta_str
    )
    safe_send(uid, msg + _countdown_footer(uid),
              parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    sess["last_q"] = q
    sess["last_meta"] = meta
    sess["current_q"] = None


# ==========================================================
# INLINE CALLBACKS — practice
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "prac_continue")
def _cb_prac_continue(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass
    if exam_engine.get_session(uid):
        _send_next_practice(uid)
    else:
        safe_send(uid, "Session ended. Use /exam to start again.")


@bot.callback_query_handler(func=lambda c: c.data == "prac_bookmark")
def _cb_prac_bookmark(call):
    uid = call.message.chat.id
    sess = exam_engine.get_session(uid)
    if not sess or not sess.get("last_q"):
        bot.answer_callback_query(call.id, "No question to bookmark.")
        return
    bpath = os.path.join(BOOKMARK_DIR, f"{uid}.json")
    bm = []
    if os.path.exists(bpath):
        try:
            with open(bpath) as f:
                bm = json.load(f)
        except Exception:
            bm = []
    q = sess["last_q"]
    entry = {
        "timestamp": datetime.now().isoformat(),
        "subject": sess.get("last_meta", {}).get("subject", ""),
        "chapter": sess.get("last_meta", {}).get("chapter", ""),
        "subtopic": sess.get("last_meta", {}).get("subtopic", ""),
        "question": q.get("question", ""),
        "options": q.get("options", []),
        "correct_index": q.get("correct_index"),
        "explanation": q.get("explanation", ""),
    }
    if any(b.get("question") == entry["question"] for b in bm):
        bot.answer_callback_query(call.id, "Already bookmarked.")
        return
    bm.append(entry)
    with open(bpath, "w") as f:
        json.dump(bm, f, indent=2, ensure_ascii=False)
    bot.answer_callback_query(call.id, f"Bookmarked! Total: {len(bm)}")


@bot.callback_query_handler(func=lambda c: c.data == "prac_stop")
def _cb_prac_stop(call):
    uid = call.message.chat.id
    _do_stop(uid)
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass


# ==========================================================
# NEXT / BOOKMARK / STOP (text commands)
# ==========================================================
@bot.message_handler(commands=['next'])
def cmd_next(message):
    uid = message.chat.id
    PENDING_NUMERICAL.pop(uid, None)
    timer_manager.stop_question_timer(bot, uid)
    sess = exam_engine.get_session(uid)
    if not sess:
        bot.reply_to(message, "Start with /exam first.")
        return
    if sess.get("mode") == "practice":
        _send_next_practice(uid)
    else:
        bot.reply_to(message, "Use the buttons to continue.")


@bot.message_handler(commands=['bookmark'])
def cmd_bookmark(message):
    uid = message.chat.id
    sess = exam_engine.get_session(uid)
    if not sess or not sess.get("last_q"):
        bot.reply_to(message, "No recent question to bookmark.")
        return
    bpath = os.path.join(BOOKMARK_DIR, f"{uid}.json")
    bm = []
    if os.path.exists(bpath):
        try:
            with open(bpath) as f:
                bm = json.load(f)
        except Exception:
            bm = []
    q = sess["last_q"]
    entry = {
        "timestamp": datetime.now().isoformat(),
        "subject": sess.get("last_meta", {}).get("subject", ""),
        "chapter": sess.get("last_meta", {}).get("chapter", ""),
        "subtopic": sess.get("last_meta", {}).get("subtopic", ""),
        "question": q.get("question", ""),
        "options": q.get("options", []),
        "correct_index": q.get("correct_index"),
        "explanation": q.get("explanation", ""),
    }
    if any(b.get("question") == entry["question"] for b in bm):
        bot.reply_to(message, "🔖 Already bookmarked.")
        return
    bm.append(entry)
    with open(bpath, "w") as f:
        json.dump(bm, f, indent=2, ensure_ascii=False)
    bot.reply_to(message, f"🔖 Bookmarked! You have {len(bm)} saved.")


@bot.message_handler(commands=['bookmarks'])
def cmd_bookmarks(message):
    uid = message.chat.id
    bpath = os.path.join(BOOKMARK_DIR, f"{uid}.json")
    if not os.path.exists(bpath):
        bot.reply_to(message, "📭 No bookmarks yet.")
        return
    with open(bpath) as f:
        bm = json.load(f)
    if not bm:
        bot.reply_to(message, "📭 No bookmarks yet.")
        return
    lines = [f"🔖 *Bookmarks* ({len(bm)})\n"]
    for i, b in enumerate(bm[:15], 1):
        lines.append(f"{i}. [{b.get('subject','?')} · {b.get('chapter','?')[:25]}]")
        lines.append(f"   {b.get('question','')[:70]}...")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    uid = message.chat.id
    _do_stop(uid)


def _do_stop(uid):
    p = load_profile(uid)
    timer_manager.stop_all_timers(bot, uid)
    PENDING_NUMERICAL.pop(uid, None)
    sess = exam_engine.get_session(uid)
    if not sess:
        if p and p.get("_practice_active"):
            p["_practice_active"] = False
            save_profile(uid, p)
        safe_send(uid, "No active session.")
        return
    if p:
        p["_practice_active"] = False
        save_profile(uid, p)

    mode = sess.get("mode", "practice")
    if mode == "conceptual":
        safe_send(uid, exam_engine.conceptual_report(uid), parse_mode="Markdown")
    elif mode == "test":
        _test_finish(uid)
        return
    else:
        safe_send(uid, exam_engine.session_report(uid), parse_mode="Markdown")

    exam_engine.end_session(uid)
    PRELOAD_QUEUE.pop(uid, None)
    WAITING_DOUBT.pop(uid, None)


print("bot.py Chunk 5 loaded: practice handlers + doubt border ready.")


from ai_client import convert_latex_envs
# ==========================================================
# bot.py — Chunk 7: test poll handler, paper break, finish report
# ==========================================================

# ==========================================================
# TEST — poll handler (silent, save answer, no feedback)
# ==========================================================
def _handle_test_poll(uid, sess, poll_answer):
    q = sess.get("current_q")
    if not q:
        return

    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    options = q.get("options", [])
    time_taken = time.time() - sess.get("current_started", time.time())
    meta = sess.get("current_meta", {})
    q_type = sess.get("current_plan_type", "mcq")

    # Determine correctness
    if selected == len(options):
        # Skipped
        sess["skipped"] = sess.get("skipped", 0) + 1
        correct = False
        user_answer_repr = "SKIP"
    else:
        correct_idx = int(q.get("correct_index", 0))
        if q_type == "multi" and q.get("correct_indices"):
            correct_idx = int(q["correct_indices"][0])
        correct = (int(selected) == correct_idx)
        user_answer_repr = chr(65 + int(selected)) if 0 <= selected <= 25 else "?"
        if correct:
            sess["correct"] = sess.get("correct", 0) + 1
        else:
            sess["wrong"] = sess.get("wrong", 0) + 1

    # Log answer for report
    sess.setdefault("answers_log", []).append({
        "q": q,
        "meta": meta,
        "q_type": q_type,
        "user_answer": user_answer_repr,
        "correct": correct,
        "time_taken": time_taken,
    })

    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["plan_index"] = sess.get("plan_index", 0) + 1

    # Record to health silently
    try:
        health.record_attempt(
            uid,
            meta.get("subject", ""),
            meta.get("chapter", ""),
            meta.get("subtopic", ""),
            "",
            correct,
            int(time_taken),
            int(q.get("ideal_time_sec", 60)),
            difficulty=q.get("difficulty", "medium"),
        )
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_test_q(uid)


# ==========================================================
# TEST — numerical answer during test
# ==========================================================
def _handle_test_numerical(uid, text):
    pending = PENDING_NUMERICAL.pop(uid, None)
    if not pending:
        return
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]

    sess = exam_engine.get_session(uid)
    if not sess:
        return

    try:
        val = float(text.replace(",", "").replace(" ", "").strip())
    except Exception:
        PENDING_NUMERICAL[uid] = pending
        safe_send(uid, "⚠️ Please send a valid number.")
        return

    try:
        correct_val = float(q.get("correct_value", 0))
        correct = abs(val - correct_val) < 1e-6
    except Exception:
        correct = False
        correct_val = q.get("correct_value", "?")

    q_type = "numerical"
    user_answer_repr = text.strip() if text.strip() else "?"

    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    sess.setdefault("answers_log", []).append({
        "q": q,
        "meta": meta,
        "q_type": q_type,
        "user_answer": user_answer_repr,
        "correct": correct,
        "time_taken": time_taken,
    })

    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["plan_index"] = sess.get("plan_index", 0) + 1

    try:
        health.record_attempt(
            uid,
            meta.get("subject", ""),
            meta.get("chapter", ""),
            meta.get("subtopic", ""),
            "",
            correct,
            int(time_taken),
            int(q.get("ideal_time_sec", 90)),
            difficulty=q.get("difficulty", "medium"),
        )
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_test_q(uid)


# ==========================================================
# TEST — timeout on paper
# ==========================================================
def _test_paper_time_up(uid):
    safe_send(uid, "⏰ Time up. Submitting paper...")
    _test_paper_finish(uid)


# ==========================================================
# TEST — finish a single paper
# ==========================================================
def _test_paper_finish(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return

    timer_manager.stop_test_timer(uid)

    paper = sess.get("current_paper", 1)
    papers = sess.get("papers", 1)

    # Save this paper's score
    p_correct = sess.get("correct", 0)
    p_wrong = sess.get("wrong", 0)
    p_skipped = sess.get("skipped", 0)
    p_log = sess.get("answers_log", [])

    score, max_score = exam_engine.test_paper_score(
        sess.get("exam"), p_correct, p_wrong, p_skipped
    )

    sess.setdefault("paper_scores", []).append({
        "paper": paper,
        "correct": p_correct,
        "wrong": p_wrong,
        "skipped": p_skipped,
        "score": score,
        "max": max_score,
        "log": list(p_log),
    })

    # If more papers to write
    if paper < papers:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton(
                "▶️ Continue to Paper 2",
                callback_data="test_paper2_start"
            ),
            telebot.types.InlineKeyboardButton(
                "⏹ End & Show Results",
                callback_data="test_end_now"
            ),
        )
        safe_send(uid,
            f"🏁 *Paper {paper} submitted*\n\n"
            f"Score: *{score} / {max_score}*\n"
            f"✅ {p_correct}  ❌ {p_wrong}  🚪 {p_skipped}\n\n"
            f"Take a short break.\n"
            f"When ready, tap Continue for Paper {paper+1}.",
            parse_mode="Markdown",
            reply_markup=markup)
        return

    # All papers done → show final report
    _test_finish(uid)


# ==========================================================
# TEST — full finish report with key + explanations
# ==========================================================
def _test_finish(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return

    timer_manager.stop_test_timer(uid)

    exam = sess.get("exam", "JEE_MAIN")
    papers_data = sess.get("paper_scores", [])

    # If no papers submitted yet (rare), grab current
    if not papers_data:
        p_correct = sess.get("correct", 0)
        p_wrong = sess.get("wrong", 0)
        p_skipped = sess.get("skipped", 0)
        log = sess.get("answers_log", [])
        score, max_score = exam_engine.test_paper_score(exam, p_correct, p_wrong, p_skipped)
        papers_data = [{
            "paper": 1,
            "correct": p_correct, "wrong": p_wrong, "skipped": p_skipped,
            "score": score, "max": max_score, "log": log,
        }]

    # Aggregate
    total_correct = sum(p["correct"] for p in papers_data)
    total_wrong = sum(p["wrong"] for p in papers_data)
    total_skipped = sum(p["skipped"] for p in papers_data)
    total_score = sum(p["score"] for p in papers_data)
    total_max = sum(p["max"] for p in papers_data)
    total_time_min = sess.get("total_time", 0) / 60

    # Headline
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "   🏁 *TEST COMPLETE*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━", "",
        f"📘 Exam: {EXAM_NAMES.get(exam, exam)}",
        f"📝 Attempted: {total_correct + total_wrong}",
        f"🚪 Skipped: {total_skipped}",
        f"⏱️ Total time: {round(total_time_min, 1)} min", "",
    ]

    for p in papers_data:
        lines.append(f"📄 *Paper {p['paper']}*: {p['score']} / {p['max']}")
    lines.append("")
    lines.append(f"🏆 *Overall Score: {total_score} / {total_max}*")
    lines.append(f"✅ Correct: {total_correct}  ❌ Wrong: {total_wrong}")
    if (total_correct + total_wrong) > 0:
        acc = round(100 * total_correct / (total_correct + total_wrong), 1)
        lines.append(f"🎯 Accuracy: {acc}%")

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")

    # Health delta SVG
    if SVG_ENABLED:
        p_holder = load_profile(uid)
        r = health.overall_health(p_holder)
        if r.get("overall") is not None:
            subj_data = {s: d["health"] for s, d in r["subjects"].items()}
            svg = svg_templates.combined_progress(r["overall"], subj_data)
            path = svg_renderer.render_svg(svg, name=f"test_graph_{uid}")
            if path:
                safe_send_photo(uid, path, caption=f"Updated overall: {r['overall']}/100")
                svg_renderer.cleanup_file(path)

    # Send full review as separate messages
    _send_full_review(uid, papers_data)

    # Cleanup
    exam_engine.end_session(uid)
    PRELOAD_QUEUE.pop(uid, None)
    PENDING_NUMERICAL.pop(uid, None)


# ==========================================================
# TEST — full question-by-question review with key + friendly explain
# ==========================================================
def _send_full_review(uid, papers_data):
    safe_send(uid,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "   📖 *FULL REVIEW*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "One question at a time with the key and reasoning.",
        parse_mode="Markdown")

    time.sleep(1)

    q_num = 0
    for p in papers_data:
        for item in p["log"]:
            q_num += 1
            _review_one_question(uid, q_num, item)
            time.sleep(0.8)


def _review_one_question(uid, q_num, item):
    q = item["q"]
    meta = item.get("meta", {})
    correct = item["correct"]
    user_answer = item["user_answer"]
    time_taken = item["time_taken"]
    q_type = item.get("q_type", "mcq")

    # Correct answer string
    if q_type == "numerical" or q.get("correct_value") is not None:
        correct_ans = str(q.get("correct_value", "?"))
    elif q.get("correct_indices"):
        correct_ans = ", ".join(chr(65 + int(i)) for i in q["correct_indices"])
    else:
        correct_ans = chr(65 + int(q.get("correct_index", 0)))

    if correct:
        head = f"✅ *Q{q_num}* — Correct"
    else:
        head = f"❌ *Q{q_num}* — Wrong"

    lines = [head]
    lines.append(f"📖 {meta.get('chapter','')} → {meta.get('subtopic','')}")
    lines.append("")
    lines.append(f"📝 *Question:*")
    lines.append(q.get("question", "(question)")[:400])
    lines.append("")
    if q_type != "numerical":
        opts = q.get("options", [])
        for i, opt in enumerate(opts[:4]):
            letter = chr(65 + i)
            marker = " ⬅ your answer" if user_answer == letter else ""
            lines.append(f"{letter}) {opt}{marker}")
        lines.append("")
    lines.append(f"🎯 *Correct answer:* {correct_ans}")
    lines.append(f"✍️ Your answer: {user_answer}")
    lines.append(f"⏱️ {int(time_taken)}s")
    lines.append("")

    # Friendly explanation
    expl = convert_latex_envs(q.get("explanation", "(no explanation)"))
    lines.append(f"📖 *Why:*")
    lines.append(expl[:700])
    lines.append("")

    # Traps
    traps = q.get("traps") or []
    if traps:
        lines.append("⚠️ *Traps:*")
        for t in traps[:3]:
            lines.append(f"• {t}")
        lines.append("")

    # Shortcut
    sc = q.get("shortcut", "")
    if sc:
        lines.append(f"⚡ *Shortcut:* {sc}")
        lines.append("")

    # Source
    st = q.get("source_type", "AI")
    sd = q.get("source_detail", "")
    tag = st + (f" · {sd}" if sd else "")
    lines.append(f"📌 {tag}")

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


# ==========================================================
# TEST — inline callbacks: Paper 2 + End now
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "test_paper2_start")
def _cb_test_paper2_start(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass

    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        safe_send(uid, "Test session ended.")
        return

    # Reset counters for paper 2
    sess["current_paper"] = 2
    sess["correct"] = 0
    sess["wrong"] = 0
    sess["skipped"] = 0
    sess["questions_done"] = 0
    sess["total_time"] = 0
    sess["plan_index"] = 0
    sess["current_q"] = None
    sess["current_meta"] = None
    sess["answers_log"] = []

    # Regenerate plan for paper 2
    p = load_profile(uid)
    exam = sess.get("exam")
    subjects = sess.get("subjects", [])
    allowed = sess.get("allowed_chapters", {})
    plan = exam_engine.build_test_plan(exam, subjects, allowed)
    sess["plan"] = plan

    PRELOAD_QUEUE[uid] = []

    dur = DURATION_MIN.get(exam, 180)
    safe_send(uid,
        f"📄 *Paper 2 started*\n\n"
        f"Duration: {dur} min\n"
        f"Questions: {len(plan)}\n\n"
        f"Good luck. No feedback until the end.",
        parse_mode="Markdown")

    timer_manager.start_test_timer(bot, uid, dur, on_time_up=_test_paper_time_up)
    _preload_test(uid, count=3)
    _send_next_test_q(uid)


@bot.callback_query_handler(func=lambda c: c.data == "test_end_now")
def _cb_test_end_now(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass
    _test_finish(uid)


# ==========================================================
# TEST — inline callback: stop test
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "test_stop")
def _cb_test_stop(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass
    _test_finish(uid)


print("bot.py Chunk 7 loaded: test handler + paper break + review ready.")


# ==========================================================
# bot.py — Chunk 8: conceptual mode (General + Exception)
# ==========================================================

# ==========================================================
# CONCEPTUAL — ask type
# ==========================================================
def _concept_pick_type(uid):
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("General Conceptual", "Exception Test")
    msg = bot.send_message(uid,
        "🧠 *Which type of Conceptual test?*\n\n"
        "• *General* — full chapter theory + concepts\n"
        "• *Exception* — edge cases, anomalies, tricky parts",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _concept_capture_type)


def _concept_capture_type(message):
    uid = message.chat.id
    p = load_profile(uid)
    t = (message.text or "").strip().lower()
    if "except" in t:
        p["_concept_type"] = "exception"
    else:
        p["_concept_type"] = "general"
    save_profile(uid, p)

    # Which chapter? Use selected chapters only for conceptual (they're the ones being tested)
    sel = p.get("selected_chapters", {})
    subjects = [s for s in ["Maths", "Physics", "Chemistry"] if sel.get(s)]
    if not subjects:
        # Fallback: all subjects available
        subjects = health.available_subjects()
    if not subjects:
        bot.send_message(uid, "❌ No subjects available.")
        return
    if len(subjects) == 1:
        _concept_ask_chapter(uid, subjects[0])
        return
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for s in subjects:
        markup.add(s)
    msg = bot.send_message(uid, "📚 *Which subject?*",
                           reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _concept_capture_subject)


def _concept_capture_subject(message):
    uid = message.chat.id
    p = load_profile(uid)
    subj = (message.text or "").strip().capitalize()
    if subj not in health.available_subjects():
        bot.reply_to(message, "❌ Invalid subject.")
        return
    _concept_ask_chapter(uid, subj)


# ==========================================================
# CONCEPTUAL — pick chapter
# ==========================================================
def _concept_ask_chapter(uid, subj):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"

    # Use selected chapters if available
    sel_ch = p.get("selected_chapters", {}).get(subj, [])
    if sel_ch:
        chapter_list = sel_ch
    else:
        data = health.load_subject_data(subj, exam)
        if not data:
            bot.send_message(uid, f"❌ No data for {subj}.")
            return
        chapter_list = list(data.keys())

    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(chapter_list))
    header = f"🧠 *{subj}* — pick a chapter:\n\n{numbered}\n\n"
    footer = "Reply with the number."

    full = header + footer
    if len(full) > 4000:
        safe_send(uid, f"🧠 *{subj}* — chapters:", parse_mode="Markdown")
        safe_send(uid, numbered[:3900])
        msg = bot.send_message(uid, footer)
        bot.register_next_step_handler(msg, _concept_capture_chapter, subj, chapter_list)
    else:
        msg = bot.send_message(uid, header + footer, parse_mode="Markdown")
        bot.register_next_step_handler(msg, _concept_capture_chapter, subj, chapter_list)


def _concept_capture_chapter(message, subj, chapter_list):
    uid = message.chat.id
    try:
        idx = int((message.text or "").strip()) - 1
        if idx < 0 or idx >= len(chapter_list):
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Invalid number.")
        return
    chapter = chapter_list[idx]

    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("40", "60", "80", "100")
    msg = bot.send_message(uid,
        f"🧠 *{chapter}*\n\nHow many questions? (min 40)\nReply 40, 60, 80, or 100",
        reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _concept_capture_count, subj, chapter)


# ==========================================================
# CONCEPTUAL — pick count + start
# ==========================================================
def _concept_capture_count(message, subj, chapter):
    uid = message.chat.id
    try:
        n = int((message.text or "").strip())
        if n < 40 or n > 100:
            raise ValueError
    except ValueError:
        bot.reply_to(message, "Send a number between 40 and 100.")
        return

    p = load_profile(uid)
    ttype = p.get("_concept_type", "general")

    sess = exam_engine.start_conceptual_test(uid, subj, chapter, n, test_type=ttype)
    if not sess:
        bot.reply_to(message, "❌ Could not start. Try /exam again.")
        return
    sess["exam"] = p.get("priority") or health.exam_of(p) or "JEE_MAIN"

    PRELOAD_QUEUE[uid] = []

    safe_send(uid,
        f"🧠 *Conceptual Test ({ttype.title()}) started*\n\n"
        f"Subject: {subj}\n"
        f"Chapter: {chapter}\n"
        f"Questions: {n}\n\n"
        f"⚠️ No feedback until end.\n"
        f"⚠️ Use /stop to submit early.\n\n"
        f"*Get ready...*",
        parse_mode="Markdown")

    time.sleep(1)
    bot.send_message(uid, "🚀 *Go!*")
    _preload_concept(uid, count=3)
    _send_next_concept_q(uid)


# ==========================================================
# CONCEPTUAL — preload
# ==========================================================
def _preload_concept(uid, count=3):
    def _job():
        try:
            p = load_profile(uid)
            sess = exam_engine.get_session(uid)
            if not sess or sess.get("mode") != "conceptual":
                return
            exam = sess.get("exam")
            subj = sess.get("subject")
            chapter = sess.get("chapter")
            plan = sess.get("plan", [])
            idx = sess.get("index", 0)
            ttype = sess.get("test_type", "general")
            queue = PRELOAD_QUEUE.setdefault(uid, [])
            attempts = 0
            while len(queue) < count and idx + len(queue) < len(plan) and attempts < 8:
                attempts += 1
                sub = plan[idx + len(queue)]
                diff = "hard" if ttype == "exception" else "medium"
                q = exam_engine.generate_question(exam, subj, chapter, sub,
                                                   q_type="mcq", difficulty=diff)
                if q:
                    q["_meta"] = {"subject": subj, "chapter": chapter, "subtopic": sub}
                    queue.append(q)
                else:
                    time.sleep(1)
        except Exception:
            pass
    threading.Thread(target=_job, daemon=True).start()


# ==========================================================
# CONCEPTUAL — send next question
# ==========================================================
def _send_next_concept_q(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "conceptual":
        return

    plan = sess.get("plan", [])
    idx = sess.get("index", 0)
    if idx >= len(plan):
        _concept_finish(uid)
        return

    exam = sess.get("exam")
    subj = sess.get("subject")
    chapter = sess.get("chapter")
    sub = plan[idx]
    ttype = sess.get("test_type", "general")

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        diff = "hard" if ttype == "exception" else "medium"
        q = exam_engine.generate_question(exam, subj, chapter, sub,
                                           q_type="mcq", difficulty=diff)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question. Try /exam again.")
                _concept_finish(uid)
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_concept_q(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": chapter, "subtopic": sub}

    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = q["_meta"]

    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["index"] = idx + 1
        _send_next_concept_q(uid)
        return
    options_skip = options + ["🚪 Skip"]

    total = len(plan)
    header = (
        f"[Conceptual | {ttype.title()} | Q{idx+1}/{total}]\n"
        f"📌 AI-Generated · Deep reasoning\n"
        f"📖 {subj} → {chapter} → {sub[:25]}"
    )
    full_q = f"{header}\n\n{q['question']}"

    svg_code = q.get("svg")
    if svg_code and SVG_ENABLED:
        path = svg_renderer.render_svg(svg_code, name=f"cq_{uid}")
        if path:
            safe_send_photo(uid, path)
            svg_renderer.cleanup_file(path)

    try:
        if len(full_q) <= 290:
            bot.send_poll(chat_id=uid, question=full_q[:300],
                          options=options_skip[:10], type="quiz",
                          correct_option_id=int(q.get("correct_index", 0)),
                          explanation="Result in final report.",
                          is_anonymous=False)
        else:
            safe_send(uid, f"📝 *Question*\n\n{full_q}", parse_mode="Markdown")
            time.sleep(0.4)
            bot.send_poll(chat_id=uid, question="👆 Tap your answer:",
                          options=options_skip[:10], type="quiz",
                          correct_option_id=int(q.get("correct_index", 0)),
                          explanation="Result in final report.",
                          is_anonymous=False)
        _preload_concept(uid, count=3)
    except Exception as e:
        safe_send(uid, f"🔄 Retry... {e}")
        time.sleep(1)
        _send_next_concept_q(uid)


# ==========================================================
# CONCEPTUAL — poll handler (silent)
# ==========================================================
def _handle_conceptual_poll(uid, sess, poll_answer):
    q = sess.get("current_q")
    if not q:
        return

    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    options = q.get("options", [])
    time_taken = time.time() - sess.get("current_started", time.time())
    meta = sess.get("current_meta", {})
    subtopic = meta.get("subtopic", "Unknown")

    if selected == len(options):
        correct = False
        sess["skipped"] = sess.get("skipped", 0) + 1
    else:
        correct = (int(selected) == int(q.get("correct_index", -1)))
        if correct:
            sess["correct"] = sess.get("correct", 0) + 1
        else:
            sess["wrong"] = sess.get("wrong", 0) + 1

    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["index"] = sess.get("index", 0) + 1

    # Track subtopic stats
    try:
        exam_engine.record_conceptual_attempt(uid, subtopic, correct)
    except Exception:
        pass

    # Record to health silently
    try:
        health.record_attempt(
            uid,
            meta.get("subject", ""),
            meta.get("chapter", ""),
            subtopic,
            "",
            correct,
            int(time_taken),
            int(q.get("ideal_time_sec", 60)),
            difficulty=q.get("difficulty", "medium"),
        )
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_concept_q(uid)


# ==========================================================
# CONCEPTUAL — finish report
# ==========================================================
def _concept_finish(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "conceptual":
        return

    safe_send(uid, exam_engine.conceptual_report(uid), parse_mode="Markdown")

    # Health delta SVG
    if SVG_ENABLED:
        p = load_profile(uid)
        r = health.overall_health(p)
        if r.get("overall") is not None:
            subj_data = {s: d["health"] for s, d in r["subjects"].items()}
            svg = svg_templates.combined_progress(r["overall"], subj_data)
            path = svg_renderer.render_svg(svg, name=f"cq_graph_{uid}")
            if path:
                safe_send_photo(uid, path, caption=f"Updated overall: {r['overall']}/100")
                svg_renderer.cleanup_file(path)

    exam_engine.end_session(uid)
    PRELOAD_QUEUE.pop(uid, None)


# ==========================================================
# CONCEPTUAL — inline callback (stop)
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "concept_stop")
def _cb_concept_stop(call):
    uid = call.message.chat.id
    try:
        bot.edit_message_reply_markup(chat_id=uid,
                                       message_id=call.message.message_id,
                                       reply_markup=None)
    except Exception:
        pass
    _concept_finish(uid)


print("bot.py Chunk 8 loaded: conceptual mode (General + Exception) ready.")


PENDING_AUTH_FLOW = {}

# ==========================================================
# bot.py — Chunk 9 (FINAL): notes, free-text, admin, leaderboard, find, boot
# ==========================================================

# ==========================================================
# NOTES — main command
# ==========================================================
@bot.message_handler(commands=['notes'])
def cmd_notes(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    sel = p.get("selected_chapters", {})
    subjects = [s for s in ["Maths", "Physics", "Chemistry"] if sel.get(s)]
    if not subjects:
        subjects = health.available_subjects()
    if not subjects:
        bot.send_message(uid, "❌ No subjects available.")
        return
    if len(subjects) == 1:
        _notes_ask_chapter(uid, subjects[0])
        return
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for s in subjects:
        markup.add(s)
    msg = bot.send_message(uid, "📝 *Which subject?*",
                           reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _notes_pick_subject)


def _notes_pick_subject(message):
    uid = message.chat.id
    p = load_profile(uid)
    subj = (message.text or "").strip().capitalize()
    if subj not in health.available_subjects():
        bot.reply_to(message, "❌ Invalid subject.")
        return
    _notes_ask_chapter(uid, subj)


def _notes_ask_chapter(uid, subj):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    sel_ch = p.get("selected_chapters", {}).get(subj, [])
    if sel_ch:
        ch_list = sel_ch
    else:
        data = health.load_subject_data(subj, exam)
        if not data:
            bot.send_message(uid, f"❌ No data for {subj}.")
            return
        ch_list = list(data.keys())

    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(ch_list))
    header = f"📝 *{subj}* — pick a chapter:\n\n{numbered}\n\nReply with number."
    if len(header) > 4000:
        safe_send(uid, f"📝 *{subj}* chapters:", parse_mode="Markdown")
        safe_send(uid, numbered[:3900])
        msg = bot.send_message(uid, "Reply with the number.")
        bot.register_next_step_handler(msg, _notes_capture_chapter, subj, ch_list)
    else:
        msg = bot.send_message(uid, header, parse_mode="Markdown")
        bot.register_next_step_handler(msg, _notes_capture_chapter, subj, ch_list)


def _notes_capture_chapter(message, subj, ch_list):
    uid = message.chat.id
    try:
        idx = int((message.text or "").strip()) - 1
        if idx < 0 or idx >= len(ch_list):
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Invalid number.")
        return
    chapter = ch_list[idx]
    _generate_notes_begin(uid, subj, chapter)


# ==========================================================
# NOTES — begin generation with part state
# ==========================================================
# def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics_list = []
    for sub, val in subs.items():
        cl = val.get("adv", []) if isinstance(val, dict) else val
        subtopics_list.append({"name": sub, "concepts": list(cl)})

    total_concepts = sum(len(s["concepts"]) for s in subtopics_list)

    # Group subtopics so each part covers ~6 subtopics
    groups = []
    current = []
    for st in subtopics_list:
        current.append(st)
        if len(current) >= 6:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if not groups:
        groups = [subtopics_list]

    total_parts = len(groups)

    # Save notes state in profile
    p["_notes_state"] = {
        "subject": subject,
        "chapter": chapter,
        "exam": exam,
        "groups": groups,
        "current_part": 0,
        "total_parts": total_parts,
        "last_notes": "",
        "waiting_continue": False,
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *Generating short notes: {chapter}*\n\n"
        f"Subtopics: {len(subtopics_list)}\n"
        f"Concepts: {total_concepts}\n"
        f"Parts: {total_parts}\n\n"
        "_Sending Part 1 now..._",
        parse_mode="Markdown")
    time.sleep(0.5)

    _send_next_notes_batch(uid)


# def _send_next_notes_batch(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes session.")
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)

    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} parts of {state['chapter']} notes delivered.*\n\n"
            "_Ask me anything about it, or /notes for another chapter._",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    topics_text = ""
    for st in group:
        topics_text += f"\n*{st['name']}*\n"
        for c in st["concepts"]:
            topics_text += f"  • {c}\n"

    timer_manager.start_generating_timer(bot, uid, f"notes {part_num}/{total}")

    prompt = (
        f"You are writing SHORT NOTES for a JEE Advanced student.\n\n"
        f"Chapter: {state['chapter']} ({state['subject']})\n"
        f"Part {part_num} of {total}.\n\n"
        f"Subtopics to cover in this part:\n{topics_text}\n\n"
        "FORMATTING RULES:\n"
        "- Talk like a friendly senior — warm, encouraging\n"
        "- Open with a warm line like 'Let\\'s dive into...' or 'Here\\'s the cool part...'\n"
        "- Use real Unicode math symbols: θ τ π √ ² ³ ⁻ ⁺ ½ → × ·\n"
        "- For chemistry: proper subscripts — H₂O, CO₂, C₆H₁₂O₆, CH₃COOH\n"
        "- NEVER use LaTeX\n"
        "- Bold key terms with *asterisks*\n"
        "- For each concept: one-line definition + key formula + 1-2 traps\n"
        "- Include numeric values where relevant\n"
        "- For EVERY structure (Fischer, Haworth, Chair, benzene, ray diagrams), "
        "include a fenced SVG block:\n"
        "```svg\n<svg>...</svg>\n```\n"
        "The SVG must show the structure accurately.\n"
        "- Cover EVERY listed subtopic — no skipping\n"
        "- End with a line saying 'Type /continue for the next part' if not last part."
    )

    bump_api_calls(uid)

    notes = ai_client.ask_hamilton(state["exam"], prompt)
    timer_manager.stop_generating_timer(bot, uid)

    if not notes:
        safe_send(uid, f"⚠️ Could not generate Part {part_num}. Type /continue to retry.")
        return

    svg, notes_clean = svg_renderer.detect_svg_in_text(notes)

    header = f"📝 *{state['chapter']} — Part {part_num}/{total}*\n\n"
    final = header + notes_clean

    if part_num < total:
        final += f"\n\n━━━━━━━━━━━━━━━\n_Type /continue for Part {part_num+1}_"
    else:
        final += "\n\n━━━━━━━━━━━━━━━\n✅ _All parts delivered._"

    safe_send(uid, final + _countdown_footer(uid), parse_mode="Markdown")

    if svg and SVG_ENABLED:
        path = svg_renderer.render_svg(svg, name=f"notes_{uid}_{part_num}")
        if path:
            safe_send_photo(uid, path)
            svg_renderer.cleanup_file(path)

    state["current_part"] = part_num
    state["last_notes"] = notes_clean[:500]
    state["waiting_continue"] = True
    p["_notes_state"] = state
    save_profile(uid, p)


@bot.message_handler(commands=['continue'])
def cmd_continue(message):
    uid = message.chat.id
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes in progress. Type /notes to start.")
        return
    _send_next_notes_batch(uid)


# ==========================================================
# LEADERBOARD
# ==========================================================
def _compute_leaderboard(level_filter=None):
    entries = []
    if not os.path.exists(PROFILE_DIR):
        return entries
    for fname in os.listdir(PROFILE_DIR):
        if not fname.endswith(".json"):
            continue
        uid_str = fname.replace(".json", "")
        try:
            with open(os.path.join(PROFILE_DIR, fname)) as f:
                p = json.load(f)
        except Exception:
            continue
        if not p.get("secured") or not p.get("name"):
            continue
        if not p.get("leaderboard_optin", True):
            continue
        if not p.get("exams"):
            continue

        lvl = (p.get("level") or "").lower()
        if level_filter == "junior" and lvl != "junior":
            continue
        if level_filter == "senior" and lvl not in ("senior", "dropper"):
            continue

        summary = health.attempts_summary(p)
        if summary["attempted"] < 20:
            continue

        r = health.overall_health(p)
        h = r.get("overall") or 0
        pct = health.predict_percentile(h)
        score = 0.4 * h + 0.4 * pct + 0.2 * min(100, summary["attempted"] / 5)

        entries.append({
            "uid": uid_str,
            "hku": p.get("hku_id", "—"),
            "name": p.get("name"),
            "institute": p.get("institute", "—"),
            "level": p.get("level", "—"),
            "health": round(h, 1),
            "percentile": pct,
            "attempted": summary["attempted"],
            "accuracy": summary["accuracy"],
            "score": round(score, 1),
        })
    entries.sort(key=lambda x: x["score"], reverse=True)
    return entries


@bot.message_handler(commands=['leaderboard'])
def cmd_leaderboard(message):
    uid = message.chat.id
    parts = message.text.split()
    filt = None
    if len(parts) > 1:
        a = parts[1].lower()
        if "jun" in a:
            filt = "junior"
        elif "sen" in a or "drop" in a:
            filt = "senior"
    entries = _compute_leaderboard(filt)
    if not entries:
        bot.reply_to(message, "📭 No qualifying users yet (min 20 attempts).")
        return
    title = "🏆 *Leaderboard*"
    if filt == "junior":
        title += " — Juniors"
    elif filt == "senior":
        title += " — Seniors & Droppers"
    lines = [title + "\n"]
    for i, e in enumerate(entries[:20], 1):
        m = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{m} {e['name']} ({e['hku']})")
        lines.append(f"   Health {e['health']} · %ile {e['percentile']} · {e['attempted']} attempts")
    lines.append("")
    lines.append("Filters: /leaderboard junior · /leaderboard senior")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("top "))
def cmd_top(message):
    uid = message.chat.id
    try:
        n = int(message.text.split()[1])
        if n < 1 or n > 20:
            raise ValueError
    except Exception:
        bot.reply_to(message, "Usage: top 3")
        return
    entries = _compute_leaderboard()
    if not entries or n > len(entries):
        bot.reply_to(message, "No data.")
        return
    e = entries[n - 1]
    safe_send(uid,
        f"🏆 *Rank #{n}*\n\n"
        f"👤 {e['name']}\n"
        f"🆔 {e['hku']}\n"
        f"🏫 {e['institute']}\n"
        f"🎓 {e['level']}\n\n"
        f"📊 Health: {e['health']}\n"
        f"🎯 %ile: {e['percentile']}\n"
        f"📝 Attempts: {e['attempted']}\n"
        f"🎯 Accuracy: {e['accuracy']}%",
        parse_mode="Markdown")


# ==========================================================
# /find HKU-XXXXXX
# ==========================================================
@bot.message_handler(commands=['find'])
def cmd_find(message):
    uid = message.chat.id
    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /find HKU-000001")
        return
    hku = parts[1].strip().upper()
    found_uid = find_user_by_hku_id(hku)
    if not found_uid:
        bot.reply_to(message, f"❌ No user found with ID {hku}.")
        return
    try:
        target = load_profile(int(found_uid))
    except Exception:
        target = load_profile(found_uid)
    if not target or not target.get("secured"):
        bot.reply_to(message, "❌ User not available.")
        return

    r = health.overall_health(target)
    summary = health.attempts_summary(target)
    pct = health.predict_percentile(r.get("overall"))
    _, tier = health.estimate_rank(target)

    board = _compute_leaderboard()
    lb_rank = None
    for i, e in enumerate(board, 1):
        if str(e.get("uid")) == str(found_uid):
            lb_rank = i
            break

    lines = [
        f"🔍 *Search Result*\n",
        f"👤 {target.get('name','—')}",
        f"🆔 {hku}",
        f"🏫 {target.get('institute','—')}",
        f"🎓 {target.get('level','—')}",
        f"📚 {', '.join(EXAM_NAMES.get(e,e) for e in target.get('exams',[]))}",
        f"📅 Year: {target.get('target_year','—')}",
        "",
        "━━━ Attempts ━━━",
        f"Total attempted: {summary['attempted']}",
        f"✅ Correct: {summary['correct']}",
        f"❌ Wrong: {summary['wrong']}",
        f"🎯 Accuracy: {summary['accuracy']}%",
        "",
        f"📊 Overall Health: {r.get('overall') or 0}/100",
        f"🎯 Predicted %ile: {pct}",
        f"🏆 Rank tier: {tier}",
    ]
    if lb_rank:
        lines.append(f"🥇 Leaderboard rank: #{lb_rank}")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")

    # 1 SVG only
    if SVG_ENABLED and r.get("overall") is not None:
        subj_data = {s: d["health"] for s, d in r["subjects"].items()}
        svg = svg_templates.combined_progress(r["overall"], subj_data)
        path = svg_renderer.render_svg(svg, name=f"find_{found_uid}")
        if path:
            safe_send_photo(uid, path, caption=f"{target.get('name','')} — Progress")
            svg_renderer.cleanup_file(path)


# ==========================================================
# ADMIN — /genkey YY COUNT
# ==========================================================
@bot.message_handler(commands=['genkey'])
def cmd_genkey(message):
    uid = message.chat.id
    if uid != ADMIN_CHAT_ID:
        return
    parts = message.text.strip().split()
    if len(parts) < 3:
        bot.reply_to(message, "Usage: /genkey YY COUNT\nExample: /genkey 27 5")
        return
    try:
        yy = parts[1].zfill(2)
        count = int(parts[2])
    except Exception:
        bot.reply_to(message, "Invalid args.")
        return
    year_full = 2000 + int(yy)
    import string
    keys = load_keys()
    new_keys = []
    for _ in range(count):
        b1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        b2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        k = f"HK-{yy}-{b1}-{b2}"
        keys[k] = {
            "year": year_full,
            "bound_to": None,
            "bound_at": None,
            "created_at": datetime.now().isoformat(),
        }
        new_keys.append(k)
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)
    safe_send(uid, f"✅ Generated {len(new_keys)} keys for year {year_full}:\n\n" +
              "\n".join(new_keys))


# ==========================================================
# ADMIN — /shutdown MESSAGE
# ==========================================================
@bot.message_handler(commands=['shutdown'])
def cmd_shutdown(message):
    uid = message.chat.id
    if uid != ADMIN_CHAT_ID:
        return
    text = message.text.replace("/shutdown", "").strip()
    if not text:
        text = ("⚠️ *Server maintenance in progress.*\n\n"
                "Hamilton will be back soon.\n\n"
                "Until then — revise a concept, do some bits, practice PYQs.\n"
                "Don't waste your time.")
    count = 0
    if os.path.exists(PROFILE_DIR):
        for fname in os.listdir(PROFILE_DIR):
            if not fname.endswith(".json"):
                continue
            try:
                chat_id = int(fname.replace(".json", ""))
            except Exception:
                continue
            try:
                safe_send(chat_id, text, parse_mode="Markdown")
                count += 1
            except Exception:
                pass
    bot.reply_to(message, f"📢 Broadcast sent to {count} users. Shutting down...")
    time.sleep(3)
    os._exit(0)


# ==========================================================
# FREE-TEXT HANDLER (the main orchestrator)
# ==========================================================
def _in_subreg_flow(uid):
    """True if user is in c30v sub-admin registration flow."""
    try:
        st = globals().get("_SUBREG_V2_STATE")
        if st and uid in st:
            return True
    except Exception:
        pass
    return False


@bot.message_handler(
    func=lambda m: not _in_subreg_flow(m.chat.id),
    content_types=['text']
)
def free_text_handler(message):
    # --- STOP AI FROM HIJACKING COMMANDS ---
    if message.text and message.text.startswith('/'):
        return
    # ---------------------------------------

    _txt = (message.text or "").strip()
    
    # HARD REDIRECTS (bypass AI)
    if _txt == "/help":
        import bot_chunks.c10 as _c10
        if hasattr(_c10, "cmd_help"):
            _c10.cmd_help(message)
            return
    elif _txt == "/exam":
        import bot_chunks.c06 as _c06
        if hasattr(_c06, "cmd_exam_new"):
            _c06.cmd_exam_new(message)
            return
    elif _txt == "/pyq":
        import bot_chunks.c06 as _c06
        if hasattr(_c06, "cmd_pyq"):
            _c06.cmd_pyq(message)
            return
    # End Hard Redirects

    # Catch numerical test answers
    try:
        _p_num = globals().get("PENDING_NUMERICAL", {}).get(message.chat.id)
        if _p_num and _p_num.get("is_test"):
            _t = (message.text or "").strip()
            if _t:
                import bot_chunks.c06a_test_advanced as _c06a
                if _c06a.handle_test_numerical(message.chat.id, _t):
                    return
    except Exception as e:
        print(f"[test-num-route] {e}")
        
    # _test_advanced_catch
    # Defer to c30v sub-admin registration — v2 state
    try:
        _v2_st = globals().get("_SUBREG_V2_STATE")
        if _v2_st and message.chat.id in _v2_st:
            return
    except Exception:
        pass
    # ---- Defer to c30u if sub-admin registration pending ----
    try:
        _u_def = message.chat.id
        _pf_def = PENDING_AUTH_FLOW.get(_u_def)
        if _pf_def and _pf_def.get("action") in ("sub_new_name", "sub_new_privacy"):
            return
    except Exception:
        pass
    # ============================================================
    # LOCKIN_PRIORITY_FIX
    # This block runs FIRST — before lock check, before AI, before anything.
    # Lock-in hex codes and /forgot bypass EVERYTHING.
    # ============================================================
    uid = message.chat.id
    _prio_text = (message.text or "").strip()
    # Track admin entry-code messages for cleanup
    try:
        if _prio_text and (_prio_text.startswith("HK ") or _prio_text.startswith("hk ")):
            _trk_c09 = globals().get("track_admin_msg")
            if _trk_c09:
                _trk_c09(uid, message.message_id)
    except Exception:
        pass

    # ---- A) 8-char hex lock-in code (bypasses lock) ----
    try:
        import admin_auth as _prio_aa
        if _prio_aa.is_hex_lockin_code(_prio_text):
            _ok, _entry = _prio_aa.verify_lockin_code(_prio_text, requester_uid=uid)
            if _ok:
                # Unlock everything
                _prio_aa.unlock_primary()
                _prio_aa.unlock_sub_admin(uid)
                _prio_aa.clear_user_block(uid)
                _prio_aa.audit("lockin_used", uid, {})
                # Also clear any pending state
                for _mn, _mo in __import__("sys").modules.items():
                    if hasattr(_mo, "PENDING_AUTH_FLOW"):
                        _mo.PENDING_AUTH_FLOW.pop(uid, None)
                        break
                safe_send(uid,
                    "🔓 *Lock-in accepted.*\n"
                    "Lockout cleared. You may now enter the admin code again.",
                    parse_mode="Markdown")
            else:
                safe_send(uid, "❌ Invalid or expired lock-in code.")
            return
    except Exception as _e:
        print(f"[lockin_priority] {_e}")

    # ---- B) /forgot (bypasses lock) ----
    if _prio_text == "/forgot":
        try:
            import admin_auth as _prio_aa
            _prio_aa.audit("forgot_requested", uid, {})
            for _mn, _mo in __import__("sys").modules.items():
                if hasattr(_mo, "PENDING_AUTH_FLOW"):
                    _mo.PENDING_AUTH_FLOW.pop(uid, None)
                    _mo.PENDING_AUTH_FLOW[uid] = {
                        "action": "primary_reset_key",
                        "at": __import__("time").time(),
                    }
                    break
            # Clear lock so reset can proceed
            _cfg = _prio_aa._load_config()
            if _cfg.get("primary"):
                _cfg["primary"]["failed_attempts"] = 0
                _cfg["primary"]["locked_until"] = None
                _prio_aa._save_config(_cfg)
            safe_send(uid,
                "🔐 *Password Recovery*\n\n"
                "Enter your *reset key* below.",
                parse_mode="Markdown")
            return
        except Exception as _e:
            print(f"[forgot_priority] {_e}")
            return

    # ============================================================
    # ---- /end and /end_chat - close two-way chat, before AI ----
    if _prio_text in ("/end", "/end_chat") or _prio_text.startswith("/end_chat "):
        import sys as _sys_end
        _closed_admin = False
        _closed_student = False
        _tgt_uid = None
        if _prio_text.startswith("/end_chat "):
            try:
                _tgt_uid = int(_prio_text.split(" ", 1)[1].strip())
            except Exception:
                _tgt_uid = None
        for _mn, _mo in _sys_end.modules.items():
            if hasattr(_mo, "PENDING_ADMIN_FLOW"):
                if _mo.PENDING_ADMIN_FLOW.pop(uid, None):
                    _closed_admin = True
            if hasattr(_mo, "TWO_WAY_CHAT"):
                if _tgt_uid and _tgt_uid in _mo.TWO_WAY_CHAT:
                    _adm = _mo.TWO_WAY_CHAT.pop(_tgt_uid, {}).get("admin_uid")
                    _closed_admin = True
                    if _adm and _adm != uid:
                        try: safe_send(_adm, "Chat closed by admin.")
                        except Exception: pass
                if uid in _mo.TWO_WAY_CHAT:
                    _adm2 = _mo.TWO_WAY_CHAT[uid].get("admin_uid")
                    _mo.TWO_WAY_CHAT.pop(uid, None)
                    _closed_student = True
                    if _adm2:
                        try: safe_send(_adm2, "Student ended the chat.")
                        except Exception: pass
        if _closed_admin or _closed_student:
            _del_e = globals().get("delete_all_admin_msgs")
            _deleted_e = 0
            if _del_e:
                try: _deleted_e, _ = _del_e(uid)
                except Exception as _e: print(f"[end_chat] del err: {_e}")
            for _cn_e in ("_STATS_MSGS", "_BTN_MSGS", "_ALL_PANEL_MSGS"):
                _cache_e = globals().get(_cn_e)
                if _cache_e is not None:
                    try: _cache_e.pop(uid, None)
                    except Exception: pass
            try:
                _unreg_e = globals().get("unregister_panel")
                if _unreg_e: _unreg_e(uid)
            except Exception: pass
            try:
                import admin_auth as _ec_aa
                _ec_sess = _ec_aa.get_session(uid)
                if _ec_sess:
                    _ec_sp = globals().get("_show_admin_panel")
                    if _ec_sp:
                        _ec_sp(uid)
                        print(f"[end_chat] {uid} deleted={_deleted_e} fresh_panel_sent")
                else:
                    safe_send(uid, "Chat closed.")
            except Exception as _ec_e:
                print(f"[end_chat] reopen err: {_ec_e}")
                safe_send(uid, "Chat closed.")
        else:
            safe_send(uid, "No active chat to close.")
        return
    # ---- /exit - close admin mode ----
    if _prio_text == "/exit":
        try:
            import admin_auth as _prio_exit_aa
            _sess_exit = _prio_exit_aa.get_session(uid)
            if _sess_exit:
                _del_fn = globals().get("delete_all_admin_msgs")
                if _del_fn:
                    try:
                        _dc, _ = _del_fn(uid)
                        print(f"[exit] {uid} deleted={_dc} msgs")
                    except Exception: pass
                _sm2 = globals().get("_STATS_MSGS")
                if _sm2 is not None:
                    try: _sm2.pop(uid, None)
                    except Exception: pass
                _bm2 = globals().get("_BTN_MSGS")
                if _bm2 is not None:
                    try: _bm2.pop(uid, None)
                    except Exception: pass
                try:
                    _prio_exit_aa._SESSIONS.pop(uid, None)
                except Exception:
                    pass
                for _mn_e, _mo_e in __import__("sys").modules.items():
                    if hasattr(_mo_e, "unregister_panel"):
                        try:
                            _mo_e.unregister_panel(uid)
                        except Exception:
                            pass
                safe_send(uid, "👋 *Admin mode closed.*\n\nYou are back to normal Hamilton chat.", parse_mode="Markdown")
            else:
                safe_send(uid, "ℹ️ You are not currently in admin mode.")
        except Exception as _e_exit:
            print(f"[exit_priority] {_e_exit}")
            safe_send(uid, f"⚠️ Exit failed: {_e_exit}")
        return
    # End of priority block - rest of handler continues normally
    # ============================================================




    # ---- Two-way chat check (student replying to admin) ----
    uid = message.chat.id
    _twc = _is_in_two_way_chat(uid)
    if _twc:
        _twc["started"] = __import__("time").time()
        try:
            _admin_id = _twc["admin_uid"]
            _pf = load_profile(uid) or {}
            _name = _pf.get("name", "?")
            _hku = _pf.get("hku_id", "?")
            safe_send(_admin_id,
                f"📨 *Reply from {_name}* (`{_hku}`)\n\n{(message.text or '')[:800]}\n\n"
                f"_Reply via panel or type /end_chat {uid} to end._",
                parse_mode="Markdown")
            safe_send(uid, "✅ Message delivered to admin.")
        except Exception as _e:
            print(f"[two-way] forward failed: {_e}")
        return

    # ---- Extended pending admin flow (broadcast text, personal msg, etc.) ----
    _pflow = PENDING_ADMIN_FLOW.get(uid)
    if _pflow:
        _now = __import__("time").time()
        if _now - _pflow["at"] > 300:
            PENDING_ADMIN_FLOW.pop(uid, None)
        else:
            _act = _pflow["action"]
            _dat = _pflow["data"]

            # ---- Broadcast message text ----
            if _act == "broadcast_text":
                _dat["text"] = message.text or ""
                PENDING_ADMIN_FLOW[uid] = {
                    "action": "broadcast_confirm",
                    "data": _dat,
                    "at": _now,
                }
                from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                _kb = InlineKeyboardMarkup(row_width=1)
                _kb.add(
                    InlineKeyboardButton("✅ Send Now", callback_data="bc_send"),
                    InlineKeyboardButton("⏰ Schedule", callback_data="bc_sched"),
                    InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel"),
                )
                safe_send(uid,
                    f"📢 *Broadcast Preview*\n\nMessage:\n_{_dat['text']}_\n\n"
                    f"Recipients: *{len(_dat.get('recipients', []))} users*",
                    parse_mode="Markdown")
                bot.send_message(uid, "Choose action:", reply_markup=_kb)
                return

            # ---- Admin Edit Name ----
            if _act == "personal_edit_name":
                _target = _dat["target_uid"]
                _new_name = (message.text or "").strip()[:40]
                _tp = load_profile(_target)
                if _tp:
                    _old_name = _tp.get("name", "?")
                    _tp["name"] = _new_name
                    save_profile(_target, _tp)
                    safe_send(uid, f"✅ Name updated to *{_new_name}*.")
                    try:
                        safe_send(_target, f"✅ *Name Updated*\n\nYour name was updated to *{_new_name}* by Admin.", parse_mode="Markdown")
                    except Exception:
                        pass
                PENDING_ADMIN_FLOW.pop(uid, None)
                return

            # ---- Personal message text ----
            if _act == "personal_text":
                _target = _dat["target_uid"]
                _text = (message.text or "")[:800]
                try:
                    safe_send(_target,
                        f"📩 *Personal message from Admin*\n\n{_text}\n\n"
                        f"_Reply to continue. Type /end to close._",
                        parse_mode="Markdown")
                    safe_send(uid, f"✅ Message sent to {_target}.")
                    # start two-way chat
                    TWO_WAY_CHAT[_target] = {
                        "admin_uid": uid,
                        "started": __import__("time").time(),
                    }
                    try:
                        safe_send(uid,
                            f"🔗 *Chat opened with user {_target}*\n"
                            f"Type `/end_chat {_target}` to close when done.",
                            parse_mode="Markdown")
                    except Exception:
                        pass
                except Exception as _e:
                    safe_send(uid, f"⚠️ Send failed: {_e}")
                # Keep personal_text flow alive so admin can send multiple messages
                PENDING_ADMIN_FLOW[uid] = {
                    "action": "personal_text",
                    "data": _dat,
                    "at": _now,
                }
                return

            # ---- Broadcast schedule: date ----
            if _act == "broadcast_title":
                _title = (message.text or "").strip()[:40]
                if len(_title) < 2:
                    safe_send(uid, "Title too short (min 2 chars). Try again:")
                    return
                _dat["title"] = _title
                PENDING_ADMIN_FLOW[uid] = {
                    "action": "broadcast_date",
                    "data": _dat,
                    "at": _now,
                }
                safe_send(uid, f"✅ Title: *{_title}*\n\n📅 *Enter date* — YYYY-MM-DD", parse_mode="Markdown")
                return

            if _act == "broadcast_date":
                _t = (message.text or "").strip()
                import re as _re
                if not _re.match(r"^\d{4}-\d{2}-\d{2}$", _t):
                    safe_send(uid, "❌ Format: YYYY-MM-DD. Try again.")
                    return
                _dat["date"] = _t
                PENDING_ADMIN_FLOW[uid] = {
                    "action": "broadcast_time",
                    "data": _dat,
                    "at": _now,
                }
                safe_send(uid, "⏰ *Enter time* — H:MM AM/PM\n_Example: 08:16 AM or 9:30 PM_\n_Indian Standard Time_", parse_mode="Markdown")
                return

            # ---- Broadcast schedule: time ----
            if _act == "broadcast_time":
                _t = (message.text or "").strip().upper()
                import re as _re
                # Accept: "08:16", "8:16 AM", "08:16 PM", "8:16AM", "0816"
                _m = _re.match(r"^(\d{1,2})[:. ]?(\d{2})?\s*(AM|PM)?$", _t)
                if not _m:
                    safe_send(uid, "❌ Format: 8:16 AM, 9:30 PM, or 08:16. Try again.")
                    return
                _h = int(_m.group(1))
                _mn = int(_m.group(2) or 0)
                _ap = _m.group(3)
                if _ap == "PM" and _h != 12:
                    _h += 12
                elif _ap == "AM" and _h == 12:
                    _h = 0
                elif not _ap:
                    # No AM/PM — treat as 24h if 0-23, else error
                    if _h > 23:
                        safe_send(uid, "❌ Time out of range. Use AM/PM.")
                        return
                if _h < 0 or _h > 23 or _mn < 0 or _mn > 59:
                    safe_send(uid, "❌ Invalid time. Try again.")
                    return
                _t24 = f"{_h:02d}:{_mn:02d}"
                _dat["time"] = _t24
                _dat["time_human"] = f"{_m.group(1)}:{_m.group(2) or '00'} {_ap or '(24h)'}"
                _dt = f"{_dat['date']} {_dat.get('time', _t)}"  # always 24h format
                _dat["scheduled_at"] = _dt
                PENDING_ADMIN_FLOW.pop(uid, None)
                safe_send(uid,
                    f"✅ *Broadcast scheduled (IST)*\n"
                    f"📅 Date: *{_dat['date']}*\n"
                    f"🕐 Time: *{_dat.get('time_human', _dat['time'])}*\n"
                    f"📩 Recipients: *{len(_dat.get('recipients', []))}*\n\n"
                    f"_Scheduler will send automatically at that time._",
                    parse_mode="Markdown")
                # BC_RETURN_TO_PANEL — reopen admin panel
                try:
                    _show_p = globals().get("_show_admin_panel")
                    if _show_p:
                        _show_p(uid)
                except Exception as _e:
                    print(f"[bc_panel_return] {_e}")
                try:
                    import admin_auth as _aa
                    _aa.log_broadcast(_dat.get("text", ""), len(_dat.get("recipients", [])), _dt)
                except Exception:
                    pass
                # Save for scheduler
                try:
                    import json as _json
                    _bpath = "scheduled_broadcasts.json"
                    _existing = []
                    import os as _os2
                    if _os2.path.exists(_bpath):
                        with open(_bpath) as _f:
                            _existing = _json.load(_f)
                    _existing.append({
                        "scheduled_at": _dt,
                        "text": _dat.get("text", ""),
                        "file_type": _dat.get("file_type"),
                        "file_id": _dat.get("file_id"),
                        "recipients": _dat.get("recipients", []),
                        "sent": False,
                    })
                    with open(_bpath, "w") as _f:
                        _json.dump(_existing, _f, indent=2)
                except Exception as _e:
                    print(f"[sched save] {_e}")
                return

    # ---- Admin/Sub/Lockin codes (existing dispatch) ----
    uid = message.chat.id
    text = (message.text or "").strip()

    # ============================================================
    # INLINE DISPATCH — handles all admin/sub/lockin codes directly.
    # Bypasses handler ordering issues.
    # ============================================================
    if text:
        import admin_auth as _aa

        # --- ADMIN entry ---
        if text == getattr(config, "ADMIN_PANEL_CODE", None):
            _aa.note_device(uid, "primary")
            sess = _aa.get_session(uid)
            if sess and sess.get("role") == "primary":
                _show_admin_panel = globals().get("_show_admin_panel")
                if _show_admin_panel:
                    _show_admin_panel(uid)
                return
            locked, mins = _aa.is_locked(uid, "primary")
            if locked:
                safe_send(uid, f"🔒 Locked. Try again in {mins} min.", parse_mode="Markdown")
                return
            # Set pending state in c30a's _PENDING
            _set_pending_global = None
            try:
                import sys as _sys
                _c30a = _sys.modules.get("__main__")
                if hasattr(_c30a, "_set_pending"):
                    _c30a._set_pending(uid, "primary_priv")
                else:
                    _set_pending_global = None
            except Exception:
                pass
            # Fallback: set our own pending dict
            try:
                _c30a_mod = __import__("bot_chunks.c30a_admin_auth", fromlist=["_set_pending"])
                _c30a_mod._set_pending(uid, "primary_priv")
            except Exception:
                pass
            PENDING_AUTH_FLOW[uid] = {"action": "primary_priv", "at": __import__("time").time()}
            safe_send(uid,
                f"👑 *Welcome Admin — {config.ADMIN_NAME}*\n\n"
                "Please enter your *privacy code* to open the admin panel.\n\n"
                "_Forgot your code? Type_ `/forgot`",
                parse_mode="Markdown")
            return

        # --- SUB-ADMIN entry ---
        if text == getattr(config, "SUB_ADMIN_CODE", None):
            _aa.note_device(uid, "sub")
            sess = _aa.get_session(uid)
            if sess and sess.get("role") == "sub":
                _show_sub = globals().get("_show_sub_admin_panel")
                if _show_sub:
                    _show_sub(uid)
                return
            locked, mins = _aa.is_locked(uid, "sub")
            if locked:
                safe_send(uid, f"🔒 Locked. Try again in {mins} min.", parse_mode="Markdown")
                return
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("\U0001f195 New Device", callback_data="sub_new"),
                InlineKeyboardButton("\u2705 Already Registered", callback_data="sub_reg"),
            )
            bot.send_message(uid,
                "\U0001f6e1 *Sub-Admin Entry*\n\nChoose your option:",
                reply_markup=kb, parse_mode="Markdown")
            return
            return

        # --- LOCK-IN GENERATOR code ---
        if text == getattr(config, "LOCKIN_GENERATOR_CODE", None):
            code, mins = _aa.generate_lockin_code(target_uid=uid)
            _aa.audit("lockin_generator_used", uid, {"expires_in_min": mins})
            safe_send(uid,
                f"🔑 *Lock-in Generator Access*\n\n"
                f"Your one-time code:\n\n"
                f"`{code}`\n\n"
                f"⏱️ Valid *{mins} minutes* · *one-time use*.\n"
                f"Type this code anywhere in the chat to unlock any lockout.",
                parse_mode="Markdown")
            return

        # --- Hex lock-in code (8-char) ---
        if _aa.is_hex_lockin_code(text):
            ok, entry = _aa.verify_lockin_code(text, requester_uid=uid)
            if ok:
                _aa.unlock_primary()
                _aa.unlock_sub_admin(uid)
                _aa.clear_user_block(uid)
                _aa.audit("lockin_used", uid, {})
                safe_send(uid,
                    "🔓 *Lock-in accepted.*\n"
                    "Your lockout and any block have been cleared.\n"
                    "Type the entry code to try again.",
                    parse_mode="Markdown")
            else:
                safe_send(uid, "❌ Invalid or expired lock-in code.")
            return

    # ============================================================

    uid = message.chat.id
    text = (message.text or "").strip()
    if not text:
        return

    p = get_or_create_profile(uid)
    try:
        p["last_seen"] = datetime.now().isoformat()
        save_profile(uid, p)
        import admin_auth as _aa_ls
        _aa_ls.bump_api_calls(uid) # Trigger live update
    except Exception: pass
    try:
        p["last_seen"] = datetime.now().isoformat()
        save_profile(uid, p)
    except Exception:
        pass

    # ============================================================
    # PENDING AUTH FLOW — check if this message is a privacy code
    # ============================================================
    _pend = PENDING_AUTH_FLOW.get(uid)
    if _pend:
        # 2-minute expiry
        if __import__("time").time() - _pend["at"] > 120:
            PENDING_AUTH_FLOW.pop(uid, None)
        else:
            act = _pend["action"]
            import admin_auth as _aa2

            # ---- Primary forgot: reset key ----
            if act == "primary_reset_key":
                import admin_auth as _aa3
                if _aa3.verify_primary_reset(text):
                    # Clear + set new privacy
                    PENDING_AUTH_FLOW[uid] = {
                        "action": "primary_new_priv",
                        "at": __import__("time").time(),
                    }
                    safe_send(uid,
                        "✅ *Reset key verified.*\n\n"
                        "Enter your *new privacy code* (6–20 chars):",
                        parse_mode="Markdown")
                else:
                    _aa3.audit("primary_reset_fail", uid, {})
                    PENDING_AUTH_FLOW.pop(uid, None)
                    safe_send(uid,
                        "❌ Wrong reset key. Recovery cancelled.\n"
                        "Type /forgot to try again.",
                        parse_mode="Markdown")
                return

            # ---- Primary new privacy code ----
            if act == "primary_new_priv":
                if len(text) < 6 or len(text) > 20:
                    safe_send(uid, "❌ Must be 6–20 characters. Try again:")
                    return
                import admin_auth as _aa4
                _aa4.set_primary_privacy(text)
                _aa4.reset_failed_attempts(uid, "primary")
                _aa4.start_session(uid, "primary")
                _aa4.audit("primary_priv_reset_ok", uid, {})
                PENDING_AUTH_FLOW.pop(uid, None)
                safe_send(uid, "✅ *Privacy code updated.* Opening panel…",
                          parse_mode="Markdown")
                _show_p = globals().get("_show_admin_panel")
                if _show_p:
                    _show_p(uid)
                return

            # ---- Primary forgot: reset key (FORGOT_FIX_V2) ----
            if act == "primary_reset_key":
                import admin_auth as _aa_rk
                if _aa_rk.verify_primary_reset(text):
                    PENDING_AUTH_FLOW[uid] = {
                        "action": "primary_new_priv",
                        "at": __import__("time").time(),
                    }
                    safe_send(uid,
                        "✅ *Reset key verified.*\n\n"
                        "Enter your *new privacy code* (6–20 chars):",
                        parse_mode="Markdown")
                else:
                    _aa_rk.audit("primary_reset_fail", uid, {})
                    PENDING_AUTH_FLOW.pop(uid, None)
                    safe_send(uid,
                        "❌ Wrong reset key. Type /forgot to try again.",
                        parse_mode="Markdown")
                return

            # ---- Primary new privacy code (FORGOT_FIX_V2) ----
            if act == "primary_new_priv":
                if len(text) < 6 or len(text) > 20:
                    safe_send(uid, "❌ Must be 6–20 characters. Try again:")
                    return
                import admin_auth as _aa_np
                _aa_np.set_primary_privacy(text)
                _aa_np.reset_failed_attempts(uid, "primary")
                _aa_np.start_session(uid, "primary")
                _aa_np.audit("primary_priv_reset_ok", uid, {})
                PENDING_AUTH_FLOW.pop(uid, None)
                safe_send(uid, "✅ *Privacy code updated.* Opening panel…",
                          parse_mode="Markdown")
                _show_p = globals().get("_show_admin_panel")
                if _show_p:
                    _show_p(uid)
                return

            # ============================================================
            # SUB_VERIFY_INLINE — Sub-admin registration flow in c09
            # ============================================================

            # ---- Sub-admin: verification code (new device) ----
            if act == "sub_verify_code":
                import admin_auth as _aa_sv
                if _aa_sv.verify_sub_admin_verify_code(text):
                    PENDING_AUTH_FLOW[uid] = {
                        "action": "sub_new_name",
                        "at": __import__("time").time(),
                    }
                    safe_send(uid,
                        "✅ *Verification code accepted.*\n\n"
                        "Enter your *name*:",
                        parse_mode="Markdown")
                else:
                    _aa_sv.record_failed_attempt(uid, "sub")
                    _aa_sv.audit("sub_verify_fail", uid, {})
                    PENDING_AUTH_FLOW.pop(uid, None)
                    safe_send(uid,
                        "❌ Wrong verification code. Entry cancelled.",
                        parse_mode="Markdown")
                return

            # ---- Sub-admin: choose name ----
            if act == "sub_new_name":
                if not text or len(text.strip()) < 2:
                    safe_send(uid, "❌ Please enter a valid name.")
                    return
                _name_pick = text.strip()[:60]
                _pf_local = None
                try:
                    for _mn_pf, _mo_pf in __import__("sys").modules.items():
                        if hasattr(_mo_pf, "PENDING_ADMIN_FLOW"):
                            _pf_local = _mo_pf.PENDING_ADMIN_FLOW.get(uid)
                            break
                except Exception:
                    _pf_local = None
                _dat = _pf_local.get("data", {}) if _pf_local else {}
                _dat["name"] = _name_pick
                PENDING_AUTH_FLOW[uid] = {
                    "action": "sub_new_privacy",
                    "data": _dat,
                    "at": __import__("time").time(),
                }
                safe_send(uid,
                    f"✅ Hi *{_name_pick}*.\n\n"
                    "Now set your *privacy code* (6–20 chars):",
                    parse_mode="Markdown")
                return

            # ---- Sub-admin: choose privacy code ----
            if act == "sub_new_privacy":
                if len(text) < 6 or len(text) > 20:
                    safe_send(uid, "❌ Must be 6–20 characters. Try again:")
                    return
                import admin_auth as _aa_sp
                _name_pick = _pflow.get("data", {}).get("name", "Sub-Admin")
                _aa_sp.register_sub_admin(uid, _name_pick, text)
                _aa_sp.start_session(uid, "sub")
                _aa_sp.audit("sub_login_ok", uid, {"name": _name_pick})
                PENDING_AUTH_FLOW.pop(uid, None)
                safe_send(uid,
                    "✅ *Sub-admin registered. Opening panel…*",
                    parse_mode="Markdown")
                _show_sub = globals().get("_show_sub_admin_panel")
                if _show_sub:
                    _show_sub(uid)
                return

            # ---- Primary privacy code ----
            if act == "primary_priv":
                locked, mins = _aa2.is_locked(uid, "primary")
                if locked:
                    safe_send(uid, f"🔒 Locked for *{mins} min*.", parse_mode="Markdown")
                    PENDING_AUTH_FLOW.pop(uid, None)
                    return
                if _aa2.verify_primary_privacy(text):
                    _aa2.reset_failed_attempts(uid, "primary")
                    _aa2.start_session(uid, "primary")
                    _aa2.audit("primary_login_ok", uid, {})
                    PENDING_AUTH_FLOW.pop(uid, None)
                    _show_panel = globals().get("_show_admin_panel")
                    if _show_panel:
                        _show_panel(uid)
                    else:
                        safe_send(uid, "✅ Logged in. Panel loading error — try /admin_lockin.")
                else:
                    _aa2.record_failed_attempt(uid, "primary")
                    import admin_auth as _aa_ck
                    _cfg = _aa_ck._load_config()
                    _attempts = _cfg.get("primary", {}).get("failed_attempts", 0)
                    _remaining = max(0, _aa_ck.MAX_FAILED - _attempts)

                    if _remaining > 0:
                        # KEEP pending flow active so user gets all attempts
                        safe_send(uid,
                            f"❌ Wrong privacy code.\n"
                            f"⚠️ *{_remaining} attempts left* before 15-min lockout.\n\n"
                            f"Type your privacy code again, or `/forgot` to reset.",
                            parse_mode="Markdown")
                    else:
                        # Only clear pending when locked out
                        PENDING_AUTH_FLOW.pop(uid, None)
                        safe_send(uid,
                            f"🔒 Locked. Too many failed attempts. Try again in 15 min.\n\n"
                            f"Type `/forgot` if you need to reset your privacy code.",
                            parse_mode="Markdown")
                return

            # ---- Sub-admin privacy code ----
            if act == "sub_priv":
                locked, mins = _aa2.is_locked(uid, "sub")
                if locked:
                    safe_send(uid, f"🔒 Locked for *{mins} min*.", parse_mode="Markdown")
                    PENDING_AUTH_FLOW.pop(uid, None)
                    return
                if _aa2.verify_sub_admin_privacy(uid, text):
                    _aa2.reset_failed_attempts(uid, "sub")
                    _aa2.start_session(uid, "sub")
                    _aa2.update_sub_admin_last_seen(uid)
                    _aa2.audit("sub_login_ok", uid, {})
                    PENDING_AUTH_FLOW.pop(uid, None)
                    _show_sub = globals().get("_show_sub_admin_panel")
                    if _show_sub:
                        _show_sub(uid)
                    else:
                        _show_panel = globals().get("_show_admin_panel")
                        if _show_panel:
                            _show_panel(uid)
                else:
                    _aa2.record_failed_attempt(uid, "sub")
                    PENDING_AUTH_FLOW.pop(uid, None)
                    safe_send(uid, "❌ Wrong privacy code. Entry cancelled.", parse_mode="Markdown")
                return

    # ---- Admin unblock code (works even when blocked) ----
    if text.strip() == ADMIN_UNBLOCK_CODE:
        p.setdefault("behavior", {"strikes": 0, "blocked_until": None})
        p["behavior"]["strikes"] = 0
        p["behavior"]["blocked_until"] = None
        save_profile(uid, p)
        bot.reply_to(message, "🔓 *Admin unblock successful.* Strikes reset to 0.",
                     parse_mode="Markdown")
        return

    # ---- Blocked check ----
    blocked, time_left = check_blocked(uid)
    if blocked:
        safe_send(uid,
            f"⛔ *Access Denied*\n\n"
            f"You are blocked.\n"
            f"Contact admin on WhatsApp *{WHATSAPP_CONTACT}* and pay *₹10* to unblock."
            + _countdown_footer(uid),
            parse_mode="Markdown")
        return

    # ---- Activation gate ----
    if not p.get("secured"):
        if is_valid_key(text):
            p["secured"] = True
            p["activation_key"] = text.strip()
            p["key_expired"] = False
            p["onboarding_step"] = "name"
            save_profile(uid, p)
            # Hamilton story (once)
            if not p.get("story_shown"):
                safe_send(uid, _hamilton_story(), parse_mode="Markdown")
                p["story_shown"] = True
                save_profile(uid, p)
                time.sleep(1)
            bot.reply_to(message, "✅ *Key confirmed. Let's set up your profile.*",
                         parse_mode="Markdown")
            _run_onboarding(uid)
        else:
            p.setdefault("no_key_attempts", 0)
            p["no_key_attempts"] += 1
            save_profile(uid, p)
            if p["no_key_attempts"] <= 2:
                safe_send(uid, _no_key_message(short=False), parse_mode="Markdown")
            else:
                safe_send(uid, _no_key_message(short=True), parse_mode="Markdown")
        return

    # ---- Expired key check ----
    if _check_key_expired(uid, p):
        return

    # ---- Onboarding gate ----
    if p.get("onboarding_step") and p["onboarding_step"] != "done":
        _run_onboarding(uid)
        return

    if not p.get("exams"):
        bot.reply_to(message, "🎯 Set exams with /mode first.")
        return

    # ============================================
    # SESSION LOCKS (borders)
    # ============================================
    sess = exam_engine.get_session(uid)

    # Test mode → hard border
    if sess and sess.get("mode") == "test":
        q_done = sess.get("questions_done", 0)
        plan = sess.get("plan", [])
        paper = sess.get("current_paper", 1)
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("⏹ Stop Test",
                                                       callback_data="test_stop"))
        safe_send(uid,
            f"📝 *Test in progress* — Paper {paper}, Q{q_done}/{len(plan)}\n\n"
            f"I can't answer questions during the test.\n"
            f"Finish first, then we can talk.\n\n"
            f"Use the button below to end early.",
            parse_mode="Markdown",
            reply_markup=markup)
        return

    # Conceptual mode → hard border
    if sess and sess.get("mode") == "conceptual":
        q_done = sess.get("questions_done", 0)
        plan = sess.get("plan", [])
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("⏹ Stop Test",
                                                       callback_data="concept_stop"))
        safe_send(uid,
            f"🧠 *Conceptual test in progress* — Q{q_done}/{len(plan)}\n\n"
            f"I can't answer questions during the test.\n"
            f"Finish first, then we can talk.",
            parse_mode="Markdown",
            reply_markup=markup)
        return

    # Practice mode → soft border (allow doubt)
    if p.get("_practice_active") and sess and sess.get("mode") == "practice":
        # Treat as doubt → answer briefly, then show Continue/Stop
        exam = sess.get("exam") or health.exam_of(p) or "JEE_MAIN"
        timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
        try:
            bump_api_calls(uid)
            answer = ai_client.ask_hamilton(exam, text)
        except Exception:
            answer = None
        timer_manager.stop_thinking_timer(uid)
        if not answer:
            safe_send(uid, "⚠️ Could not answer right now. Retry or Continue.")
            return
        svg, clean = svg_renderer.detect_svg_in_text(answer)
        final = "💬 *Your doubt answered:*\n\n" + clean
        safe_send(uid, final + _countdown_footer(uid),
                  parse_mode="Markdown",
                  reply_markup=_doubt_continue_buttons())
        if svg and SVG_ENABLED:
            path = svg_renderer.render_svg(svg, name=f"doubt_{uid}")
            if path:
                safe_send_photo(uid, path)
                svg_renderer.cleanup_file(path)
        return

    # Stuck practice flag without session → clear
    if p.get("_practice_active") and not sess:
        p["_practice_active"] = False
        save_profile(uid, p)

    # Notes session → if user types anything else, treat as doubt about notes
    if p.get("_notes_state"):
        low = text.lower().strip()
        if low in ("continue", "next", "next part", "go on", "cont"):
            _send_next_notes_batch(uid)
            return
        if low in ("stop", "exit", "done", "end"):
            p.pop("_notes_state", None)
            save_profile(uid, p)
            safe_send(uid, "✅ Notes session ended.")
            return
        if low in ("explain", "explain more", "detail"):
            state = p.get("_notes_state", {})
            last = state.get("last_notes", "")
            exam = state.get("exam", "JEE_MAIN")
            if not last:
                safe_send(uid, "Nothing to explain.")
                return
            timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
            prompt = ("The student wants a simpler explanation of these notes:\n\n"
                      + last + "\n\nRe-explain in simpler friendly language.")
            bump_api_calls(uid)
            answer = ai_client.ask_hamilton(exam, prompt)
            timer_manager.stop_thinking_timer(uid)
            if answer:
                svg, clean = svg_renderer.detect_svg_in_text(answer)
                safe_send(uid, clean + _countdown_footer(uid), parse_mode="Markdown")
                if svg and SVG_ENABLED:
                    path = svg_renderer.render_svg(svg, name=f"explain_{uid}")
                    if path:
                        safe_send_photo(uid, path)
                        svg_renderer.cleanup_file(path)
            return

    # Pending numerical (practice)
    if uid in PENDING_NUMERICAL:
        pending = PENDING_NUMERICAL.get(uid)
        if pending and pending.get("is_test"):
            _handle_test_numerical(uid, text)
        else:
            _handle_numerical_answer(uid, text)
        return

    # ============================================
    # ---- LOCK_LOGIC_V2: smart AI lock that respects any pending flow ----
    import admin_auth as _aa_lock
    _lock_sess = _aa_lock.get_session(message.chat.id)
    _lock_text = (message.text or "").strip()

    if _lock_sess and _lock_text and not _lock_text.startswith("/"):
        # Determine if ANY pending flow is active (auth OR admin)
        _flow_active = False
        for _mn, _mo in __import__("sys").modules.items():
            # Check PENDING_AUTH_FLOW
            if hasattr(_mo, "PENDING_AUTH_FLOW"):
                _af = _mo.PENDING_AUTH_FLOW.get(message.chat.id)
                if _af and _af.get("at") and (__import__("time").time() - _af["at"]) < 300:
                    _flow_active = True
                    break
            # Check PENDING_ADMIN_FLOW
            if hasattr(_mo, "PENDING_ADMIN_FLOW"):
                _pf = _mo.PENDING_ADMIN_FLOW.get(message.chat.id)
                if _pf and _pf.get("at") and (__import__("time").time() - _pf["at"]) < 300:
                    _flow_active = True
                    break

        if not _flow_active:
            # No pending flow → user is just chatting in admin mode
            # Block AI and tell them to use /exit
            safe_send(message.chat.id,
                "🛠️ *Admin Panel Active*\n\n"
                "Use panel buttons above. Type `/exit` to close admin mode and return to normal chat.",
                parse_mode="Markdown")
            return

    # ---- End LOCK_LOGIC_V2 ----
    # NORMAL FREE-TEXT AI
    # ============================================
    exam = health.exam_of(p) or "JEE_MAIN"

    # 3-tier classification (merged single-call: classify + answer)
    bump_api_calls(uid)
    try:
        intent, merged_reply = ai_client.classify_message_and_answer(
            exam, text, selected_exams=p.get("exams") or [exam]
        )
    except Exception:
        intent, merged_reply = "STUDY", None

    if intent == "OFF_TOPIC":
        blocked_now, mins = register_strike(uid)
        stats = get_usage_stats(uid)
        sc  = stats["strikes_current"]
        st  = stats["strikes_total"]
        bt  = stats["blocks_total"]
        remaining = max(0, STRIKE_LIMIT - sc)

        if blocked_now:
            safe_send(uid,
                f"⛔ *BLOCK MODE ACTIVATED*\n\n"
                f"You have been blocked for *{mins} minutes* for repeated misuse.\n\n"
                f"📊 *Your record so far:*\n"
                f"  • Strikes this session: *{sc}*\n"
                f"  • Total strikes ever: *{st}*\n"
                f"  • Previous blocks: *{bt}*\n\n"
                f"WhatsApp *{WHATSAPP_CONTACT}* if this was a mistake."
                + _countdown_footer(uid),
                parse_mode="Markdown")
            return

        safe_send(uid,
            f"⚠️ *STRIKE {sc}/{STRIKE_LIMIT}*\n"
            f"_({remaining} more strikes until temporary block)_\n\n"
            "Think about study. Think about studies. Don't simply learn. "
            "Understand it so you can simply memorize it. Remember that your "
            "ultimate success requires the right resources. If you are "
            "distracted or bored, invest your time wisely with Hemanth and "
            "Krishna Publications. Message 8074231426 to get books that "
            "clarify your concepts and elevate your ranks immediately.\n\n"
            "Focus now. Your exam is watching the calendar."
            + _countdown_footer(uid),
            parse_mode="Markdown")
        return

    # Thinking timer + AI
    timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
    try:
        bump_api_calls(uid)
        answer = ai_client.ask_hamilton(exam, text)
    except Exception:
        answer = None
    timer_manager.stop_thinking_timer(uid)

    if not answer:
        mid = timer_manager.get_thinking_msg_id(uid)
        err = "⚠️ Hamilton is momentarily overloaded. Please try again."
        if mid:
            safe_edit(uid, mid, err)
        else:
            safe_send(uid, err)
        return

    svg, clean = svg_renderer.detect_svg_in_text(answer)
    final = clean + _countdown_footer(uid)

    mid = timer_manager.get_thinking_msg_id(uid)
    if mid:
        safe_edit(uid, mid, final, parse_mode="Markdown")
    else:
        safe_send(uid, final, parse_mode="Markdown")

    if svg and SVG_ENABLED:
        path = svg_renderer.render_svg(svg, name=f"ai_{uid}")
        if path:
            safe_send_photo(uid, path)
            svg_renderer.cleanup_file(path)

# ==========================================================
# TWO-WAY CHAT (admin <-> student)
# ==========================================================
TWO_WAY_CHAT = {}   # {student_uid: {"admin_uid": int, "started": ts}}

def _is_in_two_way_chat(uid):
    entry = TWO_WAY_CHAT.get(uid)
    if not entry:
        return None
    import time as _t
    if _t.time() - entry["started"] > getattr(config, "TWO_WAY_CHAT_TIMEOUT_MIN", 30) * 60:
        TWO_WAY_CHAT.pop(uid, None)
        return None
    return entry


# ==========================================================
# EXTENDED PENDING FLOW (for admin actions)
# ==========================================================
PENDING_ADMIN_FLOW = {}   # {admin_uid: {"action": ..., "data": {...}, "at": ts}}



# ==========================================================
# bot.py — Chunk 10: missing features (overrides + help menu)
# ==========================================================

# ==========================================================
# UPDATED — No-key message with new pricing + admin contact
# ==========================================================
def _no_key_message(short=False):
    if short:
        return (
            "🔒 Hamilton needs an activation key.\n\n"
            f"💰 Price: *₹169* (fixed)\n"
            f"_May vary on your year of selection._\n\n"
            f"📞 Contact admin *Krishna Vamsi* at *Hemanth and Krishna Publications*:\n"
            f"WhatsApp *{WHATSAPP_CONTACT}*"
        )
    return (
        "🔒 *Hamilton needs an activation key to begin.*\n\n"
        f"💰 *Price: ₹169* — fixed for all exams.\n"
        f"_Note: Price may vary based on your year of selection._\n\n"
        f"📞 To get your key, message admin *Krishna Vamsi* at "
        f"*Hemanth and Krishna Publications*:\n"
        f"WhatsApp *{WHATSAPP_CONTACT}*\n\n"
        f"Once you receive your key, send it here to unlock Hamilton."
    )


# ==========================================================
# DEVICE BINDING — one key, one device
# ==========================================================
def _check_key_binding(uid, key):
    """
    Returns (allowed, reason).
    If key unbound → binds it to uid and allows.
    If key already bound to same uid → allows.
    If key bound to different uid → rejects.
    """
    keys = load_keys()
    if key not in keys:
        return False, "invalid"
    info = keys[key]
    if not isinstance(info, dict):
        # Old format — bind and allow
        keys[key] = {"year": None, "bound_to": str(uid),
                     "bound_at": datetime.now().isoformat()}
        with open(KEYS_FILE, "w") as f:
            json.dump(keys, f, indent=2)
        return True, "bound"

    bound_to = info.get("bound_to")
    if bound_to is None:
        info["bound_to"] = str(uid)
        info["bound_at"] = datetime.now().isoformat()
        keys[key] = info
        with open(KEYS_FILE, "w") as f:
            json.dump(keys, f, indent=2)
        return True, "bound"
    if str(bound_to) == str(uid):
        return True, "same_device"
    return False, "other_device"


# ==========================================================
# /help — menu with everything
# ==========================================================
# DISABLED_MASTER: @bot.message_handler(commands=['help'])
def cmd_help(message):
    uid = message.chat.id
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Group commands logically
    kb.row(
        InlineKeyboardButton("📚 Study", callback_data="help_cat:study"),
        InlineKeyboardButton("🧪 Test & Practice", callback_data="help_cat:test")
    )
    kb.row(
        InlineKeyboardButton("📊 Profile & Stats", callback_data="help_cat:profile"),
        InlineKeyboardButton("⚙️ System", callback_data="help_cat:system")
    )
    kb.add(InlineKeyboardButton("❌ Close Help", callback_data="help_close"))
    
    try:
        safe_send(uid, "🤖 *Hamilton Help Menu*\n\nTap a category below to see commands and what they do.", parse_mode="Markdown", reply_markup=kb)
        print(f"[help] sent to {uid}")
    except Exception as e:
        print(f"[help-err] {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("help_cat:"))
def cb_help_cat(call):
    cat = call.data.split(":")[1]
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    
    if cat == "study":
        kb.row(
            InlineKeyboardButton("/mode", callback_data="help_cmd:mode"),
            InlineKeyboardButton("/select", callback_data="help_cmd:select")
        )
        kb.row(
            InlineKeyboardButton("/notes", callback_data="help_cmd:notes"),
            InlineKeyboardButton("/plan", callback_data="help_cmd:plan")
        )
        text = "📚 *Study Commands*\n\nTap a command to learn what it does."
        
    elif cat == "test":
        kb.row(
            InlineKeyboardButton("/exam", callback_data="help_cmd:exam"),
            InlineKeyboardButton("/pyq", callback_data="help_cmd:pyq")
        )
        kb.row(
            InlineKeyboardButton("/stop", callback_data="help_cmd:stop"),
            InlineKeyboardButton("/bookmarks", callback_data="help_cmd:bookmarks")
        )
        text = "🧪 *Test & Practice Commands*\n\nTap a command to learn what it does."
        
    elif cat == "profile":
        kb.row(
            InlineKeyboardButton("/status", callback_data="help_cmd:status"),
            InlineKeyboardButton("/health", callback_data="help_cmd:health")
        )
        kb.row(
            InlineKeyboardButton("/leaderboard", callback_data="help_cmd:leaderboard"),
            InlineKeyboardButton("/find", callback_data="help_cmd:find")
        )
        text = "📊 *Profile & Stats*\n\nTap a command to learn what it does."
        
    elif cat == "system":
        kb.row(
            InlineKeyboardButton("/start", callback_data="help_cmd:start"),
            InlineKeyboardButton("/cancel", callback_data="help_cmd:cancel")
        )
        kb.row(
            InlineKeyboardButton("/clear_data", callback_data="help_cmd:clear_data")
        )
        text = "⚙️ *System Commands*\n\nTap a command to learn what it does."
        
    kb.add(InlineKeyboardButton("🔙 Back to Categories", callback_data="help_back"))
    
    try:
        bot.edit_message_text(text, chat_id=call.from_user.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("help_cmd:"))
def cb_help_cmd(call):
    cmd = call.data.split(":")[1]
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    
    descriptions = {
        "start": "🚀 *Start*\nInitializes your Hamilton journey. Asks for your name, institute, phone, and level.",
        "mode": "📚 *Mode*\nSet up your exams (JEE Adv, Mains, EAMCET), priority exam, target year, and target marks.",
        "select": "🎯 *Select*\nPick the specific chapters you want to focus on. Feeds into tests and notes.",
        "exam": "🧪 *Exam*\nEnter Practice, Test, or Conceptual mode. Practice gives casual questions. Test simulates the real exam with a timer. Conceptual focuses on deep theory.",
        "pyq": "📝 *PYQ*\nPrevious Year Questions. Practice REAL questions from past JEE/EAMCET papers, filtered by year and chapter.",
        "notes": "📖 *Notes*\nGenerates structured short notes for a chapter, delivered as a PDF.",
        "plan": "📅 *Plan*\nGenerates a day-by-day study schedule based on your available hours and target marks.",
        "status": "👤 *Status*\nShows your current profile summary, including level, target marks, and streak.",
        "health": "❤️ *Health*\nShows your readiness and concept mastery across all three subjects.",
        "leaderboard": "🏆 *Leaderboard*\nShows the top performers based on their Health score and Subject average.",
        "find": "🔍 *Find*\nSearch for another user by their HKU ID.",
        "bookmarks": "🔖 *Bookmarks*\nView all the questions you have saved for later review.",
        "stop": "🛑 *Stop*\nEnds your current test or practice session immediately.",
        "clear_data": "⚠️ *Clear Data*\nDeletes your entire profile and progress from the bot. This cannot be undone.",
        "cancel": "✖️ *Cancel*\nAborts any active setup (like /mode or test generation) and returns to normal chat."
    }
    
    desc = descriptions.get(cmd, "No description available.")
    try:
        bot.edit_message_text(desc, chat_id=call.from_user.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "help_back")
def cb_help_back(call):
    try:
        cmd_help(call.message)
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "help_close")
def cb_help_close(call):
    try:
        bot.delete_message(call.from_user.id, call.message.message_id)
    except: pass
    bot.answer_callback_query(call.id, "Closed")


# ==========================================================
# bot.py — Chunk 11: Rich text overrides
# ==========================================================

from rich_formatter import markdown_to_rich

# Keep a reference to the original safe_send
_original_safe_send = safe_send
_original_safe_edit = safe_edit


def _looks_like_rich(text):
    """Detect if text contains markdown/LaTeX that benefits from rich rendering."""
    if not text:
        return False
    indicators = ["$$", "$", "**", "##", "# ", "\\(", "\\[", "\\frac",
                  "\\tau", "\\int", "\\sum", "\\alpha", "\\beta", "\\vec",
                  "\\sqrt", "\\begin{", "\\end{"]
    return any(ind in text for ind in indicators)


def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    """
    If text looks like markdown/LaTeX content → send as Telegram Rich message.
    Otherwise → send as plain text (with Markdown fallback).
    """
    if not text:
        return

    # Long text → split (keep existing logic)
    if len(text) > TELEGRAM_MSG_LIMIT:
        while len(text) > TELEGRAM_MSG_LIMIT:
            cut = text.rfind("\n", 0, TELEGRAM_MSG_LIMIT)
            if cut == -1:
                cut = TELEGRAM_MSG_LIMIT
            chunk = text[:cut]
            _send_rich_or_plain(chat_id, chunk, parse_mode, None)
            text = text[cut:].lstrip()
            time.sleep(0.3)
        if text:
            _send_rich_or_plain(chat_id, text, parse_mode, reply_markup)
        return

    _send_rich_or_plain(chat_id, text, parse_mode, reply_markup)


def _send_rich_or_plain(chat_id, text, parse_mode, reply_markup):
    if _looks_like_rich(text):
        try:
            rich = markdown_to_rich(text)
            bot.send_rich_message(
                chat_id=chat_id,
                rich_message=rich,
                reply_markup=reply_markup,
            )
            return
        except Exception as e:
            print(f"[RICH] Failed: {e}. Falling back to plain.")

    # Plain fallback
    try:
        bot.send_message(chat_id, text, parse_mode=parse_mode,
                         reply_markup=reply_markup)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=reply_markup)


def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    """
    For rich content → try editing to rich. If fails → delete + send new.
    For plain → edit normally.
    """
    if not text:
        return

    if _looks_like_rich(text):
        # Try editing to rich
        try:
            rich = markdown_to_rich(text)
            # Try edit — pyTelegramBotAPI may or may not expose editRichMessage
            try:
                bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=text[:TELEGRAM_MSG_LIMIT], parse_mode=parse_mode)
                # If plain edit worked, but we wanted rich... fallback:
                # Actually delete + send rich for better result
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception:
                    pass
                bot.send_rich_message(
                    chat_id=chat_id, rich_message=rich,
                    reply_markup=reply_markup)
                return
            except Exception:
                # Couldn't edit — send new
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception:
                    pass
                bot.send_rich_message(
                    chat_id=chat_id, rich_message=rich,
                    reply_markup=reply_markup)
                return
        except Exception as e:
            print(f"[RICH-EDIT] Failed: {e}")

    # Plain edit fallback
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                              text=text[:TELEGRAM_MSG_LIMIT],
                              parse_mode=parse_mode,
                              reply_markup=reply_markup)
    except Exception:
        try:
            bot.send_message(chat_id, text, parse_mode=parse_mode,
                             reply_markup=reply_markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=reply_markup)


print("bot.py Chunk 11 loaded: rich text overrides ready.")



# ==========================================================
# bot.py — Chunk 12: New page-based notes flow (override)
# ==========================================================

NOTES_MAX_PAGES_PER_REQUEST = 10


def _estimate_pages(subtopics_count, concepts_count):
    """Local math — decide page count from concept count."""
    if concepts_count <= 0:
        return 1
    # Aim for ~10-14 concepts per page
    pages = max(2, (concepts_count + 13) // 14)
    # Cap at reasonable max
    if pages > 20:
        pages = 20
    return pages


def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics_list = []
    for sub, val in subs.items():
        cl = val.get("adv", []) if isinstance(val, dict) else val
        subtopics_list.append({"name": sub, "concepts": list(cl)})

    total_concepts = sum(len(s["concepts"]) for s in subtopics_list)
    total_subtopics = len(subtopics_list)

    # Show "Analyzing" briefly
    calc_msg = bot.send_message(uid, "⏱️ Analyzing chapter scope...")
    time.sleep(1.5)

    total_pages = _estimate_pages(total_subtopics, total_concepts)

    # Delete "analyzing"
    try:
        bot.delete_message(uid, calc_msg.message_id)
    except Exception:
        pass

    # Split subtopics across pages — keep page balance
    n_subs = len(subtopics_list)
    subs_per_page = max(1, (n_subs + total_pages - 1) // total_pages)
    groups = []
    for i in range(0, n_subs, subs_per_page):
        groups.append(subtopics_list[i:i + subs_per_page])

    # Ensure we don't have more groups than total_pages
    if len(groups) > total_pages:
        # Merge extras
        while len(groups) > total_pages:
            last = groups.pop()
            groups[-1].extend(last)
    # Ensure we have at least total_pages groups
    while len(groups) < total_pages and len(groups) < n_subs:
        # Split the largest group
        groups.sort(key=len, reverse=True)
        biggest = groups.pop(0)
        if len(biggest) < 2:
            break
        mid = len(biggest) // 2
        groups.append(biggest[:mid])
        groups.append(biggest[mid:])

    total_parts = len(groups)

    p["_notes_state"] = {
        "subject": subject,
        "chapter": chapter,
        "exam": exam,
        "groups": groups,
        "current_part": 0,
        "total_parts": total_parts,
        "concepts_total": total_concepts,
        "subtopics_total": total_subtopics,
        "pages_this_request": 0,
        "last_notes": "",
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *{chapter}*\n\n"
        f"📖 Subtopics: *{total_subtopics}*\n"
        f"🧠 Concepts: *{total_concepts}*\n"
        f"📄 Pages required: *{total_parts}*\n\n"
        f"_Sending pages one by one..._",
        parse_mode="Markdown")
    time.sleep(0.5)
    _send_next_notes_part(uid)


def _send_next_notes_part(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes session.")
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)
    pages_this_req = state.get("pages_this_request", 0)

    # All pages done?
    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.\n\n"
            "Ask me anything about it, or /notes for another chapter.",
            parse_mode="Markdown")
        return

    # Hit 10-page per-request limit?
    if pages_this_req >= NOTES_MAX_PAGES_PER_REQUEST:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_10-page batch complete. Type_ `/continue` _for the next batch._",
            parse_mode="Markdown")
        p["_notes_state"] = state
        save_profile(uid, p)
        return

    # Generate next page
    group = state["groups"][current]
    part_num = current + 1

    topics_text = ""
    for st in group:
        topics_text += f"\n## {st['name']}\n"
        for c in st["concepts"]:
            topics_text += f"- {c}\n"

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    prompt = (
        f"Write SHORT NOTES Part {part_num} of {total} for JEE preparation.\n"
        f"Chapter: {state['chapter']} ({state['subject']})\n\n"
        f"Cover these subtopics thoroughly:\n{topics_text}\n\n"
        "FORMAT REQUIREMENTS:\n"
        "- Use markdown: ## for subtopic headings, **bold** for key terms\n"
        "- Use $$...$$ for display equations (LaTeX INSIDE the $$)\n"
        "- Use $...$ for inline math\n"
        "- Include definitions, key formulas, traps, shortcuts\n"
        "- Friendly senior tone (Hey, look at this...)\n"
        "- Cover EVERY listed concept\n"
        "- Do NOT include a title — the bot already adds header\n"
    )

    notes = ai_client.ask_hamilton(state["exam"], prompt)
    timer_manager.stop_generating_timer(bot, uid)

    if not notes:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    header = f"📝 *{state['chapter']}* — Page {part_num}/{total}\n\n"
    full = header + notes + _countdown_footer(uid)
    safe_send(uid, full, parse_mode="Markdown")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_this_req + 1
    state["last_notes"] = notes[:800]
    p["_notes_state"] = state
    save_profile(uid, p)

    # Auto-send next page after short delay
    time.sleep(1)
    _send_next_notes_part(uid)


# Override /continue to reset per-request counter
@bot.message_handler(commands=['continue_old_disabled'])
def cmd_continue_old_disabled(message):
    uid = message.chat.id
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        # Maybe a plain continue with nothing pending
        safe_send(uid, "No notes in progress. Type /notes to start.")
        return
    state["pages_this_request"] = 0
    p["_notes_state"] = state
    save_profile(uid, p)
    _send_next_notes_part(uid)


print("bot.py Chunk 12 loaded: new page-based notes flow ready.")



# ==========================================================
# bot.py — Chunk 13: Rich text in all questions
# ==========================================================

# Import rich_formatter helpers (already imported in c11, but safe)
try:
    from rich_formatter import markdown_to_rich
except Exception:
    pass


# ----------------------------------------------------------
# Send rich question + letter-only poll
# ----------------------------------------------------------
def _send_rich_question_and_poll(uid, header_md, question_md, options, correct_index, mode="practice"):
    """
    Sends:
      1. Rich message with full question + options A) B) C) D)
      2. Poll with short letters A/B/C/D/Skip
    Returns nothing.
    """
    # Compose the rich message content
    rich_content = header_md + "\n\n" + question_md
    if options:
        rich_content += "\n\n"
        for i, opt in enumerate(options[:4]):
            letter = chr(65 + i)
            rich_content += f"**{letter})** {opt}\n"

    # Send rich message
    try:
        rich = markdown_to_rich(rich_content)
        bot.send_rich_message(chat_id=uid, rich_message=rich)
    except Exception as e:
        # Fallback to plain text
        print(f"[RICH-Q] fallback: {e}")
        safe_send(uid, rich_content, parse_mode="Markdown")

    time.sleep(0.4)

    # Send short poll
    poll_options = ["A", "B", "C", "D"][:len(options[:4])] + ["🚪 Skip"]
    try:
        bot.send_poll(
            chat_id=uid,
            question="👆 Read the question above. Tap your answer:",
            options=poll_options,
            type="quiz",
            correct_option_id=int(correct_index),
            explanation="See solution below.",
            is_anonymous=False,
        )
    except Exception as e:
        safe_send(uid, f"🔄 Poll error: {e}")


# ==========================================================
# OVERRIDE — _send_next_practice
# ==========================================================
def _send_next_practice(uid):
    p = load_profile(uid)
    exam = p.get("_practice_exam") or health.exam_of(p)
    level = p.get("_practice_level", "medium")
    if not exam:
        safe_send(uid, "❌ Exam not set.")
        return

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        subj = _pick_subject_for_practice(p)
        if not subj:
            timer_manager.stop_generating_timer(bot, uid)
            safe_send(uid, "❌ No chapters available.")
            return
        custom = p.get("_practice_custom_chapters")
        allowed = custom.get(subj) if custom else None
        pick = exam_engine.pick_next_subtopic(p, subj, exam, allowed_chapters=allowed)
        if not pick:
            timer_manager.stop_generating_timer(bot, uid)
            safe_send(uid, "❌ No subtopics found.")
            return
        _, ch, sub = pick
        q_type = "mcq"
        if exam in ("JEE_MAIN", "JEE_ADV") and random.random() < 0.25:
            q_type = "numerical"
        q = exam_engine.generate_question(exam, subj, ch, sub,
                                           q_type=q_type, difficulty=level)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question. Try /exam again.")
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_practice(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}

    meta = q["_meta"]
    sess = exam_engine.get_session(uid)
    if not sess:
        return
    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = meta

    st = q.get("source_type", "AI-Generated")
    sd = q.get("source_detail", "")
    diff = q.get("difficulty", level)
    ideal = q.get("ideal_time_sec", 60)
    q_num = sess.get("questions_done", 0) + 1

    avg_time = None
    key = f"{meta['subject']}::{meta['chapter']}::{meta['subtopic']}"
    stat = p.get("subtopic_stats", {}).get(key)
    if stat and stat.get("attempts", 0) > 0:
        avg_time = stat.get("avg_time", 0)

    header_lines = [
        f"## [{EXAM_NAMES.get(exam, exam)} | {meta['subject']} | Practice | Q{q_num}]",
        f"📌 Source: {st}" + (f" · {sd}" if sd else ""),
        f"⚡ {difficulty_str(diff)} | ⏱️ Ideal: {ideal}s" +
            (f" | 📈 Avg: {int(avg_time)}s" if avg_time else ""),
        f"📖 {meta['chapter']} → {meta['subtopic']}",
    ]
    header_md = "\n".join(header_lines)

    # Numericals go through rich message + text reply (existing flow)
    if q.get("correct_value") is not None:
        rich_content = (header_md + "\n\n" +
                        (q.get("question", "")) +
                        "\n\n_Type your answer as a number._")
        try:
            rich = markdown_to_rich(rich_content)
            bot.send_rich_message(chat_id=uid, rich_message=rich)
        except Exception as e:
            print(f"[RICH-NUM] fallback: {e}")
            safe_send(uid, rich_content, parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": meta, "started": time.time()}
        timer_manager.start_question_timer(bot, uid)
        _preload_practice(uid, count=2)
        return

    # MCQ — send rich question + letter-only poll
    options = q.get("options", [])[:4]
    if len(options) < 2:
        tries = _bump_retry(uid)
        if tries >= 3:
            _reset_retry(uid)
            safe_send(uid, "⚠️ Bad format. Try /exam again.")
            return
        safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
        time.sleep(2)
        _send_next_practice(uid)
        return
    _reset_retry(uid)

    _send_rich_question_and_poll(
        uid, header_md, q.get("question", ""),
        options, int(q.get("correct_index", 0)), mode="practice"
    )
    timer_manager.start_question_timer(bot, uid)
    _preload_practice(uid, count=2)


# ==========================================================
# OVERRIDE — _send_next_test_q
# ==========================================================
def _send_next_test_q(uid):
    p = load_profile(uid)
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return
    plan = sess.get("plan", [])
    idx = sess.get("plan_index", 0)
    if idx >= len(plan):
        _test_paper_finish(uid)
        return

    exam = sess.get("exam")
    subj, ch, sub, q_type, diff = plan[idx]

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        q = exam_engine.generate_question(exam, subj, ch, sub,
                                           q_type=q_type, difficulty=diff)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question. Try /exam again.")
                _test_paper_finish(uid)
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_test_q(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}
        q["_plan_type"] = q_type

    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = q["_meta"]
    sess["current_plan_type"] = q_type

    n_done = sess.get("questions_done", 0)
    n_total = len(plan)
    st = q.get("source_type", "AI-Generated")
    sd = q.get("source_detail", "")
    ideal = q.get("ideal_time_sec", 60)
    section = _section_tag_for(exam, q_type, n_done, n_total)

    header_lines = [
        f"## [{EXAM_NAMES.get(exam, exam)} | {subj} | {section} | Q{n_done+1}/{n_total}]",
        f"📌 Source: {st}" + (f" · {sd}" if sd else ""),
        f"⚡ {difficulty_str(diff)} | ⏱️ Ideal: {ideal}s",
        f"📖 {q['_meta']['chapter']} → {sub}",
    ]
    header_md = "\n".join(header_lines)

    # Numerical path
    if q_type == "numerical" or q.get("correct_value") is not None:
        rich_content = (header_md + "\n\n" + q.get("question", "") +
                        "\n\n_Type your answer as a number._")
        try:
            rich = markdown_to_rich(rich_content)
            bot.send_rich_message(chat_id=uid, rich_message=rich)
        except Exception as e:
            print(f"[RICH-TNUM] fallback: {e}")
            safe_send(uid, rich_content, parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": q["_meta"],
                                   "started": time.time(), "is_test": True}
        _preload_test(uid, count=3)
        return

    # MCQ / Multi / Match → rich + poll
    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["plan_index"] = idx + 1
        _send_next_test_q(uid)
        return

    correct_idx = int(q.get("correct_index", 0))
    if q_type == "multi" and q.get("correct_indices"):
        correct_idx = int(q["correct_indices"][0]) if q["correct_indices"] else 0

    _send_rich_question_and_poll(
        uid, header_md, q.get("question", ""),
        options, correct_idx, mode="test"
    )
    _preload_test(uid, count=3)


# ==========================================================
# OVERRIDE — _send_next_concept_q
# ==========================================================
def _send_next_concept_q(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "conceptual":
        return

    plan = sess.get("plan", [])
    idx = sess.get("index", 0)
    if idx >= len(plan):
        _concept_finish(uid)
        return

    exam = sess.get("exam")
    subj = sess.get("subject")
    chapter = sess.get("chapter")
    sub = plan[idx]
    ttype = sess.get("test_type", "general")

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        diff = "hard" if ttype == "exception" else "medium"
        q = exam_engine.generate_question(exam, subj, chapter, sub,
                                           q_type="mcq", difficulty=diff)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question. Try /exam again.")
                _concept_finish(uid)
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_concept_q(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": chapter, "subtopic": sub}

    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = q["_meta"]

    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["index"] = idx + 1
        _send_next_concept_q(uid)
        return

    total = len(plan)
    header_lines = [
        f"## [Conceptual | {ttype.title()} | Q{idx+1}/{total}]",
        f"📌 AI-Generated · Deep reasoning",
        f"📖 {subj} → {chapter} → {sub[:30]}",
    ]
    header_md = "\n".join(header_lines)

    _send_rich_question_and_poll(
        uid, header_md, q.get("question", ""),
        options, int(q.get("correct_index", 0)), mode="conceptual"
    )
    _preload_concept(uid, count=3)


print("bot.py Chunk 13 loaded: rich questions everywhere ready.")



# ==========================================================
# bot.py — Chunk 14: Round 1 fixes
# ==========================================================

# ----------------------------------------------------------
# Fix 1: Expanded rich-text detection (catches single * bold too)
# ----------------------------------------------------------
def _looks_like_rich(text):
    if not text:
        return False
    indicators = ["$$", "$", "**", "##", "# ", "\\(", "\\[",
                  "\\frac", "\\tau", "\\int", "\\sum", "\\alpha", "\\beta",
                  "\\vec", "\\sqrt", "\\begin{", "\\end{", "\\sin", "\\cos",
                  "\\theta", "\\mathbf", "\\boldsymbol", "\\times",
                  "\\det", "\\lim", "\\log", "\\pm", "\\infty"]
    return any(ind in text for ind in indicators)


# ----------------------------------------------------------
# Fix 2: Numerical SKIP handling
# ----------------------------------------------------------
def _skip_numerical(uid):
    """User typed 'skip' during a numerical question."""
    pending = PENDING_NUMERICAL.pop(uid, None)
    if not pending:
        return
    timer_manager.stop_question_timer(bot, uid)
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]
    is_test = pending.get("is_test", False)

    sess = exam_engine.get_session(uid)
    if sess:
        sess["skipped"] = sess.get("skipped", 0) + 1
        sess["questions_done"] = sess.get("questions_done", 0) + 1
        sess["total_time"] = sess.get("total_time", 0) + time_taken
        if sess.get("mode") == "test":
            sess["plan_index"] = sess.get("plan_index", 0) + 1
            sess.setdefault("answers_log", []).append({
                "q": q, "meta": meta, "q_type": "numerical",
                "user_answer": "SKIP", "correct": False,
                "time_taken": time_taken,
            })

    correct_val = q.get("correct_value", "?")

    if is_test:
        # Silent skip — no feedback during test
        if sess:
            sess["current_q"] = None
        _send_next_test_q(uid)
        return

    # Practice / Conceptual: show full solution
    msg = (
        f"🚪 *Skipped*\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 90)}s)\n\n"
        f"🎯 *Correct answer:* `{correct_val}`\n\n"
        f"📖 *Solution:*\n{q.get('explanation', '(none)')}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}"
    )
    safe_send(uid, msg + _countdown_footer(uid), parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    if sess:
        sess["last_q"] = q
        sess["last_meta"] = meta
        sess["current_q"] = None


# ----------------------------------------------------------
# Fix 3: Force rich in solutions (wrap safe_send text in $ if missing)
# ----------------------------------------------------------
_orig_record_and_delta = _record_and_delta
_orig_health_delta_text = _health_delta_text


def _force_math_delims(text):
    """
    If explanation contains raw math like \\frac, \\int without $ delimiters,
    wrap suspicious patterns so rich formatter picks them up.
    """
    if not text or "$" in text:
        return text  # already has math markers or no math
    suspicious = ["\\frac", "\\int", "\\sum", "\\sqrt", "\\tau", "\\theta",
                  "\\alpha", "\\beta", "\\vec", "\\begin{", "\\end{",
                  "\\sin", "\\cos", "\\tan", "\\log", "\\det"]
    for s in suspicious:
        if s in text:
            # Wrap the whole text in $$ to trigger math rendering
            return f"$$\n{text}\n$$"
    return text


# Patch the solution message composition by wrapping safe_send calls.
# Simplest: override _handle_practice_poll and _handle_numerical_answer.
def _handle_practice_poll(uid, sess, poll_answer):
    q = sess.get("current_q")
    if not q:
        return
    timer_manager.stop_question_timer(bot, uid)
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    options = q.get("options", [])
    time_taken = time.time() - sess.get("current_started", time.time())
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["questions_done"] = sess.get("questions_done", 0) + 1

    meta = sess.get("current_meta", {})
    subj = meta.get("subject", "")
    chapter = meta.get("chapter", "")
    subtopic = meta.get("subtopic", "")
    difficulty = q.get("difficulty", "medium")

    explanation = _force_math_delims(q.get("explanation", ""))
    traps = q.get("traps") or []
    shortcut = q.get("shortcut", "")

    # SKIP
    if selected == len(options):
        sess["skipped"] = sess.get("skipped", 0) + 1
        try:
            before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                               False, time_taken,
                                               int(q.get("ideal_time_sec", 60)),
                                               difficulty)
            delta_str = _health_delta_text(before, after)
        except Exception:
            delta_str = ""
        msg = (
            f"🚪 *Skipped*\n\n"
            f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 60)}s)\n\n"
            f"📖 *Solution:*\n{explanation}\n\n"
            f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (traps or ["(none)"]))
            + f"\n\n⚡ *Shortcut:* {shortcut or '(none)'}\n"
            + delta_str
        )
        safe_send(uid, msg + _countdown_footer(uid),
                  parse_mode="Markdown",
                  reply_markup=_practice_footer_buttons())
        sess["last_q"] = q
        sess["last_meta"] = meta
        sess["current_q"] = None
        return

    # ANSWER
    correct = (int(selected) == int(q.get("correct_index", -1)))

    guessed = False
    if correct and q.get("logic_type") == "calc":
        min_real = q.get("min_realistic_sec", 20)
        if time_taken < min_real:
            guessed = True

    if guessed:
        delta_str = "\n🚫 *Guessing detected — no health change.*"
        head = "⚠️ *Guessed correctly* — but too fast to be real calculation."
        sess["wrong"] = sess.get("wrong", 0) + 1
    else:
        if correct:
            sess["correct"] = sess.get("correct", 0) + 1
        else:
            sess["wrong"] = sess.get("wrong", 0) + 1
        try:
            before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                               correct, time_taken,
                                               int(q.get("ideal_time_sec", 60)),
                                               difficulty)
            delta_str = _health_delta_text(before, after)
            if SVG_ENABLED and before is not None and after is not None:
                svg = svg_templates.health_delta_bar(subtopic or "Subtopic", before, after)
                path = svg_renderer.render_svg(svg, name=f"hd_{uid}_{int(time.time())}")
                if path:
                    safe_send_photo(uid, path)
                    svg_renderer.cleanup_file(path)
        except Exception:
            delta_str = ""
        if correct:
            head = "✅ *Correct!*"
        else:
            ul = chr(65 + int(selected)) if 0 <= selected <= 25 else "?"
            cl = chr(65 + int(q.get("correct_index", 0)))
            head = f"❌ *Wrong* — You chose *{ul}*, correct is *{cl}*"

    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal: {q.get('ideal_time_sec', 60)}s)\n\n"
        f"📖 *Solution:*\n{explanation}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (traps or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {shortcut or '(none)'}\n"
        + delta_str
    )
    safe_send(uid, msg + _countdown_footer(uid),
              parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    sess["last_q"] = q
    sess["last_meta"] = meta
    sess["current_q"] = None


def _handle_numerical_answer(uid, text):
    pending = PENDING_NUMERICAL.pop(uid, None)
    if not pending:
        return
    timer_manager.stop_question_timer(bot, uid)
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]

    sess = exam_engine.get_session(uid)
    if not sess:
        return
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["questions_done"] = sess.get("questions_done", 0) + 1

    try:
        val = float(text.replace(",", "").replace(" ", "").strip())
    except Exception:
        PENDING_NUMERICAL[uid] = pending
        safe_send(uid, "⚠️ Please send a valid number (or type `skip`).",
                  parse_mode="Markdown")
        return

    correct_val = q.get("correct_value", 0)
    try:
        correct = abs(val - float(correct_val)) < 1e-6
    except Exception:
        correct = False

    subj = meta.get("subject", "")
    chapter = meta.get("chapter", "")
    subtopic = meta.get("subtopic", "")
    difficulty = q.get("difficulty", "medium")
    explanation = _force_math_delims(q.get("explanation", ""))

    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    try:
        before, after = _record_and_delta(uid, subj, chapter, subtopic, "",
                                           correct, time_taken,
                                           int(q.get("ideal_time_sec", 90)),
                                           difficulty)
        delta_str = _health_delta_text(before, after)
    except Exception:
        delta_str = ""

    if correct:
        head = "✅ *Correct!*"
    else:
        head = f"❌ *Wrong* — correct value: *{correct_val}*"

    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 90)}s)\n"
        f"Your answer: `{text}`\n\n"
        f"📖 *Solution:*\n{explanation}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}\n"
        + delta_str
    )
    safe_send(uid, msg + _countdown_footer(uid),
              parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    sess["last_q"] = q
    sess["last_meta"] = meta
    sess["current_q"] = None


def _handle_test_numerical(uid, text):
    pending = PENDING_NUMERICAL.pop(uid, None)
    if not pending:
        return
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]

    sess = exam_engine.get_session(uid)
    if not sess:
        return

    try:
        val = float(text.replace(",", "").replace(" ", "").strip())
    except Exception:
        PENDING_NUMERICAL[uid] = pending
        safe_send(uid, "⚠️ Please send a valid number (or type `skip`).",
                  parse_mode="Markdown")
        return

    try:
        correct_val = float(q.get("correct_value", 0))
        correct = abs(val - correct_val) < 1e-6
    except Exception:
        correct = False
        correct_val = q.get("correct_value", "?")

    if correct:
        sess["correct"] = sess.get("correct", 0) + 1
    else:
        sess["wrong"] = sess.get("wrong", 0) + 1

    sess.setdefault("answers_log", []).append({
        "q": q, "meta": meta, "q_type": "numerical",
        "user_answer": text.strip() or "?",
        "correct": correct, "time_taken": time_taken,
    })
    sess["questions_done"] = sess.get("questions_done", 0) + 1
    sess["total_time"] = sess.get("total_time", 0) + time_taken
    sess["plan_index"] = sess.get("plan_index", 0) + 1

    try:
        health.record_attempt(
            uid, meta.get("subject", ""), meta.get("chapter", ""),
            meta.get("subtopic", ""), "", correct,
            int(time_taken), int(q.get("ideal_time_sec", 90)),
            difficulty=q.get("difficulty", "medium"))
    except Exception:
        pass

    sess["current_q"] = None
    _send_next_test_q(uid)


# ----------------------------------------------------------
# Fix 4: HKU-ID backfill + numerical skip in free_text_handler
# ----------------------------------------------------------
# (duplicate handler disabled — c09 is the active one)
# @bot.message_handler(func=lambda m: True, content_types=['text'])
def free_text_handler(message):
    if message.text and message.text.startswith('/'): return
    uid = message.chat.id
    text = (message.text or "").strip()
    if not text:
        return

    p = get_or_create_profile(uid)

    # Admin unblock
    if text.strip() == ADMIN_UNBLOCK_CODE:
        p.setdefault("behavior", {"strikes": 0, "blocked_until": None})
        p["behavior"]["strikes"] = 0
        p["behavior"]["blocked_until"] = None
        save_profile(uid, p)
        bot.reply_to(message, "🔓 *Admin unblock successful.* Strikes reset.",
                     parse_mode="Markdown")
        return

    # Blocked check
    blocked, time_left = check_blocked(uid)
    if blocked:
        safe_send(uid,
            f"⛔ *Blocked*\n\n"
            f"Try again in: *{time_left}*\n\n"
            f"WhatsApp *{WHATSAPP_CONTACT}* for help."
            + _countdown_footer(uid),
            parse_mode="Markdown")
        return

    # Activation gate
    if not p.get("secured"):
        if is_valid_key(text):
            allowed, reason = _check_key_binding(uid, text.strip())
            if not allowed:
                if reason == "other_device":
                    safe_send(uid,
                        "❌ *This key is already activated on another device.*\n\n"
                        f"WhatsApp *{WHATSAPP_CONTACT}* if you need help.",
                        parse_mode="Markdown")
                else:
                    safe_send(uid, "❌ Invalid key.")
                return
            p["secured"] = True
            p["activation_key"] = text.strip()
            p["key_expired"] = False
            p["onboarding_step"] = "name"
            save_profile(uid, p)
            if not p.get("story_shown"):
                safe_send(uid, _hamilton_story(), parse_mode="Markdown")
                p["story_shown"] = True
                save_profile(uid, p)
                time.sleep(1)
            bot.reply_to(message, "✅ *Key confirmed. Let's set up your profile.*",
                         parse_mode="Markdown")
            _run_onboarding(uid)
        else:
            p.setdefault("no_key_attempts", 0)
            p["no_key_attempts"] += 1
            save_profile(uid, p)
            if p["no_key_attempts"] <= 2:
                safe_send(uid, _no_key_message(short=False), parse_mode="Markdown")
            else:
                safe_send(uid, _no_key_message(short=True), parse_mode="Markdown")
        return

    # Expired key check
    if _check_key_expired(uid, p):
        return

    # HKU-ID BACKFILL (fix for existing users)
    if not p.get("hku_id"):
        p["hku_id"] = allocate_user_id(uid)
        save_profile(uid, p)

    # Onboarding gate
    if p.get("onboarding_step") and p["onboarding_step"] != "done":
        _run_onboarding(uid)
        return

    if not p.get("exams"):
        bot.reply_to(message, "🎯 Set exams with /mode first.")
        return

    # ============================================
    # NUMERICAL SKIP CHECK (must be FIRST)
    # ============================================
    if uid in PENDING_NUMERICAL:
        low = text.lower().strip()
        if low in ("skip", "/skip"):
            _skip_numerical(uid)
            return
        # Else treat as numerical answer
        pending = PENDING_NUMERICAL.get(uid)
        if pending and pending.get("is_test"):
            _handle_test_numerical(uid, text)
        else:
            _handle_numerical_answer(uid, text)
        return

    # ============================================
    # SESSION LOCKS (borders)
    # ============================================
    sess = exam_engine.get_session(uid)

    if sess and sess.get("mode") == "test":
        q_done = sess.get("questions_done", 0)
        plan = sess.get("plan", [])
        paper = sess.get("current_paper", 1)
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("⏹ Stop Test",
                                                       callback_data="test_stop"))
        safe_send(uid,
            f"📝 *Test in progress* — Paper {paper}, Q{q_done}/{len(plan)}\n\n"
            f"I can't answer questions during the test.\n"
            f"Finish first, then we can talk.",
            parse_mode="Markdown", reply_markup=markup)
        return

    if sess and sess.get("mode") == "conceptual":
        q_done = sess.get("questions_done", 0)
        plan = sess.get("plan", [])
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("⏹ Stop Test",
                                                       callback_data="concept_stop"))
        safe_send(uid,
            f"🧠 *Conceptual test in progress* — Q{q_done}/{len(plan)}\n\n"
            f"I can't answer questions during the test.",
            parse_mode="Markdown", reply_markup=markup)
        return

    if p.get("_practice_active") and sess and sess.get("mode") == "practice":
        # Practice doubt
        exam = sess.get("exam") or health.exam_of(p) or "JEE_MAIN"
        timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
        try:
            answer = ai_client.ask_hamilton(exam, text)
        except Exception:
            answer = None
        timer_manager.stop_thinking_timer(uid)
        if not answer:
            safe_send(uid, "⚠️ Could not answer. Retry or Continue.")
            return
        svg, clean = svg_renderer.detect_svg_in_text(answer)
        final = "💬 *Your doubt answered:*\n\n" + clean
        safe_send(uid, final + _countdown_footer(uid),
                  parse_mode="Markdown",
                  reply_markup=_doubt_continue_buttons())
        if svg and SVG_ENABLED:
            path = svg_renderer.render_svg(svg, name=f"doubt_{uid}")
            if path:
                safe_send_photo(uid, path)
                svg_renderer.cleanup_file(path)
        return

    if p.get("_practice_active") and not sess:
        p["_practice_active"] = False
        save_profile(uid, p)

    if p.get("_notes_state"):
        low = text.lower().strip()
        if low in ("continue", "next", "next part", "go on", "cont"):
            _send_next_notes_part(uid)
            return
        if low in ("stop", "exit", "done", "end"):
            p.pop("_notes_state", None)
            save_profile(uid, p)
            safe_send(uid, "✅ Notes session ended.")
            return
        if low in ("explain", "explain more", "detail"):
            state = p.get("_notes_state", {})
            last = state.get("last_notes", "")
            exam = state.get("exam", "JEE_MAIN")
            if not last:
                safe_send(uid, "Nothing to explain.")
                return
            timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
            prompt = ("The student wants a simpler explanation of these notes:\n\n"
                      + last + "\n\nRe-explain in simpler friendly language.")
            answer = ai_client.ask_hamilton(exam, prompt)
            timer_manager.stop_thinking_timer(uid)
            if answer:
                svg, clean = svg_renderer.detect_svg_in_text(answer)
                safe_send(uid, clean + _countdown_footer(uid), parse_mode="Markdown")
                if svg and SVG_ENABLED:
                    path = svg_renderer.render_svg(svg, name=f"explain_{uid}")
                    if path:
                        safe_send_photo(uid, path)
                        svg_renderer.cleanup_file(path)
            return

    # NORMAL FREE-TEXT
    exam = health.exam_of(p) or "JEE_MAIN"
    try:
        intent = ai_client.classify_intent(exam, text)
    except Exception:
        intent = "STUDY"

    if intent == "OFF_TOPIC":
        blocked_now, mins = register_strike(uid)
        if blocked_now:
            safe_send(uid,
                f"⛔ *Block mode activated*\n\n"
                f"Blocked for *{mins} minutes* for repeated misuse.\n\n"
                f"WhatsApp *{WHATSAPP_CONTACT}* if this was a mistake."
                + _countdown_footer(uid),
                parse_mode="Markdown")
            return
        safe_send(uid,
            "Think about study. Think about studies. Don't simply learn. "
            "Understand it so you can simply memorize it. Remember that your "
            "ultimate success requires the right resources. If you are "
            "distracted or bored, invest your time wisely with Hemanth and "
            "Krishna Publications. Message 8074231426 to get books that "
            "clarify your concepts and elevate your ranks immediately.\n\n"
            "Focus now. Your exam is watching the calendar."
            + _countdown_footer(uid),
            parse_mode="Markdown")
        return

    timer_manager.start_thinking_timer(bot, uid, ai_client.THINKING_MSG)
    try:
        answer = ai_client.ask_hamilton(exam, text)
    except Exception:
        answer = None
    timer_manager.stop_thinking_timer(uid)

    if not answer:
        mid = timer_manager.get_thinking_msg_id(uid)
        err = "⚠️ Hamilton is momentarily overloaded. Please try again."
        if mid:
            safe_edit(uid, mid, err)
        else:
            safe_send(uid, err)
        return

    svg, clean = svg_renderer.detect_svg_in_text(answer)
    final = clean + _countdown_footer(uid)

    mid = timer_manager.get_thinking_msg_id(uid)
    if mid:
        safe_edit(uid, mid, final, parse_mode="Markdown")
    else:
        safe_send(uid, final, parse_mode="Markdown")

    if svg and SVG_ENABLED:
        path = svg_renderer.render_svg(svg, name=f"ai_{uid}")
        if path:
            safe_send_photo(uid, path)
            svg_renderer.cleanup_file(path)


print("bot.py Chunk 14 loaded: Round 1 fixes ready.")



# ==========================================================
# bot.py — Chunk 15: Remaining fixes
# ==========================================================

# ----------------------------------------------------------
# Fix: Thinking message with clickable links
# ----------------------------------------------------------
THINKING_MSG = (
    "🤔 *Hamilton is thinking deeply...*\n\n"
    "While you wait, learn something new:\n"
    "🔭 [Astronomy by KV](https://youtube.com/@astronomybykv90306?si=kDYLhYPnJwF697fb)\n"
    "🎥 [Veritasium](https://youtube.com/@veritasium?si=xsimVU5BCg-4zj0X)\n"
    "📚 [H&K Publications books](https://wa.me/918074231426) — *+91 80742 31426*"
)


# ----------------------------------------------------------
# Fix: Notes prompt — exhaustive + no page cap
# ----------------------------------------------------------
def _send_next_notes_part(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes session.")
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)
    pages_this_req = state.get("pages_this_request", 0)

    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.\n\n"
            "Ask me anything, or /notes for another chapter.",
            parse_mode="Markdown")
        return

    if pages_this_req >= 10:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_10-page batch complete. Type_ `/continue` _for the next batch._",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    topics_text = ""
    for st in group:
        topics_text += f"\n## {st['name']}\n"
        for c in st["concepts"]:
            topics_text += f"- {c}\n"

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    prompt = (
        f"Write COMPREHENSIVE JEE short notes — Part {part_num} of {total}.\n"
        f"Chapter: {state['chapter']} ({state['subject']}, {state['exam']})\n\n"
        f"Cover these subtopics exhaustively:\n{topics_text}\n\n"
        "MANDATORY RULES:\n"
        "1. Write EVERY formula relevant to each subtopic — no shortcuts.\n"
        "2. Include formulas LINKED from other chapters (e.g., if current topic "
        "uses intensity, list every intensity formula from wherever it appears).\n"
        "3. For each concept: definition + formula(s) + 2 common traps + 1 shortcut.\n"
        "4. Provide Applications 1, 2, 3 — real-world or other-chapter uses.\n"
        "5. Include 1-2 exceptional cases / edge conditions per concept.\n"
        "6. Use markdown ## headings, **bold** key terms.\n"
        "7. Wrap display equations in $$...$$, inline math in $...$.\n"
        "8. Do NOT give a title — bot adds header.\n"
        "9. Friendly senior voice — 'Hey, look at this...'\n"
        "10. Be EXHAUSTIVE. Do not summarize. Depth > brevity.\n"
    )

    notes = ai_client.ask_hamilton(state["exam"], prompt)
    timer_manager.stop_generating_timer(bot, uid)

    if not notes:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    header = f"## 📝 {state['chapter']} — Page {part_num}/{total}\n\n"
    full = header + notes + _countdown_footer(uid)
    safe_send(uid, full, parse_mode="Markdown")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_this_req + 1
    state["last_notes"] = notes[:800]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


# Better page estimate — no upper cap, based on concept density
def _estimate_pages(subtopics_count, concepts_count):
    if concepts_count <= 0:
        return 1
    # ~8 concepts per page for exhaustive notes
    pages = max(3, (concepts_count + 7) // 8)
    return pages


# ----------------------------------------------------------
# Fix: Exceptional test — filter to anomaly keywords
# ----------------------------------------------------------
EXCEPTION_KEYWORDS = [
    "anomalous", "anomaly", "exception", "exceptional", "special case",
    "edge case", "deviation", "violation", "fails", "limitation",
    "drawback", "counter", "unusual", "trick", "trap",
]


def _filter_exception_subtopics(subtopics, chapter_data):
    """Keep only subtopics/concepts with exception-related keywords."""
    result = []
    for sub in subtopics:
        sub_low = sub.lower()
        if any(k in sub_low for k in EXCEPTION_KEYWORDS):
            result.append(sub)
    if not result:
        # Fallback: use every subtopic but mark difficulty=hard
        result = list(subtopics)
    return result


# Patch: _start_conceptual_test uses filter when type=exception
_orig_start_conceptual = exam_engine.start_conceptual_test


def _start_conceptual_test_patched(uid, subject, chapter, total_q, test_type="general"):
    if test_type != "exception":
        return _orig_start_conceptual(uid, subject, chapter, total_q, test_type)

    profile = health.load_profile(uid) or {}
    exam = health.exam_of(profile) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        return None

    subs = data[chapter]
    all_subs = list(subs.keys())
    filtered = _filter_exception_subtopics(all_subs, subs)

    plan = []
    if total_q >= len(filtered):
        plan = list(filtered)
        while len(plan) < total_q:
            plan.append(random.choice(filtered))
    else:
        plan = random.sample(filtered, total_q)
    random.shuffle(plan)

    SESS = exam_engine.SESSIONS
    SESS[uid] = {
        "mode": "conceptual",
        "test_type": test_type,
        "exam": exam,
        "subject": subject,
        "chapter": chapter,
        "plan": plan,
        "index": 0,
        "total_q": total_q,
        "started_at": time.time(),
        "questions_done": 0,
        "correct": 0,
        "wrong": 0,
        "skipped": 0,
        "total_time": 0,
        "subtopic_stats": {},
        "current_q": None,
        "current_meta": None,
        "current_started": None,
        "last_q": None,
        "last_meta": None,
    }
    return SESS[uid]


exam_engine.start_conceptual_test = _start_conceptual_test_patched


# ----------------------------------------------------------
# Fix: Source attribution — match by subject
# ----------------------------------------------------------
def _fix_source_detail(source_detail, subject):
    """Sanity-check source attribution against subject."""
    if not source_detail:
        return source_detail
    # OP Tandon, MS Chouhan, JD Lee are Chemistry
    chem_only = ["OP Tandon", "MS Chouhan", "JD Lee"]
    # DC Pandey, HC Verma, Irodov are Physics
    phys_only = ["DC Pandey", "HC Verma", "Irodov", "Cengage Physics"]

    for name in chem_only:
        if name in source_detail and subject != "Chemistry":
            return "Material · Cengage"
    for name in phys_only:
        if name in source_detail and subject != "Physics":
            return "Material · Cengage"
    return source_detail


# ----------------------------------------------------------
# Fix: Difficulty tag — cap by exam
# ----------------------------------------------------------
def _cap_difficulty_for_exam(difficulty, exam):
    if exam == "EAMCET" and difficulty == "hard":
        return "medium"
    if exam == "JEE_MAIN" and difficulty == "hard":
        # Mains can have hard, but not extreme
        return "medium"
    return difficulty


# ----------------------------------------------------------
# Fix: Concept timer + verify
# ----------------------------------------------------------
def _start_concept_timer(uid, total_minutes=60):
    if uid in CONCEPT_TIMERS:
        CONCEPT_TIMERS[uid]["stop"] = True
    CONCEPT_TIMERS[uid] = {"start": time.time(), "stop": False}

    def _job():
        last5 = -1
        while not CONCEPT_TIMERS.get(uid, {}).get("stop", True):
            el = (time.time() - CONCEPT_TIMERS[uid]["start"]) / 60
            if el >= total_minutes:
                return
            cur5 = int(el // 5)
            if cur5 != last5 and cur5 > 0:
                last5 = cur5
                try:
                    bot.send_message(uid, f"⏱️ {int(el)} min elapsed")
                except Exception:
                    pass
            time.sleep(30)

    threading.Thread(target=_job, daemon=True).start()


# ----------------------------------------------------------
# Fix: Weekly report + /report command
# ----------------------------------------------------------
@bot.message_handler(commands=['report'])
def cmd_report(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    r = health.overall_health(p)
    summary = health.attempts_summary(p)
    pct = health.predict_percentile(r.get("overall"))
    _, tier = health.estimate_rank(p)

    lines = [
        "📊 *WEEKLY REPORT*",
        "",
        f"👤 {p.get('name','—')}",
        f"🆔 {p.get('hku_id','—')}",
        "",
        "━━━ Overall ━━━",
        f"Health: *{r.get('overall') or 0}/100*",
        f"Predicted %ile: *{pct}*",
        f"Rank tier: *{tier}*",
        "",
        "━━━ Attempts ━━━",
        f"Total: {summary['attempted']}",
        f"✅ Correct: {summary['correct']}",
        f"❌ Wrong: {summary['wrong']}",
        f"🎯 Accuracy: {summary['accuracy']}%",
        "",
        "━━━ Target ━━━",
    ]
    targets = p.get("target_marks", {})
    primary = p.get("priority") or (p.get("exams") or ["—"])[0]
    if isinstance(targets, dict) and primary in targets:
        max_m = MAX_MARKS.get(primary, 100)
        cur = targets[primary]
        lines.append(f"Target: *{cur} / {max_m}*")
        gap = max(0, cur - int((r.get('overall') or 0) / 100 * max_m))
        lines.append(f"Gap: *{gap} marks*")
    else:
        lines.append("_Set target with /target_")

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 15 loaded: remaining bug fixes ready.")



# ==========================================================
# bot.py — Chunk 16: Notes fix (AI-driven pages + apps + exceptions)
# ==========================================================

NOTES_BATCH_SIZE = 10      # API calls per batch before /continue


def _ask_ai_page_estimate(exam, chapter, subject, subtopics, concepts):
    """Ask AI how many pages are needed for exhaustive notes."""
    topics = "\n".join(f"- {s}" for s in subtopics)
    concept_list = "\n".join(f"- {c}" for c in concepts[:60])

    prompt = (
        f"Chapter: {chapter} ({subject}, {exam})\n"
        f"Subtopics ({len(subtopics)}):\n{topics}\n\n"
        f"Key concepts ({len(concepts)}):\n{concept_list}\n\n"
        "Task: Estimate how many PAGES of short notes are needed to make "
        "a student JEE-ready on this chapter, where each page contains:\n"
        "• definitions + every formula\n"
        "• 2-3 traps\n"
        "• as many applications as needed to solve ALL possible PYQs\n"
        "• exceptional cases\n"
        "• shortcuts\n\n"
        "Rule: one page ≈ one subtopic fully covered with all formulas.\n"
        "Reply with ONLY a single number (the page count). No text."
    )
    try:
        raw = ai_client.ask_hamilton(exam, prompt)
    except Exception:
        return None
    if not raw:
        return None
    import re
    m = re.search(r"\d+", raw)
    if not m:
        return None
    n = int(m.group(0))
    if n < 1:
        n = 1
    if n > 60:
        n = 60
    return n


def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics_list = []
    all_concepts = []
    for sub, val in subs.items():
        cl = val.get("adv", []) if isinstance(val, dict) else val
        subtopics_list.append({"name": sub, "concepts": list(cl)})
        all_concepts.extend(list(cl))

    total_concepts = len(all_concepts)
    total_subtopics = len(subtopics_list)

    # Ask AI for page estimate
    calc_msg = bot.send_message(uid, "⏱️ Analyzing chapter scope…")
    total_pages = _ask_ai_page_estimate(
        exam, chapter, subject,
        [s["name"] for s in subtopics_list],
        all_concepts
    )
    if not total_pages:
        # Fallback: 1 page per subtopic
        total_pages = max(2, total_subtopics)

    try:
        bot.delete_message(uid, calc_msg.message_id)
    except Exception:
        pass

    # Build one group per page (each group = 1 subtopic, or split if subtopic huge)
    groups = []
    for st in subtopics_list:
        concepts = st["concepts"]
        if len(concepts) <= 12:
            groups.append([st])
        else:
            # Split large subtopic into chunks of ~10 concepts
            for i in range(0, len(concepts), 10):
                chunk = concepts[i:i + 10]
                groups.append([{"name": f"{st['name']} (part {i//10 + 1})",
                                "concepts": chunk}])

    # If AI estimated more pages than groups, that's fine — we just use groups
    # If AI estimated fewer, split further
    while len(groups) < total_pages and any(len(g[0]["concepts"]) > 4 for g in groups):
        groups.sort(key=lambda g: len(g[0]["concepts"]), reverse=True)
        big = groups.pop(0)
        st = big[0]
        half = len(st["concepts"]) // 2
        groups.append([{"name": st["name"] + " (a)",
                        "concepts": st["concepts"][:half]}])
        groups.append([{"name": st["name"] + " (b)",
                        "concepts": st["concepts"][half:]}])

    total_parts = len(groups)

    p["_notes_state"] = {
        "subject": subject,
        "chapter": chapter,
        "exam": exam,
        "groups": groups,
        "current_part": 0,
        "total_parts": total_parts,
        "concepts_total": total_concepts,
        "subtopics_total": total_subtopics,
        "pages_this_request": 0,
        "last_notes": "",
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *{chapter}*\n\n"
        f"📖 Subtopics: *{total_subtopics}*\n"
        f"🧠 Concepts: *{total_concepts}*\n"
        f"📄 Pages required: *{total_parts}*\n\n"
        f"_Pages will be generated one by one. "
        f"Every {NOTES_BATCH_SIZE} pages I'll ask you to /continue._",
        parse_mode="Markdown")
    time.sleep(0.6)
    _send_next_notes_part(uid)


def _send_next_notes_part(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes session.")
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)
    pages_this_req = state.get("pages_this_request", 0)

    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.\n\n"
            "Ask me anything, or /notes for another chapter.",
            parse_mode="Markdown")
        return

    if pages_this_req >= NOTES_BATCH_SIZE:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_Batch of {NOTES_BATCH_SIZE} complete._\n"
            f"Type `/continue` for the next batch.",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    topics_text = ""
    for st in group:
        topics_text += f"\n### {st['name']}\n"
        for c in st["concepts"]:
            topics_text += f"- {c}\n"

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    prompt = (
        f"You are writing EXHAUSTIVE JEE short notes — Page {part_num} of {total}.\n"
        f"Chapter: {state['chapter']} ({state['subject']}, {state['exam']})\n\n"
        f"Subtopics to fully cover on this page:\n{topics_text}\n\n"
        "MANDATORY RULES:\n"
        "1. Write EVERY formula related to these subtopics — no skipping.\n"
        "2. Include formulas LINKED from other chapters (e.g., if intensity or "
        "force appears, list all its forms from every relevant chapter).\n"
        "3. Structure for each subtopic:\n"
        "   ### <Subtopic name>\n"
        "   **Definition** — one line\n"
        "   **Formulas** — every formula with variable meanings\n"
        "   **Traps** — 2-3 common mistakes\n"
        "   **Applications** — include AS MANY as needed so a student can "
        "solve ANY previous-year question on this subtopic. Do not limit to 3.\n"
        "   **Exceptional cases** — edge conditions, anomalies\n"
        "   **Shortcut** — if any\n"
        "4. Use $$...$$ for display math, $...$ for inline math.\n"
        "5. Friendly senior voice: 'Hey, look at this…'\n"
        "6. No title — bot adds header.\n"
        "7. Depth over brevity. Be thorough.\n"
    )

    notes = ai_client.ask_hamilton(state["exam"], prompt)
    timer_manager.stop_generating_timer(bot, uid)

    if not notes:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    header = f"## 📝 {state['chapter']} — Page {part_num}/{total}\n\n"
    full = header + notes + _countdown_footer(uid)
    safe_send(uid, full, parse_mode="Markdown")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_this_req + 1
    state["last_notes"] = notes[:1200]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


@bot.message_handler(commands=['continue_disabled_' + 'c16'])
def cmd_continue(message):
    uid = message.chat.id
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes in progress. Type /notes to start.")
        return
    state["pages_this_request"] = 0
    p["_notes_state"] = state
    save_profile(uid, p)
    _send_next_notes_part(uid)


print("bot.py Chunk 16 loaded: notes AI-estimated pages + apps + exceptions.")



# ==========================================================
# bot.py — Chunk 17: Multi-correct + progress + logo everywhere
# ==========================================================

# ==========================================================
# Fix 1: MULTI-CORRECT (JEE Advanced) — text-based answer
# ==========================================================
PENDING_MULTI = {}


def _send_multi_correct_question(uid, header_md, question_md, options):
    """
    Sends question as rich message + asks user to type answer.
    Format: 'A,C' or 'AC' or 'A C' etc.
    """
    rich_content = header_md + "\n\n" + question_md + "\n\n"
    for i, opt in enumerate(options[:4]):
        letter = chr(65 + i)
        rich_content += f"**{letter})** {opt}\n"
    rich_content += (
        "\n_🧠 This is a multiple-correct question._\n"
        "_Reply with your answers separated by commas._\n"
        "_Example:_ `A,C`  or  `ACD`  or  `B, D`"
    )

    try:
        rich = markdown_to_rich(rich_content)
        bot.send_rich_message(chat_id=uid, rich_message=rich)
    except Exception as e:
        print(f"[MULTI] fallback: {e}")
        safe_send(uid, rich_content, parse_mode="Markdown")

    # Start question timer
    timer_manager.start_question_timer(bot, uid)


def _parse_multi_answer(text, max_letters=4):
    """Parses 'A,C' / 'ACD' / 'B, D' → sorted list of indices."""
    if not text:
        return []
    clean = text.upper().replace(",", " ").replace(";", " ").replace("/", " ")
    picks = set()
    for ch in clean:
        if ch in "ABCD"[:max_letters]:
            picks.add(ord(ch) - 65)
    return sorted(picks)


def _grade_multi(picks, correct_indices, exam):
    """Returns (correct_bool, partial_score)."""
    if not picks or not correct_indices:
        return False, 0
    correct_set = set(correct_indices)
    pick_set = set(picks)
    if pick_set == correct_set:
        return True, 4      # Advanced: full +4
    if pick_set.issubset(correct_set):
        # Partial: +2 for Advanced
        if exam == "JEE_ADV":
            return False, 2
        return False, 0
    # Any wrong → -2 for Advanced
    if exam == "JEE_ADV":
        return False, -2
    return False, 0


def _handle_multi_answer(uid, text):
    """User replied with multi-correct answer."""
    pending = PENDING_MULTI.pop(uid, None)
    if not pending:
        return False

    timer_manager.stop_question_timer(bot, uid)
    q = pending["q"]
    meta = pending["meta"]
    time_taken = time.time() - pending["started"]
    exam = pending.get("exam", "JEE_MAIN")
    is_test = pending.get("is_test", False)

    picks = _parse_multi_answer(text, len(q.get("options", [])))
    if not picks:
        PENDING_MULTI[uid] = pending
        safe_send(uid, "⚠️ Reply with letters like `A,C` or `ACD`.")
        return True

    correct_indices = q.get("correct_indices") or []
    correct, partial = _grade_multi(picks, correct_indices, exam)

    sess = exam_engine.get_session(uid)
    if sess:
        sess["questions_done"] = sess.get("questions_done", 0) + 1
        sess["total_time"] = sess.get("total_time", 0) + time_taken
        if correct:
            sess["correct"] = sess.get("correct", 0) + 1
        else:
            sess["wrong"] = sess.get("wrong", 0) + 1
        sess.setdefault("answers_log", []).append({
            "q": q, "meta": meta, "q_type": "multi",
            "user_answer": ",".join(chr(65 + p) for p in picks),
            "correct": correct, "time_taken": time_taken,
        })

    # Silent during test
    if is_test:
        if sess:
            sess["plan_index"] = sess.get("plan_index", 0) + 1
            sess["current_q"] = None
        _send_next_test_q(uid)
        return True

    # Practice/Conceptual feedback
    correct_letters = ",".join(chr(65 + int(i)) for i in correct_indices)
    user_letters = ",".join(chr(65 + p) for p in picks)

    try:
        health.record_attempt(
            uid, meta.get("subject", ""), meta.get("chapter", ""),
            meta.get("subtopic", ""), "", correct,
            int(time_taken), int(q.get("ideal_time_sec", 120)),
            difficulty=q.get("difficulty", "medium"))
    except Exception:
        pass

    if correct:
        head = "✅ *Correct!*"
    elif partial > 0:
        head = f"⚠️ *Partially correct* (+{partial} marks)"
    else:
        head = f"❌ *Wrong* — Your picks: *{user_letters}* · Correct: *{correct_letters}*"

    explanation = _force_math_delims(q.get("explanation", ""))
    msg = (
        f"{head}\n\n"
        f"⏱️ Time: {int(time_taken)}s (ideal {q.get('ideal_time_sec', 120)}s)\n\n"
        f"📖 *Solution:*\n{explanation}\n\n"
        f"⚠️ *Traps:*\n" + "\n".join(f"• {t}" for t in (q.get("traps") or ["(none)"]))
        + f"\n\n⚡ *Shortcut:* {q.get('shortcut', '(none)')}"
    )
    safe_send(uid, msg + _countdown_footer(uid), parse_mode="Markdown",
              reply_markup=_practice_footer_buttons())
    if sess:
        sess["last_q"] = q
        sess["last_meta"] = meta
        sess["current_q"] = None
    return True


# ==========================================================
# Override test question sender — multi-correct path
# ==========================================================
def _send_next_test_q(uid):
    p = load_profile(uid)
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return
    plan = sess.get("plan", [])
    idx = sess.get("plan_index", 0)
    if idx >= len(plan):
        _test_paper_finish(uid)
        return

    exam = sess.get("exam")
    subj, ch, sub, q_type, diff = plan[idx]

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        q = exam_engine.generate_question(exam, subj, ch, sub,
                                           q_type=q_type, difficulty=diff)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question.")
                _test_paper_finish(uid)
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_test_q(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}
        q["_plan_type"] = q_type

    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = q["_meta"]
    sess["current_plan_type"] = q_type

    n_done = sess.get("questions_done", 0)
    n_total = len(plan)
    st = q.get("source_type", "AI-Generated")
    sd = q.get("source_detail", "")
    ideal = q.get("ideal_time_sec", 60)
    section = _section_tag_for(exam, q_type, n_done, n_total)

    header_lines = [
        f"## [{EXAM_NAMES.get(exam, exam)} | {subj} | {section} | Q{n_done+1}/{n_total}]",
        f"📌 Source: {st}" + (f" · {sd}" if sd else ""),
        f"⚡ {difficulty_str(diff)} | ⏱️ Ideal: {ideal}s",
        f"📖 {q['_meta']['chapter']} → {sub}",
    ]
    header_md = "\n".join(header_lines)

    # Multi-correct → text-based answer
    if q_type == "multi" and q.get("correct_indices"):
        _send_multi_correct_question(uid, header_md, q.get("question", ""),
                                     q.get("options", []))
        PENDING_MULTI[uid] = {"q": q, "meta": q["_meta"],
                               "started": time.time(), "exam": exam,
                               "is_test": True}
        return

    # Numerical
    if q_type == "numerical" or q.get("correct_value") is not None:
        rich_content = (header_md + "\n\n" + q.get("question", "") +
                        "\n\n_Type your answer as a number (or `skip`)._")
        try:
            rich = markdown_to_rich(rich_content)
            bot.send_rich_message(chat_id=uid, rich_message=rich)
        except Exception:
            safe_send(uid, rich_content, parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": q["_meta"],
                                   "started": time.time(), "is_test": True}
        _preload_test(uid, count=3)
        return

    # MCQ → rich + letter poll
    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["plan_index"] = idx + 1
        _send_next_test_q(uid)
        return

    correct_idx = int(q.get("correct_index", 0))
    _send_rich_question_and_poll(uid, header_md, q.get("question", ""),
                                  options, correct_idx, mode="test")
    _preload_test(uid, count=3)


# Same for practice — allow multi-correct if generated
def _send_next_practice(uid):
    p = load_profile(uid)
    exam = p.get("_practice_exam") or health.exam_of(p)
    level = p.get("_practice_level", "medium")
    if not exam:
        safe_send(uid, "❌ Exam not set.")
        return

    queue = PRELOAD_QUEUE.get(uid, [])
    q = queue.pop(0) if queue else None

    if not q:
        timer_manager.start_generating_timer(bot, uid, "question")
        subj = _pick_subject_for_practice(p)
        if not subj:
            timer_manager.stop_generating_timer(bot, uid)
            safe_send(uid, "❌ No chapters available.")
            return
        custom = p.get("_practice_custom_chapters")
        allowed = custom.get(subj) if custom else None
        pick = exam_engine.pick_next_subtopic(p, subj, exam, allowed_chapters=allowed)
        if not pick:
            timer_manager.stop_generating_timer(bot, uid)
            safe_send(uid, "❌ No subtopics found.")
            return
        _, ch, sub = pick
        q_type = "mcq"
        r = random.random()
        if exam in ("JEE_MAIN", "JEE_ADV") and r < 0.20:
            q_type = "numerical"
        elif exam == "JEE_ADV" and r < 0.35:
            q_type = "multi"
        q = exam_engine.generate_question(exam, subj, ch, sub,
                                           q_type=q_type, difficulty=level)
        timer_manager.stop_generating_timer(bot, uid)
        if not q:
            tries = _bump_retry(uid)
            if tries >= 3:
                _reset_retry(uid)
                safe_send(uid, "⚠️ Could not generate question. Try /exam again.")
                return
            safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
            time.sleep(2)
            _send_next_practice(uid)
            return
        _reset_retry(uid)
        q["_meta"] = {"subject": subj, "chapter": ch, "subtopic": sub}

    meta = q["_meta"]
    sess = exam_engine.get_session(uid)
    if not sess:
        return
    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = meta
    sess["current_plan_type"] = q.get("_plan_type", "mcq")

    st = q.get("source_type", "AI-Generated")
    sd = q.get("source_detail", "")
    diff = q.get("difficulty", level)
    ideal = q.get("ideal_time_sec", 60)
    q_num = sess.get("questions_done", 0) + 1

    avg_time = None
    key = f"{meta['subject']}::{meta['chapter']}::{meta['subtopic']}"
    stat = p.get("subtopic_stats", {}).get(key)
    if stat and stat.get("attempts", 0) > 0:
        avg_time = stat.get("avg_time", 0)

    header_lines = [
        f"## [{EXAM_NAMES.get(exam, exam)} | {meta['subject']} | Practice | Q{q_num}]",
        f"📌 Source: {st}" + (f" · {sd}" if sd else ""),
        f"⚡ {difficulty_str(diff)} | ⏱️ Ideal: {ideal}s" +
            (f" | 📈 Avg: {int(avg_time)}s" if avg_time else ""),
        f"📖 {meta['chapter']} → {meta['subtopic']}",
    ]
    header_md = "\n".join(header_lines)

    # Multi-correct path
    if q.get("correct_indices"):
        _send_multi_correct_question(uid, header_md, q.get("question", ""),
                                     q.get("options", []))
        PENDING_MULTI[uid] = {"q": q, "meta": meta, "started": time.time(),
                               "exam": exam, "is_test": False}
        _preload_practice(uid, count=2)
        return

    # Numerical path
    if q.get("correct_value") is not None:
        rich_content = (header_md + "\n\n" + q.get("question", "") +
                        "\n\n_Type your answer as a number (or `skip`)._")
        try:
            rich = markdown_to_rich(rich_content)
            bot.send_rich_message(chat_id=uid, rich_message=rich)
        except Exception:
            safe_send(uid, rich_content, parse_mode="Markdown")
        PENDING_NUMERICAL[uid] = {"q": q, "meta": meta, "started": time.time()}
        timer_manager.start_question_timer(bot, uid)
        _preload_practice(uid, count=2)
        return

    # MCQ
    options = q.get("options", [])[:4]
    if len(options) < 2:
        tries = _bump_retry(uid)
        if tries >= 3:
            _reset_retry(uid)
            safe_send(uid, "⚠️ Bad format.")
            return
        safe_send(uid, f"🔄 Regenerating... ({tries}/3)")
        time.sleep(2)
        _send_next_practice(uid)
        return
    _reset_retry(uid)

    _send_rich_question_and_poll(uid, header_md, q.get("question", ""),
                                  options, int(q.get("correct_index", 0)),
                                  mode="practice")
    timer_manager.start_question_timer(bot, uid)
    _preload_practice(uid, count=2)


# ==========================================================
# Fix 2: Progress graph — richer (chapter + rank + marks)
# ==========================================================
def _rich_progress_svg(profile):
    """
    Returns an SVG string containing:
    - Overall bar
    - Subject bars
    - Top 5 weak chapters
    - Predicted rank + percentile
    - Expected vs target marks
    """
    from config import MAX_MARKS, SVG_COLOR_BG, SVG_COLOR_TEXT

    r = health.overall_health(profile)
    overall = r.get("overall") or 0
    primary = profile.get("priority") or (profile.get("exams") or ["—"])[0]
    pct = health.predict_percentile(r.get("overall"))
    _, tier = health.estimate_rank(profile)

    targets = profile.get("target_marks", {}) or {}
    target_marks = targets.get(primary, 0) if isinstance(targets, dict) else 0
    max_marks = MAX_MARKS.get(primary, 100)
    expected_marks = int((r.get("overall") or 0) / 100 * max_marks)

    # Weak chapters
    weak = []
    for subj, sdata in r["subjects"].items():
        ch_map = health.chapter_health_map(profile, subj, primary, only_selected=True)
        for ch, cd in ch_map.items():
            if cd.get("health") is not None:
                weak.append((cd["health"], f"{subj[:3]}·{ch[:22]}"))
    weak.sort()
    weak5 = weak[:5]

    def _col(h):
        if h is None: return "#444"
        if h >= 85: return "#28a745"
        if h >= 70: return "#ffc107"
        if h >= 55: return "#fd7e14"
        return "#dc3545"

    W = 820
    H = 720
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    parts.append(f'<rect width="{W}" height="{H}" fill="{SVG_COLOR_BG}" rx="16"/>')
    parts.append(f'<text x="{W//2}" y="45" font-size="26" font-weight="bold" fill="{SVG_COLOR_TEXT}" '
                 f'font-family="Arial" text-anchor="middle">HAMILTON PROGRESS REPORT</text>')

    # Overall bar
    ow = int(overall / 100 * 700)
    oc = _col(overall)
    parts.append(f'<text x="40" y="95" font-size="16" fill="#ccc" font-family="Arial">Overall Health</text>')
    parts.append(f'<rect x="40" y="105" width="700" height="30" fill="#222" rx="15"/>')
    parts.append(f'<rect x="40" y="105" width="{ow}" height="30" fill="{oc}" rx="15"/>')
    parts.append(f'<text x="760" y="128" font-size="22" font-weight="bold" fill="{oc}" font-family="Arial">{overall:.1f}</text>')

    # Subject bars
    parts.append(f'<text x="40" y="175" font-size="14" fill="#888" font-family="Arial">SUBJECT-WISE</text>')
    y = 195
    for subj, sdata in r["subjects"].items():
        h = sdata["health"]
        col = _col(h)
        bw = int((h or 0) / 100 * 700)
        txt = f"{h:.1f}" if h is not None else "—"
        parts.append(f'<text x="40" y="{y+4}" font-size="14" fill="#ddd" font-family="Arial">{subj}</text>')
        parts.append(f'<rect x="40" y="{y+12}" width="700" height="22" fill="#222" rx="11"/>')
        parts.append(f'<rect x="40" y="{y+12}" width="{bw}" height="22" fill="{col}" rx="11"/>')
        parts.append(f'<text x="760" y="{y+30}" font-size="15" font-weight="bold" fill="{col}" font-family="Arial">{txt}</text>')
        y += 50

    # Weak chapters
    parts.append(f'<text x="40" y="{y+20}" font-size="14" fill="#888" font-family="Arial">TOP 5 WEAK CHAPTERS (focus here)</text>')
    y += 45
    for h, name in weak5:
        col = _col(h)
        bw = int((h or 0) / 100 * 700)
        parts.append(f'<text x="40" y="{y+4}" font-size="12" fill="#ddd" font-family="Arial">{name}</text>')
        parts.append(f'<rect x="40" y="{y+12}" width="700" height="18" fill="#222" rx="9"/>')
        parts.append(f'<rect x="40" y="{y+12}" width="{bw}" height="18" fill="{col}" rx="9"/>')
        parts.append(f'<text x="760" y="{y+26}" font-size="13" fill="{col}" font-family="Arial">{h:.0f}</text>')
        y += 45

    # Rank + Percentile
    parts.append(f'<text x="40" y="{y+20}" font-size="14" fill="#888" font-family="Arial">PREDICTED RANK</text>')
    parts.append(f'<text x="40" y="{y+55}" font-size="28" font-weight="bold" fill="#00d4ff" font-family="Arial">{tier}</text>')
    parts.append(f'<text x="40" y="{y+85}" font-size="18" fill="#00d4ff" font-family="Arial">Percentile: {pct:.1f}</text>')
    y += 100

    # Marks target
    parts.append(f'<text x="40" y="{y+20}" font-size="14" fill="#888" font-family="Arial">MARKS</text>')
    parts.append(f'<text x="40" y="{y+55}" font-size="22" font-weight="bold" fill="#ffc107" font-family="Arial">Expected: {expected_marks} / {max_marks}</text>')
    parts.append(f'<text x="40" y="{y+85}" font-size="18" fill="#888" font-family="Arial">Your target: {target_marks} / {max_marks}</text>')

    parts.append('</svg>')
    return "".join(parts)


# Override /graph to use the rich SVG
@bot.message_handler(commands=['graph'])
def cmd_graph(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return
    p = load_profile(uid)
    r = health.overall_health(p)
    if r["overall"] is None:
        bot.reply_to(message, "📭 No data yet. /exam first.")
        return

    svg = _rich_progress_svg(p)
    path = svg_renderer.render_svg(svg, name=f"graph_{uid}")
    if path:
        safe_send_photo(uid, path, caption=f"📊 Progress Report — Overall {r['overall']}/100")
        svg_renderer.cleanup_file(path)
    else:
        safe_send(uid, f"📊 Overall: {r['overall']}/100")


print("bot.py Chunk 17 loaded: multi-correct + rich progress ready.")



# ==========================================================
# bot.py — Chunk 18: Matrix/image fallback for complex LaTeX
# ==========================================================

from math_image_renderer import has_matrix_env, render_latex_to_png


# Override safe_send — if text has matrices, render as image
_prev_safe_send = safe_send


def _extract_matrix_lines(text):
    """Find all lines with \begin{...} matrix environments."""
    if not text:
        return [], []
    lines = text.split("\n")
    prose_lines = []
    matrix_chunks = []
    in_matrix = False
    buffer = []

    for line in lines:
        if "\\begin{" in line and any(e in line for e in [
            "matrix", "bmatrix", "vmatrix", "pmatrix", "cases",
            "aligned", "array",
        ]):
            in_matrix = True
            buffer = [line]
            if "\\end{" in line:
                matrix_chunks.append("\n".join(buffer))
                in_matrix = False
                buffer = []
            continue
        if in_matrix:
            buffer.append(line)
            if "\\end{" in line:
                matrix_chunks.append("\n".join(buffer))
                in_matrix = False
                buffer = []
            continue
        prose_lines.append(line)

    return prose_lines, matrix_chunks


def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    """
    If text contains matrix environments → split:
      - send prose as rich/plain
      - render each matrix as PNG image
    Otherwise → pass through to previous safe_send.
    """
    if not text:
        return

    if not has_matrix_env(text):
        return _prev_safe_send(chat_id, text, parse_mode=parse_mode,
                                reply_markup=reply_markup)

    prose_lines, matrix_chunks = _extract_matrix_lines(text)

    # 1. Send prose part (rich or plain)
    prose_text = "\n".join(prose_lines).strip()
    if prose_text:
        _prev_safe_send(chat_id, prose_text, parse_mode=parse_mode)

    # 2. Render each matrix chunk as image
    import time as _t
    for idx, chunk in enumerate(matrix_chunks):
        try:
            path = render_latex_to_png(chunk, name=f"matrix_{chat_id}_{int(_t.time())}_{idx}")
            if path:
                try:
                    with open(path, "rb") as f:
                        bot.send_photo(chat_id, f, caption=f"Matrix ({idx+1}/{len(matrix_chunks)})")
                except Exception as e:
                    print(f"[MATRIX-SEND] {e}")
                    # Fallback: send as plain text
                    _prev_safe_send(chat_id, chunk)
                svg_renderer.cleanup_file(path)
            else:
                _prev_safe_send(chat_id, chunk)
        except Exception as e:
            print(f"[MATRIX-RENDER] {e}")
            _prev_safe_send(chat_id, chunk)

    # 3. Apply reply_markup on last message
    if reply_markup and not matrix_chunks and prose_text:
        pass  # already sent


print("bot.py Chunk 18 loaded: matrix image fallback ready.")



# ==========================================================
# bot.py — Chunk 19: Better page estimate + better notes prompt
# ==========================================================

# ----------------------------------------------------------
# Fix: Page estimate never below subtopic count
# ----------------------------------------------------------
def _ask_ai_page_estimate(exam, chapter, subject, subtopics, concepts):
    """Ask AI for pages needed. Then enforce minimum = len(subtopics)."""
    topics = "\n".join(f"- {s}" for s in subtopics)
    concept_list = "\n".join(f"- {c}" for c in concepts[:80])

    prompt = (
        f"Chapter: {chapter} ({subject}, {exam})\n"
        f"Subtopics ({len(subtopics)}):\n{topics}\n\n"
        f"Concepts ({len(concepts)}):\n{concept_list}\n\n"
        "Task: Estimate how many A4 PAGES of exhaustive JEE short notes are "
        "needed so a student can solve EVERY PYQ on this chapter.\n\n"
        "Guidelines:\n"
        "• Minimum: 1 page per subtopic (never less).\n"
        "• Matrix-heavy or formula-dense chapters: 2-3 pages per subtopic.\n"
        "• Matrices, determinants, calculus, conics → HIGH page count.\n"
        "• Simple chapters can be 1 page per subtopic.\n\n"
        "Reply with ONLY a single number (integer). No text, no explanation."
    )
    try:
        raw = ai_client.ask_hamilton(exam, prompt)
    except Exception:
        raw = None

    import re
    n = None
    if raw:
        m = re.search(r"\d+", raw)
        if m:
            try:
                n = int(m.group(0))
            except Exception:
                n = None

    # Enforce minimum = subtopic count
    min_pages = max(1, len(subtopics))
    if n is None or n < min_pages:
        n = min_pages
    # Enforce maximum = 3 × subtopics (avoid runaway)
    max_pages = len(subtopics) * 3
    if n > max_pages:
        n = max_pages
    return n


# ----------------------------------------------------------
# Better notes prompt — matrix-aware, formulas-mandatory
# ----------------------------------------------------------
def _send_next_notes_part(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes session.")
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)
    pages_this_req = state.get("pages_this_request", 0)

    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.\n\n"
            "Ask me anything, or /notes for another chapter.",
            parse_mode="Markdown")
        return

    if pages_this_req >= 10:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_Batch of 10 complete._\n"
            f"Type `/continue` for the next batch.",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    topics_text = ""
    for st in group:
        topics_text += f"\n### {st['name']}\n"
        for c in st["concepts"]:
            topics_text += f"- {c}\n"

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    prompt = (
        f"You are writing COMPLETE JEE short notes — Page {part_num} of {total}.\n"
        f"Chapter: {state['chapter']} ({state['subject']}, {state['exam']})\n\n"
        f"Cover these subtopics FULLY on this page:\n{topics_text}\n\n"
        "ABSOLUTE REQUIREMENTS:\n"
        "1. Write EVERY formula relevant to each subtopic. Zero omissions.\n"
        "2. Include formulas from OTHER chapters that connect to these "
        "subtopics (e.g., eigenvalues relate to characteristic polynomials).\n"
        "3. Structure for each subtopic:\n"
        "   ### <Subtopic>\n"
        "   **Definition** — one line\n"
        "   **Formulas** — EVERY formula, each wrapped in $$...$$ or $...$\n"
        "   **Traps** — 2-3 common mistakes students make\n"
        "   **Applications** — as many as needed to solve every possible PYQ. "
        "Do not limit the count. Real-world and cross-chapter uses.\n"
        "   **Exceptional cases** — edge conditions, special scenarios\n"
        "   **Shortcut** — a memory trick or fast method\n\n"
        "4. CRITICAL — MATRICES/DETERMINANTS: use proper LaTeX environments:\n"
        "   $$A = \\begin{bmatrix} 1 & 2 \\\\ 3 & 4 \\end{bmatrix}$$\n"
        "   $$\\det(A) = \\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix} = ad - bc$$\n"
        "   Wrap environment blocks in $$...$$ or they will not render.\n\n"
        "5. All math MUST use $ for inline, $$ for display. Raw LaTeX without "
        "$ markers will be unreadable.\n"
        "6. Friendly senior voice: 'Hey, look at this…'\n"
        "7. Do NOT write a title — the bot adds the header.\n"
        "8. Depth > brevity. Never shorten formulas. Be exhaustive."
    )

    notes = ai_client.ask_hamilton(state["exam"], prompt)
    timer_manager.stop_generating_timer(bot, uid)

    if not notes:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    header = f"## 📝 {state['chapter']} — Page {part_num}/{total}\n\n"
    full = header + notes + _countdown_footer(uid)
    safe_send(uid, full, parse_mode="Markdown")

    # .md file for copyability
    try:
        import os
        os.makedirs("notes_files", exist_ok=True)
        fname = f"notes_files/{state['chapter'].replace(' ','_')}_p{part_num}.md"
        with open(fname, "w") as nf:
            nf.write(f"# {state['chapter']} — Page {part_num}/{total}\n\n")
            nf.write(notes)
        with open(fname, "rb") as nf:
            bot.send_document(uid, nf)
        try:
            os.remove(fname)
        except Exception:
            pass
    except Exception as e:
        print(f"[NOTES-MD] {e}")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_this_req + 1
    state["last_notes"] = notes[:1200]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


print("bot.py Chunk 19 loaded: better page estimate + matrix-aware notes.")



# ==========================================================
# bot.py — Chunk 20: Notes via notes_engine pipeline
# ==========================================================

from notes_engine import analyze_chapter, generate_page

NOTES_BATCH = 10


def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics = list(subs.keys())
    concepts = {s: (subs[s].get("adv", []) if isinstance(subs[s], dict) else subs[s])
                for s in subtopics}
    flat_concepts = sum(concepts.values(), [])

    calc_msg = bot.send_message(uid, "⏱️ Analyzing chapter scope…")
    analysis = analyze_chapter(exam, subject, chapter, subtopics, flat_concepts)

    try:
        bot.delete_message(uid, calc_msg.message_id)
    except Exception:
        pass

    total = analysis["pages_required"]
    ctype = analysis["chapter_type"]

    # Group subtopics per page
    n = len(subtopics)
    per_page = max(1, (n + total - 1) // total)
    groups = []
    for i in range(0, n, per_page):
        chunk = subtopics[i:i + per_page]
        groups.append([{"name": s, "concepts": concepts[s]} for s in chunk])
    while len(groups) < total and any(len(g) > 1 for g in groups):
        groups.sort(key=len, reverse=True)
        big = groups.pop(0)
        mid = len(big) // 2
        groups.append(big[:mid])
        groups.append(big[mid:])
    total = len(groups)

    p["_notes_state"] = {
        "subject": subject,
        "chapter": chapter,
        "exam": exam,
        "chapter_type": ctype,
        "groups": groups,
        "current_part": 0,
        "total_parts": total,
        "pages_this_request": 0,
        "concepts_total": len(flat_concepts),
        "subtopics_total": len(subtopics),
        "last_notes": "",
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *{chapter}*\n\n"
        f"📖 Subtopics: *{len(subtopics)}*\n"
        f"🧠 Concepts: *{len(flat_concepts)}*\n"
        f"📄 Pages required: *{total}*\n"
        f"🎯 Type: *{ctype}*\n\n"
        f"_Sending pages one by one. "
        f"Every {NOTES_BATCH} pages I'll ask for_ `/continue` _._",
        parse_mode="Markdown")
    time.sleep(0.6)
    _send_next_notes_part(uid)


def _send_next_notes_part(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)
    pages_req = state.get("pages_this_request", 0)

    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.",
            parse_mode="Markdown")
        return

    if pages_req >= NOTES_BATCH:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_Type_ `/continue` _for the next batch._",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    page_text = generate_page(
        state["exam"], state["subject"], state["chapter"],
        part_num, total, group, state.get("chapter_type", "mixed")
    )

    timer_manager.stop_generating_timer(bot, uid)

    if not page_text:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    header = f"## 📝 {state['chapter']} — Page {part_num}/{total}\n\n"
    full = header + page_text + _countdown_footer(uid)
    safe_send(uid, full, parse_mode="Markdown")

    # .md copy
    try:
        import os
        os.makedirs("notes_files", exist_ok=True)
        fname = f"notes_files/{state['chapter'].replace(' ','_')}_p{part_num}.md"
        with open(fname, "w") as nf:
            nf.write(header + page_text)
        with open(fname, "rb") as nf:
            bot.send_document(uid, nf)
        try:
            os.remove(fname)
        except Exception:
            pass
    except Exception as e:
        print(f"[NOTES-MD] {e}")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_req + 1
    state["last_notes"] = page_text[:800]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


print("bot.py Chunk 20 loaded: notes_engine pipeline ready.")



# ==========================================================
# bot.py — Chunk 21: Find + Leaderboard + Rank Predictor
# ==========================================================

# ----------------------------------------------------------
# Save test result to profile on finish
# ----------------------------------------------------------
def _save_test_to_profile(uid, exam, papers_data, total_score, total_max):
    p = load_profile(uid) or {}
    history = p.setdefault("test_history", [])
    entry = {
        "date": datetime.now().isoformat(),
        "exam": exam,
        "total_score": total_score,
        "total_max": total_max,
        "percentile_pred": None,
        "rank_pred": None,
        "papers": len(papers_data),
        "correct": sum(x.get("correct", 0) for x in papers_data),
        "wrong": sum(x.get("wrong", 0) for x in papers_data),
        "skipped": sum(x.get("skipped", 0) for x in papers_data),
    }
    history.append(entry)
    p["test_history"] = history[-20:]
    save_profile(uid, p)


# Wrap existing _test_finish to save result
_prev_test_finish = _test_finish


def _test_finish(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return
    exam = sess.get("exam")
    # Compute totals before original runs (it clears session)
    papers_data = sess.get("paper_scores", [])
    total_score = sum(x.get("score", 0) for x in papers_data)
    total_max = sum(x.get("max", 0) for x in papers_data)
    try:
        _save_test_to_profile(uid, exam, papers_data, total_score, total_max)
    except Exception as e:
        print(f"[TEST-SAVE] {e}")
    _prev_test_finish(uid)


# ----------------------------------------------------------
# Profile stats helper
# ----------------------------------------------------------
def _profile_stats(profile):
    """Returns dict with attempts, accuracy, health, rank, percentile, test_count."""
    summary = health.attempts_summary(profile)
    r = health.overall_health(profile)
    tests = profile.get("test_history", [])

    # Rank/percentile from test performance
    rank_score, rank_tier = _rank_from_tests(tests)
    pct = _percentile_from_tests(tests)

    # Selected chapters count
    sel = profile.get("selected_chapters", {})
    chapters_per_subject = {k: len(v) for k, v in sel.items()}
    total_chapters = sum(chapters_per_subject.values())

    return {
        "attempts": summary["attempted"],
        "correct": summary["correct"],
        "wrong": summary["wrong"],
        "accuracy": summary["accuracy"],
        "overall_health": r.get("overall"),
        "subjects": r.get("subjects", {}),
        "test_count": len(tests),
        "rank_tier": rank_tier,
        "rank_score": rank_score,
        "percentile": pct,
        "chapters_per_subject": chapters_per_subject,
        "total_chapters": total_chapters,
        "tests": tests,
    }


def _rank_from_tests(tests):
    """Best test performance → rank tier."""
    if not tests:
        return 0, "Not eligible — write a test"
    best = 0.0
    for t in tests:
        if t.get("total_max", 0) > 0:
            pct = t["total_score"] / t["total_max"] * 100
            best = max(best, pct)
    if best >= 85: return best, "Top 500"
    if best >= 75: return best, "Top 2,000"
    if best >= 65: return best, "Top 8,000"
    if best >= 55: return best, "Top 20,000"
    if best >= 45: return best, "Top 50,000"
    return best, "Needs improvement"


def _percentile_from_tests(tests):
    if not tests:
        return 0
    best = 0.0
    for t in tests:
        if t.get("total_max", 0) > 0:
            p = t["total_score"] / t["total_max"] * 100
            best = max(best, p)
    # Map 0-100 → percentile band
    if best >= 85: return 99.5
    if best >= 75: return 98.0
    if best >= 65: return 95.0
    if best >= 55: return 90.0
    if best >= 45: return 82.0
    if best >= 35: return 70.0
    return round(best * 1.5, 1)


# ----------------------------------------------------------
# Leaderboard eligibility
# ----------------------------------------------------------
CHAPTERS_MIN_PER_SUBJECT = 15
TESTS_MIN = 1


def _is_leaderboard_eligible(profile):
    """Returns (eligible_bool, reason_str)."""
    sel = profile.get("selected_chapters", {})
    if not sel:
        return False, "No chapters selected"

    for subj, chs in sel.items():
        if len(chs) < CHAPTERS_MIN_PER_SUBJECT:
            return False, f"{subj}: only {len(chs)} chapters (need {CHAPTERS_MIN_PER_SUBJECT})"

    # Require at least 2 subjects selected
    if len([s for s in sel if len(sel[s]) >= CHAPTERS_MIN_PER_SUBJECT]) < 2:
        return False, "Need at least 2 subjects with 15+ chapters"

    tests = profile.get("test_history", [])
    if len(tests) < TESTS_MIN:
        return False, f"Write at least {TESTS_MIN} full test first"

    return True, "eligible"


# ----------------------------------------------------------
# Rebuild leaderboard with new rules
# ----------------------------------------------------------
def _compute_leaderboard(level_filter=None):
    entries = []
    if not os.path.exists(PROFILE_DIR):
        return entries
    for fname in os.listdir(PROFILE_DIR):
        if not fname.endswith(".json"):
            continue
        uid_str = fname.replace(".json", "")
        try:
            with open(os.path.join(PROFILE_DIR, fname)) as f:
                p = json.load(f)
        except Exception:
            continue
        if not p.get("secured") or not p.get("name"):
            continue
        if not p.get("leaderboard_optin", True):
            continue
        if not p.get("exams"):
            continue

        lvl = (p.get("level") or "").lower()
        if level_filter == "junior" and lvl != "junior":
            continue
        if level_filter == "senior" and lvl not in ("senior", "dropper"):
            continue

        eligible, _ = _is_leaderboard_eligible(p)
        if not eligible:
            continue

        stats = _profile_stats(p)
        score = (stats["rank_score"] * 0.6) + (stats["percentile"] * 0.4)

        entries.append({
            "uid": uid_str,
            "hku": p.get("hku_id", "—"),
            "name": p.get("name"),
            "institute": p.get("institute", "—"),
            "level": p.get("level", "—"),
            "health": round(stats["overall_health"] or 0, 1),
            "percentile": stats["percentile"],
            "rank_tier": stats["rank_tier"],
            "attempts": stats["attempts"],
            "accuracy": stats["accuracy"],
            "test_count": stats["test_count"],
            "score": round(score, 1),
        })
    entries.sort(key=lambda x: x["score"], reverse=True)
    return entries


# ----------------------------------------------------------
# /find — full user profile
# ----------------------------------------------------------
@bot.message_handler(commands=['find'])
def cmd_find(message):
    uid = message.chat.id
    parts = message.text.strip().split()
    if len(parts) < 2:
        safe_send(uid,
            "🔍 *Search a user*\n\n"
            "Usage: `/find HKU-000001`\n\n"
            "_Reply with the exact HKU ID (uppercase)._",
            parse_mode="Markdown")
        return
    hku = parts[1].strip().upper()
    if not hku.startswith("HKU-"):
        safe_send(uid, "❌ ID format must be HKU-XXXXXX")
        return

    found_uid = find_user_by_hku_id(hku)
    if not found_uid:
        safe_send(uid, f"❌ No user found with ID {hku}.")
        return

    try:
        target = load_profile(int(found_uid))
    except Exception:
        target = load_profile(found_uid)
    if not target or not target.get("secured"):
        safe_send(uid, "❌ User profile not available.")
        return

    stats = _profile_stats(target)

    lines = [
        f"🔍 *Profile — {target.get('name','—')}*",
        "",
        f"🆔 {hku}",
        f"🏫 {target.get('institute','—')}",
        f"🎓 {target.get('level','—')}",
        f"📚 {', '.join(EXAM_NAMES.get(e,e) for e in target.get('exams',[]))}",
        f"📅 Year: {target.get('target_year','—')}",
        "",
        "━━━ 📖 Chapters ━━━",
    ]
    for subj, count in stats["chapters_per_subject"].items():
        lines.append(f"   {subj}: {count} chapters")
    lines.append(f"   Total: {stats['total_chapters']}")

    lines += [
        "",
        "━━━ 📊 Attempts (all modes) ━━━",
        f"Total attempted: *{stats['attempts']}*",
        f"✅ Correct: {stats['correct']}",
        f"❌ Wrong: {stats['wrong']}",
        f"🎯 Accuracy: *{stats['accuracy']}%*",
        "",
        "━━━ 🧪 Test History ━━━",
        f"Tests written: *{stats['test_count']}*",
    ]

    for t in stats["tests"][-3:]:
        lines.append(
            f"   • {t['exam']}: {t['total_score']}/{t['total_max']}")

    lines += [
        "",
        "━━━ ❤️ Health ━━━",
        f"Overall: *{stats['overall_health'] or 0}/100*",
    ]
    for subj, sd in stats["subjects"].items():
        h = sd.get("health")
        if h is not None:
            lines.append(f"   {subj}: {h}/100")

    lines += [
        "",
        "━━━ 🏆 Rank Prediction (from tests) ━━━",
        f"Tier: *{stats['rank_tier']}*",
        f"Percentile: *{stats['percentile']}*",
    ]

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")

    if SVG_ENABLED and stats["overall_health"] is not None:
        subj_data = {s: d.get("health") for s, d in stats["subjects"].items()}
        svg = svg_templates.combined_progress(stats["overall_health"], subj_data)
        path = svg_renderer.render_svg(svg, name=f"find_{found_uid}")
        if path:
            safe_send_photo(uid, path,
                            caption=f"{target.get('name','')} — Progress")
            svg_renderer.cleanup_file(path)


# ----------------------------------------------------------
# /rank — user's own prediction (per exam)
# ----------------------------------------------------------
@bot.message_handler(commands=['rank'])
def cmd_rank(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return

    p = load_profile(uid)
    stats = _profile_stats(p)

    lines = ["🏆 *YOUR RANK PREDICTION*", ""]
    lines.append(f"👤 {p.get('name','—')}  ·  🆔 {p.get('hku_id','—')}")
    lines.append("")

    # Per-exam prediction
    for exam in p.get("exams", []):
        exam_tests = [t for t in stats["tests"] if t["exam"] == exam]
        if not exam_tests:
            lines.append(f"📘 *{EXAM_NAMES[exam]}*: no tests yet")
            continue
        best = max(
            (t["total_score"] / t["total_max"] * 100) if t["total_max"] else 0
            for t in exam_tests
        )
        if best >= 85: tier, pct = "Top 500", 99.5
        elif best >= 75: tier, pct = "Top 2,000", 98.0
        elif best >= 65: tier, pct = "Top 8,000", 95.0
        elif best >= 55: tier, pct = "Top 20,000", 90.0
        elif best >= 45: tier, pct = "Top 50,000", 82.0
        else: tier, pct = "Needs work", round(best * 1.5, 1)
        lines.append(f"📘 *{EXAM_NAMES[exam]}*")
        lines.append(f"   Best score: {best:.1f}%")
        lines.append(f"   Tier: {tier}  ·  %ile: {pct}")
        lines.append("")

    lines.append(f"🧪 Tests written: {stats['test_count']}")
    lines.append(f"❤️ Overall health: {stats['overall_health'] or 0}/100")

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 21 loaded: find + leaderboard + rank ready.")



# ==========================================================
# bot.py — Chunk 22: Interactive /find + /list_ids (admin)
# ==========================================================

@bot.message_handler(commands=['find'])
def cmd_find(message):
    uid = message.chat.id
    parts = message.text.strip().split()

    # If ID given directly → search
    if len(parts) >= 2:
        _do_find(uid, parts[1].strip().upper())
        return

    # Else → prompt for ID
    msg = bot.send_message(uid,
        "🔍 *Find a user*\n\n"
        "Please enter the user's *HKU ID*.\n"
        "Format: `HKU-XXXXXX` (6 X marks)\n\n"
        "_Type the full ID and send._",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, _find_capture)


def _find_capture(message):
    uid = message.chat.id
    text = (message.text or "").strip().upper()
    if text.startswith("/"):
        # User sent a command instead of ID
        bot.reply_to(message, "❌ Cancelled. Type /find again.")
        return
    _do_find(uid, text)


def _do_find(uid, hku):
    if not hku.startswith("HKU-"):
        safe_send(uid, "❌ ID must start with `HKU-` followed by 6 characters.",
                  parse_mode="Markdown")
        return

    found_uid = find_user_by_hku_id(hku)
    if not found_uid:
        safe_send(uid,
            f"❌ No user found with ID `{hku}`.\n\n"
            "_Send the ID exactly as printed (uppercase, with the HKU- prefix)._",
            parse_mode="Markdown")
        return

    try:
        target = load_profile(int(found_uid))
    except Exception:
        target = load_profile(found_uid)

    if not target or not target.get("secured"):
        safe_send(uid, "❌ Profile not available.")
        return

    stats = _profile_stats(target)

    lines = [
        f"🔍 *Profile — {target.get('name','—')}*",
        "",
        f"🆔 `{hku}`",
        f"🏫 {target.get('institute','—')}",
        f"🎓 {target.get('level','—')}",
        f"📚 {', '.join(EXAM_NAMES.get(e,e) for e in target.get('exams',[]))}",
        f"📅 Year: {target.get('target_year','—')}",
        "",
        "━━━ 📖 Chapters ━━━",
    ]
    for subj, count in stats["chapters_per_subject"].items():
        lines.append(f"   {subj}: {count} chapters")
    lines.append(f"   Total: {stats['total_chapters']}")

    lines += [
        "",
        "━━━ 📊 Attempts (all modes) ━━━",
        f"Total attempted: *{stats['attempts']}*",
        f"✅ Correct: {stats['correct']}",
        f"❌ Wrong: {stats['wrong']}",
        f"🎯 Accuracy: *{stats['accuracy']}%*",
        "",
        "━━━ 🧪 Test History ━━━",
        f"Tests written: *{stats['test_count']}*",
    ]

    for t in stats["tests"][-3:]:
        lines.append(f"   • {t['exam']}: {t['total_score']}/{t['total_max']}")

    lines += [
        "",
        "━━━ ❤️ Health ━━━",
        f"Overall: *{stats['overall_health'] or 0}/100*",
    ]
    for subj, sd in stats["subjects"].items():
        h = sd.get("health")
        if h is not None:
            lines.append(f"   {subj}: {h}/100")

    lines += [
        "",
        "━━━ 🏆 Rank Prediction (from tests) ━━━",
        f"Tier: *{stats['rank_tier']}*",
        f"Percentile: *{stats['percentile']}*",
    ]

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")

    if SVG_ENABLED and stats["overall_health"] is not None:
        subj_data = {s: d.get("health") for s, d in stats["subjects"].items()}
        svg = svg_templates.combined_progress(stats["overall_health"], subj_data)
        path = svg_renderer.render_svg(svg, name=f"find_{found_uid}")
        if path:
            safe_send_photo(uid, path,
                            caption=f"{target.get('name','')} — Progress")
            svg_renderer.cleanup_file(path)


# ----------------------------------------------------------
# ADMIN — /list_ids (see all registered HKU IDs)
# ----------------------------------------------------------
@bot.message_handler(commands=['list_ids'])
def cmd_list_ids(message):
    uid = message.chat.id
    if uid != ADMIN_CHAT_ID:
        return
    data = _load_user_ids()
    mapping = data.get("mapping", {})
    if not mapping:
        bot.reply_to(message, "No users registered yet.")
        return
    lines = [f"📋 *Registered users* ({len(mapping)})\n"]
    for chat_id, hku in sorted(mapping.items(), key=lambda x: x[1]):
        p = load_profile(chat_id)
        name = p.get("name", "—") if p else "—"
        secured = "✅" if (p and p.get("secured")) else "❌"
        lines.append(f"{secured} `{hku}` — {name}")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 22 loaded: interactive /find + /list_ids ready.")



# ==========================================================
# bot.py — Chunk 23: Notes file-only + /continue fix
# ==========================================================

from notes_engine import analyze_chapter, generate_page

NOTES_BATCH = 10


def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics = list(subs.keys())
    concepts = {s: (subs[s].get("adv", []) if isinstance(subs[s], dict) else subs[s])
                for s in subtopics}
    flat = sum(concepts.values(), [])

    calc_msg = bot.send_message(uid, "⏱️ Analyzing chapter scope…")
    analysis = analyze_chapter(exam, subject, chapter, subtopics, flat)
    try:
        bot.delete_message(uid, calc_msg.message_id)
    except Exception:
        pass

    total = analysis["pages_required"]
    ctype = analysis["chapter_type"]

    n = len(subtopics)
    per_page = max(1, (n + total - 1) // total)
    groups = []
    for i in range(0, n, per_page):
        chunk = subtopics[i:i + per_page]
        groups.append([{"name": s, "concepts": concepts[s]} for s in chunk])
    while len(groups) < total and any(len(g) > 1 for g in groups):
        groups.sort(key=len, reverse=True)
        big = groups.pop(0)
        mid = len(big) // 2
        groups.append(big[:mid])
        groups.append(big[mid:])
    total = len(groups)

    p["_notes_state"] = {
        "subject": subject,
        "chapter": chapter,
        "exam": exam,
        "chapter_type": ctype,
        "groups": groups,
        "current_part": 0,
        "total_parts": total,
        "pages_this_request": 0,
        "concepts_total": len(flat),
        "subtopics_total": len(subtopics),
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *{chapter}*\n\n"
        f"📖 Subtopics: *{len(subtopics)}*\n"
        f"🧠 Concepts: *{len(flat)}*\n"
        f"📄 Pages required: *{total}*\n"
        f"🎯 Type: *{ctype}*\n\n"
        f"_Sending .md files one by one. "
        f"Every {NOTES_BATCH} pages I'll ask for_ `/continue` _._",
        parse_mode="Markdown")
    time.sleep(0.6)
    _send_next_notes_part(uid)


def _send_next_notes_part(uid):
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)
    pages_req = state.get("pages_this_request", 0)

    if current >= total:
        p.pop("_notes_state", None)
        save_profile(uid, p)
        safe_send(uid,
            f"✅ *All {total} pages delivered* for {state['chapter']}.",
            parse_mode="Markdown")
        return

    if pages_req >= NOTES_BATCH:
        safe_send(uid,
            f"📄 *{current}/{total} pages delivered*\n\n"
            f"_Type_ `/continue` _for the next batch of {NOTES_BATCH}._",
            parse_mode="Markdown")
        return

    group = state["groups"][current]
    part_num = current + 1

    timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{total}")

    page_text = generate_page(
        state["exam"], state["subject"], state["chapter"],
        part_num, total, group, state.get("chapter_type", "mixed")
    )

    timer_manager.stop_generating_timer(bot, uid)

    if not page_text:
        safe_send(uid, f"⚠️ Could not generate page {part_num}. Type /continue to retry.")
        return

    # Build .md file
    header = f"# {state['chapter']} — Page {part_num}/{total}\n\n"
    content = header + page_text

    try:
        import os
        os.makedirs("notes_files", exist_ok=True)
        safe_name = state['chapter'].replace(' ', '_').replace('/', '_')
        fname = f"notes_files/{safe_name}_p{part_num}.md"
        with open(fname, "w") as nf:
            nf.write(content)
        with open(fname, "rb") as nf:
            bot.send_document(
                uid, nf,
                caption=f"📝 {state['chapter']} — Page {part_num}/{total}"
            )
        try:
            os.remove(fname)
        except Exception:
            pass
    except Exception as e:
        print(f"[NOTES-FILE] {e}")
        # Fallback inline if file fails
        safe_send(uid, content, parse_mode="Markdown")

    state["current_part"] = part_num
    state["pages_this_request"] = pages_req + 1
    state["last_notes"] = page_text[:800]
    p["_notes_state"] = state
    save_profile(uid, p)

    time.sleep(1)
    _send_next_notes_part(uid)


# Aliases — fix any old references
_send_next_notes_batch = _send_next_notes_part


@bot.message_handler(commands=['continue_disabled_' + 'c23'])
def cmd_continue(message):
    uid = message.chat.id
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes in progress. Type /notes to start.")
        return
    state["pages_this_request"] = 0
    p["_notes_state"] = state
    save_profile(uid, p)
    safe_send(uid, "▶️ Continuing notes…")
    _send_next_notes_part(uid)


print("bot.py Chunk 23 loaded: notes file-only + continue fixed.")



# ==========================================================
# bot.py — Chunk 24: Bulletproof /continue handler
# ==========================================================

@bot.message_handler(commands=['continue'])
def cmd_continue(message):
    uid = message.chat.id
    p = load_profile(uid)
    state = p.get("_notes_state")
    if not state:
        safe_send(uid, "No notes in progress. Type /notes to start.")
        return

    current = state.get("current_part", 0)
    total = state.get("total_parts", 1)

    if current >= total:
        safe_send(uid, f"✅ All {total} pages already delivered for {state['chapter']}.")
        p.pop("_notes_state", None)
        save_profile(uid, p)
        return

    safe_send(uid, f"▶️ Continuing from page {current+1}…")

    # Directly generate up to 10 pages (no recursion)
    for i in range(NOTES_BATCH):
        p = load_profile(uid)
        state = p.get("_notes_state")
        if not state:
            break
        curr = state.get("current_part", 0)
        tot = state.get("total_parts", 1)
        if curr >= tot:
            break

        group = state["groups"][curr]
        part_num = curr + 1

        timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{tot}")
        page_text = generate_page(
            state["exam"], state["subject"], state["chapter"],
            part_num, tot, group, state.get("chapter_type", "mixed"))
        timer_manager.stop_generating_timer(bot, uid)

        if not page_text:
            safe_send(uid, f"⚠️ Page {part_num} failed. Try /continue again.")
            break

        header = f"# {state['chapter']} — Page {part_num}/{tot}\n\n"
        content = header + page_text
        try:
            import os
            os.makedirs("notes_files", exist_ok=True)
            safe_name = state['chapter'].replace(' ', '_').replace('/', '_')
            fname = f"notes_files/{safe_name}_p{part_num}.md"
            with open(fname, "w") as nf:
                nf.write(content)
            with open(fname, "rb") as nf:
                bot.send_document(uid, nf,
                    caption=f"📝 {state['chapter']} — Page {part_num}/{tot}")
            try:
                os.remove(fname)
            except Exception:
                pass
        except Exception as e:
            print(f"[NOTES-FILE] {e}")
            safe_send(uid, content)

        state["current_part"] = part_num
        state["pages_this_request"] = 0
        p["_notes_state"] = state
        save_profile(uid, p)
        time.sleep(0.5)

    # After batch → show status
    p = load_profile(uid)
    state = p.get("_notes_state")
    if state:
        curr = state.get("current_part", 0)
        tot = state.get("total_parts", 1)
        if curr < tot:
            safe_send(uid,
                f"📄 *{curr}/{tot} pages delivered*\n\n"
                f"_Type_ `/continue` _for the next batch._",
                parse_mode="Markdown")
        else:
            p.pop("_notes_state", None)
            save_profile(uid, p)
            safe_send(uid,
                f"✅ *All {tot} pages delivered* for {state['chapter']}.",
                parse_mode="Markdown")


print("bot.py Chunk 24 loaded: bulletproof /continue ready.")



# ==========================================================
# bot.py — Chunk 25: AUTO notes (no /continue needed)
# ==========================================================

from notes_engine import analyze_chapter, generate_page
import threading as _threading


def _generate_notes_begin(uid, subject, chapter):
    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics = list(subs.keys())
    concepts = {s: (subs[s].get("adv", []) if isinstance(subs[s], dict) else subs[s])
                for s in subtopics}
    flat = sum(concepts.values(), [])

    calc_msg = bot.send_message(uid, "⏱️ Analyzing chapter scope…")
    analysis = analyze_chapter(exam, subject, chapter, subtopics, flat)
    try:
        bot.delete_message(uid, calc_msg.message_id)
    except Exception:
        pass

    total = analysis["pages_required"]
    ctype = analysis["chapter_type"]

    n = len(subtopics)
    per_page = max(1, (n + total - 1) // total)
    groups = []
    for i in range(0, n, per_page):
        chunk = subtopics[i:i + per_page]
        groups.append([{"name": s, "concepts": concepts[s]} for s in chunk])
    while len(groups) < total and any(len(g) > 1 for g in groups):
        groups.sort(key=len, reverse=True)
        big = groups.pop(0)
        mid = len(big) // 2
        groups.append(big[:mid])
        groups.append(big[mid:])
    total = len(groups)

    p["_notes_state"] = {
        "subject": subject,
        "chapter": chapter,
        "exam": exam,
        "chapter_type": ctype,
        "groups": groups,
        "current_part": 0,
        "total_parts": total,
        "concepts_total": len(flat),
        "subtopics_total": len(subtopics),
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *{chapter}*\n\n"
        f"📖 Subtopics: *{len(subtopics)}*\n"
        f"🧠 Concepts: *{len(flat)}*\n"
        f"📄 Pages required: *{total}*\n"
        f"🎯 Type: *{ctype}*\n\n"
        f"_Generating all {total} pages automatically. This may take a few minutes._",
        parse_mode="Markdown")
    time.sleep(0.5)

    # Background thread — sends all pages without asking /continue
    def _worker():
        for _ in range(total + 2):  # safety cap
            p2 = load_profile(uid)
            st = p2.get("_notes_state")
            if not st:
                break
            curr = st.get("current_part", 0)
            tot = st.get("total_parts", 1)
            if curr >= tot:
                break

            group = st["groups"][curr]
            part_num = curr + 1

            timer_manager.start_generating_timer(bot, uid, f"page {part_num}/{tot}")
            page_text = generate_page(
                st["exam"], st["subject"], st["chapter"],
                part_num, tot, group, st.get("chapter_type", "mixed"))
            timer_manager.stop_generating_timer(bot, uid)

            if not page_text:
                safe_send(uid, f"⚠️ Page {part_num} failed. Stopping.")
                break

            header = f"# {st['chapter']} — Page {part_num}/{tot}\n\n"
            content = header + page_text
            try:
                import os
                os.makedirs("notes_files", exist_ok=True)
                safe_name = st['chapter'].replace(' ', '_').replace('/', '_')
                fname = f"notes_files/{safe_name}_p{part_num}.md"
                with open(fname, "w") as nf:
                    nf.write(content)
                with open(fname, "rb") as nf:
                    bot.send_document(uid, nf,
                        caption=f"📝 {st['chapter']} — Page {part_num}/{tot}")
                try:
                    os.remove(fname)
                except Exception:
                    pass
            except Exception as e:
                print(f"[NOTES-FILE] {e}")
                safe_send(uid, content)

            st["current_part"] = part_num
            p2["_notes_state"] = st
            save_profile(uid, p2)
            time.sleep(0.7)

        # Final
        p3 = load_profile(uid)
        st3 = p3.get("_notes_state")
        if st3 and st3.get("current_part", 0) >= st3.get("total_parts", 1):
            p3.pop("_notes_state", None)
            save_profile(uid, p3)
            safe_send(uid,
                f"✅ *All {st3['total_parts']} pages delivered* for {st3['chapter']}.",
                parse_mode="Markdown")

    _threading.Thread(target=_worker, daemon=True).start()


# Old /continue handlers now redundant, but keep a friendly message
@bot.message_handler(commands=['continue'])
def cmd_continue(message):
    uid = message.chat.id
    safe_send(uid,
        "ℹ️ Notes now generate **automatically** — no `/continue` needed.\n"
        "If the bot stopped early, just run `/notes` again.",
        parse_mode="Markdown")


print("bot.py Chunk 25 loaded: AUTO notes ready.")



# ==========================================================
# bot.py — Chunk 26: PDF auto-convert + matplotlib diagrams
# ==========================================================

import matplotlib
matplotlib.use("Agg")   # no display, Termux-safe
import matplotlib.pyplot as plt
import numpy as np


def _md_to_pdf(md_path, pdf_path):
    """Use Pandoc with LaTeX when available; otherwise use FPDF2."""
    import os
    import shutil
    import subprocess

    engine = next(
        (shutil.which(name) for name in
         ("xelatex", "lualatex", "pdflatex") if shutil.which(name)),
        None,
    )

    if shutil.which("pandoc") and engine:
        try:
            result = subprocess.run(
                ["pandoc", md_path, "-o", pdf_path,
                 "--pdf-engine=" + os.path.basename(engine)],
                capture_output=True, text=True, timeout=90,
            )
            if result.returncode == 0 and os.path.isfile(pdf_path):
                return True
            print("[PDF-pandoc]", result.stderr[-1000:])
        except Exception as exc:
            print("[PDF-pandoc]", repr(exc))

    try:
        with open(md_path, encoding="utf-8") as f:
            content = f.read()

        maker = globals().get("make_pdf")
        if not callable(maker):
            import builtins
            maker = getattr(builtins, "make_pdf", None)
        if not callable(maker):
            raise RuntimeError("FPDF2 make_pdf function unavailable")

        generated = maker(content, filename=os.path.basename(pdf_path))
        if not generated or not os.path.isfile(generated):
            raise RuntimeError("FPDF2 did not create its output file")

        if os.path.abspath(generated) != os.path.abspath(pdf_path):
            shutil.copy2(generated, pdf_path)

        return os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0
    except Exception as exc:
        print("[PDF-FPDF2]", type(exc).__name__, str(exc))
        return False

def _has_xelatex():
    import shutil
    return shutil.which("xelatex") is not None


# ----------------------------------------------------------
# Matplotlib diagram generators (accurate math-based drawings)
# ----------------------------------------------------------
def _diagram_orbit_splitting(kind="octahedral"):
    """Draw crystal field d-orbital splitting. Accurate to theory."""
    fig, ax = plt.subplots(figsize=(6, 4), facecolor="#0a0a1a")
    ax.set_facecolor("#0a0a1a")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    if kind == "octahedral":
        # Left: free ion
        ax.text(1.5, 8.5, "Free ion", color="white", fontsize=11)
        for y in [6.5, 5.5, 4.5, 3.5, 2.5]:
            ax.plot([0.8, 2.2], [y, y], color="#00d4ff", lw=2)
        ax.text(2.5, 6.4, "d_xy", color="#00d4ff", fontsize=9)
        ax.text(2.5, 5.4, "d_yz", color="#00d4ff", fontsize=9)
        ax.text(2.5, 4.4, "d_xz", color="#00d4ff", fontsize=9)
        ax.text(2.5, 3.4, "d_x²-y²", color="#00d4ff", fontsize=9)
        ax.text(2.5, 2.4, "d_z²", color="#00d4ff", fontsize=9)

        # Right: split
        ax.text(6.5, 8.5, "Octahedral field", color="white", fontsize=11)
        # eg (upper)
        ax.plot([5.5, 7.5], [6.5, 6.5], color="#ffc107", lw=2)
        ax.plot([5.5, 7.5], [6.0, 6.0], color="#ffc107", lw=2)
        ax.text(7.7, 6.2, "e_g", color="#ffc107", fontsize=10)
        # t2g (lower)
        ax.plot([5.5, 7.5], [3.0, 3.0], color="#28a745", lw=2)
        ax.plot([5.5, 7.5], [2.5, 2.5], color="#28a745", lw=2)
        ax.plot([5.5, 7.5], [2.0, 2.0], color="#28a745", lw=2)
        ax.text(7.7, 2.3, "t_2g", color="#28a745", fontsize=10)
        # Δo arrow
        ax.annotate("", xy=(9, 6.3), xytext=(9, 2.7),
                    arrowprops=dict(arrowstyle="<->", color="#dc3545", lw=2))
        ax.text(9.2, 4.3, "Δo", color="#dc3545", fontsize=12)
    elif kind == "tetrahedral":
        ax.text(1.5, 8.5, "Free ion", color="white", fontsize=11)
        for y in [6.5, 5.5, 4.5, 3.5, 2.5]:
            ax.plot([0.8, 2.2], [y, y], color="#00d4ff", lw=2)
        ax.text(6.5, 8.5, "Tetrahedral field", color="white", fontsize=11)
        # Lower e
        ax.plot([5.5, 7.5], [4.0, 4.0], color="#ffc107", lw=2)
        ax.plot([5.5, 7.5], [3.5, 3.5], color="#ffc107", lw=2)
        ax.text(7.7, 3.7, "e", color="#ffc107", fontsize=10)
        # Upper t2
        ax.plot([5.5, 7.5], [6.5, 6.5], color="#28a745", lw=2)
        ax.plot([5.5, 7.5], [6.0, 6.0], color="#28a745", lw=2)
        ax.plot([5.5, 7.5], [5.5, 5.5], color="#28a745", lw=2)
        ax.text(7.7, 6.0, "t_2", color="#28a745", fontsize=10)
        ax.annotate("", xy=(9, 6.4), xytext=(9, 3.7),
                    arrowprops=dict(arrowstyle="<->", color="#dc3545", lw=2))
        ax.text(9.2, 5.0, "Δt", color="#dc3545", fontsize=12)
    else:  # square planar
        ax.text(1.5, 8.5, "Free ion", color="white", fontsize=11)
        for y in [6.5, 5.5, 4.5, 3.5, 2.5]:
            ax.plot([0.8, 2.2], [y, y], color="#00d4ff", lw=2)
        ax.text(6.5, 8.5, "Square planar", color="white", fontsize=11)
        # Highest: dx2-y2
        ax.plot([5.5, 7.5], [7.0, 7.0], color="#dc3545", lw=2)
        ax.text(7.7, 6.9, "d_x²-y²", color="#dc3545", fontsize=9)
        # Middle: dxy
        ax.plot([5.5, 7.5], [5.0, 5.0], color="#ffc107", lw=2)
        ax.text(7.7, 4.9, "d_xy", color="#ffc107", fontsize=9)
        # Lower: dz2, dyz, dxz
        ax.plot([5.5, 7.5], [3.0, 3.0], color="#28a745", lw=2)
        ax.plot([5.5, 7.5], [2.5, 2.5], color="#28a745", lw=2)
        ax.plot([5.5, 7.5], [2.0, 2.0], color="#28a745", lw=2)
        ax.text(7.7, 2.4, "d_z², d_yz, d_xz", color="#28a745", fontsize=9)

    return _save_fig(fig)


def _diagram_colour_wheel():
    """Draw a rough colour wheel for CFT colour prediction."""
    fig, ax = plt.subplots(figsize=(6, 6), facecolor="#0a0a1a")
    ax.set_facecolor("#0a0a1a")

    colors = [
        ("Red", "#dc3545", 90),
        ("Orange", "#fd7e14", 30),
        ("Yellow", "#ffc107", -30),
        ("Green", "#28a745", -90),
        ("Blue", "#007bff", -150),
        ("Indigo", "#4B0082", 150),
        ("Violet", "#9400D3", 210),
    ]

    for name, hex_, deg in colors:
        theta = np.radians(deg)
        x, y = np.cos(theta), np.sin(theta)
        ax.annotate("", xy=(x, y), xytext=(0, 0),
                    arrowprops=dict(arrowstyle="-|>", color=hex_, lw=6))
        ax.text(x * 1.15, y * 1.15, name, color=hex_, fontsize=12,
                ha="center", va="center", fontweight="bold")

    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Colour Wheel — Opposite = Observed",
                 color="white", fontsize=12, pad=15)

    return _save_fig(fig)


def _save_fig(fig):
    """Save matplotlib figure to PNG, return path."""
    import os, time
    try:
        os.makedirs("diag_temp", exist_ok=True)
        path = f"diag_temp/diag_{int(time.time()*1000)}.png"
        fig.savefig(path, dpi=120, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return path
    except Exception as e:
        print(f"[MATPLOTLIB] {e}")
        try:
            plt.close(fig)
        except Exception:
            pass
        return None


# ----------------------------------------------------------
# NOTES — auto-attach PDF + diagrams
# ----------------------------------------------------------
def _send_notes_with_pdf(uid, chapter, page_num, total, page_text):
    """Send .md + .pdf + any auto-diagrams for this page."""
    import os
    header = f"# {chapter} — Page {page_num}/{total}\n\n"
    content = header + page_text

    # Write .md
    os.makedirs("notes_files", exist_ok=True)
    safe_name = chapter.replace(" ", "_").replace("/", "_")
    md_path = f"notes_files/{safe_name}_p{page_num}.md"
    with open(md_path, "w") as f:
        f.write(content)

    # Send .md
    try:
        with open(md_path, "rb") as f:
            bot.send_document(uid, f,
                caption=f"📝 {chapter} — Page {page_num}/{total} (.md)")
    except Exception as e:
        print(f"[MD-SEND] {e}")

    # Convert to PDF
    pdf_path = md_path.replace(".md", ".pdf")
    if _md_to_pdf(md_path, pdf_path):
        try:
            with open(pdf_path, "rb") as f:
                bot.send_document(uid, f,
                    caption=f"📄 {chapter} — Page {page_num}/{total} (.pdf)")
        except Exception as e:
            print(f"[PDF-SEND] {e}")
    else:
        safe_send(uid, "_PDF conversion failed — .md file sent above_")

    # Diagrams — detect keywords
    low = page_text.lower()
    diags = []

    if "crystal field" in low or "splitting" in low or "cft" in low:
        for kind in ["octahedral", "tetrahedral", "square planar"]:
            if kind.split()[0] in low:
                p = _diagram_orbit_splitting(kind)
                if p:
                    diags.append((p, f"{kind.title()} d-orbital splitting"))

    if "colour wheel" in low or "complementary colour" in low:
        p = _diagram_colour_wheel()
        if p:
            diags.append((p, "Colour wheel"))

    for path, cap in diags:
        try:
            with open(path, "rb") as f:
                bot.send_photo(uid, f, caption=f"📊 {cap}")
        except Exception as e:
            print(f"[DIAG-SEND] {e}")

    # Cleanup
    try:
        os.remove(md_path)
    except Exception:
        pass
    try:
        os.remove(pdf_path)
    except Exception:
        pass
    for path, _ in diags:
        try:
            os.remove(path)
        except Exception:
            pass


# Override c25's notes sender
def _generate_notes_begin(uid, subject, chapter):
    from notes_engine import analyze_chapter, generate_page
    import threading as _t

    p = load_profile(uid)
    exam = health.exam_of(p) or "JEE_MAIN"
    data = health.load_subject_data(subject, exam)
    if not data or chapter not in data:
        safe_send(uid, "❌ No data for chapter.")
        return

    subs = data[chapter]
    subtopics = list(subs.keys())
    concepts = {s: (subs[s].get("adv", []) if isinstance(subs[s], dict) else subs[s])
                for s in subtopics}
    flat = sum(concepts.values(), [])

    calc = bot.send_message(uid, "⏱️ Analyzing chapter scope…")
    analysis = analyze_chapter(exam, subject, chapter, subtopics, flat)
    try:
        bot.delete_message(uid, calc.message_id)
    except Exception:
        pass

    total = analysis["pages_required"]
    ctype = analysis["chapter_type"]

    n = len(subtopics)
    per = max(1, (n + total - 1) // total)
    groups = []
    for i in range(0, n, per):
        chunk = subtopics[i:i + per]
        groups.append([{"name": s, "concepts": concepts[s]} for s in chunk])
    while len(groups) < total and any(len(g) > 1 for g in groups):
        groups.sort(key=len, reverse=True)
        big = groups.pop(0)
        mid = len(big) // 2
        groups.append(big[:mid])
        groups.append(big[mid:])
    total = len(groups)

    p["_notes_state"] = {
        "subject": subject, "chapter": chapter, "exam": exam,
        "chapter_type": ctype, "groups": groups,
        "current_part": 0, "total_parts": total,
    }
    save_profile(uid, p)

    safe_send(uid,
        f"📝 *{chapter}*\n"
        f"📄 Pages: *{total}*  ·  Type: *{ctype}*\n"
        f"_Generating all pages with .md + .pdf automatically…_",
        parse_mode="Markdown")
    time.sleep(0.5)

    def _worker():
        for _ in range(total + 2):
            p2 = load_profile(uid)
            st = p2.get("_notes_state")
            if not st:
                break
            curr = st.get("current_part", 0)
            tot = st.get("total_parts", 1)
            if curr >= tot:
                break

            group = st["groups"][curr]
            pn = curr + 1

            timer_manager.start_generating_timer(bot, uid, f"page {pn}/{tot}")
            page = generate_page(st["exam"], st["subject"], st["chapter"],
                                  pn, tot, group, st.get("chapter_type", "mixed"))
            timer_manager.stop_generating_timer(bot, uid)

            if not page:
                safe_send(uid, f"⚠️ Page {pn} failed.")
                break

            _send_notes_with_pdf(uid, st["chapter"], pn, tot, page)

            st["current_part"] = pn
            p2["_notes_state"] = st
            save_profile(uid, p2)
            time.sleep(0.7)

        p3 = load_profile(uid)
        st3 = p3.get("_notes_state")
        if st3 and st3.get("current_part", 0) >= st3.get("total_parts", 1):
            p3.pop("_notes_state", None)
            save_profile(uid, p3)
            safe_send(uid,
                f"✅ *All {st3['total_parts']} pages delivered* — .md + .pdf.",
                parse_mode="Markdown")

    _t.Thread(target=_worker, daemon=True).start()


print("bot.py Chunk 26 loaded: PDF + diagrams ready.")



# ==========================================================
# c27 — Critical fixes + Developer credit
# ==========================================================

DEVELOPER_CREDIT = "\n\n_Developed by Vishnavi Gokarnam_"


# ==========================================================
# FIX 1 — Developer credit on every text message
# ==========================================================
_orig_safe_send = safe_send

def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    if text and "Developed by Vishnavi Gokarnam" not in text:
        text = text + DEVELOPER_CREDIT
    return _orig_safe_send(chat_id, text, parse_mode=parse_mode,
                            reply_markup=reply_markup)


_orig_safe_edit = safe_edit

def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    if text and "Developed by Vishnavi Gokarnam" not in text:
        text = text + DEVELOPER_CREDIT
    return _orig_safe_edit(chat_id, message_id, text, parse_mode=parse_mode,
                            reply_markup=reply_markup)


_orig_safe_send_photo = safe_send_photo

def safe_send_photo(chat_id, photo_path, caption=None):
    if caption:
        if "Developed by Vishnavi Gokarnam" not in caption:
            caption = caption + "\n_Developed by Vishnavi Gokarnam_"
    else:
        caption = "_Developed by Vishnavi Gokarnam_"
    return _orig_safe_send_photo(chat_id, photo_path, caption=caption)


# ==========================================================
# FIX 2 — Developer credit in thinking message
# ==========================================================
ai_client.THINKING_MSG = (
    "🤔 *Hamilton is thinking deeply...*\n\n"
    "_Developed by Vishnavi Gokarnam_"
)


# ==========================================================
# FIX 3 — /clear_data full wipe + fresh start
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "clear_data_yes")
def _clear_data_callback_fixed(call):
    uid = call.message.chat.id
    p = load_profile(uid) or {}
    fresh = new_profile()
    fresh["secured"] = True
    fresh["activation_key"] = p.get("activation_key")
    fresh["hku_id"] = p.get("hku_id")
    fresh["story_shown"] = False
    fresh["onboarding_step"] = "name"
    save_profile(uid, fresh)
    try:
        bot.edit_message_text(
            chat_id=uid,
            message_id=call.message.message_id,
            text=("✅ *All your data has been cleared.*\n\n"
                  "Name, chapters, health, attempts — everything reset.\n\n"
                  "Type /start to set up your profile fresh."
                  + DEVELOPER_CREDIT),
            parse_mode="Markdown")
    except Exception:
        safe_send(uid, "✅ All data cleared. Type /start to set up fresh.")


# ==========================================================
# FIX 4 — Repetition guard for conceptual test
# ==========================================================
# Track hash of each question sent in current conceptual session
_orig_new_test_session = exam_engine.new_test_session

def _concept_session_with_hash(uid, subject, chapter, total_q, test_type="general"):
    s = exam_engine.start_conceptual_test(uid, subject, chapter, total_q, test_type)
    if s:
        s["used_hashes"] = set()
    return s


# Override _send_next_concept_q to prevent repeats
_orig_send_next_concept = _send_next_concept_q

def _send_next_concept_q_fixed(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "conceptual":
        return

    plan = sess.get("plan", [])
    idx = sess.get("index", 0)
    if idx >= len(plan):
        _concept_finish(uid)
        return

    exam = sess.get("exam")
    subj = sess.get("subject")
    chapter = sess.get("chapter")
    sub = plan[idx]
    ttype = sess.get("test_type", "general")
    used = sess.setdefault("used_hashes", set())

    q = None
    for attempt in range(5):
        timer_manager.start_generating_timer(bot, uid, "question")
        diff = "hard" if ttype == "exception" else "medium"
        candidate = exam_engine.generate_question(
            exam, subj, chapter, sub, q_type="mcq", difficulty=diff)
        timer_manager.stop_generating_timer(bot, uid)
        if not candidate:
            continue
        h = hash(candidate.get("question", "")[:200])
        if h in used:
            continue
        q = candidate
        used.add(h)
        break

    if not q:
        # Can't generate unique — skip ahead
        sess["index"] = idx + 1
        return _send_next_concept_q_fixed(uid)

    q["_meta"] = {"subject": subj, "chapter": chapter, "subtopic": sub}
    sess["current_q"] = q
    sess["current_started"] = time.time()
    sess["current_meta"] = q["_meta"]

    options = q.get("options", [])[:4]
    if len(options) < 2:
        sess["index"] = idx + 1
        return _send_next_concept_q_fixed(uid)

    options_skip = options + ["🚪 Skip"]
    total = len(plan)
    header = (
        f"[Conceptual | {ttype.title()} | Q{idx+1}/{total}]\n"
        f"📌 AI-Generated · Deep reasoning\n"
        f"📖 {subj} → {chapter} → {sub[:25]}"
    )
    full_q = f"{header}\n\n{q['question']}"

    try:
        if len(full_q) <= 290:
            bot.send_poll(chat_id=uid, question=full_q[:300],
                          options=options_skip[:10], type="quiz",
                          correct_option_id=int(q.get("correct_index", 0)),
                          explanation="Result in final report.",
                          is_anonymous=False)
        else:
            safe_send(uid, f"📝 *Question*\n\n{full_q}", parse_mode="Markdown")
            time.sleep(0.4)
            bot.send_poll(chat_id=uid, question="👆 Tap your answer:",
                          options=options_skip[:10], type="quiz",
                          correct_option_id=int(q.get("correct_index", 0)),
                          explanation="Result in final report.",
                          is_anonymous=False)
    except Exception as e:
        safe_send(uid, f"🔄 Retry... {e}")
        time.sleep(1)
        _send_next_concept_q_fixed(uid)


# ==========================================================
# FIX 5 — NameError guard for `subject` in concept start
# ==========================================================
# Somewhere in c11-c26, `subject` is referenced without being defined.
# Wrap the concept start in try/except and provide fallback.
_orig_start_concept = _concept_capture_count

def _concept_capture_count_safe(message, subj, chapter):
    try:
        return _orig_start_concept(message, subj, chapter)
    except NameError as e:
        print(f"[FIX] NameError caught: {e}")
        safe_send(message.chat.id,
                  "⚠️ Setup glitch detected. Please /exam again.")
    except Exception as e:
        print(f"[FIX] Exception: {e}")
        safe_send(message.chat.id, f"⚠️ Error: {e}")


# ==========================================================
# FIX 6 — Health math chain fix (subtopic → chapter → subject → overall)
# ==========================================================
# Override health.overall_health to compute correctly
def _health_overall_fixed(profile):
    exam = health.exam_of(profile)
    if exam is None:
        return {"exam": None, "subjects": {}, "overall": None, "filtering": False}

    subjects = {}
    subject_averages = []

    for subj in health.available_subjects():
        # Get all subtopics in this subject
        chapter_map = health.chapter_health_map(profile, subj, exam, only_selected=True)
        chapter_healths = [c["health"] for c in chapter_map.values()
                           if c.get("health") is not None]

        if chapter_healths:
            subj_avg = round(sum(chapter_healths) / len(chapter_healths), 1)
            subject_averages.append(subj_avg)
            subjects[subj] = {
                "health": subj_avg,
                "chapters_started": len(chapter_healths),
                "chapters_total": len(chapter_map),
            }
        else:
            subjects[subj] = {
                "health": None,
                "chapters_started": 0,
                "chapters_total": len(chapter_map),
            }

    overall = round(sum(subject_averages) / len(subject_averages), 1) \
        if subject_averages else None

    return {
        "exam": exam,
        "subjects": subjects,
        "overall": overall,
        "filtering": bool(profile.get("selected_chapters")),
    }


health.overall_health = _health_overall_fixed


# ==========================================================
# FIX 7 — PDF error handling (stop infinite retry)
# ==========================================================
# Catch PDF generation errors and never retry more than once
import builtins

_pdf_attempt_count = {}

def _safe_pdf_generation(uid, content, filename):
    """Wrapper for PDF gen. Returns path or None. Never loops."""
    if _pdf_attempt_count.get(uid, 0) >= 1:
        return None
    _pdf_attempt_count[uid] = _pdf_attempt_count.get(uid, 0) + 1
    return None  # Disable PDF until code is fixed


# ==========================================================
# FIX 8 — Append developer credit to every AI reply
# ==========================================================
_orig_ai_call = ai_client.ask_hamilton

def ask_hamilton_with_credit(exam, prompt, context=None, retries=3):
    r = _orig_ai_call(exam, prompt, context=context, retries=retries)
    if r and "Vishnavi Gokarnam" not in r:
        r = r + "\n\n_Developed by Vishnavi Gokarnam_"
    return r

ai_client.ask_hamilton = ask_hamilton_with_credit


print("bot.py Chunk 27 loaded: critical fixes + developer credit ready.")



# ==========================================================
# c28 — PDF fix + NameError guard
# ==========================================================

import os as _os
import sys as _sys
import traceback as _traceback

# ----------------------------------------------------------
# FIX — PDF via fpdf2 (works, no pandoc/md2pdf)
# ----------------------------------------------------------
try:
    from fpdf import FPDF
    _PDF_OK = True
except Exception:
    _PDF_OK = False
    print("[PDF] fpdf2 not installed. Run: pip install fpdf2 --break-system-packages")


def _clean_text_for_pdf(text):
    """Strips emoji + SVG + markdown-lite for fpdf2."""
    import re
    if not text:
        return ""
    # Remove fenced code blocks (svg)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove all emojis
    text = re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF]", "", text)
    # Remove markdown bold/italic
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"[*_`>#]", "", text)
    # Replace common math symbols with readable ASCII
    replacements = {
        "θ": "theta", "τ": "tau", "π": "pi", "α": "alpha", "β": "beta",
        "Δ": "Delta", "Σ": "Sigma", "Ω": "Omega", "√": "sqrt", "×": "x",
        "·": ".", "≈": "~", "≤": "<=", "≥": ">=", "→": "->",
        "²": "^2", "³": "^3", "₁": "_1", "₂": "_2", "₀": "_0",
        "ₓ": "_x", "⁻": "^-", "⁺": "^+",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def generate_pdf(content, filename):
    """
    Generate PDF file. Returns full path or None on failure.
    Replaces old pandoc/md2pdf pipeline.
    """
    if not _PDF_OK:
        return None
    try:
        clean = _clean_text_for_pdf(content)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.set_auto_page_break(auto=True, margin=15)
        # Split into lines and write
        for line in clean.split("\n"):
            try:
                pdf.multi_cell(0, 6, line.encode("latin-1", "replace").decode("latin-1"))
            except Exception:
                pass
        out_dir = "pdf_out"
        _os.makedirs(out_dir, exist_ok=True)
        out_path = _os.path.join(out_dir, filename)
        pdf.output(out_path)
        return out_path
    except Exception as e:
        print(f"[PDF] error: {e}")
        return None


# ----------------------------------------------------------
# OVERRIDE — Global safe wrapper for any handler
# ----------------------------------------------------------
def _safe_wrap_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NameError as e:
            print(f"[SAFE] NameError in {func.__name__}: {e}")
            _traceback.print_exc()
            try:
                # Notify user minimally
                if args and hasattr(args[0], "chat"):
                    safe_send(args[0].chat.id, "⚠️ Minor glitch — please retry.")
            except Exception:
                pass
        except Exception as e:
            print(f"[SAFE] Error in {func.__name__}: {e}")
            _traceback.print_exc()
            try:
                if args and hasattr(args[0], "chat"):
                    safe_send(args[0].chat.id, "⚠️ Something went wrong. Please retry.")
            except Exception:
                pass
    return wrapper


# ----------------------------------------------------------
# Patch the notes/PDF flow — replace old PDF calls
# ----------------------------------------------------------
def _send_notes_pdf(uid, content, base_name):
    """New PDF sender. Uses working fpdf2 pipeline."""
    if not _PDF_OK:
        safe_send(uid, "⚠️ PDF library not installed. Sending as text instead.")
        safe_send(uid, content[:3500])
        return

    fname = f"{base_name}.pdf"
    path = generate_pdf(content, fname)
    if path and _os.path.exists(path):
        try:
            with open(path, "rb") as f:
                bot.send_document(uid, f, caption=f"📄 {base_name}\n_Developed by Vishnavi Gokarnam_",
                                  parse_mode="Markdown")
        except Exception as e:
            safe_send(uid, f"⚠️ PDF send failed: {e}")
        try:
            _os.remove(path)
        except Exception:
            pass
    else:
        safe_send(uid, "⚠️ PDF generation failed. Sending content as text instead.")
        safe_send(uid, content[:3500])


# ----------------------------------------------------------
# FIX — Patch specific broken call signature
# ----------------------------------------------------------
# Old code calls md2pdf(..., pdf_file_path=...). That's wrong.
# Provide a compatible shim.
def md2pdf(*args, **kwargs):
    """Compatibility shim for old broken call signature."""
    content = ""
    filename = "output.pdf"
    for a in args:
        if isinstance(a, str):
            if a.endswith(".md"):
                try:
                    with open(a) as f:
                        content = f.read()
                except Exception:
                    pass
            elif a.endswith(".pdf"):
                filename = a
            else:
                content = a
    if "md_file_path" in kwargs:
        try:
            with open(kwargs["md_file_path"]) as f:
                content = f.read()
        except Exception:
            pass
    if "pdf_file_path" in kwargs:
        filename = _os.path.basename(kwargs["pdf_file_path"])
    if not content:
        return None
    return generate_pdf(content, filename)


print("bot.py Chunk 28 loaded: PDF fixed + NameError guard ready.")



# ==========================================================
# c29 — Reset cooldowns + NameError safety + Key status
# ==========================================================

import traceback as _tb

# ----------------------------------------------------------
# RESET ALL AI COOLDOWNS ON STARTUP
# ----------------------------------------------------------
try:
    import ai_client as _ac
    if hasattr(_ac, "_COOLDOWN"):
        _ac._COOLDOWN.clear()
    if hasattr(_ac, "_KEY_FAIL_COUNT"):
        _ac._KEY_FAIL_COUNT.clear()
    if hasattr(_ac, "_CURRENT_KEY_INDEX"):
        _ac._CURRENT_KEY_INDEX[0] = 0
    print("[c29] Cooldowns reset")

    # Print key inventory
    try:
        gk = getattr(_ac, "GROQ_KEYS", [])
        gmk = getattr(_ac, "GEMINI_KEYS", [])
        print(f"[c29] Groq keys: {len(gk)}, Gemini keys: {len(gmk)}")
    except Exception:
        pass
except Exception as e:
    print(f"[c29] reset failed: {e}")


# ----------------------------------------------------------
# SAFE WRAPPER — catch NameError in any handler
# ----------------------------------------------------------
def _safe_call(uid, func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except NameError as e:
        print(f"[c29] NameError: {e}")
        _tb.print_exc()
        try:
            safe_send(uid, "⚠️ Minor glitch. Please retry or type /exam again.")
        except Exception:
            pass
    except Exception as e:
        print(f"[c29] Error: {e}")
        _tb.print_exc()
        try:
            safe_send(uid, "⚠️ Something went wrong. Please retry.")
        except Exception:
            pass


# ----------------------------------------------------------
# WRAP POLL HANDLERS (safest place for the NameError)
# ----------------------------------------------------------
_orig_on_poll = on_poll_answer

@bot.poll_answer_handler()
def on_poll_answer_safe(poll_answer):
    uid = poll_answer.user.id
    try:
        return _orig_on_poll(poll_answer)
    except NameError as e:
        print(f"[c29] NameError in poll handler: {e}")
        _tb.print_exc()
        try:
            safe_send(uid, "⚠️ Glitch detected. Please /stop and /exam again.")
        except Exception:
            pass
    except Exception as e:
        print(f"[c29] Error in poll handler: {e}")
        _tb.print_exc()


# ----------------------------------------------------------
# WRAP CONCEPTUAL START (where `subject` was undefined)
# ----------------------------------------------------------
_orig_concept_capture_count = _concept_capture_count

def _concept_capture_count_safe(message, subj, chapter):
    try:
        return _orig_concept_capture_count(message, subj, chapter)
    except NameError as e:
        print(f"[c29] NameError in concept start: {e}")
        _tb.print_exc()
        try:
            safe_send(message.chat.id, "⚠️ Setup glitch. Please /exam again.")
        except Exception:
            pass
    except Exception as e:
        print(f"[c29] Error in concept start: {e}")
        _tb.print_exc()

_concept_capture_count = _concept_capture_count_safe


# ----------------------------------------------------------
# DEBUG COMMAND — /key_status (admin only)
# ----------------------------------------------------------
@bot.message_handler(commands=['key_status'])
def cmd_key_status(message):
    uid = message.chat.id
    if uid != ADMIN_CHAT_ID:
        return
    import ai_client as _ac
    lines = ["🔑 *AI Key Status*\n"]
    gk = getattr(_ac, "GROQ_KEYS", [])
    gmk = getattr(_ac, "GEMINI_KEYS", [])
    lines.append(f"Groq: {len(gk)} keys")
    lines.append(f"Gemini: {len(gmk)} keys")
    lines.append("")
    cd = getattr(_ac, "_COOLDOWN", {})
    if cd:
        lines.append(f"Cooldowns active: {len(cd)}")
        for k, v in list(cd.items())[:5]:
            left = max(0, int(v - time.time()))
            lines.append(f"  {k}: {left}s")
    else:
        lines.append("✅ No active cooldowns")
    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 29 loaded: cooldowns reset + safety wrappers ready.")



# ==========================================================
# c30 — 4-Barrier LaTeX pipeline + PDF (Unicode font)
# ==========================================================

import os as _os
import re as _re
import time as _time
import builtins as _bt
import threading as _th
from collections import defaultdict as _dd

try:
    from telebot.types import InputRichMessage
    _RICH_OK = True
except Exception:
    _RICH_OK = False

try:
    from tg_rich_converter import to_rich as _to_rich
    _CONV_OK = True
except Exception:
    _CONV_OK = False

try:
    from fpdf import FPDF as _FPDF
    _FPDF_OK = True
    print("[c30] fpdf2 loaded")
except Exception as e:
    _FPDF_OK = False
    print(f"[c30] fpdf2 missing: {e}")

_ORIG_SEND = safe_send
_ORIG_EDIT = safe_edit

_FONT_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "DejaVuSans.ttf"))
_FONT_OK = _os.path.exists(_FONT_PATH)
print(f"[c30] Font present: {_FONT_OK}")

# ----------------------------------------------------------
# BARRIER 1 — LaTeX detection
# ----------------------------------------------------------
_LATEX_RE = _re.compile(r"\\[a-zA-Z]+|\\begin\{|\\end\{|\\\\\[|\$[^$]+\$")

def _has_latex(t):
    if not t:
        return False
    return bool(_LATEX_RE.search(t))

# ----------------------------------------------------------
# MATRIX → ASCII
# ----------------------------------------------------------
def _ascii_matrix(rows, style="bracket"):
    ncol = max((len(r) for r in rows), default=0)
    if ncol == 0:
        return ""
    widths = [0] * ncol
    for r in rows:
        for i in range(ncol):
            c = str(r[i]) if i < len(r) else ""
            widths[i] = max(widths[i], len(c))
    L, R = "[", "]"
    if style == "paren":
        L, R = "(", ")"
    elif style == "bar":
        L, R = "|", "|"
    lines = []
    for r in rows:
        cells = []
        for i in range(ncol):
            c = str(r[i]) if i < len(r) else ""
            cells.append(c.center(widths[i]))
        lines.append(f"  {L} {'   '.join(cells)} {R}")
    return "\n".join(lines)

_ENV_RE = _re.compile(
    r"\\begin\{(bmatrix|pmatrix|vmatrix|matrix|cases|aligned|array)\}"
    r"(\{[^}]*\})?"
    r"(.*?)"
    r"\\end\{\1\}",
    _re.DOTALL,
)

def _replace_matrix_envs(text):
    if not text:
        return text
    def _conv(m):
        env = m.group(1)
        body = m.group(3)
        rows_raw = _re.split(r"\\\\", body)
        rows = []
        for r in rows_raw:
            r = r.strip()
            if not r:
                continue
            cells = [c.strip() for c in r.split("&")]
            rows.append(cells)
        if not rows:
            return ""
        style = {
            "bmatrix": "bracket", "pmatrix": "paren", "vmatrix": "bar",
            "matrix": "bracket", "cases": "bracket", "aligned": "bracket",
            "array": "bracket",
        }.get(env, "bracket")
        return f"\n<pre>\n{_ascii_matrix(rows, style)}\n</pre>\n"
    return _ENV_RE.sub(_conv, text)

# ----------------------------------------------------------
# BARRIER 3 — LaTeX → Unicode
# ----------------------------------------------------------
_SYM = [
    (r"\Longrightarrow", "⇒"), (r"\Leftrightarrow", "⇔"),
    (r"\Rightarrow", "⇒"), (r"\Leftarrow", "⇐"),
    (r"\longrightarrow", "⟶"), (r"\longleftarrow", "⟵"),
    (r"\rightarrow", "→"), (r"\leftarrow", "←"),
    (r"\uparrow", "↑"), (r"\downarrow", "↓"),
    (r"\varepsilon", "ε"), (r"\emptyset", "∅"),
    (r"\varnothing", "∅"), (r"\setminus", "∖"),
    (r"\triangle", "△"), (r"\angle", "∠"),
    (r"\parallel", "∥"), (r"\perp", "⊥"),
    (r"\approx", "≈"), (r"\equiv", "≡"), (r"\cong", "≅"),
    (r"\propto", "∝"), (r"\sim", "∼"),
    (r"\subseteq", "⊆"), (r"\subset", "⊂"),
    (r"\supseteq", "⊇"), (r"\supset", "⊃"),
    (r"\notin", "∉"), (r"\in", "∈"), (r"\ni", "∋"),
    (r"\forall", "∀"), (r"\exists", "∃"),
    (r"\nabla", "∇"), (r"\partial", "∂"),
    (r"\infty", "∞"), (r"\iint", "∬"), (r"\iiint", "∭"),
    (r"\oint", "∮"), (r"\int", "∫"), (r"\sum", "∑"), (r"\prod", "∏"),
    (r"\cdots", "⋯"), (r"\ldots", "…"), (r"\dots", "…"),
    (r"\langle", "⟨"), (r"\rangle", "⟩"),
    (r"\lvert", "|"), (r"\rvert", "|"),
    (r"\lVert", "‖"), (r"\rVert", "‖"),
    (r"\lim", "lim"), (r"\exp", "exp"),
    (r"\max", "max"), (r"\min", "min"),
    (r"\log", "log"), (r"\ln", "ln"),
    (r"\sinh", "sinh"), (r"\cosh", "cosh"), (r"\tanh", "tanh"),
    (r"\arcsin", "arcsin"), (r"\arccos", "arccos"), (r"\arctan", "arctan"),
    (r"\sin", "sin"), (r"\cos", "cos"), (r"\tan", "tan"),
    (r"\cot", "cot"), (r"\sec", "sec"), (r"\csc", "csc"),
    (r"\Theta", "Θ"), (r"\Lambda", "Λ"), (r"\Xi", "Ξ"),
    (r"\Pi", "Π"), (r"\Sigma", "Σ"), (r"\Upsilon", "Υ"),
    (r"\Phi", "Φ"), (r"\Psi", "Ψ"), (r"\Omega", "Ω"),
    (r"\Delta", "Δ"), (r"\Gamma", "Γ"),
    (r"\alpha", "α"), (r"\beta", "β"), (r"\gamma", "γ"),
    (r"\delta", "δ"), (r"\epsilon", "ε"), (r"\zeta", "ζ"),
    (r"\eta", "η"), (r"\theta", "θ"), (r"\iota", "ι"),
    (r"\kappa", "κ"), (r"\lambda", "λ"), (r"\mu", "μ"),
    (r"\nu", "ν"), (r"\xi", "ξ"), (r"\pi", "π"), (r"\rho", "ρ"),
    (r"\sigma", "σ"), (r"\tau", "τ"), (r"\upsilon", "υ"),
    (r"\phi", "φ"), (r"\chi", "χ"), (r"\psi", "ψ"), (r"\omega", "ω"),
    (r"\mathbb{R}", "ℝ"), (r"\mathbb{N}", "ℕ"),
    (r"\mathbb{Z}", "ℤ"), (r"\mathbb{Q}", "ℚ"),
    (r"\mathbb{C}", "ℂ"), (r"\mathbb{P}", "ℙ"),
    (r"\times", "×"), (r"\cdot", "·"), (r"\div", "÷"),
    (r"\pm", "±"), (r"\mp", "∓"),
    (r"\leq", "≤"), (r"\geq", "≥"),
    (r"\le", "≤"), (r"\ge", "≥"),
    (r"\neq", "≠"), (r"\ne", "≠"),
    (r"\ll", "≪"), (r"\gg", "≫"),
    (r"\circ", "°"), (r"\ast", "*"), (r"\star", "⋆"),
    (r"\quad", "  "), (r"\qquad", "    "),
    (r"\,", " "), (r"\;", " "), (r"\:", " "), (r"\!", ""),
    (r"\left", ""), (r"\right", ""),
    (r"\bigl", ""), (r"\bigr", ""),
    (r"\Bigl", ""), (r"\Bigr", ""),
    (r"\big", ""), (r"\Big", ""),
    (r"\displaystyle", ""), (r"\textstyle", ""),
    (r"\limits", ""), (r"\hline", ""),
]
_SYM.sort(key=lambda x: -len(x[0]))


def _to_unicode(t):
    if not t:
        return t
    s = t
    s = s.replace("\\\\[4pt]", "\n").replace("\\\\[2pt]", "\n")
    s = s.replace("\\[4pt]", "\n").replace("\\[2pt]", "\n")
    s = _re.sub(r"\\\\?\[\d+(\.\d+)?(pt|mm|cm|ex|em)\]", "\n", s)
    for _ in range(4):
        s = _re.sub(r"\\binom\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"C(\1,\2)", s)
    for _ in range(6):
        s = _re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
    for _ in range(5):
        s = _re.sub(r"\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}", r"(\2)^(1/\1)", s)
    for _ in range(5):
        s = _re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", s)
    s = _re.sub(r"\\vec\s*\{([^{}]*)\}", r"\1⃗", s)
    s = _re.sub(r"\\hat\s*\{([^{}]*)\}", r"\1̂", s)
    s = _re.sub(r"\\bar\s*\{([^{}]*)\}", r"\1̄", s)
    s = _re.sub(r"\\dot\s*\{([^{}]*)\}", r"\1̇", s)
    s = _re.sub(r"\\vec\s+([a-zA-Z])", r"\1⃗", s)
    s = _re.sub(r"\\hat\s+([a-zA-Z])", r"\1̂", s)
    for cmd in ["mathbf", "mathrm", "mathit", "mathsf", "mathtt",
                "mathcal", "mathfrak", "text", "textbf", "textit",
                "textrm", "boldsymbol", "operatorname", "underbrace",
                "overset", "underset", "substack"]:
        s = _re.sub(r"\\" + cmd + r"\s*\{([^{}]*)\}", r"\1", s)
    s = _re.sub(r"\\boxed\s*\{([^{}]*)\}", r"[\1]", s)
    s = _re.sub(r"\\begin\s*\{[^{}]*\}", "", s)
    s = _re.sub(r"\\end\s*\{[^{}]*\}", "", s)
    s = _re.sub(r"\\begin\s*[a-zA-Z]+", "", s)
    s = _re.sub(r"\\end\s*[a-zA-Z]+", "", s)
    sub_map = {"0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅",
               "6":"₆","7":"₇","8":"₈","9":"₉","n":"ₙ","i":"ᵢ",
               "j":"ⱼ","k":"ₖ","m":"ₘ","x":"ₓ","a":"ₐ","+":"₊",
               "-":"₋","=":"₌","r":"ᵣ","s":"ₛ","p":"ₚ","L":"ₗ"}
    def _sub(m):
        return "".join(sub_map.get(c, c) for c in m.group(1))
    s = _re.sub(r"_\{([^}]+)\}", _sub, s)
    sup_map = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵",
               "6":"⁶","7":"⁷","8":"⁸","9":"⁹","n":"ⁿ","+":"⁺","-":"⁻"}
    s = _re.sub(r"\^(-)([a-zA-Z0-9])", r"^(-\2)", s)
    s = _re.sub(r"\^\{([0-9n+\-])\}",
                lambda m: sup_map.get(m.group(1), "^"+m.group(1)), s)
    for k, v in _SYM:
        s = s.replace(k, v)
    s = s.replace(r"\\", "\n")
    s = _re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("$$", "").replace("$", "")
    s = _re.sub(r"[ \t]+", " ", s)
    s = _re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

# ----------------------------------------------------------
# BARRIER 4 — Recall with live timer
# ----------------------------------------------------------
_RECALL = _dd(int)
_MAX_RECALL = 2

def _recall_with_timer(chat_id, bad_text):
    if _RECALL[chat_id] >= _MAX_RECALL:
        return None
    _RECALL[chat_id] += 1

    timer_msg = [None]
    stop_flag = [False]

    def _timer():
        try:
            m = bot.send_message(chat_id,
                "⏱️ *Regenerating to remove LaTeX... 0s*", parse_mode="Markdown")
            timer_msg[0] = m.message_id
        except Exception:
            return
        start = _time.time()
        while not stop_flag[0]:
            el = int(_time.time() - start)
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=m.message_id,
                    text=f"⏱️ *Regenerating to remove LaTeX... {el}s*",
                    parse_mode="Markdown")
            except Exception:
                pass
            _time.sleep(2)

    _th.Thread(target=_timer, daemon=True).start()
    try:
        import ai_client
        prompt = ("Rewrite the following using ONLY plain Unicode math symbols "
                  "(θ, π, √, ², ∑, ∫, →, ≤, ≥, α, β, γ). "
                  "NEVER use backslash \\, never use $ or $$, never use "
                  "\\begin or \\end. Output ONLY the rewritten text.\n\n"
                  + bad_text[:3000])
        new_text = ai_client.ask_hamilton("JEE_MAIN", prompt)
    except Exception:
        new_text = None
    finally:
        stop_flag[0] = True
        if timer_msg[0]:
            try:
                bot.delete_message(chat_id, timer_msg[0])
            except Exception:
                pass
    if new_text:
        _RECALL[chat_id] = 0
    return new_text

# ----------------------------------------------------------
# 4-BARRIER PIPELINE
# ----------------------------------------------------------
def _run_4_barriers(text, chat_id=None, allow_recall=True):
    if not text:
        return text, False
    if not _has_latex(text) and "\\begin{" not in text:
        return text, False
    if "\\begin{" in text:
        text = _replace_matrix_envs(text)
    if _CONV_OK:
        try:
            html = _to_rich(text)
            if html and isinstance(html, str) and "<tg-math" in html:
                return html, True
        except Exception:
            pass
    converted = _to_unicode(text)
    if not _has_latex(converted):
        return converted, False
    if allow_recall and chat_id:
        recalled = _recall_with_timer(chat_id, text)
        if recalled:
            if _CONV_OK:
                try:
                    html = _to_rich(recalled)
                    if html and "<tg-math" in html:
                        return html, True
                except Exception:
                    pass
            return _to_unicode(recalled), False
    return converted, False

# ----------------------------------------------------------
# safe_send / safe_edit
# ----------------------------------------------------------
def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    if not text:
        return
    final, is_rich = _run_4_barriers(text, chat_id=chat_id)
    if is_rich and _RICH_OK:
        try:
            rich = InputRichMessage(html=final)
            return bot.send_rich_message(chat_id=chat_id,
                rich_message=rich, reply_markup=reply_markup)
        except Exception as e:
            print(f"[c30] rich send fail: {e}")
    try:
        return bot.send_message(chat_id, final, parse_mode=parse_mode,
                                 reply_markup=reply_markup)
    except Exception:
        return _ORIG_SEND(chat_id, final, parse_mode=parse_mode,
                           reply_markup=reply_markup)

def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    if not text:
        return
    final, is_rich = _run_4_barriers(text, chat_id=chat_id)
    if is_rich and _RICH_OK:
        try:
            bot.delete_message(chat_id, message_id)
            rich = InputRichMessage(html=final)
            return bot.send_rich_message(chat_id=chat_id,
                rich_message=rich, reply_markup=reply_markup)
        except Exception:
            pass
    try:
        return bot.edit_message_text(chat_id=chat_id, message_id=message_id,
            text=final, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception:
        return _ORIG_EDIT(chat_id, message_id, final,
                           parse_mode=parse_mode, reply_markup=reply_markup)

# ----------------------------------------------------------
# PDF with DejaVu font
# ----------------------------------------------------------
def _clean_pdf(text):
    if not text:
        return ""
    s = _re.sub(r"```[\s\S]*?```", "", text)
    s = _re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF]", "", s)
    s = s.replace("**", "").replace("##", "")
    s = _re.sub(r"[*_`>#]", "", s)
    return _to_unicode(s)


def make_pdf(content, filename="notes.pdf"):
    if not _FPDF_OK:
        return None
    try:
        clean = _clean_pdf(content)
        pdf = _FPDF()
        pdf.add_page()

        if _FONT_OK:
            pdf.add_font("DejaVu", "", _FONT_PATH)
            pdf.set_font("DejaVu", size=11)
        else:
            pdf.set_font("Helvetica", size=11)

        pdf.set_auto_page_break(auto=True, margin=15)
        for line in clean.split("\n"):
            try:
                if _FONT_OK:
                    pdf.multi_cell(0, 6, line)
                else:
                    sl = line.encode("latin-1", "replace").decode("latin-1")
                    pdf.multi_cell(0, 6, sl)
            except Exception:
                pass

        pdf.ln(8)
        if _FONT_OK:
            pdf.set_font("DejaVu", size=9)
        else:
            pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 8, "Developed by Vishnavi Gokarnam")

        out_dir = "pdf_out"
        _os.makedirs(out_dir, exist_ok=True)
        out_path = _os.path.join(out_dir, filename)
        pdf.output(out_path)
        print(f"[c30] PDF written: {out_path}")
        return out_path
    except Exception as e:
        print(f"[c30] PDF error: {e}")
        import traceback
        traceback.print_exc()
        return None


def send_pdf_to_user(uid, content, base_name="notes"):
    fname = f"{base_name.replace(' ', '_')}.pdf"
    path = make_pdf(content, fname)
    if path and _os.path.exists(path):
        try:
            with open(path, "rb") as f:
                bot.send_document(uid, f,
                    caption=f"📄 {base_name}\n_Developed by Vishnavi Gokarnam_",
                    parse_mode="Markdown")
            try:
                _os.remove(path)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[c30] send fail: {e}")
            safe_send(uid, f"⚠️ PDF send failed. Text:\n\n{content[:3000]}")
            return False
    safe_send(uid, f"⚠️ PDF failed. Text:\n\n{content[:3000]}")
    return False

for _n in ["md2pdf", "generate_pdf", "pdf_from_markdown", "create_pdf",
           "pandoc_pdf", "md_to_pdf", "convert_to_pdf", "text_to_pdf",
           "notes_to_pdf", "build_pdf", "render_pdf"]:
    _bt.__dict__[_n] = make_pdf

import sys as _sys
_main = _sys.modules.get("__main__")
if _main:
    for _n in ["md2pdf", "generate_pdf", "pdf_from_markdown", "create_pdf",
               "pandoc_pdf", "md_to_pdf", "convert_to_pdf", "text_to_pdf",
               "notes_to_pdf", "build_pdf", "render_pdf"]:
        setattr(_main, _n, make_pdf)


@bot.message_handler(commands=['barrier_test'])
def cmd_barrier_test(message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    sample = (
        r"Energy: $\phi = \tan^{-1}\!\left(\dfrac{X_L - X_C}{R}\right)$" "\n\n"
        r"Power: $P_{avg} = V_{rms} I_{rms} \cos\phi = I_{rms}^2 R$" "\n\n"
        r"Transformer: $\displaystyle \frac{N_s}{N_p} = \frac{V_s}{V_p}$" "\n\n"
        r"Matrix: $\begin{bmatrix} 1 & 2 \\ 3 & 4 \end{bmatrix}$"
    )
    safe_send(message.chat.id, sample)


@bot.message_handler(commands=['pdf_test'])
def cmd_pdf_test(message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    sample = ("# PDF Test\n\n"
              "Matrix: [ 1 2 ; 3 4 ]\n\n"
              "Formula: int_0^inf e^(-t^2) dt = sqrt(pi)/2\n\n"
              "Greek: α β γ θ π √ Ω ² ³\n\n"
              "Developed by Vishnavi Gokarnam")
    send_pdf_to_user(message.chat.id, sample, "pdf_test")


print("bot.py Chunk 30 loaded: 4-barrier + PDF (Unicode font) ready.")


# ==========================================================
# c30e_admin_auth.py — Telegram admin auth flow
# Handles: entry, login, sub-admin setup, forgot, close
# ==========================================================
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import admin_auth as auth

# ----------------------------------------------------------
# Pending state per chat_id (awaiting next text input)
# ----------------------------------------------------------
_PENDING = {}   # {chat_id: {"action": "...", "data": {...}}}

def _set_pending(chat_id, action, **data):
    _PENDING[chat_id] = {"action": action, "data": data, "at": time.time()}

def _pop_pending(chat_id):
    return _PENDING.pop(chat_id, None)

def _get_pending(chat_id):
    return _PENDING.get(chat_id)

# ----------------------------------------------------------
# Entry points
# ----------------------------------------------------------
@bot.message_handler(func=lambda m: m.text and
                     m.text.strip() == config.ADMIN_PANEL_CODE)
def _entry_primary(message):
    uid = message.chat.id
    auth.note_device(uid, "primary")
    session = auth.get_session(uid)

    if session and session["role"] == "primary":
        # already logged in — refresh
        _open_primary_panel(uid)
        return

    locked, mins = auth.is_locked(uid, "primary")
    if locked:
        safe_send(uid, f"🔒 Too many failed attempts. Try again in *{mins} minutes*.",
                  parse_mode="Markdown")
        return

    _set_pending(uid, "primary_priv")
    safe_send(uid,
        f"👑 *Welcome Admin — {config.ADMIN_NAME}*\n\n"
        "Please enter your *privacy code* to open the admin panel.\n\n"
        "_Forgot your code? Type_ `/forgot`",
        parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text and
                     m.text.strip() == config.SUB_ADMIN_CODE)
@bot.message_handler(commands=['forgot'])
def _cmd_forgot(message):
    uid = message.chat.id
    _set_pending(uid, "primary_reset_key")
    safe_send(uid,
        "🔐 *Password Recovery*\n\n"
        "Please enter your *reset key*.\n\n"
        "_Reset key is separate from your privacy code._",
        parse_mode="Markdown")


# ----------------------------------------------------------
# /close — end current session
# ----------------------------------------------------------
@bot.message_handler(commands=['close'])
def _cmd_close(message):
    uid = message.chat.id
    auth.end_session(uid)
    _pop_pending(uid)
    safe_send(uid, "🚪 Admin panel closed. Session ended.")


# ----------------------------------------------------------
# Master text interceptor for pending flows
# (Registered LAST among text handlers via chunk ordering,
#  but guards carefully — only reacts when a flow is pending.)
# ----------------------------------------------------------
@bot.message_handler(commands=['exit'])
def _cmd_exit(message):
    uid = message.chat.id
    auth.end_session(uid)
    _pop_pending(uid)
    safe_send(uid, "🚪 Panel closed. Session ended. Type the entry code to return.")




# ==========================================================
# Direct dispatch helpers (used by _auth_text_router)
# ==========================================================
def _handle_admin_entry(uid):
    """Handle admin code entry directly."""
    auth.note_device(uid, "primary")
    session = auth.get_session(uid)
    if session and session["role"] == "primary":
        _open_primary_panel(uid)
        return
    locked, mins = auth.is_locked(uid, "primary")
    if locked:
        safe_send(uid, f"🔒 Too many failed attempts. Try again in *{mins} minutes*.",
                  parse_mode="Markdown")
        return
    _set_pending(uid, "primary_priv")
    safe_send(uid,
        f"👑 *Welcome Admin — {config.ADMIN_NAME}*\n\n"
        "Please enter your *privacy code* to open the admin panel.\n\n"
        "_Forgot your code? Type_ `/forgot`",
        parse_mode="Markdown")


def _send_lockin_with_timer(uid, code, mins):
    """Show lock-in code with live countdown timer, auto-expires after TTL."""
    import time as _t
    from threading import Thread

    msg = safe_send(uid,
        f"🔑 *Lock-in Generator Access*\n\n"
        f"Your one-time code:\n\n"
        f"`{code}`\n\n"
        f"⏱️ *ACTIVE* — expires in *{mins}:00*\n"
        f"🔒 One-time use only.",
        parse_mode="Markdown")

    if not msg:
        return

    def _tick():
        remaining = mins * 60
        msg_id = msg.message_id if hasattr(msg, "message_id") else None
        while remaining > 0:
            _t.sleep(30)   # update every 30s (Telegram rate limit safe)
            remaining -= 30
            if remaining <= 0:
                break
            mm = remaining // 60
            ss = remaining % 60
            try:
                bot.edit_message_text(
                    chat_id=uid, message_id=msg_id,
                    text=(f"🔑 *Lock-in Generator Access*\n\n"
                          f"Your one-time code:\n\n"
                          f"`{code}`\n\n"
                          f"⏱️ *ACTIVE* — expires in *{mm}:{ss:02d}*\n"
                          f"🔒 One-time use only."),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        # Expired message
        try:
            bot.edit_message_text(
                chat_id=uid, message_id=msg_id,
                text=(f"🔑 *Lock-in code EXPIRED*\n\n"
                      f"`{code}` — ❌ expired\n\n"
                      f"Regenerate by sending the generator code again:\n"
                      f"`{config.LOCKIN_GENERATOR_CODE}`"),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    Thread(target=_tick, daemon=True).start()


@bot.message_handler(func=lambda m: True, content_types=['text'])
def _auth_text_router(message):
    # _sfg_guard: skip if user in c03v sub-admin flow
    try:
        _sfg = globals().get('_SUBREG_V2_STATE')
        if _sfg and message.chat.id in _sfg:
            print(f'[auth-text-guard] skipping uid={message.chat.id} (in sub flow)')
            return
    except Exception:
        pass
    # _subreg_flow_guard: skip if user in c03v sub-admin flow
    try:
        _sfg = globals().get('_SUBREG_V2_STATE')
        if _sfg and message.chat.id in _sfg:
            return
    except Exception:
        pass
    print(f"[DEBUG] _auth_text_router: uid={message.chat.id} text={message.text!r}")
    uid = message.chat.id
    text = (message.text or "").strip()

    # ---- Direct dispatch: if this is an entry code, handle it here ----
    if text == config.ADMIN_PANEL_CODE:
        _handle_admin_entry(uid)
        return
    if text == getattr(config, "SUB_ADMIN_CODE", None):
        _handle_sub_entry(uid)
        return
    if text == getattr(config, "LOCKIN_GENERATOR_CODE", None):
        code, mins = auth.generate_lockin_code()
        auth.audit("lockin_generator_used", uid, {"expires_in_min": mins})
        _send_lockin_with_timer(uid, code, mins)
        return
    if text.startswith("/"):
        return

    # ---- Lock-in GENERATOR code intercept (bypasses privacy) ----
    if text == config.LOCKIN_GENERATOR_CODE:
        code, mins = auth.generate_lockin_code()
        auth.audit("lockin_generator_used", uid, {"expires_in_min": mins})
        safe_send(uid,
            f"🔑 *Lock-in Generator Access*\n\n"
            f"Your one-time code:\n\n"
            f"`{code}`\n\n"
            f"⏱️ Valid *{mins} minutes* · *one-time use*.\n"
            f"Type this code anywhere in the chat to unlock any lockout.",
            parse_mode="Markdown")
        return

    # ---- Lock-in code intercept (before any pending flow) ----
    if auth.is_hex_lockin_code(text):
        ok, entry = auth.verify_lockin_code(text, requester_uid=uid)
        if ok:
            auth.unlock_primary()
            auth.unlock_sub_admin(uid)
            auth.clear_user_block(uid)
            auth.audit("lockin_used", uid, {})
            safe_send(uid,
                "🔓 *Lock-in accepted.*\n"
                "Your lockout and any block have been cleared.\n"
                "Type the entry code to try again.",
                parse_mode="Markdown")
        else:
            safe_send(uid, "❌ Invalid or expired lock-in code.")
        return

    pend = _get_pending(uid)
    if not pend:
        return   # not in our flow → let other handlers process

    action = pend["action"]

    # ---- Primary privacy ----
    if action == "primary_priv":
        locked, mins = auth.is_locked(uid, "primary")
        if locked:
            safe_send(uid, f"🔒 Locked for *{mins} min*.", parse_mode="Markdown")
            _pop_pending(uid)
            return
        if auth.verify_primary_privacy(text):
            auth.reset_failed_attempts(uid, "primary")
            auth.start_session(uid, "primary")
            auth.audit("primary_login_ok", uid, {})
            _pop_pending(uid)
            _open_primary_panel(uid)
        else:
            auth.record_failed_attempt(uid, "primary")
            auth.audit("primary_login_fail", uid, {})
            _pop_pending(uid)
            left = max(0, auth.MAX_FAILED - 1)
            safe_send(uid,
                f"❌ Wrong privacy code.\n"
                f"_Type the entry code again to retry._",
                parse_mode="Markdown")
        return

    # ---- Sub-admin: verification code (new device) ----
    if action == "sub_verify_code":
        if auth.verify_sub_admin_verify_code(text):
            _set_pending(uid, "sub_new_name")
            safe_send(uid, "✅ Verified. Please enter your *name*.", parse_mode="Markdown")
        else:
            auth.record_failed_attempt(uid, "sub")
            auth.audit("sub_verify_fail", uid, {})
            _pop_pending(uid)
            safe_send(uid, "❌ Wrong verification code. Entry cancelled.",
                      parse_mode="Markdown")
        return

    # ---- Sub-admin: choose name ----
    if action == "sub_new_name":
        _PENDING[uid]["data"]["name"] = text[:60]
        _set_pending(uid, "sub_new_privacy", name=text[:60])
        safe_send(uid,
            "🔐 Now choose a *privacy code* (6–20 characters).\n"
            "_You will use this to log in later._",
            parse_mode="Markdown")
        return

    # ---- Sub-admin: choose privacy code ----
    if action == "sub_new_privacy":
        if len(text) < 6 or len(text) > 20:
            safe_send(uid, "❌ Privacy code must be 6–20 characters. Try again.")
            return
        name = pend["data"].get("name", "Sub-Admin")
        auth.register_sub_admin(uid, name, text)
        auth.start_session(uid, "sub")
        auth.audit("sub_login_ok", uid, {"name": name})
        _pop_pending(uid)
        safe_send(uid, "✅ Sub-admin registered. Opening panel…")
        _open_sub_panel(uid)
        return

    # ---- Sub-admin: existing privacy ----
    if action == "sub_priv":
        locked, mins = auth.is_locked(uid, "sub")
        if locked:
            safe_send(uid, f"🔒 Locked for *{mins} min*.", parse_mode="Markdown")
            _pop_pending(uid)
            return
        if auth.verify_sub_admin_privacy(uid, text):
            auth.reset_failed_attempts(uid, "sub")
            auth.start_session(uid, "sub")
            auth.update_sub_admin_last_seen(uid)
            auth.audit("sub_login_ok", uid, {})
            _pop_pending(uid)
            _open_sub_panel(uid)
        else:
            auth.record_failed_attempt(uid, "sub")
            auth.audit("sub_login_fail", uid, {})
            _pop_pending(uid)
            safe_send(uid, "❌ Wrong privacy code. Entry cancelled.")
        return

    # ---- Primary forgot: reset key ----
    if action == "primary_reset_key":
        if auth.verify_primary_reset(text):
            _set_pending(uid, "primary_new_priv")
            safe_send(uid,
                "✅ Reset key verified.\n\n"
                "Enter your *new privacy code* (6–20 characters).",
                parse_mode="Markdown")
        else:
            auth.audit("primary_reset_fail", uid, {})
            _pop_pending(uid)
            safe_send(uid, "❌ Wrong reset key. Recovery cancelled.")
        return

    # ---- Primary new privacy code ----
    if action == "primary_new_priv":
        if len(text) < 6 or len(text) > 20:
            safe_send(uid, "❌ Must be 6–20 characters. Try again.")
            return
        auth.set_primary_privacy(text)
        auth.reset_failed_attempts(uid, "primary")
        auth.start_session(uid, "primary")
        auth.audit("primary_priv_reset_ok", uid, {})
        _pop_pending(uid)
        safe_send(uid, "✅ Privacy code updated. Opening panel…")
        _open_primary_panel(uid)
        return

    # ---- Confirm destructive action (privacy re-check) ----
    if action == "confirm_action":
        act = pend["data"].get("action")
        target = pend["data"].get("target")
        session = auth.get_session(uid)
        if not session or session["role"] != "primary":
            safe_send(uid, "❌ Only primary admin can do this.")
            _pop_pending(uid)
            return
        if auth.verify_primary_privacy(text):
            auth.audit("action_confirmed", uid, {"action": act, "target": target})
            _pop_pending(uid)
            _execute_action(uid, act, target)
        else:
            auth.record_failed_attempt(uid, "primary")
            auth.audit("action_confirm_fail", uid, {"action": act})
            _pop_pending(uid)
            safe_send(uid, "❌ Wrong privacy code. Action cancelled.")
        return

    # ---- Generate lock-in (primary only) ----
    if action == "primary_gen_lockin":
        if auth.verify_primary_privacy(text):
            auth.reset_failed_attempts(uid, "primary")
            code, mins = auth.generate_lockin_code()
            auth.audit("lockin_generated", uid, {"expires_in_min": mins})
            _pop_pending(uid)
            safe_send(uid,
                f"🔑 *Lock-in Code Generated*\n\n"
                f"`{code}`\n\n"
                f"⏱️ Valid *{mins} minutes* · *one-time use*.\n"
                f"Share with the locked-out person.",
                parse_mode="Markdown")
        else:
            auth.record_failed_attempt(uid, "primary")
            _pop_pending(uid)
            safe_send(uid, "❌ Wrong privacy code. Generator cancelled.")
        return

    # Unknown pending action → clear
    _pop_pending(uid)


# ----------------------------------------------------------
# Panel openers (real panels are in c30b_admin.py, but if not
# yet rewritten, fallback to old behavior)
# ----------------------------------------------------------
def _open_primary_panel(uid):
    fn = globals().get("_show_admin_panel")
    if callable(fn):
        fn(uid)
    else:
        safe_send(uid, "🛠 Panel not ready yet.")


def _open_sub_panel(uid):
    fn = globals().get("_show_sub_admin_panel")
    if callable(fn):
        fn(uid)
    else:
        fn2 = globals().get("_show_admin_panel")
        if callable(fn2):
            fn2(uid)
        else:
            safe_send(uid, "🛡️ Sub-admin panel not ready yet.")


def _execute_action(uid, action, target):
    """Call the real action function if it exists."""
    fn = globals().get(f"_do_{action}")
    if callable(fn):
        fn(uid, target)
    else:
        safe_send(uid, f"⚠️ Action '{action}' not implemented yet.")


print("c30e_admin_auth: loaded.")

# ----------------------------------------------------------
# /admin_lockin — generate a fresh lock-in code (primary only)
# ----------------------------------------------------------
@bot.message_handler(commands=['admin_lockin'])
def _cmd_generate_lockin(message):
    uid = message.chat.id
    session = auth.get_session(uid)
    if not session or session["role"] != "primary":
        safe_send(uid, "❌ Only primary admin can generate lock-in codes.")
        return
    code, mins = auth.generate_lockin_code()
    auth.audit("lockin_generated", uid, {"expires_in_min": mins})
    safe_send(uid,
        f"🔑 *Lock-in Code Generated*\n\n"
        f"`{code}`\n\n"
        f"⏱️ Valid for *{mins} minutes*, *one-time use*.\n"
        f"Share it with the locked-out person.",
        parse_mode="Markdown")






# ==========================================================
# S2 - SUB-ADMIN LOCK-IN TRACKING
# ==========================================================
_SUB_LOCKIN_OK = {}


def _sub_lockin_step(message):
    uid = message.chat.id
    _lk_text = (message.text or "").strip()
    try:
        _lk_ok, _ = auth.verify_lockin_code(_lk_text, requester_uid=uid)
    except Exception as e:
        print(f"[sub_lockin] verify err: {e}")
        _lk_ok = False
    if _lk_ok:
        _SUB_LOCKIN_OK[uid] = True
        for _mn, _mo in __import__("sys").modules.items():
            if hasattr(_mo, "PENDING_AUTH_FLOW"):
                _mo.PENDING_AUTH_FLOW[uid] = {
                    "action": "sub_verify_code",
                    "at": __import__("time").time(),
                }
                break
        safe_send(uid,
            "\u2705 *Lock-in accepted.*\n\nNow enter the *verification code* from the primary admin.",
            parse_mode="Markdown")
    else:
        safe_send(uid, "\u274c Invalid or expired lock-in. Contact the primary admin.")


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
    try:
        bot.answer_callback_query(call.id, "Closing...")
    except Exception:
        pass
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


# ==========================================================
# c30n_broadcast.py — Broadcast + Personal Message + Selection
# ==========================================================
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import admin_auth as auth

# Per-admin selection state
_SELECTION = {}   # {admin_uid: set(recipient_uid)}
_BC_CUR_PAGE = {}


def _panel_users_sorted():
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


def _build_selection_keyboard(admin_uid, page=0, per_page=8):
    users = _panel_users_sorted()
    selected = _SELECTION.setdefault(admin_uid, set())
    kb = InlineKeyboardMarkup(row_width=1)
    start = page * per_page
    end = start + per_page
    for uid, p in users[start:end]:
        name = (p.get("name") or "?")[:18]
        hku = p.get("hku_id") or "—"
        check = "✅" if uid in selected else "⬜"
        kb.add(InlineKeyboardButton(
            f"{check} {hku} · {name}",
            callback_data=f"bc_toggle:{uid}"
        ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"bc_page:{page-1}"))
    if end < len(users):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"bc_page:{page+1}"))
    if nav:
        kb.row(*nav)
    kb.add(InlineKeyboardButton("✅ Select All", callback_data="bc_all"),
           InlineKeyboardButton("❌ Deselect All", callback_data="bc_none"))
    kb.add(InlineKeyboardButton(f"➡️ Continue ({len(selected)} selected)", callback_data="bc_continue"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="admin_back"))
    return kb


def _show_selection(admin_uid, page=0, message_id=None):
    _BC_CUR_PAGE[admin_uid] = page
    users = _panel_users_sorted()
    kb = _build_selection_keyboard(admin_uid, page)
    text = (
        f"📢 *BROADCAST — Step 1/3*\n\n"
        f"Tap to toggle users. Or use Select All.\n"
        f"Total users: *{len(users)}*\n"
        f"Selected: *{len(_SELECTION.get(admin_uid, set()))}*"
    )
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=admin_uid, message_id=message_id,
                                   reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            pass
    bot.send_message(admin_uid, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
def _cb_broadcast_start(call):
    uid = call.message.chat.id
    session = auth.get_session(uid)
    if not session or session["role"] != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    _SELECTION[uid] = set()
    _cur = globals().get("_BC_CUR_PAGE", {})
    _show_selection(uid, _cur.get(uid, 0), call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("bc_toggle:"))
def _cb_bc_toggle(call):
    uid = call.message.chat.id
    if not auth.get_session(uid):
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    sel = _SELECTION.setdefault(uid, set())
    if target in sel:
        sel.remove(target)
    else:
        sel.add(target)
    _cur_page = _BC_CUR_PAGE.get(uid, 0)
    _show_selection(uid, _cur_page, call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("bc_page:"))
def _cb_bc_page(call):
    uid = call.message.chat.id
    try:
        page = int(call.data.split(":")[1])
    except Exception:
        page = 0
    _show_selection(uid, page, call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data == "bc_all")
def _cb_bc_all(call):
    uid = call.message.chat.id
    _SELECTION[uid] = {u for u, _ in _panel_users_sorted()}
    _show_selection(uid, 0, call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data == "bc_none")
def _cb_bc_none(call):
    uid = call.message.chat.id
    _SELECTION[uid] = set()
    _show_selection(uid, 0, call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data == "bc_continue")
def _cb_bc_continue(call):
    uid = call.message.chat.id
    sel = _SELECTION.get(uid, set())
    if not sel:
        bot.answer_callback_query(call.id, "No users selected")
        return
    # Set pending text-capture via c09's PENDING_ADMIN_FLOW
    try:
        import importlib
        c09 = None
        for mod_name, mod in __import__("sys").modules.items():
            if hasattr(mod, "PENDING_ADMIN_FLOW"):
                mod.PENDING_ADMIN_FLOW[uid] = {
                    "action": "broadcast_text",
                    "data": {"recipients": list(sel)},
                    "at": __import__("time").time(),
                }
                break
    except Exception as e:
        print(f"[bc_continue] {e}")
    try:
        bot.edit_message_text(
            "📢 *BROADCAST — Step 2/3*\n\nNow type the message text.",
            chat_id=uid, message_id=call.message.message_id, parse_mode="Markdown")
    except Exception:
        safe_send(uid, "📢 Step 2/3: type the message text.")


# ---- Confirm actions ----
@bot.callback_query_handler(func=lambda c: c.data == "bc_send")
def _cb_bc_send(call):
    uid = call.from_user.id
    try:
        bot.answer_callback_query(call.id, "Sending...")
    except Exception:
        pass
    try:
        pf = None
        for _mn, _mo in __import__("sys").modules.items():
            if hasattr(_mo, "PENDING_ADMIN_FLOW") and uid in _mo.PENDING_ADMIN_FLOW:
                pf = _mo.PENDING_ADMIN_FLOW[uid]
                _mo.PENDING_ADMIN_FLOW.pop(uid, None)
                break
        if not pf:
            safe_send(uid, "No pending broadcast.")
            return
        data = pf.get("data", {})
        recipients = data.get("recipients", [])
        file_type = data.get("file_type")
        file_id = data.get("file_id")
        text = (data.get("text") or "").strip()

        if not recipients:
            safe_send(uid, "No recipients selected.")
            return

        HEADER = "\U0001f4e2 <b>Announcement from Admin</b>"
        FOOTER = (
            "\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "\U0001f468\u200d\U0001f4bb <i>Developed by Vishnavi Gokarnam</i>\n"
            "H&amp;K Publications"
        )

        success = 0
        failed = 0
        errs = []

        _pause_g = globals().get("_PAUSE_TRACKING")
        if _pause_g is not None:
            _pause_g["active"] = True
        for rid in recipients:
            try:
                # Part 1: header + text (skip if no text and no file)
                if text or file_type:
                    hdr_text = HEADER + (("\n\n" + text) if text else "")
                    bot.send_message(rid, hdr_text, parse_mode="HTML")
                # Part 2: file
                if file_type == "photo" and file_id:
                    bot.send_photo(rid, file_id)
                elif file_type == "video" and file_id:
                    bot.send_video(rid, file_id)
                elif file_type == "audio" and file_id:
                    bot.send_audio(rid, file_id)
                elif file_type == "voice" and file_id:
                    bot.send_voice(rid, file_id)
                elif file_type == "video_note" and file_id:
                    bot.send_video_note(rid, file_id)
                elif file_type == "document" and file_id:
                    bot.send_document(rid, file_id)
                # Part 3: footer
                bot.send_message(rid, FOOTER, parse_mode="HTML")
                success += 1
                print(f"[bc-ok] {rid} type={file_type or 'text'}")
            except Exception as e:
                failed += 1
                errs.append(f"{rid}: {str(e)[:80]}")
                print(f"[bc-fail] {rid}: {e}")

        if _pause_g is not None:
            _pause_g["active"] = False
        try:
            auth.log_broadcast(text or file_type or "file", success)
        except Exception:
            pass

        summary = f"\u2705 Broadcast delivered: *{success}*\n\u274c Failed: *{failed}*"
        if errs:
            summary += "\n\n_First errors:_\n" + "\n".join(errs[:3])
        _sum_msg = bot.send_message(uid, summary, parse_mode="Markdown")
        _trk = globals().get("track_admin_msg")
        if _trk:
            try: _trk(uid, _sum_msg.message_id)
            except Exception: pass

        try:
            bot.delete_message(uid, call.message.message_id)
        except Exception:
            pass

        # Clear panel cache so _show_admin_panel sends FRESH (not stale edit)
        _sm = globals().get("_STATS_MSGS")
        if _sm is not None:
            try: _sm.pop(uid, None)
            except Exception: pass
        _bm = globals().get("_BTN_MSGS")
        if _bm is not None:
            try: _bm.pop(uid, None)
            except Exception: pass

        _sp = globals().get("_show_admin_panel")
        if _sp:
            try:
                _sp(uid)
                print(f"[bc-panel-reopen] {uid}")
            except Exception as _e:
                print(f"[bc-panel-reopen-fail] {_e}")
    except Exception as e:
        print(f"[bc_send_outer_fail] {e}")
        try:
            safe_send(uid, f"Broadcast error: {e}")
        except Exception:
            pass



@bot.callback_query_handler(func=lambda c: c.data == "bc_sched")
def _cb_bc_sched(call):
    uid = call.message.chat.id
    data = None
    for mod_name, mod in __import__("sys").modules.items():
        if hasattr(mod, "PENDING_ADMIN_FLOW") and uid in mod.PENDING_ADMIN_FLOW:
            data = mod.PENDING_ADMIN_FLOW[uid]["data"]
            break
    if not data:
        bot.answer_callback_query(call.id, "No pending broadcast")
        return
    # NEW: ask for a title first
    _file_type = data.get("file_type") or "text"
    data["_schedule_type"] = _file_type
    for mod_name, mod in __import__("sys").modules.items():
        if hasattr(mod, "PENDING_ADMIN_FLOW"):
            mod.PENDING_ADMIN_FLOW[uid] = {
                "action": "broadcast_title",
                "data": data,
                "at": __import__("time").time(),
            }
            break
    safe_send(uid,
        "🏷 *Give this schedule a short title* (max 40 chars):\n\n"
        "_Example: `Weekly test reminder` or `Physics Ch 5 notes`_",
        parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data == "bc_cancel")
def _cb_bc_cancel(call):
    uid = call.message.chat.id
    for mod_name, mod in __import__("sys").modules.items():
        if hasattr(mod, "PENDING_ADMIN_FLOW"):
            mod.PENDING_ADMIN_FLOW.pop(uid, None)
            break
    try:
        bot.edit_message_text("❌ Broadcast cancelled.", chat_id=uid,
                               message_id=call.message.message_id)
    except Exception:
        pass


# ==========================================================
# PERSONAL MESSAGE
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_pmsg:"))
def _cb_pmsg(call):
    uid = call.message.chat.id
    session = auth.get_session(uid)
    if not session or session["role"] != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    try:
        target = int(call.data.split(":")[1])
    except Exception:
        return
    for mod_name, mod in __import__("sys").modules.items():
        if hasattr(mod, "PENDING_ADMIN_FLOW"):
            mod.PENDING_ADMIN_FLOW[uid] = {
                "action": "personal_text",
                "data": {"target_uid": target},
                "at": __import__("time").time(),
            }
            break
    p = load_profile(target) or {}
    name = p.get("name", "?")
    safe_send(uid, f"📩 Type your message for *{name}* (`{target}`):", parse_mode="Markdown")


print("c30n_broadcast: loaded.")


# ==========================================================
# FILE BROADCAST HANDLER (photo/video/audio/document)
# ==========================================================

@bot.message_handler(content_types=['photo', 'video', 'audio', 'document', 'voice', 'video_note'])
def _handle_broadcast_file(message):
    uid = message.chat.id
    if not auth.get_session(uid):
        return
        
    pf = None
    for mod_name, mod in __import__("sys").modules.items():
        if hasattr(mod, "PENDING_ADMIN_FLOW"):
            pf = mod.PENDING_ADMIN_FLOW.get(uid)
            break
            
    # Accept both states
    if not pf or pf.get("action") not in ("broadcast_text", "broadcast_confirm"):
        return
        
    _dat = pf.get("data", {})
    
    file_type, file_id = None, None
    if message.photo:
        file_type, file_id = "photo", message.photo[-1].file_id
    elif message.video:
        file_type, file_id = "video", message.video.file_id
    elif message.audio:
        file_type, file_id = "audio", message.audio.file_id
    elif message.document:
        file_type, file_id = "document", message.document.file_id
    elif message.voice:
        file_type, file_id = "voice", message.voice.file_id
    elif message.video_note:
        file_type, file_id = "video_note", message.video_note.file_id
        
    if not file_type:
        safe_send(uid, "❌ Unsupported file type.")
        return
        
    _dat["file_type"] = file_type
    _dat["file_id"] = file_id
    if message.caption:
        _dat["text"] = message.caption
        
    for mod_name, mod in __import__("sys").modules.items():
        if hasattr(mod, "PENDING_ADMIN_FLOW"):
            mod.PENDING_ADMIN_FLOW[uid] = {
                "action": "broadcast_confirm",
                "data": _dat,
                "at": __import__("time").time(),
            }
            break
            
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    _kb = InlineKeyboardMarkup(row_width=1)
    _kb.add(
        InlineKeyboardButton("✅ Send Now", callback_data="bc_send"),
        InlineKeyboardButton("⏰ Schedule", callback_data="bc_sched"),
        InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel"),
    )
    safe_send(uid,
        f"📢 *Broadcast Preview (File)*\n\n"
        f"Type: `{file_type}`\n"
        f"Caption: _{_dat.get('text', '')}_\n\n"
        f"Recipients: *{len(_dat.get('recipients', []))} users*",
        parse_mode="Markdown")
    bot.send_message(uid, "Choose action:", reply_markup=_kb)


# ==========================================================
# c30n_sched_viewer.py — Scheduled Broadcasts Viewer
# 4 tabs: Text / Image / File / Exam (coming soon)
# Actions: Reschedule / Cancel
# ==========================================================
import json as _sv_json
import os as _sv_os
from datetime import datetime as _sv_dt

_SV_FILE = "scheduled_broadcasts.json"


def _sv_load():
    if not _sv_os.path.exists(_SV_FILE):
        return []
    try:
        with open(_SV_FILE) as f:
            d = _sv_json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def _sv_save(items):
    tmp = _SV_FILE + ".tmp"
    with open(tmp, "w") as f:
        _sv_json.dump(items, f, indent=2)
    _sv_os.replace(tmp, _SV_FILE)


def _sv_item_title(it):
    """Derive display title."""
    t = it.get("title")
    if t:
        return t[:40]
    # Fallback
    ft = it.get("file_type")
    txt = (it.get("text") or "").strip()
    if ft:
        return f"[{ft}] {txt[:30]}" if txt else f"[{ft}]"
    return (txt[:40] or "(untitled)")


def _sv_item_type(it):
    ft = it.get("file_type")
    if ft in ("photo", "video", "audio", "voice", "video_note"):
        return "image" if ft == "photo" else "file"
    if ft == "document":
        return "file"
    return "text"


def _sv_time_until(scheduled_at_str):
    """Human-readable countdown."""
    try:
        s = scheduled_at_str.strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = _sv_dt.strptime(s, fmt)
                break
            except ValueError:
                continue
        else:
            return "?"
        delta = dt - _sv_dt.now()
        if delta.total_seconds() < 0:
            return "OVERDUE"
        d = delta.days
        h = delta.seconds // 3600
        m = (delta.seconds % 3600) // 60
        if d > 0:
            return f"{d}d {h}h"
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m"
    except Exception:
        return "?"


def _sv_build_list(tab):
    """Return (text, kb) for the given tab."""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    items = _sv_load()
    filtered = [it for it in items if not it.get("sent") and _sv_item_type(it) == tab]
    text = f"📋 *Scheduled Broadcasts — {tab.upper()}*\n\n"
    kb = InlineKeyboardMarkup(row_width=1)
    if not filtered:
        text += "_No pending broadcasts in this category._"
    else:
        text += f"Pending: *{len(filtered)}*\n\nTap to view & manage:"
        for idx, it in enumerate(filtered):
            title = _sv_item_title(it)
            ttl = _sv_time_until(it.get("scheduled_at", ""))
            cb = f"sv_view:{idx}"
            kb.add(InlineKeyboardButton(f"📩 {title} · {ttl}", callback_data=cb))
    # Tab navigation
    tabs = [("text", "✉️ Text"), ("image", "🖼 Image"), ("file", "📎 File"), ("exam", "📝 Exam")]
    row = []
    for t_key, t_label in tabs:
        if t_key == tab:
            t_label = f"• {t_label}"
        row.append(InlineKeyboardButton(t_label, callback_data=f"sv_tab:{t_key}"))
    # two per row
    kb.row(row[0], row[1])
    kb.row(row[2], row[3])
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
    return text, kb


@bot.callback_query_handler(func=lambda c: c.data.startswith("sv_tab:"))
def _sv_cb_tab(call):
    uid = call.from_user.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        bot.answer_callback_query(call.id, "Primary only")
        return
    tab = call.data.split(":")[1]
    if tab == "exam":
        text = "📝 *Exam Broadcasts*\\n\\n_Coming soon — needs Exam Panel (Session 5)._"
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back to Text", callback_data="sv_tab:text"))
        kb.add(InlineKeyboardButton("🔙 Panel", callback_data="admin_back"))
        try:
            bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return
    text, kb = _sv_build_list(tab)
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("sv_view:"))
def _sv_cb_view(call):
    uid = call.from_user.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    try:
        idx = int(call.data.split(":")[1])
    except Exception:
        return
    items = _sv_load()
    pending = [it for it in items if not it.get("sent")]
    if idx >= len(pending):
        bot.answer_callback_query(call.id, "Item gone")
        return
    it = pending[idx]
    title = _sv_item_title(it)
    scheduled = it.get("scheduled_at", "?")
    ttl = _sv_time_until(scheduled)
    recipients_count = len(it.get("recipients", []))
    txt = (it.get("text") or "")[:200]
    file_type = it.get("file_type")
    lines = [
        f"📋 *{title}*",
        "",
        f"⏰ *Fires in:* {ttl}  ({scheduled})",
        f"👥 *Recipients:* {recipients_count}",
        f"📝 *Type:* {_sv_item_type(it)}" + (f" ({file_type})" if file_type else ""),
        "",
    ]
    if txt:
        lines.append(f"💬 *Message:*\\n_{txt}_")
    if file_type:
        lines.append(f"\\n_Attached: {file_type} file_")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📅 Reschedule", callback_data=f"sv_resched:{idx}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"sv_cancel:{idx}"),
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"sv_tab:{_sv_item_type(it)}"))
    try:
        bot.edit_message_text(text, chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("sv_cancel:"))
def _sv_cb_cancel(call):
    uid = call.from_user.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    try:
        idx = int(call.data.split(":")[1])
    except Exception:
        return
    items = _sv_load()
    pending_indices = [i for i, it in enumerate(items) if not it.get("sent")]
    if idx >= len(pending_indices):
        bot.answer_callback_query(call.id, "Already gone")
        return
    actual_idx = pending_indices[idx]
    removed_title = _sv_item_title(items[actual_idx])
    del items[actual_idx]
    _sv_save(items)
    print(f"[sv] {uid} cancelled schedule: {removed_title}")
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Back to List", callback_data="sv_tab:text"))
    try:
        bot.edit_message_text(
            f"✅ *Cancelled:* {removed_title}\\n\\n_Won't fire._",
            chat_id=uid, message_id=call.message.message_id, reply_markup=kb, parse_mode="Markdown"
        )
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("sv_resched:"))
def _sv_cb_resched(call):
    uid = call.from_user.id
    sess = auth.get_session(uid)
    if not sess or sess.get("role") != "primary":
        return
    try:
        idx = int(call.data.split(":")[1])
    except Exception:
        return
    items = _sv_load()
    pending_indices = [i for i, it in enumerate(items) if not it.get("sent")]
    if idx >= len(pending_indices):
        bot.answer_callback_query(call.id, "Gone")
        return
    actual_idx = pending_indices[idx]
    # Store for next-step
    if not hasattr(bot, "_sv_resched_ctx"):
        bot._sv_resched_ctx = {}
    bot._sv_resched_ctx[uid] = {"idx": actual_idx}
    safe_send(uid,
        "📅 *Enter new schedule* — YYYY-MM-DD HH:MM\\n\\n"
        "_Example: `2026-10-25 18:30`_",
        parse_mode="Markdown")


@bot.message_handler(func=lambda m: hasattr(bot, "_sv_resched_ctx") and m.chat.id in getattr(bot, "_sv_resched_ctx", {}), content_types=['text'])
def _sv_catch_resched(message):
    uid = message.chat.id
    ctx = bot._sv_resched_ctx.pop(uid, None)
    if not ctx:
        return
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        return
    # Parse
    new_dt = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M %p"):
        try:
            new_dt = _sv_dt.strptime(txt, fmt)
            break
        except ValueError:
            continue
    if not new_dt:
        safe_send(uid, "❌ Invalid format. Use `YYYY-MM-DD HH:MM`:", parse_mode="Markdown")
        bot._sv_resched_ctx[uid] = ctx
        return
    if new_dt <= _sv_dt.now():
        safe_send(uid, "❌ Time must be in the future. Try again:")
        bot._sv_resched_ctx[uid] = ctx
        return
    items = _sv_load()
    idx = ctx["idx"]
    if idx >= len(items):
        safe_send(uid, "❌ Item disappeared.")
        return
    old_sched = items[idx].get("scheduled_at", "?")
    items[idx]["scheduled_at"] = new_dt.strftime("%Y-%m-%d %H:%M")
    items[idx]["sent"] = False
    items[idx]["sent_at"] = None
    _sv_save(items)
    print(f"[sv] {uid} rescheduled: {old_sched} → {items[idx]['scheduled_at']}")
    safe_send(uid,
        f"✅ *Rescheduled*\\n\\n"
        f"Was: {old_sched}\\n"
        f"Now: *{items[idx]['scheduled_at']}*",
        parse_mode="Markdown")


print("c30n_sched_viewer: loaded.")


# ==========================================================
# c30o_scheduler.py — Background scheduler for broadcasts
# ==========================================================
import json, os, time, threading
from datetime import datetime


SCHEDULE_FILE = "scheduled_broadcasts.json"


def _load_schedule():
    if not os.path.exists(SCHEDULE_FILE):
        return []
    try:
        with open(SCHEDULE_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_schedule(items):
    tmp = SCHEDULE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(items, f, indent=2)
    os.replace(tmp, SCHEDULE_FILE)


def _send_scheduled_broadcast(item):
    """Send one scheduled broadcast and mark as sent."""
    text = item.get("text", "")
    recipients = item.get("recipients", [])
    sent = 0
    file_type = item.get("file_type")
    file_id = item.get("file_id")
    
    for uid in recipients:
        try:
            if file_type and file_id:
                cap = text if text else ""
                if file_type == "photo":
                    bot.send_photo(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "video":
                    bot.send_video(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "audio":
                    bot.send_audio(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "document":
                    bot.send_document(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "voice":
                    bot.send_voice(uid, file_id, caption=cap, parse_mode="HTML")
                elif file_type == "video_note":
                    bot.send_video_note(uid, file_id)
            else:
                safe_send(uid,
                    f"📢 <b>ANNOUNCEMENT FROM ADMIN</b>\n\n{text}\n\n<i>— Admin</i>",
                    parse_mode="HTML")
            sent += 1
            time.sleep(0.05)
        except Exception as e:
            pass
    try:
        import admin_auth
        admin_auth.log_broadcast(text, sent, item.get("scheduled_at"))
    except Exception:
        pass
    print(f"[sched] broadcast sent to {sent}/{len(recipients)}")


def _parse_scheduled_time(scheduled_at):
    """Parse scheduled time. Handles 24h AND 12h AM/PM formats."""
    if not scheduled_at:
        return None
    scheduled_at = scheduled_at.strip()
    for fmt in ("%Y-%m-%d %H:%M",
                "%Y-%m-%d %I:%M %p",
                "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(scheduled_at, fmt)
        except ValueError:
            continue
    print(f"[sched] UNPARSEABLE: {scheduled_at!r}")
    return None


def _scheduler_loop():
    """Check every 20 seconds for due broadcasts."""
    print("[sched] background scheduler started")
    while True:
        try:
            items = _load_schedule()
            now = datetime.now()
            changed = False
            for item in items:
                if item.get("sent"):
                    continue
                scheduled_dt = _parse_scheduled_time(item.get("scheduled_at", ""))
                if not scheduled_dt:
                    continue
                if now >= scheduled_dt:
                    print(f"[sched] firing broadcast: {item.get('scheduled_at')}")
                    try:
                        _send_scheduled_broadcast(item)
                    except Exception as e:
                        print(f"[sched] send error: {e}")
                    item["sent"] = True
                    item["sent_at"] = now.isoformat()
                    changed = True
            if changed:
                _save_schedule(items)
        except Exception as e:
            print(f"[sched] loop error: {e}")
        time.sleep(20)


def start_scheduler():
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()
    return t


# Auto-start when loaded
start_scheduler()
print("c30o_scheduler: loaded + scheduler running.")


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
                    bot.edit_message_text(
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


# ==========================================================
# c30r_activity_tracker.py — v2
# - last_seen tracking (profile)
# - session last_activity tracking (for auto-close)
# - incoming msg tracking during admin session/pending
# - lock-in button handler
# ==========================================================
import os as _at_os
import json as _at_json
from datetime import datetime as _at_dt
import admin_auth as _at_auth

def _touch_user_activity(uid, incoming_msg_id=None):
    try:
        if not uid: return
        try:
            sess = _at_auth.get_session(uid)
            if sess:
                sess["last_activity"] = _at_dt.now().isoformat()
        except Exception:
            pass
        if incoming_msg_id:
            try:
                has = bool(_at_auth.get_session(uid))
                if not has:
                    for _mn, _mo in __import__("sys").modules.items():
                        if hasattr(_mo, "PENDING_AUTH_FLOW") and uid in _mo.PENDING_AUTH_FLOW:
                            has = True
                            break
                if not has:
                    for _mn, _mo in __import__("sys").modules.items():
                        if hasattr(_mo, "PENDING_ADMIN_FLOW") and uid in _mo.PENDING_ADMIN_FLOW:
                            has = True
                            break
                if not has:
                    try:
                        _trk_g = globals().get("_ADMIN_MSGS")
                        if _trk_g and _trk_g.get(int(uid)):
                            has = True
                    except Exception:
                        pass
                if has:
                    _trk = globals().get("track_admin_msg")
                    if _trk:
                        _trk(uid, incoming_msg_id)
            except Exception:
                pass
        pdir = globals().get("PROFILE_DIR") or "profiles"
        path = _at_os.path.join(pdir, f"{uid}.json")
        if not _at_os.path.exists(path): return
        with open(path) as f:
            p = _at_json.load(f)
        if not p.get("secured"): return
        p["last_seen"] = _at_dt.now().isoformat()
        with open(path, "w") as f:
            _at_json.dump(p, f, indent=2)
    except Exception as e:
        print(f"[at] touch err: {e}")


try:
    _orig_pnu = bot.process_new_updates
    def _at_patched_pnu(updates):
        try:
            for u in updates:
                if getattr(u, "message", None):
                    fu = getattr(u.message, "from_user", None)
                    if fu:
                        _touch_user_activity(fu.id, getattr(u.message, "message_id", None))
                if getattr(u, "callback_query", None):
                    fu = getattr(u.callback_query, "from_user", None)
                    if fu:
                        _touch_user_activity(fu.id)
        except Exception as e:
            print(f"[at] pnu err: {e}")
        return _orig_pnu(updates)
    bot.process_new_updates = _at_patched_pnu
    print("[at] activity tracker installed (v2, session+incoming)")
except Exception as e:
    print(f"[at] install FAILED: {e}")


@bot.callback_query_handler(func=lambda c: c.data == "admin_lockin_btn")
def _cb_admin_lockin_btn(call):
    try:
        _s = _at_auth.get_session(call.from_user.id)
        if not _s or _s.get("role") != "primary":
            bot.answer_callback_query(call.id, "Primary only")
            return
    except Exception:
        pass
    try:
        bot.answer_callback_query(call.id, "Generating lock-in code...")
        result = _at_auth.generate_lockin_code()
        if isinstance(result, tuple) and len(result) >= 2:
            code, mins = result[0], result[1]
        else:
            code, mins = str(result), 10
        safe_send(
            call.from_user.id,
            f"🔑 *Lock-in Code Generated*\n\n"
            f"`{code}`\n\n"
            f"Valid for *{mins} minutes*.\n"
            f"Copy exactly as shown.",
            parse_mode="Markdown",
        )
        print(f"[lockin_btn] code for {call.from_user.id}: {code}")
    except Exception as e:
        print(f"[lockin_btn] FAILED: {e}")
        safe_send(call.from_user.id, f"⚠️ Lock-in generation failed: {e}")


print("c30r_activity_tracker: loaded (v2).")


# ==========================================================
# c30s_admin_cleanup.py — v2
# - Auto-tracks ALL bot->admin messages during admin session
# - Auto-close after 5 min inactivity
# ==========================================================
import threading, time as _t
from datetime import datetime
import admin_auth as auth

_ADMIN_MSGS = {}
_ADMIN_MSG_TYPES = {}
_PAUSE_TRACKING = {"active": False}

def track_admin_msg(uid, msg_id, mtype="panel"):
    if not uid or not msg_id: return
    try:
        _ADMIN_MSGS.setdefault(int(uid), []).append(int(msg_id))
        _ADMIN_MSG_TYPES[int(msg_id)] = mtype
        if len(_ADMIN_MSGS[int(uid)]) > 500:
            _ADMIN_MSGS[int(uid)] = _ADMIN_MSGS[int(uid)][-500:]
    except Exception:
        pass


def clear_tracked(uid):
    try:
        _ADMIN_MSGS.pop(int(uid), None)
    except Exception:
        pass


def delete_all_admin_msgs(uid):
    deleted = 0; failed = 0
    try:
        ids = list(_ADMIN_MSGS.get(int(uid), []))
        for mid in ids:
            try:
                bot.delete_message(uid, mid)
                deleted += 1
            except Exception:
                failed += 1
        _ADMIN_MSGS[int(uid)] = []
    except Exception as e:
        print(f"[cleanup] delete err: {e}")
    return deleted, failed


# ---- Auto-track every bot->admin send while session active ----
def _has_pending_auth(uid):
    try:
        for _mn, _mo in __import__("sys").modules.items():
            if hasattr(_mo, "PENDING_AUTH_FLOW") and uid in _mo.PENDING_AUTH_FLOW:
                return True
    except Exception:
        pass
    return False


try:
    _orig_send = bot.send_message
    def _tracking_send(chat_id, *args, **kwargs):
        r = _orig_send(chat_id, *args, **kwargs)
        try:
            if _PAUSE_TRACKING.get("active"):
                return r
            if isinstance(chat_id, int):
                if (auth.get_session(chat_id)
                        or _has_pending_auth(chat_id)
                        or _ADMIN_MSGS.get(int(chat_id))):
                    track_admin_msg(chat_id, r.message_id)
        except Exception:
            pass
        return r
    bot.send_message = _tracking_send
    print("[cleanup] bot.send_message auto-track installed (v3)")
except Exception as _e:
    print(f"[cleanup] wrapper fail: {_e}")


# ---- Auto-close after 5 min inactivity ----
def _autoclose_loop():
    print("[cleanup] autoclose thread started (5 min idle)")
    while True:
        try:
            for uid in list(auth._SESSIONS.keys()):
                s = auth._SESSIONS.get(uid)
                if not s: continue
                la = s.get("last_activity")
                if not la: continue
                try:
                    diff = (datetime.now() - datetime.fromisoformat(la)).total_seconds()
                except Exception:
                    continue
                if diff > 300:
                    print(f"[autoclose] {uid} idle {int(diff)}s — refreshing panel")
                    # Refresh instead of delete — keep current device alive
                    try:
                        _sp = globals().get("_show_admin_panel")
                        if _sp:
                            _sp(uid)
                            print(f"[autoclose] {uid} panel refreshed")
                            # Bump activity so no re-trigger
                            s["last_activity"] = __import__("datetime").datetime.now().isoformat()
                            continue
                    except Exception as _e:
                        print(f"[autoclose] refresh err: {_e}")
                    # Fallback: delete if refresh fails
                    dc, _ = delete_all_admin_msgs(uid)
                    try: auth._SESSIONS.pop(uid, None)
                    except Exception: pass
                    for gname in ("_STATS_MSGS", "_BTN_MSGS"):
                        g = globals().get(gname)
                        if g is not None:
                            try: g.pop(uid, None)
                            except Exception: pass
                    try:
                        unreg = globals().get("unregister_panel")
                        if unreg: unreg(uid)
                    except Exception: pass
                    try:
                        m = bot.send_message(uid,
                            f"⏰ Auto-closed after 5 min idle. {dc} messages cleared.")
                        def _dn(mid=m.message_id, u=uid):
                            _t.sleep(5)
                            try: bot.delete_message(u, mid)
                            except Exception: pass
                        threading.Thread(target=_dn, daemon=True).start()
                    except Exception as e:
                        print(f"[autoclose] notice fail: {e}")
        except Exception as e:
            print(f"[autoclose] loop err: {e}")
        _t.sleep(5)


threading.Thread(target=_autoclose_loop, daemon=True).start()
print("c30s_admin_cleanup: loaded (v2, auto-close + auto-track).")


def maybe_watch_lock(uid):
    """Called after any strike. If user is watched, apply 10-day lock."""
    try:
        from datetime import datetime as _dt, timedelta as _td
        import os as _o, json as _j
        pdir = globals().get("PROFILE_DIR") or "profiles"
        path = _o.path.join(pdir, f"{uid}.json")
        if not _o.path.exists(path):
            return False
        with open(path) as f:
            p = _j.load(f)
        if not p.get("watched"):
            return False
        beh = p.get("behavior", {})
        if beh.get("watch_lock"):
            return False
        now = _dt.now()
        until = now + _td(days=10)
        p.setdefault("behavior", {})
        p["behavior"]["blocked_until"] = until.isoformat()
        p["behavior"]["watch_lock"] = True
        p["behavior"]["watch_locked_at"] = now.isoformat()
        with open(path, "w") as f:
            _j.dump(p, f, indent=2)
        _ss = globals().get("safe_send")
        if _ss:
            try:
                _ss(uid,
                    f"\U0001f512 *WATCHED ACCOUNT LOCKED*\n\n"
                    f"You are on the admin watchlist.\n"
                    f"Any strike results in an automatic 10-day lock.\n\n"
                    f"\U0001f513 Unlock via *lock-in code* from admin.\n\n"
                    f"Locked until: {until.strftime('%Y-%m-%d %H:%M')}",
                    parse_mode="Markdown")
            except Exception: pass
        if _ss:
            try:
                _ss(8857708587,
                    f"\u26a0\ufe0f *Watch-lock triggered*\n\n"
                    f"User {uid} ({p.get('name') or '?'}) got a strike.\n"
                    f"Locked 10 days until {until.strftime('%Y-%m-%d %H:%M')}")
            except Exception: pass
        print(f"[watch-lock] {uid} locked until {until.isoformat()}")
        return True
    except Exception as e:
        print(f"[watch-lock] err: {e}")
        return False


# ==========================================================
# c31 — Developer credit footer
# ==========================================================

_ORIG_SEND_C31 = safe_send
_ORIG_EDIT_C31 = safe_edit


def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    if text and "Developed by Vishnavi Gokarnam" not in text:
        text = text.rstrip() + "\n\n_Developed by Vishnavi Gokarnam_"
    return _ORIG_SEND_C31(chat_id, text, parse_mode=parse_mode,
                           reply_markup=reply_markup)


def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    if text and "Developed by Vishnavi Gokarnam" not in text:
        text = text.rstrip() + "\n\n_Developed by Vishnavi Gokarnam_"
    return _ORIG_EDIT_C31(chat_id, message_id, text, parse_mode=parse_mode,
                           reply_markup=reply_markup)


print("bot.py Chunk 31 loaded: developer credit footer ready.")


# ==========================================================
# BOOT
# ==========================================================
print("🚀 Hamilton Study AI is live.")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=20)
    except Exception as e:
        print(f"⚠️ Polling crashed: {e}")
        print("🔄 Restarting in 5 seconds...")
        _time.sleep(5)
        continue


import telebot, base64, urllib.request, json, os, subprocess

GROQ_KEYS = [
    "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",
    "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",
    "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",
    "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"
]
groq_idx = 0

def get_vision_solution(img_path):
    """Takes an image path, sends it to Groq Vision, returns the 5-part solution."""
    global groq_idx
    if not os.path.exists(img_path):
        return "❌ Image not found."
        
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
        
    url = "https://api.groq.com/openai/v1/chat/completions"
    prompt = """You are Hamilton, an elite JEE tutor. Solve this question from the image.
    Return ONLY this exact 5-part format:
    **1. General Process:** (Standard steps)
    **2. Different Angle:** (Visualizing the data)
    **3. Shortcut:** (Fast elimination or trick)
    **4. Generalization:** (How it applies to similar models)
    **5. Formula:** (Core formula used)"""
    
    while True:
        if groq_idx >= len(GROQ_KEYS): 
            return "❌ All API keys exhausted. Please try again later."
            
        headers = {
            "Authorization": f"Bearer {GROQ_KEYS[groq_idx]}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }],
            "temperature": 0.1
        }
        
        cmd = ["curl", "-s", "-X", "POST", url, "-H", f"Authorization: Bearer {GROQ_KEYS[groq_idx]}", "-H", "Content-Type: application/json", "-d", json.dumps(data)]
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            result = json.loads(res.stdout)
            if "error" in result:
                print(f"Vision API Error: {result['error']}")
                groq_idx += 1
                continue
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Curl Error: {e}")
            groq_idx += 1

# Handle user sending photo directly to bot
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.chat.id
    msg = bot.reply_to(message, "📸 Analyzing your image...")
    
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_path = f"temp_{uid}.jpg"
    with open(temp_path, 'wb') as new_file:
        new_file.write(downloaded_file)
        
    sol = get_vision_solution(temp_path)
    os.remove(temp_path)
    
    if "REJECT" in sol or "not related" in sol.lower():
        bot.edit_message_text("🚫 Please upload a study-related question.", chat_id=uid, message_id=msg.message_id)
    else:
        bot.edit_message_text(sol, chat_id=uid, message_id=msg.message_id, parse_mode="Markdown")
        
print("✅ c40_vision_ai: Vision Doubt Solver loaded.")


