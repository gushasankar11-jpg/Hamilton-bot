import os
import re
import hashlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import mathtext

TEMP = "svg_temp"
os.makedirs(TEMP, exist_ok=True)


def has_latex(text):
    if not text:
        return False
    markers = ["\\frac", "\\sqrt", "\\sum", "\\int", "\\omega",
               "\\theta", "\\pi", "\\vec", "\\hat", "\\mathbf",
               "\\begin", "\\alpha", "\\beta", "\\lambda",
               "\\Delta", "\\Sigma", "$$", "\\[", "\\(",
               "\\times", "\\cdot", "\\pm", "\\infty",
               "\\pm", "\\neq", "\\leq", "\\geq"]
    return any(m in text for m in markers)


def render_latex_block(latex_str):
    """Render a LaTeX math string to PNG. Returns path or None."""
    if not latex_str:
        return None
    try:
        fig = plt.figure(figsize=(8, 1.2), dpi=130)
        fig.patch.set_facecolor("#0a0a1a")
        fig.text(0.5, 0.5, f"${latex_str}$",
                 fontsize=22, color="#ffffff",
                 ha="center", va="center")
        h = hashlib.md5(latex_str.encode()).hexdigest()[:10]
        path = os.path.join(TEMP, f"math_{h}.png")
        plt.savefig(path, bbox_inches="tight",
                    facecolor="#0a0a1a", edgecolor="none")
        plt.close(fig)
        return path
    except Exception as e:
        print(f"[MATH] render failed: {e}")
        return None


def extract_math_blocks(text):
    """Find all $$...$$ and $...$ blocks. Returns list of (latex, type)."""
    blocks = []
    for m in re.finditer(r'\$\$(.+?)\$\$', text, re.DOTALL):
        blocks.append(("block", m.group(1).strip(), m.start(), m.end()))
    for m in re.finditer(r'(?<!\$)\$([^\$\n]+?)\$(?!\$)', text):
        blocks.append(("inline", m.group(1).strip(), m.start(), m.end()))
    blocks.sort(key=lambda x: x[2])
    return blocks
