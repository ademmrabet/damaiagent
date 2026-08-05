from parsing.metadata import (
    NOTE_PATTERN,
    extract_references,
    extract_title,
    remove_references,
)


def test_note_pattern_still_strips_a_standalone_footnote_digit():
    # NOTE_PATTERN targets a bare digit token (space-separated, not
    # glued onto a word) - the fused-onto-a-word case ("Lead2") is a
    # different code path entirely (column_roles.py's character-level
    # stripper), not this regex.
    assert NOTE_PATTERN.sub("", "Task Manager 2 approves") == "Task Manager  approves"


def test_note_pattern_leaves_comma_formatted_amounts_alone():
    assert NOTE_PATTERN.sub("", "Up to UA 2,000,000") == "Up to UA 2,000,000"


def test_note_pattern_leaves_hyphen_prefixed_levels_alone():
    # "PL-2" - digit preceded by a hyphen (the 2026-07-28 fix).
    assert NOTE_PATTERN.sub("", "staff below PL-2 level") == "staff below PL-2 level"


def test_note_pattern_leaves_hyphen_suffixed_numbers_alone():
    # "3-Year" - digit FOLLOWED by a hyphen, the mirror-image gap this
    # fix closes. Real example: 1.114.1/1.114.2's "3-Year Rolling
    # Business Plan" was coming out as "-Year Rolling Business Plan".
    assert NOTE_PATTERN.sub("", "a 3-Year Rolling Business Plan") == "a 3-Year Rolling Business Plan"


def test_see_id_colon_reference_extracted():
    # Real text from 1.117.2 (page 17): a redirect to a whole process,
    # not a specific activity - "See <id>: <short description>".
    text = "CSP / RISP Dialogue Mission (during CSP / See 2.120: Organization of mission RISP preparation)"
    assert extract_references(text) == ["2.120"]


def test_see_id_colon_reference_removed_from_title():
    text = "CSP / RISP Dialogue Mission (during CSP / See 2.120: Organization of mission RISP preparation)"
    cleaned = remove_references(text)
    assert "See 2.120:" not in cleaned
    assert "2.120" not in cleaned


def test_see_id_colon_does_not_leave_garbled_digits_behind():
    # Before the fix: the id inside "See 2.120:" was never recognized
    # as a reference, so NOTE_PATTERN's bare-digit stripper ate both
    # "2" and "120" out of it individually, leaving "See .:" behind
    # in the title - worse than not stripping it at all.
    text = "Preparation Mission for CSP / RISP See 2.120: Organization of mission Completion Report"
    title = extract_title(text, "1.117.1")
    assert "See ." not in title
    assert ".:" not in title


def test_see_id_slash_reference_extracted():
    # Real text from 1.115.1 (page 16): "(See <id> / <id>)" - two
    # alternative activities, not a range to expand.
    text = "Interim CSP/RISP; Country Brief; or JCAS Follow the respective process for new CSP/RISP (See 1.114.1 / 1.114.2)"
    assert extract_references(text) == ["1.114.1", "1.114.2"]


def test_see_id_slash_reference_removed_from_title():
    text = "Interim CSP/RISP; Country Brief; or JCAS Follow the respective process for new CSP/RISP (See 1.114.1 / 1.114.2)"
    cleaned = remove_references(text)
    assert "See" not in cleaned
    assert "1.114.1" not in cleaned
    assert "1.114.2" not in cleaned


def test_see_dam_reference_still_works():
    # Regression check: the original "See DAM <ids>" pattern must
    # still work after adding the two new patterns alongside it.
    text = "Signature ... for See DAM 16.100, 16.200, 16.300, and 16.400 technical cooperation"
    assert extract_references(text) == ["16.100", "16.200", "16.300", "16.400"]


def test_refer_to_activities_range_still_works():
    text = "Communication to Government Refer to Activities 2.114 - 2.117 in Section 2."
    assert extract_references(text) == ["2.114", "2.115", "2.116", "2.117"]
