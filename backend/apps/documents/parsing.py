import logging
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from pypdf import PdfReader

from .cleaning import clean_text, remove_boilerplate
from .exceptions import PermanentProcessingError

logger = logging.getLogger(__name__)

NO_TEXT_MESSAGE = "No readable text was found. Scanned documents need OCR, which is not supported."


@dataclass
class ParsedPage:
    number: int
    text: str


@dataclass
class ParsedDocument:
    page_count: int  # pages in the original file, including empty ones
    pages: list  # only pages that contain text


def _try_decrypt(reader):
    """Some PDFs are 'encrypted' with an empty password. Try that, nothing else."""
    try:
        return bool(reader.decrypt(""))
    except Exception:
        return False


def extract_pdf_pages(data):
    """Returns a list with the raw text of every page."""
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted and not _try_decrypt(reader):
            raise PermanentProcessingError("Password-protected PDFs are not supported.")
        total_pages = len(reader.pages)
    except PermanentProcessingError:
        raise
    except Exception as exc:
        raise PermanentProcessingError("Could not read this PDF. It may be damaged.") from exc

    if total_pages > settings.MAX_PDF_PAGES:
        raise PermanentProcessingError(
            f"This PDF has too many pages (the limit is {settings.MAX_PDF_PAGES})."
        )

    texts = []
    for index in range(total_pages):
        try:
            texts.append(reader.pages[index].extract_text() or "")
        except Exception:
            # One bad page should not lose the whole document
            logger.warning("Could not extract page %s", index + 1, exc_info=True)
            texts.append("")
    return texts


def build_parsed_document(raw_pages, strip_boilerplate):
    if strip_boilerplate:
        raw_pages = remove_boilerplate(raw_pages)

    pages = []
    total_chars = 0
    for number, raw_text in enumerate(raw_pages, start=1):
        text = clean_text(raw_text)
        if not text:
            continue
        total_chars += len(text)
        if total_chars > settings.MAX_DOCUMENT_CHARS:
            raise PermanentProcessingError("This document contains too much text.")
        pages.append(ParsedPage(number=number, text=text))

    if not pages:
        raise PermanentProcessingError(NO_TEXT_MESSAGE)
    return ParsedDocument(page_count=len(raw_pages), pages=pages)


def parse_document(data, content_type):
    """Turns the bytes of an uploaded file into cleaned pages."""
    if content_type == "application/pdf":
        return build_parsed_document(extract_pdf_pages(data), strip_boilerplate=True)
    if content_type == "text/plain":
        text = data.decode("utf-8-sig", errors="replace")  # utf-8-sig drops a BOM
        return build_parsed_document([text], strip_boilerplate=False)
    raise PermanentProcessingError("This file type is not supported.")
