import json
import re
from pathlib import Path

AUTHORITY_CODES_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reference" / "authority_codes.json"
)

# Real gap found live (2026-09-03, see docs/decisions.md): asking
# "what's I, A and (i)?" right after a task question got silently
# swallowed by the context-carryover fallback in qa.py - the letters
# are too short to count as "real content words" (see _content_word_
# count there), so the vague-question heuristic treated it as an
# under-specified follow-up about the same task, instead of what it
# actually was: a question about what the DAM's own action-code legend
# means. data/reference/authority_codes.json already had the DAM's own
# legend text extracted (carried over from v1, schema/schema.py's own
# AuthorityCode model was built for exactly this) but nothing in the
# v2 agent ever read it - this wires it in as its own detection path,
# same pattern as agent/glossary.py, and - critically - has to run
# BEFORE the context-carryover / vague-question logic in qa.py's
# answer_question(), not after, or it never gets a chance to fire.


def _load_authority_codes():
    with open(AUTHORITY_CODES_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["code"]: e for e in entries}


_CODES = _load_authority_codes()

# Ordered the way the DAM's own legend presents them (Initiate, Check/
# Verify, Consult, Review, Approve, Informed) - reused for the "explain
# the whole legend" answer below, not just individual lookups.
_LEGEND_ORDER = ["I", "C", "C3", "R", "A", "( i )"]

_EXPLAIN_TRIGGER = re.compile(
    r"\b(what does|what's|what is|what are|whats|explain|mean|means|"
    r"meaning|stand for|stands for|define|definition)\b",
    re.IGNORECASE,
)

# A generic ask about the legend/system itself, with no specific code
# named - "what do the action codes mean", "explain the legend". Kept
# separate from the per-code trigger below since this one doesn't need
# any code token present to fire.
_GENERIC_LEGEND_TRIGGER = re.compile(
    r"\b(action codes?|authority codes?|the legend|these codes|"
    r"the letters|the abbreviations? [ia] c r a)\b",
    re.IGNORECASE,
)

_INFORMED_TOKEN = re.compile(r"\(\s*i\s*\)", re.IGNORECASE)

# Case-sensitive on purpose - these codes are always written upper-
# case in the DAM and in how this app talks about them elsewhere
# (agent/authority.py's INTENTS, _format_role_list's "A: ..." lines).
# Matching lowercase too would make "i" (the pronoun) and "a"/"c" as
# ordinary short words far too easy to hit by accident.
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
        # Keep only codes that are actually in the legend (the bare-
        # token regex can in principle match a stray capital letter
        # that isn't a real code at all - "( i )" always is, and
        # [ICRA]\d? always is by construction, so this is mostly a
        # safety net, not a real filter in practice).
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

    # Generic "explain the legend" - the six top-level codes only
    # (bare I/C/R/A/(i), plus C3 as the one distinct enough from C1/C2
    # to be worth naming up front: Consult, not Check). Numbered
    # variants (A1-A3, C1-C4, R1-R2, I1-I3) exist for more specific
    # delegation levels within each action - mentioned, not spelled
    # out, to keep this answer readable; a follow-up naming a specific
    # one (e.g. "what does C2 mean") gets the detailed version above.
    lines = [_format_one_code(c) for c in _LEGEND_ORDER]
    body = "\n".join(lines)
    return (
        f"The DAM's action codes:\n{body}\n\n"
        "Some of these also have numbered levels (A1-A3, C1-C4, R1-R2, "
        "I1-I3) for more specific delegation levels within that action - "
        "ask about a specific one, e.g. \"what does C2 mean\", for the "
        "detailed definition."
    )
