"""Obsidian vault export tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.obsidian import (
    ExportConflictError,
    ObsidianExport,
    ObsidianExporter,
    TranscribedPage,
    VaultConfigurationError,
    safe_title,
)


def make_item(tmp_path: Path) -> ObsidianExport:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-synthetic-test")
    return ObsidianExport(
        document_id="document-1",
        source_message_id="gmail-message-1",
        title="Linear Systems / Stability",
        received_at=datetime(2026, 8, 26, 14, 30, tzinfo=UTC),
        source_pdf=pdf,
        pages=(
            TranscribedPage(1, "Eigenvalues determine stability."),
            TranscribedPage(2, "Why do complex values oscillate?"),
        ),
    )


def test_export_creates_linked_note_and_pdf(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    exporter = ObsidianExporter(vault)

    result = exporter.export(make_item(tmp_path))

    assert result.created is True
    note = (vault / result.note_path).read_text()
    assert result.note_path.as_posix().startswith("Remarkable/Notes/")
    assert (vault / result.attachment_path).read_bytes() == b"%PDF-synthetic-test"
    assert f'original: "[[{result.attachment_path.as_posix()}]]"' in note
    assert "<!-- remarkable-page: 1 -->" in note
    assert "<!-- remarkable-page: 2 -->" in note
    assert "# Linear Systems / Stability" in note


def test_repeat_export_is_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    exporter = ObsidianExporter(vault)
    item = make_item(tmp_path)

    first = exporter.export(item)
    second = exporter.export(item)

    assert first.note_path == second.note_path
    assert second.created is False
    assert len(list(vault.rglob("*.md"))) == 1
    assert len(list(vault.rglob("*.pdf"))) == 1


def test_changed_note_is_never_overwritten(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    exporter = ObsidianExporter(vault)
    item = make_item(tmp_path)
    result = exporter.export(item)
    note = vault / result.note_path
    note.write_text(note.read_text() + "\nMy edit.\n")

    with pytest.raises(ExportConflictError, match="Refusing to overwrite"):
        exporter.export(item)

    assert note.read_text().endswith("My edit.\n")


@pytest.mark.parametrize("folder", ["../outside", "/absolute", "."])
def test_unsafe_configured_folder_is_rejected(tmp_path: Path, folder: str) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    with pytest.raises(VaultConfigurationError, match="safe relative path"):
        ObsidianExporter(vault, notes_folder=folder)


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    outside = tmp_path / "outside"
    vault.mkdir()
    outside.mkdir()
    (vault / "Remarkable").symlink_to(outside, target_is_directory=True)
    exporter = ObsidianExporter(vault)

    with pytest.raises(VaultConfigurationError, match="outside the vault"):
        exporter.export(make_item(tmp_path))


def test_missing_vault_and_source_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(VaultConfigurationError, match="existing directory"):
        ObsidianExporter(tmp_path / "missing")

    vault = tmp_path / "vault"
    vault.mkdir()
    item = make_item(tmp_path)
    item.source_pdf.unlink()
    with pytest.raises(FileNotFoundError):
        ObsidianExporter(vault).export(item)


def test_page_numbers_must_be_positive_unique_and_ordered(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    item = make_item(tmp_path)
    invalid = ObsidianExport(
        document_id=item.document_id,
        source_message_id=item.source_message_id,
        title=item.title,
        received_at=item.received_at,
        source_pdf=item.source_pdf,
        pages=(TranscribedPage(2, "two"), TranscribedPage(1, "one")),
    )

    with pytest.raises(ValueError, match="unique, positive, and ordered"):
        ObsidianExporter(vault).export(invalid)


def test_safe_title_handles_unicode_and_unsafe_characters() -> None:
    assert safe_title("  Café: vectors / matrices?  ") == "Café- vectors - matrices"
    assert safe_title("***") == "Untitled"
