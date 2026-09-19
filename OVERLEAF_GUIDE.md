# Overleaf in 10 Minutes — for the DAM Thesis

You do not need to learn LaTeX. You need to know four things: how to open the
project, how to find the text you want to change, how to change it safely, and
how to get the PDF out. That's this guide.

---

## 1. Getting the project open (2 minutes)

1. Go to **overleaf.com**, create a free account (Google sign-in works).
2. Click **New Project** → **Upload Project**.
3. Drag in `DAM_Thesis_Overleaf_v2.zip`.
4. It opens. Click the green **Recompile** button.
5. The PDF appears on the right.

If the PDF appears, you're done with setup. Everything after this is editing text.

---

## 2. What you're looking at

Left sidebar = your files. The ones that matter:

| File | What's in it |
|---|---|
| `main.tex` | The spine. Just lists the chapters in order. You rarely touch it. |
| `preamble.tex` | Fonts, colours, page setup. **Don't edit this** unless you want to change the design. |
| `chapters/00_titlepage.tex` | Title page |
| `chapters/01_dedication.tex` | Dedication |
| `chapters/02_acknowledgments.tex` | Acknowledgments |
| `chapters/06_chapter1.tex` … `10_chapter5.tex` | The five chapters |
| `chapters/11_general_conclusion.tex` | Conclusion |
| `chapters/12_bibliography.tex` | Bibliography |
| `figures/` | The four diagrams |

Click a file in the sidebar, it opens in the middle. Edit, hit **Recompile**, see
the result. That's the whole loop.

---

## 3. The only LaTeX you actually need

Everything that isn't a `\command` is just your text. Type normally.

```latex
\chapter{Chapter Title}        % starts a new chapter
\section{Section Title}        % 1.1, 1.2, ...
\subsection{Sub Title}         % 1.1.1
\subsubsection{Deeper Title}   % 1.1.1.1

\textbf{bold text}
\textit{italic text}
\texttt{code or filenames}
```

**Paragraphs:** leave a blank line between them. That's it. A single line break
does nothing.

**Never type these characters raw** — they mean something to LaTeX. Put a
backslash in front:

| You want | You type |
|---|---|
| % | `\%` |
| $ | `\$` |
| & | `\&` |
| _ | `\_` |
| # | `\#` |

If your PDF suddenly won't compile after you typed something, one of these is
almost always why.

**Quotes:** LaTeX wants ` ``like this'' ` (two backticks, then two apostrophes)
to get proper curly quotes. Typing `"` works but looks wrong in the PDF.

---

## 4. Recompiling and errors

- **Recompile** button = rebuild the PDF. Do it often.
- If it fails, a red bar appears. Click **"View logs"** → it tells you the line
  number.
- 90% of errors are: an unescaped `%` or `&`, a missing `}`, or a typo in a
  command name.
- If you get stuck: press **Ctrl+Z** repeatedly to undo back to the last version
  that compiled, then retype more carefully.
- Overleaf keeps full history: **Menu → History** lets you roll back to any
  earlier version. You cannot permanently break this project.

---

## 5. The three things you must do before submitting

### a) Add the two logos

Open `chapters/00_titlepage.tex`. Near the top you'll see two placeholder boxes.
Upload your logo images (drag them into the `figures` folder in the sidebar),
then replace:

```latex
\fbox{\parbox[c][2cm][c]{5cm}{\centering\sffamily\small POLYTECH INTL LOGO}}
```

with:

```latex
\includegraphics[height=2cm]{figures/logo_polytech.png}
```

Same for the AfDB one. Keep both at `height=2cm` so they match.

### b) Add the two screenshots

Chapter 5 describes the chat interface and the dashboard. Take screenshots of
your running app, drag them into `figures/`, and insert them where you want
them:

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.85\textwidth]{figures/screenshot_chat.png}
\caption{The chat interface of the delivered application.}
\label{fig:chat}
\end{figure}
```

The four diagrams are already placed and working — you don't need to touch those.

### c) Download the PDF

**Menu → Download → PDF**. That's your submission file.

---

## 6. Working faster

- **Ctrl+F** searches inside the open file.
- The **table of contents** in the PDF is generated automatically from your
  `\chapter` and `\section` commands. Never type it by hand.
- Click any line in the PDF → Overleaf jumps to that line in the source.
  (And Ctrl+click in the source jumps to that spot in the PDF.) This is the
  single most useful trick for finding the text you want to edit.
- Overleaf autosaves. There is no save button.

---

## 7. If something goes badly wrong

The zip file on your computer is untouched. Delete the Overleaf project, upload
the zip again, and you're back to a known-good state. Nothing you do online can
damage the original.
