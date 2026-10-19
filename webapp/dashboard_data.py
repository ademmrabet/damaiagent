from collections import Counter

RESPONSIBILITY_BEARING_TYPES = {"process", "task", "child_task", "threshold_variant"}


# top roles for each action code, used by the clickable chart
def _roles_by_action(responsibilities, limit=15):
    by_action = {}
    for r in responsibilities:
        if r.role == "unresolved":
            continue
        by_action.setdefault(r.action, Counter())[r.role] += 1

    return {
        action: [
            {"role": role, "count": count} for role, count in counter.most_common(limit)
        ]
        for action, counter in by_action.items()
    }


# dashboard numbers for the whole matrix or for one chapter
def _scope_summary(scope_nodes):
    node_counts = Counter(n.node_type for n in scope_nodes)

    responsibilities = [r for n in scope_nodes for r in n.responsibilities]
    total_responsibilities = len(responsibilities)

    action_counts = Counter(r.action for r in responsibilities)

    unresolved = sum(1 for r in responsibilities if r.role == "unresolved")
    unresolved_rate = (
        (unresolved / total_responsibilities) if total_responsibilities else 0.0
    )

    resolved_roles = [r.role for r in responsibilities if r.role != "unresolved"]
    role_counts = Counter(resolved_roles)
    top_roles = [
        {"role": role, "count": count} for role, count in role_counts.most_common(15)
    ]

    bearing_nodes = [
        n for n in scope_nodes if n.node_type in RESPONSIBILITY_BEARING_TYPES
    ]
    avg_responsibilities_per_node = (
        round(total_responsibilities / len(bearing_nodes), 2) if bearing_nodes else 0.0
    )
    no_direct_responsibilities_count = sum(
        1 for n in bearing_nodes if not n.responsibilities
    )
    no_direct_responsibilities_rate = (
        round(no_direct_responsibilities_count / len(bearing_nodes), 4)
        if bearing_nodes
        else 0.0
    )

    return {
        "total_nodes": len(scope_nodes),
        "node_counts_by_type": dict(node_counts),
        "total_responsibilities": total_responsibilities,
        "action_counts": dict(action_counts),
        "unresolved_count": unresolved,
        "unresolved_rate": round(unresolved_rate, 4),
        "distinct_roles": len(set(resolved_roles)),
        "top_roles": top_roles,
        "avg_responsibilities_per_node": avg_responsibilities_per_node,
        "no_direct_responsibilities_count": no_direct_responsibilities_count,
        "no_direct_responsibilities_rate": no_direct_responsibilities_rate,
        "roles_by_action": _roles_by_action(responsibilities),
    }


# compute the dashboard numbers from the graph
def build_summary(nodes, graph):
    all_nodes = list(nodes.values())
    summary = _scope_summary(all_nodes)

    chapters = sorted({n.chapter for n in all_nodes if n.chapter})
    by_chapter = {
        chapter: _scope_summary([n for n in all_nodes if n.chapter == chapter])
        for chapter in chapters
    }

    summary["chapters"] = chapters
    summary["by_chapter"] = by_chapter
    summary["graph"] = {
        "total_graph_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
    }

    return summary
