"""Persistence and search tests."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import (
    Database,
    DuplicateMessageError,
    PageTranscriptionConflictError,
    sqlite_url,
)
from app.models import Document, DocumentStatus, Page, Task


@pytest.fixture()
def database(tmp_path: Path) -> Iterator[Database]:
    database = Database(sqlite_url(tmp_path / "test.db"))
    database.initialize()
    yield database
    database.close()


def make_document(message_id: str = "message-1") -> Document:
    return Document(
        source_message_id=message_id,
        filename="notes.pdf",
        title="Differential Equations",
        sender="writer@example.com",
        received_at=datetime(2026, 8, 22, tzinfo=UTC),
        raw_pdf_path="data/documents/test.pdf",
    )


def test_document_page_task_and_lifecycle_persist(database: Database) -> None:
    document = database.add_document(make_document())
    page = database.add_page(
        Page(document_id=document.id, page_number=1, markdown="Stability uses eigenvalues.")
    )
    task = database.add_task(
        Task(document_id=document.id, source_page=1, text="Review complex eigenvalues")
    )
    database.set_status(document.id, DocumentStatus.PROCESSED)

    assert page.id is not None
    assert task.id is not None
    loaded = database.get_document_by_message_id("message-1")
    assert loaded is not None
    assert loaded.status is DocumentStatus.PROCESSED


def test_duplicate_message_is_translated(database: Database) -> None:
    database.add_document(make_document())

    with pytest.raises(DuplicateMessageError, match="message-1"):
        database.add_document(make_document())


def test_page_number_is_unique_per_document(database: Database) -> None:
    document = database.add_document(make_document())
    database.add_page(Page(document_id=document.id, page_number=1, markdown="first"))

    with pytest.raises(IntegrityError):
        database.add_page(Page(document_id=document.id, page_number=1, markdown="duplicate"))


def test_search_returns_ranked_page_excerpt(database: Database) -> None:
    first = database.add_document(make_document())
    second = database.add_document(make_document("message-2"))
    second.title = "Linear Algebra"
    database.add_page(
        Page(
            document_id=first.id,
            page_number=3,
            markdown="For dx/dt = Ax, stability depends on eigenvalues.",
        )
    )
    database.add_page(
        Page(document_id=second.id, page_number=1, markdown="Eigenvectors define directions.")
    )

    results = database.search("stability")

    assert len(results) == 1
    assert results[0].title == "Differential Equations"
    assert results[0].page_number == 3
    assert "[stability]" in results[0].excerpt


def test_search_empty_query_is_empty(database: Database) -> None:
    assert database.search("  ") == []


def test_failed_status_records_error(database: Database) -> None:
    document = database.add_document(make_document())

    database.set_status(document.id, DocumentStatus.FAILED, "transcription timeout")

    loaded = database.get_document_by_message_id("message-1")
    assert loaded is not None
    assert loaded.error_summary == "transcription timeout"


def test_missing_document_status_update_fails(database: Database) -> None:
    with pytest.raises(KeyError):
        database.set_status("missing", DocumentStatus.PROCESSED)


def test_page_transcription_checkpoint_is_idempotent(database: Database) -> None:
    document = database.add_document(make_document())

    first = database.save_page_transcription(document.id, 1, "# First page")
    repeated = database.save_page_transcription(document.id, 1, "# First page")

    assert first.id == repeated.id
    assert database.page_markdown(document.id) == {1: "# First page"}


def test_page_transcription_checkpoint_refuses_overwrite(database: Database) -> None:
    document = database.add_document(make_document())
    database.save_page_transcription(document.id, 1, "Original")

    with pytest.raises(PageTranscriptionConflictError, match="different transcription"):
        database.save_page_transcription(document.id, 1, "Replacement")


@pytest.mark.parametrize(("page_number", "markdown"), [(0, "text"), (1, " ")])
def test_page_transcription_checkpoint_validates_input(
    database: Database, page_number: int, markdown: str
) -> None:
    document = database.add_document(make_document())

    with pytest.raises(ValueError):
        database.save_page_transcription(document.id, page_number, markdown)
