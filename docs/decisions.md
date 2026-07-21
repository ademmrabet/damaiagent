# Decisions Log

Running record of scope and design decisions for the v2 rebuild, dated,
so the reasoning is traceable for review (professor / jury) without
having to reconstruct it from chat history.

## 2026-07-21 - Source document

Switched source PDF from `dam_mvp_chapters.pdf` (66 pages, the original
MVP-scoped export) to `updated dam file.pdf` (79 pages). Reason: the
updated file includes the glossary, abbreviations, and authority-code
(levels, colors) legend that the MVP export didn't have, and those are
needed as reference data for the agent's `explain_authority` /
glossary-lookup capability. Old file kept in `OLD/` for reference only.

## 2026-07-21 - Scope: chapter 3 (NSO) included

The updated file contains a full chapter 3 - Non-Sovereign Operations
(client relations, identification, appraisal, trade finance, approval,
portfolio management, equity investment) - that wasn't part of the
original ~50-table MVP scope (chapters 1-2 only). Decision: chapter 3
is in scope for v2.

## 2026-07-21 - Two parsing bugs found and fixed (with tests)

1. **Title misattribution**: a task's title line that wraps to appear
   after its own actions row, immediately before the next task's bare
   identifier row, was being stolen by that next task (v1). Fixed in
   `parsing/task_blocks.py` - forward-attachment to the next identifier
   only happens when no task is currently open.
2. **Reference-text corruption**: "See DAM 16.100, 16.200..." cross-
   reference phrases were being digit-stripped into titles as noise
   instead of extracted. Fixed by centralizing reference-stripping into
   one function (`parsing/metadata.py: remove_references`) that every
   title/notes path calls, instead of two divergent implementations.

Both verified against real pages of the actual PDF, not synthetic
examples - see `tests/fixtures/known_cases.py` and `tests/test_task_blocks.py`.

## 2026-07-21 - Second real bug found via screenshot: 3.225/3.226

Confirmed against the actual table (page 48): 3.225 is a self-contained
"redirect" row ("Refer to Activities 2.114 - 2.117 in Section 2."),
period-terminated, and 3.226's title starts on the next physical line
before 3.226's own identifier appears. The v1-style fix (only forward-
attach when nothing is open) wasn't enough, since 3.225 was still
"open" by bookkeeping despite being finished. Fixed by treating a
trailing period on the open task's text as a "this is finished" signal
- see `parsing/task_blocks.py`. Also added a second reference pattern,
"Refer to Activities X - Y in Section Z" (a range, expanded to every
id in it), alongside the existing "See DAM ..." list pattern.

## 2026-07-21 - Authority code legend transcribed, "C" found to be overloaded

Full legend transcribed from the real page (`data/reference/authority_codes.json`,
validated against the `AuthorityCode` schema - 17/17 load cleanly).
Found: the letter "C" covers two unrelated concepts distinguished only
by level and color - C1/C2 (red) = "Check and Verify", C3/C4 (purple)
= "Consult" (Board/Governors or Independent Functions). Not a bug in
the schema (each full code like "C3" is stored separately with its own
meaning), but a trap for the agent's intent parser later: mapping the
word "check" or "consult" to the bare letter "C" would wrongly merge
two different authority concepts. Noted for the agent stage, not fixed
yet.

## 2026-07-21 - Task 2.126 resolved (screenshot corrected an earlier theory)

Originally diagnosed (from coordinates alone) as needing geometry: two
PDF lines ~0.15pt apart wrongly merged into one row. A real screenshot
of page 12 showed this was wrong - title+actions are genuinely one
row, textbook title-above-identifier, and it failed for the same
reason as 3.225/3.226: current_task (2.125) was still open with no
period to signal it was finished. Added a third signal to
`task_blocks.py`: a task is also treated as finished if an incoming
line carries action codes while the open task already has some of its
own - a second batch of actions is a strong sign it belongs to the
next task, not the current one. All 9 tests pass, 0 xfail. Full
79-page smoke test: 240 task/child blocks, 0 exceptions, 2 remaining
empty titles (2.516, 2.522, both on the new source's pages 49-50) -
logged for the node-validation stage, not chased now.
