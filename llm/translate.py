import re

from llm.base import LLMUnavailableError

LANGUAGE_NAMES = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
}

_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06FF]")
_ACCENTED_LATIN = re.compile(r"[àâäéèêëïîôöùûüçñãõ]", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-zà-ÿ']+")
_FUNCTION_WORDS = {
    "fr": {
        "le",
        "la",
        "les",
        "des",
        "une",
        "qui",
        "que",
        "pour",
        "dans",
        "est",
        "du",
        "avec",
        "sont",
        "quels",
        "quelles",
    },
    "es": {
        "el",
        "los",
        "las",
        "que",
        "es",
        "una",
        "por",
        "para",
        "con",
        "quien",
        "quienes",
        "cuales",
        "cual",
    },
    "pt": {
        "os",
        "que",
        "uma",
        "por",
        "para",
        "com",
        "quem",
        "quais",
        "qual",
    },
}


# quick guess whether the text is not english
def looks_non_english(text):
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


# detect the language and translate the question to english
def detect_and_translate_to_english(text, provider):
    fallback = {
        "language": "en",
        "translated_text": text,
        "used_llm": False,
        "error": None,
    }

    if provider is None:
        return {**fallback, "error": "No LLM provider available for translation."}

    try:
        raw = provider.chat(_TRANSLATE_SYSTEM_PROMPT, text).strip()
    except LLMUnavailableError as exc:
        return {**fallback, "error": str(exc)}

    lang_match = _LANGUAGE_LINE.search(raw)
    text_match = _TRANSLATED_LINE.search(raw)

    if not lang_match or not text_match:
        return {
            **fallback,
            "error": "Translation response was not in the expected format.",
        }

    language = lang_match.group(1).lower()
    translated = text_match.group(1).strip()

    if language not in LANGUAGE_NAMES or not translated:
        return {
            **fallback,
            "error": f"Unrecognized language code {language!r} in translation response.",
        }

    return {
        "language": language,
        "translated_text": translated,
        "used_llm": True,
        "error": None,
    }


# translate an english answer into the user's language
def translate_text(text, target_language, provider):
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
        return {
            "text": text,
            "used_llm": False,
            "error": "Translation returned empty output.",
        }

    return {"text": translated, "used_llm": True, "error": None}
