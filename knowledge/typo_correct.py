import difflib
import re

_WORD_PATTERN = re.compile(r"[A-Za-z']+")

# Tuned against a real false-positive, not picked arbitrarily: 0.82
# was loose enough to "correct" the genuinely-different, correctly-
# spelled word "unrelated" into "related" (ratio 0.875 - they share a
# root, textbook false positive for any edit-distance approach) purely
# because "related" happened to be the closest word in a narrow
# ~1400-word DAM-title vocabulary. Every real typo this feature was
# built for - "aproves"/"approves" (0.933), "chek"/"check" (0.889),
# "intiates"/"initiates" (0.941), "qaurterly"/"quarterly" (0.889),
# "mision"/"mission" (0.923), "helo"/"hello" (0.889) - still clears
# 0.88 with room to spare, so raising the floor to 0.88 closes that
# false-positive gap without losing any of the cases that motivated
# building this in the first place. See
# tests/test_typo_correct.py for both sides of this pinned.
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
        # Preserve the original word's capitalization style so a
        # corrected word doesn't look out of place mid-sentence (e.g.
        # a corrected first word of a sentence stays capitalized).
        return corrected.capitalize() if word[0].isupper() else corrected

    return _WORD_PATTERN.sub(replace, text)
