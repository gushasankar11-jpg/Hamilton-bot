# ==========================================================
# rich_converter.py — Markdown + LaTeX → Telegram Rich HTML
# ==========================================================
import re
from telebot.types import InputRichMessage


def _esc_html(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_to_html(text):
    """Convert AI markdown+LaTeX into Telegram rich HTML.
       LaTeX ($...$ or $$...$$) passes through untouched for native render."""
    if not text:
        return ""
    # Extract and protect LaTeX blocks
    slots = []

    def stash(m):
        slots.append(m.group(0))
        return "\x00M" + str(len(slots) - 1) + "\x00"

    text = re.sub(r'\$\$.+?\$\$', stash, text, flags=re.DOTALL)
    text = re.sub(r'(?<!\$)\$[^\$\n]+?\$(?!\$)', stash, text)

    # Escape HTML in the rest
    text = _esc_html(text)

    # Markdown → HTML
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'(?<!\*)\*([^\*\n]+?)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'`([^`\n]+?)`', r'<code>\1</code>', text)
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

    # Newlines → <br>
    text = text.replace('\n', '<br>')

    # Restore LaTeX
    for i, s in enumerate(slots):
        text = text.replace("\x00M" + str(i) + "\x00", s)
    return text


def send_rich(bot, chat_id, text, reply_markup=None):
    """Send text as Telegram rich message. Fallback to plain on failure."""
    if not text:
        return False
    html = md_to_html(text)
    try:
        msg = InputRichMessage(html=html)
        bot.send_rich_message(chat_id=chat_id, rich_message=msg,
                              reply_markup=reply_markup)
        return True
    except Exception as e:
        print("[RICH] failed: " + str(e))
        try:
            bot.send_message(chat_id, text, reply_markup=reply_markup)
            return True
        except Exception:
            return False


if __name__ == "__main__":
    print("rich_converter OK")
    s = "**Torque:** $\\tau = rF\\sin\\theta$ and $$\\frac{a}{b}$$."
    print(md_to_html(s))
