import re

from llm.base import LLMUnavailableError

LANGUAGE_NAMES = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
}

# Cheap, deterministic, LLM-free pre-filter - same "don't pay for what
# you don't need" reasoning as knowledge/typo_correct.py only running
# when a word doesn't already match: the overwhelming majority of real
# traffic here is English, and every non-English query costs an EXTRA
# Groq round trip (translate the query in, translate the answer back
# out) on top of the normal one. This heuristic only decides whether
# it's worth even ATTEMPTING translation - it is never trusted for the
# real language identification itself, that's always the LLM's job
# once this flags true. Defaults to "assume English" on anything
# ambiguous or too short, rather than paying the extra round trip on
# every message.
_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06FF]")
_ACCENTED_LATIN = re.compile(r"[àâäéèêëïîôöùûüçñãõ]", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-zà-ÿ']+")
# "o" and "as" deliberately left out of the Portuguese set - both are
# also common, short English tokens ("as needed", "as approved"), and
# unlike the rest of these lists neither is distinctive enough to
# trust on a single hit. Everything kept here is a real, whole-word
# match risk of essentially zero in ordinary English DAM phrasing.
_FUNCTION_WORDS = {
    "fr": {
        "le", "la", "les", "des", "une", "qui", "que", "pour", "dans",
        "est", "du", "avec", "sont", "quels", "quelles",
    },
    "es": {
        "el", "los", "las", "que", "es", "una", "por", "para", "con",
        "quien", "quienes", "cuales", "cual",
    },
    "pt": {
        "os", "que", "uma", "por", "para", "com", "quem", "quais", "qual",
    },
}


def looks_non_english(text):
    """
    Best-effort guess, not a real language detector - just cheap
    enough to gate the expensive path. True if `text` looks like it
    MIGHT be French/Spanish/Portuguese/Arabic; False if it looks like
    plain English (or is too ambiguous to tell either way).

    A single whole-word hit is enough - measured directly against a
    realistic short question ("qui approuve 3.111", the natural French
    phrasing of "who approves 3.111") that only contains ONE real
    function word ("qui") once the DAM-specific verb is excluded; a
    2-hit requirement (an earlier version of this check) missed it
    entirely. Safe to be this loose specifically because every word
    list above was first checked for collisions against ordinary
    English DAM vocabulary and had the risky ones (bare "o", "as")
    removed - a false positive here only costs one extra, self-
    correcting translation round trip (the model reports LANGUAGE: en
    and returns the text unchanged), never a wrong answer.
    """
    if _ARABIC_SCRIPT.search(text):
        return True
    if _ACCENTED_LATIN.search(text):
        return True

    words = set(_WORD_RE.findall(text.lower()))
    return any(words & lang_words for lang_words in _FUNCTION_WORDS.values())


_TRANSLATE_SYSTEM_PROMPT = (
    "You are a precise translation assistant. You will be given a short "
    "user question that may be in French, Spanish, Portuguese, Arabic, or "
    "English. Respond with EXACTLY two lines, nothing else:\n"
    "LANGUAGE: <two-letter code, one of en/fr/es/pt/ar>\n"
    "TRANSLATED: <the question translated to English>\n\n"
    "Critical rules:\n"
    "- Never translate, alter, or remove anything that looks like a code "
    "made of digits and periods (e.g. 2.126, 3.111.2) - copy those "
    "exactly as given, character for character.\n"
    "- If the question is already in English, set LANGUAGE: en and copy "
    "it unchanged as TRANSLATED.\n"
    "- Translate meaning, not word-for-word - keep it a natural English "
    "question."
)

_LANGUAGE_LINE = re.compile(r"^LANGUAGE:\s*([a-z]{2})", re.IGNORECASE | re.MULTILINE)
_TRANSLATED_LINE = re.compile(r"^TRANSLATED:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def detect_and_translate_to_english(text, provider):
    """
    Returns {"language": str, "translated_text": str, "used_llm": bool,
    "error": str|None}. Falls back to treating the text as English
    unchanged on any failure (provider unavailable, network error,
    unparseable response) - the caller always has a safe, usable
    English query to run the deterministic pipeline on, even if
    translation itself failed outright. Only ever changes retrieval
    behavior when it actually succeeded.
    """
    fallback = {"language": "en", "translated_text": text, "used_llm": False, "error": None}

    if provider is None:
        return {**fallback, "error": "No LLM provider available for translation."}

    try:
        raw = provider.chat(_TRANSLATE_SYSTEM_PROMPT, text).strip()
    except LLMUnavailableError as exc:
        return {**fallback, "error": str(exc)}

    lang_match = _LANGUAGE_LINE.search(raw)
    text_match = _TRANSLATED_LINE.search(raw)

    if not lang_match or not text_match:
        return {**fallback, "error": "Translation response was not in the expected format."}

    language = lang_match.group(1).lower()
    translated = text_match.group(1).strip()

    if language not in LANGUAGE_NAMES or not translated:
        return {
            **fallback,
            "error": f"Unrecognized language code {language!r} in translation response.",
        }

    return {"language": language, "translated_text": translated, "used_llm": True, "error": None}


def translate_text(text, target_language, provider):
    """
    Translates an already-composed English message (a static
    smalltalk/help/error reply - NOT a grounded DAM fact answer, those
    go through agent.generate.humanize_answer's own, stricter,
    grounding-checked path instead, since there are real facts in them
    worth protecting from fabrication) into `target_language`.

    Returns {"text": str, "used_llm": bool, "error": str|None} -
    "text" is always safe to show, falling back to the original
    English message on any failure.
    """
    if target_language == "en" or target_language not in LANGUAGE_NAMES:
        return {"text": text, "used_llm": False, "error": None}

    if provider is None:
        return {
            "text": text,
            "used_llm": False,
            "error": "No LLM provider available for translation.",
        }

    language_name = LANGUAGE_NAMES[target_language]
    system = (
        f"Translate the given text into natural, conversational "
        f"{language_name}. Keep any DAM role names, acronyms, or codes "
        "made of digits and periods (e.g. 2.126) exactly as given, "
        "untranslated. Respond with the translation only - no preamble, "
        "no quotes around it."
    )

    try:
        translated = provider.chat(system, text).strip()
    except LLMUnavailableError as exc:
        return {"text": text, "used_llm": False, "error": str(exc)}

    if not translated:
        return {"text": text, "used_llm": False, "error": "Translation returned empty output."}

    return {"text": translated, "used_llm": True, "error": None}
