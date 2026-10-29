import telebot

bot = telebot.TeleBot("8014117557:AAHWS65NsCbzu205NUFnKt2VbqQ-K36lLVs")
CHAT_ID = 8857708587

# Use raw string to preserve all backslashes exactly
md = r"""**Hamilton Math Render Test**

**1. Simple fraction:**
$$\frac{x^2 + 4x + 9}{y^2 + 2y + 1}$$

**2. Matrix (bmatrix):**
$$A = \begin{bmatrix} 1 & 2 & 3 \\ 4 & 5 & 6 \\ 7 & 8 & 9 \end{bmatrix}$$

**3. Determinant (vmatrix):**
$$|B| = \begin{vmatrix} a & b & c \\ d & e & f \\ g & h & i \end{vmatrix}$$

**4. Complex summation:**
$$\sum_{i=1}^{n} i^2 = \frac{n(n+1)(2n+1)}{6}$$

**5. Infinite series:**
$$\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}$$

**6. Integral:**
$$\int_{0}^{\infty} e^{-x^2}\, dx = \frac{\sqrt{\pi}}{2}$$

**7. Limit:**
$$\lim_{x \to 0} \frac{\sin x}{x} = 1$$

**8. Nested fraction + root:**
$$\frac{\sqrt{a^2 + b^2}}{\sqrt{c^2 + d^2}}$$

**9. Binomial:**
$$\binom{n}{r} = \frac{n!}{r!(n-r)!}$$

**10. Mixed complex:**
$$\int_{-\infty}^{\infty} \sum_{k=0}^{n} \frac{e^{ikx}}{k!} \, dx$$

**11. Greek + operators:**
$\theta \times \tau = \vec{F} \cdot \vec{r} \approx \sum \alpha_i \beta_j$

**12. Piecewise (cases):**
$$f(x) = \begin{cases} x^2 & \text{if } x \geq 0 \\ -x^2 & \text{if } x < 0 \end{cases}$$
"""

try:
    rm = telebot.types.InputRichMessage(markdown=md)
    result = bot.send_rich_message(chat_id=CHAT_ID, rich_message=rm)
    print("✅ SENT — open Telegram and check each item")
except Exception as e:
    print("❌ FAIL:", type(e).__name__, str(e))
