"""CLI smoke tests."""

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.config import get_settings

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
