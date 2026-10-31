from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.documents.models import Document
from apps.documents.pdf_factory import build_pdf
from apps.documents.tasks import process_document
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Pass#2026"
PDF_BYTES = build_pdf([["Hello from the test document"]])
User = get_user_model()


@pytest.fixture
def org():
    return Organization.objects.create(name="Acme", slug="acme")


def make_document(org, status=Document.Status.PENDING, content=PDF_BYTES, **extra):
    return Document.objects.create(
        organization=org,
        title="Policy",
        original_filename="policy.pdf",
        content_type="application/pdf",
        file=SimpleUploadedFile("policy.pdf", content),
        status=status,
        **extra,
    )


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


def test_pending_document_becomes_ready(org):
    document = make_document(org)

    assert process_document(str(document.id)) == "ready"

    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert document.processing_started_at is None


def test_empty_file_fails_permanently_with_a_clear_message(org):
    document = make_document(org, content=b"")

    assert process_document(str(document.id)) == "failed"

    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert document.error_message == "The stored file is empty."


def test_missing_file_fails_permanently(org):
    document = make_document(org)
    document.file.storage.delete(document.file.name)

    assert process_document(str(document.id)) == "failed"

    document.refresh_from_db()
    assert document.error_message == "The stored file is missing."


def test_task_is_idempotent_a_ready_document_is_skipped(org):
    document = make_document(org, status=Document.Status.READY)

    assert process_document(str(document.id)) == "skipped"


def test_fresh_processing_document_cannot_be_claimed_twice(org):
    document = make_document(
        org,
        status=Document.Status.PROCESSING,
        processing_started_at=timezone.now(),
    )

    assert process_document(str(document.id)) == "skipped"

    document.refresh_from_db()
    assert document.status == Document.Status.PROCESSING


def test_stale_processing_document_is_picked_up_again(org):
    document = make_document(
        org,
        status=Document.Status.PROCESSING,
        processing_started_at=timezone.now() - timedelta(minutes=60),
    )

    assert process_document(str(document.id)) == "ready"


def test_deleted_document_is_skipped(org):
    document = make_document(org)
    document_id = str(document.id)
    document.delete()

    assert process_document(document_id) == "skipped"


def test_transient_error_after_last_retry_marks_failed(org, monkeypatch):
    from apps.documents import tasks
    from apps.documents.exceptions import TransientProcessingError

    def always_fails(document):
        raise TransientProcessingError("api limit")

    monkeypatch.setattr(tasks, "run_pipeline", always_fails)
    document = make_document(org)

    result = process_document.apply(args=[str(document.id)], retries=3)

    assert result.result == "failed"
    document.refresh_from_db()
    assert document.status == Document.Status.FAILED


def test_unexpected_error_marks_failed_without_leaking_details(org, monkeypatch):
    from apps.documents import tasks

    def boom(document):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(tasks, "run_pipeline", boom)
    document = make_document(org)

    assert process_document(str(document.id)) == "failed"

    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert "secret" not in document.error_message


def test_upload_queues_processing_after_commit(org, django_capture_on_commit_callbacks):
    client = make_client("bob", Membership.Role.MEMBER, org)
    file = SimpleUploadedFile("policy.pdf", PDF_BYTES, content_type="application/pdf")

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post("/api/documents/", {"file": file}, format="multipart")

    assert response.status_code == 201
    document = Document.objects.get(pk=response.json()["id"])
    assert document.status == Document.Status.READY


def test_reprocess_resets_a_failed_document(org, django_capture_on_commit_callbacks):
    client = make_client("olivia", Membership.Role.OWNER, org)
    document = make_document(org, status=Document.Status.FAILED, error_message="old error")

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(f"/api/documents/{document.id}/reprocess/")

    assert response.status_code == 202
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert document.error_message == ""


def test_reprocess_is_refused_for_a_ready_document(org):
    client = make_client("olivia", Membership.Role.OWNER, org)
    document = make_document(org, status=Document.Status.READY)

    response = client.post(f"/api/documents/{document.id}/reprocess/")

    assert response.status_code == 409


def test_plain_member_cannot_reprocess_a_document_they_cannot_see(org):
    client = make_client("bob", Membership.Role.MEMBER, org)
    document = make_document(
        org, status=Document.Status.FAILED, visibility=Document.Visibility.RESTRICTED
    )

    response = client.post(f"/api/documents/{document.id}/reprocess/")

    assert response.status_code == 404
