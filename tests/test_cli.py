"""CLI smoke tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.config import get_settings
from app.database import Database, sqlite_url
from app.models import Document, Page

runner = CliRunner()


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_help_succeeds() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Process and search handwritten reMarkable notes" in result.stdout


def test_doctor_does_not_print_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REMARKABLE_OPENAI_API_KEY", "super-secret-value")

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "OpenAI API key configured: True" in result.stdout
    assert "super-secret-value" not in result.stdout


def test_strict_doctor_explains_missing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "REMARKABLE_OPENAI_API_KEY",
        "REMARKABLE_OPENAI_MODEL",
        "REMARKABLE_GMAIL_CREDENTIALS_PATH",
        "REMARKABLE_GMAIL_TOKEN_PATH",
        "REMARKABLE_ALLOWED_SENDERS",
    ):
        monkeypatch.delenv(variable, raising=False)

    result = runner.invoke(app, ["doctor", "--strict"])

    assert result.exit_code != 0
    assert "Missing live integration settings" in result.output


def test_init_db_and_search_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = sqlite_url(tmp_path / "cli.db")
    monkeypatch.setenv("REMARKABLE_DATABASE_URL", database_url)

    initialized = runner.invoke(app, ["init-db"])
    assert initialized.exit_code == 0
    assert "Database initialized" in initialized.stdout

    database = Database(database_url)
    document = database.add_document(
        Document(
            source_message_id="cli-message",
            filename="notes.pdf",
            title="Linear Systems",
            sender="writer@example.com",
            received_at=datetime(2026, 8, 22, tzinfo=UTC),
            raw_pdf_path="data/documents/example.pdf",
        )
    )
    database.add_page(
        Page(document_id=document.id, page_number=3, markdown="Stability depends on eigenvalues")
    )

    get_settings.cache_clear()
    searched = runner.invoke(app, ["search", "eigenvalues"])

    assert searched.exit_code == 0
    assert "2026-08-22 — Linear Systems" in searched.stdout
    assert "Page 3" in searched.stdout
    assert "[eigenvalues]" in searched.stdout
    database.close()


def test_search_without_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REMARKABLE_DATABASE_URL", sqlite_url(tmp_path / "empty.db"))

    result = runner.invoke(app, ["search", "eigenvalues"])

    assert result.exit_code == 0
    assert result.stdout == "No matches.\n"
