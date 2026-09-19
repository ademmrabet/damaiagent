import re

from llm.base import LLMUnavailableError


TONES = ("frustrated", "confused", "neutral")

_REPEATED_PUNCTUATION = re.compile(r"[!?]{2,}")
_ALL_CAPS_WORD = re.compile(r"\b[A-Z]{4,}\b")

_FRUSTRATION_PATTERNS = re.compile(
    r"\b(useless|terrible|annoying|frustrat\w*|ridiculous|broken|"
    r"stupid|worst|hate|sucks?|ugh+|wtf|ffs|seriously)\b|"
    r"\b(still (not|isn'?t|doesn'?t)|not working|doesn'?t work|"
    r"come on|waste of time|fix this|this again)\b",
    re.IGNORECASE,
)

_CONFUSION_PATTERNS = re.compile(
    r"\b(confus\w*|clueless|lost|huh)\b|"
    r"\b(don'?t (get|understand)|doesn'?t make sense|no idea what|"
    r"not sure what|what does that mean|i'?m (so )?lost)\b",
    re.IGNORECASE,
)


def looks_emotional(text):
    """
    Cheap, deterministic pre-filter - decides whether it's even worth
    ATTEMPTING the Groq tone classification below, never trusted for
    the actual tone itself. True if `text` shows any surface signal of
    frustration or confusion (repeated punctuation, shouted words,
    or one of the phrase patterns above); False for ordinary, plainly-
    worded questions - the large majority of real traffic.
    """
    if _REPEATED_PUNCTUATION.search(text):
        return True
    if _ALL_CAPS_WORD.search(text):
        return True
    if _FRUSTRATION_PATTERNS.search(text):
        return True
    if _CONFUSION_PATTERNS.search(text):
        return True
    return False


_TONE_SYSTEM_PROMPT = (
    "Classify the emotional tone of the user's message. Respond with "
    "EXACTLY one word, one of: frustrated, confused, neutral.\n"
    "- frustrated: annoyed, angry, impatient, or venting that something "
    "isn't working.\n"
    "- confused: lost, uncertain, or asking for clarification because "
    "they don't understand something.\n"
    "- neutral: anything else, including ordinary factual questions.\n"
    "When in doubt, answer neutral."
)


def detect_tone(text, provider):
    """
    Returns {"tone": "frustrated"|"confused"|"neutral", "used_llm":
    bool, "error": str|None}. Always defaults to "neutral" (i.e. no
    behavior change) on any failure - no provider, a network error, or
    an unparseable response - same "never guess wrong, fall back
    safely" principle as llm/translate.py's detect_and_translate_to_
    english(). Callers are expected to have already checked
    looks_emotional(text) before spending this call.
    """
    fallback = {"tone": "neutral", "used_llm": False, "error": None}

    if provider is None:
        return {**fallback, "error": "No LLM provider available for tone detection."}

    try:
        raw = provider.chat(_TONE_SYSTEM_PROMPT, text, temperature=0.0, max_tokens=8).strip()
    except LLMUnavailableError as exc:
        return {**fallback, "error": str(exc)}

    tone = raw.lower().strip(" .!\"'")
    if tone not in TONES:
        return {**fallback, "error": f"Unrecognized tone {raw!r} in classification response."}

    return {"tone": tone, "used_llm": True, "error": None}


EMPATHY_PREFIXES = {
    "en": {
        "frustrated": "I hear you, and I'm sorry this has been frustrating.",
        "confused": "No worries, let's take this one step at a time.",
    },
    "fr": {
        "frustrated": "Je comprends, désolé que cela soit frustrant.",
        "confused": "Pas de souci, prenons cela étape par étape.",
    },
    "es": {
        "frustrated": "Le entiendo, lamento que esto sea frustrante.",
        "confused": "No se preocupe, vayamos paso a paso.",
    },
    "pt": {
        "frustrated": "Entendo, lamento que isso seja frustrante.",
        "confused": "Sem problemas, vamos passo a passo.",
    },
    "ar": {
        "frustrated": "أتفهم شعورك، وآسف لأن هذا كان محبطًا.",
        "confused": "لا مشكلة، لنأخذ هذا خطوة بخطوة.",
    },
}


def apply_tone_prefix(answer, tone, language="en"):
    """
    Prepends a short, tone-appropriate opener to `answer` when `tone`
    is "frustrated" or "confused" - a no-op for "neutral" (the default,
    overwhelming majority case) or an unrecognized language. Kept
    entirely separate from `deterministic_answer` in the caller
    (webapp/backend.py) - this is a warmth/UX layer on top of the
    facts, never part of the trusted facts themselves.
    """
    prefixes = EMPATHY_PREFIXES.get(language, EMPATHY_PREFIXES["en"])
    prefix = prefixes.get(tone)
    if not prefix:
        return answer
    return f"{prefix} {answer}"
