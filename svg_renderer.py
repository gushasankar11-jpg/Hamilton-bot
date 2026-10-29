# ==========================================================
# svg_renderer.py — Hamilton Study AI
# SVG → PNG with HK Publications logo overlay.
# ==========================================================

import os
import subprocess
import hashlib
import time
import re

from config import (
    SVG_TEMP_DIR, SVG_MAX_WIDTH, SVG_CONVERT_CMD,
    SVG_TIMEOUT, SVG_ENABLED, SVG_LOGO_COLOR,
)

os.makedirs(SVG_TEMP_DIR, exist_ok=True)


# ==========================================================
# HK PUBLICATIONS LOGO (SVG)
# ==========================================================
HK_LOGO_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <defs>
    <style>
      .g { fill: #c9a961; }
      .g-line { stroke: #c9a961; fill: none; }
      .g-fill { fill: #c9a961; }
    </style>
  </defs>

  <!-- LEFT LAUREL BRANCH -->
  <g class="g-fill">
    <ellipse cx="26" cy="66" rx="8" ry="3.5" transform="rotate(-50 26 66)"/>
    <ellipse cx="22" cy="80" rx="9" ry="3.5" transform="rotate(-35 22 80)"/>
    <ellipse cx="19" cy="95" rx="10" ry="3.5" transform="rotate(-20 19 95)"/>
    <ellipse cx="18" cy="110" rx="10" ry="3.5"/>
    <ellipse cx="20" cy="125" rx="10" ry="3.5" transform="rotate(20 20 125)"/>
    <ellipse cx="24" cy="139" rx="9" ry="3.5" transform="rotate(35 24 139)"/>
    <ellipse cx="31" cy="152" rx="8" ry="3.5" transform="rotate(50 31 152)"/>
    <ellipse cx="42" cy="163" rx="7" ry="3" transform="rotate(65 42 163)"/>
    <ellipse cx="55" cy="171" rx="6" ry="2.8" transform="rotate(80 55 171)"/>
  </g>

  <!-- RIGHT LAUREL BRANCH -->
  <g class="g-fill">
    <ellipse cx="174" cy="66" rx="8" ry="3.5" transform="rotate(50 174 66)"/>
    <ellipse cx="178" cy="80" rx="9" ry="3.5" transform="rotate(35 178 80)"/>
    <ellipse cx="181" cy="95" rx="10" ry="3.5" transform="rotate(20 181 95)"/>
    <ellipse cx="182" cy="110" rx="10" ry="3.5"/>
    <ellipse cx="180" cy="125" rx="10" ry="3.5" transform="rotate(-20 180 125)"/>
    <ellipse cx="176" cy="139" rx="9" ry="3.5" transform="rotate(-35 176 139)"/>
    <ellipse cx="169" cy="152" rx="8" ry="3.5" transform="rotate(-50 169 152)"/>
    <ellipse cx="158" cy="163" rx="7" ry="3" transform="rotate(-65 158 163)"/>
    <ellipse cx="145" cy="171" rx="6" ry="2.8" transform="rotate(-80 145 171)"/>
  </g>

  <!-- SHIELD -->
  <path d="M 100,42 L 148,58 L 148,115 Q 148,148 100,168 Q 52,148 52,115 L 52,58 Z"
        class="g-line" stroke-width="3.5"/>

  <!-- H (left) -->
  <text x="70" y="110" font-family="Georgia, 'Times New Roman', serif"
        font-weight="bold" font-size="42" class="g-fill">H</text>
  <!-- Vertical bar between -->
  <rect x="98" y="72" width="3" height="60" class="g-fill"/>
  <!-- K (right) -->
  <text x="108" y="110" font-family="Georgia, 'Times New Roman', serif"
        font-weight="bold" font-size="42" class="g-fill">K</text>

  <!-- BOOK (bottom left of shield) -->
  <g transform="translate(62, 118)">
    <path d="M 0,0 Q 9,-4 18,0 L 18,15 Q 9,11 0,15 Z" class="g-line" stroke-width="2"/>
    <line x1="9" y1="0" x2="9" y2="15" class="g-line" stroke-width="1.6"/>
  </g>

  <!-- LEAF/QUILL (top right of shield) -->
  <g transform="translate(120, 68)">
    <path d="M 0,22 Q 6,6 20,0 Q 22,16 8,24 Z" class="g-fill"/>
    <path d="M 2,20 Q 8,12 16,6" class="g-line" stroke-width="1.5"/>
  </g>
</svg>'''


def _extract_logo_inner():
    """Returns HK logo SVG without <svg> wrapper."""
    s = HK_LOGO_SVG
    s = re.sub(r'^<svg[^>]*>', '', s)
    s = re.sub(r'</svg>\s*$', '', s)
    return s


def add_hk_logo(svg_code, size=70):
    """
    Injects HK Publications logo into the top-right corner of the given SVG.
    Returns modified SVG code.
    """
    m_w = re.search(r'width="(\d+)"', svg_code)
    m_h = re.search(r'height="(\d+)"', svg_code)
    if not m_w or not m_h:
        return svg_code

    w = int(m_w.group(1))
    x = w - size - 10
    y = 10
    scale = size / 200.0

    logo_inner = _extract_logo_inner()
    logo_wrapped = f'<g transform="translate({x},{y}) scale({scale})" opacity="0.9">{logo_inner}</g>'

    if "</svg>" in svg_code:
        return svg_code.replace("</svg>", logo_wrapped + "</svg>", 1)
    return svg_code


# ==========================================================
# RENDER
# ==========================================================
def _safe_name(svg_code):
    h = hashlib.md5(svg_code.encode("utf-8")).hexdigest()[:10]
    return f"svg_{h}_{int(time.time())}"


def render_svg(svg_code, name=None, width=None, add_logo=True):
    """
    Converts SVG code → PNG file.
    Adds HK logo overlay by default.
    Returns PNG path or None.
    """
    if not SVG_ENABLED:
        return None
    if not svg_code or "<svg" not in svg_code.lower():
        return None

    if add_logo:
        try:
            svg_code = add_hk_logo(svg_code)
        except Exception:
            pass

    if not name:
        name = _safe_name(svg_code)

    svg_path = os.path.join(SVG_TEMP_DIR, f"{name}.svg")
    png_path = os.path.join(SVG_TEMP_DIR, f"{name}.png")

    try:
        with open(svg_path, "w") as f:
            f.write(svg_code)
    except Exception:
        return None

    try:
        result = subprocess.run(
            [SVG_CONVERT_CMD, "-w", str(width or SVG_MAX_WIDTH),
             "-o", png_path, svg_path],
            capture_output=True, text=True, timeout=SVG_TIMEOUT,
        )
    except Exception:
        return None

    if result.returncode != 0 or not os.path.exists(png_path):
        return None

    return png_path


def cleanup_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def cleanup_old_files(max_age_sec=3600):
    now = time.time()
    try:
        for f in os.listdir(SVG_TEMP_DIR):
            fp = os.path.join(SVG_TEMP_DIR, f)
            try:
                if now - os.path.getmtime(fp) > max_age_sec:
                    os.remove(fp)
            except Exception:
                pass
    except Exception:
        pass


def detect_svg_in_text(text):
    """
    Extract SVG from text (```svg...``` or bare <svg>...</svg>).
    Returns (svg_code_or_None, cleaned_text).
    """
    if not text:
        return None, text

    if "```svg" in text:
        try:
            before, rest = text.split("```svg", 1)
            svg_part, after = rest.split("```", 1)
            return svg_part.strip(), (before + after).strip()
        except Exception:
            pass

    low = text.lower()
    if "<svg" in low and "</svg>" in low:
        start = low.find("<svg")
        end = low.find("</svg>") + len("</svg>")
        svg = text[start:end]
        cleaned = (text[:start] + text[end:]).strip()
        return svg, cleaned

    return None, text


if __name__ == "__main__":
    print("svg_renderer.py OK")
    test = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect width="400" height="200" fill="#0a0a1a"/><circle cx="200" cy="100" r="60" fill="#28a745"/><text x="200" y="30" font-size="20" fill="#ffffff" text-anchor="middle">Test</text></svg>'
    p = render_svg(test, name="self_test")
    if p and os.path.exists(p):
        print("Rendered:", p, os.path.getsize(p), "bytes")
    else:
        print("Render FAILED")
