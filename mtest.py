import telebot
bot = telebot.TeleBot("8014117557:AAHWS65NsCbzu205NUFnKt2VbqQ-K36lLVs")
CHAT_ID = 8857708587

test = (
    "**Matrix test**\n\n"
    "Real LaTeX matrix:\n"
    "$$A = \\begin{bmatrix} 1 & 2 \\\\ 3 & 4 \\end{bmatrix}$$\n\n"
    "Unicode matrix:\n"
    "```\n"
    "⎡ 1  2 ⎤\n"
    "⎣ 3  4 ⎦\n"
    "```\n\n"
    "Inline: $\\theta + \\pi$\n"
)

try:
    rm = telebot.types.InputRichMessage(markdown=test)
    result = bot.send_rich_message(chat_id=CHAT_ID, rich_message=rm)
    print("SENT OK. msg_id:", result.message_id)
except Exception as e:
    print("FAIL:", type(e).__name__, e)
