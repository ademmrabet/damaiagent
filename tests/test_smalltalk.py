import pytest

from agent.smalltalk import detect_smalltalk


@pytest.mark.parametrize("query", [
    "hi", "Hi", "HI!", "hello", "hello!", "hey", "heyy", "hiya", "yo",
    "howdy", "good morning", "Good Evening.", "greetings",
])
def test_greetings_get_a_reply(query):
    reply = detect_smalltalk(query)
    assert reply is not None
    assert "Hello" in reply


@pytest.mark.parametrize("query", ["bye", "goodbye", "see you", "take care", "later"])
def test_farewells_get_a_reply(query):
    reply = detect_smalltalk(query)
    assert reply is not None
    assert "Goodbye" in reply


@pytest.mark.parametrize("query", ["thanks", "thank you", "thx", "much appreciated"])
def test_thanks_get_a_reply(query):
    reply = detect_smalltalk(query)
    assert reply is not None
    assert "welcome" in reply.lower()


@pytest.mark.parametrize("query", ["how are you", "how are you?", "how's it going", "what's up"])
def test_how_are_you_gets_a_reply(query):
    assert detect_smalltalk(query) is not None


@pytest.mark.parametrize("query", ["help", "what can you do", "who are you", "what is this"])
def test_help_gets_a_reply(query):
    reply = detect_smalltalk(query)
    assert reply is not None
    assert "Delegation of Authority Matrix" in reply


@pytest.mark.parametrize("query", [
    "who approves 2.126",
    "which staff need to be informed",
    "hi, who approves 3.111",  # a real question that happens to start with a greeting word
    "history of the DAM",       # contains "hi" as a substring, must not false-positive
    "chief financial officer",
    "",
    "   ",
])
def test_real_questions_are_not_treated_as_smalltalk(query):
    assert detect_smalltalk(query) is None


@pytest.mark.parametrize("query,expected_substring", [
    ("helo", "Hello"),
    ("godbye", "Goodbye"),
    ("much apreciated", "welcome"),
])
def test_typo_d_smalltalk_still_gets_the_right_kind_of_reply(query, expected_substring):
    reply = detect_smalltalk(query)
    assert reply is not None
    assert expected_substring.lower() in reply.lower()
