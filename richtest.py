import telebot

bot = telebot.TeleBot("8014117557:AAHWS65NsCbzu205NUFnKt2VbqQ-K36lLVs")
CHAT_ID = 8857708587

html = "<b>Math Test</b><br><br>Fraction: $$\\frac{x^2+1}{y^2-1}$$<br><br>Inline: $\\theta + \\pi$"

try:
    rm = telebot.types.InputRichMessage(html=html)
    print("Created InputRichMessage")
    result = bot.send_rich_message(chat_id=CHAT_ID, rich_message=rm)
    print("SENT:", result)
except Exception as e:
    print("FAIL:", type(e).__name__, str(e))
