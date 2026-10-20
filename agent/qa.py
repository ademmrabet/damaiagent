import re
from difflib import SequenceMatcher

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from modeling.graph import responsible_roles
from knowledge.search import resolve_query
from agent.authority import detect_intent, action_label, _INTENT_VOCAB
from agent.smalltalk import detect_smalltalk
from agent.glossary import (
    detect_glossary_query,
    format_glossary_answer,
    expand_acronym_in_role_name,
)
from agent.action_codes import detect_action_code_query, format_action_code_answer

MIN_TEXT_SEARCH_SCORE = 0.15

CLARIFICATION_MAX_SCORE = 0.6
CLARIFICATION_MIN_GAP = 0.15

_EXTRA_GENERIC_WORDS = {
    "task",
    "activity",
    "process",
    "dam",
    "please",
    "tell",
    "party",
    "parties",
    "partie",
    "role",
    "roles",
    "people",
}
_GENERIC_QUERY_WORDS = ENGLISH_STOP_WORDS | _INTENT_VOCAB | _EXTRA_GENERIC_WORDS
_WORD_RE = re.compile(r"[a-z']+")


# count meaningful words, ignoring stop words and generic ones
def _content_word_count(query):
    words = _WORD_RE.findall(query.lower())
    return sum(1 for w in words if len(w) >= 3 and w not in _GENERIC_QUERY_WORDS)


# true if some meaningful word of the question also appears (even with a typo) in the title
def _shares_content_word(query, title):
    title_words = set(_WORD_RE.findall(title.lower()))
    for w in _WORD_RE.findall(query.lower()):
        if len(w) < 3 or w in _GENERIC_QUERY_WORDS:
            continue
        for t in title_words:
            if w == t or w[:5] == t[:5] and len(w) >= 5 and len(t) >= 5:
                return True
            if SequenceMatcher(None, w, t).ratio() >= 0.8:
                return True
    return False


# true when the match is too vague or too close to trust
def _needs_clarification(query, matches):
    too_vague = _content_word_count(query) <= 1
    top_score = matches[0]["score"]

    if len(matches) < 2:
        return too_vague and top_score < CLARIFICATION_MAX_SCORE

    close_gap = (top_score - matches[1]["score"]) < CLARIFICATION_MIN_GAP
    return (too_vague and top_score < CLARIFICATION_MAX_SCORE) or (
        close_gap and top_score < 0.85
    )


# ask the user which of the top matches they meant
def _format_clarification_answer(matches, nodes):
    suggestions = ", ".join(
        f"{m['id']} ({nodes[m['id']].title!r})" for m in matches[:3]
    )
    return (
        "That's a bit broad for me to pin down to one task. Did you mean "
        f"one of these: {suggestions}? Or try describing the specific "
        'activity, e.g. "who approves the quarterly mission program".'
    )


CONTEXT_OVERRIDE_MAX_SCORE = 0.5

_HAS_DIGIT = re.compile(r"\d")

_FOLLOWUP_MARKERS = {
    "and",
    "also",
    "then",
    "that",
    "this",
    "it",
    "its",
    "them",
    "those",
    "same",
    "again",
    "too",
    "about",
}


# true if the question looks like a follow-up and not a new topic
def _looks_like_followup(query):
    content = _content_word_count(query)
    if content == 0:
        return True
    if content > 1:
        return False
    words = set(_WORD_RE.findall(query.lower()))
    return bool(words & _FOLLOWUP_MARKERS)


# result dict for answers that are not tied to a node
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
        "llm_facts": None,
        "base_answer": answer,
        "mandatory_notes_text": "",
    }


# tell the user the id does not exist and suggest close ones
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


# join role names, adding footnote numbers and expanded acronyms
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


# short list of the child tasks under a process
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


# explain that this node has no roles and list its activities
def _format_children_pointer(node, nodes):
    children_text = _children_list_text(node, nodes)
    if children_text is None:
        return None

    return (
        f"{node.id} ({node.title!r}) is a {node.node_type} - it doesn't carry "
        f"responsibilities directly. Its activities: {children_text}."
    )


# roles whose action fits the asked intent
def _matching_roles(roles, intent):
    return [r for r in roles if intent["matches"](r["action"], r["level"])]


# roles with a check/verify action
def _check_verify_roles(roles):
    return [r for r in roles if r["action"] in ("C", "C1", "C2")]


# roles that only need to be informed
def _informed_roles(roles):
    return [r for r in roles if r["action"] == "( i )"]


# always mention check/verify roles and who must be informed
def _format_mandatory_notes(roles, intent_name):
    notes = []

    if intent_name != "check":
        check_roles = _check_verify_roles(roles)
        if check_roles:
            role_list = _format_role_list(check_roles)
            notes.append(
                "This task must also be checked/verified by "
                + ", ".join(role_list)
                + "."
            )

    if intent_name != "informed":
        informed_roles = _informed_roles(roles)
        if informed_roles:
            role_list = _format_role_list(informed_roles)
            notes.append(", ".join(role_list) + " must also be informed.")

    return " ".join(notes)


# for nodes that only say 'see X', answer with the referenced node
def _format_reference_pointer(node, nodes, graph, intent=None):
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


# answer for one specific intent, like only the approvers
def _format_intent_answer(node, intent, roles, matching, nodes, graph):
    if not matching:
        if not roles:
            pointer = _format_children_pointer(node, nodes)
            if not pointer:
                pointer = _format_reference_pointer(node, nodes, graph, intent)
            if pointer:
                return pointer, ""
        base = (
            f"No one is recorded to {intent['name']} on {node.id} "
            f"({node.title!r}) in the DAM."
        )
    else:
        role_list = _format_role_list(matching)
        base = (
            f"For {node.id} ({node.title!r}), the following {intent['verb_phrase']}: "
            + ", ".join(role_list)
            + "."
        )

    notes = _format_mandatory_notes(roles, intent["name"])
    return base, notes


# full answer when no specific intent was asked
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

    def _action_heading(action):
        label = action_label(action)
        return label if action == "( i )" else f"{label} ({action})"

    grouped = {}
    for r in roles:
        grouped.setdefault(r["action"], []).append(r)

    lines = [f"{node.id} ({node.title!r}):"]
    for action in sorted(grouped, key=_action_rank):
        role_list = _format_role_list(grouped[action])
        lines.append(f"  {_action_heading(action)}: " + ", ".join(role_list))

    return "\n".join(lines)


# main entry: question in, structured answer out
def answer_question(
    query, nodes, graph, vectorizer, matrix, searchable_ids, previous_node_id=None
):

    smalltalk_reply = detect_smalltalk(query)
    if smalltalk_reply:
        return _empty_result(smalltalk_reply, "smalltalk")

    glossary_detection = detect_glossary_query(query)
    if glossary_detection:
        answer = format_glossary_answer(glossary_detection)
        method = "glossary" if glossary_detection["found"] else "glossary_not_found"
        return _empty_result(answer, method)

    action_code_detection = detect_action_code_query(query)
    if action_code_detection:
        answer = format_action_code_answer(action_code_detection)
        return _empty_result(answer, "action_code_legend")

    resolution = resolve_query(query, nodes, vectorizer, matrix, searchable_ids)

    if resolution["method"] == "text_search":
        resolution["matches"] = [
            m
            for m in resolution["matches"]
            if _shares_content_word(query, nodes[m["id"]].title)
        ]

    context_available = (
        previous_node_id
        and previous_node_id in nodes
        and not _HAS_DIGIT.search(query)
        and _looks_like_followup(query)
    )

    resolution_is_weak = resolution["method"] == "text_search" and (
        not resolution["matches"]
        or resolution["matches"][0]["score"] < CONTEXT_OVERRIDE_MAX_SCORE
    )

    if context_available and resolution_is_weak:
        node_id = previous_node_id
        method = "context_carryover"
        score = None
    else:
        if resolution["method"] == "invalid_id":
            answer = _format_invalid_id_answer(
                resolution["invalid_id"], resolution["suggestions"]
            )
            return _empty_result(answer, "invalid_id")

        if not resolution["matches"]:
            if _content_word_count(query) <= 1:
                return _empty_result(
                    "I need a bit more to go on - can you name the "
                    'specific activity, e.g. "who approves the '
                    'quarterly mission program"?',
                    "needs_clarification",
                )
            return _empty_result(
                "That looks like it's outside what I can help with - I "
                "only answer questions about the DAM (who approves, "
                "checks, reviews, initiates, or must be informed on a "
                "task). Try asking about a specific activity or process "
                "instead.",
                "out_of_scope",
            )

        top = resolution["matches"][0]

        if resolution["method"] == "text_search" and _needs_clarification(
            query, resolution["matches"]
        ):
            return _empty_result(
                _format_clarification_answer(resolution["matches"], nodes),
                "needs_clarification",
                score=top["score"],
            )

        if (
            resolution["method"] == "text_search"
            and top["score"] < MIN_TEXT_SEARCH_SCORE
        ):
            suggestions = ", ".join(
                f"{m['id']} ({nodes[m['id']].title!r})"
                for m in resolution["matches"][:3]
            )
            return _empty_result(
                f"I'm not confident which task that refers to. Closest matches: {suggestions}.",
                resolution["method"],
                score=top["score"],
            )

        node_id = top["id"]
        method = resolution["method"]
        score = top["score"]

    node = nodes[node_id]
    roles = responsible_roles(graph, node_id)

    intent = detect_intent(query)

    if intent:
        matching = _matching_roles(roles, intent)
        base_answer, mandatory_notes_text = _format_intent_answer(
            node, intent, roles, matching, nodes, graph
        )
        answer = (
            f"{base_answer} {mandatory_notes_text}"
            if mandatory_notes_text
            else base_answer
        )
        facts = list(matching)
        if intent["name"] != "check":
            facts.extend(_check_verify_roles(roles))
        if intent["name"] != "informed":
            facts.extend(_informed_roles(roles))
        llm_facts = matching
    else:
        base_answer = _format_full_answer(node, roles, nodes, graph)
        answer = base_answer
        mandatory_notes_text = ""
        facts = roles
        llm_facts = None

    return {
        "answer": answer,
        "node_id": node_id,
        "method": method,
        "score": score,
        "roles": facts,
        "node_title": node.title,
        "node_type": node.node_type,
        "intent": intent["name"] if intent else None,
        "llm_facts": llm_facts,
        "base_answer": base_answer,
        "mandatory_notes_text": mandatory_notes_text,
    }
