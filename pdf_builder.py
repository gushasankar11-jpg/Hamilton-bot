# ==========================================================
# pdf_builder.py — v4 premium layout engine
# - Consistent page numbering (header == footer)
# - Three coloured panels (concept / trap / key equation)
# - Larger reserved diagram areas
# ==========================================================
import os, re, hashlib
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from matplotlib import use as _mpl_use
_mpl_use("Agg")
from matplotlib.mathtext import math_to_image
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
from PIL import Image

FONT_PATH = "DejaVuSans.ttf"
PDF_OUT   = "pdf_out"
TMP_DIR   = "pdf_tmp"

MARGIN     = 14
CONTENT_W  = 210 - 2*MARGIN
PAGE_H     = 297
HEADER_H   = 12
FOOTER_Y   = PAGE_H - 8

# Fonts (pt)
SZ_COVER   = 28
SZ_H1      = 17
SZ_H2      = 13
SZ_H3      = 11
SZ_BODY    = 10.5
SZ_TABLE   = 9.5
SZ_FOOTER  = 8.5
SZ_KEYEQ   = 14
SZ_LEGEND  = 9

# Line heights (mm)
LH_BODY    = 5.4
LH_H1      = 10
LH_H2      = 8
LH_H3      = 6.5
LH_TABLE   = 5.0
BLOCK_GAP  = 3.5

# Colors
NAVY       = (28, 54, 122)
NAVY_DK    = (20, 40, 95)
PALE_BLUE  = (222, 233, 248)
GREEN_BG   = (228, 244, 230)
GREEN_LINE = (90, 168, 100)
AMBER_BG   = (253, 244, 220)
AMBER_LINE = (210, 160, 40)
BODY_TEXT  = (24, 24, 28)
MUTED      = (110, 118, 130)
RULE       = (200, 210, 225)
WHITE      = (255, 255, 255)

DIAGRAM_HEIGHTS = {
    "glucose_haworth":  78,
    "glucose_chain":    50,
    "fructose":         78,
    "peptide_bond":     42,
    "alpha_helix":      85,
    "beta_sheet":       48,
    "dna_helix":        95,
}
DEFAULT_DIAGRAM_H = 70

# ---------- LaTeX → Unicode ----------
_INLINE_MAP = [
    (r"\times","×"),(r"\cdot","·"),(r"\div","÷"),
    (r"\pm","±"),(r"\mp","∓"),(r"\leq","≤"),(r"\geq","≥"),
    (r"\neq","≠"),(r"\approx","≈"),(r"\equiv","≡"),
    (r"\propto","∝"),(r"\infty","∞"),
    (r"\alpha","α"),(r"\beta","β"),(r"\gamma","γ"),
    (r"\delta","δ"),(r"\epsilon","ε"),(r"\varepsilon","ε"),
    (r"\theta","θ"),(r"\lambda","λ"),(r"\mu","μ"),
    (r"\nu","ν"),(r"\pi","π"),(r"\rho","ρ"),
    (r"\sigma","σ"),(r"\tau","τ"),(r"\phi","φ"),
    (r"\omega","ω"),(r"\Delta","Δ"),(r"\Omega","Ω"),
    (r"\rightarrow","→"),(r"\to","→"),(r"\leftarrow","←"),
    (r"\Rightarrow","⇒"),(r"\Leftrightarrow","⇔"),
]
_SUB = {"0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅","6":"₆","7":"₇","8":"₈","9":"₉","n":"ₙ","x":"ₓ","i":"ᵢ"}
_SUP = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷","8":"⁸","9":"⁹","n":"ⁿ","+":"⁺","-":"⁻"}

def inline_unicode(text):
    for a, b in _INLINE_MAP:
        text = text.replace(a, b)
    for _ in range(4):
        text = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", text)
    for cmd in ["text","mathrm","mathbf","mathit","textbf"]:
        text = re.sub(r"\\" + cmd + r"\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"_\{([0-9nxi]+)\}", lambda m: "".join(_SUB.get(c, c) for c in m.group(1)), text)
    text = re.sub(r"_([0-9nxi])", lambda m: _SUB.get(m.group(1), m.group(1)), text)
    text = re.sub(r"\^\{([0-9n+\-]+)\}", lambda m: "".join(_SUP.get(c, c) for c in m.group(1)), text)
    text = re.sub(r"\^([0-9n])", lambda m: _SUP.get(m.group(1), m.group(1)), text)
    text = text.replace("$", "").replace("{", "").replace("}", "")
    return text

def _clean_md_inline(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text

def _esc(s):
    return s.replace("—", "-").replace("–", "-").replace("’", "'")

# ---------- Formula renderer ----------
def render_formula(tex, out_path, dpi=280):
    try:
        math_to_image(tex, out_path, dpi=dpi, format="png")
        return os.path.exists(out_path) and os.path.getsize(out_path) > 100
    except Exception as e:
        print(f"[formula] fail: {e}")
        return False

# ---------- Diagram renderer ----------
def _save(fig, out):
    fig.tight_layout()
    fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return os.path.exists(out) and os.path.getsize(out) > 500

def _ring(ax, center, radius, sides=6, start_angle=np.pi/6, lw=2.2, color="k"):
    """Draw a regular polygon ring, return vertex list."""
    cx, cy = center
    angles = np.linspace(0, 2*np.pi, sides+1)[:sides] + start_angle
    xs = cx + radius * np.cos(angles)
    ys = cy + radius * np.sin(angles)
    ax.plot(list(xs) + [xs[0]], list(ys) + [ys[0]], color=color, lw=lw)
    return list(zip(xs, ys))

def diagram_glucose_haworth(out):
    fig, ax = plt.subplots(figsize=(5.5, 4.6))
    # Ring: oxygen at top-right, standard Haworth hexagon
    r = 1.0
    angles = np.deg2rad([30, 90, 150, 210, 270, 330])
    xs = r * np.cos(angles)
    ys = r * np.sin(angles)
    ax.plot(list(xs) + [xs[0]], list(ys) + [ys[0]], color="black", lw=2.4)
    # Ring oxygen at position 30° (top right)
    ax.text(xs[0]+0.18, ys[0]+0.12, "O", fontsize=15, fontweight="bold", color="#b22222")
    # Carbon positions (C1..C5 counterclockwise)
    ax.text(xs[1]+0.15, ys[1]+0.12, "C5", fontsize=9, color="#333")
    ax.text(xs[2]-0.35, ys[2]+0.12, "C4", fontsize=9, color="#333")
    ax.text(xs[3]-0.35, ys[3]-0.28, "C3", fontsize=9, color="#333")
    ax.text(xs[4]-0.15, ys[4]-0.28, "C2", fontsize=9, color="#333")
    ax.text(xs[5]+0.15, ys[5]-0.28, "C1", fontsize=9, color="#333", fontweight="bold")
    # Substituent labels
    ax.text(xs[1]-0.55, ys[1]+0.15, "CH₂OH", fontsize=10)
    ax.text(xs[2]-0.75, ys[2]+0.15, "OH", fontsize=10)
    ax.text(xs[3]-0.55, ys[3]-0.15, "OH", fontsize=10)
    ax.text(xs[4]+0.10, ys[4]-0.30, "OH", fontsize=10)
    # Anomeric OH down (α)
    ax.text(xs[5]+0.28, ys[5]-0.35, "OH (α↓)", fontsize=10, color="#b22222")
    ax.text(0, -1.85, "α-D-Glucopyranose (Haworth projection)", ha="center", fontsize=10.5, style="italic")
    ax.set_xlim(-2, 2); ax.set_ylim(-2.1, 1.6); ax.axis("off")
    return _save(fig, out)

def diagram_glucose_chain(out):
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    labels = ["CHO", "H–C–OH", "HO–C–H", "H–C–OH", "H–C–OH", "CH₂OH"]
    for i, lab in enumerate(labels):
        y = 5 - i
        ax.text(1.2, y, lab, fontsize=11, family="monospace")
        if i < len(labels)-1:
            ax.plot([1.6, 1.6], [y-0.22, y-0.78], 'k-', lw=0.8)
    # Numbering C1..C6
    for i in range(6):
        y = 5 - i
        ax.text(0.5, y, f"C{i+1}", fontsize=9, color="#666")
    ax.text(3.3, 2.5, "Open-chain\n(Fischer projection)", fontsize=10, style="italic", color="#333")
    ax.set_xlim(0, 5.8); ax.set_ylim(0, 5.8); ax.axis("off")
    return _save(fig, out)

def diagram_fructose(out):
    fig, ax = plt.subplots(figsize=(5.5, 4.6))
    r = 1.0
    angles = np.deg2rad([90, 162, 234, 306, 18])
    xs = r * np.cos(angles); ys = r * np.sin(angles)
    ax.plot(list(xs) + [xs[0]], list(ys) + [ys[0]], color="black", lw=2.4)
    ax.text(xs[0]+0.10, ys[0]+0.15, "O", fontsize=15, fontweight="bold", color="#b22222")
    ax.text(xs[0]+0.28, ys[0]+0.55, "CH₂OH", fontsize=10)
    ax.text(xs[1]-0.75, ys[1]+0.10, "OH", fontsize=10)
    ax.text(xs[2]-0.65, ys[2]-0.15, "OH", fontsize=10)
    ax.text(xs[3]+0.10, ys[3]-0.28, "CH₂OH", fontsize=10)
    ax.text(0, -1.7, "α-D-Fructofuranose (Haworth)", ha="center", fontsize=10.5, style="italic")
    ax.set_xlim(-2, 2); ax.set_ylim(-1.9, 1.8); ax.axis("off")
    return _save(fig, out)

def diagram_peptide_bond(out):
    fig, ax = plt.subplots(figsize=(6.5, 2.1))
    ax.text(0.2, 0.5, "H₂N", fontsize=11)
    ax.text(0.7, 0.55, "CH", fontsize=11)
    ax.text(0.65, 0.85, "R₁", fontsize=10)
    ax.plot([1.05, 1.6], [0.6, 0.6], 'k-', lw=1.6)
    ax.text(1.7, 0.55, "C", fontsize=11)
    ax.plot([1.95, 1.95], [0.7, 0.95], 'k-', lw=1.6)
    ax.text(1.90, 0.98, "O", fontsize=11, color="#b22222")
    ax.text(1.7, 0.20, "N", fontsize=11, color="#1f77b4")
    ax.text(1.6, 0.05, "H", fontsize=10)
    ax.plot([1.95, 2.5], [0.28, 0.28], 'k-', lw=1.6)
    ax.text(2.55, 0.22, "CH", fontsize=11)
    ax.text(2.45, 0.55, "R₂", fontsize=10)
    ax.plot([2.95, 3.4], [0.28, 0.28], 'k-', lw=1.6)
    ax.text(3.45, 0.22, "COOH", fontsize=11)
    ax.annotate("peptide bond", xy=(1.85, 0.55), xytext=(1.85, -0.15),
                arrowprops=dict(arrowstyle="->", lw=0.9), fontsize=10, ha="center")
    ax.set_xlim(0, 4.4); ax.set_ylim(-0.4, 1.3); ax.axis("off")
    return _save(fig, out)

def diagram_alpha_helix(out):
    fig, ax = plt.subplots(figsize=(3.2, 5.5))
    t = np.linspace(0, 6*np.pi, 500)
    x = np.cos(t); y = t
    ax.plot(x, y, color="#1f77b4", lw=2.6)
    # R-groups as small dots
    for i in range(0, len(t), 60):
        ax.plot(x[i], y[i], 'o', color="#d62728", markersize=6)
    ax.text(0, 6*np.pi + 1.5, "α-Helix", ha="center", fontsize=11, style="italic")
    ax.text(0, 6*np.pi + 0.5, "(red dots = R groups)", ha="center", fontsize=8.5, color="#666")
    ax.axis("off")
    return _save(fig, out)

def diagram_beta_sheet(out):
    fig, ax = plt.subplots(figsize=(6, 2.2))
    for idx, y in enumerate([0.55, -0.55]):
        x = np.linspace(0, 5.5, 200)
        ax.plot(x, y + 0.11*np.sin(x*4.2), 'k-', lw=2)
        ax.annotate("", xy=(4.8, y), xytext=(4.3, y),
                    arrowprops=dict(arrowstyle="-|>", lw=2))
    ax.annotate("", xy=(0.5, 0.20), xytext=(0.5, -0.20),
                arrowprops=dict(arrowstyle="<->", lw=0.8, color="#666"))
    ax.text(0.65, 0, "H-bonds", fontsize=8.5, color="#666")
    ax.text(2.75, 1.25, "β-Pleated Sheet", ha="center", fontsize=11, style="italic")
    ax.set_xlim(-0.4, 6); ax.set_ylim(-1.3, 1.6); ax.axis("off")
    return _save(fig, out)

def diagram_dna_helix(out):
    fig, ax = plt.subplots(figsize=(3.5, 6))
    t = np.linspace(0, 6*np.pi, 600)
    x1 = np.sin(t); x2 = np.sin(t + np.pi); y = t
    ax.plot(x1, y, color="#d62728", lw=2.2)
    ax.plot(x2, y, color="#1f77b4", lw=2.2)
    for i in range(0, len(t), 20):
        ax.plot([x1[i], x2[i]], [y[i], y[i]], color="#555", lw=0.5, alpha=0.4)
    ax.text(0, 6*np.pi + 1.8, "DNA Double Helix", ha="center", fontsize=11, style="italic")
    ax.text(0, 6*np.pi + 0.7, "(red A-T | blue G-C)", ha="center", fontsize=8.5, color="#666")
    ax.axis("off")
    return _save(fig, out)

DIAGRAM_LIB = {
    "glucose_haworth": diagram_glucose_haworth,
    "glucose_chain":   diagram_glucose_chain,
    "fructose":        diagram_fructose,
    "peptide_bond":    diagram_peptide_bond,
    "alpha_helix":     diagram_alpha_helix,
    "beta_sheet":      diagram_beta_sheet,
    "dna_helix":       diagram_dna_helix,
}

def render_diagram(kind, out_path):
    fn = DIAGRAM_LIB.get(kind)
    if not fn:
        return False
    try:
        return fn(out_path)
    except Exception as e:
        print(f"[diagram] {kind} fail: {e}")
        plt.close("all")
        return False

# ---------- MD parser ----------
_DIAGRAM_RE = re.compile(r"\[DIAGRAM:\s*([a-zA-Z_]+)\s*\]")
_KEY_RE     = re.compile(r"\[KEY:\s*(.+?)\s*\|\s*(.+?)\s*\]$")
_CONCEPT_RE = re.compile(r"\[CONCEPT:\s*(.+?)\s*\|\s*(.+?)\s*\]$")
_TRAP_RE    = re.compile(r"\[TRAP:\s*(.+?)\s*\]$")

def parse_md(md_text):
    lines = md_text.split("\n")
    elements = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        s = line.strip()
        if not s:
            i += 1; continue
        # Panels
        m = _KEY_RE.match(s)
        if m:
            elements.append(("key", m.group(1).strip(), m.group(2).strip()))
            i += 1; continue
        m = _CONCEPT_RE.match(s)
        if m:
            elements.append(("concept", m.group(1).strip(), m.group(2).strip()))
            i += 1; continue
        m = _TRAP_RE.match(s)
        if m:
            elements.append(("trap", m.group(1).strip()))
            i += 1; continue
        m = _DIAGRAM_RE.search(s)
        if m:
            elements.append(("diagram", m.group(1)))
            i += 1; continue
        # Table
        if s.startswith("|") and s.endswith("|"):
            tbl = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl.append(lines[i].strip()); i += 1
            elements.append(("table", tbl)); continue
        # Headings
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            elements.append(("h", level, s[level:].strip())); i += 1; continue
        # Formula
        if s.startswith("$") and s.endswith("$") and s.count("$") == 2 and len(s) > 3:
            elements.append(("formula", s[1:-1].strip())); i += 1; continue
        # Bullet
        if s.startswith(("- ", "* ", "• ")):
            elements.append(("bullet", s[2:].strip())); i += 1; continue
        # Rule
        if set(s) <= set("-*_ "):
            elements.append(("hr",)); i += 1; continue
        elements.append(("para", s)); i += 1
    return elements

# ---------- Layout engine ----------
class Doc:
    def __init__(self, pdf, chapter_title):
        self.pdf = pdf
        self.chapter = chapter_title
        self.interior_pages = []   # list of page numbers (fpdf page index)
        self.current_interior = 0

    def new_page(self):
        self.pdf.add_page()
        self.current_interior += 1
        self.interior_pages.append(self.pdf.page)
        # Draw header (will be re-drawn at end for correct numbers)
        self._draw_header()
        self.pdf.set_xy(MARGIN, HEADER_H + 4)

    def _draw_header(self):
        pdf = self.pdf
        pdf.set_fill_color(*NAVY)
        pdf.rect(0, 0, 210, HEADER_H, "F")
        pdf.set_text_color(*WHITE)
        pdf.set_font("DejaVu", size=SZ_FOOTER)
        pdf.set_xy(MARGIN, 3.5)
        pdf.cell(120, 5, _esc(self.chapter)[:70], align="L")
        pdf.set_xy(210 - MARGIN - 40, 3.5)
        pdf.cell(40, 5, f"Page {self.current_interior}", align="R")
        pdf.set_text_color(*BODY_TEXT)

    def y(self):
        return self.pdf.get_y()

    def space_left(self):
        return PAGE_H - FOOTER_Y + 3 - self.pdf.get_y()

    def require(self, h):
        if self.space_left() < h:
            self.new_page()

    def x(self, val=MARGIN):
        self.pdf.set_x(val)

# ---------- Element renderers ----------
def _h(doc, level, text):
    pdf = doc.pdf
    text = inline_unicode(_clean_md_inline(text))
    if level == 1:
        doc.require(LH_H1 + BLOCK_GAP + 3)
        y0 = doc.y()
        pdf.set_fill_color(*NAVY)
        pdf.rect(MARGIN, y0, CONTENT_W, LH_H1, "F")
        pdf.set_text_color(*WHITE)
        pdf.set_font("DejaVu", size=SZ_H1)
        pdf.set_xy(MARGIN + 3, y0 + 1.8)
        pdf.cell(CONTENT_W - 6, LH_H1 - 2, _esc(text),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_xy(MARGIN, y0 + LH_H1 + BLOCK_GAP)
        pdf.set_text_color(*BODY_TEXT)
    elif level == 2:
        doc.require(LH_H2 + BLOCK_GAP)
        y0 = doc.y()
        pdf.set_fill_color(*PALE_BLUE)
        pdf.rect(MARGIN, y0, CONTENT_W, LH_H2, "F")
        pdf.set_text_color(*NAVY)
        pdf.set_font("DejaVu", size=SZ_H2)
        pdf.set_xy(MARGIN + 3, y0 + 1.4)
        pdf.cell(CONTENT_W - 6, LH_H2 - 2, _esc(text),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_xy(MARGIN, y0 + LH_H2 + BLOCK_GAP)
        pdf.set_text_color(*BODY_TEXT)
    else:
        doc.require(LH_H3 + 2)
        pdf.set_text_color(*NAVY)
        pdf.set_font("DejaVu", size=SZ_H3)
        pdf.set_x(MARGIN)
        pdf.multi_cell(CONTENT_W, LH_H3, "▸ " + _esc(text),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*BODY_TEXT)
        pdf.ln(BLOCK_GAP - 1.5)


def _measure(pdf, text, size, lh, w):
    pdf.set_font("DejaVu", size=size)
    lines = pdf.multi_cell(w, lh, _esc(text), split_only=True, output="LINES")
    return max(1, len(lines)) * lh


def _bullet(doc, text):
    pdf = doc.pdf
    text = inline_unicode(_clean_md_inline(text))
    w = CONTENT_W - 5
    need = _measure(pdf, "• " + text, SZ_BODY, LH_BODY, w)
    doc.require(need)
    pdf.set_text_color(*BODY_TEXT)
    pdf.set_font("DejaVu", size=SZ_BODY)
    pdf.set_x(MARGIN + 2)
    pdf.multi_cell(w, LH_BODY, "• " + _esc(text),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _para(doc, text):
    pdf = doc.pdf
    text = inline_unicode(_clean_md_inline(text))
    need = _measure(pdf, text, SZ_BODY, LH_BODY, CONTENT_W)
    doc.require(need)
    pdf.set_text_color(*BODY_TEXT)
    pdf.set_font("DejaVu", size=SZ_BODY)
    pdf.set_x(MARGIN)
    pdf.multi_cell(CONTENT_W, LH_BODY, _esc(text),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(BLOCK_GAP - 2)


def _hr(doc):
    doc.require(3)
    pdf = doc.pdf
    pdf.set_draw_color(*RULE)
    pdf.line(MARGIN, doc.y() + 1, 210 - MARGIN, doc.y() + 1)
    pdf.ln(BLOCK_GAP)


def _formula(doc, tex):
    pdf = doc.pdf
    full = "$" + tex + "$"
    h = hashlib.md5(full.encode()).hexdigest()[:10]
    img = f"{TMP_DIR}/f_{h}.png"
    if not render_formula(full, img):
        _para(doc, inline_unicode(full)); return
    doc.require(18)
    try:
        with Image.open(img) as im:
            iw, ih = im.size
        ratio = ih / iw
        target_w = min(130, 40 + len(tex) * 1.2)
        target_h = target_w * ratio
        if target_h > 22:
            target_h = 22
            target_w = target_h / ratio
        x_pos = (210 - target_w) / 2
        y0 = doc.y() + 1.5
        pdf.image(img, x=x_pos, y=y0, w=target_w)
        pdf.set_xy(MARGIN, y0 + target_h + BLOCK_GAP)
    except Exception:
        _para(doc, inline_unicode(full))


def _diagram(doc, kind):
    pdf = doc.pdf
    h = DIAGRAM_HEIGHTS.get(kind, DEFAULT_DIAGRAM_H)
    if doc.space_left() < h + 6:
        doc.new_page()
    img = f"{TMP_DIR}/d_{kind}_{doc.current_interior}.png"
    if not render_diagram(kind, img):
        _para(doc, f"[diagram unavailable: {kind}]"); return
    try:
        with Image.open(img) as im:
            iw, ih = im.size
        ratio = ih / iw
        target_w = CONTENT_W - 6
        target_h = target_w * ratio
        if target_h > h:
            target_h = h
            target_w = target_h / ratio
        x_pos = (210 - target_w) / 2
        y0 = doc.y() + 2
        pdf.set_fill_color(248, 251, 255)
        pdf.set_draw_color(*RULE)
        pdf.rect(MARGIN, y0 - 1, CONTENT_W, target_h + 4, "DF")
        pdf.image(img, x=x_pos, y=y0 + 1.5, w=target_w)
        pdf.set_xy(MARGIN, y0 + target_h + BLOCK_GAP + 1)
    except Exception as e:
        print(f"[diagram img] {e}")
        _para(doc, f"[diagram: {kind}]")


def _table(doc, rows):
    pdf = doc.pdf
    parsed = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    data = [r for r in parsed if not all(set(c) <= set("-: ") for c in r)]
    if not data:
        return
    ncol = max(len(r) for r in data)
    for r in data:
        while len(r) < ncol:
            r.append("")
    col_w = CONTENT_W / ncol

    def row_h(row):
        m = 1
        for c in row:
            pdf.set_font("DejaVu", size=SZ_TABLE)
            ls = pdf.multi_cell(col_w - 3, LH_TABLE,
                                inline_unicode(_clean_md_inline(c)),
                                split_only=True, output="LINES")
            m = max(m, len(ls))
        return m * LH_TABLE + 3

    for idx, row in enumerate(data):
        rh = row_h(row)
        if doc.space_left() < rh + 2:
            doc.new_page()
        y0 = doc.y()
        x0 = MARGIN
        for ci in range(ncol):
            if idx == 0:
                pdf.set_fill_color(*NAVY)
            elif idx % 2 == 0:
                pdf.set_fill_color(245, 248, 252)
            else:
                pdf.set_fill_color(*WHITE)
            pdf.rect(x0 + ci*col_w, y0, col_w, rh, "F")
        pdf.set_draw_color(*RULE)
        pdf.rect(x0, y0, CONTENT_W, rh, "D")
        for ci in range(1, ncol):
            pdf.line(x0 + ci*col_w, y0, x0 + ci*col_w, y0 + rh)
        for ci, c in enumerate(row):
            pdf.set_text_color(*(WHITE if idx == 0 else BODY_TEXT))
            pdf.set_font("DejaVu", size=SZ_TABLE)
            pdf.set_xy(x0 + ci*col_w + 1.5, y0 + 1.5)
            pdf.multi_cell(col_w - 3, LH_TABLE,
                           inline_unicode(_clean_md_inline(c)),
                           new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_xy(MARGIN, y0 + rh)
    pdf.ln(BLOCK_GAP)


def _concept_box(doc, title, bullets_str):
    pdf = doc.pdf
    bullets = [b.strip() for b in bullets_str.split(";;") if b.strip()]
    title = inline_unicode(_clean_md_inline(title))
    pdf.set_font("DejaVu", size=SZ_H3)
    title_h = _measure(pdf, "CONCEPT  " + title, SZ_H3, LH_H3, CONTENT_W - 8)
    bullet_h = 0
    for b in bullets:
        bullet_h += _measure(pdf, "• " + inline_unicode(_clean_md_inline(b)),
                             SZ_BODY, LH_BODY, CONTENT_W - 8)
    total_h = title_h + bullet_h + 6
    if doc.space_left() < total_h + 3:
        doc.new_page()
    y0 = doc.y()
    # Background
    pdf.set_fill_color(*GREEN_BG)
    pdf.set_draw_color(*GREEN_LINE)
    pdf.rect(MARGIN, y0, CONTENT_W, total_h, "DF")
    # Title bar
    pdf.set_fill_color(*GREEN_LINE)
    pdf.rect(MARGIN, y0, CONTENT_W, title_h + 1, "F")
    pdf.set_text_color(*WHITE)
    pdf.set_font("DejaVu", size=SZ_H3)
    pdf.set_xy(MARGIN + 2, y0 + 1)
    pdf.cell(CONTENT_W - 4, title_h - 1, "CONCEPT  " + _esc(title),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    # Bullets
    pdf.set_text_color(*BODY_TEXT)
    pdf.set_font("DejaVu", size=SZ_BODY)
    pdf.set_xy(MARGIN + 3, y0 + title_h + 2.5)
    for b in bullets:
        pdf.set_x(MARGIN + 3)
        pdf.multi_cell(CONTENT_W - 8, LH_BODY,
                       "• " + _esc(inline_unicode(_clean_md_inline(b))),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(MARGIN, y0 + total_h + BLOCK_GAP)


def _trap_box(doc, text):
    pdf = doc.pdf
    text = inline_unicode(_clean_md_inline(text))
    h = _measure(pdf, "⚠  " + text, SZ_BODY, LH_BODY, CONTENT_W - 10) + 4
    if doc.space_left() < h + 3:
        doc.new_page()
    y0 = doc.y()
    pdf.set_fill_color(*AMBER_BG)
    pdf.set_draw_color(*AMBER_LINE)
    pdf.rect(MARGIN, y0, CONTENT_W, h, "DF")
    pdf.set_fill_color(*AMBER_LINE)
    pdf.rect(MARGIN, y0, 2, h, "F")
    pdf.set_text_color(*BODY_TEXT)
    pdf.set_font("DejaVu", size=SZ_BODY)
    pdf.set_xy(MARGIN + 4, y0 + 2)
    pdf.multi_cell(CONTENT_W - 8, LH_BODY, "⚠  " + _esc(text),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(MARGIN, y0 + h + BLOCK_GAP)


def _key_panel(doc, tex, legend_str):
    pdf = doc.pdf
    full = "$" + tex + "$"
    h_tex = hashlib.md5(full.encode()).hexdigest()[:10]
    img = f"{TMP_DIR}/k_{h_tex}.png"
    ok = render_formula(full, img)
    legend_items = [l.strip() for l in legend_str.split(",") if l.strip()]
    legend_h = len(legend_items) * 4.5

    # Reserve area
    panel_h = 20 + legend_h + 4 if ok else 14 + legend_h + 4
    if doc.space_left() < panel_h + 3:
        doc.new_page()
    y0 = doc.y()
    pdf.set_fill_color(*PALE_BLUE)
    pdf.set_draw_color(*NAVY)
    pdf.rect(MARGIN, y0, CONTENT_W, panel_h, "DF")
    # Left accent bar
    pdf.set_fill_color(*NAVY)
    pdf.rect(MARGIN, y0, 3, panel_h, "F")

    y_cursor = y0 + 3
    if ok:
        try:
            with Image.open(img) as im:
                iw, ih = im.size
            ratio = ih / iw
            target_w = min(130, 40 + len(tex) * 1.4)
            target_h = target_w * ratio
            if target_h > 14:
                target_h = 14
                target_w = target_h / ratio
            x_pos = (210 - target_w) / 2
            pdf.image(img, x=x_pos, y=y_cursor, w=target_w)
            y_cursor += target_h + 2
        except Exception:
            pdf.set_font("DejaVu", size=SZ_KEYEQ)
            pdf.set_text_color(*BODY_TEXT)
            pdf.set_xy(MARGIN + 5, y_cursor)
            pdf.multi_cell(CONTENT_W - 10, 6, inline_unicode(full))
            y_cursor += 8
    else:
        pdf.set_font("DejaVu", size=SZ_KEYEQ)
        pdf.set_text_color(*BODY_TEXT)
        pdf.set_xy(MARGIN + 5, y_cursor)
        pdf.multi_cell(CONTENT_W - 10, 6, inline_unicode(full))
        y_cursor += 8

    # Legend
    pdf.set_font("DejaVu", size=SZ_LEGEND)
    pdf.set_text_color(*BODY_TEXT)
    for item in legend_items:
        pdf.set_xy(MARGIN + 6, y_cursor)
        pdf.multi_cell(CONTENT_W - 12, 4.5, "• " + _esc(inline_unicode(item)),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y_cursor += 4.5

    pdf.set_xy(MARGIN, y0 + panel_h + BLOCK_GAP)
    pdf.set_text_color(*BODY_TEXT)


# ---------- Main ----------
def build_pdf_from_md_files(md_files, pdf_path, chapter_title="Hamilton Notes"):
    os.makedirs(PDF_OUT, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(pdf_path) or ".", exist_ok=True)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.add_font("DejaVu", "", FONT_PATH)

    # Cover
    pdf.add_page()
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 100, "F")
    pdf.set_text_color(*WHITE)
    pdf.set_font("DejaVu", size=SZ_COVER)
    pdf.set_xy(MARGIN, 38)
    pdf.multi_cell(180, 14, _esc(chapter_title), align="C",
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", size=11)
    pdf.set_xy(MARGIN, 68)
    pdf.multi_cell(180, 6, "Hamilton Study AI\nby Hemanth and Krishna Publications",
                   align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*BODY_TEXT)

    doc = Doc(pdf, chapter_title)
    doc.new_page()

    for pg_idx, md_path in enumerate(md_files, start=1):
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
        elements = parse_md(md_text)
        if pg_idx > 1:
            doc.require(15)
        for elem in elements:
            k = elem[0]
            if   k == "h":       _h(doc, elem[1], elem[2])
            elif k == "bullet":  _bullet(doc, elem[1])
            elif k == "para":    _para(doc, elem[1])
            elif k == "hr":      _hr(doc)
            elif k == "formula": _formula(doc, elem[1])
            elif k == "diagram": _diagram(doc, elem[1])
            elif k == "table":   _table(doc, elem[1])
            elif k == "concept": _concept_box(doc, elem[1], elem[2])
            elif k == "trap":    _trap_box(doc, elem[1])
            elif k == "key":     _key_panel(doc, elem[1], elem[2])

    # Stamp headers + footers with correct final numbers
    total_interior = len(doc.interior_pages)
    for pno in doc.interior_pages:
        pdf.page = pno
        interior_label = doc.interior_pages.index(pno) + 1
        # Redraw header
        pdf.set_fill_color(*NAVY)
        pdf.rect(0, 0, 210, HEADER_H, "F")
        pdf.set_text_color(*WHITE)
        pdf.set_font("DejaVu", size=SZ_FOOTER)
        pdf.set_xy(MARGIN, 3.5)
        pdf.cell(120, 5, _esc(chapter_title)[:70], align="L")
        pdf.set_xy(210 - MARGIN - 40, 3.5)
        pdf.cell(40, 5, f"Page {interior_label} / {total_interior}", align="R")
        # Footer
        pdf.set_text_color(*MUTED)
        pdf.set_font("DejaVu", size=SZ_FOOTER)
        pdf.set_xy(MARGIN, FOOTER_Y)
        pdf.cell(100, 4, "Hamilton Study AI", align="L")
        pdf.set_xy(210 - MARGIN - 60, FOOTER_Y)
        pdf.cell(60, 4, f"Page {interior_label} / {total_interior}", align="R")

    pdf.output(pdf_path)
    return pdf_path, os.path.getsize(pdf_path)
