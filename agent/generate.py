from llm.base import LLMUnavailableError
from llm.translate import LANGUAGE_NAMES

# Kept as its own constant, not inlined into SYSTEM_PROMPT below, so
# build_grounding_prompt can swap it out via an exact-string replace
# for _LONG_ANSWER_RULE when there are many facts to state (see there)
# without the two ever risking drifting out of sync with each other.
_SHORT_ANSWER_RULE = (
    "5. Answer in 1-3 sentences. No bullet points, no headers, no "
    "markdown, no emoji."
)

# Real tension found live (2026-09-03, see docs/decisions.md): the
# mandatory Check/Verify + informed-party notes feature (also
# 2026-09-03) routinely pushes a real answer's fact count to 4-6 roles
# (previously usually 1-2 - just the specific action asked about).
# Squeezing that many role names into 1-3 sentences while ALSO keeping
# every one of them verbatim intact (rule 4) is a genuinely hard
# constraint for a model to satisfy at once - the honest ways to
# resolve that pressure are to drop a role, paraphrase/shorten a name,
# or run longer than 3 sentences, and only the third one doesn't
# silently fail the grounding check below. This rule is swapped in
# specifically when the fact count is high, removing that pressure
# without touching rule 4's actual accuracy requirement at all.
_LONG_ANSWER_RULE = (
    "5. Use as many sentences as you need to naturally state every fact "
    "below - there are several this time. A longer, complete answer "
    "that keeps every fact intact is much better than a short one that "
    "drops or blends any of them. Still no bullet points, no headers, "
    "no markdown, no emoji."
)

# The fact-count threshold above which _LONG_ANSWER_RULE replaces
# _SHORT_ANSWER_RULE - 4 because 1-3 facts is exactly what the 1-3
# sentence cap was originally sized for (one fact per sentence, roughly
# - the common case before the mandatory-notes feature existed).
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


def build_grounding_prompt(question, structured_result, target_language="en"):
    node_id = structured_result.get("node_id")
    node_title = structured_result.get("node_title")
    roles = structured_result.get("roles") or []

    system = SYSTEM_PROMPT
    if len(roles) >= MANY_FACTS_THRESHOLD:
        system = system.replace(_SHORT_ANSWER_RULE, _LONG_ANSWER_RULE)

    if target_language != "en" and target_language in LANGUAGE_NAMES:
        # Appended as its own numbered rule rather than folded into the
        # rules above, so the "keep role names/footnote numbers intact"
        # rule (4) still reads naturally for the English-only case this
        # prompt was originally written for - added on 2026-08-06 for
        # multi-language support (see docs/decisions.md). Role names
        # are organizational job titles, not really "translatable" in
        # the first place, and rule 4 above already governs them - this
        # just makes explicit that the language switch doesn't relax it.
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
        f"Verified facts:\n{_facts_block(structured_result)}\n\n"
        f"Reference answer (already correct, restyle it - don't just "
        f"copy it verbatim): {structured_result['answer']}"
    )
    return system, user


def _normalize_for_match(s):
    # Collapses whitespace and lowercases before comparing - makes the
    # grounding check robust to trivial formatting noise a model might
    # introduce (extra/missing spaces, different casing) WITHOUT
    # weakening what it actually verifies: the exact same words, in the
    # exact same order, still have to be present. Added 2026-09-03 (see
    # docs/decisions.md) after finding this was rejecting some
    # otherwise-faithful rephrasings over nothing but incidental
    # whitespace/case differences.
    return " ".join(s.lower().split())


def _mentions_expected_facts(text, structured_result):
    """
    Grounding check, not just a hopeful prompt: every role name in the
    facts that back this answer must still be present, verbatim (modulo
    whitespace/case - see _normalize_for_match), in the LLM's
    rephrasing. Guards against the model quietly dropping, merging, or
    renaming a role while still sounding fluent - the exact failure
    mode that makes free-form LLM output risky for a compliance
    document, even under a strict system prompt.
    """
    roles = structured_result.get("roles")
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

    if not llm_text or not _mentions_expected_facts(llm_text, structured_result):
        return {
            "text": deterministic,
            "used_llm": False,
            "provider": provider.name,
            "error": "LLM output failed the grounding check (missing/altered role names)",
        }

    return {"text": llm_text, "used_llm": True, "provider": provider.name, "error": None}
