import re

from agent.authority import action_label
from llm.base import LLMUnavailableError
from llm.translate import LANGUAGE_NAMES

_SHORT_ANSWER_RULE = (
    "5. Answer in 1-3 sentences. No bullet points, no headers, no "
    "markdown, no emoji."
)

_LONG_ANSWER_RULE = (
    "5. Use as many sentences as you need to naturally state every fact "
    "below - there are several this time. A longer, complete answer "
    "that keeps every fact intact is much better than a short one that "
    "drops or blends any of them. Still no bullet points, no headers, "
    "no markdown, no emoji."
)

MANY_FACTS_THRESHOLD = 4

SYSTEM_PROMPT = (
    "You are the DAM Agent, a warm and confident assistant for the "
    "African Development Bank's Delegation of Authority Matrix (DAM). "
    "You will be given a question and a list of VERIFIED FACTS retrieved "
    "from the DAM's own knowledge graph. Your only job is to restate "
    "those facts as one short, natural, conversational answer - write "
    "like a knowledgeable, personable colleague giving someone a "
    "straight answer, not like a database dump. Contractions are fine. "
    'A brief, natural lead-in is fine ("Looks like...", "For that '
    'one,...") as long as every fact below still comes through intact.\n\n'
    "Rules, no exceptions:\n"
    "1. Use ONLY the facts given below. Never add a role, action, level, "
    "or footnote number that is not listed.\n"
    "2. Never use outside knowledge about the African Development Bank or "
    "any other organization.\n"
    "3. If the fact list is empty, say plainly that nothing is recorded - "
    "do not guess or soften that into a maybe.\n"
    "4. Keep every role name and footnote number from the facts intact "
    "and exactly spelled - you may reorder or reword the sentence around "
    "them, not the names or numbers themselves. Warmth is in the "
    "delivery, never in softening or hedging a fact.\n" + _SHORT_ANSWER_RULE
)


# the roles the llm must keep word for word in its answer
def _scoped_facts(structured_result, target_language):
    if target_language == "en" and structured_result.get("llm_facts") is not None:
        return structured_result["llm_facts"]
    return structured_result.get("roles") or []


# turn the roles into a plain facts list for the llm prompt
def _facts_block(roles):
    if not roles:
        return "(no responsibilities recorded for this item)"

    lines = []
    for r in roles:
        bits = [r["role"], f"action={action_label(r['action'])} ({r['action']})"]
        if r.get("level") is not None:
            bits.append(f"level={r['level']}")
        if r.get("footnote_refs"):
            bits.append("footnote " + ",".join(str(n) for n in r["footnote_refs"]))
        lines.append("- " + ", ".join(bits))
    return "\n".join(lines)


# build the system + user prompt that limits the llm to the given facts
def build_grounding_prompt(question, structured_result, target_language="en"):
    node_id = structured_result.get("node_id")
    node_title = structured_result.get("node_title")
    roles = _scoped_facts(structured_result, target_language)
    reference_answer = (
        structured_result.get("base_answer") or structured_result["answer"]
    )

    system = SYSTEM_PROMPT
    if len(roles) >= MANY_FACTS_THRESHOLD:
        system = system.replace(_SHORT_ANSWER_RULE, _LONG_ANSWER_RULE)

    if target_language != "en" and target_language in LANGUAGE_NAMES:
        language_name = LANGUAGE_NAMES[target_language]
        system += (
            f"\n\n6. Write your entire answer in {language_name} - the "
            f"user asked in {language_name}. The one exception: never "
            "translate role names, footnote numbers, or DAM ids from "
            "the facts list - copy those exactly as given, even inside "
            f"an otherwise-{language_name} sentence."
        )

    user = (
        f'User question: "{question}"\n\n'
        f"Matched DAM item: {node_id} ({node_title!r})\n\n"
        f"Verified facts:\n{_facts_block(roles)}\n\n"
        f"Reference answer (already correct, restyle it - don't just "
        f"copy it verbatim): {reference_answer}"
    )
    return system, user


# lowercase and fix spacing so role names compare reliably
def _normalize_for_match(s):
    collapsed = " ".join(s.lower().split())
    return re.sub(r"\s*/\s*", "/", collapsed)


# grounding check: is every expected role present in the llm answer
def _mentions_expected_facts(text, structured_result, target_language="en"):
    roles = _scoped_facts(structured_result, target_language)
    if not roles:
        return True
    normalized_text = _normalize_for_match(text)
    return all(_normalize_for_match(r["role"]) in normalized_text for r in roles)


# let the llm rephrase the answer, fall back to the template if it drifts
def humanize_answer(question, structured_result, provider, target_language="en"):
    deterministic = structured_result["answer"]

    if (
        provider is None
        or structured_result.get("node_id") is None
        or not structured_result.get("roles")
    ):
        return {
            "text": deterministic,
            "used_llm": False,
            "provider": None,
            "error": None,
        }

    system, user = build_grounding_prompt(question, structured_result, target_language)

    try:
        llm_text = provider.chat(system, user).strip()
    except LLMUnavailableError as exc:
        return {
            "text": deterministic,
            "used_llm": False,
            "provider": provider.name,
            "error": str(exc),
        }

    if not llm_text or not _mentions_expected_facts(
        llm_text, structured_result, target_language
    ):
        return {
            "text": deterministic,
            "used_llm": False,
            "provider": provider.name,
            "error": "LLM output failed the grounding check (missing/altered role names)",
        }

    notes = structured_result.get("mandatory_notes_text")
    final_text = (
        f"{llm_text} {notes}" if target_language == "en" and notes else llm_text
    )

    return {
        "text": final_text,
        "used_llm": True,
        "provider": provider.name,
        "error": None,
    }
