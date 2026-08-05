
from modeling.graph import responsible_roles
from knowledge.search import resolve_query
from agent.authority import detect_intent
from agent.smalltalk import detect_smalltalk
from agent.glossary import (
    detect_glossary_query,
    format_glossary_answer,
    expand_acronym_in_role_name,
)

MIN_TEXT_SEARCH_SCORE = 0.15


def _empty_result(answer, method, score=None):
    return {
        "answer": answer,
        "node_id": None,
        "method": method,
        "score": score,
        "roles": None,
        "node_title": None,
        "node_type": None,
        "intent": None,
    }


def _format_invalid_id_answer(invalid_id, suggestions):
    if suggestions:
        listed = ", ".join(f"{s['id']} ({s['title']!r})" for s in suggestions)
        return (
            f"{invalid_id!r} doesn't exist in the DAM - that task/code "
            f"isn't in the matrix. Did you mean one of these? {listed}"
        )
    return (
        f"{invalid_id!r} doesn't exist in the DAM - that task/code "
        f"isn't in the matrix. Double-check the id, or describe the "
        f'activity in words instead (e.g. "who approves the mission '
        f'program").'
    )


def _format_role_list(roles):
    by_role = {}
    for r in roles:
        by_role.setdefault(r["role"], set()).update(r["footnote_refs"])

    parts = []
    already_expanded = set()
    for role_name in sorted(by_role):
        footnotes = sorted(by_role[role_name])
        display_name = expand_acronym_in_role_name(role_name, already_expanded)
        if footnotes:
            note = "footnote " + ", ".join(str(n) for n in footnotes)
            parts.append(f"{display_name} ({note})")
        else:
            parts.append(display_name)

    return parts


def _children_list_text(node, nodes):
    if not node.children:
        return None

    listed = ", ".join(
        f"{child_id} ({nodes[child_id].title!r})"
        for child_id in node.children[:8]
        if child_id in nodes
    )
    more = "" if len(node.children) <= 8 else f", and {len(node.children) - 8} more"

    return listed + more


def _format_children_pointer(node, nodes):
    children_text = _children_list_text(node, nodes)
    if children_text is None:
        return None

    return (
        f"{node.id} ({node.title!r}) is a {node.node_type} - it doesn't carry "
        f"responsibilities directly. Its activities: {children_text}."
    )


def _matching_roles(roles, intent):
    return [r for r in roles if intent["matches"](r["action"], r["level"])]


def _format_reference_pointer(node, nodes, graph, intent=None):
    """
    For a node that carries no responsibilities of its own but DOES
    point somewhere else in the DAM (e.g. 1.117.2's real text is "See
    2.120: Organization of mission" - a redirect to a whole process,
    not a specific activity's own row). Tries each reference in order;
    if the referenced node itself has responsibilities, surfaces those
    (filtered by intent if one was given); if it has none of its own
    but has children, points to those instead - the same "don't dead-
    end" pattern _format_children_pointer already uses, just reached
    through a reference hop instead of a parent/child edge.

    Some references point entirely outside this document's ~79-page
    scope (e.g. 2.312.2's "See DAM 16.100, 16.200, 16.300, and
    16.400" - chapter 16 isn't part of this DAM export at all, see
    schema.py's own documented caution and the 2026-07-28 graph-
    building entry). Those are real, correct answers from the DAM's
    own text - "this is governed elsewhere" - not the same as "nothing
    is recorded", so they get their own message instead of silently
    falling through to the generic dead-end one.
    """
    out_of_scope = []

    for ref_id in node.references:
        if ref_id not in nodes:
            out_of_scope.append(ref_id)
            continue

        ref_node = nodes[ref_id]
        ref_roles = responsible_roles(graph, ref_id)

        if ref_roles:
            if intent:
                matching = _matching_roles(ref_roles, intent)
                if not matching:
                    continue
                role_list = _format_role_list(matching)
                return (
                    f"{node.id} ({node.title!r}) redirects to {ref_id} "
                    f"({ref_node.title!r}), where the following "
                    f"{intent['verb_phrase']}: " + ", ".join(role_list) + "."
                )
            body = _format_full_answer(ref_node, ref_roles, nodes, graph)
            return f"{node.id} ({node.title!r}) redirects to {ref_id}:\n{body}"

        if ref_node.children:
            children_text = _children_list_text(ref_node, nodes)
            if children_text:
                return (
                    f"{node.id} ({node.title!r}) redirects to {ref_id} "
                    f"({ref_node.title!r}), a {ref_node.node_type} that "
                    f"doesn't carry responsibilities directly. Its "
                    f"activities: {children_text}."
                )

    if out_of_scope:
        verb = "is" if len(out_of_scope) == 1 else "are"
        return (
            f"{node.id} ({node.title!r}) is governed by DAM section(s) "
            f"{', '.join(out_of_scope)}, which {verb} outside the scope "
            f"of this document."
        )

    return None


def _format_intent_answer(node, intent, roles, matching, nodes, graph):
    if not matching:
        if not roles:
            pointer = _format_children_pointer(node, nodes)
            if not pointer:
                pointer = _format_reference_pointer(node, nodes, graph, intent)
            if pointer:
                return pointer
        return (
            f"No one is recorded to {intent['name']} on {node.id} "
            f"({node.title!r}) in the DAM."
        )

    role_list = _format_role_list(matching)
    return (
        f"For {node.id} ({node.title!r}), the following {intent['verb_phrase']}: "
        + ", ".join(role_list) + "."
    )


def _format_full_answer(node, roles, nodes, graph):
    if not roles:
        pointer = _format_children_pointer(node, nodes)
        if not pointer:
            pointer = _format_reference_pointer(node, nodes, graph)
        if pointer:
            return pointer
        return f"{node.id} ({node.title!r}) has no recorded responsibilities."

    action_order = ["I", "C", "R", "A", "( i )"]

    def _action_rank(action):
        for i, prefix in enumerate(action_order):
            if action == prefix or action.startswith(prefix):
                return i
        return len(action_order)

    grouped = {}
    for r in roles:
        grouped.setdefault(r["action"], []).append(r)

    lines = [f"{node.id} ({node.title!r}):"]
    for action in sorted(grouped, key=_action_rank):
        role_list = _format_role_list(grouped[action])
        lines.append(f"  {action}: " + ", ".join(role_list))

    return "\n".join(lines)


def answer_question(query, nodes, graph, vectorizer, matrix, searchable_ids):
    """
    Returns {"answer": str, "node_id": str|None, "method": str|None,
    "score": float|None, "roles": list|None, "node_title": str|None,
    "node_type": str|None, "intent": str|None}. "answer" is always the
    trusted, deterministic prose - the rest is the evidence behind it
    (which node was resolved, how, how confidently, and the exact raw
    facts "answer" was built from) so a caller can show that evidence
    directly, or hand "roles" to something else (e.g. an LLM phrasing
    layer) as verified ground truth instead of re-deriving it.
    """

    smalltalk_reply = detect_smalltalk(query)
    if smalltalk_reply:
        return _empty_result(smalltalk_reply, "smalltalk")

    glossary_detection = detect_glossary_query(query)
    if glossary_detection:
        answer = format_glossary_answer(glossary_detection)
        method = "glossary" if glossary_detection["found"] else "glossary_not_found"
        return _empty_result(answer, method)

    resolution = resolve_query(query, nodes, vectorizer, matrix, searchable_ids)

    if resolution["method"] == "invalid_id":
        answer = _format_invalid_id_answer(resolution["invalid_id"], resolution["suggestions"])
        return _empty_result(answer, "invalid_id")

    if not resolution["matches"]:
        return _empty_result(
            "I couldn't find a task in the DAM matching that question.",
            resolution["method"],
        )

    top = resolution["matches"][0]

    if resolution["method"] == "text_search" and top["score"] < MIN_TEXT_SEARCH_SCORE:
        suggestions = ", ".join(
            f"{m['id']} ({nodes[m['id']].title!r})" for m in resolution["matches"][:3]
        )
        return _empty_result(
            f"I'm not confident which task that refers to. Closest matches: {suggestions}.",
            resolution["method"],
            score=top["score"],
        )

    node_id = top["id"]
    node = nodes[node_id]
    roles = responsible_roles(graph, node_id)

    intent = detect_intent(query)

    if intent:
        matching = _matching_roles(roles, intent)
        answer = _format_intent_answer(node, intent, roles, matching, nodes, graph)
        facts = matching
    else:
        answer = _format_full_answer(node, roles, nodes, graph)
        facts = roles

    return {
        "answer": answer,
        "node_id": node_id,
        "method": resolution["method"],
        "score": top["score"],
        "roles": facts,
        "node_title": node.title,
        "node_type": node.node_type,
        "intent": intent["name"] if intent else None,
    }
