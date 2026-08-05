
import networkx as nx

UNRESOLVED_ROLE_ID = "role::__unresolved__"


def _role_node_id(role_name):
    return f"role::{role_name}"


def build_graph(nodes):
    """
    `nodes`: {id: schema.Node} - the output of
    modeling.build_nodes.build_nodes().

    Returns a networkx.MultiDiGraph with every DAM node, every
    distinct role, and the contains/references/responsible_for edges
    connecting them.
    """

    graph = nx.MultiDiGraph()

    for node in nodes.values():
        graph.add_node(
            node.id,
            kind="dam_node",
            node_type=node.node_type,
            chapter=node.chapter,
            process_id=node.process_id,
            parent_task_id=node.parent_task_id,
            title=node.title,
            page=node.page,
            synthetic=node.synthetic,
        )

    seen_roles = set()

    def _ensure_role_node(role_id, label):
        if role_id not in seen_roles:
            graph.add_node(role_id, kind="role", label=label)
            seen_roles.add(role_id)

    skipped_references = []

    for node in nodes.values():

        for child_id in node.children:
            graph.add_edge(node.id, child_id, key="contains", edge_type="contains")

        for ref_id in node.references:
            if ref_id in nodes:
                graph.add_edge(
                    node.id, ref_id, key=f"references::{ref_id}", edge_type="references"
                )
            else:
                skipped_references.append((node.id, ref_id))

        for resp in node.responsibilities:

            if resp.role == "unresolved":
                role_id = UNRESOLVED_ROLE_ID
                _ensure_role_node(role_id, "(unresolved)")
            else:
                role_id = _role_node_id(resp.role)
                _ensure_role_node(role_id, resp.role)

            graph.add_edge(
                role_id,
                node.id,
                edge_type="responsible_for",
                action=resp.action,
                level=resp.level,
                footnote_refs=resp.footnote_refs,
            )

    return graph, skipped_references


def responsible_roles(graph, task_id, action=None):
    """
    Every role connected to `task_id` by a responsible_for edge,
    optionally filtered to a specific action (e.g. "A" for approvers,
    "( i )" for informed parties) - this is the direct answer to both
    founding example questions for this project ("who approves task
    X" / "who needs to be informed for task X"), since both are just
    this same lookup with a different action filter.
    """

    results = []

    for role_id, _, data in graph.in_edges(task_id, data=True):
        if data.get("edge_type") != "responsible_for":
            continue
        if action is not None and data.get("action") != action:
            continue
        results.append({
            "role": graph.nodes[role_id]["label"],
            "action": data.get("action"),
            "level": data.get("level"),
            "footnote_refs": data.get("footnote_refs", []),
        })

    return results


def tasks_for_role(graph, role_name):
    """Every DAM node a given role has any responsibility on."""

    role_id = _role_node_id(role_name)

    if role_id not in graph:
        return []

    results = []

    for _, task_id, data in graph.out_edges(role_id, data=True):
        if data.get("edge_type") != "responsible_for":
            continue
        results.append({
            "task_id": task_id,
            "title": graph.nodes[task_id].get("title", ""),
            "action": data.get("action"),
        })

    return results
