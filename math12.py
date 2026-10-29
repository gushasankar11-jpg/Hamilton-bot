import telebot
bot = telebot.TeleBot("8014117557:AAHWS65NsCbzu205NUFnKt2VbqQ-K36lLVs")
CHAT_ID = 8857708587

md = (
    "**HAMILTON MATH RENDER TEST**\n\n"
    "**1. Simple fraction:**\n"
    "$$\\frac{x^2 + 4x + 9}{y^2 + 2y + 1}$$\n\n"
    "**2. Matrix (bmatrix):**\n"
    "$$A = \\begin{bmatrix} 1 & 2 & 3 \\\\ 4 & 5 & 6 \\\\ 7 & 8 & 9 \\end{bmatrix}$$\n\n"
    "**3. Determinant (vmatrix):**\n"
    "$$|B| = \\begin{vmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i \\end{vmatrix}$$\n\n"
    "**4. Summation:**\n"
    "$$\\sum_{i=1}^{n} i^2 = \\frac{n(n+1)(2n+1)}{6}$$\n\n"
    "**5. Infinite series:**\n"
    "$$\\sum_{n=1}^{\\infty} \\frac{1}{n^2} = \\frac{\\pi^2}{6}$$\n\n"
    "**6. Integral:**\n"
    "$$\\int_{0}^{\\infty} e^{-x^2}\\, dx = \\frac{\\sqrt{\\pi}}{2}$$\n\n"
    "**7. Limit:**\n"
    "$$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$$\n\n"
    "**8. Nested fraction + root:**\n"
    "$$\\frac{\\sqrt{a^2 + b^2}}{\\sqrt{c^2 + d^2}}$$\n\n"
    "**9. Binomial:**\n"
    "$$\\binom{n}{r} = \\frac{n!}{r!(n-r)!}$$\n\n"
    "**10. Mixed integral+sum:**\n"
    "$$\\int_{-\\infty}^{\\infty} \\sum_{k=0}^{n} \\frac{e^{ikx}}{k!} \\, dx$$\n\n"
    "**11. Greek + operators:**\n"
    "$\\theta \\times \\tau = \\vec{F} \\cdot \\vec{r} \\approx \\sum \\alpha_i \\beta_j$\n\n"
    "**12. Cases (piecewise):**\n"
    "$$f(x) = \\begin{cases} x^2 & \\text{if } x \\geq 0 \\\\ -x^2 & \\text{if } x < 0 \\end{cases}$$\n"
)

try:
    rm = telebot.types.InputRichMessage(markdown=md)
    result = bot.send_rich_message(chat_id=CHAT_ID, rich_message=rm)
    print("SENT OK. msg_id:", result.message_id)
    print("Check Telegram and reply with which numbers worked.")
except Exception as e:
    print("FAIL:", type(e).__name__, e)
