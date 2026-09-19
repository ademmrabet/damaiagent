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
    + _SHORT_ANSWER_RULE
)


def _scoped_facts(structured_result, target_language):
    """
    The role list the LLM actually has to preserve verbatim - not
    always the same as the full `roles`/`answer` used for the
    deterministic display text. English answers use `llm_facts` when
    present (just the roles the question's intent matched, e.g. the
    approvers for "who approves X") rather than the wider `roles` list
    that also folds in the mandatory Check/Verify + informed-party
    notes (see agent/qa.py's answer_question). Those notes are a fixed
    boilerplate sentence, not something that needs a creative
    rephrase, and asking the LLM to also reproduce every name in them
    verbatim was the single biggest driver of grounding-check
    fallbacks once a task had several informed parties (see docs/
    decisions.md, 2026-09-19) - `humanize_answer` re-attaches that
    sentence afterward untouched instead.

    Non-English answers deliberately keep the old, wider behavior:
    `mandatory_notes_text` is a fixed English template with no
    per-language translation yet (see llm/tone.py's EMPATHY_PREFIXES
    for the pattern this would follow if that's ever added), so
    splitting it out today would tack an untranslated English sentence
    onto an otherwise-translated answer - worse than the status quo.
    Also falls back to `roles` for hand-built structured_result
    fixtures (tests/test_generate.py) that predate `llm_facts`.
    """
    if target_language == "en" and structured_result.get("llm_facts") is not None:
        return structured_result["llm_facts"]
    return structured_result.get("roles") or []


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


def build_grounding_prompt(question, structured_result, target_language="en"):
    node_id = structured_result.get("node_id")
    node_title = structured_result.get("node_title")
    roles = _scoped_facts(structured_result, target_language)
    reference_answer = structured_result.get("base_answer") or structured_result["answer"]

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


def _normalize_for_match(s):
    """
    Lowercases and collapses whitespace runs (2026-09-03), then also
    normalizes spacing immediately around "/" (2026-09-19) - one real
    role name in this DAM's own extracted data ("Task Manager/ Task
    Team Members") has no space before its slash, a raw-PDF-extraction
    artifact, not a meaningful fact. An LLM naturally "cleaning up"
    that spacing while writing fluent prose was a real, avoidable
    grounding-check false rejection - same category of incidental-
    formatting-noise problem this function already existed to solve,
    just a punctuation case the original whitespace-only version
    didn't cover. Comparing both sides through this same function (see
    _mentions_expected_facts) makes it symmetric regardless of which
    side - the stored role name or the LLM's rephrasing - has the
    inconsistent spacing.
    """
    collapsed = " ".join(s.lower().split())
    return re.sub(r"\s*/\s*", "/", collapsed)


def _mentions_expected_facts(text, structured_result, target_language="en"):
    """
    Grounding check, not just a hopeful prompt: every role name the LLM
    was actually asked to preserve (see _scoped_facts) must still be
    present, verbatim modulo whitespace/case/slash-spacing - see
    _normalize_for_match - in its rephrasing. Guards against the model
    quietly dropping, merging, or renaming a role while still sounding
    fluent - the exact failure mode that makes free-form LLM output
    risky for a compliance document, even under a strict system
    prompt. Checked against the same scoped list `_facts_block` showed
    the model, not the wider `roles` - the mandatory-notes roles this
    excludes on English answers are re-attached verbatim by
    humanize_answer afterward, never at the LLM's mercy in the first
    place.
    """
    roles = _scoped_facts(structured_result, target_language)
    if not roles:
        return True
    normalized_text = _normalize_for_match(text)
    return all(_normalize_for_match(r["role"]) in normalized_text for r in roles)


def humanize_answer(question, structured_result, provider, target_language="en"):
    """
    Returns {"text": str, "used_llm": bool, "provider": str|None,
    "error": str|None}. "text" is always safe to show the user - falls
    back to the deterministic templated answer (structured_result
    ["answer"], already validated against real DAM screenshots) any
    time the LLM is unavailable, errors, or fails the grounding check.
    The deterministic path is never bypassed, only optionally
    re-phrased on top of.

    `target_language`: an "en"/"fr"/"es"/"pt"/"ar" code (see
    llm/translate.py) - the caller (webapp/backend.py) detects this
    from the user's own question. The grounding check below
    (_mentions_expected_facts) runs unchanged regardless of language -
    it's still checking for the literal English role-name strings,
    which the prompt explicitly instructs the model to preserve
    untranslated even inside a non-English sentence (see rule 6 added
    in build_grounding_prompt), so it stays meaningful rather than
    becoming a no-op once the surrounding sentence is in French/
    Spanish/Portuguese/Arabic.
    """
    deterministic = structured_result["answer"]

    if (
        provider is None
        or structured_result.get("node_id") is None
        or not structured_result.get("roles")
    ):
        return {"text": deterministic, "used_llm": False, "provider": None, "error": None}

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

    if not llm_text or not _mentions_expected_facts(llm_text, structured_result, target_language):
        return {
            "text": deterministic,
            "used_llm": False,
            "provider": provider.name,
            "error": "LLM output failed the grounding check (missing/altered role names)",
        }

    notes = structured_result.get("mandatory_notes_text")
    final_text = f"{llm_text} {notes}" if target_language == "en" and notes else llm_text

    return {"text": final_text, "used_llm": True, "provider": provider.name, "error": None}
