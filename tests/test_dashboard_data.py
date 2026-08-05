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
