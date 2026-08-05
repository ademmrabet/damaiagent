from collections import Counter


def build_summary(nodes, graph):
    """
    Real, computed stats about the built DAM knowledge graph - not
    static copy. Every number here comes straight from `nodes`/`graph`
    at request time, so it can never drift out of sync with whatever
    the current build actually contains (the same reasoning behind
    reading authority codes from their own reference file instead of
    a hand-written vocabulary - one source of truth, queried live).
    """
    node_counts = Counter(n.node_type for n in nodes.values())

    responsibilities = [r for n in nodes.values() for r in n.responsibilities]
    total_responsibilities = len(responsibilities)

    action_counts = Counter(r.action for r in responsibilities)

    unresolved = sum(1 for r in responsibilities if r.role == "unresolved")
    unresolved_rate = (unresolved / total_responsibilities) if total_responsibilities else 0.0

    resolved_roles = [r.role for r in responsibilities if r.role != "unresolved"]
    role_counts = Counter(resolved_roles)
    top_roles = [{"role": role, "count": count} for role, count in role_counts.most_common(15)]

    return {
        "total_nodes": len(nodes),
        "node_counts_by_type": dict(node_counts),
        "total_responsibilities": total_responsibilities,
        "action_counts": dict(action_counts),
        "unresolved_count": unresolved,
        "unresolved_rate": round(unresolved_rate, 4),
        "distinct_roles": len(set(resolved_roles)),
        "top_roles": top_roles,
        "graph": {
            "total_graph_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
        },
    }
