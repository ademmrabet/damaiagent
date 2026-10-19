import pytest

from knowledge.typo_correct import correct_words

VOCAB = {
    "approve",
    "approves",
    "check",
    "checks",
    "initiate",
    "initiates",
    "consult",
    "consults",
    "review",
    "reviews",
    "hello",
    "quarterly",
    "mission",
    "related",
    "annual",
    "bank",
}


@pytest.mark.parametrize(
    "typo,expected",
    [
        ("aproves", "approves"),
        ("chek", "check"),
        ("intiates", "initiates"),
        ("qaurterly", "quarterly"),
        ("mision", "mission"),
        ("helo", "hello"),
    ],
)
def test_real_typos_get_corrected(typo, expected):
    assert correct_words(typo, VOCAB) == expected


@pytest.mark.parametrize(
    "word",
    [
        "approve",
        "check",
        "initiate",
        "consult",
        "hello",
    ],
)
def test_already_correct_words_are_left_alone(word):
    assert correct_words(word, VOCAB) == word


def test_genuinely_different_word_is_not_forced_into_the_vocabulary():
    assert correct_words("unrelated", VOCAB) == "unrelated"


def test_unrecognizable_word_is_left_alone_not_guessed_at():
    assert correct_words("spaceship", VOCAB) == "spaceship"


def test_short_words_are_never_touched():
    assert correct_words("men", {"mean"}) == "men"


def test_all_caps_words_are_never_touched():
    assert correct_words("DDG", VOCAB) == "DDG"


def test_correction_preserves_surrounding_text_and_punctuation():
    result = correct_words("who aproves 2.126?", VOCAB)
    assert result == "who approves 2.126?"


def test_correction_preserves_capitalization_style():
    assert correct_words("Aproves this", VOCAB).startswith("Approves")


def test_multiple_typos_in_one_query_all_get_corrected():
    result = correct_words(
        "who aproves the qaurterly mision report", VOCAB | {"report"}
    )
    assert result == "who approves the quarterly mission report"
