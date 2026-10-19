import difflib
import re

_WORD_PATTERN = re.compile(r"[A-Za-z']+")

DEFAULT_MIN_RATIO = 0.88
DEFAULT_MIN_WORD_LENGTH = 4


# fix typos by matching words to the matrix vocabulary
def correct_words(
    text,
    vocabulary,
    min_ratio=DEFAULT_MIN_RATIO,
    min_word_length=DEFAULT_MIN_WORD_LENGTH,
):
    lower_vocab = {w.lower() for w in vocabulary}

    def replace(match):
        word = match.group()
        if len(word) < min_word_length or word.isupper():
            return word
        lowered = word.lower()
        if lowered in lower_vocab:
            return word
        candidates = difflib.get_close_matches(
            lowered, lower_vocab, n=1, cutoff=min_ratio
        )
        if not candidates:
            return word
        corrected = candidates[0]
        return corrected.capitalize() if word[0].isupper() else corrected

    return _WORD_PATTERN.sub(replace, text)
