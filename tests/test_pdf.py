"""PDF validation, storage, and rendering tests."""

from pathlib import Path

import pymupdf
import pytest

from app.pdf import PdfLimits, PdfValidationError, render_pages, store_pdf, validate_pdf


def make_pdf(path: Path, pages: int = 1) -> Path:
    document = pymupdf.open()
    for number in range(1, pages + 1):
        page = document.new_page(width=200, height=300)
        page.insert_text((20, 30), f"Page {number}: eigenvalues")
    document.save(path)
    document.close()
    return path


def test_validate_and_render_multiple_pages(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "notes with spaces.pdf", pages=3)

    assert validate_pdf(source) == 3
    with render_pages(source, PdfLimits(render_dpi=72), tmp_path) as pages:
        paths = [page.image_path for page in pages]
        assert [page.page_number for page in pages] == [1, 2, 3]
        assert [path.name for path in paths] == [
            "page_0001.png",
            "page_0002.png",
            "page_0003.png",
        ]
        assert all(path.exists() for path in paths)
        assert all(page.width == 200 and page.height == 300 for page in pages)

    assert all(not path.exists() for path in paths)


@pytest.mark.parametrize(
    ("contents", "message"),
    [(b"", "empty"), (b"not a pdf", "signature"), (b"%PDF-corrupt", "corrupt")],
)
def test_invalid_pdfs_are_rejected(tmp_path: Path, contents: bytes, message: str) -> None:
    source = tmp_path / "bad.pdf"
    source.write_bytes(contents)

    with pytest.raises(PdfValidationError, match=message):
        validate_pdf(source)


def test_missing_pdf_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PdfValidationError, match="does not exist"):
        validate_pdf(tmp_path / "missing.pdf")


def test_resource_limits_are_enforced(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "notes.pdf", pages=2)

    with pytest.raises(PdfValidationError, match="byte limit"):
        validate_pdf(source, PdfLimits(max_bytes=10))
    with pytest.raises(PdfValidationError, match="page limit"):
        validate_pdf(source, PdfLimits(max_pages=1))


def test_store_pdf_uses_uuid_not_untrusted_filename(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / ".. evil ünicode.pdf")
    document_id = "1bf5f45d-d127-4403-93e7-7cbda1a5df55"

    stored = store_pdf(source, tmp_path / "documents", document_id)

    assert stored.name == f"{document_id}.pdf"
    assert stored.read_bytes() == source.read_bytes()


def test_store_pdf_rejects_non_uuid_identifier(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "notes.pdf")

    with pytest.raises(ValueError):
        store_pdf(source, tmp_path / "documents", "../escape")
