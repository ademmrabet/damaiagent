from knowledge.typo_correct import correct_words

INTENTS = [
    {
        "name": "informed",
        "verb_phrase": "must be informed",
        "keywords": [
            "informed", "notify", "notified", "notification",
            "aware", "awareness", "keep in the loop", "kept informed",
        ],
        "matches": lambda action, level: action == "( i )",
    },
    {
        "name": "approve",
        "verb_phrase": "approve(s)",
        "keywords": [
            "approve", "approves", "approval", "endorse", "endorses",
            "endorsement", "sign off", "signs off", "signature",
            "authorize", "authorizes", "authorization",
        ],
        "matches": lambda action, level: action.startswith("A"),
    },
    {
        "name": "review",
        "verb_phrase": "review(s) / recommend(s)",
        "keywords": [
            "review", "reviews", "recommend", "recommends",
            "recommendation",
        ],
        "matches": lambda action, level: action.startswith("R"),
    },
    {
        "name": "initiate",
        "verb_phrase": "initiate(s)",
        "keywords": [
            "initiate", "initiates", "originate", "originates",
            "launch", "launches", "starts", "kicks off",
        ],
        "matches": lambda action, level: action.startswith("I"),
    },
    {
        "name": "consult",
        "verb_phrase": "consult(s) on",
        "keywords": ["consult", "consults", "consulted", "consultation"],
        "matches": lambda action, level: action in ("C3", "C4"),
    },
    {
        "name": "check",
        "verb_phrase": "check(s) / verifie(s)",
        "keywords": ["check", "checks", "verify", "verifies", "verification"],
        "matches": lambda action, level: action in ("C", "C1", "C2"),
    },
]


# Every single word that appears in any intent's keyword list (multi-
# word keywords like "sign off" get split into their component words -
# correction operates word-by-word, then the existing substring check
# below still runs against the corrected text unchanged). Built once
# at import time since INTENTS is static.
_INTENT_VOCAB = {
    word
    for intent in INTENTS
    for keyword in intent["keywords"]
    for word in keyword.split()
}


def _match_intent(lowered):
    for intent in INTENTS:
        if any(keyword in lowered for keyword in intent["keywords"]):
            return intent
    return None


def detect_intent(query):
    """
    Returns the first matching intent dict, or None if the question
    doesn't name a specific authority action - callers should fall
    back to showing every responsibility on the resolved task rather
    than guessing which one was meant.

    Tries the query exactly as typed first (the common case, and the
    fast path - no correction needed). Only if that finds nothing does
    it retry against a typo-corrected version - "aproves" / "chek" /
    "intiates" now resolve to the same intent "approves" / "check" /
    "initiates" would, instead of silently matching no intent at all
    and falling back to showing every responsibility on the task
    (still correct, just far less targeted than what was actually
    asked). Correction only ever changes WHICH intent gets selected -
    it never touches the actual action-code matching rules just below
    (the A/A1/A2, C vs C1/C2 vs C3/C4 precision work), so it can't
    reopen the "bare C" / "consult vs check" ambiguity that was
    already carefully fixed.
    """

    lowered = query.lower()

    intent = _match_intent(lowered)
    if intent:
        return intent

    # Looser threshold than knowledge/typo_correct.py's 0.88 default,
    # same reasoning as agent/glossary.py's trigger-word correction:
    # this is a small (~35-word), curated, semantically distinct
    # vocabulary, not a large organic-language one, so the collision
    # risk that justified 0.88 elsewhere is much lower - checked
    # directly against a batch of unrelated real words before
    # lowering this, zero collisions found.
    corrected = correct_words(lowered, _INTENT_VOCAB, min_ratio=0.75)
    if corrected != lowered:
        return _match_intent(corrected)

    return None
