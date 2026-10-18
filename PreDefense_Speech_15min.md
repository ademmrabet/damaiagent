# Pre-defense speech: DAM AI Agent (14.5 minutes, one 5-minute demo)

About 1,300 spoken words plus the 5-minute demo. Do not memorize it word for word: learn the **bold key sentence** of each slide and say the rest in your own words. Words in [brackets] are stage directions. Total timing: 6:25 of slides, 5:00 demo, 3:00 evaluation, deployment and conclusion, which leaves a 30-second buffer under the 15-minute limit.

---

## Slide 1: Title (0:00 to 0:40)

Good morning, everyone. My name is Adem Mrabet, and I am a student at Polytech International.

Imagine you are a new employee at the African Development Bank. You need to know who has to approve a mission program. The answer sits in a document of 79 pages. Now imagine you type your question, and two seconds later you get the answer, with its source.

**That is what I built during my internship: an AI agent that turns the Bank's Delegation of Authority Matrix into instant, trustworthy answers.**

I will follow the six phases of CRISP-DM, and you will see the product live. Let's start with the problem.

---

## Slide 2: The problem (0:40 to 1:30)

The Delegation of Authority Matrix, or DAM, says for every task who initiates it, who approves it, who checks it, and who must be informed.

[Point to the three cards.]

The questions are simple, but the answers are buried in a dense 79-page table. People scroll, follow footnotes, and ask colleagues, who sometimes guess. And a wrong answer has a price: if someone thinks they can approve something and they cannot, that is a governance and compliance risk.

You may think: why not ChatGPT? **Because a generic chatbot invents roles that sound right.** In a bank, "sounds right" is not good enough. So the challenge was to build an assistant that never says something the document does not say.

---

## Slide 3: Objectives (1:30 to 2:05)

Three goals. Precise: every answer traces back to a task in the matrix. Instant: natural language, typos, and four languages, French, Spanish, Portuguese and Arabic. Trusted: if the question is outside the document, the agent says so.

**Success means the right role, the right level, the right footnote.** Not a demo that sounds smart, but an assistant a Bank employee can rely on.

---

## Slide 4: Data understanding (2:05 to 2:55)

The matrix is a PDF. After parsing, it contains 327 nodes: chapters, processes, tasks, child tasks and threshold variants. Add the 132 distinct roles, and the graph has 459 vertices and 2,108 relationships.

It was harder than it looks. In the PDF, a footnote is a small superscript next to a level number. Extract the text normally and the footnote "1" next to the level "2" becomes "21". Nothing warns you. Rows are also split across pages, and tasks point to each other, like "see 1.117.2".

**Dirty data in, wrong answer out.** Most of the real work was on the data, not on the AI model.

---

## Slide 5: Data preparation (2:55 to 4:10)

Four steps turn the PDF into a clean knowledge base.

One: I read characters, not words. The library pdfplumber gives the size and position of every character, so I can tell a footnote from a level.

Two: I rebuild the rows and group them into one block per task.

Three: every task is validated with Pydantic, a typed contract between the parser and the rest of the system. Wrong data fails loudly.

Four: I cache the result. On the free hosting tier, parsing the PDF at every start ran out of memory, so I parse once at build time.

**Each tool was chosen for one reason, not because it was popular.**

---

## Slide 6: Modeling, the graph and retrieval (4:10 to 5:25)

The nodes and roles are stored in a graph with NetworkX. A role is linked to a task, and the link carries the action code and the level. One role can act on a task in several ways, so I use a multi-graph with parallel links.

A question has three possible outcomes. [Point to the cards.]

Exact: an id like 2.126 is resolved with certainty.

Semantic: if you describe the task, TF-IDF finds it. I chose it over embeddings because titles are short and keyword-rich, it needs no GPU and no labelled data, and I can explain every score.

Honest: if the id does not exist, the agent says so.

Typos are corrected by a deterministic method, so it works offline.

---

## Slide 7: Modeling, grounded AI (5:25 to 6:25)

**This slide answers: why should we trust it?**

The language model never reads the whole document. It receives only the facts of the retrieved task, with a strict prompt and a low temperature: it may rephrase, it may not add a role.

Then a grounding check compares the answer with the facts. If an expected role is missing, I discard the answer and return a deterministic template. So the user always gets a correct answer, even if the model is down.

One honest limit: the check verifies that required roles are present. It does not yet detect an added role. That is my first improvement.

The system is hybrid: Groq in the cloud by default, Ollama locally when data must not leave the machine.

---

## Slide 8: Live demo (6:25 to 11:25)

Let me show you the product. [Play the 5-minute demo and speak over it. The full text and timing are in video_repo/DEMO_SPEECH.md and in these notes.]

---

## Slide 9: Evaluation (11:25 to 12:55)

How do I know it works? I have 137 automated tests covering the parser, the graph, the agent, authentication and the API.

But I will be clear: **137 tests measure code quality, not answer accuracy.**

What taught me the most were real bugs found by testing real questions. [Point to the table, pick two.] An invalid code was matching an unrelated task, and now it returns an explicit invalid-id result. Questions about action codes were swallowed by my follow-up logic, so I now check the intent first. Every bug became a regression test.

The next step is a benchmark: questions with expected roles, to give a precision figure.

---

## Slide 10: Deployment (12:55 to 13:40)

Everything is containerized with Docker. In the cloud: FastAPI, React, Postgres on Neon, and S3-compatible file storage. Security: hashed passwords, tokens, rate-limited login, Google and Microsoft sign-in.

One honest remark: rate limiting and live notifications work per process today. For several servers, I would move them to Redis.

---

## Slide 11: Conclusion (13:40 to 14:25)

What did the Bank get? A live, tested product in four languages. What is missing? A precision benchmark and a stronger grounding check. What comes next? Other Bank matrices, and a scalable setup.

**Seconds instead of minutes. Sources instead of guesses.**

Thank you for your attention. I am happy to answer your questions.

---

## If the jury asks (short answers)

- **Why not embeddings?** Short keyword-rich titles, no labelled data, no GPU, and TF-IDF scores are explainable. With a larger corpus, I would test embeddings.
- **How do you know it does not hallucinate?** Facts come from the graph, the prompt forbids additions, a grounding check rejects missing roles, and a deterministic fallback exists. The limit: added roles are not yet detected.
- **What is your accuracy?** I have no precision figure yet. I have 137 tests and live-checked questions. The benchmark is the next step.
- **Why a graph and not a database?** Relations like "see 1.117.2" and parallel role-task links. 459 vertices is small, so in-memory is enough and needs no extra infrastructure.
- **Is the data safe?** Local mode with Ollama keeps data on the machine. In cloud mode, only the retrieved facts and the question go to the LLM, not the full document.
- **What was the hardest part?** The parsing: telling footnotes from levels, and rebuilding split rows.

## Delivery tips

- Rehearse out loud three times with a timer. Aim for 14:00.
- Look at the jury, not the screen. The slides carry only cues.
- During the demo, talk over the video. Never let it play in silence.
- Keep the live app open in a second tab as a backup.
- If you run late, cut slide 10 to two sentences. Never cut the demo or the evaluation.
