from django.db import transaction

from .exceptions import PermanentProcessingError
from .models import Document, DocumentPage
from .parsing import parse_document


def read_stored_file(document):
    try:
        with document.file.open("rb") as stored:
            data = stored.read()
    except FileNotFoundError as exc:
        raise PermanentProcessingError("The stored file is missing.") from exc
    if not data:
        raise PermanentProcessingError("The stored file is empty.")
    return data


@transaction.atomic
def save_pages(document, parsed):
    """Replaces the document's pages in one transaction (safe to run twice)."""
    DocumentPage.objects.filter(document=document).delete()
    DocumentPage.objects.bulk_create(
        [
            DocumentPage(
                document=document,
                organization_id=document.organization_id,
                page_number=page.number,
                text=page.text,
            )
            for page in parsed.pages
        ]
    )
    Document.objects.filter(pk=document.pk).update(
        page_count=parsed.page_count,
        char_count=sum(len(page.text) for page in parsed.pages),
    )


def run_pipeline(document):
    """Day 8: read file -> parse -> clean -> save pages.

    Day 9 adds chunking, Day 10 adds embeddings.
    """
    data = read_stored_file(document)
    parsed = parse_document(data, document.content_type)
    save_pages(document, parsed)
