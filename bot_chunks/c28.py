# ==========================================================
# c28 — PDF fix + NameError guard
# ==========================================================

import os as _os
import sys as _sys
import traceback as _traceback

# ----------------------------------------------------------
# FIX — PDF via fpdf2 (works, no pandoc/md2pdf)
# ----------------------------------------------------------
try:
    from fpdf import FPDF
    _PDF_OK = True
except Exception:
    _PDF_OK = False
    print("[PDF] fpdf2 not installed. Run: pip install fpdf2 --break-system-packages")


def _clean_text_for_pdf(text):
    """Strips emoji + SVG + markdown-lite for fpdf2."""
    import re
    if not text:
        return ""
    # Remove fenced code blocks (svg)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove all emojis
    text = re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF]", "", text)
    # Remove markdown bold/italic
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"[*_`>#]", "", text)
    # Replace common math symbols with readable ASCII
    replacements = {
        "θ": "theta", "τ": "tau", "π": "pi", "α": "alpha", "β": "beta",
        "Δ": "Delta", "Σ": "Sigma", "Ω": "Omega", "√": "sqrt", "×": "x",
        "·": ".", "≈": "~", "≤": "<=", "≥": ">=", "→": "->",
        "²": "^2", "³": "^3", "₁": "_1", "₂": "_2", "₀": "_0",
        "ₓ": "_x", "⁻": "^-", "⁺": "^+",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def generate_pdf(content, filename):
    """
    Generate PDF file. Returns full path or None on failure.
    Replaces old pandoc/md2pdf pipeline.
    """
    if not _PDF_OK:
        return None
    try:
        clean = _clean_text_for_pdf(content)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.set_auto_page_break(auto=True, margin=15)
        # Split into lines and write
        for line in clean.split("\n"):
            try:
                pdf.multi_cell(0, 6, line.encode("latin-1", "replace").decode("latin-1"))
            except Exception:
                pass
        out_dir = "pdf_out"
        _os.makedirs(out_dir, exist_ok=True)
        out_path = _os.path.join(out_dir, filename)
        pdf.output(out_path)
        return out_path
    except Exception as e:
        print(f"[PDF] error: {e}")
        return None


# ----------------------------------------------------------
# OVERRIDE — Global safe wrapper for any handler
# ----------------------------------------------------------
def _safe_wrap_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NameError as e:
            print(f"[SAFE] NameError in {func.__name__}: {e}")
            _traceback.print_exc()
            try:
                # Notify user minimally
                if args and hasattr(args[0], "chat"):
                    safe_send(args[0].chat.id, "⚠️ Minor glitch — please retry.")
            except Exception:
                pass
        except Exception as e:
            print(f"[SAFE] Error in {func.__name__}: {e}")
            _traceback.print_exc()
            try:
                if args and hasattr(args[0], "chat"):
                    safe_send(args[0].chat.id, "⚠️ Something went wrong. Please retry.")
            except Exception:
                pass
    return wrapper


# ----------------------------------------------------------
# Patch the notes/PDF flow — replace old PDF calls
# ----------------------------------------------------------
def _send_notes_pdf(uid, content, base_name):
    """New PDF sender. Uses working fpdf2 pipeline."""
    if not _PDF_OK:
        safe_send(uid, "⚠️ PDF library not installed. Sending as text instead.")
        safe_send(uid, content[:3500])
        return

    fname = f"{base_name}.pdf"
    path = generate_pdf(content, fname)
    if path and _os.path.exists(path):
        try:
            with open(path, "rb") as f:
                bot.send_document(uid, f, caption=f"📄 {base_name}\n_Developed by Vishnavi Gokarnam_",
                                  parse_mode="Markdown")
        except Exception as e:
            safe_send(uid, f"⚠️ PDF send failed: {e}")
        try:
            _os.remove(path)
        except Exception:
            pass
    else:
        safe_send(uid, "⚠️ PDF generation failed. Sending content as text instead.")
        safe_send(uid, content[:3500])


# ----------------------------------------------------------
# FIX — Patch specific broken call signature
# ----------------------------------------------------------
# Old code calls md2pdf(..., pdf_file_path=...). That's wrong.
# Provide a compatible shim.
def md2pdf(*args, **kwargs):
    """Compatibility shim for old broken call signature."""
    content = ""
    filename = "output.pdf"
    for a in args:
        if isinstance(a, str):
            if a.endswith(".md"):
                try:
                    with open(a) as f:
                        content = f.read()
                except Exception:
                    pass
            elif a.endswith(".pdf"):
                filename = a
            else:
                content = a
    if "md_file_path" in kwargs:
        try:
            with open(kwargs["md_file_path"]) as f:
                content = f.read()
        except Exception:
            pass
    if "pdf_file_path" in kwargs:
        filename = _os.path.basename(kwargs["pdf_file_path"])
    if not content:
        return None
    return generate_pdf(content, filename)


print("bot.py Chunk 28 loaded: PDF fixed + NameError guard ready.")

