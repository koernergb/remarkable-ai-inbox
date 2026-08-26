"""Safe, atomic export of transcriptions into an Obsidian vault."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class VaultConfigurationError(ValueError):
    """Raised when a vault destination is missing or unsafe."""


class ExportConflictError(RuntimeError):
    """Raised rather than overwriting user-edited or unrelated vault content."""


@dataclass(frozen=True)
class TranscribedPage:
    """One one-based page of Markdown."""

    page_number: int
    markdown: str


@dataclass(frozen=True)
class ObsidianExport:
    """Input required to create one vault note and attachment."""

    document_id: str
    source_message_id: str
    title: str
    received_at: datetime
    source_pdf: Path
    pages: tuple[TranscribedPage, ...]


@dataclass(frozen=True)
class ExportResult:
    """Vault-relative export paths and whether files were newly written."""

    note_path: Path
    attachment_path: Path
    created: bool


_UNSAFE_TITLE = re.compile(r'[<>:"/\\|?*#\[\]^\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")


def safe_title(value: str, maximum_length: int = 80) -> str:
    """Create a readable filename component from untrusted title text."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _UNSAFE_TITLE.sub("-", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip(" .-")
    return normalized[:maximum_length].rstrip(" .-") or "Untitled"


def _safe_relative_folder(value: str) -> Path:
    folder = Path(value)
    if (
        folder.is_absolute()
        or not folder.parts
        or any(part in {"", ".", ".."} for part in folder.parts)
    ):
        raise VaultConfigurationError(f"Vault folder must be a safe relative path: {value!r}")
    return folder


def _within(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _atomic_write(destination: Path, contents: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _render_note(item: ObsidianExport, attachment_path: Path, tag: str) -> str:
    if not item.pages:
        raise ValueError("At least one transcribed page is required")
    numbers = [page.page_number for page in item.pages]
    if numbers != sorted(set(numbers)) or numbers[0] < 1:
        raise ValueError("Page numbers must be unique, positive, and ordered")

    properties = (
        "---\n"
        "source: remarkable\n"
        f"received: {json.dumps(item.received_at.isoformat())}\n"
        f"source_message_id: {json.dumps(item.source_message_id)}\n"
        f"document_id: {json.dumps(item.document_id)}\n"
        f"original: {json.dumps(f'[[{attachment_path.as_posix()}]]')}\n"
        "tags:\n"
        f"  - {json.dumps(tag)}\n"
        "---\n"
    )
    sections = [
        f"<!-- remarkable-page: {page.page_number} -->\n\n{page.markdown.strip()}"
        for page in item.pages
    ]
    return f"{properties}\n# {item.title.strip() or 'Untitled'}\n\n" + "\n\n".join(sections) + "\n"


class ObsidianExporter:
    """Export notes without touching Obsidian configuration or overwriting edits."""

    def __init__(
        self,
        vault_root: Path,
        notes_folder: str = "Remarkable/Notes",
        attachments_folder: str = "Remarkable/Attachments",
        default_tag: str = "remarkable",
    ) -> None:
        if not vault_root.is_dir():
            raise VaultConfigurationError("Obsidian vault root must be an existing directory")
        self.vault_root = vault_root.resolve()
        self.notes_folder = _safe_relative_folder(notes_folder)
        self.attachments_folder = _safe_relative_folder(attachments_folder)
        self.default_tag = default_tag.strip()
        if not self.default_tag or any(character.isspace() for character in self.default_tag):
            raise VaultConfigurationError("Default tag must be a non-empty tag without whitespace")

    def _prepare_folder(self, relative: Path) -> Path:
        destination = self.vault_root / relative
        destination.mkdir(parents=True, exist_ok=True)
        resolved = destination.resolve()
        if not _within(self.vault_root, resolved):
            raise VaultConfigurationError("Configured folder resolves outside the vault")
        return resolved

    def export(self, item: ObsidianExport) -> ExportResult:
        """Create or idempotently recognize one Markdown/PDF pair."""
        if not item.source_pdf.is_file():
            raise FileNotFoundError(item.source_pdf)
        notes_directory = self._prepare_folder(self.notes_folder)
        attachments_directory = self._prepare_folder(self.attachments_folder)
        digest = hashlib.sha256(item.source_message_id.encode()).hexdigest()[:8]
        stem = f"{item.received_at:%Y-%m-%d} {safe_title(item.title)}--{digest}"
        note_relative = self.notes_folder / f"{stem}.md"
        attachment_relative = self.attachments_folder / f"{stem}.pdf"
        note_destination = notes_directory / note_relative.name
        attachment_destination = attachments_directory / attachment_relative.name

        note_bytes = _render_note(item, attachment_relative, self.default_tag).encode("utf-8")
        pdf_bytes = item.source_pdf.read_bytes()
        targets = ((note_destination, note_bytes), (attachment_destination, pdf_bytes))
        for destination, expected in targets:
            if destination.exists() and destination.read_bytes() != expected:
                raise ExportConflictError(
                    f"Refusing to overwrite changed vault file: {destination}"
                )

        created = any(not destination.exists() for destination, _ in targets)
        if not attachment_destination.exists():
            _atomic_write(attachment_destination, pdf_bytes)
        if not note_destination.exists():
            _atomic_write(note_destination, note_bytes)
        return ExportResult(note_relative, attachment_relative, created)
