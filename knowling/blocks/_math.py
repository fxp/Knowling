"""Tiny self-contained LaTeX→HTML renderer for inline/display math.

Covers the subset LLMs actually emit in learning content: Greek letters, \\frac,
super/subscripts, \\sqrt, function names (\\sin…), common operators/relations,
\\left/\\right, \\text. No KaTeX/MathJax, no external assets — just HTML + CSS
(see the .kl-math* rules in assembler), so cards stay self-contained.

It is intentionally lenient: unknown commands are dropped rather than shown raw,
so a card never displays `\\frac` or `$` literals to a learner.
"""

from __future__ import annotations

import html as _html
import re


def esc(s) -> str:
    return _html.escape("" if s is None else str(s), quote=True)

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "varpi": "ϖ", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
SYMBOLS = {
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓", "ast": "∗",
    "star": "⋆", "circ": "∘", "bullet": "•", "leq": "≤", "le": "≤", "geq": "≥",
    "ge": "≥", "neq": "≠", "ne": "≠", "equiv": "≡", "approx": "≈", "sim": "∼",
    "cong": "≅", "propto": "∝", "infty": "∞", "partial": "∂", "nabla": "∇",
    "cdots": "⋯", "ldots": "…", "dots": "…", "to": "→", "rightarrow": "→",
    "Rightarrow": "⇒", "leftarrow": "←", "Leftarrow": "⇐", "leftrightarrow": "↔",
    "mapsto": "↦", "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆",
    "cup": "∪", "cap": "∩", "forall": "∀", "exists": "∃", "neg": "¬",
    "land": "∧", "lor": "∨", "sum": "∑", "prod": "∏", "int": "∫", "oint": "∮",
    "sqrt": "√", "angle": "∠", "perp": "⊥", "parallel": "∥", "degree": "°",
    "prime": "′", "dagger": "†", "ell": "ℓ", "Re": "ℜ", "Im": "ℑ", "hbar": "ℏ",
    "leftexp": "", "quad": " ", "qquad": "  ",
}
FUNCS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh", "tanh", "arcsin",
    "arccos", "arctan", "log", "ln", "lg", "exp", "lim", "max", "min", "sup",
    "inf", "det", "dim", "gcd", "deg", "arg", "mod",
}


def _read_name(s: str, i: int):
    j = i
    while j < len(s) and s[j].isalpha():
        j += 1
    return s[i:j], j


def _read_braced(s: str, i: int):
    """s[i] == '{' → (inner, index after matching '}')."""
    depth, j = 1, i + 1
    while j < len(s) and depth:
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
        j += 1
    return s[i + 1:j - 1], j


def _atom(s: str, i: int):
    """Render the operand of ^/_ : a {group}, a \\command, or one char."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        inner, j = _read_braced(s, i)
        return _parse(inner), j
    if s[i] == "\\":
        name, j = _read_name(s, i + 1)
        if name in GREEK:
            return GREEK[name], j
        if name in SYMBOLS:
            return SYMBOLS[name], j
        if name in FUNCS:
            return f'<span class="kl-mathrm">{name}</span>', j
        return "", j
    return esc(s[i]), i + 1


def _parse(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            name, i = _read_name(s, i + 1)
            if name == "frac":
                num, i = _atom(s, i)
                den, i = _atom(s, i)
                out.append(f'<span class="kl-frac"><span class="kl-num">{num}</span>'
                           f'<span class="kl-den">{den}</span></span>')
            elif name == "sqrt":
                arg, i = _atom(s, i)
                out.append(f'<span class="kl-sqrt">√<span class="kl-sqrt-arg">{arg}</span></span>')
            elif name in ("text", "mathrm", "mathbf", "mathsf", "operatorname"):
                if i < n and s[i] == "{":
                    raw, i = _read_braced(s, i)
                    out.append(f'<span class="kl-mathrm">{esc(raw)}</span>')
            elif name in ("left", "right"):
                if i < n:
                    d = s[i]; i += 1
                    out.append("" if d == "." else esc(d))
            elif name in GREEK:
                out.append(GREEK[name])
            elif name in SYMBOLS:
                out.append(SYMBOLS[name])
            elif name in FUNCS:
                out.append(f'<span class="kl-mathrm">{name}</span>')
            elif name == "":
                # backslash + non-letter: spacing or escaped char
                if i < n:
                    nx = s[i]
                    if nx in " ,;:!":
                        out.append(" ")
                    elif nx in "{}%$&_#":
                        out.append(esc(nx))
                    i += 1
            # unknown command → silently dropped
        elif c == "^":
            arg, i = _atom(s, i + 1)
            out.append(f"<sup>{arg}</sup>")
        elif c == "_":
            arg, i = _atom(s, i + 1)
            out.append(f"<sub>{arg}</sub>")
        elif c == "{":
            inner, i = _read_braced(s, i)
            out.append(_parse(inner))
        elif c == "}":
            i += 1
        else:
            out.append(esc(c))
            i += 1
    return "".join(out)


def render_math(src: str, display: bool = False) -> str:
    cls = "kl-math kl-math-display" if display else "kl-math"
    return f'<span class="{cls}">{_parse(src)}</span>'


_MATH_RE = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]|\$(.+?)\$|\\\((.+?)\\\)", re.DOTALL)


def has_math(text: str) -> bool:
    return bool(text) and bool(_MATH_RE.search(text))


def split_math(text: str):
    """Yield (segment, is_math, display) tuples covering ``text``."""
    pos = 0
    for m in _MATH_RE.finditer(text or ""):
        if m.start() > pos:
            yield text[pos:m.start()], False, False
        display = m.group(1) is not None or m.group(2) is not None
        inner = next(g for g in m.groups() if g is not None)
        yield inner, True, display
        pos = m.end()
    if pos < len(text or ""):
        yield text[pos:], False, False
