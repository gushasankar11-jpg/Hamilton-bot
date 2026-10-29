# Test tg-rich-converter with your bot
import telebot
from tg_rich_converter import to_rich

# Your bot token + chat_id
TOKEN = "8014117557:AAHWS65NsCbzu205NUFnKt2VbqQ-K36lLVs"
CHAT_ID = 8857708587

bot = telebot.TeleBot(TOKEN)

# Test content with heavy LaTeX
test_md = r"""
# Rich Text Test — Torque

Let's see if **math renders perfectly** now.

## Basic inline
Torque is $\tau = r \times F$ and its magnitude is $|\tau| = rF\sin\theta$.

## Display equations
$$\tau = \vec{r} \times \vec{F}$$

$$\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$$

## Matrix / Determinant
$$A = \begin{bmatrix} 1 & 2 & 3 \\ 4 & 5 & 6 \\ 7 & 8 & 9 \end{bmatrix}$$

$$\det(A) = \begin{vmatrix} 1 & 2 \\ 3 & 4 \end{vmatrix} = -2$$

## Fraction
$$\frac{a}{b} = \frac{c}{d} \implies ad = bc$$

## Summation
$$\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}$$

## Table
| Concept | Quick tip |
|---------|-----------|
| Sign convention | Choose +ve direction |
| Couple | $\tau = F \times d$ |
| Equilibrium | $\sum F = 0$ and $\sum \tau = 0$ |

---

If you see **real math** above (not $ these $ symbols), rich text is working.
"""

print("Converting markdown → rich HTML...")
rich_html = to_rich(test_md)
print("Converted. Sending...")

try:
    result = bot.send_rich_message(
        chat_id=CHAT_ID,
        rich_message={"html": rich_html}
    )
    print("✅ Message sent successfully!")
    print("Message ID:", result.message_id)
except Exception as e:
    print(f"❌ Failed: {type(e).__name__}: {e}")
    # Fallback: send as plain text so we at least see raw output
    try:
        bot.send_message(CHAT_ID, test_md)
        print("Fallback: sent raw markdown text.")
    except Exception as e2:
        print(f"Fallback also failed: {e2}")
