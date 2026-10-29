# ==========================================================
# rich_formatter.py — Hamilton Study AI
# ==========================================================

import re
try:
    from math_sanitizer import sanitize_math as _sanitize_math
except Exception:
    def _sanitize_math(t):
        return t
from telebot.types import (
    InputRichMessage,
    InputRichBlockParagraph,
    InputRichBlockSectionHeading,
    InputRichBlockMathematicalExpression,
    RichTextBold,
    RichTextItalic,
    RichTextCode,
    RichTextMathematicalExpression,
)

MATH_HINTS = [
    "\\begin", "\\end", "\\frac", "\\sqrt", "\\sum", "\\int",
    "\\vec", "\\hat", "\\bar", "\\dot", "\\det", "\\lim",
    "\\sin", "\\cos", "\\tan", "\\log", "\\ln", "\\exp",
    "\\alpha", "\\beta", "\\gamma", "\\delta", "\\theta",
    "\\lambda", "\\mu", "\\pi", "\\sigma", "\\omega", "\\phi",
    "\\times", "\\cdot", "\\pm", "\\infty", "\\partial",
    "\\nabla", "\\rightarrow", "\\Rightarrow", "\\implies",
    "\\varepsilon", "\\rho", "\\Delta",
    "\\left", "\\right", "\\big",
    "\\mathbf", "\\mathrm", "\\mathit",
    "\\text", "\\langle", "\\rangle", "\\displaystyle",
    "\\tfrac", "\\dfrac",
    "\\le", "\\ge", "\\ne", "\\approx",
]


def _has_math(line):
    return any(h in line for h in MATH_HINTS)


def _wrap_line_math(line):
    if not line:
        return line
    if "$" in line:
        return line
    if _has_math(line):
        prose_re = re.compile(
            r"\b(the|is|are|was|were|will|would|this|that|these|those|"
            r"find|compute|answer|solve|consider|given|which|what|"
            r"question|option|choose|select|from|with|when|then|and|or|"
            r"of|for|to|in|on|at|by|as|an|a|be|we|you|it|its|"
            r"matrix|determinant|value|result|solution|equation|"
            r"therefore|hence|thus|since|because|where|if|"
            r"note|remember|example|application|trap|important|"
            r"chapter|concept|definition|formula|units|table)\b",
            re.IGNORECASE,
        )
        if not prose_re.search(line):
            return "$$" + line.strip() + "$$"
    return line




def _array_to_table(md_text):
    """Convert \\begin{array}{...}...\\end{array} into markdown tables."""
    if not md_text:
        return md_text
    pattern = re.compile(
        r"\\begin\{array\}\{[^{}]*\}(.*?)\\end\{array\}",
        re.DOTALL,
    )

    def _build(m):
        body = m.group(1)
        rows = re.split(r"\\\\", body)
        clean_rows = []
        for r in rows:
            r = r.strip()
            if not r:
                continue
            # remove \hline
            r = r.replace("\\hline", "").strip()
            if not r:
                continue
            cells = [c.strip() for c in r.split("&")]
            clean_cells = []
            for c in cells:
                c = re.sub(r"\\text\{([^{}]*)\}", r"\1", c)
                c = c.replace("\\", "")
                clean_cells.append(c.strip())
            clean_rows.append(clean_cells)
        if not clean_rows:
            return ""
        ncols = max(len(r) for r in clean_rows)
        md = []
        md.append("| " + " | ".join(clean_rows[0]) + " |")
        md.append("|" + "---|" * ncols)
        for r in clean_rows[1:]:
            while len(r) < ncols:
                r.append("")
            md.append("| " + " | ".join(r) + " |")
        return "\n\n" + "\n".join(md) + "\n\n"

    return pattern.sub(_build, md_text)

def ensure_math_delims(text):
    if not text:
        return text
    text = re.sub(r"\\\((.+?)\\\)", r"$\1$", text, flags=re.DOTALL)
    text = re.sub(r"\\\[(.+?)\\\]", r"$$\1$$", text, flags=re.DOTALL)

    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "\\begin{" in line and "\\end{" not in line and "$" not in line:
            block = [line]
            j = i + 1
            while j < len(lines) and "\\end{" not in lines[j]:
                block.append(lines[j])
                j += 1
            if j < len(lines):
                block.append(lines[j])
            combined = "\n".join(block)
            out.append("$$\n" + combined + "\n$$")
            i = j + 1
            continue
        out.append(_wrap_line_math(line))
        i += 1
    return "\n".join(out)


def _parse_inline(text):
    if not text:
        return [""]
    result = []
    pattern = re.compile(
        r"(\*\*(.+?)\*\*)"
        r"|(\*(.+?)\*)"
        r"|(`(.+?)`)"
        r"|(\$(.+?)\$)"
    )
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            result.append(text[pos:m.start()])
        if m.group(2):
            result.append(RichTextBold(text=m.group(2)))
        elif m.group(4):
            result.append(RichTextItalic(text=m.group(4)))
        elif m.group(6):
            result.append(RichTextCode(text=m.group(6)))
        elif m.group(8):
            try:
                result.append(RichTextMathematicalExpression(
                    expression=m.group(8), math_source="latex"))
            except Exception:
                result.append(RichTextMathematicalExpression(
                    expression=m.group(8)))
        pos = m.end()
    if pos < len(text):
        result.append(text[pos:])
    cleaned = [r for r in result if r != ""]
    return cleaned or [""]


def markdown_to_rich(md_text):
    if not md_text:
        return InputRichMessage(blocks=[InputRichBlockParagraph(text="(empty)")])

    md_text = _sanitize_math(md_text)
    md_text = _array_to_table(md_text)
    # md_text = ensure_math_delims(md_text)  # disabled — kept plain text

    blocks = []
    lines = md_text.split("\n")
    i = 0
    para_buffer = []

    def flush_para():
        if para_buffer:
            joined = "\n".join(para_buffer).strip()
            if joined:
                blocks.append(InputRichBlockParagraph(text=_parse_inline(joined)))
            para_buffer.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("$$"):
            flush_para()
            if stripped.count("$$") >= 2 and len(stripped) > 4:
                inner = stripped[2:-2].strip()
                try:
                    blocks.append(InputRichBlockMathematicalExpression(
                        expression=inner, math_source="latex"))
                except Exception:
                    blocks.append(InputRichBlockMathematicalExpression(inner))
                i += 1
                continue
            math_buf = [stripped[2:]]
            i += 1
            while i < len(lines) and "$$" not in lines[i]:
                math_buf.append(lines[i])
                i += 1
            if i < len(lines):
                math_buf.append(lines[i].replace("$$", ""))
            expr = "\n".join(math_buf).strip()
            if expr:
                try:
                    blocks.append(InputRichBlockMathematicalExpression(
                        expression=expr, math_source="latex"))
                except Exception:
                    blocks.append(InputRichBlockMathematicalExpression(expr))
            i += 1
            continue

        if stripped.startswith("### "):
            flush_para()
            blocks.append(InputRichBlockSectionHeading(
                text=stripped[4:].strip(), size=3))
        elif stripped.startswith("## "):
            flush_para()
            blocks.append(InputRichBlockSectionHeading(
                text=stripped[3:].strip(), size=2))
        elif stripped.startswith("# "):
            flush_para()
            blocks.append(InputRichBlockSectionHeading(
                text=stripped[2:].strip(), size=1))
        elif stripped in ("---", "***", "___"):
            flush_para()
            blocks.append(InputRichBlockParagraph(text="─"))
        elif stripped == "":
            flush_para()
        else:
            para_buffer.append(line)
        i += 1

    flush_para()

    if not blocks:
        blocks.append(InputRichBlockParagraph(text=md_text[:4000]))

    return InputRichMessage(blocks=blocks)


if __name__ == "__main__":
    print("rich_formatter.py loaded OK")
