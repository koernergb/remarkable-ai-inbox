"""Typed application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, SecretStr
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_senders(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


SenderList = Annotated[list[str], NoDecode, BeforeValidator(_parse_senders)]


class Settings(BaseSettings):
    """Application settings loaded from ``REMARKABLE_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="REMARKABLE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    database_url: str = "sqlite:///remarkable.db"

    openai_api_key: SecretStr | None = None
    openai_model: str | None = None

    gmail_credentials_path: Path | None = None
    gmail_token_path: Path | None = None
    gmail_inbox_label: str = "remarkable-ai"
    gmail_processed_label: str = "remarkable-ai/processed"
    allowed_senders: SenderList = []

    @property
    def redacted_database_url(self) -> str:
        """Return a safe database description for diagnostics."""
        if "@" not in self.database_url:
            return self.database_url
        scheme, _, location = self.database_url.partition("://")
        _, _, host = location.rpartition("@")
        return f"{scheme}://***@{host}"

    @property
    def missing_live_settings(self) -> list[str]:
        """List configuration that will be required for live integrations."""
        values = {
            "REMARKABLE_OPENAI_API_KEY": self.openai_api_key,
            "REMARKABLE_OPENAI_MODEL": self.openai_model,
            "REMARKABLE_GMAIL_CREDENTIALS_PATH": self.gmail_credentials_path,
            "REMARKABLE_GMAIL_TOKEN_PATH": self.gmail_token_path,
            "REMARKABLE_ALLOWED_SENDERS": self.allowed_senders,
        }
        return [name for name, value in values.items() if not value]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings for the process lifetime."""
    return Settings()
