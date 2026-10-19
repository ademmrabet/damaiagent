import json
import re
from pathlib import Path

from knowledge.typo_correct import correct_words

GLOSSARY_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reference" / "abbreviations.json"
)

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
    "what",
    "whats",
    "does",
    "the",
    "acronym",
    "abbreviation",
    "mean",
    "means",
    "stand",
    "stands",
    "for",
    "is",
    "meaning",
    "definition",
    "of",
    "define",
}

_ACRONYM_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]{1,6}\b")


# load acronyms from the abbreviations json, keyed by uppercase term
def _load_glossary():
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["term"].upper(): (e["term"], e["definition"]) for e in entries}


_GLOSSARY = _load_glossary()

MANUAL_ALIASES = {
    "RDNG": (
        "RDNG",
        "Director, Nigeria Country Office. Not separately defined in the "
        'DAM\'s own Abbreviations list (pages 2-7) - only "RDG" is '
        'defined there, with a note that RDG "also covers" this role - '
        'but "RDNG" is the acronym the DAM\'s own role names actually '
        'use (e.g. "RDG / Director RDNG").',
    ),
}


# strip quotes and punctuation around the term
def _clean_candidate(raw):
    return raw.strip(" \t\n\"'.,!?")


# case-insensitive lookup in the acronym reference
def lookup_term(term):
    if not term:
        return None
    hit = _GLOSSARY.get(term.upper())
    if hit:
        return hit
    return MANUAL_ALIASES.get(term.upper())


# try each trigger pattern and return the term asked about
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


# detect 'what does X stand for' style questions and look the term up
def detect_glossary_query(query):
    detection = _detect_glossary_query_raw(query)
    if detection:
        return detection

    corrected = correct_words(query, _GLOSSARY_TRIGGER_VOCAB, min_ratio=0.75)
    if corrected != query:
        return _detect_glossary_query_raw(corrected)

    return None


# say what the acronym stands for, or that it is unknown
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


# add the acronym meaning in brackets the first time it appears
def expand_acronym_in_role_name(role_name, already_expanded):
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
