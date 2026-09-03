import pytest

from agent.action_codes import detect_action_code_query, format_action_code_answer


@pytest.mark.parametrize("query", [
    "what's I, A and (i)?",
    "what does C2 mean",
    "explain the action codes",
    "what do the action codes mean",
    "what is A2",
    "what does (i) mean",
])
def test_real_legend_questions_are_detected(query):
    assert detect_action_code_query(query) is not None


@pytest.mark.parametrize("query", [
    "what is 2.120",
    "what's SWIFT",
    "who approves 3.111",
    "I approve this",
    "what is the quarterly mission program",
    "hi",
    "thanks",
    "what does DDG stand for",
    "A2 is fine",
    "C is for cookie",
])
def test_ordinary_questions_never_false_positive(query):
    # The riskiest part of this detector: bare single-letter codes
    # (I/C/R/A) collide with ordinary English (especially the pronoun
    # "I") far too easily to trust alone - every case here either has
    # no explain-intent trigger at all, or only a single bare code with
    # no second code and no digit suffix to make it unambiguous.
    assert detect_action_code_query(query) is None


def test_specific_codes_answer_includes_the_real_dam_definitions():
    detection = detect_action_code_query("what's I, A and (i)?")
    answer = format_action_code_answer(detection)

    assert "Initiate" in answer
    assert "Approve" in answer
    assert "informed" in answer.lower()


def test_generic_legend_question_lists_all_top_level_codes():
    detection = detect_action_code_query("explain the action codes")
    answer = format_action_code_answer(detection)

    for code in ("I", "C", "R", "A", "( i )"):
        assert code in answer


def test_suffixed_code_alone_is_enough_to_trigger_without_a_second_code():
    # Real distinguishing case: "A2" is not a plausible English word,
    # so a single mention (with an explain-intent trigger) is trusted
    # on its own, unlike a bare "A".
    detection = detect_action_code_query("what does A2 mean")
    assert detection == {"codes": ["A2"]}


def test_informed_token_alone_is_enough_to_trigger():
    detection = detect_action_code_query("what does (i) mean")
    assert detection == {"codes": ["( i )"]}
