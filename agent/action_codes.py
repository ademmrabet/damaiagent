import json
import re
from pathlib import Path

AUTHORITY_CODES_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reference" / "authority_codes.json"
)


def _load_authority_codes():
    with open(AUTHORITY_CODES_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["code"]: e for e in entries}


_CODES = _load_authority_codes()

_LEGEND_ORDER = ["I", "C", "C3", "R", "A", "( i )"]

_EXPLAIN_TRIGGER = re.compile(
    r"\b(what does|what's|what is|what are|whats|explain|mean|means|"
    r"meaning|stand for|stands for|define|definition)\b",
    re.IGNORECASE,
)

_GENERIC_LEGEND_TRIGGER = re.compile(
    r"\b(action codes?|authority codes?|the legend|these codes|"
    r"the letters|the abbreviations? [ia] c r a)\b",
    re.IGNORECASE,
)

_INFORMED_TOKEN = re.compile(r"\(\s*i\s*\)", re.IGNORECASE)

_BARE_CODE_TOKEN = re.compile(r"\b([ICRA][1-4]?)\b")
_SUFFIXED_CODE = re.compile(r"^[ICRA][1-4]$")


def _extract_code_tokens(query):
    """
    Returns the distinct action-code-shaped tokens found in `query`,
    in first-seen order. "(i)"/"( i )" is checked first and separately
    since the bare-letter regex can't see through the parentheses.
    """
    tokens = []
    seen = set()

    if _INFORMED_TOKEN.search(query):
        tokens.append("( i )")
        seen.add("( i )")

    for match in _BARE_CODE_TOKEN.findall(query):
        if match not in seen:
            seen.add(match)
            tokens.append(match)

    return tokens


def detect_action_code_query(query):
    """
    Returns {"codes": [...]} (specific codes asked about) or
    {"codes": None} (a generic "explain the codes" question with none
    named) if this looks like a question about the DAM's action-code
    legend, else None.

    Deliberately conservative about single bare letters (I/C/R/A) by
    themselves - "I" in particular collides with the pronoun far too
    often to trust alone. Only treated as a real code mention when
    EITHER: two or more code-shaped tokens appear together (a list,
    like the real "I, A and (i)" case this was built from), or at
    least one token is unambiguous on its own ("(i)"/"( i )", or a
    letter+digit combination like "A2"/"C1" that is not a plausible
    English word).
    """
    if not _EXPLAIN_TRIGGER.search(query):
        return None

    codes = _extract_code_tokens(query)
    has_unambiguous = any(c == "( i )" or _SUFFIXED_CODE.match(c) for c in codes)

    if codes and (len(codes) >= 2 or has_unambiguous):
        valid = [c for c in codes if c in _CODES]
        if valid:
            return {"codes": valid}

    if _GENERIC_LEGEND_TRIGGER.search(query):
        return {"codes": None}

    return None


def _format_one_code(code):
    entry = _CODES[code]
    return f"**{entry['code']}** - {entry['meaning']}"


def format_action_code_answer(detection):
    codes = detection["codes"]

    if codes:
        lines = [_format_one_code(c) for c in codes]
        return "\n".join(lines)

    lines = [_format_one_code(c) for c in _LEGEND_ORDER]
    body = "\n".join(lines)
    return (
        f"The DAM's action codes:\n{body}\n\n"
        "Some of these also have numbered levels (A1-A3, C1-C4, R1-R2, "
        "I1-I3) for more specific delegation levels within that action - "
        "ask about a specific one, e.g. \"what does C2 mean\", for the "
        "detailed definition."
    )
