import sys, telebot
sys.path.insert(0, "/data/data/com.termux/files/home/hamilton")
import ai_client

bot = telebot.TeleBot("8014117557:AAHWS65NsCbzu205NUFnKt2VbqQ-K36lLVs")
CHAT_ID = 8857708587

md = (
    "**HAMILTON MATH TEST (with conversion)**\n\n"
    "**1. Fraction:**\n$$\\frac{x^2+1}{y^2-1}$$\n\n"
    "**2. Matrix:**\n$$A = \\begin{bmatrix} 1 & 2 & 3 \\\\ 4 & 5 & 6 \\\\ 7 & 8 & 9 \\end{bmatrix}$$\n\n"
    "**3. Determinant:**\n$$|B| = \\begin{vmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i \\end{vmatrix}$$\n\n"
    "**4. Sum:**\n$$\\sum_{i=1}^{n} i^2 = \\frac{n(n+1)(2n+1)}{6}$$\n\n"
    "**5. Integral:**\n$$\\int_0^{\\infty} e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$$\n\n"
    "**6. Cases:**\n$$f(x) = \\begin{cases} x^2 & x \\geq 0 \\\\ -x^2 & x < 0 \\end{cases}$$\n"
)

# THE FIX — convert before sending
converted = ai_client.convert_latex_envs(md)

try:
    rm = telebot.types.InputRichMessage(markdown=converted)
    result = bot.send_rich_message(chat_id=CHAT_ID, rich_message=rm)
    print("SENT OK. msg_id:", result.message_id)
except Exception as e:
    print("FAIL:", type(e).__name__, e)
