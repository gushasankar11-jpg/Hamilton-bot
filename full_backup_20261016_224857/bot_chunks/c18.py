# ==========================================================
# bot.py — Chunk 18: Matrix/image fallback for complex LaTeX
# ==========================================================

from math_image_renderer import has_matrix_env, render_latex_to_png


# Override safe_send — if text has matrices, render as image
_prev_safe_send = safe_send


def _extract_matrix_lines(text):
    """Find all lines with \begin{...} matrix environments."""
    if not text:
        return [], []
    lines = text.split("\n")
    prose_lines = []
    matrix_chunks = []
    in_matrix = False
    buffer = []

    for line in lines:
        if "\\begin{" in line and any(e in line for e in [
            "matrix", "bmatrix", "vmatrix", "pmatrix", "cases",
            "aligned", "array",
        ]):
            in_matrix = True
            buffer = [line]
            if "\\end{" in line:
                matrix_chunks.append("\n".join(buffer))
                in_matrix = False
                buffer = []
            continue
        if in_matrix:
            buffer.append(line)
            if "\\end{" in line:
                matrix_chunks.append("\n".join(buffer))
                in_matrix = False
                buffer = []
            continue
        prose_lines.append(line)

    return prose_lines, matrix_chunks


def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    """
    If text contains matrix environments → split:
      - send prose as rich/plain
      - render each matrix as PNG image
    Otherwise → pass through to previous safe_send.
    """
    if not text:
        return

    if not has_matrix_env(text):
        return _prev_safe_send(chat_id, text, parse_mode=parse_mode,
                                reply_markup=reply_markup)

    prose_lines, matrix_chunks = _extract_matrix_lines(text)

    # 1. Send prose part (rich or plain)
    prose_text = "\n".join(prose_lines).strip()
    if prose_text:
        _prev_safe_send(chat_id, prose_text, parse_mode=parse_mode)

    # 2. Render each matrix chunk as image
    import time as _t
    for idx, chunk in enumerate(matrix_chunks):
        try:
            path = render_latex_to_png(chunk, name=f"matrix_{chat_id}_{int(_t.time())}_{idx}")
            if path:
                try:
                    with open(path, "rb") as f:
                        bot.send_photo(chat_id, f, caption=f"Matrix ({idx+1}/{len(matrix_chunks)})")
                except Exception as e:
                    print(f"[MATRIX-SEND] {e}")
                    # Fallback: send as plain text
                    _prev_safe_send(chat_id, chunk)
                svg_renderer.cleanup_file(path)
            else:
                _prev_safe_send(chat_id, chunk)
        except Exception as e:
            print(f"[MATRIX-RENDER] {e}")
            _prev_safe_send(chat_id, chunk)

    # 3. Apply reply_markup on last message
    if reply_markup and not matrix_chunks and prose_text:
        pass  # already sent


print("bot.py Chunk 18 loaded: matrix image fallback ready.")

