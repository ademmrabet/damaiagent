from collections import Counter

# Only these node types can ever carry a responsibility directly (see
# schema.Node) - chapter/process nodes are organizational, always
# empty. Used for the two new "how complete is this DAM's coverage"
# KPIs below, so the denominator is real answerable nodes, not the
# full node count.
RESPONSIBILITY_BEARING_TYPES = {"process", "task", "child_task", "threshold_variant"}


def _roles_by_action(responsibilities, limit=15):
    """
    For each action code, the top roles by how often they hold that
    action - the data behind the dashboard's action-code chart also
    being clickable to filter the roles chart to just that action.
    Computed once here (not on the fly in the frontend) so the
    counting logic - excluding "unresolved" the same way top_roles
    already does - lives in exactly one place.
    """
    by_action = {}
    for r in responsibilities:
        if r.role == "unresolved":
            continue
        by_action.setdefault(r.action, Counter())[r.role] += 1

    return {
        action: [{"role": role, "count": count} for role, count in counter.most_common(limit)]
        for action, counter in by_action.items()
    }


def _scope_summary(scope_nodes):
    """
    The full set of dashboard stats for one "scope" - either every
    node in the DAM, or every node in a single chapter. Same shape
    either way, so the frontend can point at either the top-level
    (whole-DAM) fields or `by_chapter[chapter]` without caring which.
    """
    node_counts = Counter(n.node_type for n in scope_nodes)

    responsibilities = [r for n in scope_nodes for r in n.responsibilities]
    total_responsibilities = len(responsibilities)

    action_counts = Counter(r.action for r in responsibilities)

    unresolved = sum(1 for r in responsibilities if r.role == "unresolved")
    unresolved_rate = (unresolved / total_responsibilities) if total_responsibilities else 0.0

    resolved_roles = [r.role for r in responsibilities if r.role != "unresolved"]
    role_counts = Counter(resolved_roles)
    top_roles = [{"role": role, "count": count} for role, count in role_counts.most_common(15)]

    bearing_nodes = [n for n in scope_nodes if n.node_type in RESPONSIBILITY_BEARING_TYPES]
    avg_responsibilities_per_node = (
        round(total_responsibilities / len(bearing_nodes), 2) if bearing_nodes else 0.0
    )
    no_direct_responsibilities_count = sum(1 for n in bearing_nodes if not n.responsibilities)
    no_direct_responsibilities_rate = (
        round(no_direct_responsibilities_count / len(bearing_nodes), 4) if bearing_nodes else 0.0
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


def build_summary(nodes, graph):
    """
    Real, computed stats about the built DAM knowledge graph - not
    static copy. Every number here comes straight from `nodes`/`graph`
    at request time, so it can never drift out of sync with whatever
    the current build actually contains.

    The whole-DAM scope's fields are kept flattened at the top level
    (unchanged from before the 2026-08-06 chapter-filter rework, so
    nothing that already reads this endpoint breaks) - `chapters` and
    `by_chapter` are purely additive. `graph` stays whole-DAM-only on
    purpose: role/reference edges routinely cross chapter boundaries
    (the same role appearing in multiple chapters, a reference pointer
    from one chapter into another), so a "chapter subgraph" would
    either need its own edge-filtering semantics or just be
    misleading - not worth the scope for what the dashboard needs.
    """
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
