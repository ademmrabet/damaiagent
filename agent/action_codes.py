import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

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

_TRIGGER_WORDS = {
    "what", "whats", "does", "do", "is", "are", "explain", "mean",
    "means", "meaning", "stand", "stands", "for", "define", "definition",
}
_WORD_TOKEN = re.compile(r"[a-zA-Z']+")


def _no_other_subject(query, codes):
    """
    True when, once the explain-trigger words, common English
    stopwords, and the matched code letter(s) themselves are stripped
    out, nothing else is left in the query. "what I means?", "what's
    I?" have no other real subject once that's done, so the lone
    letter can only be this action code - not the pronoun "I", the
    exact collision detect_action_code_query's docstring is otherwise
    deliberately conservative about. A longer question that just
    happens to contain a stray "I" ("I don't understand what approve
    means") still has real leftover content afterward ("understand",
    "approve"), so this stays False there and the single-bare-letter
    path is never reached for it. Generalizes past "I" - the same
    ambiguity-when-alone concern applies just as much to a bare "A" or
    "C" landing on an unrelated capitalized word.
    """
    code_letters = {c.strip("()").strip().upper() for c in codes}
    leftover = [
        w for w in _WORD_TOKEN.findall(query.lower())
        if w not in _TRIGGER_WORDS
        and w.upper() not in code_letters
        and w not in ENGLISH_STOP_WORDS
    ]
    return not leftover


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
    often to trust alone. Treated as a real code mention when: two or
    more code-shaped tokens appear together (a list, like the real
    "I, A and (i)" case this was built from); at least one token is
    unambiguous on its own ("(i)"/"( i )", or a letter+digit
    combination like "A2"/"C1" that is not a plausible English word);
    or a single bare letter has no other real subject alongside it
    ("what I means?", "what's A?") - see _no_other_subject for why
    that last case is still safe against the pronoun collision.
    """
    if not _EXPLAIN_TRIGGER.search(query):
        return None

    codes = _extract_code_tokens(query)
    has_unambiguous = any(c == "( i )" or _SUFFIXED_CODE.match(c) for c in codes)

    if codes and (len(codes) >= 2 or has_unambiguous or _no_other_subject(query, codes)):
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
