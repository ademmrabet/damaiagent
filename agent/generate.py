from llm.base import LLMUnavailableError

SYSTEM_PROMPT = (
    "You are the DAM Agent, a warm and confident assistant for the "
    "African Development Bank's Delegation of Authority Matrix (DAM). "
    "You will be given a question and a list of VERIFIED FACTS retrieved "
    "from the DAM's own knowledge graph. Your only job is to restate "
    "those facts as one short, natural, conversational answer - write "
    "like a knowledgeable, personable colleague giving someone a "
    "straight answer, not like a database dump. Contractions are fine. "
    "A brief, natural lead-in is fine (\"Looks like...\", \"For that "
    "one,...\") as long as every fact below still comes through intact.\n\n"
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
    "delivery, never in softening or hedging a fact.\n"
    "5. Answer in 1-3 sentences. No bullet points, no headers, no "
    "markdown, no emoji."
)


def _facts_block(structured_result):
    roles = structured_result.get("roles")
    if not roles:
        return "(no responsibilities recorded for this item)"

    lines = []
    for r in roles:
        bits = [r["role"], f"action={r['action']}"]
        if r.get("level") is not None:
            bits.append(f"level={r['level']}")
        if r.get("footnote_refs"):
            bits.append("footnote " + ",".join(str(n) for n in r["footnote_refs"]))
        lines.append("- " + ", ".join(bits))
    return "\n".join(lines)


def build_grounding_prompt(question, structured_result):
    node_id = structured_result.get("node_id")
    node_title = structured_result.get("node_title")

    user = (
        f'User question: "{question}"\n\n'
        f"Matched DAM item: {node_id} ({node_title!r})\n\n"
        f"Verified facts:\n{_facts_block(structured_result)}\n\n"
        f"Reference answer (already correct, restyle it - don't just "
        f"copy it verbatim): {structured_result['answer']}"
    )
    return SYSTEM_PROMPT, user


def _mentions_expected_facts(text, structured_result):
    """
    Grounding check, not just a hopeful prompt: every role name in the
    facts that back this answer must still be present, verbatim, in
    the LLM's rephrasing. Guards against the model quietly dropping,
    merging, or renaming a role while still sounding fluent - the
    exact failure mode that makes free-form LLM output risky for a
    compliance document, even under a strict system prompt.
    """
    roles = structured_result.get("roles")
    if not roles:
        return True
    return all(r["role"] in text for r in roles)


def humanize_answer(question, structured_result, provider):
    """
    Returns {"text": str, "used_llm": bool, "provider": str|None,
    "error": str|None}. "text" is always safe to show the user - falls
    back to the deterministic templated answer (structured_result
    ["answer"], already validated against real DAM screenshots) any
    time the LLM is unavailable, errors, or fails the grounding check.
    The deterministic path is never bypassed, only optionally
    re-phrased on top of.
    """
    deterministic = structured_result["answer"]

    if (
        provider is None
        or structured_result.get("node_id") is None
        or not structured_result.get("roles")
    ):
        return {"text": deterministic, "used_llm": False, "provider": None, "error": None}

    system, user = build_grounding_prompt(question, structured_result)

    try:
        llm_text = provider.chat(system, user).strip()
    except LLMUnavailableError as exc:
        return {
            "text": deterministic,
            "used_llm": False,
            "provider": provider.name,
            "error": str(exc),
        }

    if not llm_text or not _mentions_expected_facts(llm_text, structured_result):
        return {
            "text": deterministic,
            "used_llm": False,
            "provider": provider.name,
            "error": "LLM output failed the grounding check (missing/altered role names)",
        }

    return {"text": llm_text, "used_llm": True, "provider": provider.name, "error": None}
