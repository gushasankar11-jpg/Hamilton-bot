# ==========================================================
# math_sanitizer.py — LaTeX → clean Unicode for Telegram
# ==========================================================
import re

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

# Commands that can appear with SPACE instead of braces: \mathbf n_1
_MOD_WORDS = ["mathbf", "mathrm", "mathit", "mathsf", "mathtt",
              "mathcal", "mathfrak", "text", "textbf", "textit",
              "textrm", "boldsymbol", "operatorname", "vec", "hat",
              "bar", "dot", "tilde", "overline", "underline"]

_MATRIX_ENV_RE = re.compile(
    r"\\begin\{(bmatrix|pmatrix|vmatrix|matrix|cases|aligned|array)\}"
    r"(\{[^}]*\})?"
    r"(.*?)"
    r"\\end\{\1\}",
    re.DOTALL,
)

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

def _replace_matrix_envs(text):
    if not text:
        return text
    def _conv(m):
        env = m.group(1)
        body = m.group(3)
        rows_raw = re.split(r"\\\\", body)
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
        return "\n" + _ascii_matrix(rows, style) + "\n"
    return _MATRIX_ENV_RE.sub(_conv, text)


def _to_unicode(text):
    if not text:
        return text
    s = text

    # Strip any HTML tags (Telegram rich doesn't render <pre> literally)
    s = re.sub(r"</?pre[^>]*>", "\n", s)
    s = re.sub(r"</?(?:b|i|u|code|strong|em)[^>]*>", "", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>\n]{1,40}>", "", s)

    # Strip [Npt] / [Nmm] markers
    s = re.sub(r"\[\d+(?:\.\d+)?(?:pt|mm|cm|ex|em)\]", " ", s)
    s = re.sub(r"\\\[\d+(?:\.\d+)?(?:pt|mm|cm|ex|em)\]", "\n", s)

    # \binom
    for _ in range(4):
        s = re.sub(r"\\binom\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"C(\1,\2)", s)

    # \frac family
    for _ in range(6):
        s = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)

    # \sqrt[n]{x} and \sqrt{x}
    for _ in range(5):
        s = re.sub(r"\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}", r"(\2)^(1/\1)", s)
    for _ in range(5):
        s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", s)

    # Strip modifier commands WITH braces: \mathbf{ABC}
    for cmd in _MOD_WORDS:
        s = re.sub(r"\\" + cmd + r"\s*\{([^{}]*)\}", r"\1", s)

    # Strip modifier commands WITH space: \mathbf ABC (no braces)
    for cmd in _MOD_WORDS:
        s = re.sub(r"\\" + cmd + r"\s+", "", s)

    # \boxed
    s = re.sub(r"\\boxed\s*\{([^{}]*)\}", r"[\1]", s)

    # Strip env braces
    s = re.sub(r"\\begin\s*\{[^{}]*\}", "", s)
    s = re.sub(r"\\end\s*\{[^{}]*\}", "", s)
    s = re.sub(r"\\begin\s*[a-zA-Z]+", "", s)
    s = re.sub(r"\\end\s*[a-zA-Z]+", "", s)

    # Subscripts: _{...} and _x
    sub_map = {"0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅",
               "6":"₆","7":"₇","8":"₈","9":"₉","n":"ₙ","i":"ᵢ",
               "j":"ⱼ","k":"ₖ","m":"ₘ","x":"ₓ","a":"ₐ","+":"₊",
               "-":"₋","=":"₌","r":"ᵣ","s":"ₛ","p":"ₚ","L":"ₗ"}
    def _sub(m):
        return "".join(sub_map.get(c, c) for c in m.group(1))
    s = re.sub(r"_\{([^}]+)\}", _sub, s)
    # plain _x → ₓ (single char after _)
    s = re.sub(r"_([0-9nijmxaprspL])", lambda m: sub_map.get(m.group(1), "_"+m.group(1)), s)

    # Superscripts: ^{...} and ^x
    sup_map = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵",
               "6":"⁶","7":"⁷","8":"⁸","9":"⁹","n":"ⁿ","+":"⁺","-":"⁻"}
    s = re.sub(r"\^\{([0-9n+\-])\}",
               lambda m: sup_map.get(m.group(1), "^"+m.group(1)), s)
    s = re.sub(r"\^([0-9n])", lambda m: sup_map.get(m.group(1), "^"+m.group(1)), s)

    # Symbol table
    for k, v in _SYM:
        s = s.replace(k, v)

    # Final cleanup
    s = s.replace(r"\\", "\n")
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("$$", "").replace("$", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def sanitize_math(text):
    if not text:
        return text
    text = _replace_matrix_envs(text)
    text = _to_unicode(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


if __name__ == "__main__":
    tests = [
        r"\theta$ is a constant parameter",
        r"\mathbf n_1=(1,1,1),\qquad \mathbf n_2=(2,-1,1)",
        r"Find $\frac{a}{b}$ when $x^2 + y^2 = r^2$",
        r"<pre> [x + y + z + 1 = 0 \\ 2x-y+z+3=0 ] </pre>",
        r"D=\frac{|a+15|}{\sqrt{42}}",
        r"\mathbf d_1 \times \mathbf d_2",
    ]
    for t in tests:
        print("IN : ", t)
        print("OUT: ", sanitize_math(t))
        print("---")
