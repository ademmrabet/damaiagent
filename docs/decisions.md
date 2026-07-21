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

## 2026-07-21 - New hierarchy level found: threshold_variant

Screenshot of page 36 (2.513.3) showed a child_task can have its OWN
children, letter-labeled by amount threshold rather than numbered
(e.g. 2.513.3 -> (a) Up to UA 2,000,000 / (b) Over UA 2M up to UA 10M
/ (c) Over UA 10M). Confirmed recurring, not a one-off: 53 lettered
sub-item lines found document-wide (51 real, 2 false positives from
letter-lists inside footnote prose, already safely excluded by the
existing Notes-on boundary). Decided with Adem: id = dot-joined
("2.513.3.a"), node_type = new value "threshold_variant" (schema.py),
distinct from child_task since it represents a condition/amount band
of one activity rather than a separate activity. `task_blocks.py` now
reconstructs the id from whichever child_task opened most recently,
since the PDF only ever prints the bare "(a)". Also found and fixed a
related bug while testing this: NOTE_PATTERN's footnote-digit stripper
was corrupting titles containing comma-formatted amounts ("2,000,000"
-> ",,,") - fixed for comma-adjacent digits. Plain space-separated
amounts ("2 million") are NOT fixed by this and still get corrupted -
left as a documented xfail, genuinely needs superscript/geometry
detection (v1's original approach), not another text-pattern patch.
Full 79-page re-run: 291 blocks (138 task, 102 child_task, 51
threshold_variant), 0 errors, same 2 pre-existing empty titles.

## 2026-07-21 - Confirmed (not assumed): fused level+footnote digits need real geometry

Screenshot of page 29 (2.223.2/2.223.3) showed cells like "C13" -
level digit and footnote digit both superscript, no separator.
Checked at the character level: both digits are genuinely size 6 vs
the letter's size 9 (confirms superscript), BUT pdfplumber's own
extract_words() is inconsistent about grouping them - the identical
visual pattern comes out as one fused word "C13" in one cell and as
two separate words "C" + "13" in the next cell on the same row. Text-
pattern logic gives different, disagreeing answers depending on which
way pdfplumber happened to tokenize it (fused: level=1/footnote=3;
split: level=none/footnote=13) - not a regex problem, a tokenization
problem underneath the regex. Real fix needs raw character x-position
und size, not extract_words(). Confirms the remaining geometry backlog
(role attribution, informed-role gap, fused footnote digits) is
correctly scoped as geometry work, not more text heuristics.

CORRECTED below - the "base" isn't the cell center, it's the letter's
own top/bottom (Adem's original v1 idea, refined).

## 2026-07-21 - Level vs. footnote geometry rule, validated with real coordinates

Compared two real cases character-by-character:
- 2.224.4 "A1" with footnote 21: level digit "1" is BOTTOM-aligned
  with the letter (bottom 440.12 vs letter's 440.28); footnote digits
  "2","1" are TOP-aligned with the letter (top 430.64 vs letter's
  431.28) and share identical height with each other.
- 2.223.2/2.223.3 "C13"/"C14": both trailing digits in every instance
  share identical top AND bottom with each other, matching the
  FOOTNOTE alignment, not the level alignment. Corrected an earlier
  wrong guess (level=1/footnote=3) - there's no level digit in these
  cells at all, it's bare "C" + two-digit footnote "13"/"14".

Rule: compare each small (size 6) character after the action letter
to the LETTER's own top/bottom (not a cell-center estimate). Bottom-
aligned = the level digit (at most one). Top-aligned = a footnote
digit; consecutive top-aligned digits at the same height concatenate
into one multi-digit footnote number. This is the basis for the
geometry-based action/footnote extractor, next to build.

## 2026-07-21 - Geometry action/footnote extractor built (parsing/action_geometry.py) - partially validated

Built on the confirmed level/footnote alignment rule above. Anchor
detection went through 3 rounds against real false positives, all
found on one title (2.223.2, "Project Appraisal Report..."): raw
character scans caught OCR-spaced letters ("A" from "A p p r a is a
l"); requiring the whole word to match ^[ICRA]\d*$ fixed embedded
letters ("PAR)") but not isolated single-letter spaced words; final
version also checks word adjacency to catch that case.

Cross-checked geometry's per-task action count against the already-
trusted text-based count (extract_actions) across all 79 pages: 228
tasks with actions, 197 match, 31 don't (~14%), with mismatches
ranging from off-by-one to wildly off (2.412.1: text=3/geo=0; 3.642:
text=1/geo=9). Spread suggests more than one remaining cause, not a
single last bug. NOT wired into node-building yet - status is "core
alignment rule proven correct, anchor detection still has real,
uncatalogued gaps." Needs either more real examples to diagnose
against, or a conscious decision to ship with text-based counts as the
trusted source and geometry as best-effort supplementary detail only.
