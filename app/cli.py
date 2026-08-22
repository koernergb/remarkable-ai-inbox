"""Command-line interface for reMarkable AI Inbox."""

from typing import Annotated

import typer

from app.config import get_settings

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

    missing = settings.missing_live_settings
    if strict and missing:
        names = ", ".join(missing)
        raise typer.BadParameter(f"Missing live integration settings: {names}")

    typer.echo("Local configuration is valid.")


def main() -> None:
    """Console-script wrapper used by packaging tools."""
    app()
