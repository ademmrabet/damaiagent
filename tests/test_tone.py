from unittest.mock import Mock

import pytest

from llm.base import LLMUnavailableError
from llm.tone import (
    EMPATHY_PREFIXES,
    apply_tone_prefix,
    detect_tone,
    looks_emotional,
)


@pytest.mark.parametrize("text", [
    "who approves 2.126",
    "what does DDG stand for",
    "who checks the annual budget submission",
    "hi",
    "thanks",
    "and who needs to sign off on this",
])
def test_looks_emotional_is_false_for_plain_questions(text):
    assert looks_emotional(text) is False


@pytest.mark.parametrize("text", [
    "why does this still not work??",
    "this is USELESS",
    "ugh, not this again",
    "I'm so confused about what C1 means",
    "I don't understand any of this",
    "seriously, fix this",
])
def test_looks_emotional_is_true_for_real_examples(text):
    assert looks_emotional(text) is True


def _provider(reply_text):
    provider = Mock()
    provider.chat = Mock(return_value=reply_text)
    provider.name = "fake"
    return provider


class TestDetectTone:
    def test_parses_frustrated(self):
        result = detect_tone("why does this still not work??", _provider("frustrated"))
        assert result == {"tone": "frustrated", "used_llm": True, "error": None}

    def test_parses_confused(self):
        result = detect_tone("I don't get it", _provider("confused"))
        assert result["tone"] == "confused"
        assert result["used_llm"] is True

    def test_parses_neutral(self):
        result = detect_tone("who approves 2.126", _provider("neutral"))
        assert result["tone"] == "neutral"

    def test_tolerates_extra_formatting_in_the_response(self):
        # A model wrapping the single word in punctuation or case
        # noise ("Frustrated." / "FRUSTRATED") shouldn't be treated as
        # unparseable - only genuinely unrecognized words should.
        result = detect_tone("ugh", _provider("Frustrated."))
        assert result["tone"] == "frustrated"

    def test_no_provider_falls_back_to_neutral(self):
        result = detect_tone("why does this still not work??", None)
        assert result["tone"] == "neutral"
        assert result["used_llm"] is False
        assert result["error"]

    def test_provider_failure_falls_back_to_neutral(self):
        provider = Mock()
        provider.chat = Mock(side_effect=LLMUnavailableError("network down"))
        result = detect_tone("why does this still not work??", provider)
        assert result["tone"] == "neutral"
        assert result["used_llm"] is False
        assert "network down" in result["error"]

    def test_unparseable_response_falls_back_to_neutral(self):
        result = detect_tone("ugh", _provider("I'm not going to follow the format."))
        assert result["tone"] == "neutral"
        assert result["used_llm"] is False
        assert result["error"]


class TestApplyTonePrefix:
    def test_neutral_is_a_no_op(self):
        assert apply_tone_prefix("For 3.111, X approves.", "neutral") == "For 3.111, X approves."

    def test_frustrated_gets_an_english_prefix(self):
        result = apply_tone_prefix("For 3.111, X approves.", "frustrated")
        assert result.startswith(EMPATHY_PREFIXES["en"]["frustrated"])
        assert result.endswith("For 3.111, X approves.")

    def test_confused_gets_an_english_prefix(self):
        result = apply_tone_prefix("For 3.111, X approves.", "confused")
        assert result.startswith(EMPATHY_PREFIXES["en"]["confused"])

    def test_respects_the_answer_language(self):
        result = apply_tone_prefix("Pour 3.111, X approuve.", "frustrated", "fr")
        assert result.startswith(EMPATHY_PREFIXES["fr"]["frustrated"])

    def test_unsupported_language_falls_back_to_english_prefix(self):
        result = apply_tone_prefix("Some answer.", "frustrated", "de")
        assert result.startswith(EMPATHY_PREFIXES["en"]["frustrated"])


def test_all_five_languages_have_both_tone_prefixes():
    for lang in ("en", "fr", "es", "pt", "ar"):
        assert "frustrated" in EMPATHY_PREFIXES[lang]
        assert "confused" in EMPATHY_PREFIXES[lang]
