# ==========================================================
# formula_renderer.py — LaTeX → PNG via matplotlib
# ==========================================================
import os
import re
import io
import hashlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TEMP = "svg_temp"
os.makedirs(TEMP, exist_ok=True)


LATEX_MARKERS = [
    "\\frac", "\\sqrt", "\\sum", "\\int", "\\omega", "\\theta",
    "\\pi", "\\vec", "\\hat", "\\mathbf", "\\begin", "\\alpha",
    "\\beta", "\\lambda", "\\Delta", "\\Sigma", "\\times", "\\cdot",
    "\\pm", "\\infty", "\\neq", "\\leq", "\\geq", "\\partial",
    "\\nabla", "\\rho", "\\sigma", "\\phi", "\\psi", "\\chi",
    "\\eta", "\\zeta", "\\xi", "\\mu", "\\nu", "\\tau", "\\gamma",
    "\\epsilon", "\\approx", "\\equiv", "\\subset", "\\in", "\\to",
    "\\rightarrow", "\\Rightarrow", "\\leftarrow", "\\leftrightarrow",
    "\\ldots", "\\cdots", "\\therefore", "\\because", "\\implies",
    "$$", "\\[", "\\(",
]


def has_latex(text):
    if not text:
        return False
    return any(m in text for m in LATEX_MARKERS)


def _preprocess_matrix(latex):
    """Convert \\begin{vmatrix|bmatrix|pmatrix|matrix}...end to flat readable form."""
    def repl(m):
        env = m.group(1)
        body = m.group(2)
        rows = [r.strip() for r in re.split(r'\\\\', body) if r.strip()]
        row_strs = []
        for r in rows:
            cells = [c.strip() for c in r.split('&')]
            row_strs.append('  '.join(cells))
        joined = ' ; '.join(row_strs)
        if env == 'vmatrix':
            return '| ' + joined + ' |'
        elif env == 'bmatrix':
            return '[ ' + joined + ' ]'
        elif env == 'pmatrix':
            return '( ' + joined + ' )'
        else:
            return joined
    pattern = r'\\begin\{(vmatrix|bmatrix|pmatrix|matrix)\}(.*?)\\end\{\1\}'
    return re.sub(pattern, repl, latex, flags=re.DOTALL)


def latex_to_png(latex_str):
    """Render LaTeX math string → PNG file path. Returns None on failure."""
    if not latex_str or not latex_str.strip():
        return None
    h = hashlib.md5(latex_str.encode()).hexdigest()[:12]
    path = os.path.join(TEMP, "formula_" + h + ".png")

    # Cleanup: remove alignment environments that matplotlib can't render
    cleaned = latex_str.strip()
    cleaned = _preprocess_matrix(cleaned)
    cleaned = re.sub(r'\\begin\{aligned\}', '', cleaned)
    cleaned = re.sub(r'\\end\{aligned\}', '', cleaned)
    cleaned = re.sub(r'\\begin\{align\}', '', cleaned)
    cleaned = re.sub(r'\\end\{align\}', '', cleaned)
    cleaned = cleaned.replace('&', '')
    cleaned = cleaned.replace('\\\\', ' \\ ')
    cleaned = cleaned.replace("\\displaystyle", "")

    try:
        # Split into lines if multi-line
        lines = [l.strip() for l in re.split(r'\\\\|\n', cleaned) if l.strip()]
        if not lines:
            return None
        n = len(lines)
        fig_h = max(1.0, n * 0.6)
        fig = plt.figure(figsize=(8, fig_h), dpi=150)
        fig.patch.set_facecolor("#0a0a1a")

        for i, line in enumerate(lines):
            y = 1 - (i + 0.5) / n
            fig.text(0.5, y, "$" + line + "$",
                     fontsize=22, color="#ffffff",
                     ha="center", va="center")

        plt.savefig(path, bbox_inches="tight",
                    facecolor="#0a0a1a", edgecolor="none", pad_inches=0.2)
        plt.close(fig)
        if os.path.exists(path) and os.path.getsize(path) > 500:
            return path
        return None
    except Exception as e:
        print("[FORMULA] render failed: " + str(e) + " | source: " + latex_str[:80])
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def extract_math_parts(text):
    """Split text into [('text', str) | ('math', latex)] parts."""
    if not text:
        return []
    pattern = r'(\$\$.+?\$\$|\\\[.+?\\\]|\\\(.+?\\\)|(?<!\$)\$[^\$\n]+?\$(?!\$))'
    parts = re.split(pattern, text, flags=re.DOTALL)
    out = []
    for p in parts:
        if not p:
            continue
        if p.startswith("$$") and p.endswith("$$"):
            out.append(("math", p[2:-2].strip()))
        elif p.startswith("\\[") and p.endswith("\\]"):
            out.append(("math", p[2:-2].strip()))
        elif p.startswith("\\(") and p.endswith("\\)"):
            out.append(("math", p[2:-2].strip()))
        elif p.startswith("$") and p.endswith("$") and len(p) > 2:
            out.append(("math", p[1:-1].strip()))
        else:
            out.append(("text", p))
    return out


if __name__ == "__main__":
    print("formula_renderer.py OK")
    print("has_latex test:", has_latex("Use \\\\frac{a}{b}"))
    p = latex_to_png("\\frac{x^2+4x+9}{y^2+2y+1}")
    print("PNG path:", p)
    p2 = latex_to_png("\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix} = ad - bc")
    print("Matrix PNG:", p2)
