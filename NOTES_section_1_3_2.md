# Section 1.3.2 — Study of Existing Systems
## Working notes. Write the prose yourself from these.

Target: ~3 pages. Four subsections + one table.

---

## Before you start — three things that make this fast

1. **Write ugly first.** Get every point down as a bad sentence, fix later. The
   blank page is the expensive part, not the editing.
2. **One idea per paragraph.** If a paragraph has two, split it.
3. **Say the point, then the evidence.** Not the other way round. Academic
   writing that builds to a conclusion is harder to read and harder to write.

Read your own notes below, close this file, then write. If you write with the
notes open you'll end up copying phrasing instead of thinking.

---

## 1.3.2.0 — Opening paragraph (3–4 sentences)

Job: tell the reader why this section exists at all.

- Four categories of tool exist that could be aimed at this
- None works
- But: each fails for a *different, specific* reason
- Those reasons → become the requirements in 1.4 → become the design in 1.5
- Point to make: the section isn't a survey, it's where the spec comes from

---

## 1.3.2.1 — Manual consultation and document search

Length: 2 short paragraphs.

**Para 1 — what people do now**
- Open PDF → Ctrl+F → that's it
- Full-text search = character string matching
- Works if you know: exact activity title OR the identifier
- Fails otherwise
- Concrete: search "approve" → hundreds of hits, page order, no relevance ranking
- Concrete: half-remembered activity name → zero results unless wording matches printed wording exactly

**Para 2 — the deeper failure (this is the real point)**
- Search returns a *location*. User needs an *answer*.
- Example to use: it tells you the phrase is on page 24
- It cannot say who approves that activity
- Why not → would require knowing: (a) page contains a table, (b) headers rotated,
  (c) a letter in a cell = a specific role's authority
- None of that is in a string match

**The turn:** distinction between finding and answering. Land it plainly.

---

## 1.3.2.2 — Generic document question-answering assistants

Length: 2–3 paragraphs.

**Para 1 — what they are and how they work**
- Category: upload PDF, ask in plain language, get an answer
- Named examples: ChatPDF, NotebookLM, Microsoft Copilot, file-upload modes of
  the major chat assistants
- Mechanism (state it accurately, you'll be asked):
  document → split into passages → embed each as a vector →
  retrieve passages nearest the question → language model writes from those
- This is standard RAG. Say so; the term will be expected.

**Para 2 — why it fails here**
- Works fine on prose
- Fails on the DAM — and the reason is *structural*, not model quality
  (important: don't let a reader think a better model would fix it)
- Mechanism of failure: flatten page → plain text → spatial relationships destroyed
- The rotated header that identified a column → becomes a loose string, attached to nothing
- Result: retrieved passage can contain the activity name AND the letter A,
  while having lost which column the A was in
- So the answer is gone *before* the model sees anything
- Model then produces something plausible from what remains

**Do this — highest value 15 minutes you have:**
- Upload 2–3 DAM pages to ChatPDF or NotebookLM
- Ask: "who approves 2.126"
- Screenshot whatever comes back
- If it's wrong or vague → that screenshot turns this subsection from argument
  into evidence, and it's the kind of thing a jury remembers
- Add as a figure, reference it in this paragraph

---

## 1.3.2.3 — Commercial document-extraction services

Length: 2 paragraphs.

**Para 1 — what they are**
- Different category: they don't answer questions, they extract structure
- Named: Azure Document Intelligence, AWS Textract, Google Document AI, LlamaParse
- Be fair to them: markedly better at tables than a general-purpose library
- These are the *serious* alternative to hand-written extraction rules —
  say so, it strengthens you rather than weakens you

**Para 2 — three reasons ruled out**
1. Cost + confidentiality: priced per page, and requires sending an internal
   governance document to a third party. That's an institutional decision, not
   a student's.
2. Fit: tuned for invoices, receipts, contracts, forms. Not for a bespoke
   authority matrix with rotated headers and superscript-qualified codes.
3. **Explainability — the one that actually decided it:** when they get a cell
   wrong, there's no account of why. Compare: a rule derived from a measured
   character offset can be checked against the page that motivated it. A
   confidence score can't be.

Reason 3 is your strongest and connects to your whole thesis. Give it the most room.

---

## 1.3.2.4 — Critical analysis: limitations

Length: 2–3 paragraphs + the table.

**Para 1 — the shared shape of the failures**
- None fail from poor engineering
- Each fails on an *assumption* that doesn't hold here:
  - Search assumes → user can phrase it in the document's vocabulary
  - Assistants assume → flattening preserves meaning (false for positional tables)
  - Extraction services assume → document resembles their training forms
  - GRC platforms (4th category) assume → institution will re-enter its rules
    into their data model = change programme, not a tool

**Para 2 — the one they all share (put weight here)**
- None has any concept of being wrong
- Search returns results. Model returns text. Neither distinguishes
  "answer I can support" from "answer I can't"
- For a compliance reference that distinction is the whole point
- This is the gap your system is built in

**Para 3 — hand off to the table, then to 1.5**

---

## Table — verify each cell yourself before using

Suggested columns: Search · Assistants · Extraction · GRC · This work

| Requirement | Notes for you |
|---|---|
| Preserves positional table meaning | be honest about "Partly" for extraction services |
| Answers a question vs returns a location | |
| Answer traceable to a source row | |
| Refuses when it cannot answer | some cells are N/A, not No |
| Surfaces mandatory obligations | your FR4 |
| Tolerates typos / loose phrasing | |
| Document stays inside the institution | |
| No per-page or licence cost | |
| Deployable within this project's constraints | |

Don't mark a competitor "No" on something you haven't checked. Use N/A or
"Partly" and you'll be on safe ground if asked.

**Closing move:** read down your own column. That list *is* your specification.
Say that, then point forward to 1.5.

---

## Facts you can cite (verified)

- Extraction services landscape: Azure Document Intelligence, AWS Textract,
  Google Document AI are the established platforms; LlamaParse and similar
  layout-aware parsers are the newer entrants and now compete on complex layouts
- These services are priced per page
- They ship prebuilt models for invoices, receipts, IDs, tax forms, contracts
- Generic assistants use passage-splitting + embedding + retrieval (RAG)

## Your own numbers, for cross-reference

- DAM: 250+ pages total, 79-page subset processed
- 327 records, 1,776 responsibility entries, 131 roles
- 0.56% unresolved role rate
- Graph: 459 nodes, 2,108 edges
- 374 tests across 23 files
