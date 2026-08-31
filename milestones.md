# reMarkable to Obsidian — Implementation Milestones

## Objective

Deliver a dependable pipeline that turns emailed reMarkable PDFs into faithful Markdown notes and linked original PDFs inside an Obsidian vault. Email is intake only. Obsidian is the reading, search, linking, and AI-question interface.

## Agent operating rules

The agent may autonomously edit repository files, add synthetic fixtures, run local quality checks, and make reversible choices already constrained by `build_brief.md`.

The agent must pause before:

- accessing a real Gmail account or changing Gmail labels;
- using a real API key or uploading any PDF to an AI provider;
- writing to the user's real Obsidian vault;
- installing or choosing an Obsidian community plugin;
- sending any email or creating external/cloud resources;
- deleting or overwriting real notes, PDFs, database records, or credentials;
- declaring transcription quality or the end-to-end workflow acceptable.

At a pause, report what is complete, the exact approval or validation needed, the recommended choice, safe instructions, and what happens next. Lack of a reply is never approval.

Every milestone requires all tests, formatting, linting, and strict type checking to pass. No secret, token, real PDF, transcription, database, or generated vault content may be committed.

## Status summary

| Milestone | Status |
| --- | --- |
| 0. Product direction | Accepted, then revised to Obsidian-first on 2026-08-26 |
| 1. Repository scaffold | Complete |
| 2. Persistence and search | Complete |
| 3. PDF validation and rendering | Complete |
| 4. Command parser | Complete but no longer central; only `@todo` may remain |
| 5. Obsidian export | In progress |
| 6. Vision transcription | Implementation complete; live privacy and quality validation pending |
| 7. Local end-to-end pipeline | Pending |
| 8. Gmail intake | Pending |
| 9. Real-vault validation | Pending |
| 10. Obsidian AI evaluation | Pending, optional |
| 11. Release hardening | Pending |

---

## Milestone 0 — Product direction

### Accepted decisions

- OpenAI Responses API behind a replaceable transcription interface.
- Gmail API with OAuth, dedicated intake/processed labels, and a sender allowlist.
- No outbound response email.
- Obsidian vault is the canonical user-facing store.
- Retain original PDFs and Markdown; delete temporary page images after success.
- Do not require handwritten commands. Defer `@ask`, `@challenge`, and `@summarize`.
- Keep `@todo` only as a possible later convenience.
- Defer custom RAG until ingestion works and existing Obsidian AI options are evaluated.

### Exit artifact

- Revised `build_brief.md` and this plan.

---

## Milestone 1 — Repository scaffold

### Scope

- Installable Python 3.12+ package and `remarkable` CLI.
- Typed settings, `.env.example`, safe `.gitignore`, lockfile, README, and diagnostics.
- Ruff formatting/linting, strict mypy, pytest, and coverage baseline.

### Status

Complete and verified.

---

## Milestone 2 — Persistence and operational search

### Scope

- Documents, pages, tasks, lifecycle status, error state, and message-ID idempotency.
- SQLite FTS5 for operational inspection and CLI search.
- SQLite remains backend state; Obsidian files are the user-facing notes.

### Status

Complete and verified. Add an exported vault path and export timestamp to the document record when the orchestration milestone needs them.

---

## Milestone 3 — Safe PDF intake and rendering

### Scope

- Signature, size, encryption, readability, and page-count validation.
- UUID-derived storage paths.
- Ordered PNG rendering with temporary-file cleanup.

### Status

Complete and verified with synthetic PDFs.

---

## Milestone 4 — Command detection

### Revised role

The implemented parser is retained, but it is not part of the main ingestion path. `@ask`, `@challenge`, and `@summarize` must not trigger backend actions. AI questions will happen in Obsidian with broader vault context.

`@todo` may later convert inline handwritten tasks into Markdown checkboxes, but only after faithful raw transcription is preserved.

### Status

Parser complete. No further human validation is needed unless optional task rewriting is enabled.

---

## Milestone 5 — Obsidian vault export

### Goal

Export a completed transcription and original PDF into a configurable test vault safely and predictably.

### Implementation

- Add typed settings for vault root, notes folder, attachments folder, and default tag.
- Validate that configured destinations remain inside the vault.
- Generate readable, collision-resistant filenames without trusting email filenames or titles.
- Add YAML properties for source, received time, source message ID, original PDF link, and tags.
- Preserve page boundaries with unobtrusive HTML comments.
- Copy PDFs and write Markdown through temporary sibling files followed by atomic replacement.
- On retry, recognize an identical prior export and return it without duplication.
- Refuse to overwrite an existing file whose content differs.
- Return vault-relative paths suitable for Obsidian links.
- Test Unicode titles, unsafe characters, duplicates, conflicts, missing source files, and path escape attempts.

### Agent verification

- Export synthetic content into a temporary fake vault.
- Parse frontmatter and verify the PDF link resolves.
- Repeat the same export and confirm no duplicate or rewrite.
- Modify the target note and confirm a retry refuses to overwrite it.

### Human input gate

None for a temporary test vault. Pause before first use of the real vault in Milestone 9.

---

## Milestone 6 — Vision transcription

### Goal

Turn rendered pages into faithful Markdown through a replaceable provider interface.

### Implementation

- Add a protocol/interface and fake transcription provider.
- Implement OpenAI Responses API integration with a configurable model.
- Preserve structure, equations, checkboxes, diagrams, and uncertain text.
- Capture request metadata without logging note content.
- Use bounded retries for transient errors only.
- Persist pages as they complete and resume partial documents.
- Add a dry-run that reports pages, model, and estimated image payload without uploading.
- Test success, timeout, rate limit, malformed response, partial failure, resume, and command preservation.

### Mandatory privacy gate

Before the first live request, pause and ask the human to configure the API key locally, approve the model and expected cost, approve the specific PDF for upload, and choose synthetic handwriting first unless they explicitly prefer a real note.

### Mandatory quality gate

Show original pages beside Markdown. The human validates fidelity, structure, equations, diagrams, commands, omissions, and appropriate `[?]` usage.

### Implementation status — 2026-08-26

- Provider protocol, deterministic fake provider, and OpenAI Responses API adapter implemented.
- Base64 PNG requests use `detail: original` for OCR-like fidelity.
- Model remains configurable; `.env.example` records the current documented recommendation.
- Transient failures use bounded exponential retries; authentication and invalid-response failures do not retry.
- Operational metadata excludes note contents and secret-bearing provider messages.
- Dry-run reports page count and payload sizes without constructing or sending a request.
- Successful pages checkpoint individually in SQLite; partial work resumes without repeated requests.
- Automated implementation verification is complete. No live API request has been made, so the privacy and quality gates above remain open.

---

## Milestone 7 — Local end-to-end pipeline

### Goal

Prove PDF-to-Obsidian behavior without Gmail.

### Implementation

- Orchestrate validation, storage, rendering, transcription, page persistence, Markdown assembly, and vault export.
- Add `remarkable import-pdf PATH` with `--dry-run` and an explicit test-vault destination.
- Persist restart-safe stage transitions.
- Store export path and timestamp.
- Add structured, content-redacted logs and clear errors.
- Test injected failures at every boundary and successful resume.

### Human validation gate

Use an approved PDF and temporary vault. The human opens the note in Obsidian and validates readability, page boundaries, properties, original-PDF link, and search behavior.

---

## Milestone 8 — Gmail intake

### Goal

Fetch eligible PDFs idempotently and feed them into the proven local pipeline.

### Implementation

- Gmail provider protocol plus a fake provider.
- OAuth with least-privilege scopes.
- Dedicated label and sender-allowlist filtering.
- Deterministic handling of multiple PDF attachments.
- One-shot polling first; interval loop only after validation.
- Mark processed only after successful vault export.
- Retry failures without duplicate notes or label mutations.
- `--dry-run` lists candidates without downloading or modifying mail.

### Mandatory Gmail gate

Pause before OAuth or real mailbox access. The human confirms account, labels, scopes, allowlist, credential placement, and a read-only dry-run.

### Staged live validation

Pause at each boundary:

1. Read-only candidate listing.
2. Download one approved synthetic/test PDF.
3. Process into a temporary vault without Gmail mutation.
4. Apply the processed label.
5. Poll again and confirm no duplicate export.

No outbound email is sent.

---

## Milestone 9 — Real Obsidian vault validation

### Goal

Safely adopt the user's actual vault only after temporary-vault behavior is accepted.

### Mandatory vault gate

Pause and ask the human for:

- the local vault root;
- approved notes and attachments subfolders;
- preferred filename/date convention and tags;
- confirmation that the vault is backed up;
- confirmation that a single synthetic note may be written.

Never modify `.obsidian/` configuration or install plugins without separate approval.

### Staged validation

1. Resolve and display proposed absolute and vault-relative paths without writing.
2. Write one synthetic note and PDF.
3. Human opens it in Obsidian and validates links/properties/search.
4. Process one approved real reMarkable export.
5. Repeat ingestion and prove idempotency.

### Exit artifact

- One accepted real note in the real vault with no duplicate or overwritten content.

---

## Milestone 10 — Obsidian AI evaluation (optional)

### Goal

Choose the smallest adequate method for asking questions over notes.

### Evaluation order

1. Obsidian native search and backlinks.
2. AI over explicitly selected notes/folders.
3. An existing Obsidian AI plugin with vault retrieval.
4. Only if evidence shows these are insufficient, a separate embeddings index.

### Mandatory plugin/privacy gate

Before recommending or installing a plugin, document its provider, data sent externally, API-key handling, indexing behavior, cost, maintenance status, and whether it modifies notes. The human chooses and installs it; the agent does not silently alter the vault configuration.

### Exit artifact

- A human-approved Obsidian AI workflow, or an explicit decision to defer AI while using search.

---

## Milestone 11 — Release hardening

### Scope

- Clean-install verification.
- Setup, OAuth, vault, privacy, retention, backup, recovery, retry, and troubleshooting documentation.
- Dependency bounds and supported Python version.
- Secret/private-data audit.
- Mapping from every MVP criterion to implementation and tests.

### Final human acceptance gate

The human confirms a reMarkable PDF becomes one faithful, searchable Obsidian note with a working original-PDF link; retries do not duplicate or overwrite notes; failures are recoverable; and privacy, cost, synchronization, and backup behavior are understood.

Only then declare the MVP complete.
