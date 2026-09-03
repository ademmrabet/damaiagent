import random
import re

from knowledge.typo_correct import correct_words

_GREETING = re.compile(r"^(hi+|hello+|hey+|hiya|yo|howdy|greetings)[\s!.,]*$", re.IGNORECASE)
_TIME_GREETING = re.compile(r"^good (morning|afternoon|evening|day)[\s!.,]*$", re.IGNORECASE)
_FAREWELL = re.compile(r"^(bye|goodbye|bye bye|see you|see ya|take care|later|farewell)[\s!.,]*$", re.IGNORECASE)
_THANKS = re.compile(r"^(thanks|thank you|thx|ty|much appreciated|appreciate it|appreciated)[\s!.,]*$", re.IGNORECASE)
_HOW_ARE_YOU = re.compile(r"^how('?s| is| are) (it going|you doing|you|things)\??[\s!.,]*$", re.IGNORECASE)
_WHATS_UP = re.compile(r"^(what'?s up|sup|wassup)\??[\s!.,]*$", re.IGNORECASE)
# Widened 2026-08-06 for a brand-new employee who doesn't know this
# tool or the DAM at all and wouldn't necessarily type the word "help"
# - "how does this work", "I'm new here", "I don't know where to
# start" all land on the same guided reply as "help" itself.
_HELP = re.compile(
    r"^(help|what can you do|who are you|what is this|what do you do|"
    r"how does this work|how do i use this|(i'?m|i am) new( here)?|"
    r"i don'?t know where to start|where do i start)\??[\s!.,]*$",
    re.IGNORECASE,
)

# A few variants per category rather than one fixed line each - purely
# cosmetic (every variant still says the same substantive thing), but
# a canned reply that's identical on every single greeting is one of
# the fastest ways a tool reads as a script instead of something
# actually responding to you. Kept small and all still individually
# true/accurate - not going for jokes, just not repeating word for
# word every time. Every "greeting" variant still contains "Hello"
# (capital H), every "farewell" variant still contains "Goodbye"
# (capital G), and the "help" variants still contain the exact phrase
# "Delegation of Authority Matrix" - tests pin those substrings on
# purpose, so any new variant added later has to keep them too.
_RESPONSES = {
    "greeting": [
        "Hello! I'm the DAM Agent - ask me who approves, reviews, checks, "
        "initiates, or must be informed on any activity in the DAM. Try "
        "something like \"who approves 2.126?\" or name a task by its "
        "title.",
        "Hello there! Ask me about any task in the Delegation of Authority "
        "Matrix - by id (like 2.126) or just describe it - and I'll pull "
        "the answer straight from the matrix, not a guess.",
        "Hello! Happy to help you navigate the DAM. Ask who approves, "
        "checks, or must be informed on any task, whenever you're ready.",
    ],
    "farewell": [
        "Goodbye! Come back anytime you need to check the DAM.",
        "Goodbye for now - I'll be here whenever you need another DAM "
        "answer.",
        "Goodbye! Hope that got you the approval you were after.",
    ],
    "thanks": [
        "You're welcome! Let me know if there's another task you'd like "
        "to check.",
        "You're welcome - happy to help with the next one too.",
        "Anytime! You're welcome to ask about as many tasks as you need.",
    ],
    "how_are_you": [
        "Doing well, thanks for asking! Ask me about any task in the DAM "
        "whenever you're ready.",
        "All good here and ready to go - what DAM question can I help "
        "with?",
    ],
    "help": [
        "I'm the DAM Agent - I answer questions about the African "
        "Development Bank's Delegation of Authority Matrix: who "
        "approves, reviews, checks, initiates, or must be informed for "
        "any task. Ask by id (like 2.126) or describe the activity in "
        "your own words.",
        "I answer questions about the African Development Bank's "
        "Delegation of Authority Matrix - things like \"who approves "
        "2.126?\", \"who checks the mission program?\", or \"who must be "
        "informed for 3.111?\". Ask by task id or by describing the "
        "activity.",
        "New here? No problem - you don't need to know any Delegation "
        "of Authority Matrix codes to get started. Just describe what "
        "you're trying to do, like \"who approves a mission expense "
        "report?\" or \"who needs to sign off on a budget change?\", and "
        "I'll find the matching task for you.",
    ],
}

_PATTERNS = [
    (_GREETING, "greeting"),
    (_TIME_GREETING, "greeting"),
    (_FAREWELL, "farewell"),
    (_THANKS, "thanks"),
    (_HOW_ARE_YOU, "how_are_you"),
    (_WHATS_UP, "how_are_you"),
    (_HELP, "help"),
]

# Every plain word the patterns above can match on, so a typo in one
# of them ("helo", "godbye", "thnaks") still resolves - anything
# shorter than 4 letters ("hi", "hey", "bye"...) is left to match
# exactly, same reasoning as knowledge/typo_correct.py's own
# min_word_length default: fuzzy-correcting a 2-3 letter word is
# unreliable enough to not be worth the false-positive risk.
_SMALLTALK_VOCAB = {
    "hello", "hiya", "howdy", "greetings",
    "good", "morning", "afternoon", "evening", "day",
    "goodbye", "later", "farewell",
    "thanks", "thank", "appreciated", "appreciate",
    "going", "doing", "things",
    "wassup", "sup",
    "help",
}


def _match_smalltalk(normalized):
    for pattern, category in _PATTERNS:
        if pattern.match(normalized):
            return random.choice(_RESPONSES[category])
    return None


def detect_smalltalk(query):
    """
    Returns a canned reply for greetings/farewells/thanks/small talk, or
    None if the query should go through the normal DAM lookup pipeline.
    Anchored (^...$) against the whole normalized query rather than a
    substring search - "hi" must be the entire message, not a false
    match inside a real question that happens to contain those letters.

    Tries the exact normalized query first; only retries against a
    typo-corrected version if that finds nothing, so a well-formed
    query never pays the correction cost and can never have its match
    changed by it.
    """
    normalized = " ".join(query.strip().lower().split())

    reply = _match_smalltalk(normalized)
    if reply:
        return reply

    # Looser threshold than knowledge/typo_correct.py's 0.88 default -
    # same reasoning as agent/authority.py and agent/glossary.py's
    # trigger-word correction: a small, curated, semantically distinct
    # vocabulary carries much less false-positive risk than a large
    # organic-language one, checked directly before lowering this.
    corrected = correct_words(normalized, _SMALLTALK_VOCAB, min_ratio=0.75)
    if corrected != normalized:
        return _match_smalltalk(corrected)

    return None
