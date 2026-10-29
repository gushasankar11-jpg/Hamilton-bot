import telebot

bot = telebot.TeleBot("8014117557:AAHWS65NsCbzu205NUFnKt2VbqQ-K36lLVs")
CHAT_ID = 8857708587

md = "**Math Test 2**\n\nFraction: $$\\frac{x^2+1}{y^2-1}$$\n\nInline: $\\theta + \\pi$ and $\\sqrt{x^2+y^2}$\n\nDeterminant: $$\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}$$"

try:
    rm = telebot.types.InputRichMessage(markdown=md)
    result = bot.send_rich_message(chat_id=CHAT_ID, rich_message=rm)
    print("SENT OK — check Telegram")
except Exception as e:
    print("FAIL:", type(e).__name__, str(e))
