import difflib
import re

_WORD_PATTERN = re.compile(r"[A-Za-z']+")

DEFAULT_MIN_RATIO = 0.88
DEFAULT_MIN_WORD_LENGTH = 4


def correct_words(text, vocabulary, min_ratio=DEFAULT_MIN_RATIO, min_word_length=DEFAULT_MIN_WORD_LENGTH):
    """
    Deterministic, offline typo correction - no LLM, no network, works
    every time regardless of whether an LLM mode is even configured,
    same reasoning as everything else in this project's retrieval path
    (grounded, explainable, doesn't depend on an external model being
    reachable). Replaces each alphabetic word in `text` with its
    closest match in `vocabulary` when it isn't already an exact match
    (case-insensitive) but is close enough (difflib SequenceMatcher
    ratio >= min_ratio).

    Conservative on purpose - a word with no sufficiently close match
    is left exactly as typed rather than guessed at, the same
    "say what you actually know, don't fabricate" discipline the rest
    of this project's retrieval logic already follows. Two more
    deliberate guards against over-correction:
    - words shorter than `min_word_length` are skipped - edit-distance
      similarity is close to meaningless at 1-3 letters (almost
      anything looks "close" to "is" or "the"), and the highest-value
      typos in practice ("aproves", "chek", "qaurterly") are all 4+
      letters anyway.
    - words that are already ALL CAPS (DDG, RDG, PGCL...) are skipped
      entirely - those are DAM role/authority acronyms, not misspelled
      English words, and fuzzy-matching a real acronym against an
      English/DAM-title vocabulary risks "correcting" it into an
      unrelated common word.
    """
    lower_vocab = {w.lower() for w in vocabulary}

    def replace(match):
        word = match.group()
        if len(word) < min_word_length or word.isupper():
            return word
        lowered = word.lower()
        if lowered in lower_vocab:
            return word
        candidates = difflib.get_close_matches(lowered, lower_vocab, n=1, cutoff=min_ratio)
        if not candidates:
            return word
        corrected = candidates[0]
        return corrected.capitalize() if word[0].isupper() else corrected

    return _WORD_PATTERN.sub(replace, text)
