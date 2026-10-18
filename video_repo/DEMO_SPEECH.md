# One demo, 5 minutes: spoken text and actions

One continuous run, 5:00 maximum. Say the text in quotes, do the actions in [brackets]. Use a test account, the hosted app already awake, LLM mode Auto.

Product flow: the landing page shows two cards, **Chat** and **Dashboard**. Clicking either opens a **login page**, then you reach that page.

Total: about 560 spoken words. The app needs a few seconds to answer each question: keep talking while it loads, or use the pause.

---

## 0:00 to 0:35 Landing and login

[Landing page. Let the animation play two seconds.]

"This is the application. The landing page has two entry points: the Chat, where you ask questions, and the Dashboard, where you see the matrix at a glance."

[Click the Chat card. The login page appears.]

"Both are protected, because this tool is for Bank staff. I can sign in with email, or with Google, or Microsoft."

[Sign in. The chat opens.]

"I am in. Conversations are saved to my account, and the LLM mode is on Auto."

## 0:35 to 1:25 Exact question

[Type `who approves 2.126`, press Enter.]

"First question: who approves task 2.126?"

[Answer appears. Move the cursor over the approver, then over the Check/Verify and informed lines.]

"The agent names the approver. And look: it also tells me who must check and verify, and who must be informed. In the matrix, those steps are mandatory, so the agent shows them every time, even if I only asked about the approver. A new employee is never told half of the obligations."

## 1:25 to 2:00 Natural language

[Type `who needs to be informed for quarterly mission program`.]

"Now I do not give any id. I just describe the task."

[Answer appears.]

"Same task, found from its name. The agent understands what I describe, not only the codes I type."

## 2:00 to 2:30 Typos

[Type `who aproves the qaurterly mision program`.]

"Now with two typos."

[Answer appears.]

"Same correct answer. The correction is deterministic, based on the matrix's own vocabulary, so it works even offline."

## 2:30 to 3:05 French

[Type the French question. Show the language badge and the interface change.]

"And now in French. The answer comes in French, and the whole interface follows the language I write in. The role names are never translated, because they are official titles."

## 3:05 to 3:50 Follow-up and redirect

[Type `who approves of Communication with Co-Financiers of projects`. Then, without naming the subject: `and who are the informed parties?`]

"I ask about another task, and then I ask a follow-up without repeating the subject. The agent remembers what we were talking about, like a person would."

[Type `who initiates 1.117.2`.]

"This task contains only a pointer: 'see 2.120'. The agent follows the reference for me, like flipping to another page in the paper matrix."

## 3:50 to 4:10 Honest refusal

[Type `what happens with 9.999.999`. Pause two seconds on the refusal.]

"Last question: an id that does not exist. The agent refuses. It does not guess. This refusal is a feature, not a failure: every real answer must come from a real row of the matrix."

## 4:10 to 4:35 Sharing and voice

[Click Share, show the QR code. Close it. Click the mic, ask a short question, then click speak-aloud on the answer.]

"The platform is built for a team. I can share a conversation with a colleague through a QR code, and they are notified live. I can also ask by voice and hear the answer."

## 4:35 to 5:00 Dashboard

[Go back to the landing page, click the Dashboard card. If login appears again, sign in. Pick a chapter, then click an action bar.]

"Back to the landing page, now the Dashboard, with the same protection. I filter by chapter, and I click an action code to see which roles perform it most. That is the whole matrix at a glance."

Bridge: "So we have a working product. How do I know it is correct? Let's look at the evaluation."

---

## Cutting and safety

- Over 5:00? Cut the follow-up and redirect part (3:05 to 3:50), then voice. Never cut: login, the Check/Verify remark, the refusal, the Dashboard.
- Under 4:30? Add the upload of a short Word file (ask a question about it) after the voice step.
- Login appears again on the Dashboard click? Sign in. If it does not, say: "I am still signed in, so it opens directly."
- Video fails: "Let me show it live." Switch to the live tab and follow the same order.
- Slow first answer (free tier waking): "The hosted version sleeps when unused. This is a free-tier limit, not an architecture limit."
- LLM down, plain answer: "The language model is unavailable, so the agent returns the structured answer. The user still gets a correct answer. That is the design."
- Test the French question and any question you have not run before. If an answer differs from what is described, adapt your words to what is on screen.
