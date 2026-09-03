import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from modeling.graph import responsible_roles
from knowledge.search import resolve_query
from agent.authority import detect_intent, _INTENT_VOCAB
from agent.smalltalk import detect_smalltalk
from agent.glossary import (
    detect_glossary_query,
    format_glossary_answer,
    expand_acronym_in_role_name,
)

MIN_TEXT_SEARCH_SCORE = 0.15

# Real gap the professor flagged: a brand-new employee who doesn't
# know any DAM ids tends to type something short - a single word
# ("mission"), or just the verb with no subject ("approve") - and the
# old behavior silently picked resolve_query's top-scoring guess and
# answered as if it were certain. Measured directly: "mission" alone
# scores 0.48/0.45/0.41 across THREE different real tasks (2.121,
# 2.124, 2.125) - genuinely ambiguous, not a confident match that just
# happens to have a modest score. "approve" alone scores 0.46 against
# a single task (2.513.3) it has no real reason to specifically mean.
# Two independent, deterministic signals catch this - same "measure,
# don't guess" approach as CONTEXT_OVERRIDE_MAX_SCORE above:
#
# 1. Too few real content words: strip English stopwords (sklearn's
#    own list) and this app's own intent-verb vocabulary ("approve",
#    "informed", "check", ...) - a verb alone or a question with no
#    real subject left over is inherently under-specified, regardless
#    of what resolve_query happens to score it.
# 2. A close score gap to the runner-up: even a longer, well-formed
#    query can genuinely name something with 2+ plausible targets -
#    "mission" is the clean example (0.48 vs 0.45, a 6% gap).
#
# CLARIFICATION_MAX_SCORE (0.6) and CLARIFICATION_MIN_GAP (0.15) reuse
# the same measured cluster CONTEXT_OVERRIDE_MAX_SCORE was calibrated
# against: genuine, unambiguous matches in this corpus score 0.65-0.89
# with real separation from their runner-up (see docs/decisions.md).
CLARIFICATION_MAX_SCORE = 0.6
CLARIFICATION_MIN_GAP = 0.15

_EXTRA_GENERIC_WORDS = {"task", "activity", "process", "dam", "please", "tell"}
_GENERIC_QUERY_WORDS = ENGLISH_STOP_WORDS | _INTENT_VOCAB | _EXTRA_GENERIC_WORDS
_WORD_RE = re.compile(r"[a-z']+")


def _content_word_count(query):
    words = _WORD_RE.findall(query.lower())
    return sum(1 for w in words if len(w) >= 3 and w not in _GENERIC_QUERY_WORDS)


def _needs_clarification(query, matches):
    """
    True when resolve_query technically returned a top match, but
    there isn't enough real signal to trust it silently - either the
    query itself is too under-specified (too few real content words),
    or multiple candidates are close enough that picking just the top
    one would be a guess dressed up as an answer.
    """
    too_vague = _content_word_count(query) <= 1
    top_score = matches[0]["score"]

    if len(matches) < 2:
        return too_vague and top_score < CLARIFICATION_MAX_SCORE

    close_gap = (top_score - matches[1]["score"]) < CLARIFICATION_MIN_GAP
    return (too_vague and top_score < CLARIFICATION_MAX_SCORE) or (
        close_gap and top_score < 0.85
    )


def _format_clarification_answer(matches, nodes):
    suggestions = ", ".join(f"{m['id']} ({nodes[m['id']].title!r})" for m in matches[:3])
    return (
        "That's a bit broad for me to pin down to one task. Did you mean "
        f"one of these: {suggestions}? Or try describing the specific "
        'activity, e.g. "who approves the quarterly mission program".'
    )

# Real bug this fixes: a chat follow-up like "who are the informed
# parties for that activity?" names no real subject of its own, so
# resolve_query has zero legitimate signal about which node it means -
# it was landing on coincidentally-overlapping, unrelated nodes instead
# (2.118 "Communication with Co-Financiers of projects" vs the
# entirely different 3.226 "...and third parties" - the follow-up's
# stray word "parties" happened to overlap with 3.226's title, not
# 2.118's, at a comfortably "confident" 0.42).
#
# First attempt at this fix matched a fixed list of anaphoric phrases
# ("that activity", "it", etc.) - defeated immediately by a second,
# differently-worded live follow-up ("and who are the informed
# partie?") that resolved to the exact same wrong node at the exact
# same 0.42 score, with no pronoun and no phrase from the list at all.
# Measured directly (not guessed) instead: genuine, specific-subject
# matches in this corpus score 0.71-0.89 ("quarterly mission program"
# 0.888, "loan grant processing" 0.714); both real coincidental-
# overlap failures measured here score 0.39-0.42. CONTEXT_OVERRIDE_
# MAX_SCORE sits at the empirical gap between those two clusters -
# same "measure the real cases, don't guess the threshold" approach as
# knowledge/typo_correct.py's DEFAULT_MIN_RATIO. See docs/decisions.md,
# 2026-08-06, for the measurements and the full comparison table.
CONTEXT_OVERRIDE_MAX_SCORE = 0.5

_HAS_DIGIT = re.compile(r"\d")


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


def _check_verify_roles(roles):
    # C/C1/C2 (check, verify) only - deliberately excludes C3/C4
    # (consult), same action-code split agent/authority.py's "check"
    # vs "consult" intents already draw. See _format_mandatory_notes.
    return [r for r in roles if r["action"] in ("C", "C1", "C2")]


def _informed_roles(roles):
    return [r for r in roles if r["action"] == "( i )"]


def _format_mandatory_notes(roles, intent_name):
    """
    Domain rule from Adem (2026-09-03, see docs/decisions.md): when a
    task has a recorded Check/Verify (C/C1/C2) entity in the DAM, that
    step is mandatory - not optional context, a real part of the
    process - so it belongs on ANY narrow answer about that task ("who
    approves", "who initiates", ...), not only when someone happens to
    ask "who checks this." Same always-surface treatment extended to
    the informed-party (( i )) entity, for consistency (also Adem's
    explicit call, over the alternative of gating it behind some vaguer
    "when it feels needed" heuristic that couldn't be built reliably
    without either an LLM judgment call or an undertested guess).

    Skipped when the intent actually asked about IS that same action -
    "who checks 3.111" already answers with the check/verify roles as
    its main sentence; repeating them as a trailing note would be a
    redundant echo, not new information.
    """
    notes = []

    if intent_name != "check":
        check_roles = _check_verify_roles(roles)
        if check_roles:
            role_list = _format_role_list(check_roles)
            notes.append(
                "This task must also be checked/verified by " + ", ".join(role_list) + "."
            )

    if intent_name != "informed":
        informed_roles = _informed_roles(roles)
        if informed_roles:
            role_list = _format_role_list(informed_roles)
            notes.append(", ".join(role_list) + " must also be informed.")

    return " ".join(notes)


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
        base = (
            f"No one is recorded to {intent['name']} on {node.id} "
            f"({node.title!r}) in the DAM."
        )
    else:
        role_list = _format_role_list(matching)
        base = (
            f"For {node.id} ({node.title!r}), the following {intent['verb_phrase']}: "
            + ", ".join(role_list) + "."
        )

    notes = _format_mandatory_notes(roles, intent["name"])
    return f"{base} {notes}" if notes else base


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


def answer_question(query, nodes, graph, vectorizer, matrix, searchable_ids, previous_node_id=None):
    """
    Returns {"answer": str, "node_id": str|None, "method": str|None,
    "score": float|None, "roles": list|None, "node_title": str|None,
    "node_type": str|None, "intent": str|None}. "answer" is always the
    trusted, deterministic prose - the rest is the evidence behind it
    (which node was resolved, how, how confidently, and the exact raw
    facts "answer" was built from) so a caller can show that evidence
    directly, or hand "roles" to something else (e.g. an LLM phrasing
    layer) as verified ground truth instead of re-deriving it.

    `previous_node_id`: the node_id this same conversation last
    resolved to, if any (the caller - webapp/backend.py - gets this
    from the frontend, which tracks it per chat thread). Used only as
    a fallback anchor when a fresh resolution of `query` alone is weak
    or absent (see CONTEXT_OVERRIDE_MAX_SCORE above) - an explicit id
    in `query`, or a fresh text match that clears the bar on its own
    merits, always takes priority. resolve_query still runs first
    either way; this only decides which result to trust once both are
    known.
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

    context_available = (
        previous_node_id
        and previous_node_id in nodes
        and not _HAS_DIGIT.search(query)
    )

    resolution_is_weak = resolution["method"] == "text_search" and (
        not resolution["matches"] or resolution["matches"][0]["score"] < CONTEXT_OVERRIDE_MAX_SCORE
    )

    if context_available and resolution_is_weak:
        node_id = previous_node_id
        method = "context_carryover"
        score = None
    else:
        if resolution["method"] == "invalid_id":
            answer = _format_invalid_id_answer(resolution["invalid_id"], resolution["suggestions"])
            return _empty_result(answer, "invalid_id")

        if not resolution["matches"]:
            # Zero TF-IDF overlap with anything in the DAM has two very
            # different real causes, and they need different replies:
            # a query that's ONLY generic/intent words with no real
            # subject at all ("informed" alone) is still on-topic, just
            # under-specified - same fix as _needs_clarification above,
            # just reached via an empty match list instead of a weak
            # one. A query with real, substantive content words that
            # still shares nothing with the DAM's vocabulary
            # ("what's the weather today") is a much stronger, honest
            # signal that it's genuinely outside this app's scope -
            # said explicitly instead of the vaguer "couldn't find a
            # task", which reads like a search miss rather than "this
            # isn't what I'm for". Reuses _content_word_count rather
            # than a topic keyword list on purpose - a fixed list of
            # "off-topic subjects" is exactly the kind of brittle,
            # rephrasing-defeated heuristic that failed once already
            # this session (see the context-carryover entries in
            # docs/decisions.md).
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
        method = resolution["method"]
        score = top["score"]

    node = nodes[node_id]
    roles = responsible_roles(graph, node_id)

    intent = detect_intent(query)

    if intent:
        matching = _matching_roles(roles, intent)
        answer = _format_intent_answer(node, intent, roles, matching, nodes, graph)
        # facts drives both the deterministic "roles" shown to the user
        # and what agent/generate.py's grounding check requires an LLM
        # rephrasing to preserve verbatim - the mandatory Check/Verify
        # and informed-party notes above are real facts stated in
        # "answer" now, so they have to be in here too, or an LLM
        # phrasing pass could silently drop them without the grounding
        # check ever catching it (see docs/decisions.md, 2026-09-03).
        facts = list(matching)
        if intent["name"] != "check":
            facts.extend(_check_verify_roles(roles))
        if intent["name"] != "informed":
            facts.extend(_informed_roles(roles))
    else:
        answer = _format_full_answer(node, roles, nodes, graph)
        facts = roles

    return {
        "answer": answer,
        "node_id": node_id,
        "method": method,
        "score": score,
        "roles": facts,
        "node_title": node.title,
        "node_type": node.node_type,
        "intent": intent["name"] if intent else None,
    }
