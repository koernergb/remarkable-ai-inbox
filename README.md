# reMarkable AI Inbox

A lightweight Python application that receives reMarkable PDF exports, transcribes handwritten pages into Markdown, processes a small set of handwritten AI commands, stores the results, and replies by email.

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

The `.env` file is ignored by Git. Never commit API keys, Gmail OAuth credentials, OAuth tokens, notebook PDFs, rendered pages, transcriptions, or the SQLite database.

## Commands

```bash
# Show CLI help
uv run remarkable --help

# Check configuration without displaying secret values
uv run remarkable doctor
```

## Quality checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest --cov=app
```

## Approved MVP decisions

- OpenAI Responses API with a configurable vision-capable model.
- Gmail API with OAuth for inbox access and outbound replies.
- Dedicated `remarkable-ai` and `remarkable-ai/processed` labels.
- Explicit sender allowlist.
- Original PDFs and Markdown are retained indefinitely for the MVP.
- Temporary rendered page images are removed after successful processing.

External credentials are not needed for the repository scaffold. Setup instructions for each integration will be added immediately before its live validation milestone.
