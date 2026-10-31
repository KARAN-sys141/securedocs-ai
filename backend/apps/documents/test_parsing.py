import pytest

from apps.documents.exceptions import PermanentProcessingError
from apps.documents.parsing import parse_document
from apps.documents.pdf_factory import build_pdf

PDF = "application/pdf"
TXT = "text/plain"


def test_extracts_text_from_a_pdf():
    parsed = parse_document(build_pdf([["Hello world", "second line"]]), PDF)

    assert parsed.page_count == 1
    assert "Hello world" in parsed.pages[0].text
    assert parsed.pages[0].number == 1


def test_removes_repeated_header_and_page_numbers_from_a_pdf():
    bodies = ["alpha findings", "beta results", "gamma summary", "delta outlook"]
    pages = [["ACME CONFIDENTIAL", body, f"Page {i + 1}"] for i, body in enumerate(bodies)]

    parsed = parse_document(build_pdf(pages), PDF)

    assert parsed.page_count == 4
    for page, body in zip(parsed.pages, bodies, strict=True):
        assert page.text == body


def test_pdf_without_any_text_is_rejected_as_scanned():
    with pytest.raises(PermanentProcessingError, match="No readable text"):
        parse_document(build_pdf([[]]), PDF)


def test_damaged_pdf_is_rejected():
    with pytest.raises(PermanentProcessingError, match="Could not read this PDF"):
        parse_document(b"%PDF-1.4 this is garbage", PDF)


def test_pdf_with_too_many_pages_is_rejected(settings):
    settings.MAX_PDF_PAGES = 2
    data = build_pdf([["one"], ["two"], ["three"]])

    with pytest.raises(PermanentProcessingError, match="too many pages"):
        parse_document(data, PDF)


def test_plain_text_is_parsed_as_one_page():
    parsed = parse_document(b"Hello\nworld", TXT)

    assert parsed.page_count == 1
    assert parsed.pages[0].text == "Hello world"


def test_utf8_byte_order_mark_is_removed():
    parsed = parse_document(b"\xef\xbb\xbfHello", TXT)

    assert parsed.pages[0].text == "Hello"


def test_unsupported_content_type_is_rejected():
    with pytest.raises(PermanentProcessingError, match="not supported"):
        parse_document(b"data", "application/zip")


def test_document_with_too_much_text_is_rejected(settings):
    settings.MAX_DOCUMENT_CHARS = 10

    with pytest.raises(PermanentProcessingError, match="too much text"):
        parse_document(b"this text is longer than ten characters", TXT)
