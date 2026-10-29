# ==========================================================
# svg_templates.py — Hamilton Study AI
# Pre-built SVG templates for health, progress, rank, heatmap.
# ==========================================================

import math

from config import (
    SVG_COLOR_GREEN, SVG_COLOR_YELLOW, SVG_COLOR_ORANGE,
    SVG_COLOR_RED, SVG_COLOR_BG, SVG_COLOR_TEXT, SVG_COLOR_ACCENT,
)


def _color_for(health):
    if health is None:
        return "#444444"
    if health >= 85:
        return SVG_COLOR_GREEN
    if health >= 70:
        return SVG_COLOR_YELLOW
    if health >= 55:
        return SVG_COLOR_ORANGE
    return SVG_COLOR_RED


# ==========================================================
# HEALTH DELTA BAR
# ==========================================================
def health_delta_bar(concept_name, before, after):
    w, h = 700, 260
    b = before or 0
    a = after or 0
    delta = a - b

    if delta > 0:
        dcolor = SVG_COLOR_GREEN
        dtext = f"+{delta:.1f}"
    elif delta < 0:
        dcolor = SVG_COLOR_RED
        dtext = f"{delta:.1f}"
    else:
        dcolor = "#888888"
        dtext = "0"

    bcolor = _color_for(before)
    acolor = _color_for(after)
    bw = int(b / 100 * 500)
    aw = int(a / 100 * 500)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect width="{w}" height="{h}" fill="{SVG_COLOR_BG}" rx="15"/>
  <text x="30" y="40" font-size="18" font-weight="bold" fill="{SVG_COLOR_TEXT}" font-family="Arial">
    Health Update — {concept_name[:55]}
  </text>

  <text x="30" y="90" font-size="14" fill="#cccccc" font-family="Arial">Before</text>
  <rect x="120" y="75" width="500" height="24" fill="#222" rx="12"/>
  <rect x="120" y="75" width="{bw}" height="24" fill="{bcolor}" rx="12"/>
  <text x="640" y="93" font-size="15" fill="{bcolor}" font-family="Arial" font-weight="bold">{b:.1f}</text>

  <text x="30" y="150" font-size="14" fill="#cccccc" font-family="Arial">After</text>
  <rect x="120" y="135" width="500" height="24" fill="#222" rx="12"/>
  <rect x="120" y="135" width="{aw}" height="24" fill="{acolor}" rx="12"/>
  <text x="640" y="153" font-size="15" fill="{acolor}" font-family="Arial" font-weight="bold">{a:.1f}</text>

  <text x="350" y="215" font-size="26" font-weight="bold" fill="{dcolor}" font-family="Arial" text-anchor="middle">
    {dtext}
  </text>
  <text x="350" y="240" font-size="12" fill="#888888" font-family="Arial" text-anchor="middle">
    Change in health
  </text>
</svg>'''


# ==========================================================
# COMBINED PROGRESS (overall + subjects)
# ==========================================================
def combined_progress(overall, subject_data):
    w = 800
    row_h = 55
    n = len(subject_data)
    h = 200 + row_h * n

    ocolor = _color_for(overall)
    ow = int((overall or 0) / 100 * 600)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="{SVG_COLOR_BG}" rx="15"/>',
        f'<text x="{w//2}" y="42" font-size="22" font-weight="bold" fill="{SVG_COLOR_TEXT}" '
        f'font-family="Arial" text-anchor="middle">OVERALL PROGRESS</text>',
        f'<text x="40" y="100" font-size="16" fill="#cccccc" font-family="Arial">Overall</text>',
        f'<rect x="40" y="110" width="600" height="28" fill="#222" rx="14"/>',
        f'<rect x="40" y="110" width="{ow}" height="28" fill="{ocolor}" rx="14"/>',
        f'<text x="660" y="132" font-size="20" font-weight="bold" fill="{ocolor}" '
        f'font-family="Arial">{(overall or 0):.1f}</text>',
        f'<text x="40" y="175" font-size="14" fill="#888888" font-family="Arial">SUBJECT-WISE</text>',
    ]

    y = 200
    for subj, h_val in subject_data.items():
        color = _color_for(h_val)
        bw = int((h_val or 0) / 100 * 600)
        val_txt = f"{h_val:.1f}" if h_val is not None else "—"
        parts.append(f'<text x="40" y="{y+4}" font-size="14" fill="#dddddd" font-family="Arial">{subj}</text>')
        parts.append(f'<rect x="40" y="{y+12}" width="600" height="22" fill="#222" rx="11"/>')
        parts.append(f'<rect x="40" y="{y+12}" width="{bw}" height="22" fill="{color}" rx="11"/>')
        parts.append(f'<text x="660" y="{y+30}" font-size="15" font-weight="bold" fill="{color}" '
                     f'font-family="Arial">{val_txt}</text>')
        y += row_h

    parts.append('</svg>')
    return "".join(parts)


# ==========================================================
# RANK GAUGE
# ==========================================================
def rank_gauge(percentile):
    w, h = 500, 320
    pct = max(0.0, min(100.0, percentile or 0.0))
    angle = -180 + (pct / 100 * 180)
    rad = math.radians(angle)
    cx, cy, r = 250, 220, 140
    nx = cx + r * math.cos(rad)
    ny = cy + r * math.sin(rad)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect width="{w}" height="{h}" fill="{SVG_COLOR_BG}" rx="15"/>
  <text x="{w//2}" y="40" font-size="20" font-weight="bold" fill="{SVG_COLOR_TEXT}" font-family="Arial" text-anchor="middle">Predicted Percentile</text>

  <path d="M 110 220 A 140 140 0 0 1 390 220" fill="none" stroke="#333" stroke-width="20"/>
  <path d="M 110 220 A 140 140 0 0 1 180 100" fill="none" stroke="{SVG_COLOR_RED}" stroke-width="20"/>
  <path d="M 180 100 A 140 140 0 0 1 250 85" fill="none" stroke="{SVG_COLOR_ORANGE}" stroke-width="20"/>
  <path d="M 250 85 A 140 140 0 0 1 320 100" fill="none" stroke="{SVG_COLOR_YELLOW}" stroke-width="20"/>
  <path d="M 320 100 A 140 140 0 0 1 390 220" fill="none" stroke="{SVG_COLOR_GREEN}" stroke-width="20"/>

  <line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="{SVG_COLOR_ACCENT}" stroke-width="4"/>
  <circle cx="{cx}" cy="{cy}" r="10" fill="{SVG_COLOR_ACCENT}"/>

  <text x="{w//2}" y="290" font-size="36" font-weight="bold" fill="{SVG_COLOR_ACCENT}" font-family="Arial" text-anchor="middle">{pct:.1f}</text>
</svg>'''


# ==========================================================
# CHAPTER HEATMAP
# ==========================================================
def chapter_heatmap(chapters):
    cols = 4
    tile_w, tile_h, gap = 180, 70, 12
    rows = (len(chapters) + cols - 1) // cols if chapters else 1
    w = 40 + cols * (tile_w + gap)
    h = 110 + rows * (tile_h + gap)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="{SVG_COLOR_BG}" rx="15"/>',
        f'<text x="{w//2}" y="45" font-size="20" font-weight="bold" fill="{SVG_COLOR_TEXT}" '
        f'font-family="Arial" text-anchor="middle">Chapter Health Map</text>',
    ]

    x0, y0 = 40, 90
    for i, (name, val) in enumerate(chapters[:24]):
        r = i // cols
        c = i % cols
        x = x0 + c * (tile_w + gap)
        y = y0 + r * (tile_h + gap)
        color = _color_for(val)
        vtxt = f"{val:.0f}" if val is not None else "—"
        short = name[:20] + ("…" if len(name) > 20 else "")
        parts.append(f'<rect x="{x}" y="{y}" width="{tile_w}" height="{tile_h}" '
                     f'fill="{color}" rx="8" opacity="0.85"/>')
        parts.append(f'<text x="{x + tile_w//2}" y="{y + 28}" font-size="12" fill="#ffffff" '
                     f'font-family="Arial" text-anchor="middle" font-weight="bold">{short}</text>')
        parts.append(f'<text x="{x + tile_w//2}" y="{y + 52}" font-size="18" fill="#ffffff" '
                     f'font-family="Arial" text-anchor="middle" font-weight="bold">{vtxt}</text>')

    parts.append('</svg>')
    return "".join(parts)


if __name__ == "__main__":
    print("svg_templates.py OK")
