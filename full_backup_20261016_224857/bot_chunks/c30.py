# ==========================================================
# c30 — 4-Barrier LaTeX pipeline + PDF (Unicode font)
# ==========================================================

import os as _os
import re as _re
import time as _time
import builtins as _bt
import threading as _th
from collections import defaultdict as _dd

try:
    from telebot.types import InputRichMessage
    _RICH_OK = True
except Exception:
    _RICH_OK = False

try:
    from tg_rich_converter import to_rich as _to_rich
    _CONV_OK = True
except Exception:
    _CONV_OK = False

try:
    from fpdf import FPDF as _FPDF
    _FPDF_OK = True
    print("[c30] fpdf2 loaded")
except Exception as e:
    _FPDF_OK = False
    print(f"[c30] fpdf2 missing: {e}")

_ORIG_SEND = safe_send
_ORIG_EDIT = safe_edit

_FONT_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "DejaVuSans.ttf"))
_FONT_OK = _os.path.exists(_FONT_PATH)
print(f"[c30] Font present: {_FONT_OK}")

# ----------------------------------------------------------
# BARRIER 1 — LaTeX detection
# ----------------------------------------------------------
_LATEX_RE = _re.compile(r"\\[a-zA-Z]+|\\begin\{|\\end\{|\\\\\[|\$[^$]+\$")

def _has_latex(t):
    if not t:
        return False
    return bool(_LATEX_RE.search(t))

# ----------------------------------------------------------
# MATRIX → ASCII
# ----------------------------------------------------------
def _ascii_matrix(rows, style="bracket"):
    ncol = max((len(r) for r in rows), default=0)
    if ncol == 0:
        return ""
    widths = [0] * ncol
    for r in rows:
        for i in range(ncol):
            c = str(r[i]) if i < len(r) else ""
            widths[i] = max(widths[i], len(c))
    L, R = "[", "]"
    if style == "paren":
        L, R = "(", ")"
    elif style == "bar":
        L, R = "|", "|"
    lines = []
    for r in rows:
        cells = []
        for i in range(ncol):
            c = str(r[i]) if i < len(r) else ""
            cells.append(c.center(widths[i]))
        lines.append(f"  {L} {'   '.join(cells)} {R}")
    return "\n".join(lines)

_ENV_RE = _re.compile(
    r"\\begin\{(bmatrix|pmatrix|vmatrix|matrix|cases|aligned|array)\}"
    r"(\{[^}]*\})?"
    r"(.*?)"
    r"\\end\{\1\}",
    _re.DOTALL,
)

def _replace_matrix_envs(text):
    if not text:
        return text
    def _conv(m):
        env = m.group(1)
        body = m.group(3)
        rows_raw = _re.split(r"\\\\", body)
        rows = []
        for r in rows_raw:
            r = r.strip()
            if not r:
                continue
            cells = [c.strip() for c in r.split("&")]
            rows.append(cells)
        if not rows:
            return ""
        style = {
            "bmatrix": "bracket", "pmatrix": "paren", "vmatrix": "bar",
            "matrix": "bracket", "cases": "bracket", "aligned": "bracket",
            "array": "bracket",
        }.get(env, "bracket")
        return f"\n<pre>\n{_ascii_matrix(rows, style)}\n</pre>\n"
    return _ENV_RE.sub(_conv, text)

# ----------------------------------------------------------
# BARRIER 3 — LaTeX → Unicode
# ----------------------------------------------------------
_SYM = [
    (r"\Longrightarrow", "⇒"), (r"\Leftrightarrow", "⇔"),
    (r"\Rightarrow", "⇒"), (r"\Leftarrow", "⇐"),
    (r"\longrightarrow", "⟶"), (r"\longleftarrow", "⟵"),
    (r"\rightarrow", "→"), (r"\leftarrow", "←"),
    (r"\uparrow", "↑"), (r"\downarrow", "↓"),
    (r"\varepsilon", "ε"), (r"\emptyset", "∅"),
    (r"\varnothing", "∅"), (r"\setminus", "∖"),
    (r"\triangle", "△"), (r"\angle", "∠"),
    (r"\parallel", "∥"), (r"\perp", "⊥"),
    (r"\approx", "≈"), (r"\equiv", "≡"), (r"\cong", "≅"),
    (r"\propto", "∝"), (r"\sim", "∼"),
    (r"\subseteq", "⊆"), (r"\subset", "⊂"),
    (r"\supseteq", "⊇"), (r"\supset", "⊃"),
    (r"\notin", "∉"), (r"\in", "∈"), (r"\ni", "∋"),
    (r"\forall", "∀"), (r"\exists", "∃"),
    (r"\nabla", "∇"), (r"\partial", "∂"),
    (r"\infty", "∞"), (r"\iint", "∬"), (r"\iiint", "∭"),
    (r"\oint", "∮"), (r"\int", "∫"), (r"\sum", "∑"), (r"\prod", "∏"),
    (r"\cdots", "⋯"), (r"\ldots", "…"), (r"\dots", "…"),
    (r"\langle", "⟨"), (r"\rangle", "⟩"),
    (r"\lvert", "|"), (r"\rvert", "|"),
    (r"\lVert", "‖"), (r"\rVert", "‖"),
    (r"\lim", "lim"), (r"\exp", "exp"),
    (r"\max", "max"), (r"\min", "min"),
    (r"\log", "log"), (r"\ln", "ln"),
    (r"\sinh", "sinh"), (r"\cosh", "cosh"), (r"\tanh", "tanh"),
    (r"\arcsin", "arcsin"), (r"\arccos", "arccos"), (r"\arctan", "arctan"),
    (r"\sin", "sin"), (r"\cos", "cos"), (r"\tan", "tan"),
    (r"\cot", "cot"), (r"\sec", "sec"), (r"\csc", "csc"),
    (r"\Theta", "Θ"), (r"\Lambda", "Λ"), (r"\Xi", "Ξ"),
    (r"\Pi", "Π"), (r"\Sigma", "Σ"), (r"\Upsilon", "Υ"),
    (r"\Phi", "Φ"), (r"\Psi", "Ψ"), (r"\Omega", "Ω"),
    (r"\Delta", "Δ"), (r"\Gamma", "Γ"),
    (r"\alpha", "α"), (r"\beta", "β"), (r"\gamma", "γ"),
    (r"\delta", "δ"), (r"\epsilon", "ε"), (r"\zeta", "ζ"),
    (r"\eta", "η"), (r"\theta", "θ"), (r"\iota", "ι"),
    (r"\kappa", "κ"), (r"\lambda", "λ"), (r"\mu", "μ"),
    (r"\nu", "ν"), (r"\xi", "ξ"), (r"\pi", "π"), (r"\rho", "ρ"),
    (r"\sigma", "σ"), (r"\tau", "τ"), (r"\upsilon", "υ"),
    (r"\phi", "φ"), (r"\chi", "χ"), (r"\psi", "ψ"), (r"\omega", "ω"),
    (r"\mathbb{R}", "ℝ"), (r"\mathbb{N}", "ℕ"),
    (r"\mathbb{Z}", "ℤ"), (r"\mathbb{Q}", "ℚ"),
    (r"\mathbb{C}", "ℂ"), (r"\mathbb{P}", "ℙ"),
    (r"\times", "×"), (r"\cdot", "·"), (r"\div", "÷"),
    (r"\pm", "±"), (r"\mp", "∓"),
    (r"\leq", "≤"), (r"\geq", "≥"),
    (r"\le", "≤"), (r"\ge", "≥"),
    (r"\neq", "≠"), (r"\ne", "≠"),
    (r"\ll", "≪"), (r"\gg", "≫"),
    (r"\circ", "°"), (r"\ast", "*"), (r"\star", "⋆"),
    (r"\quad", "  "), (r"\qquad", "    "),
    (r"\,", " "), (r"\;", " "), (r"\:", " "), (r"\!", ""),
    (r"\left", ""), (r"\right", ""),
    (r"\bigl", ""), (r"\bigr", ""),
    (r"\Bigl", ""), (r"\Bigr", ""),
    (r"\big", ""), (r"\Big", ""),
    (r"\displaystyle", ""), (r"\textstyle", ""),
    (r"\limits", ""), (r"\hline", ""),
]
_SYM.sort(key=lambda x: -len(x[0]))


def _to_unicode(t):
    if not t:
        return t
    s = t
    s = s.replace("\\\\[4pt]", "\n").replace("\\\\[2pt]", "\n")
    s = s.replace("\\[4pt]", "\n").replace("\\[2pt]", "\n")
    s = _re.sub(r"\\\\?\[\d+(\.\d+)?(pt|mm|cm|ex|em)\]", "\n", s)
    for _ in range(4):
        s = _re.sub(r"\\binom\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"C(\1,\2)", s)
    for _ in range(6):
        s = _re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
    for _ in range(5):
        s = _re.sub(r"\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}", r"(\2)^(1/\1)", s)
    for _ in range(5):
        s = _re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", s)
    s = _re.sub(r"\\vec\s*\{([^{}]*)\}", r"\1⃗", s)
    s = _re.sub(r"\\hat\s*\{([^{}]*)\}", r"\1̂", s)
    s = _re.sub(r"\\bar\s*\{([^{}]*)\}", r"\1̄", s)
    s = _re.sub(r"\\dot\s*\{([^{}]*)\}", r"\1̇", s)
    s = _re.sub(r"\\vec\s+([a-zA-Z])", r"\1⃗", s)
    s = _re.sub(r"\\hat\s+([a-zA-Z])", r"\1̂", s)
    for cmd in ["mathbf", "mathrm", "mathit", "mathsf", "mathtt",
                "mathcal", "mathfrak", "text", "textbf", "textit",
                "textrm", "boldsymbol", "operatorname", "underbrace",
                "overset", "underset", "substack"]:
        s = _re.sub(r"\\" + cmd + r"\s*\{([^{}]*)\}", r"\1", s)
    s = _re.sub(r"\\boxed\s*\{([^{}]*)\}", r"[\1]", s)
    s = _re.sub(r"\\begin\s*\{[^{}]*\}", "", s)
    s = _re.sub(r"\\end\s*\{[^{}]*\}", "", s)
    s = _re.sub(r"\\begin\s*[a-zA-Z]+", "", s)
    s = _re.sub(r"\\end\s*[a-zA-Z]+", "", s)
    sub_map = {"0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅",
               "6":"₆","7":"₇","8":"₈","9":"₉","n":"ₙ","i":"ᵢ",
               "j":"ⱼ","k":"ₖ","m":"ₘ","x":"ₓ","a":"ₐ","+":"₊",
               "-":"₋","=":"₌","r":"ᵣ","s":"ₛ","p":"ₚ","L":"ₗ"}
    def _sub(m):
        return "".join(sub_map.get(c, c) for c in m.group(1))
    s = _re.sub(r"_\{([^}]+)\}", _sub, s)
    sup_map = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵",
               "6":"⁶","7":"⁷","8":"⁸","9":"⁹","n":"ⁿ","+":"⁺","-":"⁻"}
    s = _re.sub(r"\^(-)([a-zA-Z0-9])", r"^(-\2)", s)
    s = _re.sub(r"\^\{([0-9n+\-])\}",
                lambda m: sup_map.get(m.group(1), "^"+m.group(1)), s)
    for k, v in _SYM:
        s = s.replace(k, v)
    s = s.replace(r"\\", "\n")
    s = _re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("$$", "").replace("$", "")
    s = _re.sub(r"[ \t]+", " ", s)
    s = _re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

# ----------------------------------------------------------
# BARRIER 4 — Recall with live timer
# ----------------------------------------------------------
_RECALL = _dd(int)
_MAX_RECALL = 2

def _recall_with_timer(chat_id, bad_text):
    if _RECALL[chat_id] >= _MAX_RECALL:
        return None
    _RECALL[chat_id] += 1

    timer_msg = [None]
    stop_flag = [False]

    def _timer():
        try:
            m = bot.send_message(chat_id,
                "⏱️ *Regenerating to remove LaTeX... 0s*", parse_mode="Markdown")
            timer_msg[0] = m.message_id
        except Exception:
            return
        start = _time.time()
        while not stop_flag[0]:
            el = int(_time.time() - start)
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=m.message_id,
                    text=f"⏱️ *Regenerating to remove LaTeX... {el}s*",
                    parse_mode="Markdown")
            except Exception:
                pass
            _time.sleep(2)

    _th.Thread(target=_timer, daemon=True).start()
    try:
        import ai_client
        prompt = ("Rewrite the following using ONLY plain Unicode math symbols "
                  "(θ, π, √, ², ∑, ∫, →, ≤, ≥, α, β, γ). "
                  "NEVER use backslash \\, never use $ or $$, never use "
                  "\\begin or \\end. Output ONLY the rewritten text.\n\n"
                  + bad_text[:3000])
        new_text = ai_client.ask_hamilton("JEE_MAIN", prompt)
    except Exception:
        new_text = None
    finally:
        stop_flag[0] = True
        if timer_msg[0]:
            try:
                bot.delete_message(chat_id, timer_msg[0])
            except Exception:
                pass
    if new_text:
        _RECALL[chat_id] = 0
    return new_text

# ----------------------------------------------------------
# 4-BARRIER PIPELINE
# ----------------------------------------------------------
def _run_4_barriers(text, chat_id=None, allow_recall=True):
    if not text:
        return text, False
    if not _has_latex(text) and "\\begin{" not in text:
        return text, False
    if "\\begin{" in text:
        text = _replace_matrix_envs(text)
    if _CONV_OK:
        try:
            html = _to_rich(text)
            if html and isinstance(html, str) and "<tg-math" in html:
                return html, True
        except Exception:
            pass
    converted = _to_unicode(text)
    if not _has_latex(converted):
        return converted, False
    if allow_recall and chat_id:
        recalled = _recall_with_timer(chat_id, text)
        if recalled:
            if _CONV_OK:
                try:
                    html = _to_rich(recalled)
                    if html and "<tg-math" in html:
                        return html, True
                except Exception:
                    pass
            return _to_unicode(recalled), False
    return converted, False

# ----------------------------------------------------------
# safe_send / safe_edit
# ----------------------------------------------------------
def safe_send(chat_id, text, parse_mode=None, reply_markup=None):
    if not text:
        return
    final, is_rich = _run_4_barriers(text, chat_id=chat_id)
    if is_rich and _RICH_OK:
        try:
            rich = InputRichMessage(html=final)
            return bot.send_rich_message(chat_id=chat_id,
                rich_message=rich, reply_markup=reply_markup)
        except Exception as e:
            print(f"[c30] rich send fail: {e}")
    try:
        return bot.send_message(chat_id, final, parse_mode=parse_mode,
                                 reply_markup=reply_markup)
    except Exception:
        return _ORIG_SEND(chat_id, final, parse_mode=parse_mode,
                           reply_markup=reply_markup)

def safe_edit(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    if not text:
        return
    final, is_rich = _run_4_barriers(text, chat_id=chat_id)
    if is_rich and _RICH_OK:
        try:
            bot.delete_message(chat_id, message_id)
            rich = InputRichMessage(html=final)
            return bot.send_rich_message(chat_id=chat_id,
                rich_message=rich, reply_markup=reply_markup)
        except Exception:
            pass
    try:
        return bot.edit_message_text(chat_id=chat_id, message_id=message_id,
            text=final, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception:
        return _ORIG_EDIT(chat_id, message_id, final,
                           parse_mode=parse_mode, reply_markup=reply_markup)

# ----------------------------------------------------------
# PDF with DejaVu font
# ----------------------------------------------------------
def _clean_pdf(text):
    if not text:
        return ""
    s = _re.sub(r"```[\s\S]*?```", "", text)
    s = _re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF]", "", s)
    s = s.replace("**", "").replace("##", "")
    s = _re.sub(r"[*_`>#]", "", s)
    return _to_unicode(s)


def make_pdf(content, filename="notes.pdf"):
    if not _FPDF_OK:
        return None
    try:
        clean = _clean_pdf(content)
        pdf = _FPDF()
        pdf.add_page()

        if _FONT_OK:
            pdf.add_font("DejaVu", "", _FONT_PATH)
            pdf.set_font("DejaVu", size=11)
        else:
            pdf.set_font("Helvetica", size=11)

        pdf.set_auto_page_break(auto=True, margin=15)
        for line in clean.split("\n"):
            try:
                if _FONT_OK:
                    pdf.multi_cell(0, 6, line)
                else:
                    sl = line.encode("latin-1", "replace").decode("latin-1")
                    pdf.multi_cell(0, 6, sl)
            except Exception:
                pass

        pdf.ln(8)
        if _FONT_OK:
            pdf.set_font("DejaVu", size=9)
        else:
            pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 8, "Developed by Vishnavi Gokarnam")

        out_dir = "pdf_out"
        _os.makedirs(out_dir, exist_ok=True)
        out_path = _os.path.join(out_dir, filename)
        pdf.output(out_path)
        print(f"[c30] PDF written: {out_path}")
        return out_path
    except Exception as e:
        print(f"[c30] PDF error: {e}")
        import traceback
        traceback.print_exc()
        return None


def send_pdf_to_user(uid, content, base_name="notes"):
    fname = f"{base_name.replace(' ', '_')}.pdf"
    path = make_pdf(content, fname)
    if path and _os.path.exists(path):
        try:
            with open(path, "rb") as f:
                bot.send_document(uid, f,
                    caption=f"📄 {base_name}\n_Developed by Vishnavi Gokarnam_",
                    parse_mode="Markdown")
            try:
                _os.remove(path)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[c30] send fail: {e}")
            safe_send(uid, f"⚠️ PDF send failed. Text:\n\n{content[:3000]}")
            return False
    safe_send(uid, f"⚠️ PDF failed. Text:\n\n{content[:3000]}")
    return False

for _n in ["md2pdf", "generate_pdf", "pdf_from_markdown", "create_pdf",
           "pandoc_pdf", "md_to_pdf", "convert_to_pdf", "text_to_pdf",
           "notes_to_pdf", "build_pdf", "render_pdf"]:
    _bt.__dict__[_n] = make_pdf

import sys as _sys
_main = _sys.modules.get("__main__")
if _main:
    for _n in ["md2pdf", "generate_pdf", "pdf_from_markdown", "create_pdf",
               "pandoc_pdf", "md_to_pdf", "convert_to_pdf", "text_to_pdf",
               "notes_to_pdf", "build_pdf", "render_pdf"]:
        setattr(_main, _n, make_pdf)


@bot.message_handler(commands=['barrier_test'])
def cmd_barrier_test(message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    sample = (
        r"Energy: $\phi = \tan^{-1}\!\left(\dfrac{X_L - X_C}{R}\right)$" "\n\n"
        r"Power: $P_{avg} = V_{rms} I_{rms} \cos\phi = I_{rms}^2 R$" "\n\n"
        r"Transformer: $\displaystyle \frac{N_s}{N_p} = \frac{V_s}{V_p}$" "\n\n"
        r"Matrix: $\begin{bmatrix} 1 & 2 \\ 3 & 4 \end{bmatrix}$"
    )
    safe_send(message.chat.id, sample)


@bot.message_handler(commands=['pdf_test'])
def cmd_pdf_test(message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    sample = ("# PDF Test\n\n"
              "Matrix: [ 1 2 ; 3 4 ]\n\n"
              "Formula: int_0^inf e^(-t^2) dt = sqrt(pi)/2\n\n"
              "Greek: α β γ θ π √ Ω ² ³\n\n"
              "Developed by Vishnavi Gokarnam")
    send_pdf_to_user(message.chat.id, sample, "pdf_test")


print("bot.py Chunk 30 loaded: 4-barrier + PDF (Unicode font) ready.")
