# Code Notes

Every inline comment that used to live in the source, pulled out here
so the code itself reads clean for review while the reasoning stays
recorded. Organized by file, in source order. Function/module
docstrings were left in place in the code (not duplicated here) -
these are the `#` comments only: local rationale, caveats, and
pointers that don't belong in a docstring.

## `agent/generate.py`

**in `humanize_answer`, on the early-return for no-node-id / no-provider / no-roles**

Nothing resolved (no-match / low-confidence case), or a resolved node
with no facts to phrase (a "no responsibilities here, see X instead"
pointer answer) - don't hand an LLM a mostly-empty prompt and risk it
inventing something plausible-sounding instead. The no-roles case
matters specifically because `_mentions_expected_facts`'s grounding
check is vacuously true over an empty facts list - without this extra
skip, a pointer answer's empty `roles` would let the LLM rephrase a
navigational answer with no real check on it at all.

## `webapp/static/index.html`

**style block, top of `<style>`**

Palette: white background, #228b22 (forest green) as the primary
color, #c80815 (red) used sparingly as an accent - specifically
tied to LOW-CONFIDENCE or no-match answers, not decoration, so
the color itself carries meaning consistent with how the agent
already reports its own confidence (see agent/qa.py's
"method"/"score" fields).


## `agent/authority.py`


**lines 1-16**

Maps how a person actually phrases a question ("who signs off on
X", "who checks X", "who must be informed about X") to the DAM's
own authority codes (data/reference/authority_codes.json) - built
to read FROM that file's code/level structure, not a hand-written
vocabulary that could quietly drift out of sync with it the way
authority_rules.py and authority_codes.json drifted apart in v1
(see docs/decisions.md).

The "C" trap, already resolved in the reference data itself - see
authority_codes.json's own note on the bare "C" entry: bare "C" (no
digit, meaning the geometry extractor couldn't resolve a level)
defaults to "Check and Verify", NOT "Consult". C1/C2 = Check and
Verify, C3/C4 = Consult - two unrelated concepts sharing one letter.
A question about "consult" must only ever match C3/C4, never a bare
"C" or C1/C2 - encoded directly in each intent's `matches` predicate
below, not left to chance.


**lines 59-61**

Checked BEFORE "check" below - "consult" never matches the
"check" keyword list, but check the more specific/narrower
intent first regardless, in case that ever changes.


## `agent/qa.py`


**lines 1-12**

The actual question-answering logic - ties together everything
built in the earlier stages (knowledge/search.py to find the right
node, modeling/graph.py to look up who's responsible, agent/
authority.py to figure out which authority action was actually
asked about) into one function a UI can call with a plain-text
question and get a plain-text answer back.

Deliberately UI-agnostic: this module doesn't know or care whether
it's called from a CLI, a test, or the Day 8 web backend - it just
takes a string and returns a structured dict (answer text + the
evidence behind it), so the web layer only has to wrap this, not
reimplement any of the actual logic.


**lines 18-25**

How confident a text-search match needs to be before answering with
it rather than saying "I'm not sure". Not rigorously calibrated
against a labeled query set (there isn't one) - a soft, honest
heuristic, not a validated threshold. Real unrelated queries scored
a genuine 0.0 in testing (filtered out before this even applies);
this mainly guards against a technically-nonzero but very weak
single-word coincidental overlap being answered as if it were a
confident match.


**lines 30-34 (def _format_role_list(roles))**

One role can show up more than once in the raw responsibilities
list (e.g. two informed markers, occasionally to the same role -
see docs/decisions.md, page 43's residual duplicates) - de-dupe
by name for the sentence, but keep footnote numbers from every
instance.


**lines 52-58 (def _format_children_pointer(node, nodes))**

Real gap found testing this: a query matching a process/chapter
(e.g. "organization of nso missions" -> process 3.110) has no
responsibilities of its own - build_nodes.py only extracts those
for task/child_task/threshold_variant - so answering with just
"no recorded responsibilities" is technically true but a dead
end. Point to its children instead, since that's almost always
actually useful here.


**lines 102-103 (def _format_full_answer(node, roles, nodes))**

group by action for a readable summary, in the DAM's own
I -> C -> R -> A -> ( i ) reading order rather than alphabetical


## `knowledge/search.py`


**lines 1-26**

Turns a free-text question into one or more node ids in the graph -
the missing link between "what the user typed" and "which node do I
look up." Two paths, tried in order:

1. ID fast-path: if the question already contains a literal DAM
id ("2.513.3", "2.513.3.a"), just look it up directly. 100%
accurate, no ambiguity, no model involved - most of this
project's own example questions ("who approves task X") are
phrased with an explicit id, so this covers a lot of real
traffic for free.
2. TF-IDF text search (fallback): for questions phrased by title
instead of id ("who approves quarterly mission program"),
vectorize every task/child_task/threshold_variant title with
scikit-learn's TfidfVectorizer and rank by cosine similarity to
the query.

Chose TF-IDF over pretrained sentence embeddings for this stage -
see docs/decisions.md for the full reasoning (training a real
embedding model was ruled out outright: 327 short titles is nowhere
near enough data; pretrained embeddings would handle paraphrasing
better but need a heavy PyTorch dependency that didn't reliably
install even in the dev sandbox). TF-IDF is lexical, not semantic -
it matches shared WORDS, not meaning - worth remembering when a
query uses different words than the title does (see the honest
"method" label returned by resolve_query below, so callers - and
the report - never overstate what this is actually doing).


**lines 34-37**

Unlike parsing.hierarchy.ID_PATTERN (anchored to the START of a
line, because it's parsing PDF rows where the id IS the whole line's
lead token), this has to find an id ANYWHERE inside a free-text
question - "who approves 2.513.3?" has real words before the id.


**lines 40-48**

Real gap found testing this against "organization of nso missions":
that phrase is a real, meaningful PROCESS title ("3.110 ORGANIZATION
OF NSO MISSIONS"), but processes were originally excluded from the
searchable corpus - the query matched nothing relevant instead.
Processes have no responsibilities of their own (build_nodes.py only
extracts those for task/child_task/threshold_variant), but they're
still real, meaningful content someone might search by name for -
what the agent DOES with a process-type match (e.g. "these are the
process's tasks: ...") is Day 7's concern, not this module's.


## `modeling/build_nodes.py`


**lines 1-19**

Pass 2 (and final assembly): walks every page once, builds task
blocks, and enriches each one into a real schema.Node - title,
references, and responsibilities (role + action + level +
footnote_refs), then merges that with the Pass-1 skeleton
(hierarchy_skeleton.py) to produce the full node set: chapter and
process nodes (which task_blocks.py never emits), threshold_variant
nodes (which task_blocks.py DOES emit, but Pass 1 doesn't know
about), and task/child_task nodes with correct children on all of
them - computed once, at the end, over the COMPLETE id set, not
twice from two partial ones.

Why one page-walk instead of reusing hierarchy_skeleton's separate
scan: enrichment needs `chars`/`words` (for geometry) alongside the
same page's `lines` (for task_blocks and process-title lines), and
re-opening/re-walking every page a second time to get that would
just be slower for no accuracy benefit. hierarchy_skeleton.py is
still used for its skeleton-building logic (get_node_type,
get_children, etc.) - just fed a merged id set here instead of
calling its own scan.


**line 104 (def build_nodes(pdf_path))** - on `enriched = {}`

id -> dict of Node fields, from block-walking


**line 105 (def build_nodes(pdf_path))** - on `process_titles = {}`

id -> title, from raw process boundary lines


**line 106 (def build_nodes(pdf_path))** - on `all_task_child_ids = set()`

from task_blocks (task/child_task/threshold_variant)


**line 107 (def build_nodes(pdf_path))** - on `last_headers = []`

carry-forward for continuation pages (page 45 gap)


**lines 115-116 (def build_nodes(pdf_path))**

process/chapter titles: read straight off the line, since
task_blocks.py never keeps these rows.


**line 125 (def build_nodes(pdf_path))** - on `page_headers = last_headers`

carry-forward fix for page 45's gap


**lines 133-135 (def build_nodes(pdf_path))**

shouldn't happen - build_task_blocks only opens a
block from an identifier-led line - but fail safe
rather than crash the whole 79-page run on one bad row.


**lines 143-150 (def build_nodes(pdf_path))**

Corruption recovery: if the word-based title looks
word-boundary-corrupted (pdfplumber's own word
extraction merged two close-together lines' characters -
see _reconstruct_clean_block_text), re-derive the title
from raw characters for this block's span instead. Only
done when triggered, not for every block - the normal
word-based path is faster and already correct for the
~320 other titles.


**lines 189-194 (def build_nodes(pdf_path))**

--- merge id sets ---
process ids come from process_titles (task_blocks never emits
them at all); task/child_task/threshold_variant ids come from
all_task_child_ids (block-walking, includes threshold_variant -
which Pass 1's plain-text scan structurally cannot find, since
the PDF never prints the full "2.513.3.a", only a bare "(a)").


**lines 200-205 (def build_nodes(pdf_path))**

chapter nodes - synthesized, never printed as their own line
with a parseable identifier (bare "1"/"2"/"3" has no dot, so
get_identifier() never matches it). Title left blank: chasing
chapter cover-page titles wasn't worth the time against the
9-day budget - flagged in docs/decisions.md, not silently
skipped.


**line 215 (def build_nodes(pdf_path))**

process nodes - real titles, but never a task_blocks entry


**line 225 (def build_nodes(pdf_path))**

task / child_task / threshold_variant nodes - from block-walking


## `modeling/graph.py`


**lines 1-43**

Turns the 327 Node objects (modeling/build_nodes.py) into an actual
graph - the "knowledge graph" this whole project is meant to be
built around, not just a fancier word for the dict we already had.

Why a real graph library (networkx) instead of just querying the
dict of Nodes directly: the two founding example questions for this
project - "who approves task X" and "who needs to be informed for
task X" - are really the same shape of question (look at who's
connected to X by a particular kind of edge), and a role like
"Country Manager / DDG" is itself a real, recurring entity that
shows up across dozens of tasks - worth being a first-class node
with its own identity, not just a string repeated inside 168
different Responsibility lists. networkx gives traversal, neighbor
lookups, and (later) visualization/export for free once the data is
shaped this way.

Graph schema:
NODES:
- every schema.Node (chapter/process/task/child_task/
threshold_variant), keyed by its own id ("2.513.3")
- one node per canonical role string ("Country Manager / DDG"),
keyed by "role::<name>" - prefixed so a role name can never
collide with a real DAM id
- one shared "role::__unresolved__" node for the small number
of responsibilities whose role never resolved to a header
(0.5% of 1772, as of the last full rebuild) - kept visible
and queryable rather than silently dropped, since a query for
"everyone responsible for task X" should still surface that
something couldn't be attributed, not just quietly omit it.
EDGES (a MultiDiGraph, not DiGraph - a role can have two separate
responsibilities on the same task, e.g. checks AND later
approves, which is two parallel edges between the same pair of
nodes, not one edge with two labels):
- "contains": parent -> child, one per entry in Node.children
(chapter->process->task->child_task->threshold_variant,
already the correct DIRECT-child-only relationship - see
parsing/hierarchy.py get_children() and its 2026-07-28 fix)
- "references": task -> referenced task, one per entry in
Node.references, ONLY wired if the target id actually exists
in the node set (schema.py's own documented caution - a
reference might point outside scope)
- "responsible_for": role -> task, one per Responsibility, with
action/level/footnote_refs as edge attributes


**line 66 (def build_graph(nodes))**

--- DAM nodes ---


**lines 80-82 (def build_graph(nodes))**

--- role nodes (only ones actually used, discovered while
walking responsibilities below - no point pre-declaring every
role if none of them turn out to be referenced) ---


**line 90 (def _ensure_role_node(role_id, label))**

--- edges ---


## `modeling/hierarchy_skeleton.py`


**lines 1-18**

Pass 1 of node building: scan every line on every page for anything
that looks like a DAM identifier, and build the hierarchy shape
(chapter/process/task/child_task, parent/children) from the
numbering scheme alone - before any title/action/geometry work.

Why a separate pass: task_blocks.py deliberately DISCARDS process
boundary rows (e.g. "2.510 LOAN / GRANT DISBURSEMENT PROCESSING")
without emitting a block - it only cares about task/child_task
content. That's correct for block-building, but it means process
ids are never captured anywhere else unless something else scans
for them directly. This does that scan, and only that scan - no
titles, no actions, no geometry, just "what identifiers exist and
how do they nest."

threshold_variant ids (e.g. "2.513.3.a") are NOT found here - they
never appear as their own text line, only as a bare "(a)" that
task_blocks.py reconstructs during enrichment (pass 2). They're
merged into the skeleton afterward, in build_nodes.py.


## `parsing/action_geometry.py`


**lines 1-25**

Splits each action code into (letter, level, footnote_refs) using
character geometry, not text patterns - see docs/decisions.md for
the validated rule and the real coordinates it's based on.

Rule (confirmed against real coordinates - 2.224.4's "A1" + footnote
21, and 2.223.2/2.223.3's "C13"/"C14"):
- the action letter is a "big" character (size >= BODY_SIZE_MIN)
- a small (size < BODY_SIZE_MIN) character whose BOTTOM lines up
with the letter's bottom is the level digit (at most one)
- small characters whose TOP lines up with the letter's top are
footnote digits; consecutive same-height ones concatenate into
one multi-digit footnote number

Anchor design, revised twice against real false positives on
2.223.2 (title: "Project Appraisal Report (PAR) for a non-
exceptional operation"):
1st attempt: scan raw characters for big I/C/R/A. False-positived
on "A"/"R" from OCR-spaced title letters ("A p p r a is a l").
2nd attempt: exclude runs of single-letter WORDS. Still false-
positived on "A"/"R" living INSIDE an ordinary word, "(PAR)".
Final: only trust a WORD whose entire text already matches
^[ICRA]\d*$ (i.e. it looks exactly like a bare action code with
nothing else attached) as an anchor. "PAR)" and "Appraisal" fail
that test outright - there's no partial-match risk left, because
the whole word has to be just the letter (+ maybe fused digits).


**lines 33-47**

Was 1.5. Raised after finding real footnote digits silently dropped
by a hair: task 3.111's "A3" (page 58/NSO 3.110) has its digit's top
1.50432pt from the letter's top - a rendering-precision fluke that
missed the old `<= 1.5` cutoff by 0.004pt, while its bottom-diff
(4.02pt) was nowhere near level-aligned either, so it matched
neither rule and got dropped. Checked document-wide before changing
this: 30/345 digit decorations were being dropped this way, and 23
of them share this EXACT same near-miss pattern (top-diff 1.504,
bottom-diff 4.024) - genuine footnote digits, not ambiguous. The
other 7 are 10.4-21.2pt from both alignments - genuinely unrelated,
correctly still excluded at this new tolerance too. 2.0 sits cleanly
in the gap between the near-misses (1.504) and the real ambiguous
cases (10.4+), and stays well clear of the two examples that
originally calibrated 1.5 (2.224.4's level digit, diff 0.16; its
footnote digits, diff 0.64) - re-checked both before raising this.


**line 48** - on `ALIGNMENT_TOLERANCE = 2.0`

points


**line 49** - on `MAX_DECORATION_GAP = 8.0`

points - how close a small char must be to


**lines 50-52**

still count as "attached" to the letter
before it, rather than the start of
something else entirely


**lines 56-62**

Third false-positive found on the SAME title (2.223.2): OCR-spacing
("A p p r a is a l", "R e p o r t") sometimes isolates the first
letter of a word as its own one-character WORD, and a bare "A" or
"R" with zero digits still matches LETTER_ACTION_PATTERN trivially.
The word-match-only fix doesn't catch this - needs the spaced-run
check back too, now applied at the word level, not mixed with
fragile word-vs-char coordinate comparisons like the first attempt.


**line 63** - on `SPACED_WORD_GAP_MAX = 6.0`

points


**lines 193-195 (def _split_level_and_footnotes(anchor, decorations))**

Doesn't cleanly match either alignment - not confident
enough to guess, so it's left out rather than risk a wrong
answer. Worth a look if validation flags a lot of these.


**lines 239-247 (def extract_informed_instances(chars, top, bottom))**

Real characters for this marker (checked directly against
2.126, page 24 - block "2.126 ( i ) Quarterly Mission program
( i ) I C C R A ( i )") turned out to be five separate
characters, "(", " ", "i", " ", ")" - the space between the
parenthesis and the "i" is a real PDF character, not just
visual spacing absorbed by x0/x1 gaps. Scanning band[i:i+3]
directly for "(", "i", ")" therefore always missed - band[i+1]
was a space character, never "i". Filtering out whitespace-only
characters first restores the simple 3-in-a-row scan.


**line 324 (def extract_action_instances(text, chars, words, top, bottom))** - on `"x0": anchor["x0"]`

for column_roles.nearest_role()


## `parsing/column_roles.py`


**lines 1-21**

Extracts the table's column headers (role names - "Task Manager",
"Sector Manager (HQ-based)", etc.) and maps an action's x-position
to the nearest one, so a Responsibility can carry a real role, not
just an action letter.

Column headers in this DAM are rotated 90 degrees (pdfplumber marks
them upright=False) - confirmed by inspecting real characters:
reading "Task" gave 'T' at top=251.0, 'a' at top=246.5, 's' at
top=242.9, 'k' at top=237.9 - each next letter has a SMALLER top,
meaning the correct reading order is DESCENDING top, not the normal
left-to-right x order used for regular text. x0 is (near) constant
for all characters in one header - it marks the column's horizontal
position, same role x-clustering does for rows on the y-axis.

Two-line-wrapped headers (e.g. "Task Manager" / "Team Members" as
two visually adjacent vertical strips) need a two-pass cluster: a
tight pass groups characters into single text runs first (order
matters - descending top - before anything gets concatenated), then
a wider pass merges adjacent runs. Merging in one pass with a wide
threshold interleaves the two runs character-by-character instead
of concatenating them, since their y-ranges can overlap.


**line 23** - on `TIGHT_CLUSTER_GAP = 3.0`

points - groups a single text run


**line 24** - on `COLUMN_MERGE_GAP = 14.0`

points - merges wrapped header lines,


**lines 25-27**

confirmed against real gaps: wrapped
lines sit ~10-12pt apart, genuinely
different columns sit ~19-27pt apart


**lines 29-49**

Real bug found checking column headers across the whole document
(not just the one page - 29 - originally spot-checked): on some
pages, two ADJACENT but genuinely different columns sit close
enough in x0 (as little as ~2.0pt apart) to fall inside the same
TIGHT_CLUSTER_GAP(3.0) cluster. Since both runs span roughly the
same y-range (both are full header strings, not fragments), sorting
the merged cluster by top alone interleaves their characters -
"Regional Implementation Support Manager (RISM)" and "Country
Manager / DDG" (page index 43) came out as "...Support Manager
(CRoIuSntMr) y Manager / DDG". Checked real coordinates: within that
one cluster, characters alternate between EXACTLY two x0 values
(559.17 / 561.21, zero variance within each) - a clean bimodal
split, not natural single-run jitter. Y-range overlap was tried
first as the detection signal and rejected: rotated character
bounding boxes overlap substantially even in completely normal runs
(a rotated character's "height" is its pre-rotation WIDTH, which is
usually bigger than the spacing step between characters) - checked
document-wide, 838/841 clusters showed overlap, so it doesn't
distinguish anything. The x0-bimodality check does: run document-
wide, it flags exactly the one real corrupted cluster and nothing
else.


**line 50** - on `SUBGROUP_TOLERANCE = 0.6`

points - x0s within this count as "the


**line 51**

same" sub-run when checking bimodality


**line 52** - on `SUBGROUP_MIN_GAP = 1.5`

points - gap between sub-runs required to


**lines 53-55**

call a cluster genuinely bimodal, not
just jittery (real corrupted gap seen:
~2.04pt)


**lines 57-77**

Role headers can carry a trailing footnote-reference digit, e.g.
"Regional NSO Lead2" (confirmed via "Notes on NSO 3.110", footnote
2 = "Regional NSO Lead: PL-2 or PL-1 staff..." - see
docs/decisions.md 2026-07-28 entry). Left unstripped, the same real
role fragments into several different strings depending on which
footnote number happened to attach ("Regional NSO Lead1" through
"...Lead5" are all one role) - fatal for graph-building, where role
identity has to be canonical.

This is the SAME superscript concept as the action-level/footnote
split in action_geometry.py, just expressed differently because
header text is rotated 90 degrees: instead of a top/bottom
alignment shift, it shows up as a smaller SIZE and a small x0
offset relative to the character before it. Confirmed against 5
independent real examples ("Regional NSO Lead1" through "...Lead5",
pages 58/60/64/67/69) before using this: the trailing digit is
always size ~3.00 (vs. 4.5-8.5+ for surrounding lowercase body
letters) with an x0 offset of ~0.7-1.15pt. Checked it does NOT
false-positive on legitimate trailing digits that are part of a
real department code ("Manager PGCL.1", "Manager FIFC.3") - those
render at normal body size, not the shrunk footnote size.


**line 78** - on `FOOTNOTE_DIGIT_MAX_SIZE = 4.0`

points


**lines 104-109 (def _strip_trailing_footnote_digit(ordered_chars))**

The run's trailing characters are often whitespace (a real
character with its own position, not just a join artifact) -
first real bug found testing this: checking ordered_chars[-1]
directly almost always hit a trailing space instead of the
digit, so the check never fired at all. Need the last NON-space
character, not literally the last character.


**lines 117-122 (def _strip_trailing_footnote_digit(ordered_chars))**

Second real bug found testing this: multi-digit footnote numbers
("Specialist14" -> footnote 14, "FIFC Officer 11" -> footnote
11) only had their LAST digit stripped ("Specialist14" ->
"Specialist1") - need to walk back over EVERY consecutive small
trailing digit, not just one, the same way action_geometry.py
concatenates multi-digit footnote numbers.


**lines 138-147 (def _strip_trailing_footnote_digit(ordered_chars))**

What's immediately before the digit run, if this run has
anything else in it? If it's a literal ".", this is a
department code suffix (e.g. "FIFC.4"), not a footnote - leave
it alone. Third real bug found testing this: a footnote digit
can also be an entire run by itself (nothing else in it, e.g. a
bare "1 " or "2 " run split off on its own) - there's no "before
character" to check in that case, and real evidence (checked
document-wide) is that an isolated small-digit-only run is
always a stray footnote reference, so it's safe to drop the
whole thing.


**lines 215-217 (def extract_column_headers(chars))**

pass 1: tight runs, each internally ordered correctly - split
apart first if a "cluster" is actually two different columns'
runs merged by x0 proximity alone (see _split_if_interleaved).


**lines 230-251 (def extract_column_headers(chars))**

pass 2: merge adjacent runs (wrapped header lines) in x0 order.

Real bug found on pages 42/43/44: two genuinely DIFFERENT
columns ("Regional Implementation Support Manager (RISM)" and
"Country Manager / DDG") sit closer together (~2pt) on these
pages than a real wrapped-line continuation sits elsewhere on
the SAME page (~9pt) - gap size alone can't tell them apart
here, the "wrong" gap is smaller than the "right" one.

Added a second, non-geometric signal: if the accumulated group
text already ends with a BALANCED closing paren - e.g. "...
(RISM)" - treat that as a natural end-of-role boundary and stop
merging there, regardless of gap. Checked this document-wide
before keeping it (comparing against the old gap-only merge for
all 79 pages): it only changed output on the 3 pages with the
real bug, plus one more real find on page 26, where "Director,
Safeguards & Compliance (SNSC) Director, Resources Mobilisation
& Partnerships (FIRM) Director, Syndications & Client Solutions
(FIST) Manager - Programming (SNPB.1)" - four separate director
roles - was similarly merged into one blob and is now correctly
split into four. No other page changed, so this isn't
introducing new false splits anywhere else in the document.


**line 273 (def _ends_with_balanced_parens(text))** - on `if role:`

a stray whitespace-only run can otherwise


**line 274 (def _ends_with_balanced_parens(text))**

produce an empty group right at a forced break


## `parsing/hierarchy.py`


**lines 1-4**

Turns a DAM identifier string into hierarchy facts, purely from the
numbering scheme - no PDF layout involved. This logic checked out
correct against real data in the schema review (chapter "X",
process "X.XX0", task "X.XXX", child "X.XXX.X") - ported unchanged.


**lines 8-11**

Trailing (?:\.[a-z])? handles threshold_variant ids like "2.513.3.a"
- task_blocks.py constructs these itself (the PDF only ever prints
the bare "(a)", never the full id), so this only needs to round-trip
what task_blocks.py already built, not parse it from raw PDF text.


**line 31 (def get_chapter(identifier))**

2.221.1 -> '2'


**lines 91-95 (def get_parent_task_id(identifier))**

2.221.1 -> 2.221 ; 2.112 -> None (tasks have no parent_task_id,
only child_tasks do - their "parent" is the process, tracked
via process_id, not parent_task_id)
2.513.3.a -> 2.513.3 (a threshold_variant's parent is the
child_task it's a condition of)


**lines 137-142 (def get_children(task_id, all_ids))**

No depth-arithmetic shortcut here on purpose: process ("2.510")
and task ("2.513") are BOTH 2-segment ids - a process's children
(tasks) sit at the SAME string depth as the process itself, not
one level deeper, unlike every other level in this hierarchy.
Explicit node_type pairing avoids relying on segment count at
all, so this edge case can't silently creep back in.


**lines 144-148 (def get_children(task_id, all_ids))**

get_node_type() only handles dotted identifiers by design (its
own docstring: "X -> chapter, handled by caller before this") -
a bare chapter id like "2" has no dot and falls through to None.
Cover that case explicitly rather than silently getting an empty
children list for every chapter.


**lines 175-176 (def get_children(task_id, all_ids))**

threshold_variant nodes have no children - falls through,
nothing appended, correct by omission.


## `parsing/metadata.py`


**lines 1-17**

Pulls title / actions / footnote references / cross-references out
of a task's raw merged text.

v1 had a real bug here, found by testing against real pages (2.312.2):
extract_title() and extract_note_references() each tried to strip
"See DAM 16.100, 16.200..." cross-reference text independently, and
only ONE of the two paths actually did it. The other (the one title
went through) just ran NOTE_PATTERN (a bare 1-3 digit matcher) over
the raw text, which doesn't know "16.100" is a reference and instead
treats each digit group in it as footnote noise and deletes them -
producing titles like "See DAM ., ., ., and . technical cooperation".

Fix: reference-stripping happens in exactly ONE place
(`remove_references`), and every other function that needs
reference-free text calls it first. One source of truth instead of
two paths that can silently disagree - same lesson as the
authority_rules.py / authority_codes.json duplication in v1.


**lines 29-45**

v2 bug, found via the threshold_variant test on 2.513.3.a ("Up to
UA 2,000,000"): a bare \b\d{1,3}\b footnote-number matcher also
matches the digit groups inside a comma-formatted amount - "2" and
each "000" in "2,000,000" - and strips them, corrupting the title
into "Up to UA ,,". Real footnote-reference digits in this DAM are
always comma-free (surrounded by spaces or attached to an action
letter, e.g. "5 I6" or "2 2"), so excluding any digit group directly
touching a comma is a safe, evidence-based fix - not a guess.

Second instance of the exact same category of bug, found building
modeling/build_nodes.py: "PL-2"/"PL-1" (a staff grade notation, not
a footnote) also got stripped - "Concerned Staff members below PL-2
level" corrupted into "...below PL- level". Checked document-wide
before extending the fix (6 affected blocks, all "PL-N" staff-grade
references) and confirmed footnote digits in this DAM never sit
directly after a hyphen either - same reasoning as the comma
exclusion, extended to cover both.


**lines 53-56**

Second reference style, found in chapter 3 (task 3.225): a task
whose entire row is a redirect, e.g. "Refer to Activities 2.114 -
2.117 in Section 2." - a RANGE, not a comma list, and it needs
expanding (2.114..2.117), not just capturing the two endpoints.


**lines 75-76 (def _expand_id_range(start_id, end_id))**

Different prefixes (e.g. different chapter) - can't safely
assume a numeric range makes sense, just keep both ends.


**lines 166-168 (def extract_actions(text))**

OCR fused an action letter to a stray footnote digit
(e.g. "C4" meant to be "C" + footnote "4") - keep the
letter, the digit gets picked up separately as a note.


**line 187 (def extract_note_references(text, identifier=None))** - on `text = remove_references(text)`

<- fixed: was missing on the title path, present here


**lines 219-227 (def remove_note_references(text))**

Signal for the word-boundary corruption found via agent output on
2.223.2's title (see docs/decisions.md, 2026-07-28 OCR entry): a
lowercase letter immediately followed by an uppercase letter with no
space between them, e.g. "...alReport(...". Real clean English text
essentially never does this (the one place it legitimately could -
an acronym stuck to a word - isn't a pattern seen anywhere in this
document's clean titles). Checked document-wide before using this
as a trigger: found exactly the 6 known-corrupted titles, 0 false
positives among the other ~320.


**line 242 (def extract_title(text, identifier=None))** - on `text = remove_references(text)`

<- fixed: this line didn't exist in v1's title path


## `parsing/rows.py`


**lines 1-28**

Groups words into physical text rows by y-position, then sorts each
row left-to-right by x-position. This is the row-clustering that
solves pdfplumber handing back individual words with no line
structure.

Real bug found via a screenshot (NSO 3.110 table, page index 58):
rounding the top y-coordinate absorbs ordinary sub-pixel jitter
between words on the same line, but for a WIDE table row, the
rightmost cells can render at a y just far enough from the leftmost
cells (~1pt) to round into a different bucket entirely, even though
it's genuinely one visual row. Task 3.111's own "A3"/"A4" approval
codes landed in a separate row-bucket ABOVE 3.111's own identifier
row, and task_blocks.py had no way to know they belonged to the row
that followed - they were silently dropped as an unattachable
orphan. Confirmed document-wide, not a one-off: 25 rows across the
document are entirely action-code content sitting right next to an
identifier-led row - a shape no real standalone row can have.

Checked a blanket fix first (merge any two row-buckets within 5pt
that have zero overlapping word x-ranges) and rejected it: 1614
candidates document-wide, and several were NOT safe - rotated header
text fragments, footnote list markers, and at least one case
("Directors:17" sitting right before the next task's bare identifier
"2.224") that would have spliced two DIFFERENT tasks together.
Restricting the merge to rows that are ENTIRELY action-code content
(see _is_pure_action_row) excludes every one of those false
positives, since each of them contains a real word or a non-action
fragment.


**line 35** - on `ROW_MERGE_MAX_GAP = 5.0`

points - the real cases found are exactly


**lines 36-38**

1pt apart; this leaves headroom without
reaching into the ~9pt+ gaps that separate
genuinely different single-spaced lines.


## `parsing/task_blocks.py`


**lines 1-55**

Merges physical PDF rows into one text block per task/child_task.

v1 BUG, confirmed against real page 21 of the DAM (tasks 2.311 /
2.312.1): when a task's title wraps onto a line that lands AFTER its
actions row but immediately BEFORE the next task's bare identifier
row, v1 misread that trailing wrapped line as "floating title text
for the upcoming task" and stole it - producing 2.312.1's stored
title "agreement for Signature Signature of Financing Agreements
for..." where "agreement for Signature" actually belongs to 2.311,
not 2.312.1.

Root cause: v1 decided whether a stray line belonged to "the task
that follows" using ONLY a look-ahead check (is the next row a bare
identifier?) - it never checked whether a task was already open and
waiting for exactly this kind of trailing continuation.

Fix, v1: only apply the "this belongs to the next identifier"
look-ahead when `current_task is None`. That closed the 2.311 case
above, but a second real example (3.225 -> 3.226, chapter 3) proved
it wasn't sufficient: 3.225 is a "redirect" task whose entire row
("Communication to Government Refer to Activities 2.114 - 2.117 in
Section 2.") is grammatically complete and PDF-authored with a
terminating period - and 3.226's title genuinely starts on the very
next line, before 3.226's own identifier row appears. current_task
(3.225) was still "open" by the code's bookkeeping, so the v1 fix
wrongly glued 3.226's first title line onto 3.225.

Fix, v2: a currently-open task is only treated as "still accepting
stray lines" if its accumulated text does NOT already end in a
period. A trailing period is the PDF's own signal that the row is a
finished sentence (this DAM only seems to terminate text that way
for these redirect/"Refer to..." rows) - once seen, further stray
lines go through the same look-ahead check as the "nothing open"
case, instead of being blindly attached.

Fix, v3: a real screenshot of page 12 found a THIRD variant neither
v1 nor v2 caught. Task 2.126's entire title+actions ("Quarterly
Mission program ( i ) I C C R A ( i )") sit on ONE row, right before
2.126's own bare identifier row - textbook title-above-identifier.
But current_task (2.125) was still open, hadn't seen a period, so
v2's rule attached it to 2.125 anyway. The missing signal: 2.125
had ALREADY consumed its own actions row earlier. A task's actions
normally appear once; a stray line carrying a fresh batch of action
codes on top of a task that already has some is a much stronger
sign of "this is actually the next task" than punctuation is.

That signal is deliberately narrower than "line contains any action
code": it only fires when the line ALSO has real prose before the
first action code (like "Quarterly Mission program" before "( i )").
A bare trailing line like "( i )" with nothing in front of it is an
extremely common, completely normal pattern - the informed marker or
a footnote digit landing on its own row right after a task's main
action row - and must still attach to the currently open task, not
get diverted. Without this narrowing, the v3 rule would have wrongly
hijacked every task that has that (very common) trailing-row shape.


**lines 63-70**

Real bug found via agent output: page index 69's footnote section
header reads "Notes to NSO 3.510 - 3.520" (not "Notes on ...", every
other page's phrasing) - a one-off typo in the source PDF itself
(checked document-wide: 21 pages say "on", exactly 1 says "to").
NOTES_PATTERN never matched it, so task_blocks.py never recognized
the boundary and glued the ENTIRE footnote section - and even the
page footer ("Page 57") - onto task 3.524 as if it were still part
of its title.


**lines 74-85**

threshold_variant sub-items (found via screenshot: 2.513.3 -> (a)/(b)/
(c) by loan amount, 53 real occurrences across the doc, mostly
procurement threshold tables). The PDF only ever prints the bare
"(a)", never the full id - this has to be reconstructed from
whichever child_task was most recently opened.

Deliberately tight, no internal spaces: "(a)" not "( a )". The
informed marker always extracts as "( i )" with spaces (three
separate PDF characters joined by row-building), so this pattern
doesn't collide with it in practice. Excluding the letter "i"
outright anyway, as a defensive belt-and-braces in case a table ever
has a 9th lettered item and pdfplumber happens to render it tight.


**line 104 (def build_task_blocks(lines))** - on `last_child_task_id = None`

for reconstructing threshold_variant ids


**lines 111-112 (def open_task(line, row))**

identifier must stay first - get_identifier() anchors
to the start of the string.


**lines 125-127 (def attach(line, row))**

Append a stray continuation line to whichever task is
currently open. Callers only invoke this when current_task
is truthy.


**lines 153-156 (def attach(line, row))**

--- threshold_variant: bare "(a)"/"(b)"/... label, id has to
be reconstructed from whichever child_task opened last. Never
ambiguous with anything else on the page, so it always closes
whatever's open and starts fresh - no look-ahead needed.


**line 172 (def attach(line, row))**

--- continuation line (doesn't start with a bare identifier) ---


**lines 198-200 (def attach(line, row))**

A task is open, hasn't been signaled as finished
(no trailing period, and not "receiving a second
batch of actions") - this line belongs to IT.


**lines 204-207 (def attach(line, row))**

Either nothing is open, or what's open looks finished -
in both cases check whether the very next row is a bare
identifier with nothing else on it, meaning this line is
really the start of THAT task's title.


**lines 223-224 (def attach(line, row))**

Belongs to the upcoming identifier - close out
whatever's open first (e.g. the finished 3.225).


**lines 230-233 (def attach(line, row))**

Looked "finished" (trailing period) but the next
row isn't a clean identifier lead-in after all -
safest fallback is still attaching it to what's
open rather than silently dropping real text.


**lines 236-238 (def attach(line, row))**

else: nothing open and no upcoming identifier to hand
it to - genuinely orphaned, dropped. Rare; worth a test
fixture if it shows up in validation.


**line 242 (def attach(line, row))**

--- identifier line ---


**line 246 (def attach(line, row))**

child task, e.g. 2.325.1 - always starts a new block


**lines 257-258 (def attach(line, row))**

not actually a real identifier (shouldn't normally
happen given IDENTIFIER_PATTERN, kept defensive)


**line 264 (def attach(line, row))**

process boundary, e.g. 2.220 - closes, emits nothing


**line 269 (def attach(line, row))**

regular task, e.g. 2.221


**lines 274-275 (def attach(line, row))**

defensive fallback - shouldn't be reachable given the
patterns above, but fail safe rather than silently drop data


## `parsing/text_cleaning.py`


**lines 1-5**

Low-level OCR/spacing cleanup that runs before anything tries to
interpret text as a title, action, or reference. Not implicated in
any bug found - ported unchanged, except `fix_known_ocr_errors`
is flagged below as debt worth knowing about, not debt worth
fixing under a 9-day clock.


**lines 11-12 (def normalize_split_numbers(text))**

"1 6.100" -> "16.100" - pdfplumber sometimes reports digits of
the same number as separate words with a gap between them.


**lines 20-22 (def collapse_spaced_words(text))**

"R e c o m m e n d a t i o n s" -> "Recommendations", but never
collapse runs of action-code letters (I/C/R/A) - "I C C R A" is
four separate action columns, not the word "ICCRA".


**line 63 (def fix_known_ocr_errors(text))**

Split first letter: "R ecommendations" -> "Recommendations"


## `schema/schema.py`


**lines 6-7**

Order matters here: Node references Responsibility in a type hint,
so Responsibility (and the other leaf classes) must be defined above it.


**line 19 (class Responsibility(BaseModel))** - on `action: str`

single letter: "I", "C", "R", "A", or "( i )" for informed


**lines 21-23 (class Responsibility(BaseModel))**

Not every action code carries a level (plain "C" has none, "C1" does).
Optional with a real None default, instead of a separate has_level
bool - one field, one source of truth, can't disagree with itself.


**lines 26-28 (class Responsibility(BaseModel))**

A responsibility can cite zero, one, or several footnotes.
int to match Footnote.number below - same type on both ends of the
relationship so lookups don't need str/int coercion.


**line 41 (class AuthorityCode(BaseModel))** - on `code: str`

"I", "I1", "C3", "A2", etc. - matches Responsibility.action


**lines 45-49 (class AuthorityCode(BaseModel))**

Confirmed against the real legend (page 48 of the updated PDF):
I=black, C=red, R=yellow, A=green, (i)=no fill (italic only).
Optional since it's only known for the base letters until the
legend itself gets parsed/transcribed - don't fake a color for
entries that haven't been confirmed yet.


**line 68 (class Footnote(BaseModel))** - on `scope: str`

process_id this footnote number is scoped to


**line 83 (class Node(BaseModel))** - on `id: str`

NOT int - real ids are dotted strings like "2.221.1"


**lines 85-89 (class Node(BaseModel))**

threshold_variant added after finding 53 real cases (e.g.
2.513.3 -> (a)/(b)/(c) by loan amount) of a child_task having
ITS OWN children, letter-labeled rather than numbered. id
convention: "2.513.3.a", parent_task_id "2.513.3" - see
parsing/hierarchy.py and docs/decisions.md.


**line 100 (class Node(BaseModel))** - on `page: int | None = None`

source traceability back to the PDF


**lines 102-105 (class Node(BaseModel))**

True only for parents synthesized in modeling because the PDF
skipped straight to child ids (e.g. 2.312 never has its own row,
only 2.312.1 / 2.312.2 do). Never set this during extraction -
the parser stays faithful to what's actually on the page.


**lines 110-114 (class Node(BaseModel))**

Cross-references to OTHER tasks ("See DAM 2.xxx"), not footnotes.
Left unvalidated here on purpose - a reference might point outside
your ~50-table scope. Whatever builds graph edges from this later
has to check the target actually exists as a node before wiring
an edge; this field doesn't guarantee that.


**lines 120-122 (def has_children(self) -> bool)**

Derived from `children`, not a separate stored bool - two
fields that both mean "does this have children" is exactly
the kind of pair that can quietly disagree with itself.


**lines 128-132 (def actions(self) -> list[str])**

The aggregate "what actions happen on this task" view you
asked for - but computed from responsibilities, not stored
and populated separately. Responsibility.action stays the
one authoritative source; this is just a convenience read,
so it can never drift out of sync with the real data.


## `webapp/backend.py`


**lines 1-11**

The web layer - wraps agent.qa.answer_question() in an HTTP API and
serves the frontend. Deliberately thin: every real decision (how to
resolve a question, how to answer it) already lives in agent/qa.py,
this file's only job is request/response plumbing.

Why build-once-at-startup, not per-request: building nodes + graph +
search index from the PDF takes ~15-20s (confirmed while testing
earlier stages). Rebuilding that on every question would make the
agent unusably slow and would hammer the PDF parser for no reason -
the DAM doesn't change between requests. Built once when the server
starts, kept in memory, reused for every question after that.


**lines 31-34**

Populated once in the startup event below - a plain dict instead of
FastAPI's dependency-injection machinery, since there's only one of
these and it never changes after startup; not worth the extra
indirection for a project this size.


## `tests/fixtures/known_cases.py`


**lines 1-9**

Real DAM pages/tasks already diagnosed by hand against the actual
PDF (data/raw/updated dam file.pdf - the 79-page source, chosen
over the old 66-page MVP subset because it includes the glossary,
abbreviations, and authority-code legend). Same task ids, different
page numbers than the original diagnosis - re-verified against this
file directly, not assumed to carry over.

Each case documents an actual bug that was found and either fixed
or knowingly deferred, with the page/row evidence to back it up.


**lines 15-18**

v1 bug: title text trailing after the actions row got stolen by
the NEXT task (2.312.1) because both tasks happen to have a
bare identifier row nearby. Fixed in task_blocks.py by only
forward-attaching a stray line when nothing is currently open.


**lines 30-32**

v1 bug: "See DAM 16.100, 16.200..." cross-reference text got
digit-stripped into "See DAM ., ., ., and ." instead of being
extracted as references and removed cleanly from the title.


**lines 40-45**

RESOLVED with the task_blocks.py v3 fix (see module docstring):
a real screenshot of page 12 showed 2.126's title+actions are
genuinely on ONE row, textbook title-above-identifier - the
earlier "two lines merged by row-rounding" theory was wrong,
caught by seeing the actual table instead of guessing from
coordinates alone.


**lines 52-57**

v1-equivalent bug, found via a screenshot of the real table
(page 48): 3.225 is a "redirect" row whose whole line is a
complete, period-terminated sentence; 3.226's title genuinely
starts on the next line, before 3.226's own identifier appears.
Fixed by treating a period-terminated open task as finished,
rather than blindly attaching the next stray line to it.


**lines 71-73**

threshold_variant cases (2.513.3 -> (a)/(b)/(c) by loan amount) -
separate from CASES above since they need id reconstruction, not
just a title check. Page 48, confirmed via screenshot.


**lines 78-92**

Row-split case (NSO 3.110, page index 58 / printed page 46),
confirmed against a real screenshot: a wide table row's rightmost
action cells rendered on a DIFFERENT row-bucket than its own
identifier row (~1pt y-difference, enough to round differently in
build_rows()). Cascaded across the whole table - 3.111's own "A3
A4" were being dropped as an orphan, 3.112's I2/I3/I4/A5/A6 were
landing on 3.111 instead, 3.113's I5/I6 were landing on 3.112.
Fixed in parsing/rows.py (_merge_split_action_rows). Expected
values transcribed directly from the screenshot, not derived from
the code under test - (action, level) pairs, matching
extract_action_instances()/extract_informed_instances() output. The
trailing digits on "A3"/"A4"/"I2" etc. are footnote references, not
authority levels (see docs/decisions.md, 2026-07-21 geometry entry),
so level is always None here - the digit shows up in footnote_refs
instead, not checked by this fixture.


**lines 100-101**

The footnote numbers actually printed next to each action (e.g. the
"3"/"4" in "A3"/"A4") - flattened, since instance order isn't fixed.


**lines 108-110**

NOTE_PATTERN hyphen-adjacency case ("PL-2"/"PL-1" staff grades were
being corrupted into "PL-"/"PL-" by the footnote-digit stripper,
same category as the earlier comma-adjacency fix for "2,000,000").


## `tests/test_agent.py`


**lines 20-23 (def test_id_phrased_and_title_phrased_questions_give_same_answer(setup))**

The founding example from the very first project conversation:
"who are the informed parties for [Task_ID]" and "who needs to
be informed for [Task_title]" are the same question and must
produce the same answer, not different code paths.


**lines 51-53 (def test_consult_intent_never_matches_bare_c_or_check(setup))**

The "C" trap: bare "C"/C1/C2 = Check and Verify, C3/C4 = Consult
- two unrelated concepts sharing a letter. A "consult" question
must not accidentally surface Check and Verify responsibilities.


## `tests/test_backend.py`


**lines 1-10**

Tests the HTTP layer itself (routing, request/response shape), not the
agent logic again (that's already covered by tests/test_agent.py).

Uses FastAPI's TestClient instead of a real uvicorn process. TestClient
runs the app in-process and fires FastAPI's startup event itself, so
there's no "start a server, then hope it's still alive" problem - the
exact problem hit manually earlier (a background uvicorn process started
in one shell call doesn't exist anymore in the next, separate shell call).
In-process testing sidesteps that entirely, which is also just the
correct way to test an API layer.


**lines 33-34 (def test_ask_by_id_and_by_title_agree(client))**

Same founding example as test_agent.py's id-vs-title check, but
through the actual HTTP endpoint this time.


## `tests/test_build_nodes.py`


**lines 13-15 (def test_full_document_builds_without_error(nodes))**

79-page smoke test - just needs to not crash and produce a
plausible node count (3 chapters, ~35 processes, ~138 tasks,
~102 child_tasks, ~49 threshold_variants -> ~327 total).


**lines 20-24 (def test_chapter_process_task_hierarchy_is_internally_consistent(nodes))**

Every node's children must be the correct node_type one level
down, and every child's own parent-pointer must point back at
it - catches the get_children() prefix-vs-parent-pointer bug
(process/chapter children were silently wrong: process always
empty, chapter a flattened blob of every descendant).


**line 46 (def test_chapter_process_task_hierarchy_is_internally_consistent(nodes))** - on `assert checked > 200`

sanity: the check actually ran on real data


**lines 50-52 (def test_process_children_are_not_empty(nodes))**

The exact bug found: get_process_id-based reversal, not prefix
matching - "2.513" doesn't start with "2.510.", so a naive
prefix check always returned [] for every process.


**lines 57-58 (def test_chapter_children_are_processes_only(nodes))**

Not a flattened blob of every task/child_task/threshold_variant
under the chapter - just its direct processes.


**line 62 (def test_chapter_children_are_processes_only(nodes))** - on `assert "2.513" not in chapter_2.children`

a task - not a direct child


**lines 77-79 (def test_informed_marker_gets_a_resolved_role(nodes))**

The original v1 gap: "(i)" instances had no x0 at all, so they
never resolved to a role. 2.126 has multiple (i) markers on
page 12's table, which does have column headers.


**lines 88-90 (def test_unresolved_role_rate_stays_low(nodes))**

Not a hard invariant the DAM guarantees - a regression guard.
Was 1.2% (11/937) when this was last measured; fail loudly if a
future change silently makes role attribution much worse.


## `tests/test_column_roles.py`


**lines 9-15**

Page index 43: two adjacent columns ("Regional Implementation
Support Manager (RISM)" and "Country Manager / DDG") sit only
~2pt apart in x0 - closer together than a real wrapped-line
continuation sits elsewhere on the SAME page (~9pt). This one page
exercises both column-header bugs found and fixed: character
interleaving in the tight-cluster pass, and a false merge across
genuinely different columns in the wide-merge pass.


**lines 18-20**

Page index 26: a separate real find made while validating the
balanced-paren fix - four distinct Director roles were merging into
one blob.


**lines 32-34 (def test_no_character_interleaving(page_43_headers))**

The bug produced "Regional Implementation Support Manager
(CRoIuSntMr) y Manager / DDG" - garbled fusion of "(RISM)" and
"Country". Confirm that specific corruption is gone.


**lines 39-40 (def test_rism_and_country_manager_are_separate_columns(page_43_headers))**

Two genuinely different roles - must not be merged into one
header string.


**lines 49-50 (def test_four_director_roles_not_merged())**

page index 26 - real find while validating the balanced-paren
fix: four distinct Director roles were merging into one blob.


**line 63 (def test_four_director_roles_not_merged())**

the merged blob must not appear


**lines 68-70 (def test_no_empty_headers())**

A stray whitespace-only run right at a forced break (balanced
paren) used to produce an empty header entry before this was
filtered - confirm it's gone, document-wide.


**lines 79-82 (def test_footnote_digit_stripped_from_role_headers())**

"Regional NSO Lead1" through "...Lead5" (pages 58/60/64/67/69)
are all the SAME real role, fragmented by a trailing footnote
digit baked into the header text. Confirmed via "Notes on NSO
3.110" (footnote 2 explains "Regional NSO Lead") before fixing.


**lines 95-98 (def test_multi_digit_footnote_fully_stripped())**

"FIFC Officer 11" / "Specialist14" only had their LAST digit
stripped by the first version of this fix ("...11" -> "...1") -
real multi-digit footnote numbers need every trailing small
digit removed, not just one.


**lines 109-112 (def test_department_codes_with_periods_not_stripped())**

"Manager FIFC.4" / "Manager FITR.2" / "Manager PGCL.1" are real
department codes, not footnote references - the digit directly
follows a literal ".", which every confirmed real footnote case
never does. Must survive the strip.


**lines 124-127 (def test_full_document_duplicate_responsibilities_stay_low())**

Regression guard for the underlying goal: near-duplicate
responsibilities caused by header corruption. Was 50 before the
column_roles.py fixes, 3 after (all on page 43, the tightest
column spacing in the document - a known, localized residual).


## `tests/test_graph.py`


**lines 26-28 (def test_who_approves_matches_screenshot(graph_and_nodes))**

Task 3.111 (NSO 3.110 table, page index 58) - confirmed against
a real screenshot: Origination Sector Manager (footnote 3) and
Supporting Dept. Division Manager (footnote 4) both approve.


**lines 42-45 (def test_who_must_be_informed_is_the_same_query_shape(graph_and_nodes))**

The founding example from the very first project brief: "who
are the informed parties for X" and "who needs to be informed
for X" are the same question, and should be the same lookup
with a different action filter, not different code paths.


**lines 64-67 (def test_out_of_scope_references_are_skipped_not_wired(graph_and_nodes))**

2.312.2 references "See DAM 16.100, 16.200, 16.300, 16.400" -
outside the ~79-page scope of this document. schema.py's own
comment warns a reference might point outside scope and has to
be checked before wiring an edge - confirm that check happens.


**line 103 (def test_tasks_for_role_is_reverse_of_responsible_roles(graph_and_nodes))**

reverse check: 3.111's approvers should include this role back


## `tests/test_row_merge.py`


**lines 38-43 (def test_row_split_actions_match_screenshot(page_58_blocks, task_id))**

NSO 3.110 table (page index 58): a wide table row's rightmost
action cells were rendering on a different row-bucket than their
own identifier row, causing task_blocks.py to drop them as
orphans or misattribute them to the wrong task entirely (a
cascading one-row shift). Values below are transcribed directly
from a real screenshot, not derived from the code under test.


**lines 65-67 (def test_hyphen_adjacent_digits_not_stripped(page_58_blocks, task_id, expected_title))**

NOTE_PATTERN was stripping the "2"/"1" in "PL-2"/"PL-1" as if
they were false footnote numbers - same category of bug as the
comma-adjacency fix for "2,000,000", just via a hyphen instead.


## `tests/test_search.py`


**lines 27-29 (def test_fake_looking_number_not_treated_as_id(index))**

find_ids_in_query only returns candidates that actually exist as
real node ids - a query mentioning some other number shouldn't
be mistaken for a DAM id.


**lines 47-49 (def test_process_titles_are_searchable(index))**

Real gap found testing this: process titles ("3.110 ORGANIZATION
OF NSO MISSIONS...") were originally excluded from the index -
a query matching a real process name matched nothing relevant.


## `tests/test_task_blocks.py`


**line 83 (def test_threshold_variant_ids_reconstructed())**

and the parent itself should still parse as an ordinary child_task


## `tests/test_title_corruption.py`


**lines 15-17 (def test_notes_to_variant_recognized_as_section_boundary())**

Page index 69's footnote header reads "Notes to NSO 3.510 -
3.520" - a one-off typo in the source PDF (every other page
says "Notes on"). NOTES_PATTERN must match both.


**lines 23-26 (def test_3524_title_no_longer_swallows_footnote_section(nodes))**

Before the fix: 3.524's title included the entire "Notes to
NSO 3.510 - 3.520" footnote section AND the page footer
("Page 57"), because task_blocks.py never recognized the
section boundary and kept attaching every following line.


**line 30 (def test_3524_title_no_longer_swallows_footnote_section(nodes))** - on `assert "Regional NSO Lead" not in title`

footnote 1's text


**lines 37-42 (def test_known_corrupted_titles_recovered(nodes, task_id))**

These 6 titles were word-boundary-corrupted by pdfplumber's own
word extraction merging two close-together lines' characters
(e.g. "ProjectApprais alReport" instead of "Project Appraisal
Report") - not a general claim of perfection, just confirming
the character-level recovery path actually improves them versus
the raw corrupted word-based text.


**lines 48-49 (def test_2223_2_title_recovers_real_words(nodes))**

The original motivating case - confirm actual readable English
comes back, not just "not corrupted by the detector's own regex".


**lines 59-62 (def test_corruption_rate_stays_low(nodes))**

Was 6/327 before recovery; the character-level fallback fixes
most but not guaranteed all (superscript footnote digits can
still land in an unexpected row-bucket in rare cases - a known,
documented trade-off, not silently ignored).



## `agent/action_codes.py`

**lines 9-22**
Real gap found live (2026-09-03, see docs/decisions.md): asking "what's I, A and (i)?" right after a task question got silently swallowed by the context-carryover fallback in qa.py - the letters are too short to count as "real content words" (see _content_word_ count there), so the vague-question heuristic treated it as an under-specified follow-up about the same task, instead of what it actually was: a question about what the DAM's own action-code legend means. data/reference/authority_codes.json already had the DAM's own legend text extracted (carried over from v1, schema/schema.py's own AuthorityCode model was built for exactly this) but nothing in the v2 agent ever read it - this wires it in as its own detection path, same pattern as agent/glossary.py, and - critically - has to run BEFORE the context-carryover / vague-question logic in qa.py's answer_question(), not after, or it never gets a chance to fire.

**lines 33-35**
Ordered the way the DAM's own legend presents them (Initiate, Check/ Verify, Consult, Review, Approve, Informed) - reused for the "explain the whole legend" answer below, not just individual lookups.

**lines 44-47**
A generic ask about the legend/system itself, with no specific code named - "what do the action codes mean", "explain the legend". Kept separate from the per-code trigger below since this one doesn't need any code token present to fire.

**lines 56-60**
Case-sensitive on purpose - these codes are always written upper- case in the DAM and in how this app talks about them elsewhere (agent/authority.py's INTENTS, _format_role_list's "A: ..." lines). Matching lowercase too would make "i" (the pronoun) and "a"/"c" as ordinary short words far too easy to hit by accident.

**lines 109-113**
Keep only codes that are actually in the legend (the bare- token regex can in principle match a stray capital letter that isn't a real code at all - "( i )" always is, and [ICRA]\d? always is by construction, so this is mostly a safety net, not a real filter in practice).

**lines 136-142**
Generic "explain the legend" - the six top-level codes only (bare I/C/R/A/(i), plus C3 as the one distinct enough from C1/C2 to be worth naming up front: Consult, not Check). Numbered variants (A1-A3, C1-C4, R1-R2, I1-I3) exist for more specific delegation levels within each action - mentioned, not spelled out, to keep this answer readable; a follow-up naming a specific one (e.g. "what does C2 mean") gets the detailed version above.

## `agent/authority.py`

**lines 56-60**
Every single word that appears in any intent's keyword list (multi- word keywords like "sign off" get split into their component words - correction operates word-by-word, then the existing substring check below still runs against the corrected text unchanged). Built once at import time since INTENTS is static.

**lines 103-109**
Looser threshold than knowledge/typo_correct.py's 0.88 default, same reasoning as agent/glossary.py's trigger-word correction: this is a small (~35-word), curated, semantically distinct vocabulary, not a large organic-language one, so the collision risk that justified 0.88 elsewhere is much lower - checked directly against a batch of unrelated real words before lowering this, zero collisions found.

## `agent/generate.py`

**lines 4-7**
Kept as its own constant, not inlined into SYSTEM_PROMPT below, so build_grounding_prompt can swap it out via an exact-string replace for _LONG_ANSWER_RULE when there are many facts to state (see there) without the two ever risking drifting out of sync with each other.

**lines 13-24**
Real tension found live (2026-09-03, see docs/decisions.md): the mandatory Check/Verify + informed-party notes feature (also 2026-09-03) routinely pushes a real answer's fact count to 4-6 roles (previously usually 1-2 - just the specific action asked about). Squeezing that many role names into 1-3 sentences while ALSO keeping every one of them verbatim intact (rule 4) is a genuinely hard constraint for a model to satisfy at once - the honest ways to resolve that pressure are to drop a role, paraphrase/shorten a name, or run longer than 3 sentences, and only the third one doesn't silently fail the grounding check below. This rule is swapped in specifically when the fact count is high, removing that pressure without touching rule 4's actual accuracy requirement at all.

**lines 33-36**
The fact-count threshold above which _LONG_ANSWER_RULE replaces _SHORT_ANSWER_RULE - 4 because 1-3 facts is exactly what the 1-3 sentence cap was originally sized for (one fact per sentence, roughly - the common case before the mandatory-notes feature existed).

**lines 90-97**
Appended as its own numbered rule rather than folded into the rules above, so the "keep role names/footnote numbers intact" rule (4) still reads naturally for the English-only case this prompt was originally written for - added on 2026-08-06 for multi-language support (see docs/decisions.md). Role names are organizational job titles, not really "translatable" in the first place, and rule 4 above already governs them - this just makes explicit that the language switch doesn't relax it.

**lines 118-125**
Collapses whitespace and lowercases before comparing - makes the grounding check robust to trivial formatting noise a model might introduce (extra/missing spaces, different casing) WITHOUT weakening what it actually verifies: the exact same words, in the exact same order, still have to be present. Added 2026-09-03 (see docs/decisions.md) after finding this was rejecting some otherwise-faithful rephrasings over nothing but incidental whitespace/case differences.

## `agent/glossary.py`

**lines 9-14**
Deliberately narrow trigger phrasing - only fires on "what does X mean/stand for", "define X", "meaning of X" style questions. Does NOT trigger on a bare "what is X", since that overlaps too heavily with ordinary DAM-task questions like "what is 2.120" - those need to keep reaching the normal node-resolution pipeline in qa.py, not get hijacked here.

**lines 28-39**
Bare "what's X" / "what is X" / "whats X" - deliberately handled separately from _TRIGGER_PATTERNS above, not merged into them, because this phrasing is genuinely ambiguous ("what is 2.120" must still reach the normal DAM id lookup). Only ever treated as a glossary question when: (a) it's a single bare token with no dots or spaces (a DAM id always has a dot, e.g. "2.120"; a task description is always multiple words), and (b) that token actually resolves in the glossary - if it doesn't resolve, this returns no match at all rather than an honest "not found", since an unresolved bare "what's X" might just as easily be a mistyped task question as a real glossary miss, and guessing wrong here is worse than falling through to the normal pipeline.

**lines 43-48**
The trigger phrasing's own words, not the term being asked about - typo-correcting "what dose DDG men" into "what does DDG mean" should never risk touching "DDG" itself. Safe in practice even without this vocabulary being exhaustive: correct_words() already skips ALL-CAPS and sub-4-letter words, which covers virtually every real acronym in this glossary (see MANUAL_ALIASES / abbreviations.json).

**lines 55-60**
Matches a standalone all-caps token like "DDG" or "RDVP" embedded in a longer role name (e.g. "Country Manager / DDG") - built from checking real role names extracted from the DAM: composite roles consistently spell out full words in Title Case and only use ALL-CAPS for an embedded acronym, so this stays narrow to genuine acronym mentions instead of matching ordinary words.

**lines 72-83**
Manual, hand-added exceptions - NOT extracted from pages 2-7, kept in a separate dict rather than merged into abbreviations.json so that file stays a pure, reproducible extraction of the PDF (rerun parsing/glossary.py against the source and you get exactly abbreviations.json back, no hidden manual edits). Added here because real usage surfaced a real gap: "RDNG" appears directly in DAM role names (confirmed: "RDG / Director RDNG", "Country Manager / DDG RDG / Director RDNG") but the Abbreviations list itself never defines it as its own entry - only "RDG" is defined there, with a note that RDG "also covers the Director of the Nigeria Country Office". This is that same fact, just also reachable under the exact acronym the DAM actually uses in role names.

**lines 152-162**
A looser threshold than knowledge/typo_correct.py's 0.88 default on purpose: short trigger words ("what"/"does") only reach ~0.75 against a common 1-character transposition typo ("waht", "dose") - a 4-letter word's ratio ceiling under a transposition is just lower than a longer word's. 0.88 was raised specifically to stop a large, organic-language vocabulary (DAM title words) from false-positiving on unrelated real words; that risk is much smaller here - this vocabulary is a short, curated, semantically distinct list of ~16 words, checked directly against a batch of unrelated realistic words before lowering this (only one weak collision found: "form" -> "for", low-impact even if it fires).

## `agent/qa.py`

**lines 18-42**
Real gap the professor flagged: a brand-new employee who doesn't know any DAM ids tends to type something short - a single word ("mission"), or just the verb with no subject ("approve") - and the old behavior silently picked resolve_query's top-scoring guess and answered as if it were certain. Measured directly: "mission" alone scores 0.48/0.45/0.41 across THREE different real tasks (2.121, 2.124, 2.125) - genuinely ambiguous, not a confident match that just happens to have a modest score. "approve" alone scores 0.46 against a single task (2.513.3) it has no real reason to specifically mean. Two independent, deterministic signals catch this - same "measure, don't guess" approach as CONTEXT_OVERRIDE_MAX_SCORE above:

1. Too few real content words: strip English stopwords (sklearn's    own list) and this app's own intent-verb vocabulary ("approve",    "informed", "check", ...) - a verb alone or a question with no    real subject left over is inherently under-specified, regardless    of what resolve_query happens to score it. 2. A close score gap to the runner-up: even a longer, well-formed    query can genuinely name something with 2+ plausible targets -    "mission" is the clean example (0.48 vs 0.45, a 6% gap).

CLARIFICATION_MAX_SCORE (0.6) and CLARIFICATION_MIN_GAP (0.15) reuse the same measured cluster CONTEXT_OVERRIDE_MAX_SCORE was calibrated against: genuine, unambiguous matches in this corpus score 0.65-0.89 with real separation from their runner-up (see docs/decisions.md).

**lines 84-105**
Real bug this fixes: a chat follow-up like "who are the informed parties for that activity?" names no real subject of its own, so resolve_query has zero legitimate signal about which node it means - it was landing on coincidentally-overlapping, unrelated nodes instead (2.118 "Communication with Co-Financiers of projects" vs the entirely different 3.226 "...and third parties" - the follow-up's stray word "parties" happened to overlap with 3.226's title, not 2.118's, at a comfortably "confident" 0.42).

First attempt at this fix matched a fixed list of anaphoric phrases ("that activity", "it", etc.) - defeated immediately by a second, differently-worded live follow-up ("and who are the informed partie?") that resolved to the exact same wrong node at the exact same 0.42 score, with no pronoun and no phrase from the list at all. Measured directly (not guessed) instead: genuine, specific-subject matches in this corpus score 0.71-0.89 ("quarterly mission program" 0.888, "loan grant processing" 0.714); both real coincidental- overlap failures measured here score 0.39-0.42. CONTEXT_OVERRIDE_ MAX_SCORE sits at the empirical gap between those two clusters - same "measure the real cases, don't guess the threshold" approach as knowledge/typo_correct.py's DEFAULT_MIN_RATIO. See docs/decisions.md, 2026-08-06, for the measurements and the full comparison table.

**lines 188-190**
C/C1/C2 (check, verify) only - deliberately excludes C3/C4 (consult), same action-code split agent/authority.py's "check" vs "consult" intents already draw. See _format_mandatory_notes.

**lines 385-393**
Action-code legend questions ("what's I, A and (i)?", "what does C2 mean") have to be caught here, before resolve_query/context- carryover run - a real live bug found this the hard way: these questions have too few "real content words" (bare letters get stripped by _content_word_count) to look like anything but an under-specified follow-up, so they were silently getting swallowed by the context-carryover fallback below and re- answering whatever task was already open instead. See agent/action_codes.py, docs/decisions.md 2026-09-03.

**lines 421-438**
Zero TF-IDF overlap with anything in the DAM has two very different real causes, and they need different replies: a query that's ONLY generic/intent words with no real subject at all ("informed" alone) is still on-topic, just under-specified - same fix as _needs_clarification above, just reached via an empty match list instead of a weak one. A query with real, substantive content words that still shares nothing with the DAM's vocabulary ("what's the weather today") is a much stronger, honest signal that it's genuinely outside this app's scope - said explicitly instead of the vaguer "couldn't find a task", which reads like a search miss rather than "this isn't what I'm for". Reuses _content_word_count rather than a topic keyword list on purpose - a fixed list of "off-topic subjects" is exactly the kind of brittle, rephrasing-defeated heuristic that failed once already this session (see the context-carryover entries in docs/decisions.md).

**lines 488-494**
facts drives both the deterministic "roles" shown to the user and what agent/generate.py's grounding check requires an LLM rephrasing to preserve verbatim - the mandatory Check/Verify and informed-party notes above are real facts stated in "answer" now, so they have to be in here too, or an LLM phrasing pass could silently drop them without the grounding check ever catching it (see docs/decisions.md, 2026-09-03).

## `agent/smalltalk.py`

**lines 12-15**
Widened 2026-08-06 for a brand-new employee who doesn't know this tool or the DAM at all and wouldn't necessarily type the word "help" - "how does this work", "I'm new here", "I don't know where to start" all land on the same guided reply as "help" itself.

**lines 23-33**
A few variants per category rather than one fixed line each - purely cosmetic (every variant still says the same substantive thing), but a canned reply that's identical on every single greeting is one of the fastest ways a tool reads as a script instead of something actually responding to you. Kept small and all still individually true/accurate - not going for jokes, just not repeating word for word every time. Every "greeting" variant still contains "Hello" (capital H), every "farewell" variant still contains "Goodbye" (capital G), and the "help" variants still contain the exact phrase "Delegation of Authority Matrix" - tests pin those substrings on purpose, so any new variant added later has to keep them too.

**lines 93-98**
Every plain word the patterns above can match on, so a typo in one of them ("helo", "godbye", "thnaks") still resolves - anything shorter than 4 letters ("hi", "hey", "bye"...) is left to match exactly, same reasoning as knowledge/typo_correct.py's own min_word_length default: fuzzy-correcting a 2-3 letter word is unreliable enough to not be worth the false-positive risk.

**lines 136-140**
Looser threshold than knowledge/typo_correct.py's 0.88 default - same reasoning as agent/authority.py and agent/glossary.py's trigger-word correction: a small, curated, semantically distinct vocabulary carries much less false-positive risk than a large organic-language one, checked directly before lowering this.

## `knowledge/search.py`

**lines 103-106**
vectorizer.vocabulary_ includes the fitted bigrams too (e.g. "country strategy") alongside single words - only the single words are meaningful things to typo-correct an individual query word against.

## `knowledge/typo_correct.py`

**lines 6-18**
Tuned against a real false-positive, not picked arbitrarily: 0.82 was loose enough to "correct" the genuinely-different, correctly- spelled word "unrelated" into "related" (ratio 0.875 - they share a root, textbook false positive for any edit-distance approach) purely because "related" happened to be the closest word in a narrow ~1400-word DAM-title vocabulary. Every real typo this feature was built for - "aproves"/"approves" (0.933), "chek"/"check" (0.889), "intiates"/"initiates" (0.941), "qaurterly"/"quarterly" (0.889), "mision"/"mission" (0.923), "helo"/"hello" (0.889) - still clears 0.88 with room to spare, so raising the floor to 0.88 closes that false-positive gap without losing any of the cases that motivated building this in the first place. See tests/test_typo_correct.py for both sides of this pinned.

**lines 63-65**
Preserve the original word's capitalization style so a corrected word doesn't look out of place mid-sentence (e.g. a corrected first word of a sentence stays capitalized).

## `llm/groq_provider.py`

**lines 7-15**
llama-3.3-70b-versatile was the original default but Groq shut it down for standard/developer API keys on 2026-08-16 (moved to Enterprise-only, contact-sales pricing - see console.groq.com/docs/ models, confirmed live against a real 404 from production, not assumed - see docs/decisions.md). openai/gpt-oss-120b is Groq's current flagship production model on the standard plan: similar speed (~500 t/s), 131K context, and - unlike the smaller 20B variant - strong enough instruction-following for this app's strict grounded- phrasing and two-line translation-format prompts.

## `llm/tone.py`

**lines 5-24**
Chatbot major 4 of 4 (2026-09-03, see docs/decisions.md): "the chatbot should ... handle tone detection and better responses." Applies to every response type (Adem's explicit choice), not just grounded DAM answers - a frustrated "why won't this work AGAIN" and a confused "I don't get what C1 means" deserve a warmer opening whether the answer underneath is a fact lookup, a glossary lookup, or an honest refusal.

Architecture, deliberately kept simple: detection (LLM-based, per Adem's explicit choice over a deterministic heuristic) is a single, separate, CHEAP call - gated by looks_emotional() below so the overwhelming majority of ordinary, neutral questions never pay for it, same cost-avoidance pattern llm/translate.py's looks_non_ english() already uses. The RESPONSE adjustment itself is then a small, deterministic prefix (EMPATHY_PREFIXES) rather than a second LLM call or a folded-in instruction - keeps this fast, free of a second round trip, trivially testable, and applicable uniformly to every response type (including the many canned/deterministic messages - smalltalk, out-of-scope, glossary - that otherwise never touch an LLM at all).

**lines 28-34**
Real signal, not a guess: short, common frustration/confusion markers checked against realistic phrasing. Multi-word phrases matched as substrings (not a word-set), single words matched whole-word (via \b) to avoid matching inside unrelated words. False positives here only cost one extra, self-correcting Groq call (detect_tone below defaults to "neutral" on any doubt) - never a wrong answer - same reasoning translate.py's looks_non_english() already documents for itself.

**lines 113-119**
One deterministic, natural-sounding opener per tone per supported language - not routed through the LLM translation shim (llm/ translate.py) for the same reason webapp/frontend/src/i18n.js's UI chrome isn't: this is a small, fixed set of strings, not dynamic content, so hand-translating once is faster, free, and more consistent than an LLM call on every use. "neutral" has no entry on purpose - apply_tone_prefix() below is a no-op for it.

## `llm/translate.py`

**lines 13-23**
Cheap, deterministic, LLM-free pre-filter - same "don't pay for what you don't need" reasoning as knowledge/typo_correct.py only running when a word doesn't already match: the overwhelming majority of real traffic here is English, and every non-English query costs an EXTRA Groq round trip (translate the query in, translate the answer back out) on top of the normal one. This heuristic only decides whether it's worth even ATTEMPTING translation - it is never trusted for the real language identification itself, that's always the LLM's job once this flags true. Defaults to "assume English" on anything ambiguous or too short, rather than paying the extra round trip on every message.

**lines 27-31**
"o" and "as" deliberately left out of the Portuguese set - both are also common, short English tokens ("as needed", "as approved"), and unlike the rest of these lists neither is distinctive enough to trust on a single hit. Everything kept here is a real, whole-word match risk of essentially zero in ordinary English DAM phrasing.

## `modeling/nodes_cache.py`

**lines 6-9**
has_children/actions are @computed_field on Node - always derivable from children/responsibilities, so caching them would just be dead weight on disk and Node recomputes them for free the moment load_nodes() reconstructs each one.

## `extraction/pdf_loader.py`

**lines 1-3**
Opens the DAM PDF and hands back a pdfplumber document (pages, words, characters). This layer wasn't implicated in any bug found in v1 - ported essentially unchanged, just with an honest docstring.

## `extraction/table_extractor.py`

**lines 1-8**
Pulls words and characters off a single pdfplumber page. Both are just pdfplumber's own primitives, positioned (x0/top/bottom per item) - that positioning is what row-clustering and geometry work downstream depend on.

NOTE: v1's version of this file had a comment claiming it used "Camelot/Tabula" - it never did, it's always been plain pdfplumber. Wrong comments are worse than no comments; fixed here.

## `parsing/column_roles.py`

**lines 152-165**
NOT safe to unconditionally insert a space at this merge boundary - tried that live on 2026-09-03 as a candidate fix for the "Task Manager1 & Project Team Members" glued- role-name bug (see docs/decisions.md) and it broke a DIFFERENT, previously-correct case instead: "Sector Manager (HQ-based / Region-based)" became "HQ- based" because that merge boundary falls right after a hyphen, which needs NO space. Confirmed by direct re-extraction that the Task Manager1 case isn't even a wrapped-header- merge issue in the first place (the missing space is inside a single run, between "Manager" and a shrunk "1" that looks like an unstripped mid-string footnote digit - a real, separate, narrower issue, left as a known limitation rather than chasing a risky general fix here).

## `parsing/glossary.py`

**lines 15-24**
Every one of these pages ends with a lone lower-case roman numeral (the page footer's own page number, e.g. "xiv", "xv", "xvi" ... in strict page order across pages 2-7) landing close enough in `top` to the last real definition row on the page that TOP_MERGE_TOLERANCE folds it into that row's text - confirmed by checking that these trailing tokens form an unbroken page-number sequence, not real content. Stripped as a final cleanup pass rather than filtered at the row level, since it's cheaper and more precise than trying to exclude the footer at cluster time (which risks also cutting real single-word defs).

**lines 126-130**
A fresh term arriving alongside definition text is what actually starts a new entry - NOT "any row with definition-column text", which would wrongly treat a definition that simply wraps onto its own line (no new term on it) as a brand new, term-less entry.

## `webapp/auth.py`

**lines 30-36**
--------------------------------------------------------------- Secret / config --------------------------------------------------------------- No safe fallback for this one - unlike DATABASE_URL, a missing JWT_SECRET_KEY should fail loudly at startup rather than quietly sign every token with a guessable default that would still work after someone reads this source file.

**lines 45-47**
--------------------------------------------------------------- Passwords ---------------------------------------------------------------

**lines 56-58**
--------------------------------------------------------------- JWTs ---------------------------------------------------------------

**lines 115-122**
--------------------------------------------------------------- Login rate limiting (per source IP, sliding window) --------------------------------------------------------------- In-memory is a deliberate, acknowledged limitation: it resets on every process restart and doesn't share state across multiple backend instances. Fine for this project's single-instance free- tier deployment; would need a shared store (Redis) to be correct behind more than one instance.

## `webapp/backend.py`

**lines 49-54**
Authlib's OAuth client stores a short-lived state/nonce in the session between the redirect to Google/Microsoft and the callback coming back - this is that session, cookie-based and signed with the same secret that signs JWTs. It never holds anything beyond that OAuth handshake; login state itself lives entirely in the JWT the client stores, not in this session.

**lines 64-71**
Prefer the pre-built cache (baked into the Docker image at build time via scripts/build_nodes_cache.py - see that file and docs/decisions.md, 2026-08-06) - re-parsing the raw PDF with pdfplumber on every process boot was heavy enough to OOM-kill the container on Render's free tier. Falls back to a live parse when no cache exists yet (fresh checkout, or data/raw/ changed and the cache hasn't been regenerated), so this never hard-depends on the cache being present.

**lines 79-83**
Creates the users table if it doesn't exist yet. Safe to call on every startup - a no-op once the table is there. Separate from the nodes/graph load above: this is the one piece of state that needs to survive process restarts (see webapp/db.py's docstring on why that means Postgres, not SQLite, once deployed).

**lines 96-101**
The node_id this same chat thread last resolved to, if any - the frontend tracks this per conversation (see Chat.jsx) and sends it back so pronoun-style follow-ups ("who are the informed parties for THAT ACTIVITY?") have a real anchor instead of resolve_query guessing off incidental word overlap. See agent/qa.py's answer_question docstring and docs/decisions.md, 2026-08-06.

**lines 103-109**
Explicit language picker override (2026-09-03, see docs/ decisions.md) for the ANSWER's language - independent of whatever language the question text itself is in. None/"auto"/ omitted (the default) keeps the original auto-detect-from-the- question behavior. Any other supported code (en/fr/es/pt/ar) always wins - e.g. asking "who approves 3.111" in English while the UI language picker is set to French still answers in French.

**lines 152-155**
Can't detect/translate without an LLM - be honest about why instead of silently matching non-English text against an English-only search index and (most likely) failing to resolve anything at all.

**lines 164-168**
Only reachable here when the question itself looked English (so the branch above never set translation_error) but the user explicitly picked a non-English answer language with no LLM available to produce one - be honest about that gap too, same principle as the query-side check above.

**lines 184-187**
Real DAM facts to protect - the stricter, grounding- checked path (agent/generate.py), phrased in answer_language (explicit picker override if one was given, else whatever the question was detected in).

**lines 192-194**
No facts to fabricate here (smalltalk/help/vague/out-of- scope/invalid-id) - a static English message just needs straight translation, no grounding check required.

**lines 219-232**
Tone detection (2026-09-03, see docs/decisions.md) - applies to EVERY response type (Adem's explicit choice), not just grounded DAM answers, which is exactly why this runs as a deterministic prefix applied here at the very end rather than folded into humanize_answer()'s prompt above: that path only runs for grounded answers, but a frustrated "why won't this work AGAIN" deserves the same warmer opening whether the answer underneath is a fact lookup, a glossary lookup, or an honest out-of-scope refusal. looks_emotional() gates the actual Groq call so ordinary neutral questions (the large majority) never pay for it - same pattern as looks_non_english() gating translation above. Detected from payload.question (what the user actually typed), never the translated/English version - tone is about how they expressed themselves, not the retrieval-pipeline text.

**lines 302-305**
Rate-limited by source IP before touching the database at all - per NFR8/Chapter 5, both to slow down credential stuffing and so a flood of login attempts can't be used to load-test the password-hashing step itself.

**lines 310-312**
Same generic error whether the account doesn't exist or the password is wrong - a different message for each would let this endpoint be used to enumerate which emails have accounts.

**lines 316-318**
hashed_password is None for OAuth-only accounts - correct behaviour here is the same generic refusal, not "use Google instead", which would also leak account existence.

**lines 333-351**
--------------------------------------------------------------- OAuth (Google / Microsoft)

Both follow the same shape: /login redirects the browser to the provider's consent screen, /callback is where the provider sends the browser back with an authorization code. authorize_access_token exchanges that code for tokens AND verifies them (signature, issuer, audience) - by the time userinfo is read here, Authlib has already done that verification; this code only has to trust the claims, not re-derive their validity.

The callback ends by redirecting to the frontend's own /login route with the freshly issued JWT as a query parameter - the frontend (task: Login.jsx) reads it from the URL once, stores it in sessionStorage exactly as a form login would, and strips it from the address bar. The backend never sets a cookie for the actual logged-in session; the JWT is the only credential, same as the email/password path. ---------------------------------------------------------------

**lines 447-460**
The React build (webapp/frontend/, built via `npm run build`) emits its bundled JS/CSS under webapp/static/assets - Vite's default asset base path is "/", so this has to be mounted at "/assets" to match what the built HTML actually references. "/static" is kept too for anything that ever needs the raw directory (e.g. favicon), same mount point as before this rewrite.

check_dir=False on both: webapp/static (and its assets/ subfolder) is now a BUILD ARTIFACT, not something committed to git (see .gitignore) - it only exists after `npm run build` has run. Without this, importing this module before that build step (e.g. a test suite run on a fresh checkout) would crash at import time with "directory does not exist" instead of failing only the requests that actually need the built files.

## `webapp/dashboard_data.py`

**lines 3-7**
Only these node types can ever carry a responsibility directly (see schema.Node) - chapter/process nodes are organizational, always empty. Used for the two new "how complete is this DAM's coverage" KPIs below, so the denominator is real answerable nodes, not the full node count.

## `webapp/db.py`

**lines 31-32**
SQLite needs this flag to allow use across FastAPI's threadpool; Postgres doesn't use (or accept) it, so it's added conditionally.

**line 52**
noqa: F401 - import registers models on Base

## `webapp/models.py`

**lines 37-38**
A given provider account (e.g. this exact Google user) can only ever be linked to one row here.

**lines 48-49**
"google" | "microsoft" | None provider's stable subject/user id

## `webapp/frontend/src/api.js`

**above `const TOKEN_KEY`**
Token lives in sessionStorage, not localStorage - a deliberate choice (see docs/decisions.md and Chapter 5): closing the tab loses the session, but a token in localStorage would survive indefinitely and be readable by any script that ever runs on the page. Kept under one key so every page (Chat, Dashboard, Login) reads/writes the same slot.

**above `authFetch`**
Wraps fetch with the Authorization header and one shared rule: a 401 means the token is missing, expired, or otherwise invalid, and there is nothing a page can usefully do with that response except send the user back to sign in again - so that redirect happens once, here, instead of being re-implemented in every page that calls a protected endpoint.

**inside `authFetch`, on the 401 branch's returned promise**
Never resolves meaningfully - the redirect above is already navigating away, so callers don't need (and won't get) a response to handle.

**in `askQuestion`, on `target_language`**
"auto" (the default) tells the backend to keep detecting the answer language from the question itself - anything else is an explicit override from the language picker (see LanguagePicker.jsx, docs/decisions.md 2026-09-03).

**above `signup`/`login`**
signup()/login() deliberately use plain fetch, not authFetch - there is no token yet to attach, and a 401 here (wrong password) is a normal, expected response the Login page needs to read and display, not a signal to redirect away from the login page itself.

## `webapp/frontend/src/pages/Login.jsx`

**in `useEffect`, above the token/redirect check**
Two ways a visitor can land here already carrying a token: (1) an OAuth callback (Google/Microsoft) redirected back with `?token=...` in the URL - webapp/backend.py's google_callback/microsoft_callback do exactly this; (2) they're already logged in from an earlier visit this tab and just navigated back to /login by mistake or via a stale link. Either way, the outcome is the same: store the token (if new) and go straight to the chat page instead of showing the form.

## `webapp/frontend/src/pages/Chat.jsx`

**in `MessageBubble`, above `answeredInOtherLanguage`**
The answer actually came back in a non-English language only when the LLM phrasing step both ran AND succeeded - answerLanguage alone just reflects what was *requested* (see webapp/backend.py, docs/decisions.md 2026-09-03), so a failed/unavailable LLM still correctly shows the fallback warning below instead of falsely claiming success.

**above `const [uiLanguage, setUiLanguage]`**
The language picker's own selection - 'auto' (default) keeps the existing per-question auto-detect behavior; anything else is an explicit override sent to the backend as target_language (see api.js, webapp/backend.py, docs/decisions.md 2026-09-03). Also drives which UI_STRINGS dictionary the surrounding chrome (send button, placeholder, meta labels) renders in.

**in the login-guard `useEffect`**
Fast, client-side check only - a missing token means definitely logged out, so there's no reason to wait for a failed API call before redirecting. An expired-but-present token still gets caught the normal way: the first real request 401s and api.js's authFetch() redirects from there instead.

**in `handleSubmit`, on `targetId`**
Captured up front, not read again after the await - if the user switches conversations while a request is in flight, the answer still lands in the conversation that actually asked the question, not whatever happens to be on screen when it resolves.

**in `handleSubmit`, on `previousNodeId`**
The most recent node_id this conversation resolved to, if any - sent along so a pronoun-style follow-up ("who are the informed parties for THAT ACTIVITY?") has a real anchor instead of the backend guessing off incidental word overlap (see agent/qa.py's answer_question, docs/decisions.md 2026-08-06). Read from activeConversation.messages BEFORE appendMessage below adds this new question, same reasoning as capturing targetId.

Note: the `// eslint-disable-next-line react-hooks/exhaustive-deps` line above the empty-dependency `useEffect` in `MessageBubble` was kept in place rather than moved here - it's a functional lint directive, not documentation.

## `webapp/frontend/src/pages/Dashboard.jsx`

**in the login-guard `useEffect`**
Same fast client-side check as Chat.jsx - a missing token is definitely logged out, no need to wait on a round trip. This page is also administrator-only server-side (require_admin in webapp/backend.py); a logged-in analyst still gets redirected, just via the 403 that getDashboardSummary() below turns into `error`, not this check.

**above `const scope = useMemo(...)`**
The chapter filter re-scopes every card and chart on the page - "all" is the whole-DAM data already flattened at the top level of the response (see webapp/dashboard_data.py), any other value looks up that chapter's own breakdown instead. Graph structure (total_graph_nodes/total_edges) deliberately stays whole-DAM-only regardless of this filter - role/reference edges routinely cross chapter boundaries, so a "chapter subgraph" would need its own, more complex semantics that aren't worth it for what this dashboard needs (see the backend docstring for the full reasoning).

**above `handleChapterChange`**
An action selected under one chapter's breakdown may not exist at all under another (or under "all") - clearing it on every chapter change avoids pointing the roles chart at stale, chapter-specific data that no longer matches what's on screen.

**in the action-distribution chart's `onClick`, on the `'other'` guard**
"other" is a rollup of everything past the top 10, not a real action code - nothing in roles_by_action to look it up against.
