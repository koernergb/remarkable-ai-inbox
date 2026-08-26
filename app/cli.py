"""Command-line interface for reMarkable AI Inbox."""

from typing import Annotated

import typer

from app.config import get_settings
from app.database import Database

app = typer.Typer(
    name="remarkable",
    help="Process and search handwritten reMarkable notes.",
    no_args_is_help=True,
)


@app.callback()
def cli() -> None:
    """Process and search handwritten reMarkable notes."""


@app.command()
def doctor(
    strict: Annotated[
        bool,
        typer.Option(help="Fail if settings needed by future live integrations are missing."),
    ] = False,
) -> None:
    """Validate local configuration without exposing secret values."""
    settings = get_settings()
    typer.echo(f"Data directory: {settings.data_dir}")
    typer.echo(f"Database: {settings.redacted_database_url}")
    typer.echo(f"OpenAI API key configured: {settings.openai_api_key is not None}")
    typer.echo(f"OpenAI model configured: {settings.openai_model is not None}")
    typer.echo(f"Gmail credentials configured: {settings.gmail_credentials_path is not None}")
    typer.echo(f"Allowed senders configured: {bool(settings.allowed_senders)}")
    typer.echo(f"Obsidian vault configured: {settings.obsidian_vault_path is not None}")

    missing = settings.missing_live_settings
    if strict and missing:
        names = ", ".join(missing)
        raise typer.BadParameter(f"Missing live integration settings: {names}")

    typer.echo("Local configuration is valid.")


@app.command("init-db")
def init_db() -> None:
    """Create or update the local database schema."""
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        database.initialize()
    finally:
        database.close()
    typer.echo("Database initialized.")


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="SQLite FTS5 query")],
    limit: Annotated[int, typer.Option(min=1, max=100)] = 20,
) -> None:
    """Search stored page transcriptions."""
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        database.initialize()
        results = database.search(query, limit)
    finally:
        database.close()
    if not results:
        typer.echo("No matches.")
        return
    for result in results:
        typer.echo(f"{result.received_at:%Y-%m-%d} — {result.title}")
        typer.echo(f"Page {result.page_number}")
        typer.echo(result.excerpt)
        typer.echo()


def main() -> None:
    """Console-script wrapper used by packaging tools."""
    app()
