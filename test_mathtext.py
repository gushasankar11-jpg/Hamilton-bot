import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig = plt.figure(figsize=(8, 3))
fig.patch.set_facecolor("white")
fig.text(0.5, 0.7, r"$\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$", fontsize=22, ha="center")
fig.text(0.5, 0.3, r"$\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}$", fontsize=18, ha="center")
plt.axis("off")
plt.savefig("mathtest.png", dpi=150, bbox_inches="tight", facecolor="white")
print("Saved: mathtest.png")
