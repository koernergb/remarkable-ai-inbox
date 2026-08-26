"""Tests for typed application settings."""

from pathlib import Path

import pytest
from pydantic import SecretStr

from app.config import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.data_dir == Path("data")
    assert settings.database_url == "sqlite:///remarkable.db"
    assert settings.openai_api_key is None
    assert settings.allowed_senders == []
    assert settings.obsidian_vault_path is None
    assert settings.obsidian_notes_folder == "Remarkable/Notes"


def test_sender_environment_value_is_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REMARKABLE_ALLOWED_SENDERS", "one@example.com, two@example.com")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.allowed_senders == ["one@example.com", "two@example.com"]


def test_database_credentials_are_redacted() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql://user:password@db.example.com/notes",
        openai_api_key=SecretStr("secret"),
    )

    assert settings.redacted_database_url == "postgresql://***@db.example.com/notes"
    assert "password" not in settings.redacted_database_url


def test_missing_live_settings_are_actionable() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert "REMARKABLE_OPENAI_API_KEY" in settings.missing_live_settings
    assert "REMARKABLE_ALLOWED_SENDERS" in settings.missing_live_settings
    assert "REMARKABLE_OBSIDIAN_VAULT_PATH" in settings.missing_live_settings
