import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.models import Document, DocumentPage
from apps.documents.pdf_factory import build_pdf
from apps.documents.tasks import process_document
from apps.organizations.models import Organization

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Acme", slug="acme")


def make_document(org, content):
    return Document.objects.create(
        organization=org,
        title="Report",
        original_filename="report.pdf",
        content_type="application/pdf",
        file=SimpleUploadedFile("report.pdf", content),
    )


def test_processing_saves_pages_and_counts(org):
    document = make_document(org, build_pdf([["First page text"], ["Second page text"]]))

    assert process_document(str(document.id)) == "ready"

    document.refresh_from_db()
    assert document.page_count == 2
    assert document.char_count == len("First page text") + len("Second page text")
    pages = list(DocumentPage.objects.filter(document=document))
    assert [page.page_number for page in pages] == [1, 2]
    assert all(page.organization_id == org.id for page in pages)


def test_reprocessing_replaces_pages_instead_of_duplicating_them(org):
    document = make_document(org, build_pdf([["First page text"], ["Second page text"]]))
    process_document(str(document.id))

    Document.objects.filter(pk=document.pk).update(status=Document.Status.PENDING)
    process_document(str(document.id))

    assert DocumentPage.objects.filter(document=document).count() == 2


def test_scanned_pdf_fails_with_a_clear_message(org):
    document = make_document(org, build_pdf([[]]))

    assert process_document(str(document.id)) == "failed"

    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert document.error_message.startswith("No readable text")
    assert DocumentPage.objects.filter(document=document).count() == 0


def test_deleting_a_document_deletes_its_pages(org):
    document = make_document(org, build_pdf([["Some text"]]))
    process_document(str(document.id))

    document.delete()

    assert DocumentPage.objects.count() == 0
