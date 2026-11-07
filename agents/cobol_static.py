"""Static (no-LLM) COBOL analysis shared by the understanding agents.

Deterministic facts - PIC sizes, the ACCEPT record layout, arithmetic stored without
ROUNDED - are computed here and handed to the models, so the models only have to
explain them, not discover them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Keyword boundary that respects COBOL hyphenated names (ON is not inside ON-HAND).
def kw(words: str) -> str:
    return rf"(?<![A-Za-z0-9-])(?:{words})(?![A-Za-z0-9-])"


NAME = r"[A-Za-z0-9][A-Za-z0-9_-]*"
_LITERAL = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
_SEQ_AREA = re.compile(r"^[0-9 ]{6}$")
_STOP = re.compile(
    kw(
        "ACCEPT|ADD|CALL|COMPUTE|CONTINUE|DISPLAY|DIVIDE|ELSE|END-ADD|END-COMPUTE|END-DIVIDE|"
        "END-EVALUATE|END-IF|END-MULTIPLY|END-PERFORM|END-SUBTRACT|EVALUATE|EXIT|GO|GOBACK|IF|"
        "INITIALIZE|INSPECT|MOVE|MULTIPLY|NOT|ON|PERFORM|SET|SIZE|STOP|STRING|SUBTRACT|UNSTRING|WHEN"
    )
    + r"|\.(?=\s|$)",
    re.I,
)
_NOT_NAMES = {"ROUNDED", "GIVING", "REMAINDER", "BY", "TO", "FROM", "INTO", "OF", "IN", "ZERO", "ZEROS", "ZEROES"}


# --------------------------------------------------------------------------- source text

def _cut_inline_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif line.startswith("*>", i):
            return line[:i]
    return line


def strip_comments(src: str) -> str:
    """Blank out comments but keep line numbering identical to the original file."""
    out = []
    for line in src.expandtabs(4).splitlines():
        if len(line) >= 7 and _SEQ_AREA.match(line[:6]) and line[6] in "*/":
            out.append("")  # fixed-format comment line
            continue
        if len(line) >= 6 and line[:6].isdigit():
            line = "      " + line[6:]  # sequence numbers
        out.append(_cut_inline_comment(line))
    return "\n".join(out)


def literal_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _LITERAL.finditer(text)]


def _inside(pos: int, spans) -> bool:
    return any(a <= pos < b for a, b in spans)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def program_id(src: str) -> str | None:
    m = re.search(r"PROGRAM-ID\s*\.\s*['\"]?(" + NAME + ")", strip_comments(src), re.I)
    return m.group(1).upper() if m else None


def find_calls(src: str) -> tuple[list[str], list[str]]:
    """(static CALL 'X' targets, dynamic CALL identifier names)."""
    text = strip_comments(src)
    spans = literal_spans(text)
    static, dynamic = [], []
    for m in re.finditer(kw("CALL") + r"\s+(?:(['\"])([^'\"\n]+)\1|(" + NAME + "))", text, re.I):
        if _inside(m.start(), spans):
            continue
        if m.group(2):
            static.append(m.group(2).strip().upper())
        else:
            dynamic.append(m.group(3).upper())
    return _dedupe(static), _dedupe(dynamic)


def find_copies(src: str) -> list[str]:
    text = strip_comments(src)
    spans = literal_spans(text)
    out = []
    for m in re.finditer(kw("COPY") + r"\s+(?:(['\"])([^'\"\n]+)\1|(" + NAME + r"(?:\.[A-Za-z0-9]+)?))", text, re.I):
        if not _inside(m.start(), spans):
            out.append((m.group(2) or m.group(3)).strip().rstrip("."))
    return _dedupe(out)


def _dedupe(items):
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# --------------------------------------------------------------------------- PIC clauses

def expand_pic(pic: str) -> str:
    return re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())


@dataclass
class Field:
    level: int
    name: str
    line: int
    section: str = ""
    pic: str | None = None
    usage: str = "DISPLAY"
    value: str | None = None
    occurs: int = 1
    redefines: str | None = None
    sign_separate: bool = False
    kind: str = "group"  # group | numeric | alphanumeric | edited
    signed: bool = False
    int_digits: int = 0
    decimals: int = 0
    length: int = 0
    offset: int = 0
    children: list = field(default_factory=list)
    conditions: list = field(default_factory=list)  # [(88-name, raw values)]

    @property
    def is_elementary(self) -> bool:
        return self.pic is not None

    def describe(self) -> str:
        if self.kind == "group":
            return f"group, {self.length} chars"
        if self.kind == "alphanumeric":
            return f"PIC {self.pic}: text, {self.length} chars"
        if self.kind == "edited":
            return (f"PIC {self.pic}: display-edited number, {self.length} chars wide, "
                    f"{self.decimals} decimals shown{', shows sign' if self.signed else ''}")
        sign = "signed" if self.signed else "unsigned"
        mx = "9" * self.int_digits + ("." + "9" * self.decimals if self.decimals else "")
        dec = f" + {self.decimals} implied decimals (no decimal point stored)" if self.decimals else ""
        usage = f", USAGE {self.usage}" if self.usage != "DISPLAY" else ""
        return f"PIC {self.pic}: {sign} number, {self.int_digits} integer digits{dec}, max {mx or '0'}{usage}"


def _apply_pic(f: Field) -> None:
    e = expand_pic(f.pic)
    body = e[1:] if e.startswith("S") else e
    if body and set(body) <= set("9VP"):
        f.kind = "numeric"
        f.signed = e.startswith("S")
        int_part, _, dec_part = body.partition("V")
        f.int_digits, f.decimals = int_part.count("9"), dec_part.count("9")
        digits = f.int_digits + f.decimals
        if f.usage in ("COMP-3", "PACKED-DECIMAL"):
            f.length = digits // 2 + 1
        elif f.usage in ("COMP", "COMP-4", "COMP-5", "BINARY"):
            f.length = 2 if digits <= 4 else 4 if digits <= 9 else 8
        else:
            f.length = digits + (1 if f.sign_separate else 0)
    elif body and set(body) <= set("XA9"):
        f.kind, f.length = "alphanumeric", len(body)
    else:
        f.kind = "edited"
        f.signed = any(t in e for t in ("+", "-", "CR", "DB"))
        f.length = len(e.replace("V", ""))
        if "." in e:
            f.decimals = sum(1 for c in e.split(".", 1)[1] if c in "9Z*")
        f.int_digits = sum(1 for c in e.split(".", 1)[0] if c in "9Z*")


_ENTRY = re.compile(r"^\s*(\d{1,2})(?:\s+(" + NAME + r"))?(.*)$", re.S)
_CLAUSE_WORDS = {"PIC", "PICTURE", "VALUE", "VALUES", "REDEFINES", "OCCURS", "USAGE", "COMP", "COMP-3",
                 "COMP-5", "BINARY", "PACKED-DECIMAL", "SIGN"}


def _parse_entry(text: str, line: int, section: str) -> Field | None:
    m = _ENTRY.match(text)
    if not m:
        return None
    level, name, rest = int(m.group(1)), m.group(2) or "FILLER", m.group(3)
    if name.upper() in _CLAUSE_WORDS:
        rest, name = f"{name} {rest}", "FILLER"
    f = Field(level=level, name=name.upper(), line=line, section=section)
    if level == 88:
        vm = re.search(kw("VALUES?") + r"\s+(?:IS\s+|ARE\s+)?(.+)$", rest, re.I | re.S)
        f.value = " ".join(vm.group(1).split()) if vm else ""
        return f
    if pm := re.search(kw("PIC|PICTURE") + r"\s+(?:IS\s+)?(\S+)", rest, re.I):
        f.pic = pm.group(1).upper().rstrip(".")
    if um := re.search(kw("COMP-3|COMP-4|COMP-5|COMPUTATIONAL-3|COMP|COMPUTATIONAL|BINARY|PACKED-DECIMAL"), rest, re.I):
        f.usage = um.group(0).upper().replace("COMPUTATIONAL", "COMP")
    if om := re.search(kw("OCCURS") + r"\s+(\d+)", rest, re.I):
        f.occurs = int(om.group(1))
    if rm := re.search(kw("REDEFINES") + r"\s+(" + NAME + ")", rest, re.I):
        f.redefines = rm.group(1).upper()
    if vm := re.search(kw("VALUE") + r"\s+(?:IS\s+)?('[^']*'|\"[^\"]*\"|\S+)", rest, re.I):
        f.value = vm.group(1)
    f.sign_separate = bool(re.search(kw("SEPARATE"), rest, re.I))
    if f.pic:
        _apply_pic(f)
    return f


def _layout(f: Field, offset: int) -> int:
    f.offset = offset
    if f.is_elementary:
        return f.length
    size, pos = 0, offset
    for c in f.children:
        n = _layout(c, pos) * c.occurs
        if c.redefines:
            continue
        size += n
        pos += n
    f.length = size
    return size


def parse_data_division(clean: str) -> tuple[list[Field], dict[str, Field]]:
    dm = re.search(kw("DATA") + r"\s+DIVISION", clean, re.I)
    pm = re.search(kw("PROCEDURE") + r"\s+DIVISION", clean, re.I)
    if not dm:
        return [], {}
    start, end = dm.end(), pm.start() if pm else len(clean)
    text = clean[start:end]
    tops: list[Field] = []
    index: dict[str, Field] = {}
    stack: list[Field] = []
    section, prev = "", 0
    for t in re.finditer(r"\.(?=\s|$)", text + " "):
        chunk, chunk_start, prev = text[prev:t.start()], start + prev, t.end()
        sm = re.match(r"^\s*([A-Za-z-]+)\s+SECTION\s*$", chunk, re.I)
        if sm:
            section = sm.group(1).upper()
            continue
        f = _parse_entry(chunk, line_of(clean, chunk_start + len(chunk) - len(chunk.lstrip())), section)
        if not f:
            continue
        if f.level == 88:
            if stack:
                stack[-1].conditions.append((f.name, f.value))
            continue
        if f.level == 66:
            continue
        if f.level in (1, 77):
            stack = [f]
            tops.append(f)
        else:
            while stack and stack[-1].level >= f.level:
                stack.pop()
            (stack[-1].children if stack else tops).append(f)
            stack.append(f)
        if f.name != "FILLER":
            index.setdefault(f.name, f)
    for t in tops:
        _layout(t, 0)
    return tops, index


def leaves(f: Field) -> list[Field]:
    if f.is_elementary:
        return [f]
    return [leaf for c in f.children if not c.redefines for leaf in leaves(c)]


# --------------------------------------------------------------------------- subprogram parameters

_USING = re.compile(kw("PROCEDURE") + r"\s+DIVISION\s+USING\s+(.*?)(?:\.(?=\s|$)|" + kw("RETURNING") + ")",
                    re.I | re.S)
_USING_NOISE = {"BY", "REFERENCE", "VALUE", "CONTENT", "OPTIONAL"}


def using_names(src: str) -> list[str]:
    """Names after PROCEDURE DIVISION USING, in order (BY REFERENCE/VALUE words dropped)."""
    m = _USING.search(strip_comments(src))
    if not m:
        return []
    return [t.upper() for t in re.findall(NAME, m.group(1)) if t.upper() not in _USING_NOISE]


def param_of(f: Field) -> dict:
    """contract.Param for one LINKAGE item. Group items are text of their total length."""
    if f.kind == "numeric":
        return {"name": f.name, "pic": f.pic, "kind": "numeric", "int_digits": f.int_digits,
                "dec_digits": f.decimals, "length": f.int_digits + f.decimals, "signed": f.signed}
    return {"name": f.name, "pic": f.pic or f"X({f.length})", "kind": "text", "int_digits": 0,
            "dec_digits": 0, "length": f.length, "signed": False}


def linkage_params(src: str) -> list[dict]:
    """PROCEDURE DIVISION USING parameters as contract.Param dicts; [] for a main program."""
    names = using_names(src)
    if not names:
        return []
    _, index = parse_data_division(strip_comments(src))
    missing = [n for n in names if n not in index]
    if missing:
        raise ValueError(f"USING names not declared in the DATA DIVISION: {missing}")
    return [param_of(index[n]) for n in names]


def edited_pic(p: dict) -> str:
    """Display PIC the test driver shows a numeric param with: 9(i).9(d), 9(i), .9(d), leading '-' if signed."""
    i, d = p["int_digits"], p["dec_digits"]
    body = (f"9({i})" if i else "") + (f".9({d})" if d else "")
    return ("-" if p["signed"] else "") + (body or "9")


# --------------------------------------------------------------------------- procedure division

@dataclass
class Arith:
    line: int
    verb: str
    targets: list  # [(name, rounded)]
    operands: str
    size_error: bool
    notes: list = field(default_factory=list)
    truncation_targets: list = field(default_factory=list)


def _stmt_end(text: str, pos: int) -> int:
    m = _STOP.search(text, pos)
    return m.start() if m else len(text)


def _targets(chunk: str) -> list[tuple[str, bool]]:
    chunk = re.sub(r"\([^)]*\)", " ", chunk)
    toks = re.findall(NAME, chunk)
    out = []
    for i, tok in enumerate(toks):
        if tok.upper() in _NOT_NAMES or tok[0].isdigit():
            continue
        rounded = i + 1 < len(toks) and toks[i + 1].upper() == "ROUNDED"
        out.append((tok.upper(), rounded))
    return out


def _has_size_error(text: str, pos: int) -> bool:
    return bool(re.match(r"\s*(?:ON\s+)?SIZE\s+ERROR", text[pos:], re.I))


def _operand_decimals(expr: str, index: dict[str, Field]) -> list[int]:
    decs = [len(m.group(1)) for m in re.finditer(r"(?<![A-Za-z0-9-])\d+\.(\d+)", expr)]
    for tok in re.findall(NAME, expr):
        f = index.get(tok.upper())
        if f and f.kind == "numeric":
            decs.append(f.decimals)
    return decs


def _example(f: Field) -> str:
    whole = "12" if f.int_digits >= 2 else "1"
    if f.decimals:
        kept = "3" * f.decimals
        return f"{whole}.{kept}9 is stored as {whole}.{kept}, not {whole}.{'3' * (f.decimals - 1)}4"
    return f"{whole}.7 is stored as {whole}, not {int(whole) + 1}"


def _annotate(a: Arith, index: dict[str, Field], has_div: bool, has_mul: bool) -> None:
    decs = _operand_decimals(a.operands, index)
    for name, rounded in a.targets:
        f = index.get(name)
        if not f or f.kind != "numeric":
            continue
        loses_decimals = has_div or (has_mul and sum(decs) > f.decimals) or (decs and max(decs) > f.decimals)
        if loses_decimals and not rounded:
            a.truncation_targets.append(name)
            a.notes.append(
                f"{name} ({f.describe()}) is stored WITHOUT ROUNDED: digits beyond {f.decimals} decimal "
                f"place(s) are TRUNCATED, not rounded (e.g. {_example(f)})."
            )
        if not a.size_error:
            a.notes.append(
                f"No ON SIZE ERROR: a result above {'9' * f.int_digits or '0'}"
                f"{'.' + '9' * f.decimals if f.decimals else ''} silently loses its high-order digits in {name}."
            )
        if not f.signed and (a.verb == "SUBTRACT" or "-" in re.sub(NAME, "", a.operands)):
            a.notes.append(f"{name} is unsigned: a negative result is stored without its sign.")


def find_arithmetic(proc: str, base: int, clean: str, index: dict[str, Field]) -> list[Arith]:
    out = []
    spans = literal_spans(proc)
    for m in re.finditer(kw("COMPUTE"), proc, re.I):
        if _inside(m.start(), spans):
            continue
        eq = proc.find("=", m.end())
        if eq < 0:
            continue
        end = _stmt_end(proc, eq + 1)
        expr = " ".join(proc[eq + 1:end].split())
        a = Arith(line_of(clean, base + m.start()), "COMPUTE", _targets(proc[m.end():eq]), expr,
                  _has_size_error(proc, end))
        _annotate(a, index, "/" in expr, "*" in expr)
        out.append(a)
    for m in re.finditer(kw("ADD|SUBTRACT|MULTIPLY|DIVIDE"), proc, re.I):
        if _inside(m.start(), spans):
            continue
        verb = m.group(0).upper()
        end = _stmt_end(proc, m.end())
        stmt = proc[m.end():end]
        g = re.search(kw("GIVING"), stmt, re.I)
        if g:
            operands, tgt = stmt[:g.start()], re.split(kw("REMAINDER"), stmt[g.end():], flags=re.I)[0]
        else:
            sep = {"ADD": "TO", "SUBTRACT": "FROM", "MULTIPLY": "BY", "DIVIDE": "INTO"}[verb]
            parts = re.split(kw(sep), stmt, maxsplit=1, flags=re.I)
            if len(parts) < 2:
                continue
            operands, tgt = parts
            operands = f"{operands} {tgt}"
        a = Arith(line_of(clean, base + m.start()), verb, _targets(tgt), " ".join(operands.split()),
                  _has_size_error(proc, end))
        _annotate(a, index, verb == "DIVIDE", verb == "MULTIPLY")
        out.append(a)
    # MOVE can discard fractional cents too; it is the invoice's actual quirk.
    for m in re.finditer(kw("MOVE") + r"\s+(" + NAME + r")\s+TO\s+(" + NAME + r")", proc, re.I):
        if _inside(m.start(), spans):
            continue
        source, target = (index.get(n.upper()) for n in m.groups())
        if source and target and source.kind == target.kind == "numeric" and source.decimals > target.decimals:
            a = Arith(line_of(clean, base + m.start()), "MOVE", [(target.name, False)], source.name, False)
            _annotate(a, index, False, False)
            out.append(a)
    return sorted(out, key=lambda a: a.line)


@dataclass
class Analysis:
    program_id: str | None
    fields: list
    index: dict
    accept_targets: list
    input_layout: list  # [{name, start, end, length, pic, meaning}]
    input_width: int
    arithmetic: list
    branches: list  # [(line, text)]
    displays: list  # [(line, text)]
    calls: list
    dynamic_calls: list
    copies: list
    delimiter: str | None = None
    delimited_fields: list = field(default_factory=list)
    kind: str = "program"  # "subprogram" = PROCEDURE DIVISION USING ...
    params: list = field(default_factory=list)  # contract.Param dicts, USING order

    @property
    def truncation_targets(self) -> list[str]:
        return _dedupe(t for a in self.arithmetic for t in a.truncation_targets)


def analyze(src: str) -> Analysis:
    clean = strip_comments(src)
    tops, index = parse_data_division(clean)
    pm = re.search(kw("PROCEDURE") + r"\s+DIVISION", clean, re.I)
    base = pm.start() if pm else len(clean)
    proc = clean[base:]
    spans = literal_spans(proc)

    accepts = []
    for m in re.finditer(kw("ACCEPT") + r"\s+(" + NAME + r")(\s+FROM\s+(" + NAME + "))?", proc, re.I):
        source = (m.group(3) or "").upper()
        if not _inside(m.start(), spans) and source in ("", "CONSOLE", "SYSIN", "STDIN"):
            accepts.append(m.group(1).upper())
    accepts = _dedupe(accepts)

    layout, width = [], 0
    if accepts and accepts[0] in index:
        target = index[accepts[0]]
        for leaf in leaves(target):
            start = leaf.offset - target.offset
            layout.append({"name": leaf.name, "start": start + 1, "end": start + leaf.length,
                           "length": leaf.length, "pic": leaf.pic, "meaning": leaf.describe(),
                           "conditions": leaf.conditions})
        width = target.length

    delimiter, delimited_fields = None, []
    # A text ACCEPT buffer is storage capacity, not the external record width.
    pattern = (kw("UNSTRING") + r"\s+(" + NAME + r")\s+DELIMITED\s+BY\s+"
               r"(['\"])([^'\"\n]+)\2\s+INTO\s+(.*?)\s+END-UNSTRING")
    for m in re.finditer(pattern, proc, re.I | re.S):
        if _inside(m.start(), spans) or m.group(1).upper() not in accepts:
            continue
        delimiter = m.group(3)
        for raw in re.findall(NAME, m.group(4)):
            raw = raw.upper()
            conversion = re.search(kw("MOVE") + r"\s+(?:FUNCTION\s+)?NUMVAL\s*\(\s*"
                                   + re.escape(raw) + r"\s*\)\s+TO\s+(" + NAME + r")", proc, re.I)
            target = index.get(conversion.group(1).upper() if conversion else raw)
            if target:
                delimited_fields.append({"name": target.name, "raw": raw, "pic": target.pic,
                                         "type": "decimal" if target.decimals else "integer" if target.kind == "numeric" else "string",
                                         "meaning": target.describe()})
        layout, width = [], 0
        break

    def raw_lines(pattern):
        out = []
        for m in re.finditer(pattern, proc, re.I):
            if _inside(m.start(), spans):
                continue
            eol = proc.find("\n", m.start())
            out.append((line_of(clean, base + m.start()), proc[m.start():eol if eol > 0 else None].strip()))
        return out

    using = using_names(src)
    params = [param_of(index[n]) for n in using if n in index]
    kind = "subprogram" if using else "program"
    if kind == "subprogram" and delimiter is None:
        # Tested through make_driver: one "|"-separated token per param, USING order.
        delimiter = "|"
        delimited_fields = [{"name": p["name"], "raw": f"T{i}", "pic": p["pic"],
                             "type": ("decimal" if p["dec_digits"] else "integer") if p["kind"] == "numeric" else "string",
                             "meaning": index[p["name"]].describe()} for i, p in enumerate(params, 1)]

    calls, dynamic = find_calls(src)
    return Analysis(
        program_id=program_id(src), fields=tops, index=index, accept_targets=accepts,
        input_layout=layout, input_width=width,
        arithmetic=find_arithmetic(proc, base, clean, index),
        branches=raw_lines(kw("IF|WHEN|EVALUATE|UNTIL")), displays=raw_lines(kw("DISPLAY")),
        calls=calls, dynamic_calls=dynamic, copies=find_copies(src),
        delimiter=delimiter, delimited_fields=delimited_fields, kind=kind, params=params,
    )


def render_summary(a: Analysis, max_fields: int = 60) -> str:
    """Compact plain-text fact sheet that goes into the prompts."""
    out = [f"PROGRAM-ID: {a.program_id or '?'}"]
    if a.kind == "subprogram":
        names = [p["name"] for p in a.params]
        out.append(f"\nSUBPROGRAM: no ACCEPT of its own; CALLed with USING {' '.join(names)}.")
        out.append("It is tested through a generated test driver that reads ONE line of '|'-separated tokens,")
        out.append("one per parameter (numbers typed with a literal decimal point, read with NUMVAL;")
        out.append("an empty numeric token is 0, an empty text token is spaces), CALLs it, and prints the")
        out.append("parameters after the call.")
        out.append(f"INPUT LINE (test driver): {'|'.join(names)}")
        for i, p in enumerate(a.params, 1):
            out.append(f"  token {i}: {p['name']} - {a.index[p['name']].describe()}")
        shown = [f"{p['name']}={edited_pic(p)}" if p["kind"] == "numeric" else f"{p['name']}=<{p['length']} chars as stored>"
                 for p in a.params]
        out.append(f"OUTPUT LINE (test driver): {'|'.join(shown)}")
    elif a.delimiter is not None:
        out.append(f"\nINPUT LINE: variable-length tokens separated by {a.delimiter!r}; literal decimal points are typed.")
        out.append("The ACCEPT text buffer is capacity, NOT a required line length. Do not pad to it.")
        for i, f in enumerate(a.delimited_fields, 1):
            out.append(f"  token {i}: {f['name']} via NUMVAL({f['raw']}) - {f['meaning']}")
        out.append("Numeric PICs describe internal storage; consult validation and IF checks for allowed input ranges.")
    elif a.input_layout:
        out.append(f"\nINPUT LINE (ACCEPT {a.accept_targets[0]}): fixed width, {a.input_width} characters total")
        for f in a.input_layout:
            cond = "; values: " + ", ".join(f"{n}={v}" for n, v in f["conditions"]) if f["conditions"] else ""
            out.append(f"  cols {f['start']}-{f['end']}: {f['name']} - {f['meaning']}{cond}")
    elif a.accept_targets:
        out.append(f"\nINPUT: ACCEPT {', '.join(a.accept_targets)} (layout not found - read the source)")
    else:
        out.append("\nINPUT: no ACCEPT found (subprogram? parameters come through LINKAGE SECTION)")

    elementary = [f for t in a.fields for f in leaves(t)] if a.fields else []
    if elementary:
        out.append("\nFIELDS:")
        for f in elementary[:max_fields]:
            sec = f" [{f.section}]" if f.section and f.section != "WORKING-STORAGE" else ""
            cond = "; 88-levels: " + ", ".join(f"{n}={v}" for n, v in f.conditions) if f.conditions else ""
            out.append(f"  {f.name}{sec}: {f.describe()}{cond}")
    if a.arithmetic:
        out.append("\nARITHMETIC (static check):")
        for s in a.arithmetic:
            tg = ", ".join(n + (" ROUNDED" if r else "") for n, r in s.targets)
            out.append(f"  line {s.line}: {s.verb} -> {tg} | {s.operands}")
            out.extend(f"      ! {n}" for n in s.notes)
    if a.branches:
        out.append("\nBRANCHES:")
        out.extend(f"  line {ln}: {t}" for ln, t in a.branches)
    if a.displays:
        out.append("\nDISPLAY STATEMENTS:")
        out.extend(f"  line {ln}: {t}" for ln, t in a.displays)
    if a.calls or a.dynamic_calls:
        out.append("\nCALLS: " + ", ".join(a.calls + [f"{d} (dynamic)" for d in a.dynamic_calls]))
    if a.copies:
        out.append("COPYBOOKS: " + ", ".join(a.copies))
    return "\n".join(out)


def numbered(src: str) -> str:
    return "\n".join(f"{i:4}| {line}" for i, line in enumerate(src.splitlines(), 1))
