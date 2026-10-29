# ==========================================================
# timer_manager.py — Hamilton Study AI
# All timers in one place.
# ==========================================================

import time
import threading

THINKING_TIMERS = {}
GENERATING_TIMERS = {}
QUESTION_TIMERS = {}
TEST_TIMERS = {}


# ----------------------------------------------------------
# THINKING TIMER (AI reply)
# ----------------------------------------------------------
def start_thinking_timer(bot, uid, base_msg):
    THINKING_TIMERS[uid] = {"msg_id": None, "start": time.time(), "stop": False}

    def _job():
        try:
            m = bot.send_message(uid, base_msg + "\n\n⏱️ _Thinking for 0s..._",
                                 parse_mode="Markdown")
            THINKING_TIMERS[uid]["msg_id"] = m.message_id
        except Exception:
            return

        last_shown = -1
        while not THINKING_TIMERS.get(uid, {}).get("stop", True):
            el = int(time.time() - THINKING_TIMERS[uid]["start"])
            if el != last_shown:
                last_shown = el
                try:
                    bot.edit_message_text(
                        chat_id=uid, message_id=m.message_id,
                        text=base_msg + f"\n\n⏱️ _Thinking for {el}s..._",
                        parse_mode="Markdown")
                except Exception:
                    pass
            time.sleep(0.5)

    threading.Thread(target=_job, daemon=True).start()


def stop_thinking_timer(uid):
    info = THINKING_TIMERS.get(uid)
    if info:
        # Ensure message was shown for at least 1.5 seconds
        elapsed = time.time() - info.get("start", time.time())
        if elapsed < 1.5:
            time.sleep(1.5 - elapsed)
        info["stop"] = True


def get_thinking_msg_id(uid):
    return THINKING_TIMERS.get(uid, {}).get("msg_id")


# ----------------------------------------------------------
# GENERATING TIMER (before question/notes appear)
# ----------------------------------------------------------
def start_generating_timer(bot, uid, label="question"):
    GENERATING_TIMERS[uid] = {"msg_id": None, "start": time.time(), "stop": False}

    def _job():
        try:
            m = bot.send_message(uid, f"⏱️ Generating {label}... 0s")
            GENERATING_TIMERS[uid]["msg_id"] = m.message_id
        except Exception:
            return

        last_shown = -1
        while not GENERATING_TIMERS.get(uid, {}).get("stop", True):
            el = int(time.time() - GENERATING_TIMERS[uid]["start"])
            if el != last_shown:
                last_shown = el
                try:
                    bot.edit_message_text(
                        chat_id=uid, message_id=m.message_id,
                        text=f"⏱️ Generating {label}... {el}s")
                except Exception:
                    pass
            time.sleep(0.5)

    threading.Thread(target=_job, daemon=True).start()


def stop_generating_timer(bot, uid):
    info = GENERATING_TIMERS.get(uid)
    if not info:
        return
    info["stop"] = True
    mid = info.get("msg_id")
    if mid:
        try:
            bot.delete_message(uid, mid)
        except Exception:
            pass


# ----------------------------------------------------------
# LIVE QUESTION TIMER
# ----------------------------------------------------------
def start_question_timer(bot, uid):
    QUESTION_TIMERS[uid] = {"msg_id": None, "start": time.time(), "stop": False}

    def _job():
        try:
            m = bot.send_message(uid, "⏱️ 0s")
            QUESTION_TIMERS[uid]["msg_id"] = m.message_id
        except Exception:
            return

        last_shown = -1
        while not QUESTION_TIMERS.get(uid, {}).get("stop", True):
            el = int(time.time() - QUESTION_TIMERS[uid]["start"])
            if el != last_shown:
                last_shown = el
                try:
                    bot.edit_message_text(
                        chat_id=uid, message_id=m.message_id,
                        text=f"⏱️ *{el}s* elapsed", parse_mode="Markdown")
                except Exception:
                    pass
            time.sleep(0.5)

    threading.Thread(target=_job, daemon=True).start()


def stop_question_timer(bot, uid):
    info = QUESTION_TIMERS.get(uid)
    if not info:
        return
    info["stop"] = True
    mid = info.get("msg_id")
    if mid:
        try:
            bot.delete_message(uid, mid)
        except Exception:
            pass


def get_question_elapsed(uid):
    info = QUESTION_TIMERS.get(uid)
    if not info:
        return 0
    return time.time() - info["start"]


# ----------------------------------------------------------
# TEST TIMER
# ----------------------------------------------------------
def start_test_timer(bot, uid, total_minutes, on_time_up=None):
    TEST_TIMERS[uid] = {"start": time.time(), "stop": False}

    def _job():
        last5 = -1
        warned = {"half": False, "last_5": False, "last_min": False}

        while not TEST_TIMERS.get(uid, {}).get("stop", True):
            el = (time.time() - TEST_TIMERS[uid]["start"]) / 60
            remain = total_minutes - el

            cur5 = int(el // 5)
            if cur5 != last5 and cur5 > 0 and remain > 5:
                last5 = cur5
                try:
                    bot.send_message(uid, f"⏳ {int(remain)} min left")
                except Exception:
                    pass

            if not warned["half"] and el >= total_minutes / 2:
                try:
                    bot.send_message(uid, f"⏳ Halfway — {int(remain)} min left")
                except Exception:
                    pass
                warned["half"] = True

            if not warned["last_5"] and el >= total_minutes - 5:
                try:
                    bot.send_message(uid, "⚠️ 5 minutes left!")
                except Exception:
                    pass
                warned["last_5"] = True

            if not warned["last_min"] and el >= total_minutes - 1:
                try:
                    bot.send_message(uid, "🔴 1 minute left!")
                except Exception:
                    pass
                warned["last_min"] = True

            if el >= total_minutes:
                try:
                    bot.send_message(uid, "⏰ Time's up. Auto-submitting.")
                except Exception:
                    pass
                if on_time_up:
                    try:
                        on_time_up(uid)
                    except Exception:
                        pass
                return

            time.sleep(20)

    threading.Thread(target=_job, daemon=True).start()


def stop_test_timer(uid):
    if uid in TEST_TIMERS:
        TEST_TIMERS[uid]["stop"] = True


# ----------------------------------------------------------
# STOP ALL
# ----------------------------------------------------------
def stop_all_timers(bot, uid):
    stop_thinking_timer(uid)
    stop_generating_timer(bot, uid)
    stop_question_timer(bot, uid)
    stop_test_timer(uid)


if __name__ == "__main__":
    print("timer_manager.py OK")
    print("Functions: thinking, generating, question, test timers")
