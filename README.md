# reMarkable to Obsidian

A lightweight Python application that receives reMarkable PDF exports, transcribes handwritten pages into Markdown, and places both the Markdown and original PDF into an Obsidian vault.

Email is intake only. Obsidian is where notes are read, searched, linked, edited, and used with AI.

The project is under active development. See [`build_brief.md`](build_brief.md) for the product scope and [`milestones.md`](milestones.md) for the implementation and human-validation gates.

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/) is recommended for local development

## Local setup

```bash
uv sync --extra dev
cp .env.example .env
uv run remarkable --help
```

The `.env` file is ignored by Git. Never commit API keys, Gmail OAuth credentials, OAuth tokens, notebook PDFs, rendered pages, transcriptions, vault contents, or the SQLite database.

## Commands

```bash
# Show CLI help
uv run remarkable --help

# Check configuration without displaying secret values
uv run remarkable doctor

# Initialize the local SQLite schema and FTS5 index
uv run remarkable init-db

# Search stored page transcriptions using SQLite FTS5 syntax
uv run remarkable search "eigenvalues"
```

## Current implementation

- SQLite models for documents, pages, tasks, processing state, and source-message idempotency.
- SQLite FTS5 page search with ranked, highlighted excerpts.
- PDF signature, size, encryption, readability, and page-count validation.
- Ordered PNG rendering in an automatically cleaned temporary directory.
- Safe Obsidian export with properties, stable page markers, linked PDFs, atomic writes, idempotent retries, and conflict detection.
- Replaceable vision transcription interface with an OpenAI Responses API adapter, base64 PNG input, bounded transient retries, redacted errors, dry-run payload metadata, and SQLite page checkpoints.
- A command parser remains available, but `@ask`, `@challenge`, and `@summarize` are no longer part of the revised MVP workflow.

No live OpenAI or Gmail call has been made. The exporter currently uses temporary test vaults only. Real note upload and real vault access remain behind the human-validation gates in `milestones.md`.

The model is configured with `REMARKABLE_OPENAI_MODEL`; `gpt-5.6-sol` is the documented vision-capable recommendation used in `.env.example` as of 2026-08-26. The application sends one rendered PNG per request with original image detail because handwriting transcription is an OCR-like task.

## Quality checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest --cov=app
```

## Approved MVP decisions

- OpenAI Responses API with a configurable vision-capable model.
- Gmail API with OAuth for inbox access only; no response email.
- Dedicated `remarkable-ai` and `remarkable-ai/processed` labels.
- Explicit sender allowlist.
- Obsidian is the canonical user-facing notes store; SQLite is operational state.
- Original PDFs and Markdown are retained in the vault.
- Temporary rendered page images are removed after successful processing.
- AI/RAG is evaluated inside Obsidian after transcription ingestion is dependable.

External credentials are not needed for the repository scaffold. Setup instructions for each integration will be added immediately before its live validation milestone.
