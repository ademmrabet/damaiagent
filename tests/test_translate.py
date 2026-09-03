from unittest.mock import Mock

import pytest

from llm.base import LLMUnavailableError
from llm.translate import (
    LANGUAGE_NAMES,
    detect_and_translate_to_english,
    looks_non_english,
    translate_text,
)


@pytest.mark.parametrize("text", [
    "who approves 2.126",
    "who approves the quarterly mission program",
    "help",
    "mission",
    "",
])
def test_looks_non_english_is_false_for_plain_english(text):
    assert looks_non_english(text) is False


@pytest.mark.parametrize("text", [
    "qui approuve le programme de mission",
    "quién aprueba el programa de misión",
    "quem aprova o programa de missão",
    "من يوافق على برنامج البعثة",
    "où est-ce que je dois signer",
    # The exact real gap found while building this: a short, natural
    # question with only ONE real function word once the DAM-specific
    # verb is excluded ("qui") - an earlier version of this heuristic
    # required 2+ hits and missed it entirely.
    "qui approuve 3.111",
])
def test_looks_non_english_is_true_for_real_examples(text):
    assert looks_non_english(text) is True


@pytest.mark.parametrize("text", [
    "who approves as required",
    "who checks the annual budget submission",
    "and who needs to sign off on this",
])
def test_looks_non_english_has_no_false_positives_on_tricky_english(text):
    # "as" (Portuguese) and "o"/similar short tokens are deliberately
    # excluded from the function-word lists for exactly this reason -
    # both are also ordinary English words, and a false positive here
    # would burn an unnecessary translation round trip on completely
    # normal English questions.
    assert looks_non_english(text) is False


def _provider(reply_text):
    provider = Mock()
    provider.chat = Mock(return_value=reply_text)
    provider.name = "fake"
    return provider


class TestDetectAndTranslateToEnglish:
    def test_parses_a_well_formed_response(self):
        provider = _provider("LANGUAGE: fr\nTRANSLATED: who approves the mission program")
        result = detect_and_translate_to_english("qui approuve le programme", provider)
        assert result["language"] == "fr"
        assert result["translated_text"] == "who approves the mission program"
        assert result["used_llm"] is True
        assert result["error"] is None

    def test_preserves_dam_ids_when_the_model_does(self):
        # The prompt instructs the model to copy id-shaped substrings
        # verbatim - this pins that the plumbing doesn't itself mangle
        # them, given a well-behaved model response.
        provider = _provider("LANGUAGE: fr\nTRANSLATED: who approves 2.126")
        result = detect_and_translate_to_english("qui approuve 2.126", provider)
        assert "2.126" in result["translated_text"]

    def test_no_provider_falls_back_to_english_unchanged(self):
        result = detect_and_translate_to_english("qui approuve le programme", None)
        assert result["language"] == "en"
        assert result["translated_text"] == "qui approuve le programme"
        assert result["used_llm"] is False
        assert result["error"]

    def test_provider_failure_falls_back_safely(self):
        provider = Mock()
        provider.chat = Mock(side_effect=LLMUnavailableError("network down"))
        result = detect_and_translate_to_english("qui approuve le programme", provider)
        assert result["used_llm"] is False
        assert result["translated_text"] == "qui approuve le programme"
        assert "network down" in result["error"]

    def test_unparseable_response_falls_back_safely(self):
        provider = _provider("I'm not going to follow the format.")
        result = detect_and_translate_to_english("qui approuve", provider)
        assert result["used_llm"] is False
        assert result["language"] == "en"
        assert result["error"]

    def test_unrecognized_language_code_falls_back_safely(self):
        provider = _provider("LANGUAGE: zz\nTRANSLATED: something")
        result = detect_and_translate_to_english("???", provider)
        assert result["used_llm"] is False
        assert result["error"]


class TestTranslateText:
    def test_english_target_is_a_no_op(self):
        result = translate_text("Hello there", "en", _provider("should not be used"))
        assert result["text"] == "Hello there"
        assert result["used_llm"] is False

    def test_translates_into_the_target_language(self):
        provider = _provider("Bonjour ! Comment puis-je vous aider avec le DAM ?")
        result = translate_text("Hello! How can I help with the DAM?", "fr", provider)
        assert result["used_llm"] is True
        assert result["text"] == "Bonjour ! Comment puis-je vous aider avec le DAM ?"

    def test_no_provider_falls_back_to_original_text(self):
        result = translate_text("Hello there", "fr", None)
        assert result["text"] == "Hello there"
        assert result["used_llm"] is False
        assert result["error"]

    def test_provider_failure_falls_back_to_original_text(self):
        provider = Mock()
        provider.chat = Mock(side_effect=LLMUnavailableError("timeout"))
        result = translate_text("Hello there", "es", provider)
        assert result["text"] == "Hello there"
        assert result["used_llm"] is False
        assert "timeout" in result["error"]

    def test_unsupported_language_code_is_a_no_op(self):
        result = translate_text("Hello there", "de", _provider("should not be used"))
        assert result["text"] == "Hello there"
        assert result["used_llm"] is False


def test_all_four_requested_languages_are_supported():
    for code in ("fr", "es", "pt", "ar"):
        assert code in LANGUAGE_NAMES
