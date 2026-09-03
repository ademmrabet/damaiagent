import pytest

from modeling.build_nodes import build_nodes
from modeling.graph import build_graph
from webapp.dashboard_data import build_summary
from tests.fixtures.known_cases import PDF_PATH


@pytest.fixture(scope="module")
def summary():
    nodes = build_nodes(PDF_PATH)
    graph, _ = build_graph(nodes)
    return build_summary(nodes, graph)


def test_total_nodes_matches_known_build(summary):
    assert summary["total_nodes"] == 327


def test_node_counts_by_type_sum_to_total(summary):
    assert sum(summary["node_counts_by_type"].values()) == summary["total_nodes"]


def test_action_counts_cover_known_action_letters(summary):
    # Not asserting exact values (those shift slightly as parsing
    # improves) - just that the real, expected action types are present
    # at all, which would fail loudly if action extraction broke.
    assert "A" in summary["action_counts"]
    assert "I" in summary["action_counts"] or "( i )" in summary["action_counts"]


def test_unresolved_rate_stays_low(summary):
    # Matches the 0.5% figure from the 2026-07-28 decisions.md entry -
    # a regression test, not a fresh claim.
    assert summary["unresolved_rate"] <= 0.02


def test_top_roles_sorted_descending_and_capped(summary):
    counts = [r["count"] for r in summary["top_roles"]]
    assert counts == sorted(counts, reverse=True)
    assert len(summary["top_roles"]) <= 15


def test_graph_node_count_includes_role_nodes(summary):
    # Graph nodes = DAM nodes + distinct role nodes (+ the unresolved
    # placeholder) - always >= total_nodes, never equal unless there
    # were zero responsibilities at all.
    assert summary["graph"]["total_graph_nodes"] > summary["total_nodes"]


def test_chapters_list_is_sorted_and_non_empty(summary):
    assert summary["chapters"] == sorted(summary["chapters"])
    assert len(summary["chapters"]) > 0


def test_by_chapter_covers_every_listed_chapter(summary):
    assert set(summary["by_chapter"].keys()) == set(summary["chapters"])


def test_by_chapter_node_counts_sum_to_the_whole_dam_total(summary):
    # Every node belongs to exactly one chapter, so summing the
    # per-chapter breakdown should exactly reconstruct the whole-DAM
    # total - a strong, cheap regression guard against a filtering bug
    # (e.g. a node counted in the wrong chapter, or double-counted).
    total_from_chapters = sum(
        chapter_summary["total_nodes"] for chapter_summary in summary["by_chapter"].values()
    )
    assert total_from_chapters == summary["total_nodes"]


def test_by_chapter_has_the_same_shape_as_the_whole_dam_summary(summary):
    expected_keys = {
        "total_nodes", "node_counts_by_type", "total_responsibilities",
        "action_counts", "unresolved_count", "unresolved_rate",
        "distinct_roles", "top_roles", "avg_responsibilities_per_node",
        "no_direct_responsibilities_count", "no_direct_responsibilities_rate",
        "roles_by_action",
    }
    any_chapter = next(iter(summary["by_chapter"].values()))
    assert expected_keys.issubset(any_chapter.keys())


def test_avg_responsibilities_per_node_is_sane(summary):
    # Should be a small positive number of responsibilities per
    # answerable node, not something like total_responsibilities
    # itself (would indicate the denominator picked the wrong node set).
    assert 0 < summary["avg_responsibilities_per_node"] < 20


def test_no_direct_responsibilities_rate_is_a_real_fraction(summary):
    assert 0 <= summary["no_direct_responsibilities_rate"] <= 1


def test_roles_by_action_only_covers_real_action_codes(summary):
    # Not exact equality: an action code whose every single occurrence
    # happens to be role == "unresolved" legitimately has no entry
    # here at all (roles_by_action excludes unresolved, same as
    # top_roles already does) - confirmed real, not a bug, via the
    # 'O'/'F' action codes in this DAM.
    assert set(summary["roles_by_action"].keys()) <= set(summary["action_counts"].keys())


def test_roles_by_action_entries_sorted_descending_and_capped(summary):
    for entries in summary["roles_by_action"].values():
        counts = [e["count"] for e in entries]
        assert counts == sorted(counts, reverse=True)
        assert len(entries) <= 15


def test_roles_by_action_never_includes_the_unresolved_placeholder(summary):
    for entries in summary["roles_by_action"].values():
        assert all(e["role"] != "unresolved" for e in entries)
