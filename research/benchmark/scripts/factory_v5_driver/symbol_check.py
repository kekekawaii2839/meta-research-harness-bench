"""Controller notation check for Markdown/LaTeX deliverables (no model calls; heuristic FLAGS, not scores).

Lists math symbols (base letter or Greek command plus subscript, with style: plain / bold / calligraphic /
blackboard) whose occurrences never share a sentence with a definition cue ("where", "denotes", "let", "is the",
...), and letters used in two styles (e.g. italic A and bold A). The judge must confirm or refute every candidate:
heuristics miss definitions given in tables or prior sections and can over-flag indices. Introduced for judge v3.9
after v3.7/v3.8 graded comprehensibility 4 on "every symbol is defined" while symbols were undefined.
"""
from pathlib import Path
import json
import re

GREEK = ("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi rho sigma tau "
         "upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Phi Psi Omega").split()
STYLE = {"mathbf": "bold", "boldsymbol": "bold", "bm": "bold", "mathcal": "cal", "mathbb": "bb", "mathfrak": "frak"}
DROP_ARG = r"\\(?:text|mathrm|operatorname|textrm|textit|textbf|mbox|label|tag)\s*\{[^{}]*\}"
FUNCS = {"sin", "cos", "tan", "log", "exp", "max", "min", "arg", "argmax", "argmin", "det", "tr", "lim", "sup", "inf", "mod", "dim"}
CUE = re.compile(r"\b(where|wherein|denot\w*|defin\w*|let|is the|are the|is a|is an|be the|stands? for|refers? to|represents?|"
                 r"called|given by|we write|is set to|are set to|equals?|is fixed|are fixed|index(?:es)?|indicates?)\b|:=", re.I)
MATH = re.compile(r"\$\$(.+?)\$\$|\$([^$\n]+?)\$", re.S)


def _symbols(tex):
    # keep text subscripts (alpha_{\text{MEI}} -> alpha_{MEI}) before dropping text arguments
    tex = re.sub(r"_\{\s*\\(?:text|mathrm|textrm|operatorname)\s*\{([^{}]*)\}\s*\}", r"_{\1}", tex)
    tex = re.sub(DROP_ARG, " ", tex)
    out = []
    for m in re.finditer(r"\\(tilde|hat|bar|widetilde|widehat|overline|dot)\s*\{\s*(\\?[A-Za-z]+)\s*\}((?:_\{[^{}]*\}|_\\?[A-Za-z0-9]+)?)", tex):
        out.append((m.group(1).replace("wide", ""), m.group(2).lstrip("\\"), _sub(m.group(3))))
    tex = re.sub(r"\\(tilde|hat|bar|widetilde|widehat|overline|dot)\s*\{[^{}]*\}((?:_\{[^{}]*\}|_\\?[A-Za-z0-9]+)?)", " ", tex)
    for m in re.finditer(r"\\(mathbf|boldsymbol|bm|mathcal|mathbb|mathfrak)\s*\{\s*(\\?[A-Za-z]+)\s*\}((?:_\{[^{}]*\}|_\\?[A-Za-z0-9]+)?)", tex):
        base = m.group(2).lstrip("\\")
        out.append((STYLE[m.group(1)], base, _sub(m.group(3))))
    tex = re.sub(r"\\(mathbf|boldsymbol|bm|mathcal|mathbb|mathfrak)\s*\{[^{}]*\}((?:_\{[^{}]*\}|_\\?[A-Za-z0-9]+)?)", " ", tex)
    for m in re.finditer(r"\\([A-Za-z]+)((?:_\{[^{}]*\}|_\\?[A-Za-z0-9]+)?)", tex):
        if m.group(1) in GREEK:
            out.append(("plain", m.group(1), _sub(m.group(2))))
    tex = re.sub(r"\\[A-Za-z]+", " ", tex)
    for m in re.finditer(r"(?<![A-Za-z])([A-Za-z])((?:_\{[^{}]*\}|_[A-Za-z0-9])?)(?![A-Za-z])", tex):
        out.append(("plain", m.group(1), _sub(m.group(2))))
    return out


def _sub(s):
    s = (s or "").lstrip("_").strip("{}").replace("\\", "").replace(" ", "")
    return s


def _unused_sentences(text):
    """(start, end) spans split at sentence ends outside math."""
    spans, start, i, inmath = [], 0, 0, False
    while i < len(text):
        if text.startswith("$$", i):
            inmath = not inmath
            i += 2
            continue
        c = text[i]
        if c == "$":
            inmath = not inmath
        elif not inmath and (c == "\n" and text.startswith("\n", i + 1) or c in ".;" and i + 1 < len(text) and text[i + 1] in " \n"):
            spans.append((start, i + 1))
            start = i + 1
        i += 1
    spans.append((start, len(text)))
    return spans


def check_text(text):
    """A symbol counts as defined when (a) it occurs in a short inline math span (<= 60 chars) with a definition cue
    in the plain text within 60 characters before or after that span, or (b) it is the whole left-hand side of an
    '=' or ':=' in any math span. Occurrences in long or display equations alone never define a symbol."""
    occ, defined = {}, {}
    for m in MATH.finditer(text):
        tex = m.group(1) or m.group(2)
        syms = [k for k in _symbols(tex) if k[1].lower() not in FUNCS]
        line = text.count(chr(10), 0, m.start()) + 1
        for k in syms:
            occ.setdefault(k, []).append(line)
        if m.group(2) is not None and len(tex) <= 60:
            around = re.sub(MATH, " ", text[max(0, m.start() - 60):m.start()] + " " + text[m.end():m.end() + 60])
            if CUE.search(around):
                for k in syms:
                    defined.setdefault(k, line)
        for part in re.split(r"\\\\|\\quad|\\qquad|,|;", tex):
            lhs = re.split(r":=|(?<![<>!])=(?!=)", part, maxsplit=1)
            if len(lhs) == 2:
                ls = _symbols(lhs[0])
                if len(ls) == 1:
                    defined.setdefault(ls[0], line)

    def name(st, b, sb):
        return ("%s %s" % (st, b) if st != "plain" else b) + ("_" + sb if sb else "")
    undefined = [{"symbol": name(*k), "occurrences": len(lines), "first_line": lines[0]}
                 for k, lines in occ.items() if k not in defined]
    late = [{"symbol": name(*k), "first_use_line": lines[0], "first_definition_line": defined[k]}
            for k, lines in occ.items() if k in defined and lines[0] + 5 < defined[k]]
    styles = {}
    for (st, b, sb) in occ:
        styles.setdefault(b, set()).add(st)
    clashes = [{"letter": b, "styles": sorted(x)} for b, x in styles.items() if len(x) > 1 and len(b) == 1]
    undefined.sort(key=lambda x: (-x["occurrences"], x["first_line"]))
    return {"symbols_found": len(occ), "candidate_undefined": undefined[:200], "candidate_undefined_count": len(undefined),
            "candidate_used_before_definition": late[:200], "style_clashes": clashes}


def check(artifacts_dir):
    files = {}
    for p in sorted(Path(artifacts_dir).rglob("*.md")):
        if "h0_notes" in p.parts:
            continue
        text = p.read_text(encoding="utf8", errors="replace")
        if "$" in text:
            files[str(p.relative_to(artifacts_dir)).replace("\\", "/")] = check_text(text)
    return {"schema_version": "symbol-check-1",
            "what": ("Heuristic notation check of the solver's Markdown/LaTeX deliverables: symbols (with subscript and "
                     "style) none of whose sentences contains a definition cue, and letters used in two styles. "
                     "CANDIDATES ONLY: definitions in tables, earlier sections or the task's notation list are not "
                     "recognised, and indices may be over-flagged. Confirm or refute each before relying on it."),
            "files": files}


if __name__ == "__main__":
    import sys
    print(json.dumps(check(sys.argv[1]), ensure_ascii=False, indent=1))
