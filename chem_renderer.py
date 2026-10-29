# ==========================================================
# chem_renderer.py — True textbook Haworth projections
# Drawn with matplotlib primitives: polygons, wedges, dashes
# ==========================================================
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyArrowPatch

# Colours from textbook style
C_RING   = "#0a0a0a"      # thick black ring
C_LABEL  = "#1a1a1a"      # atom labels (C, H, O as text)
C_OH     = "#c81e1e"      # red for OH/O
C_NUM    = "#1f4eb8"      # blue carbon numbers
C_UP     = "#0a0a0a"      # up substituent
C_DOWN   = "#0a0a0a"      # down substituent
C_HI     = "#c81e1e"      # highlight (α/β anomeric)

def _save(fig, out):
    fig.tight_layout(pad=0.15)
    fig.savefig(out, dpi=180, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    return os.path.exists(out) and os.path.getsize(out) > 500

def _wedge(ax, base, tip, color=C_UP, width=0.09):
    """Solid filled wedge from base toward tip."""
    bx, by = base; tx, ty = tip
    dx, dy = tx - bx, ty - by
    L = np.hypot(dx, dy)
    if L < 1e-6: return
    ux, uy = dx / L, dy / L
    px, py = -uy, ux   # perpendicular
    ax.add_patch(Polygon(
        [(bx, by),
         (tx + px*width*L*0.5, ty + py*width*L*0.5),
         (tx - px*width*L*0.5, ty - py*width*L*0.5)],
        closed=True, color=color, linewidth=0
    ))

def _hashed(ax, base, tip, color=C_DOWN, n=6, width=0.07):
    """Hashed wedge — series of short lines growing outward."""
    bx, by = base; tx, ty = tip
    dx, dy = tx - bx, ty - by
    L = np.hypot(dx, dy)
    if L < 1e-6: return
    ux, uy = dx / L, dy / L
    px, py = -uy, ux
    for i in range(1, n+1):
        t = i / n
        cx, cy = bx + dx*t, by + dy*t
        w = width * L * t * 0.5
        ax.plot([cx + px*w, cx - px*w], [cy + py*w, cy - py*w],
                color=color, lw=1.6, solid_capstyle="butt")

def _plain(ax, base, tip, color=C_UP, lw=1.6):
    ax.plot([base[0], tip[0]], [base[1], tip[1]], color=color, lw=lw)

def _atom(ax, xy, label, color=C_LABEL, size=11, weight="normal"):
    ax.text(xy[0], xy[1], label, color=color, fontsize=size,
            ha="center", va="center", fontweight=weight)

# ---------- Haworth hexagon (glucose / galactose / mannose) ----------
def draw_haworth_hexagon(ax, alpha=True,
                          c1_substituent="OH",
                          c1_orientation=None,   # "down" (α) or "up" (β)
                          c2="OH-down", c3="OH-up",
                          c4="OH-down", c5_ch2oh="up",
                          anomeric_color=None):
    """
    Standard Haworth hexagon for D-aldohexoses.
    Positions C1..C5 with ring O between C5 and C1.
    """
    # Ring vertices (chemistry convention):
    # C1 right-middle, O top-right, C5 top-left, C4 left, C3 bottom-left, C2 bottom-right
    C1 = (1.30, 0.00)
    O_ring = (0.65, 0.95)
    C5 = (-0.65, 0.95)
    C4 = (-1.30, 0.00)
    C3 = (-0.65, -0.95)
    C2 = (0.65, -0.95)
    ring = [C5, O_ring, C1, C2, C3, C4, C5]

    # Thick outline
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    ax.plot(xs, ys, color=C_RING, lw=3.0, solid_capstyle="round")

    # Bold front edge (C1-C2, C2-C3) — thickest
    ax.plot([C1[0], C2[0]], [C1[1], C2[1]], color=C_RING, lw=4.5, solid_capstyle="round")
    ax.plot([C2[0], C3[0]], [C2[1], C3[1]], color=C_RING, lw=4.5, solid_capstyle="round")

    # Ring O label (replace vertex with "O")
    _atom(ax, O_ring, "O", color=C_OH, size=13, weight="bold")

    # Carbon numbers
    _atom(ax, (C1[0]+0.30, C1[1]+0.28), "1", color=C_NUM, size=9)
    _atom(ax, (C2[0]+0.05, C2[1]-0.25), "2", color=C_NUM, size=9)
    _atom(ax, (C3[0]-0.05, C3[1]-0.25), "3", color=C_NUM, size=9)
    _atom(ax, (C4[0]-0.30, C4[1]+0.28), "4", color=C_NUM, size=9)
    _atom(ax, (C5[0]-0.05, C5[1]+0.25), "5", color=C_NUM, size=9)

    # C5: CH2OH pointing up
    if c5_ch2oh == "up":
        ax.plot([C5[0], C5[0]-0.10], [C5[1], C5[1]+0.55], color=C_RING, lw=1.6)
        ax.plot([C5[0]-0.10, C5[0]+0.35], [C5[1]+0.55, C5[1]+0.55], color=C_RING, lw=1.6)
        _atom(ax, (C5[0]+0.15, C5[1]+0.80), "CH₂OH", color=C_LABEL, size=10)
        _atom(ax, (C5[0]+0.60, C5[1]+0.45), "6", color=C_NUM, size=9)

    # C4: OH down
    if c4 == "OH-down":
        base = C4
        tip = (C4[0]-0.10, C4[1]-0.55)
        _hashed(ax, base, tip)
        _atom(ax, (C4[0]-0.15, C4[1]-0.75), "OH", color=C_OH, size=10)
        _atom(ax, (C4[0]-0.10, C4[1]+0.40), "H", color=C_LABEL, size=10)

    # C3: OH up
    if c3 == "OH-up":
        base = C3
        tip = (C3[0]+0.10, C3[1]+0.55)
        _wedge(ax, base, tip)
        _atom(ax, (C3[0]+0.15, C3[1]+0.75), "OH", color=C_OH, size=10)
        _atom(ax, (C3[0]-0.05, C3[1]-0.40), "H", color=C_LABEL, size=10)

    # C2: OH down
    if c2 == "OH-down":
        base = C2
        tip = (C2[0]+0.10, C2[1]-0.55)
        _hashed(ax, base, tip)
        _atom(ax, (C2[0]+0.15, C2[1]-0.75), "OH", color=C_OH, size=10)
        _atom(ax, (C2[0]-0.10, C2[1]+0.40), "H", color=C_LABEL, size=10)

    # C1: anomeric OH
    if c1_orientation == "down":
        base = C1
        tip = (C1[0]+0.55, C1[1]-0.15)
        _hashed(ax, base, tip)
        hi = anomeric_color or C_HI
        _atom(ax, (C1[0]+0.85, C1[1]-0.20), c1_substituent, color=hi, size=11, weight="bold")
        _atom(ax, (C1[0]+0.55, C1[1]+0.40), "H", color=C_LABEL, size=10)
    elif c1_orientation == "up":
        base = C1
        tip = (C1[0]+0.55, C1[1]+0.15)
        _wedge(ax, base, tip)
        hi = anomeric_color or C_HI
        _atom(ax, (C1[0]+0.85, C1[1]+0.20), c1_substituent, color=hi, size=11, weight="bold")
        _atom(ax, (C1[0]+0.55, C1[1]-0.40), "H", color=C_LABEL, size=10)

    # Clean axes
    ax.set_xlim(-2.1, 2.4)
    ax.set_ylim(-1.8, 1.8)
    ax.axis("off")
    ax.set_aspect("equal")


# ---------- Haworth pentagon (fructose) ----------
def draw_haworth_pentagon(ax, alpha=True,
                           anomeric_color=None):
    """D-fructofuranose Haworth 5-membered ring."""
    O_ring = (0.00, 0.95)
    C2 = (0.95, 0.35)
    C3 = (0.60, -0.75)
    C4 = (-0.60, -0.75)
    C5 = (-0.95, 0.35)
    ring = [C5, O_ring, C2, C3, C4, C5]
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    ax.plot(xs, ys, color=C_RING, lw=3.0, solid_capstyle="round")
    # Bold front edge C3-C4
    ax.plot([C3[0], C4[0]], [C3[1], C4[1]], color=C_RING, lw=4.5)

    _atom(ax, O_ring, "O", color=C_OH, size=13, weight="bold")

    # Carbon numbers
    _atom(ax, (C2[0]+0.25, C2[1]+0.20), "2", color=C_NUM, size=9)
    _atom(ax, (C3[0]+0.10, C3[1]-0.22), "3", color=C_NUM, size=9)
    _atom(ax, (C4[0]-0.10, C4[1]-0.22), "4", color=C_NUM, size=9)
    _atom(ax, (C5[0]-0.25, C5[1]+0.20), "5", color=C_NUM, size=9)

    # C5: CH2OH up-left
    ax.plot([C5[0], C5[0]-0.35], [C5[1], C5[1]+0.55], color=C_RING, lw=1.6)
    _atom(ax, (C5[0]-0.70, C5[1]+0.70), "HOH₂C", color=C_LABEL, size=10)
    # C2: anomeric OH
    if alpha:
        _hashed(ax, C2, (C2[0]+0.15, C2[1]-0.55))
        hi = anomeric_color or C_HI
        _atom(ax, (C2[0]+0.20, C2[1]-0.80), "OH", color=hi, size=10, weight="bold")
        ax.plot([C2[0], C2[0]+0.55], [C2[1], C2[1]+0.10], color=C_RING, lw=1.6)
        _atom(ax, (C2[0]+0.75, C2[1]+0.10), "CH₂OH", color=C_LABEL, size=10)
        _atom(ax, (C2[0]+0.30, C2[1]+0.35), "1", color=C_NUM, size=9)
    else:
        _wedge(ax, C2, (C2[0]+0.15, C2[1]+0.55))
        hi = anomeric_color or C_HI
        _atom(ax, (C2[0]+0.20, C2[1]+0.80), "OH", color=hi, size=10, weight="bold")
        ax.plot([C2[0], C2[0]+0.55], [C2[1], C2[1]-0.15], color=C_RING, lw=1.6)
        _atom(ax, (C2[0]+0.75, C2[1]-0.20), "CH₂OH", color=C_LABEL, size=10)
        _atom(ax, (C2[0]+0.30, C2[1]-0.40), "1", color=C_NUM, size=9)

    # C3: OH down
    _hashed(ax, C3, (C3[0]+0.10, C3[1]-0.55))
    _atom(ax, (C3[0]+0.15, C3[1]-0.75), "OH", color=C_OH, size=10)
    _atom(ax, (C3[0]-0.10, C3[1]+0.35), "H", color=C_LABEL, size=10)

    # C4: OH up
    _wedge(ax, C4, (C4[0]-0.10, C4[1]+0.55))
    _atom(ax, (C4[0]-0.15, C4[1]+0.75), "OH", color=C_OH, size=10)
    _atom(ax, (C4[0]+0.10, C4[1]-0.35), "H", color=C_LABEL, size=10)

    ax.set_xlim(-2.1, 2.4)
    ax.set_ylim(-1.8, 1.8)
    ax.axis("off")
    ax.set_aspect("equal")


# ---------- Public API: single-molecule renders ----------
def chem_glucose_alpha_haworth(out):
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    draw_haworth_hexagon(ax, alpha=True, c1_orientation="down")
    ax.text(0, -1.65, "α-D-Glucopyranose", ha="center", fontsize=11,
            fontweight="bold", color="#203a7a")
    ax.text(0, -1.90, "Anomeric OH at C1 is DOWN", ha="center",
            fontsize=9, style="italic", color="#b03030")
    return _save(fig, out)

def chem_glucose_beta_haworth(out):
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    draw_haworth_hexagon(ax, alpha=False, c1_orientation="up")
    ax.text(0, -1.65, "β-D-Glucopyranose", ha="center", fontsize=11,
            fontweight="bold", color="#203a7a")
    ax.text(0, -1.90, "Anomeric OH at C1 is UP", ha="center",
            fontsize=9, style="italic", color="#b03030")
    return _save(fig, out)

def chem_glucose_pair(out):
    """Side-by-side α + β comparison (matches textbook layout)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2))
    draw_haworth_hexagon(ax1, alpha=True, c1_orientation="down")
    ax1.text(0, -1.75, "α-D-Glucopyranose", ha="center", fontsize=11,
             fontweight="bold", color="#203a7a")
    ax1.text(0, -2.00, "OH at C1: DOWN", ha="center",
             fontsize=9, style="italic", color="#b03030")
    draw_haworth_hexagon(ax2, alpha=False, c1_orientation="up")
    ax2.text(0, -1.75, "β-D-Glucopyranose", ha="center", fontsize=11,
             fontweight="bold", color="#203a7a")
    ax2.text(0, -2.00, "OH at C1: UP", ha="center",
             fontsize=9, style="italic", color="#b03030")
    return _save(fig, out)

def chem_fructose_alpha_haworth(out):
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    draw_haworth_pentagon(ax, alpha=True)
    ax.text(0, -1.60, "α-D-Fructofuranose", ha="center", fontsize=11,
            fontweight="bold", color="#203a7a")
    return _save(fig, out)

def chem_fructose_beta_haworth(out):
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    draw_haworth_pentagon(ax, alpha=False)
    ax.text(0, -1.60, "β-D-Fructofuranose", ha="center", fontsize=11,
            fontweight="bold", color="#203a7a")
    return _save(fig, out)

def chem_glucose_fischer(out):
    """Fischer projection with numbered C atoms, CHO at top."""
    fig, ax = plt.subplots(figsize=(2.6, 4.4))
    # Skeleton: vertical line
    ys = [5, 4, 3, 2, 1, 0]
    ax.plot([1, 1], [ys[-1], ys[0]], color=C_RING, lw=1.8)
    # Top CHO
    ax.text(1, 5.35, "CHO", ha="center", fontsize=11, fontweight="bold")
    # OH / H columns
    row_labels = [
        ("H", "OH"),   # C2
        ("HO", "H"),   # C3
        ("H", "OH"),   # C4
        ("H", "OH"),   # C5
    ]
    for i, (left, right) in enumerate(row_labels):
        y = ys[i+1]
        ax.plot([0.5, 1], [y, y], color=C_RING, lw=1.6)
        ax.plot([1, 1.5], [y, y], color=C_RING, lw=1.6)
        ax.text(0.35, y, left, ha="right", va="center", fontsize=10,
                color=C_OH if left == "HO" or left == "OH" else C_LABEL)
        ax.text(1.65, y, right, ha="left", va="center", fontsize=10,
                color=C_OH if right == "OH" else C_LABEL)
    # Bottom CH2OH
    ax.plot([1, 1], [ys[-1], ys[-1]-0.35], color=C_RING, lw=1.6)
    ax.text(1, ys[-1]-0.60, "CH₂OH", ha="center", fontsize=11, fontweight="bold")
    # Carbon numbers
    for i, y in enumerate(ys[1:], start=2):
        ax.text(0.05, y, f"{i}", ha="right", va="center",
                fontsize=9, color=C_NUM)
    ax.text(1, 5.35+0.0, "", ha="center")
    ax.text(0.05, ys[0], "1", ha="right", va="center", fontsize=9, color=C_NUM)
    ax.text(0.05, ys[-1]-0.60, "6", ha="right", va="center", fontsize=9, color=C_NUM)
    ax.set_xlim(-0.3, 2.3)
    ax.set_ylim(-1.2, 5.9)
    ax.axis("off")
    ax.set_aspect("equal")
    ax.text(1, -1.0, "D-Glucose (Fischer projection)", ha="center",
            fontsize=10, fontweight="bold", color="#203a7a")
    return _save(fig, out)

def chem_sucrose(out):
    """Glucose (pyranose) + Fructose (furanose) linked α1↔β2."""
    fig, ax = plt.subplots(figsize=(8.0, 3.4))
    # Left: glucose ring
    draw_haworth_hexagon(ax, alpha=True, c1_orientation="down",
                          anomeric_color="#b03030")
    ax.text(-0.05, -1.90, "α-D-Glucopyranosyl", ha="center", fontsize=10,
            fontweight="bold", color="#203a7a")
    # Right: fructose ring (translated)
    old_xlim = ax.get_xlim()
    # Shift fructose by drawing on offset coords
    saved_x = 3.6
    O_ring = (saved_x + 0.00, 0.95)
    C2 = (saved_x + 0.95, 0.35)
    C3 = (saved_x + 0.60, -0.75)
    C4 = (saved_x - 0.60, -0.75)
    C5 = (saved_x - 0.95, 0.35)
    ring = [C5, O_ring, C2, C3, C4, C5]
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    ax.plot(xs, ys, color=C_RING, lw=3.0)
    ax.plot([C3[0], C4[0]], [C3[1], C4[1]], color=C_RING, lw=4.5)
    _atom(ax, O_ring, "O", color=C_OH, size=13, weight="bold")
    ax.text(saved_x, -1.90, "β-D-Fructofuranosyl", ha="center",
            fontsize=10, fontweight="bold", color="#203a7a")
    # Glycosidic bridge (C1 of glucose -> C2 of fructose)
    g_c1 = (1.30, 0.00)
    f_c2 = (saved_x + 0.95, 0.35)
    ax.plot([g_c1[0]+0.55, f_c2[0]-0.15], [g_c1[1], f_c2[1]],
            color="#c81e1e", lw=1.8, linestyle="--")
    mid_x = (g_c1[0] + 0.55 + f_c2[0] - 0.15) / 2
    ax.text(mid_x, 0.55, "O", color="#c81e1e", fontsize=12,
            ha="center", va="center", fontweight="bold")
    ax.annotate("α(1→2)\nglycosidic bond",
                xy=(mid_x, 0.20), xytext=(mid_x, -0.60),
                arrowprops=dict(arrowstyle="->", color="#b03030", lw=1),
                fontsize=9, color="#b03030", ha="center", fontweight="bold")
    ax.set_xlim(-2.2, 6.0)
    ax.set_ylim(-2.4, 2.0)
    ax.axis("off")
    ax.set_aspect("equal")
    ax.text(2.0, 1.75, "Sucrose = α-D-Glucopyranosyl-(1→2)-β-D-Fructofuranoside",
            ha="center", fontsize=10, fontweight="bold", color="#203a7a")
    return _save(fig, out)


if __name__ == "__main__":
    os.makedirs("chem_test", exist_ok=True)
    tests = [
        ("glucose_alpha",   chem_glucose_alpha_haworth),
        ("glucose_beta",    chem_glucose_beta_haworth),
        ("glucose_pair",    chem_glucose_pair),
        ("fructose_alpha",  chem_fructose_alpha_haworth),
        ("glucose_fischer", chem_glucose_fischer),
        ("sucrose",         chem_sucrose),
    ]
    for name, fn in tests:
        out = f"chem_test/{name}.png"
        ok = fn(out)
        size = os.path.getsize(out) if ok else 0
        print(f"{'OK  ' if ok else 'FAIL'} {name:20s} {size:>8} bytes")
