"""SQLite persistence, schema initialization, and full-text search."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Document, DocumentStatus, Page, Task

SCHEMA_VERSION = 1


class DuplicateMessageError(ValueError):
    """Raised when an already-known source message is inserted."""


class SearchUnavailableError(RuntimeError):
    """Raised when the local SQLite build lacks FTS5."""


@dataclass(frozen=True)
class SearchResult:
    """One page-level full-text search match."""

    document_id: str
    title: str
    received_at: datetime
    page_number: int
    excerpt: str


def create_database_engine(database_url: str) -> Engine:
    """Create an engine with SQLite safety defaults."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


class Database:
    """Small unit-of-work facade around SQLAlchemy and SQLite FTS5."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_database_engine(database_url)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def initialize(self) -> None:
        """Create versioned schema and FTS synchronization triggers."""
        Base.metadata.create_all(self.engine)
        statements = (
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)",
            "INSERT INTO schema_version(version) SELECT 1 WHERE NOT EXISTS "
            "(SELECT 1 FROM schema_version)",
            "CREATE VIRTUAL TABLE IF NOT EXISTS page_search USING fts5(markdown, content='pages', "
            "content_rowid='id')",
            "CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN "
            "INSERT INTO page_search(rowid, markdown) VALUES (new.id, new.markdown); END",
            "CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN "
            "INSERT INTO page_search(page_search, rowid, markdown) "
            "VALUES ('delete', old.id, old.markdown); END",
            "CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN "
            "INSERT INTO page_search(page_search, rowid, markdown) "
            "VALUES ('delete', old.id, old.markdown); "
            "INSERT INTO page_search(rowid, markdown) VALUES (new.id, new.markdown); END",
            "INSERT INTO page_search(page_search) VALUES ('rebuild')",
        )
        try:
            with self.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
        except OperationalError as error:
            if "fts5" in str(error).lower():
                raise SearchUnavailableError("SQLite was built without FTS5 support") from error
            raise

    def close(self) -> None:
        """Release pooled database connections."""
        self.engine.dispose()

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Commit on success and roll back on error."""
        session = self._sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_document(self, document: Document) -> Document:
        """Persist a new document, translating uniqueness errors."""
        try:
            with self.session() as session:
                session.add(document)
                session.flush()
        except IntegrityError as error:
            if "source_message_id" in str(error):
                raise DuplicateMessageError(document.source_message_id) from error
            raise
        return document

    def get_document_by_message_id(self, message_id: str) -> Document | None:
        """Find a document by its idempotency key."""
        with self.session() as session:
            return session.scalar(select(Document).where(Document.source_message_id == message_id))

    def add_page(self, page: Page) -> Page:
        with self.session() as session:
            session.add(page)
            session.flush()
        return page

    def add_task(self, task: Task) -> Task:
        with self.session() as session:
            session.add(task)
            session.flush()
        return task

    def set_status(
        self, document_id: str, status: DocumentStatus, error: str | None = None
    ) -> None:
        """Update document processing state."""
        with self.session() as session:
            document = session.get(Document, document_id)
            if document is None:
                raise KeyError(document_id)
            document.transition_to(status, error)

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        """Search page Markdown with FTS5 ranking and highlighted excerpts."""
        if not query.strip():
            return []
        statement = text(
            "SELECT d.id, COALESCE(d.title, d.filename) AS title, d.received_at, "
            "p.page_number, snippet(page_search, 0, '[', ']', ' … ', 18) AS excerpt "
            "FROM page_search JOIN pages p ON p.id = page_search.rowid "
            "JOIN documents d ON d.id = p.document_id "
            "WHERE page_search MATCH :query ORDER BY bm25(page_search), "
            "d.received_at DESC LIMIT :limit"
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement, {"query": query, "limit": limit})
            return [
                SearchResult(
                    document_id=row.id,
                    title=row.title,
                    received_at=datetime.fromisoformat(row.received_at)
                    if isinstance(row.received_at, str)
                    else row.received_at,
                    page_number=row.page_number,
                    excerpt=row.excerpt,
                )
                for row in rows
            ]


def sqlite_url(path: Path) -> str:
    """Build a SQLite URL from an explicit path."""
    return f"sqlite:///{path.resolve()}"
