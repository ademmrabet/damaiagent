# Demo script: what to do and what to say, exactly

Two demos of about 50 seconds each (slides 8 and 9). Speak over the video live. The questions below come from `docs/demo_script.md`, where each was run against the real build. The French and upload questions are the exceptions: test them first (see "Before you start").

Format: **DO** = what appears on screen, **SAY** = what you say, word for word.

---

## Before you start (do this the day before)

1. Open the hosted app 5 minutes early so the free tier is awake. Log in with a test account. LLM mode: **Auto**.
2. Ask every question below once, and check the answer matches what is described here. If an answer differs, adapt the SAY line, never read a line that contradicts the screen.
3. Test the French question. If the answer is wrong, replace it with another French wording of "who approves 2.126": `qui approuve 2.126`.
4. Prepare a short test PDF or Word file (one page, no confidential content) for the upload shot.
5. Keep the live app open in a second tab as a backup.

---

## DEMO 1: the core agent (slide 8, about 50 s)

| # | DO | SAY |
|---|----|-----|
| 1 | Type `who approves 2.126`, press Enter | "I ask who approves task 2.126." |
| 2 | Answer appears. Point the cursor at the approver, then at the Check/Verify and informed lines | "It names the approver. But look: it also tells me who must check and verify, and who must be informed. In the matrix those steps are mandatory, so the agent always shows them." |
| 3 | Type `who needs to be informed for quarterly mission program` | "Now I do not give any id. I just describe the task." |
| 4 | Answer appears for the same task 2.126 | "Same task, found from its name." |
| 5 | Type `who aproves the qaurterly mision program` | "Now with two typos." |
| 6 | Same correct answer appears | "Same correct answer. The correction is deterministic, and it works offline." |
| 7 | Type the French question, show the language badge and the interface changing | "And in French: the answer comes in French, and the whole interface follows." |
| 8 | Type `what happens with 9.999.999` | "Last one: an id that does not exist." |
| 9 | Refusal appears. Pause two seconds | "The agent refuses. It does not guess. This refusal is a feature, not a failure." |

Bridge to the next slide: "So that is the agent. Now let's see the platform around it."

---

## DEMO 2: the platform (slide 9, about 50 s)

| # | DO | SAY |
|---|----|-----|
| 1 | Show the login screen, sign in | "Users sign in, with email or with Google or Microsoft." |
| 2 | Show the saved conversations in the sidebar | "Every conversation is saved to the user's account." |
| 3 | Click Share, QR code appears | "I can share a conversation with a colleague through a QR code, and they are notified live." |
| 4 | Click the mic, ask a question aloud, then click speak-aloud on the answer | "I can ask by voice, and have the answer read back to me." |
| 5 | Attach the test file, ask a question about it | "I can upload a document and ask questions about it." |
| 6 | Open the Dashboard, pick a chapter | "And the dashboard gives a view of the whole matrix. I filter by chapter..." |
| 7 | Click a bar in the action-code chart, roles update | "...and clicking an action code shows who performs it most." |

Bridge to the next slide: "Now, how do I know it works? Let's talk about evaluation."

---

## If you demo live instead of the video (backup order)

Use this if the video fails or the jury asks you to try a question.

1. `hi` (shows personality, a warm reply, not a search box)
2. `who approves 2.126`
3. `who approves of Communication with Co-Financiers of projects`, then without naming the subject: `and who are the informed parties?` Say: "It remembers what we were talking about, like a person would."
4. `who initiates 1.117.2` Say: "This task only contains a pointer, 'see 2.120'. The agent follows it for me, like flipping to another page in the paper matrix."
5. `what does RDNG stand for` Say: "It answers, and it tells me this one comes from a maintained alias, not from the Bank's printed glossary. It is honest about its sources."
6. `what happens with 9.999.999`

---

## If something goes wrong

| Problem | What to say and do |
|---------|--------------------|
| The video does not play | "Let me show you live instead." Switch to the live tab and run steps 2, 3 and 6 of the backup order. |
| The answer is slow (free tier waking up) | "The hosted version sleeps when unused, so it needs a moment to wake. This is a free-tier limit, not an architecture limit." Keep talking about the next feature. |
| The LLM is down and the answer looks plain | "The LLM is unavailable, so the agent falls back to the structured template answer. The user still gets a correct answer. That is the design." (This is a good moment, not a bad one.) |
| A jury member gives their own question | "Good question, let me try it." Type it. If the agent refuses, say: "It refuses when the document does not contain it. That is what I want." |
| You forget your words | Say what you see: "Here the agent names the approver, and here the people who must check and be informed." |

---

## Timing check

- Demo 1: 9 steps, about 50 s. Cut steps 3 and 4 if you need 35 s.
- Demo 2: 7 steps, about 50 s. Cut step 2 if you need to save time.
- Never cut the refusal (Demo 1, step 8). It is the strongest 10 seconds of the demo.
