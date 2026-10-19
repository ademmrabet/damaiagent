import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

AUTHORITY_CODES_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "reference"
    / "authority_codes.json"
)


# load the A/C/R/I code meanings from the reference json
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

_TRIGGER_WORDS = {
    "what",
    "whats",
    "does",
    "do",
    "is",
    "are",
    "explain",
    "mean",
    "means",
    "meaning",
    "stand",
    "stands",
    "for",
    "define",
    "definition",
}
_WORD_TOKEN = re.compile(r"[a-zA-Z']+")


# true when nothing is left in the question except the code itself
def _no_other_subject(query, codes):
    code_letters = {c.strip("()").strip().upper() for c in codes}
    leftover = [
        w
        for w in _WORD_TOKEN.findall(query.lower())
        if w not in _TRIGGER_WORDS
        and w.upper() not in code_letters
        and w not in ENGLISH_STOP_WORDS
    ]
    return not leftover


# action codes (A, C, R, I...) mentioned in the question, in order
def _extract_code_tokens(query):
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


# detect 'what does A2 mean' style questions about action codes
def detect_action_code_query(query):
    if not _EXPLAIN_TRIGGER.search(query):
        return None

    codes = _extract_code_tokens(query)
    has_unambiguous = any(c == "( i )" or _SUFFIXED_CODE.match(c) for c in codes)

    if codes and (
        len(codes) >= 2 or has_unambiguous or _no_other_subject(query, codes)
    ):
        valid = [c for c in codes if c in _CODES]
        if valid:
            return {"codes": valid}

    if _GENERIC_LEGEND_TRIGGER.search(query):
        return {"codes": None}

    return None


# one line: code and what it means
def _format_one_code(code):
    entry = _CODES[code]
    return f"**{entry['code']}** - {entry['meaning']}"


# answer for specific codes, or the full legend if none were named
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
        'ask about a specific one, e.g. "what does C2 mean", for the '
        "detailed definition."
    )
