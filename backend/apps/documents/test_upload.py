import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.documents.models import Document
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Pass#2026"
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
User = get_user_model()


@pytest.fixture
def org():
    return Organization.objects.create(name="Acme", slug="acme")


def make_client(username, role, org):
    user = User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD
    )
    Membership.objects.create(user=user, organization=org, role=role)
    client = APIClient()
    response = client.post(
        "/api/auth/login/", {"username": username, "password": PASSWORD}, format="json"
    )
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    return client


def upload(client, name="policy.pdf", content=PDF_BYTES, **extra):
    file = SimpleUploadedFile(name, content, content_type="application/pdf")
    return client.post("/api/documents/", {"file": file, **extra}, format="multipart")


def test_member_can_upload_pdf_and_it_is_restricted_by_default(org):
    client = make_client("bob", Membership.Role.MEMBER, org)
    response = upload(client)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["visibility"] == "restricted"
    assert data["title"] == "policy.pdf"
    assert data["size_bytes"] == len(PDF_BYTES)

    document = Document.objects.get(pk=data["id"])
    assert document.content_hash != ""
    assert document.file.storage.exists(document.file.name)


def test_uploader_can_choose_organization_visibility(org):
    client = make_client("olivia", Membership.Role.OWNER, org)
    response = upload(client, visibility="organization")

    assert response.status_code == 201
    assert response.json()["visibility"] == "organization"


def test_fake_pdf_is_rejected(org):
    client = make_client("bob", Membership.Role.MEMBER, org)
    response = upload(client, name="fake.pdf", content=b"hello world")

    assert response.status_code == 400
    assert Document.objects.count() == 0


def test_disallowed_extension_is_rejected(org):
    client = make_client("bob", Membership.Role.MEMBER, org)
    assert upload(client, name="malware.exe").status_code == 400


def test_binary_data_in_a_txt_file_is_rejected(org):
    client = make_client("bob", Membership.Role.MEMBER, org)
    assert upload(client, name="notes.txt", content=b"\x00\x01\x02").status_code == 400


def test_empty_file_is_rejected(org):
    client = make_client("bob", Membership.Role.MEMBER, org)
    assert upload(client, content=b"").status_code == 400


def test_file_over_size_limit_is_rejected(org, settings):
    settings.MAX_UPLOAD_SIZE_BYTES = 10
    client = make_client("bob", Membership.Role.MEMBER, org)

    assert upload(client).status_code == 413


def test_organization_storage_quota_is_enforced(org, settings):
    settings.MAX_ORG_STORAGE_BYTES = len(PDF_BYTES) + 5
    client = make_client("bob", Membership.Role.MEMBER, org)

    assert upload(client).status_code == 201
    assert upload(client, name="second.pdf", content=PDF_BYTES + b"x").status_code == 413


def test_same_file_twice_is_rejected_as_duplicate(org):
    client = make_client("bob", Membership.Role.MEMBER, org)

    assert upload(client).status_code == 201
    assert upload(client, name="copy.pdf").status_code == 409


def test_duplicate_of_a_document_you_cannot_see_is_allowed(org):
    owner = make_client("olivia", Membership.Role.OWNER, org)
    bob = make_client("bob", Membership.Role.MEMBER, org)

    assert upload(owner).status_code == 201  # restricted, so bob cannot see it
    assert upload(bob).status_code == 201  # no hint that the file already exists


def test_folder_tricks_in_file_names_are_removed(org):
    client = make_client("bob", Membership.Role.MEMBER, org)
    response = upload(client, name="../../evil.pdf")

    assert response.status_code == 201
    assert response.json()["title"] == "evil.pdf"


def test_delete_removes_the_row_and_the_file(org):
    client = make_client("olivia", Membership.Role.OWNER, org)
    doc_id = upload(client).json()["id"]
    document = Document.objects.get(pk=doc_id)
    storage, file_name = document.file.storage, document.file.name

    assert client.delete(f"/api/documents/{doc_id}/").status_code == 204
    assert not Document.objects.filter(pk=doc_id).exists()
    assert not storage.exists(file_name)


def test_plain_member_cannot_delete_someone_elses_document(org):
    owner = make_client("olivia", Membership.Role.OWNER, org)
    bob = make_client("bob", Membership.Role.MEMBER, org)
    doc_id = upload(owner, visibility="organization").json()["id"]

    assert bob.delete(f"/api/documents/{doc_id}/").status_code == 403
    assert Document.objects.filter(pk=doc_id).exists()


def test_upload_requires_login():
    file = SimpleUploadedFile("policy.pdf", PDF_BYTES)
    response = APIClient().post("/api/documents/", {"file": file}, format="multipart")

    assert response.status_code == 401
