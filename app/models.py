"""SQLAlchemy persistence models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative model base."""


class DocumentStatus(StrEnum):
    """Restart-safe document processing lifecycle."""

    RECEIVED = "received"
    RENDERED = "rendered"
    TRANSCRIBED = "transcribed"
    PROCESSED = "processed"
    EXPORTED = "exported"
    REPLIED = "replied"
    FAILED = "failed"


class TimestampMixin:
    """Creation and modification timestamps."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Document(TimestampMixin, Base):
    """One PDF attachment and its combined transcription."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_pdf_path: Mapped[str] = mapped_column(Text, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=32),
        default=DocumentStatus.RECEIVED,
        nullable=False,
    )
    error_summary: Mapped[str | None] = mapped_column(Text)

    pages: Mapped[list[Page]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Page.page_number"
    )
    tasks: Mapped[list[Task]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    def transition_to(self, status: DocumentStatus, error: str | None = None) -> None:
        """Move to a lifecycle state and consistently manage error details."""
        self.status = status
        self.error_summary = error if status is DocumentStatus.FAILED else None


class Page(TimestampMixin, Base):
    """Transcription for one one-based PDF page."""

    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)

    document: Mapped[Document] = relationship(back_populates="pages")


class Task(TimestampMixin, Base):
    """A task extracted from a document."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    source_page: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    document: Mapped[Document] = relationship(back_populates="tasks")


def model_values(instance: Base) -> dict[str, Any]:
    """Return mapped scalar values, primarily for diagnostics and tests."""
    return {column.name: getattr(instance, column.name) for column in instance.__table__.columns}
