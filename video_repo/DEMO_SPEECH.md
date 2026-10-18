# Demo speech (spoken text, in order)

Flow of the product: the **landing page** shows two cards, **Chat** and **Dashboard**. Clicking either one opens a **login page**, and after signing in you reach that page. The speech follows this flow, so the login is shown as part of the story, not as a delay.

Say the text in quotes. Stage directions are in [brackets]. Test account only, no real credentials on screen.

---

## DEMO 1: landing, login, chat (slide 8, about 90 s)

[Landing page appears. Let the animation play for two seconds.]

"This is the landing page of the application. Two entry points: the Chat, where you ask questions, and the Dashboard, where you see the matrix at a glance."

[Click the Chat card. The login page appears.]

"Both are protected. When I click Chat, I am asked to sign in, because this tool is for Bank staff. I can use my email, or Google, or Microsoft."

[Sign in. The chat opens.]

"I am in. LLM mode is on Auto, and my conversations are saved to my account. Let's ask a first question."

[Type `who approves 2.126`, press Enter.]

"Who approves task 2.126?"

[Answer appears. Move the cursor over the approver, then the Check/Verify and informed lines.]

"The agent names the approver. And look: it also tells me who must check and verify, and who must be informed. In the matrix, those steps are mandatory, so the agent shows them every time, even if I only asked about the approver."

[Type `who needs to be informed for quarterly mission program`.]

"Now I do not give an id. I describe the task in words."

[Answer appears.]

"Same task, found from its name."

[Type `who aproves the qaurterly mision program`.]

"Now with two typos."

[Answer appears.]

"Same correct answer. The correction is deterministic, so it works even offline."

[Type the French question. Show the language badge.]

"And in French. The answer comes in French, and the interface follows."

[Type `what happens with 9.999.999`.]

"One last question, an id that does not exist."

[Refusal appears. Pause two seconds.]

"The agent refuses. It does not guess. This refusal is a feature, not a failure: every real answer must come from a real row of the matrix."

Bridge: "That is the agent. Now let's see the rest of the platform."

---

## DEMO 2: sharing, voice, upload, dashboard (slide 9, about 90 s)

[Still in the chat. Open the conversation sidebar.]

"Every conversation is saved in the sidebar, so a user can come back to it later."

[Click Share. The QR code appears.]

"I can share a conversation with a colleague through a QR code. They scan it, and they are notified live."

[Close the modal. Click the mic, ask a question aloud, then click speak-aloud on the answer.]

"I can ask by voice, and have the answer read back to me. This helps staff who are on the move."

[Attach the test file, ask a question about it.]

"And I can upload a document, for example a Word file or a PDF, and ask questions about it."

[Go back to the landing page. Click the Dashboard card. If the login page appears, sign in again.]

"Back on the landing page, I now click Dashboard. The same protection applies: access is only for authenticated users."

[Dashboard opens. Pick a chapter in the filter.]

"The dashboard gives a view of the whole matrix. I can filter by chapter, and every card and chart updates."

[Click a bar in the action-code chart. The roles chart changes.]

"If I click an action code, for example Approve, I see which roles approve the most. And these two coverage indicators are real data-quality signals about the extraction: the average responsibilities per task, and the share of tasks with no direct responsibility."

Bridge: "So we have a working product. The next question is: how do I know it is correct? Let's talk about evaluation."

---

## Timing

- Demo 1: about 90 s. To cut to 60 s, remove the description question and the typos question, keep the French one.
- Demo 2: about 90 s. To cut to 60 s, remove the voice step.
- Never cut: the login moment (it shows security), the Check/Verify remark, and the refusal.

## If the login does not appear a second time

The session may still be active when you click the Dashboard card. Say: "I am still signed in, so the dashboard opens directly." Do not apologise, it is normal behaviour.

## If something goes wrong

- **Video fails:** "Let me show it live." Open the live tab, start from the landing page, and follow the same speech.
- **Slow first load (free tier waking up):** "The hosted version sleeps when unused. This is a free-tier limit, not an architecture limit."
- **LLM down, plain answer:** "The language model is unavailable, so the agent returns the structured answer. The user still gets a correct answer. That is the design."
- **Login fails on stage:** use the test account kept in a notes file, and say: "I will use my demo account."
