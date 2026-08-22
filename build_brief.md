# reMarkable AI Inbox

## 1. Goal

Build a lightweight AI layer around a reMarkable tablet.

The user writes normally on the reMarkable and emails a page/notebook to a dedicated email address.

The system automatically:

1. Receives the PDF.
2. Converts handwriting into structured Markdown.
3. Saves the original PDF and extracted text.
4. Detects simple handwritten AI commands.
5. Runs the requested AI action.
6. Emails the result back as readable text/Markdown.

The reMarkable remains a distraction-free writing surface. All intelligence lives in the backend.

---

# 2. MVP Experience

### Normal notes

Write:

> Differential equations notes...
>
> The characteristic equation gives us...
>
> @todo review complex eigenvalues

Email the notebook.

Receive:

**Processed: Differential Equations Notes**

```markdown
# Differential Equations Notes

The characteristic equation gives us...

## Tasks
- Review complex eigenvalues
```

The note is now stored and searchable.

### Ask something

Write:

> Why does this solution become unstable?
>
> @ask

The system recognizes the command and emails an explanation.

### Test understanding

Write:

> Eigenvectors describe directions that remain unchanged under a linear transformation.
>
> @challenge

Receive:

**Test yourself**

1. What exactly does "unchanged" mean here?
2. Can an eigenvector's magnitude change?
3. What does a negative eigenvalue imply?
4. What happens if a matrix has fewer independent eigenvectors than its dimension?

The important design principle is that AI helps interrogate the user's thinking rather than replacing it.

---

# 3. MVP Commands

Only implement four.

| Command      | Behavior                                     |
| ------------ | -------------------------------------------- |
| `@ask`       | Answer the nearby handwritten question       |
| `@challenge` | Generate 3–5 questions testing understanding |
| `@todo`      | Extract an item into the task list           |
| `@summarize` | Produce a concise summary of the notes       |

Do not build a complicated command parser.

After OCR, search the extracted text for these strings.

---

# 4. Architecture

```text
reMarkable
    │
    │ email PDF
    ▼
Dedicated Gmail inbox
    │
    ▼
Python backend
    │
    ├── download attachment
    │
    ▼
PDF → page images
    │
    ▼
Vision-capable model
    │
    ├── handwriting OCR
    ├── layout understanding
    └── basic diagram description
    │
    ▼
Structured Markdown
    │
    ▼
Command detector
    │
    ├── @ask
    ├── @challenge
    ├── @todo
    └── @summarize
    │
    ▼
LLM
    │
    ▼
SQLite
    │
    ├── documents
    ├── pages
    └── tasks
    │
    ▼
Email response
```

Avoid microservices, queues, vector databases, agents, Kubernetes, and elaborate event infrastructure.

One Python application is enough.

---

# 5. Suggested Stack

## Backend

Python 3.12+

Use something like:

```text
FastAPI
SQLAlchemy
SQLite
PyMuPDF
Pydantic
```

FastAPI isn't strictly necessary, but gives the project somewhere to grow.

## AI

Use one multimodal model capable of directly reading handwriting from page images.

Do **not** build a traditional OCR pipeline initially.

Input:

```text
PDF
 ↓
PNG pages
 ↓
vision model
 ↓
Markdown
```

Ask the model to preserve:

* headings
* paragraphs
* lists
* equations where possible
* checkboxes
* command markers
* basic descriptions of diagrams

Store both the original PDF and extracted representation.

## Storage

Start with:

```text
data/
    documents/
        <uuid>.pdf

remarkable.db
```

SQLite schema:

```text
documents
---------
id
filename
received_at
raw_pdf_path
markdown

pages
-----
id
document_id
page_number
markdown

tasks
-----
id
document_id
text
completed
created_at
```

No cloud database required.

---

# 6. Processing Pipeline

## Step 1 — Receive email

Create a dedicated address or Gmail label such as:

```text
remarkable-ai@
```

The backend periodically checks for unread messages containing PDF attachments.

Download the PDF.

Mark the message processed.

---

## Step 2 — Render pages

Use PyMuPDF:

```text
notes.pdf

↓

page_001.png
page_002.png
page_003.png
```

A moderate resolution is sufficient.

---

## Step 3 — Transcribe

Send each page image to the vision model.

Prompt conceptually:

```text
Transcribe this handwritten notebook page.

Preserve the structure of the page using Markdown.

Preserve commands beginning with @ exactly.

For equations, use LaTeX where reasonably confident.

Do not invent illegible text.

Represent uncertain transcription as [?].
```

Result:

```markdown
# Linear Systems

For dx/dt = Ax, solutions depend on the eigenvalues
of A.

@challenge

## Questions

Why do complex eigenvalues produce oscillations?

@ask
```

---

# 7. Command Detection

Keep this extremely simple.

After transcription:

```python
commands = [
    "@ask",
    "@challenge",
    "@todo",
    "@summarize",
]
```

Search the Markdown.

The model can then determine the nearby context.

For example:

```text
Why does λ > 0 make the equilibrium unstable?

@ask
```

Send the surrounding section to the LLM.

You don't need bounding boxes or spatial reasoning for the MVP.

---

# 8. AI Actions

## `@ask`

Input:

```text
notes + nearby question
```

Output:

```text
Your question

Why does λ > 0 make the equilibrium unstable?

Answer

A positive eigenvalue causes the corresponding
component of the solution to grow exponentially...
```

---

## `@challenge`

Take the surrounding notes and generate 3–5 questions.

Instruction:

```text
Test whether the writer genuinely understands the
material.

Prefer questions requiring explanation, derivation,
or application.

Do not merely ask for definitions.
```

---

## `@todo`

Extract the nearby task.

Example:

```text
@todo redo exercise 4 without looking at solution
```

becomes:

```text
tasks

[ ] Redo exercise 4 without looking at solution
```

---

## `@summarize`

Generate approximately 5–10 bullets covering:

* main concepts
* conclusions
* unresolved questions
* important equations

---

# 9. Email Response

Keep this simple too.

Subject:

```text
reMarkable AI — Linear Systems
```

Body:

```text
Processed 4 pages.

COMMANDS FOUND

@ask
Why does λ > 0 make the equilibrium unstable?

ANSWER
...

@challenge

1. ...
2. ...
3. ...

TASKS

[ ] Redo exercise 4 without looking at solution
```

Attach the generated Markdown as `.md` if useful.

For the first version, **don't bother generating a PDF to send back to the reMarkable.**

Email is enough to prove the interaction works.

---

# 10. Minimal Search

Once notes are stored, add one CLI command:

```bash
remarkable search "eigenvalues"
```

Initially this can literally be SQLite full-text search.

Example:

```text
> remarkable search "eigenvalues"

2026-08-22 — Differential Equations
Page 3

"For dx/dt = Ax, stability depends on..."
```

Don't implement embeddings yet.

---

# 11. Repository

```text
remarkable-ai/
│
├── app/
│   ├── main.py
│   ├── email.py
│   ├── pdf.py
│   ├── transcription.py
│   ├── commands.py
│   ├── actions.py
│   ├── database.py
│   └── models.py
│
├── data/
│   └── documents/
│
├── tests/
│   ├── test_commands.py
│   └── test_transcription.py
│
├── remarkable.db
├── pyproject.toml
├── .env.example
└── README.md
```

---

# 12. Build Order

## Milestone 1 — Handwriting → Markdown

**Target: 2–3 hours**

Manually provide a reMarkable PDF.

Implement:

```text
PDF
→ images
→ vision model
→ Markdown
```

Success criterion:

A real handwritten notebook becomes reasonably faithful Markdown.

This validates the hardest assumption immediately.

---

## Milestone 2 — Commands

**Target: 2–3 hours**

Implement:

```text
@ask
@challenge
@summarize
```

Input can still be a local PDF.

Success criterion:

```bash
python process.py notes.pdf
```

produces transcription plus AI responses.

---

## Milestone 3 — Email

**Target: ~half day**

Connect the dedicated inbox.

Implement:

```text
reMarkable
→ email
→ backend
→ processing
→ response email
```

This creates the first genuinely useful version.

---

## Milestone 4 — Persistence + TODOs

**Target: ~half day**

Add SQLite.

Store:

* documents
* pages
* Markdown
* TODOs

Add simple search.

---

# 13. MVP Boundary

Explicitly **do not build yet**:

* vector database
* RAG framework
* autonomous agents
* mobile app
* web frontend
* handwriting training
* custom OCR model
* Anki integration
* calendar integration
* diagram editing
* automatic research citations
* knowledge graphs
* handwriting recognition personalization
* generated PDFs
* syncing directly with reMarkable APIs

Those are V2 features.

---

# 14. Success Criterion

The project is successful when this interaction feels normal:

```text
1. Sit somewhere with reMarkable.

2. Work through an idea/problem by hand.

3. Write:

      @challenge

4. Email notebook.

5. A minute later receive:

   "Here are five questions exposing weaknesses
    in your reasoning."

6. Tomorrow:

      remarkable search "camera covariance"

   retrieves the relevant handwritten notes.
```

At that point you have something worth extending.

The next major feature should probably be **semantic search + `@connect`**, because once you've accumulated hundreds of handwritten pages, being able to retrieve and connect your own previous thinking is considerably more valuable than adding another dozen AI commands.

