# ==========================================================
# math_image_renderer.py — Convert complex LaTeX to SVG image
# Uses MathJax-like layout logic for matrices and big expressions.
# ==========================================================

import re
import os
from svg_renderer import render_svg


MATRIX_ENVS = ["matrix", "pmatrix", "bmatrix", "vmatrix", "Vmatrix",
               "smallmatrix", "cases", "array", "aligned", "align"]


def has_matrix_env(text):
    if not text:
        return False
    for env in MATRIX_ENVS:
        if f"\\begin{{{env}}}" in text:
            return True
    return False


def _parse_matrix_rows(body):
    """Split matrix body into rows of cells."""
    rows = body.split("\\\\")
    parsed = []
    for row in rows:
        row = row.strip()
        if not row:
            continue
        cells = [c.strip() for c in row.split("&")]
        parsed.append(cells)
    return parsed


def _escape_xml(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def latex_to_svg(latex_text, width=800):
    """
    Minimal LaTeX → SVG renderer for matrices and simple math.
    Returns SVG string.
    """
    # Simple substitutions for common commands
    text = latex_text
    text = text.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    text = text.replace("\\displaystyle", "").replace("\\left", "").replace("\\right", "")
    text = text.replace("\\cdot", "·").replace("\\times", "×")
    text = text.replace("\\sin", "sin").replace("\\cos", "cos").replace("\\tan", "tan")
    text = text.replace("\\theta", "θ").replace("\\alpha", "α").replace("\\beta", "β")
    text = text.replace("\\pi", "π").replace("\\tau", "τ").replace("\\mu", "μ")
    text = text.replace("\\varepsilon", "ε").replace("\\epsilon", "ε")
    text = text.replace("\\infty", "∞").replace("\\int", "∫").replace("\\sum", "Σ")
    text = text.replace("\\sqrt", "√").replace("\\pm", "±")
    text = text.replace("\\rightarrow", "→").replace("\\Rightarrow", "⇒")
    text = text.replace("\\det", "det").replace("\\vec", "")

    # Match matrix environments
    mat_pattern = re.compile(
        r"\\begin\{(" + "|".join(MATRIX_ENVS) + r")\}(.*?)\\end\{\1\}",
        re.DOTALL,
    )

    matches = list(mat_pattern.finditer(text))
    if not matches:
        # No matrix — just return as plain paragraph SVG (won't be used)
        return None

    # Build SVG with each matrix
    parts = []
    parts.append('<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{width}" height="120" viewBox="0 0 {width} 120">')
    parts.append('<rect width="100%" height="100%" fill="#0a0a1a"/>')

    y = 40
    for m in matches:
        env = m.group(1)
        body = m.group(2)
        rows = _parse_matrix_rows(body)

        n_rows = len(rows)
        n_cols = max(len(r) for r in rows) if rows else 1

        cell_w = 60
        cell_h = 32
        pad_left = 30
        mat_w = n_cols * cell_w
        mat_h = n_rows * cell_h

        # Adjust SVG height
        if y + mat_h + 30 > 120:
            h = y + mat_h + 60
            parts[0] = parts[0].replace('height="120"', f'height="{h}"').replace('120" viewBox', f'{h}" viewBox')

        # Left bracket
        bracket_map = {
            "pmatrix": ("(", ")"),
            "bmatrix": ("[", "]"),
            "vmatrix": ("|", "|"),
            "Vmatrix": ("‖", "‖"),
        }
        lb, rb = bracket_map.get(env, ("", ""))

        if lb:
            parts.append(f'<text x="{pad_left - 15}" y="{y + mat_h - 8}" '
                         f'font-size="{mat_h}" font-family="serif" fill="#ffffff">{lb}</text>')
        if rb:
            parts.append(f'<text x="{pad_left + mat_w + 5}" y="{y + mat_h - 8}" '
                         f'font-size="{mat_h}" font-family="serif" fill="#ffffff">{rb}</text>')

        # Cells
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                cell = cell.replace("\\\\", "\\")
                cell = _escape_xml(cell)
                x = pad_left + c * cell_w + cell_w // 2
                yy = y + r * cell_h + cell_h - 8
                parts.append(f'<text x="{x}" y="{yy}" text-anchor="middle" '
                             f'font-size="18" font-family="Arial" fill="#ffffff">{cell}</text>')

        # Position text before matrix (if any)
        pre_text = text[:m.start()].strip()
        if pre_text:
            pre_text = _escape_xml(pre_text[-40:])
            parts.append(f'<text x="{pad_left}" y="{y - 8}" font-size="14" '
                         f'font-family="Arial" fill="#cccccc">{pre_text}</text>')

        y += mat_h + 40

    parts.append('</svg>')
    return "".join(parts)


def render_latex_to_png(latex_text, name="math"):
    """Renders LaTeX (matrix-heavy) to PNG. Returns path or None."""
    svg = latex_to_svg(latex_text)
    if not svg:
        return None
    return render_svg(svg, name=name)


if __name__ == "__main__":
    test = r"Matrix A = \begin{bmatrix} 1 & 2 & 3 \\ 4 & 5 & 6 \\ 7 & 8 & 9 \end{bmatrix}"
    svg = latex_to_svg(test)
    if svg:
        print("✅ SVG generated")
        p = render_svg(svg, name="matrix_test")
        print("PNG:", p)
    else:
        print("❌ Failed")
