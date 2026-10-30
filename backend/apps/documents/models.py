import uuid

from django.conf import settings
from django.db import models
from pgvector.django import VectorField

from apps.core.models import TimeStampedModel
from apps.organizations.models import Organization

# Size of each embedding vector. We will request this size from the embedding API on Day 10.
EMBEDDING_DIMENSIONS = 768


def document_upload_path(instance, filename):
    """Saves files as org_<id>/<document-id>_<filename>."""
    return f"org_{instance.organization_id}/{instance.id}_{filename}"


class Document(TimeStampedModel):
    """A file uploaded by a company."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    class Visibility(models.TextChoices):
        ORGANIZATION = "organization", "Whole organization"
        RESTRICTED = "restricted", "Restricted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_documents",
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    visibility = models.CharField(
        max_length=14,
        choices=Visibility.choices,
        default=Visibility.ORGANIZATION,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self):
        return self.title


class Chunk(models.Model):
    """A small piece of a document, with its embedding for similarity search."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="unique_chunk_index_per_document",
            )
        ]
        indexes = [models.Index(fields=["organization", "document"])]

    def save(self, *args, **kwargs):
        # Safety net: a chunk always belongs to the same organization as its document.
        self.organization_id = self.document.organization_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.document_id} #{self.chunk_index}"


class DocumentAccess(TimeStampedModel):
    """Gives one user permission to see one restricted document."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="access_grants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_grants",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "user"],
                name="unique_grant_per_document_user",
            )
        ]

    def __str__(self):
        return f"{self.user} -> {self.document}"
