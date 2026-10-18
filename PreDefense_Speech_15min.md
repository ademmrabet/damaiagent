# Pre-defense speech: DAM AI Agent (14 minutes)

About 1,800 spoken words at a calm pace. Do not memorize it word for word: learn the **bold key sentence** of each slide and say the rest in your own words. Words in [brackets] are stage directions.

---

## Slide 1: Title (0:00 to 0:45)

Good morning, everyone. My name is Adem Mrabet, and I am a student at Polytech International.

Imagine you are a new employee at the African Development Bank. You need to know who has to approve a mission program. The answer exists, but it sits in a document of 79 pages. Now imagine you type your question, and two seconds later you get the answer, with its source.

**That is what I built during my internship, from April to October: an AI agent that turns the Bank's Delegation of Authority Matrix into instant, trustworthy answers.**

I will walk you through the project following the six phases of CRISP-DM, and you will see the product live twice. Let's start with the problem.

---

## Slide 2: The problem (0:45 to 1:45)

The document is called the Delegation of Authority Matrix, or DAM. For every task in the Bank, it says who initiates it, who approves it, who checks it, and who must be informed.

[Point to the three cards, one at a time.]

First, the questions are simple: who approves? who checks? who is informed? But the answers are buried in a dense 79-page table.

Second, this costs time. People scroll, follow footnotes, and ask colleagues, who sometimes guess.

Third, and this is the important one, a wrong answer has a price. If someone thinks they have the authority to approve something and they do not, that is a governance and compliance risk.

You may think: why not use ChatGPT? **Because a generic chatbot invents roles that sound right.** In a bank, "sounds right" is not good enough. So the real challenge was not building a chatbot. It was building an assistant that never says something the document does not say.

---

## Slide 3: Objectives (1:45 to 2:30)

I translated this into three goals.

One: precise. Every answer must trace back to a specific task in the matrix. No source, no answer.

Two: instant. You can ask in natural language, you can make typos, and you can write in French, Spanish, Portuguese or Arabic.

Three: trusted. If the question is outside the document, the agent says so honestly.

**My definition of success is simple: the right role, the right level, the right footnote.** Not a demo that sounds smart, but an assistant a Bank employee can rely on.

---

## Slide 4: Data understanding (2:30 to 3:30)

Now the data. The matrix is a PDF. After parsing, it contains 327 nodes: 3 chapters, 35 processes, 138 tasks, 102 child tasks and 49 threshold variants. Add the 132 distinct roles and the graph has 459 vertices and 2,108 relationships, with action codes such as Initiate, Check and Verify, Review, Approve and Informed.

It was harder than it looks. Let me give you one example. In the PDF, a footnote number is printed as a small superscript next to a level number. When you extract the text normally, the footnote "1" next to the level "2" becomes "21". The text is wrong, and nothing warns you.

Also, rows are split across pages, merged cells hide roles, and tasks point to each other, for example "see 1.117.2".

**Dirty data in, wrong answer out.** So most of the real work of this project was on the data, not on the AI model.

---

## Slide 5: Data preparation (3:30 to 5:00)

Here is how I turned the PDF into a clean knowledge base, in four steps.

Step one: I read characters, not words. The library pdfplumber gives me the size and position of every character, so I can tell a footnote from a level.

Step two: I rebuild the rows and group them into one block per task, which fixes the split and merged rows.

Step three: every task is validated with Pydantic. It is a typed contract between the parser and the rest of the system. If the data is wrong, it fails loudly instead of silently.

Step four: I save the result as a cached file. Why? Because during deployment on the free hosting tier, parsing the PDF at every start ran out of memory. I parsed once at build time, and the problem disappeared.

**Each tool was chosen for one reason, not because it was popular.**

---

## Slide 6: Modeling, the graph and retrieval (5:00 to 6:30)

Now the modeling. The 327 nodes and 132 roles are stored in a graph, using NetworkX. A task is connected to the roles that act on it, and the connection says how: responsible, level, action code. One role can act on one task in several ways, so I use a multi-graph that allows parallel links.

When a question arrives, there are three possible outcomes. [Point to the three cards.]

Exact: if you type an id like 2.126, it is resolved with certainty.

Semantic: if you describe the task, I use TF-IDF to find it. I chose it over embeddings for three reasons: titles are short and keyword-rich, it needs no GPU and no labelled data, and I can explain every score.

Honest: if the id does not exist, the agent says so, instead of guessing.

Typos are corrected with a deterministic method based on string similarity, so it also works offline.

---

## Slide 7: Modeling, grounded AI (6:30 to 7:30)

**This is the slide that answers: why should we trust it?**

The language model never reads the whole document. It receives only the facts of the task that was retrieved. Its prompt is strict, with a low temperature: it may rephrase, it may not add a role.

Then a grounding check compares the answer with the facts. If an expected role is missing, I throw the answer away and return a deterministic template answer instead. So the user always gets a correct answer, even if the language model is down.

I want to be honest about one limit: today, the check verifies that the required roles are present. It does not yet detect an extra role that was added. That is my first improvement.

The system is hybrid: Groq in the cloud by default, and Ollama locally for cases where data must not leave the machine.

---

## Slide 8: Demo 1 (7:30 to 9:00)

Let me show you the agent. [Start the video, speak over it.]

I ask "who approves 2.126". The id is resolved, and the answer names the approver. Look at this: it also tells me who must check and verify the task, and who must be informed. In the matrix, these steps are mandatory, so the agent always shows them, even if I only asked about the approver.

Now the same task from a plain description. Same result.

Now with two typos in my question. Same correct answer.

Now in French. The answer is in French, and the whole interface switches language.

And now an id that does not exist. The agent refuses clearly. [Pause.] **This refusal is a feature, not a failure.**

---

## Slide 9: Demo 2, the platform (9:00 to 10:30)

The project is more than a question box. [Start the video.]

Users sign in, and their conversations are saved. They can share a conversation with a colleague through a QR code, with live notifications. They can speak their question and hear the answer. They can upload a document and ask about it. And there is a dashboard that shows the matrix at a glance, by chapter and by action code, where each chart is clickable to filter the roles.

Authentication uses hashed passwords and tokens, with rate limiting on login, and Google and Microsoft sign-in.

---

## Slide 10: Evaluation (10:30 to 12:00)

Now, evaluation. I have 137 automated tests covering the parser, the graph, the agent, authentication and the API.

But I will be clear: **137 tests measure code quality, not answer accuracy.**

What taught me the most were real bugs, found by testing real questions. [Point to the table, pick two.]

For example, an invalid code was matching an unrelated task. Now it returns an explicit "invalid id" result. Another: questions about action codes were swallowed by my follow-up logic, so I now check the intent first. And as I said, the free hosting ran out of memory, so I cached the parsed data. Every bug became a regression test.

The next step is a benchmark: a set of questions with the expected roles, to give you a precision figure. I already know how to build it, and it is the first thing I would do next.

---

## Slide 11: Deployment (12:00 to 13:00)

For deployment, everything is containerized with Docker: one command starts the application, the frontend and the local model.

In the cloud, the backend is FastAPI, the frontend is React, the database is Postgres on Neon, and files are stored on S3-compatible storage.

Security: hashed passwords, tokens, rate-limited login, admin-only routes.

And the interface adapts to the language the user types in.

One honest remark: rate limiting and live notifications work per process today. For several servers, I would move them to Redis.

---

## Slide 12: Conclusion (13:00 to 14:00)

To conclude. What did the Bank get? A live product, tested, in four languages. What is missing? A precision benchmark and a stronger grounding check. What comes next? Other Bank matrices, and a scalable setup.

**Seconds instead of minutes. Sources instead of guesses.**

Thank you for your attention. I am happy to answer your questions.

---

## If the jury asks (short answers)

- **Why not embeddings?** Short keyword-rich titles, no labelled data, no GPU, and TF-IDF scores are explainable. With a larger corpus, I would test embeddings.
- **How do you know it does not hallucinate?** Facts come from the graph, the prompt forbids additions, a grounding check rejects missing roles, and a deterministic fallback exists. The limit: extra roles are not yet detected.
- **What is your accuracy?** I have no precision figure yet. I have 137 tests and live-checked questions. The benchmark is the next step.
- **Why a graph and not a database?** Relations like "see 1.117.2" and parallel role-task links. 459 vertices is small, so in-memory is enough and needs no extra infrastructure.
- **Is the data safe?** Local mode with Ollama keeps data on the machine. In cloud mode, only the retrieved facts and the question go to the LLM, not the full document.
- **What was the hardest part?** The parsing: telling footnotes from levels, and rebuilding split rows.

## Delivery tips

- Rehearse out loud three times with a timer. Aim for 13:30 so you have a buffer.
- Look at the jury, not the screen. The slides carry only cues.
- During the demos, talk over the video. Never let it play in silence.
- Have the live app open as a backup in case a video fails.
- If you run late, cut slide 11 to two sentences. Never cut the demos or the evaluation.
