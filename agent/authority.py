from knowledge.typo_correct import correct_words

INTENTS = [
    {
        "name": "informed",
        "verb_phrase": "must be informed",
        "keywords": [
            "informed",
            "notify",
            "notified",
            "notification",
            "aware",
            "awareness",
            "keep in the loop",
            "kept informed",
        ],
        "matches": lambda action, level: action == "( i )",
    },
    {
        "name": "approve",
        "verb_phrase": "approve(s)",
        "keywords": [
            "approve",
            "approves",
            "approval",
            "endorse",
            "endorses",
            "endorsement",
            "sign off",
            "signs off",
            "signature",
            "authorize",
            "authorizes",
            "authorization",
        ],
        "matches": lambda action, level: action.startswith("A"),
    },
    {
        "name": "review",
        "verb_phrase": "review(s) / recommend(s)",
        "keywords": [
            "review",
            "reviews",
            "recommend",
            "recommends",
            "recommendation",
        ],
        "matches": lambda action, level: action.startswith("R"),
    },
    {
        "name": "initiate",
        "verb_phrase": "initiate(s)",
        "keywords": [
            "initiate",
            "initiates",
            "originate",
            "originates",
            "launch",
            "launches",
            "starts",
            "kicks off",
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


_INTENT_VOCAB = {
    word
    for intent in INTENTS
    for keyword in intent["keywords"]
    for word in keyword.split()
}

_ACTION_DISPLAY_NAMES = {
    "initiate": "Initiate",
    "check": "Check/Verify",
    "consult": "Consult",
    "review": "Review",
    "approve": "Approve",
    "informed": "Informed",
}


# readable name for an action code
def action_label(action):
    for intent in INTENTS:
        if intent["matches"](action, None):
            return _ACTION_DISPLAY_NAMES[intent["name"]]
    return action


# first intent whose keyword appears in the question
def _match_intent(lowered):
    for intent in INTENTS:
        if any(keyword in lowered for keyword in intent["keywords"]):
            return intent
    return None


# what the user wants to know (approve, check, inform...), tolerating typos
def detect_intent(query):

    lowered = query.lower()

    intent = _match_intent(lowered)
    if intent:
        return intent

    corrected = correct_words(lowered, _INTENT_VOCAB, min_ratio=0.75)
    if corrected != lowered:
        return _match_intent(corrected)

    return None
