import pytest

from modeling.build_nodes import build_nodes
from tests.fixtures.known_cases import PDF_PATH


@pytest.fixture(scope="module")
def nodes():
    return build_nodes(PDF_PATH)


def test_full_document_builds_without_error(nodes):
    assert len(nodes) > 300


def test_chapter_process_task_hierarchy_is_internally_consistent(nodes):
    expected_child_type = {
        "chapter": "process",
        "process": "task",
        "task": "child_task",
        "child_task": "threshold_variant",
    }

    checked = 0

    for node in nodes.values():
        if node.node_type not in expected_child_type:
            continue

        for child_id in node.children:
            child = nodes[child_id]
            assert child.node_type == expected_child_type[node.node_type], (
                f"{node.id} ({node.node_type}) has child {child_id} "
                f"with wrong node_type {child.node_type}"
            )
            checked += 1

    assert checked > 200


def test_process_children_are_not_empty(nodes):
    assert nodes["2.510"].children == ["2.511", "2.512", "2.513", "2.514", "2.515", "2.516"]


def test_chapter_children_are_processes_only(nodes):
    chapter_2 = nodes["2"]
    assert all(nodes[cid].node_type == "process" for cid in chapter_2.children)
    assert "2.510" in chapter_2.children
    assert "2.513" not in chapter_2.children


def test_threshold_variant_merged_into_parent_child_task(nodes):
    child_task = nodes["2.513.3"]
    assert child_task.children == ["2.513.3.a", "2.513.3.b", "2.513.3.c"]

    variant = nodes["2.513.3.a"]
    assert variant.node_type == "threshold_variant"
    assert variant.parent_task_id == "2.513.3"
    assert variant.children == []
    assert not variant.has_children


def test_informed_marker_gets_a_resolved_role(nodes):
    task = nodes["2.126"]
    informed = [r for r in task.responsibilities if r.action == "( i )"]
    assert informed, "expected at least one informed responsibility on 2.126"
    for r in informed:
        assert r.role != "unresolved"


def test_unresolved_role_rate_stays_low(nodes):
    total = 0
    unresolved = 0

    for node in nodes.values():
        for r in node.responsibilities:
            total += 1
            if r.role == "unresolved":
                unresolved += 1

    assert total > 900
    assert unresolved / total < 0.05
