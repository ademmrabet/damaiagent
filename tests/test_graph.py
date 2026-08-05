import pytest

from modeling.build_nodes import build_nodes
from modeling.graph import build_graph, responsible_roles, tasks_for_role, UNRESOLVED_ROLE_ID
from tests.fixtures.known_cases import PDF_PATH


@pytest.fixture(scope="module")
def graph_and_nodes():
    nodes = build_nodes(PDF_PATH)
    graph, skipped_refs = build_graph(nodes)
    return graph, nodes, skipped_refs


def test_node_count_matches_dam_nodes_plus_roles(graph_and_nodes):
    graph, nodes, _ = graph_and_nodes

    role_strings = {
        r.role for n in nodes.values() for r in n.responsibilities
    }

    assert graph.number_of_nodes() == len(nodes) + len(role_strings)


def test_who_approves_matches_screenshot(graph_and_nodes):
    graph, _, _ = graph_and_nodes

    approvers = responsible_roles(graph, "3.111", action="A")
    roles = {a["role"] for a in approvers}

    assert roles == {"Origination Sector Manager", "Supporting Dept. Division Manager"}

    footnotes = {a["role"]: a["footnote_refs"] for a in approvers}
    assert footnotes["Origination Sector Manager"] == [3]
    assert footnotes["Supporting Dept. Division Manager"] == [4]


def test_who_must_be_informed_is_the_same_query_shape(graph_and_nodes):
    graph, _, _ = graph_and_nodes

    informed = responsible_roles(graph, "2.126", action="( i )")
    assert len(informed) > 0
    assert all(a["action"] == "( i )" for a in informed)


def test_contains_edges_are_direct_children_only(graph_and_nodes):
    graph, _, _ = graph_and_nodes

    children = [
        target for _, target, data in graph.out_edges("2.513", data=True)
        if data.get("edge_type") == "contains"
    ]
    assert sorted(children) == ["2.513.1", "2.513.2", "2.513.3"]


def test_out_of_scope_references_are_skipped_not_wired(graph_and_nodes):
    graph, nodes, skipped_refs = graph_and_nodes

    assert "16.100" not in nodes
    assert ("2.312.2", "16.100") in skipped_refs

    out_edges = [
        target for _, target, data in graph.out_edges("2.312.2", data=True)
        if data.get("edge_type") == "references"
    ]
    assert "16.100" not in out_edges


def test_unresolved_responsibilities_stay_visible_not_dropped(graph_and_nodes):
    graph, nodes, _ = graph_and_nodes

    has_unresolved = any(
        r.role == "unresolved"
        for n in nodes.values()
        for r in n.responsibilities
    )

    if has_unresolved:
        assert UNRESOLVED_ROLE_ID in graph
        assert graph.out_degree(UNRESOLVED_ROLE_ID) > 0


def test_tasks_for_role_is_reverse_of_responsible_roles(graph_and_nodes):
    graph, _, _ = graph_and_nodes

    role = "Origination Sector Manager"
    forward = tasks_for_role(graph, role)
    task_ids = {t["task_id"] for t in forward}

    assert "3.111" in task_ids

    approvers = {a["role"] for a in responsible_roles(graph, "3.111")}
    assert role in approvers
