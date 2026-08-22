"""Safe PDF intake and page rendering."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pymupdf


class PdfValidationError(ValueError):
    """Raised when an attachment is not an acceptable PDF."""


@dataclass(frozen=True)
class PdfLimits:
    """Resource limits applied before rendering."""

    max_bytes: int = 25 * 1024 * 1024
    max_pages: int = 100
    render_dpi: int = 150


DEFAULT_PDF_LIMITS = PdfLimits()


@dataclass(frozen=True)
class RenderedPage:
    """One rendered, one-based page image."""

    page_number: int
    image_path: Path
    width: int
    height: int


def validate_pdf(path: Path, limits: PdfLimits = DEFAULT_PDF_LIMITS) -> int:
    """Validate signature, size, encryption, page count, and readability."""
    if not path.is_file():
        raise PdfValidationError("PDF does not exist or is not a regular file")
    size = path.stat().st_size
    if size == 0:
        raise PdfValidationError("PDF is empty")
    if size > limits.max_bytes:
        raise PdfValidationError(f"PDF exceeds the {limits.max_bytes}-byte limit")
    with path.open("rb") as source:
        if source.read(5) != b"%PDF-":
            raise PdfValidationError("Attachment does not have a PDF signature")
    try:
        with pymupdf.open(path) as document:
            if document.needs_pass:
                raise PdfValidationError("Encrypted PDFs are not supported")
            page_count = cast(int, document.page_count)
            if page_count < 1:
                raise PdfValidationError("PDF contains no pages")
            if page_count > limits.max_pages:
                raise PdfValidationError(f"PDF exceeds the {limits.max_pages}-page limit")
            document.load_page(0)
    except PdfValidationError:
        raise
    except (RuntimeError, ValueError) as error:
        raise PdfValidationError("PDF is corrupt or unreadable") from error
    return page_count


def store_pdf(source: Path, documents_dir: Path, document_id: str | None = None) -> Path:
    """Copy a validated PDF to a UUID-derived path inside the data directory."""
    resolved_directory = documents_dir.resolve()
    resolved_directory.mkdir(parents=True, exist_ok=True)
    safe_id = str(uuid.UUID(document_id)) if document_id else str(uuid.uuid4())
    destination = (resolved_directory / f"{safe_id}.pdf").resolve()
    if destination.parent != resolved_directory:
        raise PdfValidationError("Resolved PDF path escaped the document directory")
    shutil.copyfile(source, destination)
    return destination


@contextmanager
def render_pages(
    pdf_path: Path,
    limits: PdfLimits = DEFAULT_PDF_LIMITS,
    temporary_root: Path | None = None,
) -> Iterator[list[RenderedPage]]:
    """Yield ordered PNG pages and remove them when the context exits."""
    validate_pdf(pdf_path, limits)
    with tempfile.TemporaryDirectory(prefix="remarkable-pages-", dir=temporary_root) as directory:
        rendered: list[RenderedPage] = []
        try:
            with pymupdf.open(pdf_path) as document:
                matrix = pymupdf.Matrix(limits.render_dpi / 72, limits.render_dpi / 72)
                for index, page in enumerate(document):
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False, colorspace=pymupdf.csRGB)
                    image_path = Path(directory) / f"page_{index + 1:04d}.png"
                    pixmap.save(image_path)
                    rendered.append(
                        RenderedPage(
                            page_number=index + 1,
                            image_path=image_path,
                            width=pixmap.width,
                            height=pixmap.height,
                        )
                    )
            yield rendered
        finally:
            rendered.clear()
