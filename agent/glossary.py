import json
import re
from pathlib import Path

from knowledge.typo_correct import correct_words

GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "data" / "reference" / "abbreviations.json"

_TRIGGER_PATTERNS = [
    re.compile(
        r"what does\s+(?:the\s+)?(?:acronym\s+|abbreviation\s+)?(.+?)\s+(?:mean|means|stand for|stands for)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"what(?:'s| is)\s+(?:the\s+)?(?:meaning|definition)\s+of\s+(.+?)(?:\?|$)",
        re.IGNORECASE,
    ),
    re.compile(r"\bdefine\s+(.+?)(?:\?|$)", re.IGNORECASE),
    re.compile(r"\bmeaning of\s+(.+?)(?:\?|$)", re.IGNORECASE),
]

_BARE_WHATS_PATTERN = re.compile(r"^whats?(?:'s|\s+is)?\s+(.+?)\s*\??$", re.IGNORECASE)
_BARE_ACRONYM_SHAPE = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,7}$")

_GLOSSARY_TRIGGER_VOCAB = {
    "what", "whats", "does", "the", "acronym", "abbreviation",
    "mean", "means", "stand", "stands", "for", "is", "meaning",
    "definition", "of", "define",
}

_ACRONYM_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]{1,6}\b")


def _load_glossary():
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["term"].upper(): (e["term"], e["definition"]) for e in entries}


_GLOSSARY = _load_glossary()

MANUAL_ALIASES = {
    "RDNG": (
        "RDNG",
        "Director, Nigeria Country Office. Not separately defined in the "
        "DAM's own Abbreviations list (pages 2-7) - only \"RDG\" is "
        "defined there, with a note that RDG \"also covers\" this role - "
        "but \"RDNG\" is the acronym the DAM's own role names actually "
        "use (e.g. \"RDG / Director RDNG\").",
    ),
}


def _clean_candidate(raw):
    return raw.strip(" \t\n\"'.,!?")


def lookup_term(term):
    """
    Case-insensitive exact lookup against the Abbreviations and
    Acronyms reference (data/reference/abbreviations.json, built from
    the DAM's own pages 2-7 - see parsing/glossary.py), falling back
    to MANUAL_ALIASES for the handful of real acronyms the DAM uses
    but never separately defines. Returns (canonical_term, definition)
    or None.
    """
    if not term:
        return None
    hit = _GLOSSARY.get(term.upper())
    if hit:
        return hit
    return MANUAL_ALIASES.get(term.upper())


def _detect_glossary_query_raw(query):
    for pattern in _TRIGGER_PATTERNS:
        match = pattern.search(query)
        if match:
            raw_term = _clean_candidate(match.group(match.lastindex))
            if not raw_term:
                continue
            return {"term": raw_term, "found": lookup_term(raw_term)}

    bare_match = _BARE_WHATS_PATTERN.match(query.strip())
    if bare_match:
        raw_term = _clean_candidate(bare_match.group(1))
        if raw_term and _BARE_ACRONYM_SHAPE.match(raw_term):
            found = lookup_term(raw_term)
            if found:
                return {"term": raw_term, "found": found}

    return None


def detect_glossary_query(query):
    """
    Returns {"term": raw_term, "found": (canonical_term, definition)|None}
    if the query looks like a glossary question, else None.

    Tries the query exactly as typed first; only retries against a
    typo-corrected version of the TRIGGER PHRASING if that finds
    nothing ("what dose DDG men" -> "what does DDG mean") - the term
    being asked about is deliberately not in the correction vocabulary,
    so it's never at risk of being "corrected" into something else.
    """
    detection = _detect_glossary_query_raw(query)
    if detection:
        return detection

    corrected = correct_words(query, _GLOSSARY_TRIGGER_VOCAB, min_ratio=0.75)
    if corrected != query:
        return _detect_glossary_query_raw(corrected)

    return None


def format_glossary_answer(detection):
    term = detection["term"]
    found = detection["found"]
    if found:
        canonical, definition = found
        return f"{canonical} stands for: {definition}"
    return (
        f"{term!r} isn't in the DAM's Abbreviations and Acronyms list "
        f"(pages 2-7) or isn't a role code I have on file. Double-check "
        f"the spelling, or ask about a specific task instead."
    )


def expand_acronym_in_role_name(role_name, already_expanded):
    """
    Appends a plain-language expansion in parentheses the first time a
    known acronym is seen within one formatted answer - e.g. "DDG" ->
    "DDG (Deputy Director-General)", "Country Manager / DDG" ->
    "Country Manager / DDG (DDG = Deputy Director-General)".

    `already_expanded` is a set the caller keeps for the lifetime of
    one _format_role_list() call, so the same acronym isn't re-
    expanded on every role in a long list - only the first mention.
    Checks the whole role name first (covers roles that ARE just the
    acronym, e.g. "RDG"), then falls back to scanning for an embedded
    all-caps token (covers composite roles like "Country Manager /
    DDG"), and expands at most one acronym per role name to avoid
    cluttering roles that already chain several together.
    """
    whole_match = lookup_term(role_name)
    if whole_match:
        canonical, definition = whole_match
        if canonical.upper() in already_expanded:
            return role_name
        already_expanded.add(canonical.upper())
        return f"{role_name} ({definition})"

    for token in _ACRONYM_TOKEN.findall(role_name):
        hit = lookup_term(token)
        if not hit:
            continue
        canonical, definition = hit
        if canonical.upper() in already_expanded:
            continue
        already_expanded.add(canonical.upper())
        return f"{role_name} ({token} = {definition})"

    return role_name
