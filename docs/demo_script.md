# Live Demo Script — DAM AI Agent

Every question below was run against the real, current build before being
included here — none of this is guessed. Node ids, scores, and answer text
are the actual output as of 2026-08-06. Numbers may shift slightly if the
underlying PDF or parsing changes, but the behavior each section
demonstrates will not.

## Before you start

- Set the LLM mode to **Auto** (top right of the chat page) so answers are
  phrased naturally by Groq, with the deterministic template answer as a
  visible fallback ("Show structured (template) answer" under any reply).
- If you're demoing the hosted version, open it a minute or two beforehand
  so it's already awake (see `docs/hosting.md` — free tiers sleep after
  inactivity).
- Each numbered section below is deliberately a fresh idea — you don't have
  to run every single line, but running them in order tells a coherent
  story: precise lookup → natural language → resilience → domain knowledge
  → conversation → honesty about limits.

## 1. Direct id lookup — precision

Ask:

> who approves 2.126

Expect: a direct answer for node 2.126 ("Quarterly Mission program"),
naming **RDG / Director RDNG** as approver, with the RDG acronym expanded
inline. This shows the agent isn't guessing — an id in the DAM resolves
with certainty (`method: id`, confidence 1.0).

Also worth pointing out, since it's right there in this same answer: the
reply doesn't stop at "who approves" — it also states that the task **must
also be checked/verified by** the Sector Manager and Supporting Dept.
Division Manager, and that the Concerned Sector VP, RDVP, and Task
Manager/Project Team **must also be informed**. This is a deliberate
domain rule (added 2026-09-03): a recorded Check/Verify step in the DAM is
mandatory, not optional context, so the agent surfaces it on *any* narrow
question about that task — not only when someone happens to ask "who
checks this." Good moment to say out loud: a new employee asking a narrow
question still gets told about the other real obligations on that task,
instead of only the one thing they thought to ask about.

## 2. Natural language — no id needed

Ask:

> who needs to be informed for quarterly mission program

Expect: the *same* node (2.126) resolved purely from the activity's name,
now listing the informed parties instead of approvers. This is the point
to make explicitly: the agent understands what you're describing, not just
codes you type in.

## 3. Typo tolerance

Ask:

> who aproves the qaurterly mision program

(Two deliberate typos: "aproves" and "qaurterly mision".) Expect: it still
resolves to 2.126 with the correct approver answer, identical to section 1.
Worth saying out loud: this correction is deterministic (a measured
similarity check against the DAM's own vocabulary), not an LLM guessing —
it works the same with or without an internet connection to Groq.

## 4. Domain glossary

Ask:

> what does DDG stand for

Expect: "DDG stands for: Deputy Director-General." Then, for a more
interesting case — an acronym that appears throughout the DAM's role names
but is *not* separately defined in its own Abbreviations pages:

> what does RDNG stand for

Expect: the agent still resolves it, and is transparent that this came
from a maintained alias rather than the DAM's own printed glossary — a
good moment to show the app is honest about its own sourcing, not just
its answers.

## 5. Conversation follow-up (no need to repeat yourself)

Ask:

> who approves of Communication with Co-Financiers of projects

Expect: resolves to node 2.118, naming the Country Manager / DDG as
approver. Then, **without naming the subject again**:

> and who are the informed parties?

Expect: it stays on 2.118 and answers the informed-parties question for
the *same* activity (labelled "carried over from previous question" in the
UI), instead of guessing at an unrelated, similarly-titled node. This is a
genuinely interesting one to narrate: the app tracks what you were just
talking about, the same way a person would.

## 6. Redirects — the DAM's own cross-references, followed automatically

Ask:

> who initiates 1.117.2

Expect: 1.117.2's own row has no responsibilities recorded — its real text
in the DAM is a pointer ("See 2.120: Organization of mission"). The agent
follows that redirect automatically and surfaces 2.120's actual
responsibilities instead of dead-ending. Good to explicitly point out: this
mirrors how a human reading the paper DAM would have to flip to another
page — the agent does that for you.

## 7. Honest refusal — the important "failure"

This is exactly the kind of question your professor tried, and it's meant
to fail this way:

> what happens with 9.999.999

Expect: "'9.999.999' doesn't exist in the DAM... Double-check the id, or
describe the activity in words instead." No fabricated answer, no
guessing. Worth stating directly in the demo: **this refusal is the
feature, not a bug** — the whole design principle behind this project is
that every real answer is traceable to an actual row in the DAM, so an
answer for something that isn't in the document would be worse than no
answer at all.

## 8. Personality / smalltalk

Ask "hi", then later "thanks" — these get warm, varied replies (not the
DAM lookup pipeline at all), so the agent doesn't feel like a bare search
box for the parts of a conversation that are just conversation.

## Also worth showing: the dashboard

Not chat-related, but pairs well with this script — go to `/dashboard` and:

- Use the **Chapter** filter to re-scope every card and chart to a single
  chapter of the DAM, then clear it back to "All chapters."
- Click a bar on the **action code distribution** chart (e.g. "A") — the
  roles chart above it filters to just that action's top performers,
  showing who does the most approving vs. who's informed most often.
- Point out the two coverage KPIs (avg. responsibilities per node, % of
  nodes with no direct responsibilities) — these are real, previously
  invisible data-quality signals about the DAM extraction itself, not
  cosmetic numbers.
