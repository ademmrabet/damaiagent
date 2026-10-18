# Where is everything? Code map for the jury Q&A

Project root: `damaiagent/`. All numbers below were measured on the real data.

## 1. The big picture in one sentence

PDF (`data/raw/updated dam file.pdf`, 79 pages) -> parsed into **nodes** (`data/processed/nodes.json`) -> loaded in memory as a **knowledge graph** at server start -> a question is **resolved** to a node -> the **answer** is built from the graph -> optionally **rephrased** by the LLM and checked.

## 2. Folder by folder

| Folder / file | What it does | Say it like this |
|---|---|---|
| `data/raw/` | The original DAM PDF | "The only source of truth." |
| `extraction/` (`pdf_loader.py`, `table_extractor.py`) | Opens the PDF, pulls characters and table rows with pdfplumber | "Stage 1: raw characters with position and font size." |
| `parsing/` (`rows.py`, `task_blocks.py`, `hierarchy.py`, `column_roles.py`, `action_geometry.py`, `text_cleaning.py`, `metadata.py`, `glossary.py`) | Rebuilds rows, groups them into task blocks, finds the hierarchy, reads which column an action letter sits in, cleans text, extracts the abbreviations glossary | "Stage 2: turns messy geometry into structured tasks." |
| `schema/schema.py` | Pydantic models: `Node`, `Responsibility`, `AuthorityCode`, `Footnote` | "The data contract between parser and graph." |
| `modeling/build_nodes.py` | Builds the `Node` objects from the parsed PDF | "Stage 3: assembly and validation." |
| `modeling/nodes_cache.py` + `data/processed/nodes.json` | Saves and loads the nodes as JSON | "Parse once at build time. The server loads this file at startup." |
| `modeling/graph.py` | `build_graph(nodes)` creates the NetworkX graph; `responsible_roles()` and `tasks_for_role()` query it | "This is the knowledge graph." |
| `data/reference/` | `abbreviations.json` (glossary), `authority_codes.json` (meaning of A, C, R, I and levels) | "Reference data, stored separately from tasks so it cannot drift." |
| `knowledge/search.py` | TF-IDF index, id detection, `resolve_query()` | "Retrieval: exact id, text search, or invalid id." |
| `knowledge/typo_correct.py` | difflib typo correction | "Deterministic, offline." |
| `agent/qa.py` | `answer_question()`: the decision ladder, builds the structured answer | "The agent's brain. Rules, not an LLM." |
| `agent/generate.py` | `humanize_answer()`: LLM rephrasing + grounding check + fallback | "Where the LLM is allowed to speak, and where it is checked." |
| `agent/action_codes.py`, `authority.py`, `glossary.py`, `smalltalk.py` | Code legend questions, authority logic, acronym lookup, greetings | |
| `llm/` | `router.py` (chooses Groq / Ollama / none), `groq_provider.py`, `ollama_provider.py`, `translate.py`, `tone.py`, `transcribe.py` (Whisper), `attachments.py` (document Q&A) | "One interface, several engines." |
| `webapp/backend.py` | FastAPI app. Startup loads nodes, builds graph and search index into memory. Routes: `/api/ask`, `/api/auth/*`, `/api/conversations/*`, `/api/events` (SSE), `/api/uploads`, `/api/transcribe`, `/api/dashboard/summary`, `/api/health` | |
| `webapp/auth.py`, `oauth.py`, `models.py`, `db.py` | Passwords, JWT, Google and Microsoft sign-in, SQLAlchemy models, database connection | |
| `webapp/conversations.py`, `events.py`, `qr.py`, `storage.py`, `dashboard_data.py` | Saved chats and sharing, live notifications, QR code, S3 files, dashboard numbers | |
| `webapp/frontend/src/` | React app (pages Landing, Login, Chat, Dashboard; `i18n.js` for languages). Built into `webapp/static/` | |
| `tests/` | 137 tests (pytest) | |
| `docs/decisions.md` | Dated log of every design decision and why | "My engineering journal." |

## 3. What exactly is a "node"?

A **node** is one entry of the DAM: a chapter, a process, a task, a child task or a threshold variant. It is a `Node` object (`schema/schema.py`) with: `id` (for example `2.126`), `node_type`, `chapter`, `process_id`, `parent_task_id`, `children` (ids below it), `title`, `page`, `responsibilities` (list of role + action + level + footnotes), and `references` (other ids it points to).

Measured: **327 nodes** = 3 chapters + 35 processes + 138 tasks + 102 child tasks + 49 threshold variants.

Be careful with the numbers: 327 is the number of DAM nodes. **459 is the number of vertices in the graph**, because the graph also contains the **132 roles** (327 + 132 = 459). Do not say "459 tasks".

## 4. What exactly is the "knowledge graph"?

It is a NetworkX `MultiDiGraph` built in memory by `build_graph()` every time the server starts (it takes a moment, nothing is stored in a graph database). It has two kinds of vertices:

- `dam_node` vertices: the 327 DAM nodes
- `role` vertices: the 132 distinct roles (for example "Sector Manager")

and three kinds of edges, **2,108 in total**:

- `responsible_for` (1,776): role -> task, with the attributes `action` (A, C, R, I...), `level`, `footnote_refs`
- `contains` (322): parent -> child in the hierarchy
- `references` (10): task -> task, for "See 2.120" pointers

Why "Multi": one role can act on the same task in several ways (for example check and approve), so there can be several parallel edges between the same two vertices. Why "Di": direction matters (role acts on task).

Example: to answer "who approves 2.126", the agent looks at all `responsible_for` edges that point to vertex `2.126` and keeps the ones whose action starts with A.

## 5. The path of one question, step by step

1. Browser: React sends the question to `POST /api/ask` (`webapp/backend.py`).
2. If the text is not English, `llm/translate.py` translates it to English first.
3. `agent/qa.py` -> `answer_question()` runs the ladder: small talk, glossary, action-code legend, then `knowledge/search.py` -> `resolve_query()`:
   - an id in the text -> direct node (confidence 1.0)
   - an id that does not exist -> invalid id answer with suggestions
   - otherwise TF-IDF over node titles -> best match
4. With the node found, the agent asks the graph (`responsible_roles()`) for the roles, filters by intent (approve, check, inform...), and always adds the mandatory Check/Verify and informed notes.
5. `agent/generate.py` -> `humanize_answer()`: the LLM rephrases the facts; the grounding check verifies the required roles are present; otherwise the template answer is returned.
6. If needed, the answer is translated back, and the reply goes to the browser. The conversation is saved in Postgres.

## 6. Where is the data at runtime?

- The PDF is only read when you rebuild the cache. At runtime the server loads `data/processed/nodes.json` (327 nodes) into memory.
- The graph and the TF-IDF index live **in memory** (`state` dictionary in `backend.py`), rebuilt at each startup.
- Users, conversations and shares: Postgres on Neon (SQLite fallback locally).
- Uploaded files: S3-compatible object storage.

## 7. Likely jury questions on this part, with short answers

- **Why is the graph not in a database like Neo4j?** 459 vertices and 2,108 edges fit in memory, startup is fast, and a graph database would add infrastructure for no benefit at this size.
- **Why 327 nodes but 459 in the graph?** The graph adds 132 role vertices.
- **What is the difference between a task and a node?** Node is the generic type; a task is one `node_type`. A node can also be a chapter, process, child task or threshold variant.
- **What happens if the PDF changes?** Re-run the build (`build_nodes`), regenerate `nodes.json`, restart. The graph and index rebuild automatically.
- **Where do the action letters come from?** From the character geometry of the PDF (`action_geometry.py`, `column_roles.py`), and their meaning from `authority_codes.json`.
- **Is the graph persisted?** No, it is rebuilt from `nodes.json` at startup. The JSON is the persisted form.

## 8. Corrections I made to the earlier material

Earlier versions of the deck and speech said "459 tasks" and "hundreds of pages". The correct figures are **327 nodes, 132 roles, 459 graph vertices, 2,108 edges, 79 pages**. They are fixed in `DAM_PreDefense_FINAL_v2.pptx`, the speech and the 5-minute script.
