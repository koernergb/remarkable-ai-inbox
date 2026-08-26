# reMarkable to Obsidian

## Goal

Build a quiet transcription bridge between a reMarkable tablet and an Obsidian vault.

The user writes normally on the reMarkable and emails a page or notebook to a dedicated Gmail inbox. The backend receives the PDF, transcribes the handwriting into faithful Markdown, and places both the Markdown and original PDF into the user's Obsidian vault.

Obsidian—not email—is where the user reads, searches, links, edits, and asks AI questions about the notes.

## MVP experience

1. Write notes on the reMarkable without special syntax.
2. Email the notebook PDF to the dedicated Gmail address.
3. The backend downloads and validates the attachment.
4. A vision-capable model transcribes each page.
5. The backend writes an Obsidian note and original PDF into configured vault folders.
6. Obsidian Sync, iCloud, Git, or the user's existing vault synchronization makes the note available on their devices.
7. The user searches or asks questions from within Obsidian.

There is no response email in the MVP.

## Product principles

- The transcription must be useful even if no AI chat or RAG feature is installed.
- The Obsidian vault is the canonical user-facing knowledge store.
- SQLite is operational state for idempotency, retry, and diagnostics—not a competing notes database.
- Preserve the original PDF beside every transcription.
- Prefer faithful transcription over aggressive summarization or rewriting.
- Mark uncertain text as `[?]`; do not invent illegible content.
- Do not require handwritten commands for normal use.
- Keep ingestion independent from the eventual Obsidian AI solution.

## Architecture

```text
reMarkable
    │ email PDF
    ▼
Dedicated Gmail label
    │
    ▼
Single Python application
    ├── validate and store PDF
    ├── render ordered page images
    ├── transcribe pages with a vision model
    ├── persist processing state in SQLite
    └── atomically export Markdown + PDF
            │
            ▼
        Obsidian vault
            ├── Remarkable/Notes/*.md
            └── Remarkable/Attachments/*.pdf
```

## Obsidian note format

```markdown
---
source: remarkable
received: 2026-08-26T14:30:00Z
source_message_id: gmail-message-id
original: "[[Remarkable/Attachments/2026-08-26 Linear Systems.pdf]]"
tags:
  - remarkable
---

# Linear Systems

<!-- remarkable-page: 1 -->

Transcribed notes...

<!-- remarkable-page: 2 -->

More notes...
```

Stable page comments preserve page boundaries without cluttering Obsidian's rendered view. The original PDF link provides an audit path when transcription is uncertain.

## AI transcription

Use the OpenAI Responses API through a replaceable provider interface. Send rendered page images and ask the model to preserve:

- headings, paragraphs, and lists;
- checkboxes;
- equations in LaTeX where reasonably confident;
- basic diagram descriptions;
- visible structure and page order;
- uncertain content as `[?]`.

Persist successful pages individually so interrupted documents can resume without retranscribing completed pages.

## Obsidian AI and RAG

RAG is deliberately separate from ingestion.

For the first release, use Obsidian's normal search and evaluate an Obsidian AI integration that can use selected notes, folders, or the vault as context. Do not build an embeddings index until real usage shows that native search and existing Obsidian tooling are insufficient.

The generated Markdown must remain portable if the user changes AI plugins or providers.

## Optional handwritten task extraction

`@todo` may remain as an optional convenience after transcription quality is validated:

```text
@todo redo exercise 4
```

may become:

```markdown
- [ ] Redo exercise 4
```

`@ask`, `@challenge`, and `@summarize` are not part of the revised MVP. AI questions belong in Obsidian, where the user has access to the wider vault context.

## Safety and idempotency

- Process only configured Gmail labels and allowed senders.
- Enforce attachment size and page-count limits.
- Use Gmail message IDs as idempotency keys.
- Never derive filesystem paths directly from email filenames or note titles.
- Write vault files atomically.
- Never overwrite a user-edited note silently.
- Do not mark a Gmail message processed until the vault export succeeds.
- Do not log note contents or secrets by default.

## MVP completion criteria

The MVP is complete when a representative reMarkable PDF can travel through Gmail into an approved test vault and produce:

- a faithful, readable Markdown transcription;
- stable page boundaries;
- a working link to the preserved original PDF;
- searchable text in Obsidian;
- no duplicate note after repeated polling;
- recoverable operational state after a simulated failure.

## Deferred

- Emailing AI responses.
- `@ask`, `@challenge`, and `@summarize` actions.
- A custom Obsidian plugin.
- A custom chat UI.
- Embeddings or a vector database.
- Cloud deployment, queues, or multiple workers.
- Advanced diagram reconstruction or equation verification.
