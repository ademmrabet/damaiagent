import json
import re
from pathlib import Path

from knowledge.typo_correct import correct_words

GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "data" / "reference" / "abbreviations.json"

# Deliberately narrow trigger phrasing - only fires on "what does X
# mean/stand for", "define X", "meaning of X" style questions. Does
# NOT trigger on a bare "what is X", since that overlaps too heavily
# with ordinary DAM-task questions like "what is 2.120" - those need
# to keep reaching the normal node-resolution pipeline in qa.py, not
# get hijacked here.
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

# Bare "what's X" / "what is X" / "whats X" - deliberately handled
# separately from _TRIGGER_PATTERNS above, not merged into them,
# because this phrasing is genuinely ambiguous ("what is 2.120" must
# still reach the normal DAM id lookup). Only ever treated as a
# glossary question when: (a) it's a single bare token with no dots
# or spaces (a DAM id always has a dot, e.g. "2.120"; a task
# description is always multiple words), and (b) that token actually
# resolves in the glossary - if it doesn't resolve, this returns no
# match at all rather than an honest "not found", since an
# unresolved bare "what's X" might just as easily be a mistyped task
# question as a real glossary miss, and guessing wrong here is worse
# than falling through to the normal pipeline.
_BARE_WHATS_PATTERN = re.compile(r"^whats?(?:'s|\s+is)?\s+(.+?)\s*\??$", re.IGNORECASE)
_BARE_ACRONYM_SHAPE = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,7}$")

# The trigger phrasing's own words, not the term being asked about -
# typo-correcting "what dose DDG men" into "what does DDG mean" should
# never risk touching "DDG" itself. Safe in practice even without this
# vocabulary being exhaustive: correct_words() already skips ALL-CAPS
# and sub-4-letter words, which covers virtually every real acronym in
# this glossary (see MANUAL_ALIASES / abbreviations.json).
_GLOSSARY_TRIGGER_VOCAB = {
    "what", "whats", "does", "the", "acronym", "abbreviation",
    "mean", "means", "stand", "stands", "for", "is", "meaning",
    "definition", "of", "define",
}

# Matches a standalone all-caps token like "DDG" or "RDVP" embedded in
# a longer role name (e.g. "Country Manager / DDG") - built from
# checking real role names extracted from the DAM: composite roles
# consistently spell out full words in Title Case and only use
# ALL-CAPS for an embedded acronym, so this stays narrow to genuine
# acronym mentions instead of matching ordinary words.
_ACRONYM_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]{1,6}\b")


def _load_glossary():
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["term"].upper(): (e["term"], e["definition"]) for e in entries}


_GLOSSARY = _load_glossary()

# Manual, hand-added exceptions - NOT extracted from pages 2-7, kept
# in a separate dict rather than merged into abbreviations.json so
# that file stays a pure, reproducible extraction of the PDF (rerun
# parsing/glossary.py against the source and you get exactly
# abbreviations.json back, no hidden manual edits). Added here because
# real usage surfaced a real gap: "RDNG" appears directly in DAM role
# names (confirmed: "RDG / Director RDNG", "Country Manager / DDG RDG
# / Director RDNG") but the Abbreviations list itself never defines it
# as its own entry - only "RDG" is defined there, with a note that RDG
# "also covers the Director of the Nigeria Country Office". This is
# that same fact, just also reachable under the exact acronym the DAM
# actually uses in role names.
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

    # A looser threshold than knowledge/typo_correct.py's 0.88 default
    # on purpose: short trigger words ("what"/"does") only reach ~0.75
    # against a common 1-character transposition typo ("waht", "dose")
    # - a 4-letter word's ratio ceiling under a transposition is just
    # lower than a longer word's. 0.88 was raised specifically to stop
    # a large, organic-language vocabulary (DAM title words) from
    # false-positiving on unrelated real words; that risk is much
    # smaller here - this vocabulary is a short, curated, semantically
    # distinct list of ~16 words, checked directly against a batch of
    # unrelated realistic words before lowering this (only one weak
    # collision found: "form" -> "for", low-impact even if it fires).
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
