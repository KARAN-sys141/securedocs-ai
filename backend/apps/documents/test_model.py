import pytest

from apps.documents.models import Chunk, Document
from apps.organizations.models import Organization

pytestmark = pytest.mark.django_db


def test_chunk_copies_organization_from_its_document():
    org = Organization.objects.create(name="Acme", slug="acme")
    doc = Document.objects.create(
        organization=org, title="Leave Policy", original_filename="leave.pdf"
    )
    chunk = Chunk.objects.create(document=doc, chunk_index=0, content="Employees get 20 leaves.")

    assert chunk.organization_id == org.id
