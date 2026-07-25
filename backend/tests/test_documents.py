import io

import pytest

from ada.services.documents import (
    UnsupportedDocument,
    _extension,
    _extract,
    process_cv_upload,
)

CV_TEXT = "Senior Backend Engineer with eight years of Python and Postgres experience."


def _docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf_bytes(text: str) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_extension_parsing():
    assert _extension("cv.PDF") == ".pdf"
    assert _extension("archive.tar.gz") == ".gz"
    assert _extension("noext") == ""


def test_extract_txt():
    assert _extract("cv.txt", CV_TEXT.encode()) == CV_TEXT


def test_extract_docx_paragraphs():
    text = _extract("cv.docx", _docx_bytes([CV_TEXT, "Led a team of five."]))
    assert CV_TEXT in text
    assert "Led a team of five." in text


def test_extract_rejects_unknown_extension():
    with pytest.raises(UnsupportedDocument, match="unsupported file type"):
        _extract("cv.rtf", CV_TEXT.encode())


def test_extract_rejects_missing_extension():
    with pytest.raises(UnsupportedDocument, match="no extension"):
        _extract("cv", CV_TEXT.encode())


def test_extract_rejects_too_little_text():
    with pytest.raises(UnsupportedDocument, match="couldn't read enough text"):
        _extract("cv.txt", b"short")


def test_extract_rejects_scanned_pdf():
    with pytest.raises(UnsupportedDocument, match="couldn't read enough text"):
        _extract("cv.pdf", _pdf_bytes(CV_TEXT))


async def test_process_cv_upload_returns_text_without_bucket(monkeypatch):
    # Isolate from local .env: force "no bucket configured" regardless of dev setup.
    from ada.services import documents

    monkeypatch.setattr(documents, "_store", lambda *a: None)
    text, gcs_uri = await process_cv_upload("user-1", "cv.txt", CV_TEXT.encode(), "text/plain")
    assert text == CV_TEXT
    assert gcs_uri is None


async def test_process_cv_upload_survives_archive_failure(monkeypatch):
    from ada.services import documents

    def boom(*args: object) -> str:
        raise RuntimeError("gcs down")

    monkeypatch.setattr(documents, "_store", boom)
    text, gcs_uri = await process_cv_upload("user-1", "cv.txt", CV_TEXT.encode(), "text/plain")
    assert text == CV_TEXT
    assert gcs_uri is None
