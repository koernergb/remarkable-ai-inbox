# reMarkable AI Inbox — Implementation Milestones

## Purpose

This plan turns `build_brief.md` into a sequence of small, testable increments. The MVP is complete when a user can email a reMarkable PDF, have it transcribed and stored, invoke the four supported commands, receive a useful email response, and search previously processed notes.

The implementation should remain a single Python application. Do not introduce queues, microservices, embeddings, vector databases, autonomous agents, or cloud infrastructure unless the human explicitly expands the scope.

## Working conventions

### Agent autonomy

The implementation agent may proceed without asking for permission when it is:

- Creating or editing files inside this repository.
- Running local formatting, linting, type-checking, unit, and integration tests.
- Creating local test fixtures that contain no private user data.
- Making reversible implementation choices already constrained by the build brief.
- Fixing defects found by automated tests when the fix does not change agreed behavior.

The agent should prefer deterministic tests and mocked external services until a milestone explicitly calls for a live integration test.

### Mandatory pause conditions

The agent must pause and request human input before:

- Selecting a product behavior that materially changes the user experience and is not settled in this plan or `build_brief.md`.
- Creating, changing, or using a real Gmail account, Google Cloud project, OAuth client, API key, sender allowlist, or other external credential.
- Installing or provisioning external/cloud resources that could incur cost or persist outside the repository.
- Sending email to a real recipient or marking messages in a real mailbox as processed.
- Uploading a real notebook, PDF, email, or other private content to an AI provider for the first time.
- Running a live AI test that could incur non-trivial cost or expose sensitive content.
- Performing destructive database migrations, deleting stored documents, or changing production-like data.
- Moving beyond the MVP commands or architecture.
- Declaring a milestone complete when its acceptance criteria require subjective human judgment.

When pausing, the agent must state:

1. What has been completed and verified locally.
2. The exact decision, credential, or validation needed.
3. The recommended choice and meaningful alternatives.
4. The precise action the human should take.
5. What the agent will do after approval.

### Validation vocabulary

- **Agent verification:** automated or local checks the agent performs independently.
- **Human verification:** a person inspects behavior or output and confirms it is acceptable.
- **Human input gate:** work cannot safely continue until a person supplies a decision, credential, or real-world action.
- **Exit artifact:** the concrete files or behavior that demonstrate milestone completion.

## Definition of done for every milestone

Before presenting a milestone for review, the agent must:

- Run all existing tests plus the tests added for the milestone.
- Run the configured formatter, linter, and type checker.
- Confirm secrets, generated PDFs, page images, databases, and private fixtures are not accidentally tracked.
- Update the README or configuration documentation when user-facing setup changes.
- Report commands run, results, known limitations, and any deferred work.
- Stop at the milestone's human gate when one is specified; do not silently treat lack of feedback as approval.

---

## Milestone 0 — Resolve foundational choices

### Goal

Agree on the few external-service and product decisions that affect the application boundaries before implementation begins.

### Decisions needed

1. **AI provider and model:** Default recommendation: OpenAI Responses API with a current vision-capable model, configured through environment variables so the specific model is replaceable.
2. **Gmail access method:** Default recommendation: Gmail API with OAuth, read-only access during initial validation, adding label modification only when end-to-end processing is ready. Avoid IMAP passwords.
3. **Outbound email method:** Default recommendation: Gmail API using the same account, subject to the minimum required OAuth scope.
4. **Mailbox workflow:** Default recommendation: a dedicated Gmail label, for example `remarkable-ai`, plus a second label such as `remarkable-ai/processed` rather than relying only on read/unread state.
5. **Authorized senders:** Default recommendation: require an explicit sender allowlist.
6. **Data retention:** Decide whether original PDFs, rendered page images, and AI outputs remain indefinitely for the MVP. Default: retain PDFs and Markdown; remove temporary page images after successful processing.

### Human input gate — required before Milestone 1

The agent must pause and ask the human to approve or revise the six decisions above. No credentials should be requested yet. Record the accepted decisions in the README or an architecture-decision section of this file.

### Exit artifact

- Documented, human-approved integration and retention choices.

---

## Milestone 1 — Repository scaffold and quality baseline

### Goal

Create an installable Python 3.12+ application with a stable local development workflow.

### Implementation

- Create `pyproject.toml` with runtime and development dependencies.
- Create the `app/` package and initial modules from the build brief.
- Add a CLI entry point named `remarkable`.
- Add configuration loading through environment variables using typed settings.
- Add `.env.example` containing names and descriptions only—never real secrets.
- Add `.gitignore` entries for `.env`, OAuth token files, databases, stored PDFs, rendered images, caches, and test artifacts.
- Create `data/documents/` with a tracked placeholder if useful, while ignoring its contents.
- Add pytest, formatting, linting, and static type-checking configuration.
- Add a README with local setup and test commands.
- Add a minimal health/config diagnostic command that does not print secret values.

### Agent verification

- A clean environment can install the project from its declared metadata.
- `remarkable --help` succeeds.
- Tests, formatter check, linter, and type checker succeed.
- A repository scan shows no secrets or generated private data.
- Missing required configuration produces a concise actionable error.

### Human verification

None required if all automated checks pass and the agreed decisions from Milestone 0 are reflected accurately.

### Exit artifact

- Installable package, documented local workflow, and green quality checks.

---

## Milestone 2 — Persistence, document lifecycle, and search foundation

### Goal

Persist documents, pages, tasks, and processing state safely before connecting external systems.

### Implementation

- Define SQLAlchemy models for:
  - `documents`: UUID, source message ID, filename, title, sender, received time, stored PDF path, combined Markdown, status, error summary, timestamps.
  - `pages`: document ID, one-based page number, Markdown, timestamps, and a uniqueness constraint on document/page.
  - `tasks`: document ID, source page if known, text, completion state, timestamps.
- Enforce uniqueness of the source Gmail message ID for idempotency.
- Define explicit lifecycle states such as `received`, `rendered`, `transcribed`, `processed`, `replied`, and `failed`.
- Add database initialization and migration support appropriate for a local SQLite app.
- Store files using generated UUID names rather than email-provided filenames.
- Validate paths so attachments cannot escape the configured data directory.
- Enable SQLite FTS5 over document/page Markdown, with a deterministic fallback or clear error if FTS5 is unavailable.
- Implement `remarkable search QUERY` with useful excerpts, dates, titles, and page numbers.

### Tests

- Model creation, relations, constraints, and lifecycle transitions.
- Duplicate message IDs cannot create duplicate documents.
- Task creation and completion persistence.
- FTS indexing and representative search queries.
- Malicious filenames and path traversal attempts.
- Database errors leave actionable status/error information.

### Agent verification

- Initialize a temporary database, insert fixtures, reopen it, and verify all records.
- Search returns the correct page and excerpt for multiple fixture documents.
- Reprocessing the same synthetic message ID is a no-op or safe resume, never a duplicate.

### Human verification

None required. The agent should show one sample CLI search result in the milestone report.

### Exit artifact

- Tested schema, lifecycle state model, idempotent persistence, and local full-text search.

---

## Milestone 3 — PDF intake validation and page rendering

### Goal

Accept a local PDF safely and render ordered page images suitable for vision transcription.

### Implementation

- Validate attachment extension, MIME information where available, PDF signature, size, and configurable page-count limits.
- Copy accepted PDFs into `data/documents/` using the document UUID.
- Render pages with PyMuPDF at a configurable, moderate resolution.
- Normalize image format and dimensions while avoiding unnecessary quality loss.
- Return ordered page metadata to the processing pipeline.
- Use a temporary working directory and clean it after success; preserve enough diagnostic information on failure without retaining private rendered pages by default.
- Add a local command or test helper to process a PDF without Gmail.

### Tests

- One-page and multi-page PDFs.
- Empty, corrupt, encrypted, oversized, and non-PDF inputs.
- Stable page ordering and page numbering.
- Temporary-file cleanup on success and failure.
- Filenames containing spaces, Unicode, and path traversal sequences.

### Agent verification

- Render synthetic typed and simple drawing fixtures.
- Confirm page count, order, dimensions, and cleanup behavior.
- Confirm invalid inputs fail before any AI request.

### Human verification

Optional visual inspection of synthetic rendered pages. Real reMarkable content is deliberately deferred to Milestone 5.

### Exit artifact

- Safe, deterministic local PDF-to-page-image pipeline.

---

## Milestone 4 — Command detection and deterministic context extraction

### Goal

Find the four commands in Markdown and extract predictable nearby context without invoking an AI model.

### Implementation

- Recognize only `@ask`, `@challenge`, `@todo`, and `@summarize` as standalone command markers.
- Preserve command order and page origin.
- Avoid false positives in email addresses, longer tokens, and fenced code where appropriate.
- Define context rules:
  - Inline text after `@todo` is the task.
  - Otherwise use the closest non-empty block before the command, bounded by the previous heading or command.
  - For `@ask`, prefer a preceding question block; fall back to the bounded section.
  - For `@challenge` and `@summarize`, use the bounded section, with an explicit fallback to the whole page when the section is empty.
- Represent detected commands with typed data containing command type, raw marker, page, context, and source span/line information.
- Deduplicate only exact duplicate detections from the same source location.

### Tests

- Every command in inline and standalone forms.
- Several commands on one page and across pages.
- Headings, blank lines, lists, equations, and punctuation.
- Near misses such as `person@ask.com`, `@asking`, and escaped examples.
- Missing context and ambiguous placement.
- `@todo` with inline and preceding text.

### Agent verification

- All rules are documented and covered by table-driven tests.
- Command detection is deterministic and makes no network calls.

### Human verification gate — required

The agent must present at least six representative Markdown examples with detected context. The human confirms that the context behavior matches how they expect to write on the tablet. If it does not, revise the rules and tests before continuing.

### Exit artifact

- Human-approved, fully tested command and context semantics.

---

## Milestone 5 — Vision transcription integration

### Goal

Transcribe rendered notebook pages into faithful structured Markdown through a vision-capable model.

### Implementation

- Define a provider interface so transcription can be mocked in tests.
- Implement the approved AI provider using current supported APIs.
- Use structured output where practical, while preserving Markdown verbatim.
- Prompt the model to preserve headings, paragraphs, lists, checkboxes, equations, diagrams, and `@commands`; mark uncertainty as `[?]`; never invent illegible text.
- Capture model name, request ID if available, duration, and token/cost metadata without logging page content by default.
- Add bounded retries for transient failures and no retries for invalid credentials or rejected content.
- Add configurable concurrency and request/page limits; default to conservative sequential processing.
- Persist each completed page so an interrupted document can resume without retranscribing successful pages.
- Combine page Markdown deterministically into document Markdown.

### Tests

- Mocked successful transcription, timeout, rate limit, malformed response, provider error, and partial multi-page failure.
- Resume behavior after partial failure.
- Commands remain intact in returned Markdown.
- Sensitive page content is absent from normal logs and exceptions.

### Agent verification before requesting credentials

- All provider interactions pass through mocks.
- The complete multi-page pipeline works with fixture responses.
- A dry-run clearly lists how many pages would be sent and to which configured model.

### Human input and privacy gate — required

The agent must pause before the first live request and ask the human to:

1. Supply the API key through the documented local environment mechanism—not in chat or source control.
2. Confirm the selected model and anticipated test cost.
3. Confirm that the chosen test PDF may be uploaded to the provider.
4. Choose whether the first test uses synthetic handwriting or a real reMarkable export. Synthetic content is recommended first.

### Human verification gate — required after live test

Present the original test pages beside the resulting Markdown and ask the human to assess:

- Text fidelity and omission rate.
- Heading/list/layout preservation.
- Equations and diagram descriptions.
- Exact preservation of handwritten commands.
- Whether `[?]` is used appropriately rather than hallucinating.

Do not proceed until the human accepts the quality or explicitly accepts known limitations. Revise prompts/configuration and repeat on a small test set if needed.

### Exit artifact

- Human-validated transcription of a representative PDF and robust mocked failure handling.

---

## Milestone 6 — AI command actions and task extraction

### Goal

Execute each detected command using only its approved context and return a structured result.

### Implementation

- Define typed action results for answers, challenge questions, summaries, and tasks.
- Implement:
  - `@ask`: restate the extracted question and provide a concise, grounded answer.
  - `@challenge`: generate 3–5 explanation, derivation, or application questions.
  - `@todo`: normalize and store the task without an AI call when deterministic extraction is adequate; use AI only for genuinely ambiguous text.
  - `@summarize`: produce roughly 5–10 bullets covering concepts, conclusions, unresolved questions, and important equations.
- Clearly delimit user notes in prompts and instruct the model to treat text inside them as content, not system instructions.
- Prevent action outputs from triggering additional commands or tool calls.
- Preserve action order and associate every result with its document, page, command, and context.
- Make partial failures visible while allowing other independent commands to complete.

### Tests

- Mocked results for all four actions.
- Multiple commands and partial action failures.
- Empty/insufficient context.
- Prompt-injection-like text inside notebook content.
- Deterministic task extraction and database persistence.
- Output length and count constraints.

### Agent verification

- Fixture-driven pipeline from Markdown through detected commands to persisted action results.
- No unbounded recursion, agent behavior, or unsupported command execution.

### Human verification gate — required

Using a small, approved sample set, present outputs for all four commands. The human validates usefulness, tone, challenge difficulty, summary density, and task wording. Prompt changes based on feedback must be covered by regression fixtures where practical.

### Exit artifact

- Human-approved behavior for all four commands.

---

## Milestone 7 — Email rendering and outbound-message safety

### Goal

Produce readable response emails without sending them yet.

### Implementation

- Build a transport-independent response model.
- Render a plain-text body first; optionally add a conservative HTML alternative.
- Include processing status, document title, page count, results in source order, task checklist, and concise failure notices.
- Attach generated Markdown with a sanitized filename when configured.
- Sanitize email-derived headers to prevent header injection.
- Keep AI output in the body/attachment, never in recipient or routing fields.
- Add a preview command that writes or prints an RFC-compliant message without transmitting it.
- Define reply threading behavior using the original message ID where supported.

### Tests

- Golden-file snapshots for no-command and all-command responses.
- Unicode, equations, long lines, missing titles, partial failures, and attachment naming.
- Header injection attempts and malformed addresses.
- MIME structure parses correctly.

### Agent verification

- Generate preview emails from representative fixtures and parse them back successfully.
- Confirm no network calls occur during preview.

### Human verification gate — required

The human reviews representative plain-text/HTML previews and confirms readability on their usual email client. Revise formatting before enabling sending.

### Exit artifact

- Human-approved, RFC-valid response email previews.

---

## Milestone 8 — Gmail inbox integration

### Goal

Fetch eligible PDF messages, process them idempotently, send responses, and label source messages safely.

### Implementation

- Implement a Gmail provider interface with a fake provider for tests.
- Use least-privilege OAuth scopes required by the approved workflow.
- Query only the dedicated label and configured sender allowlist.
- Ignore or reject messages without eligible PDF attachments.
- Handle multiple attachments deterministically; default to one document per PDF.
- Store the Gmail message ID before processing and enforce database idempotency.
- Send the response only after processing results are persisted.
- Add the processed label only after a successful send.
- On failure, retain retryable state and apply an error label if approved; do not send duplicate replies.
- Implement a one-shot poll command first. Add a simple interval loop only after the one-shot workflow is proven.
- Provide `--dry-run` that lists candidate message IDs and attachment metadata without downloading, processing, sending, or changing labels.

### Tests

- Fake Gmail inbox covering eligible, ineligible, duplicate, malformed, and multi-attachment messages.
- Send failure, label failure, retry, and restart scenarios.
- Verify exactly-once reply behavior under repeated polling.
- Verify sender allowlist and label filtering.
- Verify dry-run has no mutations.

### Agent verification before live access

- End-to-end processing succeeds against the fake provider.
- Repeating the same fixture poll does not duplicate documents or replies.
- Dry-run mutation assertions pass.

### Human input gate — required

The agent must pause before OAuth setup or real mailbox access. Ask the human to:

1. Confirm the Gmail account and label names.
2. Create or approve the Google Cloud/OAuth configuration using documented steps.
3. Place credentials in the ignored local path—never paste tokens into chat or commit them.
4. Confirm OAuth scopes and sender allowlist.
5. Approve a live dry-run.

### Live validation sequence — pause at each numbered boundary

1. **Read-only dry-run:** List matching messages and attachments without downloading or modifying anything. Human confirms selection is correct.
2. **Download-only test:** Download one approved synthetic/test PDF and persist intake metadata without AI processing. Human confirms the correct message and file were selected.
3. **Full processing, no send:** Process that message and render an email preview. Human confirms transcription and actions.
4. **Send to approved recipient:** Send exactly one response. Human confirms receipt, formatting, and threading.
5. **Label mutation:** Apply the processed label to that message. Human confirms mailbox state.
6. **Idempotency rerun:** Poll again. Both agent and human confirm no duplicate document or reply was created.

The agent must not combine these first-live-use boundaries without explicit human authorization.

### Exit artifact

- Human-validated Gmail round trip with proven idempotency and least-privilege access.

---

## Milestone 9 — End-to-end orchestration and operational behavior

### Goal

Connect the pipeline into a dependable single-process application suitable for regular personal use.

### Implementation

- Implement the orchestrator: discover message, validate attachment, persist intake, render, transcribe, detect commands, run actions, save results, compose response, send, and label.
- Make every stage restart-safe using persisted lifecycle state.
- Add structured logs with document IDs and stages, excluding note text and secrets by default.
- Add clear exit codes and operator-facing error messages.
- Add configurable timeouts, retry limits, file/page limits, polling interval, and log level.
- Add commands to inspect failed documents and retry a specific document safely.
- Prevent concurrent processing of the same message in one or multiple local processes using a database-backed claim or equivalent simple lock.
- Document backup and restore for `remarkable.db` and `data/documents/`.
- Document how to run manually and, optionally, through a user-level scheduler. Do not install a scheduler without human approval.

### Tests

- Full fake-provider end-to-end happy path.
- Crash/restart at each lifecycle boundary.
- Partial transcription and action failures.
- Duplicate polls and concurrent claims.
- Retry of failed documents without duplicate email.
- Logging redaction and configuration validation.

### Agent verification

- Run the entire suite repeatedly from a clean temporary directory.
- Demonstrate recovery from at least three injected failures.
- Confirm a second poll is a no-op after success.

### Human verification gate — required

Run a real reMarkable-originated email through the system. The human verifies:

- The intended email was selected.
- The stored PDF matches the attachment.
- Markdown is searchable and page associations are correct.
- All handwritten commands produced appropriate results.
- The reply is readable and arrived only once.
- Processed/error labels match the actual outcome.

The human explicitly decides whether the MVP is reliable enough for recurring operation.

### Exit artifact

- One successful, human-validated reMarkable-to-email round trip plus documented recovery procedures.

---

## Milestone 10 — Release hardening and MVP handoff

### Goal

Make the completed MVP reproducible, understandable, and safe to operate.

### Implementation

- Consolidate setup, OAuth, configuration, usage, troubleshooting, privacy, retention, backup, and recovery documentation.
- Add an architecture overview and processing-state diagram.
- Document AI-provider data handling assumptions and which content leaves the machine.
- Document expected costs and the configuration knobs that constrain them.
- Pin or bound dependencies appropriately and record the supported Python version.
- Add a clean-install smoke test.
- Add a release checklist and known-limitations section.
- Remove obsolete experimental code and ensure sample data is synthetic.

### Agent verification

- Follow the setup instructions from a clean environment using fake credentials/providers.
- Run the complete automated test and quality suite.
- Confirm the git diff contains no secrets, tokens, databases, user PDFs, rendered pages, or private transcriptions.
- Confirm all MVP requirements in `build_brief.md` map to an implementation and test.

### Final human acceptance gate — required

The agent presents an acceptance checklist. The human explicitly confirms:

- Normal notes are transcribed, stored, and searchable.
- `@ask`, `@challenge`, `@todo`, and `@summarize` behave acceptably.
- Original PDFs and extracted Markdown are retained according to the approved policy.
- Email responses are readable and are not duplicated.
- Failures can be found and retried.
- Privacy, cost, and backup behavior are understood.
- Known limitations are acceptable for MVP release.

Only after this confirmation should the MVP be declared complete.

### Exit artifact

- Reproducible MVP release with human sign-off.

---

## Cross-milestone acceptance matrix

| Capability | Built in | First agent verification | Required human validation |
| --- | --- | --- | --- |
| Project setup and quality tooling | M1 | Clean install and green checks | None |
| SQLite persistence and FTS search | M2 | Fixture database and CLI search | Final end-to-end search in M9 |
| PDF validation and rendering | M3 | Synthetic PDFs | Representative real PDF in M5/M9 |
| Command/context semantics | M4 | Table-driven tests | Context examples in M4 |
| Handwriting transcription | M5 | Mock provider and dry-run | Side-by-side live output in M5 |
| Four AI actions | M6 | Mocked pipeline | Sample outputs in M6 |
| Email formatting | M7 | MIME parsing and snapshots | Email-client preview in M7 |
| Gmail receive/send/labels | M8 | Fake provider | Staged live Gmail validation in M8 |
| Restart safety and operations | M9 | Failure injection | Real reMarkable round trip in M9 |
| MVP release | M10 | Clean-install audit | Final acceptance sign-off |

## Explicitly deferred beyond MVP

Do not begin these items without a new human-approved plan:

- Embeddings, semantic/vector search, or retrieval-augmented generation.
- A web application or mobile application.
- Multi-user accounts, shared notebooks, or role-based access.
- Calendar/task-manager integrations.
- Automatic PDF generation for return to the reMarkable.
- Advanced diagram reconstruction or equation verification.
- General-purpose handwritten command syntax.
- Background queues, distributed workers, or cloud deployment.
- Analytics, telemetry, or long-term prompt experimentation infrastructure.

## Recommended milestone reporting template

At every milestone boundary, the agent should report:

```text
Milestone: <number and name>
Status: ready for review | blocked | accepted

Completed:
- ...

Verification performed:
- <command/check>: <result>

Artifacts:
- <files, commands, or sample output>

Known limitations:
- ...

Human action required:
- none
  OR
- <specific decision/credential/validation and how to provide it safely>

Next after approval:
- ...
```

