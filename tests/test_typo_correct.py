import pytest

from knowledge.typo_correct import correct_words


VOCAB = {
    "approve", "approves", "check", "checks", "initiate", "initiates",
    "consult", "consults", "review", "reviews", "hello", "quarterly",
    "mission", "related", "annual", "bank",
}


@pytest.mark.parametrize("typo,expected", [
    ("aproves", "approves"),
    ("chek", "check"),
    ("intiates", "initiates"),
    ("qaurterly", "quarterly"),
    ("mision", "mission"),
    ("helo", "hello"),
])
def test_real_typos_get_corrected(typo, expected):
    assert correct_words(typo, VOCAB) == expected


@pytest.mark.parametrize("word", [
    "approve", "check", "initiate", "consult", "hello",
])
def test_already_correct_words_are_left_alone(word):
    # Exact vocabulary matches must be a true no-op - correction should
    # never even attempt fuzzy matching on a word that's already right.
    assert correct_words(word, VOCAB) == word


def test_genuinely_different_word_is_not_forced_into_the_vocabulary():
    # The real false positive this threshold was tuned against:
    # "unrelated" (correctly spelled, not a typo) is textually close
    # to "related" (ratio 0.875) purely because they share a root -
    # forcing it to "related" would silently change the meaning of
    # the sentence, not fix a spelling mistake.
    assert correct_words("unrelated", VOCAB) == "unrelated"


def test_unrecognizable_word_is_left_alone_not_guessed_at():
    assert correct_words("spaceship", VOCAB) == "spaceship"


def test_short_words_are_never_touched():
    # "men" is a real 3-letter typo of "mean" in practice, but fuzzy-
    # matching at 2-3 letters is unreliable enough (almost anything is
    # "close" to a short word) that it's deliberately out of scope.
    assert correct_words("men", {"mean"}) == "men"


def test_all_caps_words_are_never_touched():
    # DAM role acronyms (DDG, RDG, PGCL...) must never be "corrected"
    # into an unrelated common word just because they're short and
    # don't appear in whatever vocabulary is passed in.
    assert correct_words("DDG", VOCAB) == "DDG"


def test_correction_preserves_surrounding_text_and_punctuation():
    result = correct_words("who aproves 2.126?", VOCAB)
    assert result == "who approves 2.126?"


def test_correction_preserves_capitalization_style():
    # A capitalized typo becomes a capitalized correction, not a
    # lowercase one stitched awkwardly into a capitalized sentence.
    assert correct_words("Aproves this", VOCAB).startswith("Approves")


def test_multiple_typos_in_one_query_all_get_corrected():
    result = correct_words("who aproves the qaurterly mision report", VOCAB | {"report"})
    assert result == "who approves the quarterly mission report"
